"""Flow 2 live gate (main PC only — real adapters + real Vertex).

The example-interaction dialogue arc over HTTP against the local-agents
compose stack: create a real session (flow 1), then one dialogue turn
that asks for a re-review with extra context (reviewers → re-synthesis →
continue). The facilitator is a real model, so the delegation decision is
observed, not scripted. Skipped unless the ORCH_LIVE_* environment is
fully provided by the `orchestration-turns-live-test` Makefile target.
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

from .test_flow1_live import REQUIRED_ENV, _live_env

pytestmark = pytest.mark.skipif(
    _live_env() is None,
    reason="live gate env missing — run via make orchestration-turns-live-test",
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


async def test_live_flow2_dialogue_turn(live_client):
    """Create a session, then run one dialogue turn end-to-end:
    facilitator (real model) → delegation execution per its decision →
    gate → schema-valid TurnResponse with the session still active."""
    client, pool = live_client
    created = await client.post(
        "/api/v1/sessions",
        json={"story_id": "story-07", "requested_formats": ["md"]},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert created.status_code == 201, created.text
    session = created.json()
    session_id = session["session_id"]

    key = uuid.uuid4()
    turn = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={
            "message": (
                "The API limit is 100 rps — we checked with ops. "
                "Please re-review with that constraint in mind."
            ),
            "po_accepted": False,
        },
        headers={"Idempotency-Key": str(key)},
    )
    assert turn.status_code == 200, turn.text
    body = turn.json()
    assert body["session_id"] == session_id
    assert body["turn_number"] == 2
    assert body["outcome"] in {"continue", "park"}
    assert body["facilitator_reply"]

    # durable state: turn 2 recorded, facilitator count advanced
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "select state, outcome from turns "
            "where session_id = $1 and turn_number = 2",
            session_id,
        )
        assert record is not None and record["state"] == "succeeded"
        assert record["outcome"] == body["outcome"]
        count = await conn.fetchval(
            "select facilitator_turn_count from sessions where session_id = $1",
            session_id,
        )
    assert count == 2

    # replay returns the stored canonical response, no new side effects
    replay = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={
            "message": (
                "The API limit is 100 rps — we checked with ops. "
                "Please re-review with that constraint in mind."
            ),
            "po_accepted": False,
        },
        headers={"Idempotency-Key": str(key)},
    )
    assert replay.status_code == 200
    assert replay.json() == body

    # history read path serves the dialogue
    detail = await client.get(f"/api/v1/sessions/{session_id}")
    assert detail.status_code == 200
    assert [t["turn_number"] for t in detail.json()["turns"]] == [1, 2]
