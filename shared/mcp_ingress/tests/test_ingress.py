"""Middleware behavior tests (pure ASGI — no web framework needed).

Covers the fail-closed contract from mcp-servers.md cross-cutting concerns:
/healthz stays public, missing audience with auth on is 503, missing or
invalid tokens are 401, and a verified token sets the principal contextvar
for downstream tool handlers. Async coroutines run via `asyncio.run` — the
plugin-free convention shared with the MCP server test suites.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from mcp_ingress.auth import IdTokenAuthMiddleware, current_principal


def _scope(path: str = "/", headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    return {
        "type": "http",
        "path": path,
        "headers": headers or [],
    }


class _Captured:
    """Minimal ASGI app recording scope and replies."""

    def __init__(self) -> None:
        self.scope = None
        self.responses: list[dict] = []
        self.principal_at_call = None

    async def __call__(self, scope, receive, send) -> None:
        self.scope = scope
        # Read inside the request context, where MCP tool handlers run.
        self.principal_at_call = current_principal()
        response = {"type": "http.response.start", "status": 200, "headers": []}
        self.responses.append(response)
        await send(response)
        await send({"type": "http.response.body", "body": b"ok"})


class _Harness:
    """One middleware call capturing app responses and raw sends."""

    def __init__(self, middleware: IdTokenAuthMiddleware) -> None:
        self.middleware = middleware
        self.app: _Captured = middleware._app
        self.sends: list[dict] = []

    def call(self, scope: dict) -> None:
        asyncio.run(self._run(scope))

    async def _run(self, scope: dict) -> None:
        async def receive() -> dict:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict) -> None:
            self.sends.append(message)

        await self.middleware(scope, receive, send)


@pytest.fixture()
def harness():
    def _build(
        verifier=None, audience: str = "https://svc", app: _Captured | None = None
    ) -> _Harness:
        app = app or _Captured()
        verifier = verifier or (lambda *_: {})
        return _Harness(IdTokenAuthMiddleware(app, verifier, audience))

    return _build


def test_healthz_is_public(harness) -> None:
    h = harness()
    h.call(_scope("/healthz"))
    assert h.app.responses, "/healthz must bypass token verification"


def test_missing_audience_fails_closed_503(harness) -> None:
    h = harness(audience="")
    h.call(_scope("/mcp"))
    assert h.sends[0]["status"] == 503
    assert not h.app.responses, "no request may reach the app without an audience"


def test_missing_bearer_token_is_401(harness) -> None:
    h = harness()
    h.call(_scope("/mcp"))
    assert h.sends[0]["status"] == 401
    assert not h.app.responses


def test_invalid_bearer_token_is_401(harness) -> None:
    def _reject(token: str, audience: str) -> dict:
        raise ValueError("bad token")

    h = harness(verifier=_reject)
    h.call(_scope("/mcp", [(b"authorization", b"Bearer not-a-real-token")]))
    assert h.sends[0]["status"] == 401
    assert not h.app.responses


def test_verified_token_sets_principal_and_passes_through(harness) -> None:
    seen = {}

    def _verify(token: str, audience: str) -> dict:
        seen["token"], seen["audience"] = token, audience
        return {"email": "caller@example.com"}

    h = harness(verifier=_verify)
    h.call(_scope("/mcp", [(b"authorization", b"Bearer good-token")]))
    assert seen == {"token": "good-token", "audience": "https://svc"}
    assert h.app.responses, "verified request must reach the app"
    assert h.app.principal_at_call == "caller@example.com"


def test_error_response_body_is_json(harness) -> None:
    h = harness()
    h.call(_scope("/mcp"))
    body = h.sends[-1]["body"].decode()
    assert json.loads(body)["error"] == "missing bearer token"


def test_non_http_scope_passes_through(harness) -> None:
    h = harness()
    h.call({"type": "lifespan"})
    assert h.app.scope == {"type": "lifespan"}
