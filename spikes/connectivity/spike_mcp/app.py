"""ASGI application wiring for the deployed connectivity-spike MCP service.

Composes the MCP server (streamable HTTP, stateless), the Cloud SQL or
in-memory session-marker store, `/healthz`, and the ID-token middleware.
The container entrypoint (`main.py`) runs this app with uvicorn.

Environment (production, set by Terraform):
  SPIKE_SERVICE_URL — the service's own URL (ID-token audience; fail-closed
      503 when unset, covering the window between first and second apply);
  SPIKE_INSTANCE_CONNECTION_NAME — <project>:<region>:<instance> for the
      Cloud Run-injected `/cloudsql` unix socket;
  SPIKE_SA_EMAIL — the runtime service account email (IAM db user).
Absent env vars fall back to the in-memory store, which is what the local
tests exercise.
"""

from __future__ import annotations

import os

from starlette.responses import JSONResponse

from spike_mcp.auth_middleware import (
    IdTokenAuthMiddleware,
    Verifier,
    current_principal,
    google_token_verifier,
)
from spike_mcp.server import SessionMarkerServer, create_server
from spike_mcp.store import InMemorySessionMarkerStore, SessionMarkerStore
from spike_mcp.store_sql import SqlSessionMarkerStore, access_token_provider, iam_db_user


def build_app(
    verifier: Verifier | None = None,
    audience: str | None = None,
    store: SessionMarkerStore | None = None,
    http_host: str | None = None,
) -> object:
    """Build the complete ASGI app; injectable parts default to production.

    `http_host` is the expected Host header (MCP transport-security check);
    tests use the Starlette TestClient host, production derives it from
    SPIKE_SERVICE_URL.
    """
    server: SessionMarkerServer = create_server(store or _store_from_env())
    server.set_principal_provider(current_principal)

    mcp = server.app()

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    resolved_host = http_host or _host_from_url(
        os.environ.get("SPIKE_SERVICE_URL", "")
    )
    starlette = mcp.streamable_http_app(stateless_http=True, host=resolved_host)

    resolved_verifier = verifier or google_token_verifier
    resolved_audience = (
        audience if audience is not None else os.environ.get("SPIKE_SERVICE_URL", "")
    )
    return IdTokenAuthMiddleware(starlette, resolved_verifier, resolved_audience)


def _host_from_url(url: str) -> str:
    """Extract the Host-header value from a service URL."""
    from urllib.parse import urlparse

    return urlparse(url).netloc if url else "127.0.0.1"


def _store_from_env() -> SessionMarkerStore:
    conn_name = os.environ.get("SPIKE_INSTANCE_CONNECTION_NAME")
    sa_email = os.environ.get("SPIKE_SA_EMAIL")
    if conn_name and sa_email:
        return SqlSessionMarkerStore(
            instance_connection_name=conn_name,
            db_user=iam_db_user(sa_email),
            password_provider=access_token_provider,
        )
    return InMemorySessionMarkerStore()


def app() -> object:
    """Module-level ASGI entrypoint (uvicorn spike_mcp.main:app)."""
    return build_app()
