"""Live integration: lease contention under concurrency (main PC).

A slow delegating turn holds the session lease (facilitator + reviewer
fan-out + synthesis take seconds); a concurrent turn on the same
session is rejected before any work starts with 409 SESSION_LOCKED and
a retry hint, and leaves no durable turn behind.
"""

from __future__ import annotations

import asyncio

import pytest

from .helpers import create_session, idem_key, live_env

pytestmark = pytest.mark.skipif(
    live_env() is None,
    reason="live integration env missing — run via make orchestration-integration-test",
)

SLOW_TURN_MESSAGE = (
    "The API limit is 100 rps — we checked with ops. "
    "Please re-review both perspectives with that constraint in mind."
)


async def test_live_concurrent_turn_is_locked_out(live_client):
    """A turn in flight locks the session; a concurrent turn gets
    SESSION_LOCKED and persists nothing."""
    client, pool = live_client
    session = await create_session(client, "story-06")
    session_id = session["session_id"]

    first = asyncio.create_task(
        client.post(
            f"/api/v1/sessions/{session_id}/turns",
            json={"message": SLOW_TURN_MESSAGE, "po_accepted": False},
            headers={"Idempotency-Key": idem_key()},
        )
    )
    # let the first request acquire the lease and reach the facilitator
    # (lease acquisition is in-process/ms; the realistic race is the
    # first turn completing under 2 s, but observed model turns run 30 s+
    # and a premature completion fails this test loudly, not silently)
    await asyncio.sleep(2.0)

    second = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"message": "an unrelated quick note", "po_accepted": False},
        headers={"Idempotency-Key": idem_key()},
    )
    assert second.status_code == 409, second.text
    error = second.json()["error"]
    assert error["code"] == "SESSION_LOCKED"
    assert error["retry_after_seconds"] >= 1

    first_response = await first
    assert first_response.status_code == 200, first_response.text
    body = first_response.json()
    assert body["turn_number"] == 2
    assert body["outcome"] in {"continue", "park"}

    # the rejected attempt left no durable turn; only turn 2 exists
    async with pool.acquire() as conn:
        turns = await conn.fetch(
            "select turn_number from turns where session_id = $1 "
            "order by turn_number",
            session_id,
        )
    assert [t["turn_number"] for t in turns] == [1, 2]
