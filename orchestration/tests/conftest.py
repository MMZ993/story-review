"""Shared fixtures: asyncpg pool against the throwaway Postgres the
`orchestration-test` Makefile target starts and migrates.

Requires ORCH_TEST_DB_DSN (set by the Makefile target); tests fail fast
without it so the target can never silently skip the DB tier.
"""

from __future__ import annotations

import os

import asyncpg
import pytest

DSN = os.environ.get("ORCH_TEST_DB_DSN")


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
