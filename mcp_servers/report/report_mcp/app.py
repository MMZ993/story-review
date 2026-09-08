"""ASGI application wiring for the report MCP service.

Composes the MCP server (Streamable HTTP, stateless), the report store,
`/healthz`, and the shared ID-token ingress middleware (`mcp_ingress` —
extracted from the story/artifact copies at increment 3). The container
entrypoint (`main.py`) runs this app with uvicorn.

Environment (production, set at deploy time):

  REPORT_BUCKET            — the artifact bucket (required; shared with the
                             artifact server, disjoint object prefixes).
  REPORT_GCS_ENDPOINT      — optional storage endpoint override
                             (fake-gcs-server in the local profile).
  REPORT_SERVICE_URL       — the service's own URL; the ID-token audience.
                             Empty + auth enabled → fail-closed 503.
  REPORT_AUTH_DISABLED     — `1` disables ingress auth **local profile only**.
  REPORT_ORCHESTRATION_CALLERS — comma-separated orchestration emails
                             (render_report is orchestration-only).

`build_app` parameters override the environment (tests inject verifiers,
buckets, endpoints, and callers); the defaults are the production wiring.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from starlette.responses import JSONResponse

from mcp_ingress.auth import IdTokenAuthMiddleware, Verifier, google_token_verifier

from report_mcp.server import ReportServer
from report_mcp.storage import ReportStore


def build_app(
    *,
    verifier: Verifier | None = None,
    audience: str | None = None,
    auth_disabled: bool | None = None,
    bucket: str | None = None,
    gcs_endpoint: str | None = None,
    orchestration_callers: set[str] | None = None,
    http_host: str | None = None,
) -> object:
    """Build the complete ASGI app; injectable parts default to production."""
    resolved_bucket = bucket or os.environ.get("REPORT_BUCKET", "")
    if not resolved_bucket:
        raise ValueError(
            "REPORT_BUCKET is not configured — refusing to build an app "
            "that would fail opaquely at the first tool call"
        )
    store = ReportStore(
        bucket=resolved_bucket,
        endpoint=gcs_endpoint if gcs_endpoint is not None
        else os.environ.get("REPORT_GCS_ENDPOINT") or None,
    )
    resolved_callers = (
        orchestration_callers
        if orchestration_callers is not None
        else _callers_from_env()
    )
    resolved_auth_disabled = (
        auth_disabled if auth_disabled is not None else _auth_disabled_from_env()
    )
    server = ReportServer(
        store=store,
        orchestration_callers=(
            None if resolved_auth_disabled and orchestration_callers is None
            else resolved_callers
        ),
    )

    mcp = server.mcp()

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    resolved_host = http_host or _host_from_url(os.environ.get("REPORT_SERVICE_URL", ""))
    starlette = mcp.streamable_http_app(stateless_http=True, host=resolved_host)

    if resolved_auth_disabled:
        return starlette  # local profile: no ingress verification

    resolved_audience = (
        audience if audience is not None else os.environ.get("REPORT_SERVICE_URL", "")
    )
    return IdTokenAuthMiddleware(starlette, verifier or google_token_verifier, resolved_audience)


def _callers_from_env() -> set[str]:
    raw = os.environ.get("REPORT_ORCHESTRATION_CALLERS", "")
    return {email.strip() for email in raw.split(",") if email.strip()}


def _auth_disabled_from_env() -> bool:
    return os.environ.get("REPORT_AUTH_DISABLED", "") in {"1", "true", "True"}


def _host_from_url(url: str) -> str:
    return urlparse(url).netloc if url else "127.0.0.1"
