"""ASGI application wiring for the story MCP service.

Composes the MCP server (Streamable HTTP, stateless), the configured data
sources, `/health`, and the ID-token ingress middleware (adapted from the
Runbook-06 spike). The container entrypoint (`main.py`) runs this app with
uvicorn.

Environment (production, set at deploy time):

  STORY_SOURCE           — deployment data-source default (`azure` |
                           `mock`; D10).
  STORY_DATASET_LOCATION — mock-source location: a directory path or a
                           `gs://bucket/prefix/` URI.
  STORY_AZURE_ORG / STORY_AZURE_PROJECT / STORY_ADO_PAT — azure source
                           (PAT moves to Secret Manager at increment 5).
  STORY_SERVICE_URL      — the service's own URL; the ID-token audience.
                           Empty + auth enabled → fail-closed 503.
  STORY_AUTH_DISABLED    — `1` disables ingress auth **local profile only**.
  STORY_ALLOWED_CALLERS  — comma-separated caller emails (allowlist).

`build_app` parameters override the environment (tests inject verifiers,
locations, and allowlists); the defaults are the production wiring.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from starlette.responses import JSONResponse

from mcp_ingress.auth import IdTokenAuthMiddleware, Verifier, google_token_verifier
from story_mcp.backlog import BacklogLike
from story_mcp.mock_source import MockBacklogSource
from story_mcp.server import StoryServer


def build_app(
    *,
    verifier: Verifier | None = None,
    audience: str | None = None,
    auth_disabled: bool | None = None,
    sources: dict[str, BacklogLike] | None = None,
    default_source: str | None = None,
    stories_location: str | None = None,
    allowed_callers: set[str] | None = None,
    http_host: str | None = None,
) -> object:
    """Build the complete ASGI app; injectable parts default to production."""
    resolved_sources = sources if sources is not None else _sources_from_env(stories_location)
    resolved_default = default_source if default_source is not None else os.environ.get(
        "STORY_SOURCE", "mock"
    )
    resolved_auth_disabled = (
        auth_disabled if auth_disabled is not None else _auth_disabled_from_env()
    )
    resolved_callers = _resolve_callers(allowed_callers, resolved_auth_disabled)
    server = StoryServer(
        sources=resolved_sources,
        default_source=resolved_default,
        allowed_callers=resolved_callers,
    )

    mcp = server.mcp()

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    resolved_host = http_host or _host_from_url(os.environ.get("STORY_SERVICE_URL", ""))
    starlette = mcp.streamable_http_app(stateless_http=True, host=resolved_host)

    if resolved_auth_disabled:
        return starlette  # local profile: no ingress verification

    resolved_audience = (
        audience if audience is not None else os.environ.get("STORY_SERVICE_URL", "")
    )
    return IdTokenAuthMiddleware(starlette, verifier or google_token_verifier, resolved_audience)


def _sources_from_env(location_override: str | None) -> dict[str, BacklogLike]:
    """Build the configured sources; the azure source appears only when its
    environment is complete."""
    sources: dict[str, BacklogLike] = {
        "mock": MockBacklogSource.from_location(
            location_override or os.environ.get("STORY_DATASET_LOCATION", "")
        )
    }
    org = os.environ.get("STORY_AZURE_ORG")
    project = os.environ.get("STORY_AZURE_PROJECT")
    pat = os.environ.get("STORY_ADO_PAT")
    if org and project and pat:
        from story_mcp.azure_source import AzureBacklogSource

        sources["azure"] = AzureBacklogSource(org=org, project=project, pat=pat)
    return sources


def _resolve_callers(allowed_callers: set[str] | None, auth_disabled: bool) -> set[str] | None:
    """Allowlist resolution, fail-closed in the production shape.

    Bypass (None) requires auth disabled AND no explicit allowlist. With
    auth enabled, a missing/empty allowlist env is the empty set — every
    verified caller is FORBIDDEN — never an implicit allow-all.
    """
    if auth_disabled and allowed_callers is None:
        return None
    if allowed_callers is not None:
        return allowed_callers
    return _allowlist_from_env() or set()


def _allowlist_from_env() -> set[str]:
    """The allowlist from `STORY_ALLOWED_CALLERS` (possibly empty)."""
    raw = os.environ.get("STORY_ALLOWED_CALLERS", "")
    return {email.strip() for email in raw.split(",") if email.strip()}


def _auth_disabled_from_env() -> bool:
    return os.environ.get("STORY_AUTH_DISABLED", "") in {"1", "true", "True"}


def _host_from_url(url: str) -> str:
    return urlparse(url).netloc if url else "127.0.0.1"
