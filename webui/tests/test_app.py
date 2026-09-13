"""Tests for the webui app shell: health, static serving, and the
/api reverse proxy (D17-1 amendment: same-origin routing to orchestration).
"""

import httpx
import json

#: A v4-shaped sample user id (D24-3 header tests).
VALID_USER = "12345678-1234-4123-8123-123456789abc"


def test_health_reports_liveness_without_dependencies(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_serves_the_static_shell(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "story-review" in response.text


def test_root_includes_the_owner_attribution_footer(client):
    response = client.get("/")

    assert "@ 2026 Marcin Żak /" in response.text
    assert 'href="https://mmz.sh/"' in response.text
    assert ">mmz.sh</a>" in response.text


def test_config_requires_orchestration_base_url():
    from webui.config import Settings

    import pytest

    with pytest.raises(ValueError, match="ORCHESTRATION_BASE_URL"):
        Settings.from_env(env={})


def test_proxy_forwards_get_path_query_and_key_header(client, upstream):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/stories"
        assert request.url.params["limit"] == "10"
        assert request.headers["idempotency-key"] == "key-1"
        return httpx.Response(200, json={"stories": []}, headers={"X-Correlation-Id": "c-1"})

    upstream["handler"] = handler
    response = client.get(
        "/api/v1/stories?limit=10", headers={"Idempotency-Key": "key-1"}
    )

    assert response.status_code == 200
    assert response.json() == {"stories": []}
    assert response.headers["X-Correlation-Id"] == "c-1"


def test_proxy_forwards_post_body_verbatim(client, upstream):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/sessions"
        assert request.headers["content-type"] == "application/json"
        assert json.loads(request.content) == {"story_id": "story-01"}
        assert request.headers["idempotency-key"] == "key-2"
        return httpx.Response(201, json={"session_id": "s-1"})

    upstream["handler"] = handler
    response = client.post(
        "/api/v1/sessions",
        json={"story_id": "story-01"},
        headers={"Idempotency-Key": "key-2"},
    )

    assert response.status_code == 201
    assert response.json() == {"session_id": "s-1"}


def test_proxy_passes_upstream_status_and_error_envelope_through(client, upstream):
    upstream["handler"] = lambda request: httpx.Response(
        409,
        json={"error": {"code": "ACTIVE_SESSION_EXISTS", "retryable": False}},
    )

    response = client.post("/api/v1/sessions", json={"story_id": "story-01"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACTIVE_SESSION_EXISTS"


def test_proxy_reports_unreachable_orchestration_as_retryable_503(client, upstream):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    upstream["handler"] = handler
    response = client.post(
        "/api/v1/sessions",
        json={"story_id": "story-01"},
        headers={"X-Correlation-Id": "c-9"},
    )

    assert response.status_code == 503
    body = response.json()["error"]
    assert body["code"] == "ORCHESTRATION_UNREACHABLE"
    assert body["retryable"] is True
    assert body["correlation_id"] == "c-9"


def test_proxy_rejects_paths_escaping_the_api_prefix(client, upstream):
    # dot-segment traversal (decoded) would reach upstream /health — refuse
    upstream["handler"] = lambda request: httpx.Response(200, json={"leak": True})

    for path in ("/api/%2e%2e/health", "/api/../../etc"):
        response = client.get(path)

        assert response.status_code == 404, path


def test_proxy_forwards_only_the_allowlisted_headers(client, upstream):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return httpx.Response(200)

    upstream["handler"] = handler
    client.get(
        "/api/v1/stories",
        headers={
            "Cookie": "session=secret",
            "Authorization": "Bearer secret",
            "X-Custom": "whatever",
            "X-Correlation-Id": "c-1",
        },
    )

    assert "cookie" not in captured and "authorization" not in captured
    assert "x-custom" not in captured
    assert captured["x-correlation-id"] == "c-1"


def test_proxy_forwards_the_user_scoping_header(client, upstream):
    """X-User-Id (D24-3) is a client-hop header: the browser's anonymous
    user id must reach orchestration so sessions scope per user."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["x-user-id"] = request.headers.get("x-user-id")
        return httpx.Response(200)

    upstream["handler"] = handler
    client.get("/api/v1/sessions", headers={"X-User-Id": VALID_USER})
    assert captured["x-user-id"] == VALID_USER


def test_proxy_rejects_non_forwarded_methods(client):
    assert client.put("/api/v1/sessions").status_code == 405
    assert client.delete("/api/v1/sessions/x").status_code == 405


def test_proxy_has_no_client_side_read_timeout(app):
    # A turn may run for minutes; the server deadline governs (review
    # finding: httpx's 5 s default would surface live turns as 503s).
    assert app.state.orchestration_client.timeout.connect is None
    assert app.state.orchestration_client.timeout.read is None


def test_static_responses_are_never_heuristically_cached(client):
    # The static shell is baked into the image and changes across rebuilds;
    # without an explicit Cache-Control the browser may heuristically cache
    # a stale chat.js across deploys (live finding, Runbook 13).
    for path in ("/", "/chat.js", "/progress.js"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["cache-control"] == "no-cache", path


def test_config_reads_id_token_auth_flag():
    # Phase 8 increment 5: the deployed tier authenticates the proxy hop
    # to the IAM-gated orchestration service; local/compose keep it off.
    from webui.config import Settings

    base = {"ORCHESTRATION_BASE_URL": "https://orchestration"}
    assert Settings.from_env(env=base).orchestration_id_token_auth is False
    for value in ("1", "true", "True"):
        settings = Settings.from_env(env={**base, "ORCHESTRATION_ID_TOKEN_AUTH": value})
        assert settings.orchestration_id_token_auth is True


def test_proxy_attaches_minted_id_token_when_auth_enabled(upstream_auth):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(200)

    upstream_auth["handler"] = handler
    upstream_auth["client"].get("/api/v1/stories")
    assert captured["authorization"] == "Bearer minted-token-for-test"


def test_proxy_omits_authorization_when_auth_disabled(client, upstream):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(200)

    upstream["handler"] = handler
    client.get("/api/v1/stories")
    assert captured["authorization"] is None


def test_proxy_reports_mint_failure_as_retryable_503(upstream_auth):
    upstream_auth["fail_mint"] = True
    response = upstream_auth["client"].get("/api/v1/stories")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ORCHESTRATION_UNREACHABLE"
    assert response.json()["error"]["retryable"] is True
