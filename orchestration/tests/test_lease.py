"""Turn-lease primitive tests: token-holder checks, contention with
retry_after_seconds, expiry takeover, release semantics — per observability.md
("Turn leases and finalization": TTL 6 min, one lease row per session)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from orchestration import lease
from orchestration.errors import SessionLocked
from orchestration.lease import TTL
from orchestration.records_store import create_session, create_story_run

from . import factories


@pytest.fixture
async def session_row(pool):
    run = factories.story_run(story_id="story-07")
    session = factories.session(run)
    await create_story_run(pool, run)
    await create_session(pool, session)
    return session


async def test_acquire_renew_and_release_by_holder(pool, session_row):
    token = await lease.acquire(pool, session_row.session_id)
    assert token is not None

    assert await lease.renew(pool, session_row.session_id, token)
    assert await lease.release(pool, session_row.session_id, token)

    # After release a fresh acquire succeeds with a new token.
    new_token = await lease.acquire(pool, session_row.session_id)
    assert new_token != token


async def test_renew_and_release_rejected_for_non_holder(pool, session_row):
    token = await lease.acquire(pool, session_row.session_id)
    stranger = __import__("uuid").uuid4()

    assert not await lease.renew(pool, session_row.session_id, stranger)
    assert not await lease.release(pool, session_row.session_id, stranger)
    # The holder's token still works — the stranger's calls were no-ops.
    assert await lease.renew(pool, session_row.session_id, token)


async def test_contention_raises_session_locked_with_retry_after(pool, session_row):
    await lease.acquire(pool, session_row.session_id)

    with pytest.raises(SessionLocked) as excinfo:
        await lease.acquire(pool, session_row.session_id)

    assert 1 <= excinfo.value.retry_after_seconds <= int(TTL.total_seconds())


async def test_expired_lease_is_taken_over(pool, session_row):
    holder = await lease.acquire(pool, session_row.session_id)
    # Simulate expiry: rewind acquisition into the past beyond the TTL.
    async with pool.acquire() as conn:
        await conn.execute(
            "update turn_leases set acquired_at = now() - $1::interval - "
            "interval '1 second', expires_at = now() - interval '1 second' "
            "where session_id = $2",
            TTL,
            session_row.session_id,
        )

    taker = await lease.acquire(pool, session_row.session_id)
    assert taker is not None and taker != holder
    # The old holder can no longer renew or release.
    assert not await lease.renew(pool, session_row.session_id, holder)
    assert not await lease.release(pool, session_row.session_id, holder)


async def test_ttl_is_six_minutes():
    assert TTL == timedelta(minutes=6)
