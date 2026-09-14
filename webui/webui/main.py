"""FastAPI application factory (Phase 7 webui).

Serves the static chat shell and proxies ``/api/*`` to the orchestration
service so the browser talks to a single origin (no CORS anywhere; the same
path-routing model carries to the GCP deployment, where an HTTPS load
balancer routes ``/api`` instead). The proxy is a pure pass-through: no
business logic, no persistence, no header mutation beyond the client-hop
headers the API contract defines (Idempotency-Key, X-Correlation-Id,
X-User-Id — the anonymous per-user scoping key, D24-3) plus the proxy-hop
ID token when the deployed tier gates orchestration behind Cloud Run IAM
(ORCHESTRATION_ID_TOKEN_AUTH).
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from posixpath import normpath

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .config import Settings
from . import id_tokens
from .structured_logging import configure_logging

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_FORWARDED_METHODS = ["GET", "POST"]
_FORWARDED_HEADERS = ["content-type", "idempotency-key", "x-correlation-id", "x-user-id"]


def create_app(
    settings: Settings | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Build the webui app; tests may inject settings and an httpx transport
    (which stands in for the real orchestration endpoint)."""
    resolved = settings or Settings.from_env()
    configure_logging("webui")
    client = httpx.AsyncClient(
        base_url=resolved.orchestration_base_url,
        transport=transport,
        # No client timeout: the server deadline governs (turns run up to
        # the 5-minute request deadline / 6-minute lease; a client-side
        # read timeout would surface a live turn as a retryable 503 and
        # set up a same-key retry against the in-flight one).
        timeout=httpx.Timeout(None),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Own the proxy client's connection pool for the app's lifetime."""
        try:
            yield
        finally:
            await client.aclose()

    app = FastAPI(
        title="story-review webui", version="0.1.0", lifespan=lifespan
    )
    app.state.settings = resolved
    app.state.orchestration_client = client

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness only — the webui has no dependencies of its own;
        orchestration reachability is observable through any proxied read
        (e.g. `GET /api/v1/stories`; orchestration's own /health lives
        outside the /api prefix)."""
        return {"status": "ok"}

    @app.api_route("/api/{path:path}", methods=_FORWARDED_METHODS)
    async def proxy(path: str, request: Request) -> Response:
        """Forward one request to orchestration verbatim and return its
        response (status, body, content type, correlation id).

        Side effects: one upstream HTTP call per proxied request.
        Errors: unreachable orchestration → 503 with an error envelope
        (the client retries the same logical request with the same key);
        paths whose decoded form escapes the /api/ prefix → 404 (the
        proxy is /api-scoped, mirroring the deployment's path routing).
        """
        if normpath(request.url.path) != request.url.path or not request.url.path.startswith(
            "/api/"
        ):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        headers = {
            name: value
            for name, value in request.headers.items()
            if name.lower() in _FORWARDED_HEADERS
        }
        if resolved.orchestration_id_token_auth:
            # IAM-gated orchestration (deployed tier): attach the
            # audience-scoped ID token. A mint failure is an environment
            # problem surfaced like unreachability — retryable 503.
            try:
                headers.update(id_tokens.metadata_id_token(resolved.orchestration_base_url))
            except OSError:
                correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": {
                            "code": "ORCHESTRATION_UNREACHABLE",
                            "message": "orchestration service is not reachable",
                            "correlation_id": correlation_id,
                            "retryable": True,
                        }
                    },
                )
        body = await request.body()
        try:
            upstream = await client.request(
                request.method,
                request.url.path,
                params=request.query_params,
                headers=headers,
                content=body,
            )
        except httpx.RequestError:
            correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "ORCHESTRATION_UNREACHABLE",
                        "message": "orchestration service is not reachable",
                        "correlation_id": correlation_id,
                        "retryable": True,
                    }
                },
            )
        response = Response(
            status_code=upstream.status_code,
            content=upstream.content,
            media_type=upstream.headers.get("content-type"),
        )
        if correlation := upstream.headers.get("X-Correlation-Id"):
            response.headers["X-Correlation-Id"] = correlation
        return response

    request_logger = logging.getLogger("storyreview.request")

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        """Emit one structured event per API/health request
        (observability.md telemetry): method, path, upstream status,
        duration, and the correlation id the response carries. Static
        shell assets are deliberately not logged — this is a public
        unauthenticated endpoint and API traffic is the signal."""
        if not (request.url.path.startswith("/api") or request.url.path == "/health"):
            return await call_next(request)
        started = time.perf_counter()
        response = await call_next(request)
        request_logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "correlation_id": response.headers.get("X-Correlation-Id"),
            },
        )
        return response

    class NoCacheStaticMiddleware(BaseHTTPMiddleware):
        """Mark static-shell responses `Cache-Control: no-cache`: the shell
        is baked into the image and changes across rebuilds, and without an
        explicit directive browsers may heuristically cache a stale chat.js
        across deploys (live finding, Runbook 13). Revalidation via ETag
        still avoids re-downloading unchanged files."""

        async def dispatch(self, request, call_next):
            response = await call_next(request)
            if not request.url.path.startswith("/api"):
                response.headers["Cache-Control"] = "no-cache"
            return response

    app.add_middleware(NoCacheStaticMiddleware)
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
    return app
