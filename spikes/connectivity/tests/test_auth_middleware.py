"""ID-token authentication boundary tests for the deployed MCP service.

The production middleware verifies a Google ID token (audience = the Cloud
Run service URL) before any MCP request reaches the server. Tests inject a
fake verifier so the verification *library* is not exercised here — only the
boundary behavior: no token → 401, invalid token → 401, valid token → the
request proceeds with the verified principal visible to the service.
`/healthz` stays reachable without a token for Cloud Run health checks.
"""

from __future__ import annotations

from typing import Callable

import pytest
from starlette.testclient import TestClient

from spike_mcp.app import build_app

Verifier = Callable[[str, str], dict]


def _fake_verifier(valid_token: str, email: str) -> Verifier:
    """Return a verifier accepting exactly `valid_token` for any audience."""

    def verify(token: str, audience: str) -> dict:
        if token != valid_token:
            raise ValueError("invalid token")
        if not audience:
            raise ValueError("audience must not be empty")
        return {"email": email, "sub": "fake-subject"}

    return verify


def test_missing_authorization_header_is_rejected() -> None:
    app = build_app(verifier=_fake_verifier("tok", "caller@project.iam"), audience="https://spike.example", http_host="testserver")
    with TestClient(app) as client:
        response = client.post("/mcp", json={"jsonrpc": "2.0", "method": "initialize"})
    assert response.status_code == 401


def test_non_bearer_or_invalid_token_is_rejected() -> None:
    verifier = _fake_verifier("tok", "caller@project.iam")
    app = build_app(verifier=verifier, audience="https://spike.example", http_host="testserver")
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize"},
            headers={"Authorization": "Bearer wrong-token"},
        )
    assert response.status_code == 401


def test_valid_token_reaches_the_service_with_verified_principal() -> None:
    app = build_app(verifier=_fake_verifier("tok", "caller@project.iam"), audience="https://spike.example", http_host="testserver")
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
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
            headers={"Authorization": "Bearer tok"},
        )
    assert response.status_code == 200


def test_healthz_is_reachable_without_a_token() -> None:
    app = build_app(verifier=_fake_verifier("tok", "caller@project.iam"), audience="https://spike.example", http_host="testserver")
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unconfigured_audience_fails_closed() -> None:
    # No audience (SPIKE_SERVICE_URL unset at deploy time) must reject traffic
    # rather than skip verification — with a token and without one.
    app = build_app(verifier=_fake_verifier("tok", "caller@project.iam"), audience="", http_host="testserver")
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize"},
            headers={"Authorization": "Bearer tok"},
        )
        assert response.status_code == 503
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize"},
        )
        assert response.status_code == 503
