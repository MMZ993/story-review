"""Shared fixtures: asyncpg pool against the throwaway Postgres the
`orchestration-test` Makefile target starts and migrates.

Requires ORCH_TEST_DB_DSN (set by the Makefile target); tests fail fast
without it so the target can never silently skip the DB tier.
"""

from __future__ import annotations

import os
import uuid

import asyncpg
import pytest
import httpx

from orchestration.config import Settings

DSN = os.environ.get("ORCH_TEST_DB_DSN")


def make_settings(**overrides) -> Settings:
    """Deterministic-tier settings (fake transports; no network)."""
    values = dict(
        db_dsn="postgresql://x",
        story_url="http://story:8080/mcp",
        artifact_url="http://artifact:8080/mcp",
        report_url="http://report:8080/mcp",
        bucket="artifacts-local",
        business_url="http://business:8080",
        engineering_url="http://engineering:8080",
        synthesis_url="http://synthesis:8080",
        facilitator_url="http://facilitator:8080",
        gcs_public_url="https://127.0.0.1:9026",
    )
    values.update(overrides)
    return Settings(**values)


def _require_dsn() -> str:
    if not DSN:
        pytest.fail(
            "ORCH_TEST_DB_DSN is not set — run tests via `make orchestration-test`"
        )
    return DSN


@pytest.fixture(scope="session")
def dsn() -> str:
    return _require_dsn()


@pytest.fixture
async def pool(dsn: str):
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture(autouse=True)
async def _clean_tables(pool):
    """Isolate tests: wipe orchestration rows (child tables first)."""
    async with pool.acquire() as conn:
        await conn.execute(
            "truncate table turns, agent_runs, turn_leases, sessions, "
            "story_runs, idempotency_claims"
        )
    yield


#: Default test user (X-User-Id scoping): one user for the single-user
#: legacy tests; the multi-user tests mint their own ids.
TEST_USER = uuid.uuid4()
USER_HEADERS = {"X-User-Id": str(TEST_USER)}
