"""Flow 1 live gate (main PC only — real adapters + real Vertex).

One real session creation over HTTP against the local-agents compose
stack (story/artifact MCP + four agent adapters) and the throwaway
migrated Postgres. Skipped unless the ORCH_LIVE_* environment is fully
provided by the `orchestration-flow1-live-test` Makefile target.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from orchestration.agent_clients import default_agent_set
from orchestration.config import Settings
from orchestration.main import create_app
from orchestration.mcp_client import McpClient

from .conftest import USER_HEADERS

REQUIRED_ENV = (
    "ORCH_LIVE_STORY_URL",
    "ORCH_LIVE_ARTIFACT_URL",
    "ORCH_LIVE_REPORT_URL",
    "ORCH_LIVE_BUSINESS_URL",
    "ORCH_LIVE_ENGINEERING_URL",
    "ORCH_LIVE_SYNTHESIS_URL",
    "ORCH_LIVE_FACILITATOR_URL",
    "ORCH_LIVE_DB_DSN",
    "ORCH_LIVE_BUCKET",
)


def _live_env() -> dict[str, str] | None:
    values = {name: os.environ.get(name, "").strip() for name in REQUIRED_ENV}
    return values if all(values.values()) else None


pytestmark = pytest.mark.skipif(
    _live_env() is None,
    reason="live gate env missing — run via make orchestration-flow1-live-test",
)


@pytest.fixture
async def live_client():
    import asyncpg

    env = _live_env()
    assert env is not None
    settings = Settings(
        db_dsn=env["ORCH_LIVE_DB_DSN"],
        story_url=env["ORCH_LIVE_STORY_URL"],
        artifact_url=env["ORCH_LIVE_ARTIFACT_URL"],
        report_url=env["ORCH_LIVE_REPORT_URL"],
        bucket=env["ORCH_LIVE_BUCKET"],
        business_url=env["ORCH_LIVE_BUSINESS_URL"],
        engineering_url=env["ORCH_LIVE_ENGINEERING_URL"],
        synthesis_url=env["ORCH_LIVE_SYNTHESIS_URL"],
        facilitator_url=env["ORCH_LIVE_FACILITATOR_URL"],
    )
    pool = await asyncpg.create_pool(env["ORCH_LIVE_DB_DSN"], min_size=1, max_size=4)
    app = create_app(
        settings=settings,
        pool=pool,
        story_client=McpClient(settings.story_url, settings),
        artifact_client=McpClient(settings.artifact_url, settings),
        report_client=McpClient(settings.report_url, settings),
        agents=default_agent_set(settings),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://orch", headers=USER_HEADERS) as client:
        yield client, pool
    await pool.close()


async def test_live_flow1_session_creation(live_client):
    """One real session creation end-to-end (reviewers → synthesis →
    facilitator opening turn) → schema-valid CreateSessionResponse."""
    client, pool = live_client
    key = uuid.uuid4()
    response = await client.post(
        "/api/v1/sessions",
        json={"story_id": "story-07", "requested_formats": ["md"]},
        headers={"Idempotency-Key": str(key)},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["delegation"]["invoke"] == "none"
    assert body["facilitator_reply"]

    # durable state landed, and the read paths serve the new session
    detail = await client.get(f"/api/v1/sessions/{body['session_id']}")
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["turns"]) == 1
    listing = await client.get("/api/v1/sessions")
    assert body["session_id"] in {s["session_id"] for s in listing.json()["sessions"]}
    async with pool.acquire() as conn:
        runs = await conn.fetchval(
            "select count(*) from agent_runs where story_run_id = $1",
            body["story_run_id"],
        )
    assert runs == 4

    # replay returns the stored canonical response, no new side effects
    replay = await client.post(
        "/api/v1/sessions",
        json={"story_id": "story-07", "requested_formats": ["md"]},
        headers={"Idempotency-Key": str(key)},
    )
    assert replay.status_code == 201
    assert replay.json() == body
