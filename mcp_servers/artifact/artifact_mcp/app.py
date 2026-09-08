"""ASGI application wiring for the artifact MCP service.

Composes the MCP server (Streamable HTTP, stateless), the GCS-backed
storage service, `/healthz`, and the ID-token ingress middleware (the
Runbook-06 spike pattern, shared with the story server). The container
entrypoint (`main.py`) runs this app with uvicorn.

Environment (production, set at deploy time):

  ARTIFACT_BUCKET          — the artifact bucket (required).
  ARTIFACT_GCS_ENDPOINT    — optional storage endpoint override
                             (fake-gcs-server in the local profile).
  ARTIFACT_SERVICE_URL     — the service's own URL; the ID-token audience.
                             Empty + auth enabled → fail-closed 503.
  ARTIFACT_AUTH_DISABLED   — `1` disables ingress auth **local profile only**.
  ARTIFACT_ORCHESTRATION_CALLERS — comma-separated orchestration emails.
  ARTIFACT_FACILITATOR_CALLERS   — comma-separated facilitator emails
                             (read tools only).

`build_app` parameters override the environment (tests inject verifiers,
buckets, endpoints, and roles); the defaults are the production wiring.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from starlette.responses import JSONResponse

from artifact_mcp.auth import IdTokenAuthMiddleware, Verifier, google_token_verifier
from artifact_mcp.server import ArtifactServer, CallerRoles
from artifact_mcp.storage import GcsArtifactService


def build_app(
    *,
    verifier: Verifier | None = None,
    audience: str | None = None,
    auth_disabled: bool | None = None,
    bucket: str | None = None,
    gcs_endpoint: str | None = None,
    roles: CallerRoles | None = None,
    http_host: str | None = None,
) -> object:
    """Build the complete ASGI app; injectable parts default to production."""
    resolved_bucket = bucket or os.environ.get("ARTIFACT_BUCKET", "")
    if not resolved_bucket:
        raise ValueError(
            "ARTIFACT_BUCKET is not configured — refusing to build an app "
            "that would fail opaquely at the first tool call"
        )
    service = GcsArtifactService(
        bucket=resolved_bucket,
        endpoint=gcs_endpoint if gcs_endpoint is not None
        else os.environ.get("ARTIFACT_GCS_ENDPOINT") or None,
    )
    resolved_roles = _roles_from_env()
    if roles is not None:
        resolved_roles = roles
    resolved_auth_disabled = (
        auth_disabled if auth_disabled is not None else _auth_disabled_from_env()
    )
    server = ArtifactServer(
        service=service,
        roles=None if resolved_auth_disabled and roles is None else resolved_roles,
    )

    mcp = server.mcp()

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    resolved_host = http_host or _host_from_url(os.environ.get("ARTIFACT_SERVICE_URL", ""))
    starlette = mcp.streamable_http_app(stateless_http=True, host=resolved_host)

    if resolved_auth_disabled:
        return starlette  # local profile: no ingress verification

    resolved_audience = (
        audience if audience is not None else os.environ.get("ARTIFACT_SERVICE_URL", "")
    )
    return IdTokenAuthMiddleware(starlette, verifier or google_token_verifier, resolved_audience)


def _roles_from_env() -> CallerRoles:
    """Caller roles from the two allowlist env vars (possibly empty)."""
    return CallerRoles(
        orchestration=_allowlist_from_env("ARTIFACT_ORCHESTRATION_CALLERS"),
        facilitator=_allowlist_from_env("ARTIFACT_FACILITATOR_CALLERS"),
    )


def _allowlist_from_env(name: str) -> set[str]:
    raw = os.environ.get(name, "")
    return {email.strip() for email in raw.split(",") if email.strip()}


def _auth_disabled_from_env() -> bool:
    return os.environ.get("ARTIFACT_AUTH_DISABLED", "") in {"1", "true", "True"}


def _host_from_url(url: str) -> str:
    return urlparse(url).netloc if url else "127.0.0.1"
