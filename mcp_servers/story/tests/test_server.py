"""Contract tests for the story MCP server against the ASGI app.

Drives the app exactly as orchestration will: the `mcp` client SDK over
Streamable HTTP (an ASGI transport standing in for the network). Each test
runs one scenario in its own event loop (`asyncio.run`) — the plugin-free
equivalent of the spike's sync TestClient pattern. Covers the tool matrix,
the shared-model payloads, the error taxonomy (unknown fields, id spaces,
source selection), correlation-ID propagation, and the ingress authorization
plumbing (middleware + caller allowlist).
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from asgi_lifespan import LifespanManager
from review_schemas.review import StoryDetail

from story_mcp.app import build_app

STORIES_DIR = Path(__file__).resolve().parents[3] / "dataset" / "stories"
ORCH = "orchestration@example.com"
FACI = "facilitator@example.com"


def _fake_verifier(email: str):
    def verify(token: str, audience: str) -> dict:
        assert token == "good-token"
        return {"email": email}

    return verify


def _mock_app(allowed_callers: set[str] | None = None):
    return build_app(
        auth_disabled=True,
        stories_location=str(STORIES_DIR),
        allowed_callers=allowed_callers,
        http_host="story.test",
    )


async def call_tool(
    app, tool: str, arguments: dict, *, headers: dict[str, str] | None = None
):
    """One MCP round trip; returns the client-side CallToolResult."""
    async with LifespanManager(app):
        http = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://story.test",
            headers=headers or {},
        )
        async with streamable_http_client(
            "http://story.test/mcp", http_client=http, terminate_on_close=False
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool, arguments)


async def list_tools(app):
    async with LifespanManager(app):
        http = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://story.test"
        )
        async with streamable_http_client(
            "http://story.test/mcp", http_client=http, terminate_on_close=False
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return (await session.list_tools()).tools


def _payload(result) -> dict:
    assert result.structured_content is not None, result.content
    return dict(result.structured_content)


def test_tool_schemas_are_flat_and_exact():
    tools = {t.name: t for t in asyncio.run(list_tools(_mock_app()))}
    assert set(tools) == {"list_stories", "get_story"}
    assert tools["list_stories"].input_schema["properties"].keys() == {"filter", "source"}
    assert tools["get_story"].input_schema["properties"].keys() == {"story_id", "source"}
    assert tools["get_story"].input_schema.get("required") == ["story_id"]


def test_list_stories_returns_all_summaries():
    result = asyncio.run(call_tool(_mock_app(), "list_stories", {}))
    stories = _payload(result)["stories"]
    assert not result.is_error
    assert len(stories) == 45
    assert stories[0]["story_id"] == "story-01"
    assert all({"story_id", "title", "status"} == set(s) for s in stories)


def test_list_stories_filter_narrows_by_status():
    result = asyncio.run(call_tool(_mock_app(), "list_stories", {"filter": "nonexistent-status"}))
    assert _payload(result)["stories"] == []


def test_get_story_returns_valid_story_detail():
    result = asyncio.run(call_tool(_mock_app(), "get_story", {"story_id": "story-01"}))
    detail = StoryDetail.model_validate(_payload(result))
    assert detail.story_id == "story-01"


def test_cross_source_id_is_story_not_found():
    result = asyncio.run(call_tool(_mock_app(), "get_story", {"story_id": "ado-5"}))
    error = _payload(result)["error"]
    assert result.is_error
    assert error["code"] == "STORY_NOT_FOUND"
    assert error["retryable"] is False


def test_unknown_story_is_story_not_found():
    result = asyncio.run(call_tool(_mock_app(), "get_story", {"story_id": "story-99"}))
    assert _payload(result)["error"]["code"] == "STORY_NOT_FOUND"


def test_invalid_story_id_pattern_is_validation_error():
    result = asyncio.run(call_tool(_mock_app(), "get_story", {"story_id": "story-1"}))
    assert _payload(result)["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_field_is_validation_error():
    result = asyncio.run(
        call_tool(_mock_app(), "get_story", {"story_id": "story-01", "bogus": 1})
    )
    error = _payload(result)["error"]
    assert result.is_error
    assert error["code"] == "VALIDATION_ERROR"
    assert "bogus" in error["message"]


def test_invalid_source_is_validation_error():
    result = asyncio.run(call_tool(_mock_app(), "list_stories", {"source": "bogus"}))
    assert _payload(result)["error"]["code"] == "VALIDATION_ERROR"


def test_azure_source_not_configured_is_upstream_unavailable():
    result = asyncio.run(
        call_tool(_mock_app(), "get_story", {"story_id": "ado-5", "source": "azure"})
    )
    error = _payload(result)["error"]
    assert error["code"] == "UPSTREAM_UNAVAILABLE"
    assert error["retryable"] is False


def test_explicit_mock_override_serves_the_dataset():
    result = asyncio.run(
        call_tool(_mock_app(), "get_story", {"story_id": "story-01", "source": "mock"})
    )
    assert not result.is_error
    assert _payload(result)["story_id"] == "story-01"


def test_header_correlation_id_echoed_in_errors():
    correlation_id = str(uuid.uuid4())
    result = asyncio.run(
        call_tool(
            _mock_app(),
            "get_story",
            {"story_id": "story-99"},
            headers={"X-Correlation-Id": correlation_id},
        )
    )
    assert _payload(result)["error"]["correlation_id"] == correlation_id


def test_missing_header_gets_generated_uuid4():
    result = asyncio.run(call_tool(_mock_app(), "get_story", {"story_id": "story-99"}))
    correlation_id = _payload(result)["error"]["correlation_id"]
    assert uuid.UUID(correlation_id).version == 4


def test_malformed_header_is_replaced_not_rejected():
    result = asyncio.run(
        call_tool(
            _mock_app(),
            "get_story",
            {"story_id": "story-99"},
            headers={"X-Correlation-Id": "not-a-uuid"},
        )
    )
    correlation_id = _payload(result)["error"]["correlation_id"]
    assert uuid.UUID(correlation_id).version == 4


def _authed_app(verifier, allowed_callers):
    return build_app(
        verifier=verifier,
        audience="https://story.test",
        stories_location=str(STORIES_DIR),
        allowed_callers=allowed_callers,
        http_host="story.test",
    )


def test_missing_token_is_rejected_at_ingress():
    async def scenario():
        transport = httpx2.ASGITransport(app=_authed_app(_fake_verifier(ORCH), {ORCH}))
        async with httpx2.AsyncClient(transport=transport, base_url="http://story.test") as c:
            return await c.post(
                "http://story.test/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )

    assert asyncio.run(scenario()).status_code == 401


def test_verified_allowlisted_caller_succeeds():
    app = _authed_app(_fake_verifier(ORCH), {ORCH, FACI})
    headers = {"Authorization": "Bearer good-token"}
    result = asyncio.run(call_tool(app, "list_stories", {}, headers=headers))
    assert not result.is_error


def test_verified_caller_outside_allowlist_is_forbidden():
    app = _authed_app(_fake_verifier("stranger@example.com"), {ORCH})
    headers = {"Authorization": "Bearer good-token"}
    result = asyncio.run(call_tool(app, "list_stories", {}, headers=headers))
    assert result.is_error
    assert _payload(result)["error"]["code"] == "FORBIDDEN"


def test_auth_enabled_with_missing_allowlist_env_fails_closed(monkeypatch):
    """Production shape: no STORY_ALLOWED_CALLERS → nobody is authorized."""
    monkeypatch.setenv("STORY_SERVICE_URL", "https://story.test")
    monkeypatch.delenv("STORY_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("STORY_ALLOWED_CALLERS", raising=False)
    monkeypatch.setenv("STORY_DATASET_LOCATION", str(STORIES_DIR))
    app = build_app(verifier=_fake_verifier(ORCH), http_host="story.test")
    headers = {"Authorization": "Bearer good-token"}
    result = asyncio.run(call_tool(app, "list_stories", {}, headers=headers))
    assert result.is_error
    assert _payload(result)["error"]["code"] == "FORBIDDEN"


def test_missing_audience_fails_closed():
    app = build_app(
        verifier=_fake_verifier(ORCH),
        audience="",
        stories_location=str(STORIES_DIR),
        allowed_callers={ORCH},
        http_host="story.test",
    )

    async def scenario():
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://story.test") as c:
            return await c.post(
                "http://story.test/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                headers={"Authorization": "Bearer good-token"},
            )

    assert asyncio.run(scenario()).status_code == 503


def test_health_is_public():
    async def scenario():
        app = _authed_app(_fake_verifier(ORCH), {ORCH})
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://story.test") as c:
            return await c.get("http://story.test/health")

    assert asyncio.run(scenario()).status_code == 200


def test_local_profile_without_allowlist_serves_tools():
    result = asyncio.run(call_tool(_mock_app(allowed_callers=None), "list_stories", {}))
    assert not result.is_error
