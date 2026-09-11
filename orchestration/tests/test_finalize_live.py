"""Flows 3+4 live gate (main PC only — real adapters + real Vertex).

A full session from creation to downloaded report over HTTP against the
local-agents compose stack: real session creation (flow 1), an explicit
PO acceptance turn that finalizes synchronously in the same response
(TurnResponse with report downloads), fresh URLs from GET /report, and a
real download of the rendered bytes from fake-gcs over HTTPS
(self-signed; verification relaxed locally — Runbook 12). Skipped unless
the ORCH_LIVE_* environment is fully provided by the
`orchestration-finalize-live-test` Makefile target.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest

from orchestration.agent_clients import default_agent_set
from orchestration.config import Settings
from orchestration.main import create_app
from orchestration.mcp_client import McpClient

from .test_flow1_live import _live_env

pytestmark = pytest.mark.skipif(
    _live_env() is None,
    reason="live gate env missing — run via make orchestration-finalize-live-test",
)


@pytest.fixture
async def live_client():
    import asyncpg
    import os

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
        gcs_public_url=os.environ.get("ORCH_LIVE_GCS_PUBLIC_URL", "").strip() or None,
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
    async with httpx.AsyncClient(transport=transport, base_url="http://orch") as client:
        yield client, pool
    await pool.close()


async def test_live_full_session_to_downloaded_report(live_client):
    """Creation → acceptance turn (synchronous finalize) → report URLs →
    downloaded report bytes: one schema-valid TurnResponse whose report
    entry downloads from fake-gcs over the signed HTTPS URL."""
    client, pool = live_client
    created = await client.post(
        "/api/v1/sessions",
        json={"story_id": "story-07", "requested_formats": ["md", "pdf"]},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["session_id"]

    # explicit PO acceptance: bypasses the facilitator, finalizes in the
    # same response
    accepted = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"message": None, "po_accepted": True},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert accepted.status_code == 200, accepted.text
    turn = accepted.json()
    assert turn["outcome"] == "finalize"
    assert turn["state"] == "completed"
    assert sorted(entry["format"] for entry in turn["report"]) == ["md", "pdf"]

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select state, report_references, facilitator_turn_count "
            "from sessions where session_id = $1",
            session_id,
        )
        assert row["state"] == "completed"
        assert len(json.loads(row["report_references"])) == 2
        assert row["facilitator_turn_count"] == 1  # acceptance adds none

    # report endpoint regenerates the URLs
    reports = await client.get(f"/api/v1/sessions/{session_id}/report")
    assert reports.status_code == 200, reports.text
    entries = reports.json()["report"]
    assert sorted(entry["format"] for entry in entries) == ["md", "pdf"]

    # the download URL actually serves the rendered bytes (self-signed
    # local TLS — relaxed verification is the documented local substitution)
    async with httpx.AsyncClient(verify=False) as downloader:
        for entry in entries:
            downloaded = await downloader.get(entry["signed_url"])
            assert downloaded.status_code == 200, downloaded.text
            assert len(downloaded.content) > 0
