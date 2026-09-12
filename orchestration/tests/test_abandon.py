"""Abandon endpoint deterministic tests (D22, api-contract.md "explicit
park-now"): the state table — active/finalizing park now, terminal states
409 SESSION_READ_ONLY, unknown 404, lease contention 409 SESSION_LOCKED
retryable — plus same-key replay, story-run release, and idempotency-key
validation. Real Postgres, flow-1-created sessions."""

from __future__ import annotations

import uuid

import pytest

from orchestration import abandon_api, lease, records_store

from .conftest import TEST_USER
from .factories import (
    artifact_reference,
    session as session_record,
    story_run,
)
from .test_create_session_flow import CORR, post_create, flow_client
from .test_turns_flow import make_agents

KEY_ABANDON = "99999999-9999-4999-8999-999999999999"
KEY_OTHER = "77777777-7777-4777-8777-777777777777"


@pytest.fixture
def artifact():
    from .fakes import FakeArtifactMcp

    return FakeArtifactMcp()


@pytest.fixture
def settings():
    from .conftest import make_settings

    return make_settings()


async def _abandon(client, session_id, key=KEY_ABANDON):
    return await client.post(
        f"/api/v1/sessions/{session_id}/abandon",
        json={},
        headers={"Idempotency-Key": key, "X-Correlation-Id": CORR},
    )


async def _seed(pool, state: str):
    """Insert a session (and its story run) directly in the given state;
    owned by the default test user (the client's X-User-Id)."""
    run = story_run(user_id=TEST_USER)
    record = session_record(story_run_record=run)
    if state == "completed":
        # SessionRecord requires final review + every requested report
        record = record.model_copy(
            update={
                "final_review_reference": artifact_reference(
                    run.story_run_id, "finalized-review"
                ),
                "report_references": [
                    artifact_reference(run.story_run_id, "report-md")
                ],
            }
        )
    await records_store.create_story_run(pool, run)
    await records_store.create_session(pool, record)
    if state != "active":
        async with pool.acquire() as conn:
            async with conn.transaction():
                await records_store.update_session(
                    pool, record.session_id, state=state, conn=conn
                )
    return record


async def _make_client(pool, settings, artifact):
    return flow_client(settings, pool, artifact, make_agents())


# --- state table -----------------------------------------------------------


async def test_active_session_parks_now_and_releases_the_story(
    pool, settings, artifact
):
    client = await _make_client(pool, settings, artifact)
    created = await post_create(
        client, "22222222-2222-4222-8222-222222222222",
        {"story_id": "story-07", "requested_formats": ["md"]},
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["session_id"]

    response = await _abandon(client, session_id)
    assert response.status_code == 200, response.text
    assert response.json() == {"session_id": session_id, "state": "parked"}

    session = await records_store.get_session(pool, session_id, user_id=TEST_USER)
    assert session.state == "parked"
    assert session.facilitator_turn_count == 1  # unchanged by the abandon
    run = await records_store.get_story_run(pool, session.story_run_id)
    assert run.state == "parked"

    # the story is released: a new session on the same story succeeds
    fresh = await post_create(
        client, "33333333-3333-4333-8333-333333333333",
        {"story_id": "story-07", "requested_formats": ["md"]},
    )
    assert fresh.status_code == 201, fresh.text


async def test_finalizing_session_parks_now(pool, settings, artifact):
    client = await _make_client(pool, settings, artifact)
    record = await _seed(pool, "finalizing")

    response = await _abandon(client, record.session_id)
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "parked"
    run = await records_store.get_story_run(pool, record.story_run_id)
    assert run.state == "parked"


@pytest.mark.parametrize("state", ["parked", "completed"])
async def test_terminal_states_are_read_only(pool, settings, artifact, state):
    client = await _make_client(pool, settings, artifact)
    record = await _seed(pool, state)

    response = await _abandon(client, record.session_id)
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "SESSION_READ_ONLY"
    assert body["error"]["retryable"] is False
    assert (await records_store.get_session(pool, record.session_id, user_id=TEST_USER)).state == state


async def test_unknown_session_is_404(pool, settings, artifact):
    client = await _make_client(pool, settings, artifact)
    response = await _abandon(client, "sess-00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


async def test_lease_contention_is_session_locked_retryable(pool, settings, artifact):
    client = await _make_client(pool, settings, artifact)
    record = await _seed(pool, "active")
    token = await lease.acquire(pool, record.session_id)

    response = await _abandon(client, record.session_id)
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "SESSION_LOCKED"
    assert body["error"]["retryable"] is True
    assert body["error"]["retry_after_seconds"] >= 1

    # after the holder releases, the abandon succeeds
    assert await lease.release(pool, record.session_id, token)
    assert (await _abandon(client, record.session_id)).status_code == 200


# --- idempotency -----------------------------------------------------------


async def test_same_key_replays_the_stored_response(pool, settings, artifact):
    client = await _make_client(pool, settings, artifact)
    record = await _seed(pool, "active")

    first = await _abandon(client, record.session_id)
    assert first.status_code == 200
    replay = await _abandon(client, record.session_id)
    assert replay.status_code == 200
    assert replay.json() == first.json()


async def test_non_v4_key_is_422(pool, settings, artifact):
    client = await _make_client(pool, settings, artifact)
    record = await _seed(pool, "active")
    response = await _abandon(
        client, record.session_id, key=str(uuid.uuid1())
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_read_only_rejection_releases_a_stale_claim_row(
    pool, settings, artifact
):
    """A new key whose claim lands while the session is read-only must be
    released: a later retry of that key starts clean instead of arriving
    as IN_PROGRESS / IDEMPOTENCY_KEY_REUSED."""
    from orchestration import flows, idempotency as idem

    client = await _make_client(pool, settings, artifact)
    record = await _seed(pool, "active")
    # a crashed abandon holder left an in_progress claim for this key
    claim = await idem.claim(
        pool, abandon_api.ROUTE,
        record.session_id, uuid.UUID(KEY_OTHER), flows.fingerprint({}),
    )
    assert claim.outcome is idem.ClaimOutcome.CLAIMED
    # the session meanwhile reached a terminal state
    async with pool.acquire() as conn:
        async with conn.transaction():
            await records_store.update_session(
                pool, record.session_id, state="parked", conn=conn
            )

    response = await _abandon(client, record.session_id, key=KEY_OTHER)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_READ_ONLY"

    # the stale claim row was released: the same key claims cleanly now
    fresh = await idem.claim(
        pool, abandon_api.ROUTE,
        record.session_id, uuid.UUID(KEY_OTHER), flows.fingerprint({}),
    )
    assert fresh.outcome is idem.ClaimOutcome.CLAIMED


async def test_abandon_clears_a_stale_processing_stage(pool, settings, artifact):
    client = await _make_client(pool, settings, artifact)
    record = await _seed(pool, "finalizing")
    await records_store.set_processing_stage(pool, record.session_id, "finalizing")

    response = await _abandon(client, record.session_id)
    assert response.status_code == 200
    assert await records_store.get_processing_stage(pool, record.session_id) is None
