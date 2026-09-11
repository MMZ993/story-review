"""Flows 3+4 deterministic tests — finalization retry endpoint, report
endpoint, render-failure recovery, replay after lost responses, signed
URLs, completed-session detail (fake report MCP seam, real Postgres).
"""

from __future__ import annotations

import uuid

import pytest

from review_schemas.errors import ErrorBody

from .fakes import FakeArtifactMcp, FakeReportMcp
from .test_create_session_flow import CORR
from .test_turns_flow import (
    KEY_OTHER,
    KEY_TURN,
    ScriptedFacilitator,
    create_session_with,
    dialogue_client,
    dialogue_output,
    post_turn,
)

KEY_FINALIZE = "88888888-8888-4888-8888-888888888888"


@pytest.fixture
def settings():
    from .conftest import make_settings

    return make_settings()


@pytest.fixture
def artifact():
    return FakeArtifactMcp()


def finalize_client(pool, settings, artifact, report=None):
    report = report if report is not None else FakeReportMcp(artifact)
    return dialogue_client(pool, settings, artifact, report=report), report


async def post_finalize(client, session_id, key=KEY_FINALIZE):
    return await client.post(
        f"/api/v1/sessions/{session_id}/finalize",
        json={},
        headers={"Idempotency-Key": key, "X-Correlation-Id": CORR},
    )


async def completed_session(client_and_report, *, po_accepted=True):
    """A session driven to completion via an explicit acceptance turn."""
    client, report = client_and_report
    facilitator = ScriptedFacilitator([])
    session = await create_session_with(client, facilitator)
    if po_accepted:
        response = await post_turn(
            client,
            session["session_id"],
            payload={"message": None, "po_accepted": True},
        )
        assert response.status_code == 200, response.text
    return client, report, session


# --- finalize endpoint state machine ----------------------------------------


async def test_finalize_active_session_409_not_finalizing(pool, settings, artifact):
    client, _ = finalize_client(pool, settings, artifact)
    facilitator = ScriptedFacilitator([])
    session = await create_session_with(client, facilitator)
    response = await post_finalize(client, session["session_id"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NOT_FINALIZING"


async def test_finalize_parked_session_409_read_only(pool, settings, artifact):
    client, _ = finalize_client(pool, settings, artifact)
    facilitator = ScriptedFacilitator([dialogue_output("none")])
    session = await create_session_with(client, facilitator)
    async with pool.acquire() as conn:
        await conn.execute(
            "update sessions set state = 'parked' where session_id = $1",
            session["session_id"],
        )
    response = await post_finalize(client, session["session_id"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_READ_ONLY"


async def test_finalize_unknown_session_404(pool, settings, artifact):
    client, _ = finalize_client(pool, settings, artifact)
    response = await post_finalize(client, "sess-" + "0" * 32)
    assert response.status_code == 404


async def test_finalize_completed_session_returns_fresh_urls_no_writes(
    pool, settings, artifact
):
    client, report = finalize_client(pool, settings, artifact)
    _, _, session = await completed_session((client, report))
    first = await post_finalize(client, session["session_id"])
    assert first.status_code == 200, first.text
    renders = len(report.render_calls)
    refs = [entry["reference"] for entry in first.json()["report"]]

    # a different key on a completed session is read-only: same references,
    # fresh signed URLs, no new renders
    second = await post_finalize(client, session["session_id"], key=KEY_OTHER)
    assert second.status_code == 200
    assert [entry["reference"] for entry in second.json()["report"]] == refs
    assert len(report.render_calls) == renders


# --- retryable render failure + finalize-endpoint recovery -------------------


async def test_retryable_render_failure_stays_finalizing_and_recovers(
    pool, settings, artifact
):
    report = FakeReportMcp(artifact)
    for _ in range(3):  # exhaust the short-call retry policy
        report.failures.append(
            ErrorBody(
                code="UPSTREAM_UNAVAILABLE",
                message="report render timed out",
                correlation_id=uuid.uuid4(),
                retryable=True,
                retry_after_seconds=5,
            )
        )
    client, _ = finalize_client(pool, settings, artifact, report=report)
    facilitator = ScriptedFacilitator([])
    session = await create_session_with(client, facilitator)

    failed = await post_turn(
        client,
        session["session_id"],
        payload={"message": None, "po_accepted": True},
    )
    assert failed.status_code == 503, failed.text
    assert failed.json()["error"]["retryable"] is True
    async with pool.acquire() as conn:
        state = await conn.fetchval(
            "select state from sessions where session_id = $1",
            session["session_id"],
        )
        lease_row = await conn.fetchrow(
            "select * from turn_leases where session_id = $1",
            session["session_id"],
        )
    assert state == "finalizing"
    assert lease_row is None  # lock released for the retry

    # a later turn with a new key is rejected (finalizing is not active
    # dialogue state); the rejected claim is released, so retrying that
    # same new key keeps getting the read-only rejection instead of
    # arriving as an IN_PROGRESS takeover
    for _ in range(2):
        later = await post_turn(client, session["session_id"], key=KEY_OTHER)
        assert later.status_code == 409
        assert later.json()["error"]["code"] == "SESSION_READ_ONLY"

    # the same-key retry resumes flow 3 directly: no facilitator call, no
    # second turn record — the acceptance turn completes (data-flow.md §2)
    facilitator_probe = ScriptedFacilitator([])
    client._transport.app.state.agents.facilitator = facilitator_probe
    resumed = await post_turn(
        client,
        session["session_id"],
        payload={"message": None, "po_accepted": True},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["outcome"] == "finalize"
    assert facilitator_probe.calls == []
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "select count(*) from turns where session_id = $1",
            session["session_id"],
        )
        state = await conn.fetchval(
            "select state from sessions where session_id = $1",
            session["session_id"],
        )
    assert count == 2
    assert state == "completed"

    # a different key sees the completed session read-only via finalize
    completed_view = await post_finalize(client, session["session_id"], key=KEY_OTHER)
    assert completed_view.status_code == 200
    assert [entry["format"] for entry in completed_view.json()["report"]] == ["md"]
    assert all(
        entry["signed_url"].startswith("https://") for entry in completed_view.json()["report"]
    )


async def test_finalize_endpoint_replay_after_lost_response(
    pool, settings, artifact
):
    client, report = finalize_client(pool, settings, artifact)
    facilitator = ScriptedFacilitator([])
    session = await create_session_with(client, facilitator)
    acceptance = await post_turn(
        client,
        session["session_id"],
        payload={"message": None, "po_accepted": True},
    )
    assert acceptance.status_code == 200, acceptance.text

    # simulate a lost response: the claim row is completed but no client
    # saw it — the same key replays the canonical result with fresh URLs
    first = await post_finalize(client, session["session_id"], key=KEY_FINALIZE)
    assert first.status_code == 200, first.text
    renders = len(report.render_calls)
    refs = [entry["reference"] for entry in first.json()["report"]]
    replay = await post_finalize(client, session["session_id"], key=KEY_FINALIZE)
    assert replay.status_code == 200
    assert [entry["reference"] for entry in replay.json()["report"]] == refs
    assert len(report.render_calls) == renders


async def test_non_retryable_render_failure_rolls_back_to_active(
    pool, settings, artifact
):
    report = FakeReportMcp(artifact)
    report.failures.append(
        ErrorBody(
            code="RENDER_FAILED",
            message="deterministic render defect",
            correlation_id=uuid.uuid4(),
            retryable=False,
        )
    )
    client, _ = finalize_client(pool, settings, artifact, report=report)
    facilitator = ScriptedFacilitator([])
    session = await create_session_with(client, facilitator)

    failed = await post_turn(
        client,
        session["session_id"],
        payload={"message": None, "po_accepted": True},
    )
    assert failed.status_code == 503, failed.text
    assert failed.json()["error"]["retryable"] is False
    assert failed.json()["error"]["code"] == "RENDER_FAILED"
    async with pool.acquire() as conn:
        state = await conn.fetchval(
            "select state from sessions where session_id = $1",
            session["session_id"],
        )
    assert state == "active"

    # the session is usable again: a later PO turn finalizes once the
    # defect is corrected
    report.failures.clear()
    client._transport.app.state.agents.facilitator = ScriptedFacilitator(
        [dialogue_output("none", open_issues=[])]
    )
    retry = await post_turn(
        client,
        session["session_id"],
        key=KEY_TURN,
        payload={"message": None, "po_accepted": True},
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["outcome"] == "finalize"


async def test_non_retryable_artifact_save_failure_rolls_back_to_active(
    pool, settings, artifact
):
    """A deterministic finalized-review save failure (non-retryable) also
    rolls the session back to active — no session is permanently stuck in
    finalizing (data-flow.md §3)."""
    client, _ = finalize_client(pool, settings, artifact)
    facilitator = ScriptedFacilitator([])
    session = await create_session_with(client, facilitator)
    artifact.save_failures.append(
        ErrorBody(
            code="VALIDATION_ERROR",
            message="finalized review content rejected",
            correlation_id=uuid.uuid4(),
            retryable=False,
        )
    )

    failed = await post_turn(
        client,
        session["session_id"],
        payload={"message": None, "po_accepted": True},
    )
    assert failed.status_code == 503, failed.text
    assert failed.json()["error"]["retryable"] is False
    assert failed.json()["error"]["code"] == "VALIDATION_ERROR"
    async with pool.acquire() as conn:
        state = await conn.fetchval(
            "select state from sessions where session_id = $1",
            session["session_id"],
        )
        count = await conn.fetchval(
            "select facilitator_turn_count from sessions where session_id = $1",
            session["session_id"],
        )
    assert state == "active"
    assert count == 1


# --- report endpoint ---------------------------------------------------------


async def test_report_endpoint_regenerates_signed_urls(pool, settings, artifact):
    client, report = finalize_client(pool, settings, artifact)
    _, _, session = await completed_session((client, report))
    response = await client.get(
        f"/api/v1/sessions/{session['session_id']}/report",
        headers={"X-Correlation-Id": CORR},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [entry["format"] for entry in body["report"]] == ["md"]
    assert all(
        entry["signed_url"].startswith("https://") for entry in body["report"]
    )


async def test_report_endpoint_not_ready_409(pool, settings, artifact):
    client, _ = finalize_client(pool, settings, artifact)
    facilitator = ScriptedFacilitator([])
    session = await create_session_with(client, facilitator)
    response = await client.get(
        f"/api/v1/sessions/{session['session_id']}/report",
        headers={"X-Correlation-Id": CORR},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REPORT_NOT_READY"


async def test_report_endpoint_unknown_session_404(pool, settings, artifact):
    client, _ = finalize_client(pool, settings, artifact)
    response = await client.get(
        f"/api/v1/sessions/sess-{'0' * 32}/report",
        headers={"X-Correlation-Id": CORR},
    )
    assert response.status_code == 404


# --- completed-session detail exposes report downloads -----------------------


async def test_completed_session_detail_exposes_reports(pool, settings, artifact):
    client, report = finalize_client(pool, settings, artifact)
    _, _, session = await completed_session((client, report))
    response = await client.get(
        f"/api/v1/sessions/{session['session_id']}",
        headers={"X-Correlation-Id": CORR},
    )
    assert response.status_code == 200, response.text
    detail = response.json()
    assert [entry["format"] for entry in detail["reports"]] == ["md"]
    last = detail["turns"][-1]
    assert last["po_accepted"] is True and last["outcome"] == "finalize"


# --- signed URL shape ---------------------------------------------------------


async def test_signed_urls_carry_expiry_and_signature(pool, settings, artifact):
    client, report = finalize_client(pool, settings, artifact)
    _, _, session = await completed_session((client, report))
    response = await client.get(
        f"/api/v1/sessions/{session['session_id']}/report",
        headers={"X-Correlation-Id": CORR},
    )
    entry = response.json()["report"][0]
    url = entry["signed_url"]
    assert "X-Goog-Signature=" in url and "X-Goog-Expires" in url
    assert entry["expires_at"] is not None
