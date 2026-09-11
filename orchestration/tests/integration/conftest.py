"""Phase 6 increment 5 — live integration suite (main PC only).

Shared fixture for the exit-gate suite: the full orchestration app over
the real compose stack (story/artifact/report MCP + four agent adapters
+ real Vertex) and the throwaway migrated Postgres, exercised over
HTTP. Skipped unless the ORCH_LIVE_* environment is fully provided by
the `orchestration-integration-test` Makefile target.
"""

from __future__ import annotations

import os

import httpx
import pytest

from orchestration.agent_clients import default_agent_set
from orchestration.config import Settings
from orchestration.main import create_app
from orchestration.mcp_client import McpClient

from .helpers import live_env


@pytest.fixture
async def live_client():
    env = live_env()
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
        # read directly from os.environ: the Makefile target provides it,
        # and without it the signer falls back to ADC (cannot sign V4).
        gcs_public_url=os.environ.get("ORCH_LIVE_GCS_PUBLIC_URL", "").strip()
        or None,
    )
    import asyncpg

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
