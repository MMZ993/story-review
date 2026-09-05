"""ID-token verification middleware for the deployed MCP service.

Pure ASGI middleware (same task as the app, so the verified principal set in
a contextvar is visible to MCP tool handlers). Every path except `/healthz`
requires a Google ID token verified against the configured audience (the
Cloud Run service URL). Missing/invalid token → 401; missing audience → 503
(fail closed: the service must never serve MCP traffic unverified, including
the window between the first and second Terraform apply).

The verification callable is injectable: production uses
`google_token_verifier` (google.oauth2.id_token); tests inject a fake.
"""

from __future__ import annotations

import contextvars
import json
import logging
from collections.abc import Callable

from spike_mcp.principal import Principal

logger = logging.getLogger("spike_mcp.auth")

PUBLIC_PATHS = frozenset({"/healthz"})

Verifier = Callable[[str, str], dict]

_principal: contextvars.ContextVar[Principal | None] = contextvars.ContextVar(
    "spike_verified_principal", default=None
)


def current_principal() -> Principal | None:
    """The verified caller for the current request, or None."""
    return _principal.get()


def google_token_verifier(token: str, audience: str) -> dict:
    """Verify a Google ID token; returns its claims or raises on failure."""
    import google.oauth2.id_token
    import google.auth.transport.requests

    claims = google.oauth2.id_token.verify_oauth2_token(
        token, google.auth.transport.requests.Request(), audience=audience
    )
    if "email" not in claims:
        raise ValueError("token carries no email claim")
    return claims


class IdTokenAuthMiddleware:
    """Verifies the bearer ID token before the request reaches the app."""

    def __init__(self, app, verifier: Verifier, audience: str) -> None:
        self._app = app
        self._verifier = verifier
        self._audience = audience

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in PUBLIC_PATHS:
            await self._app(scope, receive, send)
            return

        async def _respond(status: int, message: str) -> None:
            body = json.dumps({"error": message}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": body})

        if not self._audience:
            await _respond(503, "service audience not configured")
            return

        token = _bearer_token(scope)
        if token is None:
            await _respond(401, "missing bearer token")
            return
        try:
            claims = self._verifier(token, self._audience)
        except Exception:
            logger.warning("token verification failed for path=%s", path, exc_info=True)
            await _respond(401, "invalid token")
            return

        _principal.set(
            Principal(email=claims["email"], subject=claims.get("sub"))
        )
        await self._app(scope, receive, send)


def _bearer_token(scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            parts = value.decode("latin-1").split(" ", 1)
            if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1]:
                return parts[1]
    return None
