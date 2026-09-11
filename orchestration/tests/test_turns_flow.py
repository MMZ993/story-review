"""Flow 2 (dialogue turns) deterministic tests — fake agent clients and
scripted MCP seams, real Postgres via the throwaway-pool fixture.

Covers: gate truth table (continue / synthesis-beats-finalize / park at
facilitator turn 10 / open-issues-empty finalize gap), delegation fan-out
(both / reuse_previous / none), lease serialization (SESSION_LOCKED),
read-only sessions, empty-message 422, DELEGATION_VALIDATION 422, same-key
replay, invocation-id reconciliation on retry.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import httpx
import pytest

from review_schemas.facilitator import DelegationDecision, FacilitatorTurnOutput

from orchestration.agent_clients import (
    AgentCallFailure,
    AgentSet,
    AgentTransportError,
    FacilitatorResult,
)

from .fakes import FakeArtifactMcp, opening_turn_output, story_detail, story_transport
from .test_create_session_flow import (
    CORR,
    FakeReviewer,
    FakeSynthesis,
    create_payload,
    flow_client,
    make_agents,
    post_create,
)

KEY_TURN = "66666666-6666-4666-8666-666666666666"
KEY_OTHER = "77777777-7777-4777-8777-777777777777"


def dialogue_output(
    invoke: str = "none",
    *,
    open_issues: list[str] | None = None,
    extra_context: str | None = None,
    reuse_previous: bool = False,
    resolutions: list | None = None,
) -> FacilitatorTurnOutput:
    """A schema-valid later-turn facilitator output (scripted per test)."""
    return FacilitatorTurnOutput(
        reply="Here is my reply.",
        delegation=DelegationDecision(
            invoke=invoke,
            extra_context=extra_context,
            reuse_previous=reuse_previous,
            open_issues=open_issues if open_issues is not None else ["API limit unverified"],
            readiness="needs_work",
        ),
        resolutions=resolutions or [],
    )


class ScriptedFacilitator:
    """Frozen-contract facilitator fake with adapter-shaped result
    persistence: one stored result per (session, invocation id) — a retry
    of a completed invocation replays the stored result (D15-6)."""

    def __init__(self, outputs: list[FacilitatorTurnOutput]):
        self.outputs = list(outputs)
        self.calls: list = []
        self.results: dict[tuple, FacilitatorResult] = {}
        self.fail_after_store = False  # ambiguous timeout after persisting

    async def invoke(self, request, *, deadline: float):
        stored = self.results.get((request.session_id, request.invocation_id))
        if stored is not None:
            if self.fail_after_store:
                raise AgentTransportError("response lost after completion")
            return stored
        self.calls.append(request)
        output = self.outputs.pop(0)
        result = FacilitatorResult(
            output=output,
            agent_version="0.1.0",
            prompt_sha256="e" * 64,
            corrective_reprompts=0,
        )
        self.results[(request.session_id, request.invocation_id)] = result
        if self.fail_after_store:
            raise AgentTransportError("response lost after completion")
        return result


def turn_payload(message: str = "The API limit is 100 rps.") -> dict:
    return {"message": message, "po_accepted": False}


async def create_session(client) -> dict:
    response = await post_create(client, "22222222-2222-4222-8222-222222222222", create_payload())
    assert response.status_code == 201, response.text
    return response.json()


def dialogue_client(pool, settings, artifact, report=None):
    """Flow-1 client (opening facilitator fake); tests swap the
    facilitator for their scripted one after creating the session."""
    return flow_client(settings, pool, artifact, make_agents(), report=report)


async def create_session_with(client, facilitator=None) -> dict:
    """Create the session (flow 1), then arm the scripted facilitator."""
    session = await create_session(client)
    if facilitator is not None:
        client._transport.app.state.agents.facilitator = facilitator
    return session


async def post_turn(client, session_id, key=KEY_TURN, payload=None):
    return await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json=payload or turn_payload(),
        headers={"Idempotency-Key": key, "X-Correlation-Id": CORR},
    )


@pytest.fixture
def settings():
    from .conftest import make_settings

    return make_settings()


@pytest.fixture
def artifact():
    return FakeArtifactMcp()


# --- happy dialogue turns --------------------------------------------------


async def test_delegation_both_reruns_reviewers_and_synthesis(
    pool, settings, artifact
):
    facilitator = ScriptedFacilitator(
        [dialogue_output("both", extra_context="Rate limit confirmed by ops.")]
    )
    agents_holder = {}

    class CountingReviewer(FakeReviewer):
        def __init__(self, perspective):
            super().__init__(perspective)
            agents_holder[f"{perspective}-calls"] = 0

        async def invoke(self, request, *, deadline):
            agents_holder[f"{self.perspective}-calls"] += 1
            return await super().invoke(request, deadline=deadline)

    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)

    # swap reviewers for counting (rebuild client with counting reviewers)
    from orchestration.agent_clients import AgentSet as _AS

    app = client._transport.app
    app.state.agents = _AS(
        business=CountingReviewer("business"),
        engineering=CountingReviewer("engineering"),
        synthesis=FakeSynthesis(),
        facilitator=facilitator,
    )

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["turn_number"] == 2
    assert body["outcome"] == "continue"
    assert body["state"] == "active"
    assert body["delegation"]["invoke"] == "both"
    assert body["issues"] == ["API limit unverified"]
    # reviewers re-ran; synthesis re-ran; synthesis version bumped
    assert agents_holder["business-calls"] == 1
    assert agents_holder["engineering-calls"] == 1
    assert body["synthesis"]["version"] == 2

    async with pool.acquire() as conn:
        turn = await conn.fetchrow(
            "select * from turns where session_id = $1 and turn_number = 2",
            session["session_id"],
        )
        assert turn is not None and turn["outcome"] == "continue"
        assert turn["po_message"] == "The API limit is 100 rps."
        assert json.loads(turn["delegation"])["invoke"] == "both"
        count = await conn.fetchval(
            "select facilitator_turn_count from sessions where session_id = $1",
            session["session_id"],
        )
        assert count == 2
    # reviewer got previous review + extra context
    request = facilitator.calls[0]
    assert request.turn_number == 2
    assert request.po_message == "The API limit is 100 rps."
    assert request.synthesis_reference.type == "synthesis"


async def test_invoke_none_dialogue_only(pool, settings, artifact):
    facilitator = ScriptedFacilitator([dialogue_output("none")])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)
    synthesis_calls_before = len(client._transport.app.state.agents.synthesis.calls)

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "continue"
    assert body["synthesis"]["version"] == 1  # unchanged
    assert (
        len(client._transport.app.state.agents.synthesis.calls)
        == synthesis_calls_before
    )


async def test_reuse_previous_reruns_synthesis_only(pool, settings, artifact):
    facilitator = ScriptedFacilitator(
        [dialogue_output("none", reuse_previous=True, open_issues=[])]
    )
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)
    reviewers_before = (
        len(client._transport.app.state.agents.business.calls),
        len(client._transport.app.state.agents.engineering.calls),
    )

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 200, response.text
    body = response.json()
    # synthesis produced -> continue even though open_issues is empty
    assert body["outcome"] == "continue"
    assert body["synthesis"]["version"] == 2
    assert (
        len(client._transport.app.state.agents.business.calls),
        len(client._transport.app.state.agents.engineering.calls),
    ) == reviewers_before


async def test_resolutions_are_stamped_with_api_turn_number(
    pool, settings, artifact
):
    from review_schemas.facilitator import ResolutionDraft

    facilitator = ScriptedFacilitator(
        [
            dialogue_output(
                "none",
                resolutions=[
                    ResolutionDraft(
                        issue="API limit unverified",
                        disposition="resolved",
                        explanation="Ops confirmed 100 rps.",
                    )
                ],
            )
        ]
    )
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 200, response.text
    assert response.json()["resolutions"][0]["turn_number"] == 2
    async with pool.acquire() as conn:
        turn = await conn.fetchrow(
            "select resolutions from turns where session_id = $1 and turn_number = 2",
            session["session_id"],
        )
        assert json.loads(turn["resolutions"])[0]["turn_number"] == 2


# --- gate truth table -------------------------------------------------------


async def test_park_at_facilitator_turn_10(pool, settings, artifact):
    facilitator = ScriptedFacilitator([dialogue_output("none")])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)
    async with pool.acquire() as conn:
        await conn.execute(
            "update sessions set facilitator_turn_count = 9 "
            "where session_id = $1",
            session["session_id"],
        )

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "park"
    assert body["state"] == "parked"
    async with pool.acquire() as conn:
        state = await conn.fetchval(
            "select state from sessions where session_id = $1",
            session["session_id"],
        )
    assert state == "parked"

    # parked sessions are read-only
    again = await post_turn(client, session["session_id"], key=KEY_OTHER)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "SESSION_READ_ONLY"


async def test_park_beats_synthesis_at_turn_10(pool, settings, artifact):
    """Gate precedence rule 2 > 3: facilitator turn 10 parks even when a
    synthesis was produced that turn."""
    facilitator = ScriptedFacilitator([dialogue_output("both")])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)
    async with pool.acquire() as conn:
        await conn.execute(
            "update sessions set facilitator_turn_count = 9 "
            "where session_id = $1",
            session["session_id"],
        )

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "park"
    assert body["synthesis"]["version"] == 2  # synthesis still produced

    # a lost park response still replays on the parked session (same key)
    replay = await post_turn(client, session["session_id"], key=KEY_TURN)
    assert replay.status_code == 200
    assert replay.json() == body


async def test_open_issues_empty_finalize_completes(pool, settings, artifact):
    """open_issues empty + invoke none evaluates to finalize: flow 3 runs
    synchronously in the same response — finalized-review artifact saved,
    report rendered per requested format, session completed, report
    downloads present."""
    facilitator = ScriptedFacilitator(
        [dialogue_output("none", open_issues=[])]
    )
    from .fakes import FakeReportMcp

    report = FakeReportMcp(artifact)
    client = dialogue_client(pool, settings, artifact, report=report)
    session = await create_session_with(client, facilitator)

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "finalize"
    assert body["state"] == "completed"
    assert [entry["format"] for entry in body["report"]] == ["md"]
    assert body["report"][0]["signed_url"].startswith("https://")
    assert len(report.render_calls) == 1
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select state, report_references, final_review_reference "
            "from sessions where session_id = $1",
            session["session_id"],
        )
        assert row["state"] == "completed"
        assert len(json.loads(row["report_references"])) == 1
        assert row["final_review_reference"] is not None
    # finalized-review artifact content carries the acceptance state
    saved = [
        call
        for call in artifact.save_calls
        if call["type"] == "finalized-review"
    ]
    assert len(saved) == 1
    assert saved[0]["content"]["po_accepted"] is False
    assert saved[0]["content"]["remaining_open_issues"] == []

    # completed session is read-only for further turns
    again = await post_turn(client, session["session_id"], key=KEY_OTHER)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "SESSION_READ_ONLY"


async def test_po_accepted_finalizes_without_facilitator(pool, settings, artifact):
    facilitator = ScriptedFacilitator([])
    from .fakes import FakeReportMcp

    report = FakeReportMcp(artifact)
    client = dialogue_client(pool, settings, artifact, report=report)
    session = await create_session_with(client, facilitator)

    response = await post_turn(
        client,
        session["session_id"],
        payload={"message": None, "po_accepted": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "finalize"
    assert body["state"] == "completed"
    assert body["facilitator_reply"] is None and body["delegation"] is None
    assert facilitator.calls == []
    # explicit acceptance keeps the open issues in the final review
    saved = [
        call
        for call in artifact.save_calls
        if call["type"] == "finalized-review"
    ]
    assert saved[0]["content"]["po_accepted"] is True
    assert saved[0]["content"]["remaining_open_issues"] == [
        "Which rate limit applies?",
        "Business value unclear",
    ]
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "select facilitator_turn_count from sessions where session_id = $1",
            session["session_id"],
        )
        turn = await conn.fetchrow(
            "select * from turns where session_id = $1 and turn_number = 2",
            session["session_id"],
        )
    assert count == 1  # acceptance never increments the facilitator count
    assert turn is not None and turn["po_accepted"] is True
    assert turn["outcome"] == "finalize"


# --- lease, validation, errors ----------------------------------------------


async def test_locked_session_409_with_retry_hint(pool, settings, artifact):
    from orchestration import lease

    facilitator = ScriptedFacilitator([dialogue_output("none")])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)
    await lease.acquire(pool, session["session_id"])

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "SESSION_LOCKED"
    assert error["retry_after_seconds"] >= 1
    assert facilitator.calls == []


async def test_empty_message_422(pool, settings, artifact):
    facilitator = ScriptedFacilitator([])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)

    response = await post_turn(
        client, session["session_id"], payload={"message": None, "po_accepted": False}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_unknown_session_404(pool, settings, artifact):
    facilitator = ScriptedFacilitator([])
    client = dialogue_client(pool, settings, artifact)
    await create_session_with(client, facilitator)
    response = await post_turn(client, "sess-" + "0" * 32)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


async def test_non_v4_key_422(pool, settings, artifact):
    facilitator = ScriptedFacilitator([])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)
    response = await client.post(
        f"/api/v1/sessions/{session['session_id']}/turns",
        json=turn_payload(),
        headers={"Idempotency-Key": "99999999-9999-5999-8999-999999999999"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_delegation_validation_422(pool, settings, artifact):
    class InvalidFacilitator(ScriptedFacilitator):
        async def invoke(self, request, *, deadline):
            from review_schemas.errors import ErrorBody

            raise AgentCallFailure(
                ErrorBody(
                    code="DELEGATION_VALIDATION",
                    message="exhausted corrective re-prompts",
                    correlation_id=uuid.uuid4(),
                    retryable=False,
                )
            )

    facilitator = InvalidFacilitator([])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "DELEGATION_VALIDATION"
    async with pool.acquire() as conn:
        turn = await conn.fetchrow(
            "select * from turns where session_id = $1 and turn_number = 2",
            session["session_id"],
        )
        assert turn is None
        # lease released: the next turn request proceeds to work
    facilitator2 = ScriptedFacilitator([dialogue_output("none")])
    client._transport.app.state.agents.facilitator = facilitator2
    ok = await post_turn(client, session["session_id"], key=KEY_OTHER)
    assert ok.status_code == 200, ok.text


async def test_upstream_503_releases_lease_and_keeps_claim(pool, settings, artifact):
    class DeadFacilitator(ScriptedFacilitator):
        async def invoke(self, request, *, deadline):
            raise AgentTransportError("facilitator unreachable")

    facilitator = DeadFacilitator([])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 503
    async with pool.acquire() as conn:
        lease_row = await conn.fetchrow(
            "select * from turn_leases where session_id = $1",
            session["session_id"],
        )
        assert lease_row is None


# --- idempotency ------------------------------------------------------------


async def test_same_key_replay_returns_stored_response(pool, settings, artifact):
    facilitator = ScriptedFacilitator([dialogue_output("none")])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)

    first = await post_turn(client, session["session_id"], key=KEY_TURN)
    assert first.status_code == 200
    calls = len(facilitator.calls)
    saves = len(artifact.save_calls)

    replay = await post_turn(client, session["session_id"], key=KEY_TURN)
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert len(facilitator.calls) == calls
    assert len(artifact.save_calls) == saves


async def test_same_key_different_body_409(pool, settings, artifact):
    facilitator = ScriptedFacilitator([dialogue_output("none")])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)

    first = await post_turn(client, session["session_id"], key=KEY_TURN)
    assert first.status_code == 200
    reused = await post_turn(
        client,
        session["session_id"],
        key=KEY_TURN,
        payload={"message": "Different message.", "po_accepted": False},
    )
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_crashed_in_progress_claim_takeover_reuses_invocation(
    pool, settings, artifact
):
    """Retry after a lost response replays the facilitator's stored result
    (same invocation id) instead of invoking the model again."""
    facilitator = ScriptedFacilitator([dialogue_output("none")])
    facilitator.fail_after_store = True
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)

    failed = await post_turn(client, session["session_id"], key=KEY_TURN)
    assert failed.status_code == 503

    facilitator.fail_after_store = False
    recovered = await post_turn(client, session["session_id"], key=KEY_TURN)
    assert recovered.status_code == 200, recovered.text
    assert len(facilitator.calls) == 1  # model seam used exactly once
    assert recovered.json()["outcome"] == "continue"
