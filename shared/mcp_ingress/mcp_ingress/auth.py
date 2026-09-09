"""ID-token ingress middleware and caller-principal plumbing.

Extracted verbatim from the story/artifact server copies (identical modulo
logger/contextvar names — diff-verified before the move). A pure ASGI
middleware verifies the bearer Google ID token against the configured
audience (the service URL) and exposes the verified caller through a
contextvar visible to MCP tool handlers running in the same request.

Fail-closed rules:

- every path except `/health` requires a verified token;
- with auth enabled, a missing audience is a 503 (the window between the
  first and second Terraform apply must never serve traffic unverified);
- auth is disabled only via the per-server env switch in the **local
  compose profile**, never in the production shape (each server's `app.py`
  decides; this package reads no environment).
"""

from __future__ import annotations

import contextvars
import json
import logging
from collections.abc import Callable

logger = logging.getLogger("mcp_ingress.auth")

PUBLIC_PATHS = frozenset({"/health"})

Verifier = Callable[[str, str], dict]

_principal: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "verified_principal", default=None
)


def current_principal() -> str | None:
    """The verified caller email for the current request, or None."""
    return _principal.get()


def google_token_verifier(token: str, audience: str) -> dict:
    """Verify a Google ID token; returns its claims or raises on failure."""
    import google.auth.transport.requests
    import google.oauth2.id_token

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

        if not self._audience:
            # Fail closed: enabled auth with no audience must never serve.
            await _respond(send, 503, "auth audience is not configured")
            return

        token = _bearer_token(scope.get("headers", []))
        if token is None:
            await _respond(send, 401, "missing bearer token")
            return
        try:
            claims = self._verifier(token, self._audience)
        except Exception:
            logger.info("rejected token for %s", path, exc_info=True)
            await _respond(send, 401, "invalid token")
            return

        _principal.set(claims["email"])
        await self._app(scope, receive, send)


def _bearer_token(headers: list[tuple[bytes, bytes]]) -> str | None:
    for name, value in headers:
        if name == b"authorization":
            parts = value.decode("latin-1").split(" ", 1)
            if len(parts) == 2 and parts[0].lower() == "bearer":
                return parts[1]
    return None


async def _respond(send, status: int, message: str) -> None:
    body = json.dumps({"error": message}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})
