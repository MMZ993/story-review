"""Live integration: park at facilitator turn 10 (main PC, real adapters).

The facilitator is a real model steered to keep the dialogue open with
dialogue-only turns; the park gate itself is orchestration logic keyed
on the durable facilitator turn count, so the observable contract is:
turns 2–9 continue, turn 10 parks, and the parked session is read-only
(turns rejected, finalize rejected, history readable).
"""

from __future__ import annotations

import pytest

from .helpers import create_session, idem_key, live_env, post_turn

pytestmark = pytest.mark.skipif(
    live_env() is None,
    reason="live integration env missing — run via make orchestration-integration-test",
)

KEEP_OPEN_MESSAGE = (
    "Note for the record only: no facts have changed since the last "
    "synthesis. Do not invoke any reviewer and do not use "
    "reuse_previous; keep the open issues as they are and reply "
    "briefly so the dialogue stays open."
)


async def test_live_park_at_turn_ten(live_client):
    """Turns 2–9 continue; turn 10 parks; parked sessions are read-only."""
    client, pool = live_client
    session = await create_session(client, "story-05")
    session_id = session["session_id"]

    for expected_turn in range(2, 11):
        response = await post_turn(client, session_id, KEEP_OPEN_MESSAGE)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["turn_number"] == expected_turn, body
        if expected_turn < 10:
            assert body["outcome"] == "continue", body
            assert body["state"] == "active"
        else:
            assert body["outcome"] == "park", body
            assert body["state"] == "parked"

    # parked sessions are read-only: turns and finalize are rejected,
    # history stays readable
    rejected = await post_turn(client, session_id, "one more thing")
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "SESSION_READ_ONLY"

    finalize = await client.post(
        f"/api/v1/sessions/{session_id}/finalize",
        headers={"Idempotency-Key": idem_key()},
    )
    assert finalize.status_code == 409
    assert finalize.json()["error"]["code"] == "SESSION_READ_ONLY"

    detail = await client.get(f"/api/v1/sessions/{session_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["state"] == "parked"
