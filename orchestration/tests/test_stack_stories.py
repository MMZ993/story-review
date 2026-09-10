"""Deterministic stack tests against the compose local story MCP (no LLM).

Skipped unless ORCH_TEST_STORY_URL is set (run via `make
orchestration-stack-test` after `make compose-up`) — the same env-gated
live-test convention as the Phase 5 adapter gates. The story MCP service is
the real compose deployment; artifact/report URLs stay fake placeholders
because these tests exercise only the stories proxy path.
"""

from __future__ import annotations

import os

import httpx
import pytest

from orchestration.config import Settings
from orchestration.main import create_app
from orchestration.mcp_client import McpClient

STORY_URL = os.environ.get("ORCH_TEST_STORY_URL", "")

pytestmark = pytest.mark.skipif(
    not STORY_URL, reason="compose story MCP not configured (make orchestration-stack-test)"
)


@pytest.fixture
def client():
    settings = Settings(
        db_dsn="postgresql://x",
        story_url=STORY_URL,
        artifact_url="http://artifact:8080/mcp",
        report_url="http://report:8080/mcp",
        bucket="artifacts-local",
    )
    app = create_app(settings=settings)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    )


async def test_stack_list_stories_returns_dataset_summaries(client):
    response = await client.get("/api/v1/stories")
    assert response.status_code == 200
    stories = response.json()["stories"]
    assert stories, "mock backlog must not be empty"
    assert {s["story_id"] for s in stories} <= {
        f"story-{n:02d}" for n in range(1, 56)
    }


async def test_stack_title_filter_matches_one_story(client):
    response = await client.get("/api/v1/stories", params={"filter": "INVOICE"})
    assert response.status_code == 200
    non_empty = response.json()["stories"]
    assert non_empty, "expected invoice-titled stories"
    assert all("invoice" in s["title"].lower() for s in non_empty)


async def test_stack_story_detail_returns_full_story(client):
    response = await client.get("/api/v1/stories/story-01")
    assert response.status_code == 200
    detail = response.json()
    assert detail["story_id"] == "story-01"
    assert {"description", "epic_context", "roadmap_context"} <= set(detail)


async def test_stack_unknown_story_is_404(client):
    response = await client.get("/api/v1/stories/story-99")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "STORY_NOT_FOUND"


async def test_wrapper_reaches_stack_directly():
    settings = Settings(
        db_dsn="postgresql://x",
        story_url=STORY_URL,
        artifact_url="http://artifact:8080/mcp",
        report_url="http://report:8080/mcp",
        bucket="artifacts-local",
    )
    wrapper = McpClient(url=STORY_URL, settings=settings)
    payload = await wrapper.call("list_stories", {})
    assert payload["stories"]
