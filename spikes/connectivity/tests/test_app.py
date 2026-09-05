"""App wiring tests: the deployed ASGI app's HTTP surface.

`build_app` composes the MCP server, the ID-token middleware, and `/healthz`.
Over the real streamable-HTTP transport (ASGI, no network): healthz works,
MCP is unreachable without a token, and an authenticated caller can execute
the full persist/restore round trip through the same app the container runs.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from spike_mcp.app import build_app


def _verifier(valid_token: str):
    def verify(token: str, audience: str) -> dict:
        if token != valid_token:
            raise ValueError("invalid token")
        return {"email": "caller@project.iam", "sub": "fake-subject"}

    return verify


AUTH = {"Authorization": "Bearer tok"}


def _init_headers(extra: dict | None = None, token: str = "tok") -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-06-18",
    }
    headers.update(extra or {})
    return headers


def test_full_persist_restore_round_trip_over_http() -> None:
    app = build_app(verifier=_verifier("tok"), audience="https://spike.example", http_host="testserver")
    with TestClient(app) as client:
        init = client.post(
            "/mcp",
            headers=_init_headers(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
        )
        assert init.status_code == 200

        persist = client.post(
            "/mcp",
            headers=_init_headers(),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "persist_session",
                    "arguments": {
                        "session_id": "http-1",
                        "marker": "http-marker",
                        "correlation_id": "corr-http",
                    },
                },
            },
        )
        assert persist.status_code == 200

        restore = client.post(
            "/mcp",
            headers=_init_headers(),
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "restore_session",
                    "arguments": {"session_id": "http-1", "correlation_id": "corr-http"},
                },
            },
        )
        assert restore.status_code == 200
        body = restore.text
        assert "http-marker" in body
        assert "http-1" in body


def test_mcp_request_without_token_is_401_over_http() -> None:
    app = build_app(verifier=_verifier("tok"), audience="https://spike.example", http_host="testserver")
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize"},
        )
    assert response.status_code == 401
