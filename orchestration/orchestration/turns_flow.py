"""Flow 2 — dialogue turns (data-flow.md §2).

One PO message = one request: turn-lease acquisition → idempotency claim →
lineage-scoped input assembly → facilitator session-scoped invocation →
TurnRecord persistence → delegation execution per DelegationDecision (see
`turn_execution`) → at-most-once synthesis per turn → gate precedence →
one TurnResponse.

Gate precedence (evaluated before the response is sent, on the turn's
FINAL typed facilitator output — the second call's when the turn produced
a synthesis, Item G / D21): park at facilitator turn 10; finalize when
`open_issues` is empty and `invoke` = none; otherwise continue. Both
finalize paths (the gate outcome and an explicit `po_accepted` client
action, which skips the facilitator and delegated work entirely and never
increments `facilitator_turn_count`) continue synchronously into flow 3
(see `finalization`) while retaining the turn lock, answering with one
TurnResponse whose `report` carries the signed downloads.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime

import asyncpg
from review_schemas.api import CanonicalTurnResult, TurnResponse
from review_schemas.facilitator import ResolutionItem, latest_resolutions
from review_schemas.records import TurnRecord
from review_schemas.synthesis import SynthesisReport

from . import (
    finalization,
    flows,
    idempotency,
    lease,
    lineage,
    records_store,
    turn_execution,
)
from .agent_clients import AgentSet, DecisionState, FacilitatorInvocation
from .api_errors import ApiError, make_error
from .config import Settings
from .errors import SessionLocked
from .mcp_client import McpClient
from .signed_urls import ReportSigner

ROUTE = "POST /api/v1/sessions/{}/turns"

#: Facilitator turn cap: turn 10 parks the session (observability.md).
PARK_TURN = 10


def _now() -> datetime:
    return datetime.now(UTC)


def evaluate_gate(*, facilitator_turn: int, delegation) -> str:
    """Gate precedence, pure (data-flow.md §2 "Gate precedence"), on the
    turn's FINAL typed output: a delegated turn's second call has already
    evaluated the fresh synthesis, so no synthesis-forces-continue rule
    exists (Item G / D21) — the final output may finalize same-turn."""
    if facilitator_turn >= PARK_TURN:
        return "park"
    if not delegation.open_issues and delegation.invoke == "none":
        return "finalize"
    return "continue"


async def run_turn(
    pool: asyncpg.Pool,
    settings: Settings,
    *,
    story_client: McpClient,
    artifact_client: McpClient,
    report_client: McpClient,
    agents: AgentSet,
    signer: ReportSigner,
    session_id: str,
    payload: dict,
    key: uuid.UUID,
    correlation_id: str,
    user_id: uuid.UUID,
) -> TurnResponse:
    """Execute flow 2 for one (already validated) request body."""
    session = await records_store.get_session(
        pool, session_id, user_id=user_id
    )
    if session is None:
        raise _not_found(correlation_id)

    token = await lease.acquire(pool, session_id)
    try:
        return await _execute(
            pool,
            settings,
            story_client=story_client,
            artifact_client=artifact_client,
            report_client=report_client,
            agents=agents,
            signer=signer,
            session_id=session_id,
            payload=payload,
            key=key,
            correlation_id=correlation_id,
            user_id=user_id,
        )
    finally:
        # the advisory stage marker never outlives the lease holder
        await records_store.set_processing_stage(pool, session_id, None)
        await lease.release(pool, session_id, token)


async def _execute(
    pool: asyncpg.Pool,
    settings: Settings,
    *,
    story_client: McpClient,
    artifact_client: McpClient,
    report_client: McpClient,
    agents: AgentSet,
    signer: ReportSigner,
    session_id: str,
    payload: dict,
    key: uuid.UUID,
    correlation_id: str,
    user_id: uuid.UUID,
) -> TurnResponse:
    """Turn body under the lease (claim, agents, gate, persistence)."""
    claim = await idempotency.claim(
        pool, ROUTE, session_id, key, flows.fingerprint(payload)
    )
    if claim.outcome is idempotency.ClaimOutcome.REPLAY:
        assert claim.canonical_response is not None
        return await _response_from_canonical(pool, claim.canonical_response, signer)

    session = await records_store.get_session(
        pool, session_id, user_id=user_id
    )
    assert session is not None
    if session.state == "finalizing":
        # same-key retry of a turn whose flow 3 failed retryably resumes
        # flow 3 directly (data-flow.md §2); a new key is rejected and its
        # fresh claim row released so it cannot later masquerade as a
        # legitimate IN_PROGRESS takeover
        if claim.outcome is not idempotency.ClaimOutcome.IN_PROGRESS:
            await idempotency.release(pool, ROUTE, session_id, key)
            raise _read_only(correlation_id, session.state)
        turns = await records_store.list_turns(pool, session_id)
        assert turns and turns[-1].outcome == "finalize", (
            "finalizing session without its finalize turn record"
        )
        synthesis_reference = await _latest_synthesis(
            artifact_client, session, deadline_of(settings), correlation_id
        )
        await records_store.set_processing_stage(pool, session_id, "finalizing")
        return await _finalize_and_respond(
            pool,
            settings,
            artifact_client=artifact_client,
            report_client=report_client,
            signer=signer,
            session=session,
            turn=turns[-1],
            turns=turns,
            synthesis_reference=synthesis_reference,
            facilitator_turn_count=None,
            key=key,
            correlation_id=correlation_id,
            deadline=deadline_of(settings),
        )
    if session.state != "active":
        # a new key on a read-only session (park + completion are stored
        # atomically with the canonical response, so a same-key retry of
        # the parking turn always hits the REPLAY branch above); the
        # rejected claim row is released so a later retry of this key
        # starts clean
        await idempotency.release(pool, ROUTE, session_id, key)
        raise _read_only(correlation_id, session.state)
    deadline = time.monotonic() + settings.request_deadline_seconds
    turns = await records_store.list_turns(pool, session_id)
    turn_number = (turns[-1].turn_number if turns else 0) + 1

    if payload["po_accepted"]:
        # explicit client action: bypass facilitator and delegated work,
        # persist the acceptance, and finalize synchronously (flow 3)
        turn = await records_store.create_turn_or_get(
            pool,
            TurnRecord(
                session_id=session_id,
                turn_number=turn_number,
                correlation_id=uuid.UUID(correlation_id),
                state="succeeded",
                po_message=None,
                po_accepted=True,
                facilitator_reply=None,
                delegation=None,
                resolutions=[],
                outcome="finalize",
                produced_artifacts=[],
                created_at=_now(),
                completed_at=_now(),
            ),
        )
        turns = await records_store.list_turns(pool, session_id)
        synthesis_reference = await _latest_synthesis(
            artifact_client, session, deadline, correlation_id
        )
        await records_store.set_processing_stage(pool, session_id, "finalizing")
        return await _finalize_and_respond(
            pool,
            settings,
            artifact_client=artifact_client,
            report_client=report_client,
            signer=signer,
            session=session,
            turn=turn,
            turns=turns,
            synthesis_reference=synthesis_reference,
            facilitator_turn_count=None,
            key=key,
            correlation_id=correlation_id,
            deadline=deadline,
        )

    message = payload["message"]
    facilitator_turn = session.facilitator_turn_count + 1
    assert facilitator_turn <= PARK_TURN, "active sessions cannot exceed turn 10"

    await records_store.set_processing_stage(pool, session_id, "facilitator")

    story, references = await lineage.assemble_inputs(
        story_client, artifact_client, session, deadline, correlation_id
    )
    synthesis_reference = lineage.latest(references, "synthesis", None, correlation_id)
    synthesis_report = lineage.parse_content(
        SynthesisReport,
        await lineage.artifact_content(
            artifact_client, synthesis_reference, deadline, correlation_id
        ),
    )
    evidence_references = [
        lineage.latest(references, "story", None, correlation_id),
        lineage.latest(references, "review-business", "business", correlation_id),
        lineage.latest(
            references, "review-engineering", "engineering", correlation_id
        ),
    ]

    try:
        facilitator = await agents.facilitator.invoke(
            FacilitatorInvocation(
                session_id=session_id,
                turn_number=facilitator_turn,
                invocation_id=flows.facilitator_invocation_id(
                    key, session_id, facilitator_turn
                ),
                po_message=message,
                synthesis_report=synthesis_report,
                synthesis_reference=synthesis_reference,
                evidence_references=evidence_references,
                decision_state=_decision_state(turns),
            ),
            deadline=deadline,
        )
    except Exception as exc:
        raise flows._agent_failure(exc, correlation_id, "facilitator") from exc

    delegation = facilitator.output.delegation
    resolutions = _stamped_resolutions(facilitator.output.resolutions, turn_number)

    await turn_execution.record_run(
        pool,
        key,
        correlation_id,
        session,
        turn_number,
        (
            facilitator,
            [synthesis_reference],
            [synthesis_reference, *evidence_references],
            "facilitator",
        ),
    )

    await records_store.set_processing_stage(pool, session_id, "delegating")
    new_references = await turn_execution.execute_delegation(
        pool,
        artifact_client,
        agents,
        session=session,
        story=story,
        references=references,
        delegation=delegation,
        key=key,
        turn_number=turn_number,
        deadline=deadline,
        correlation_id=correlation_id,
    )

    await records_store.set_processing_stage(pool, session_id, "synthesizing")
    synthesis = await turn_execution.maybe_synthesize(
        pool,
        artifact_client,
        agents,
        session=session,
        new_review_references=new_references,
        reuse_previous=delegation.reuse_previous,
        key=key,
        turn_number=turn_number,
        deadline=deadline,
        correlation_id=correlation_id,
        fallback_synthesis=synthesis_reference,
    )
    synthesis_reference = synthesis.reference

    if synthesis.produced:
        # Item G / D21: the post-delegation summary turn — the facilitator
        # is invoked a second time within the same turn, sees the fresh
        # synthesis, and produces the turn's final, gate-authoritative
        # output; the pre-delegation reply persists as audit rationale
        assert synthesis.report is not None
        await records_store.set_processing_stage(pool, session_id, "facilitator")
        summary = await _invoke_summary_facilitator(
            pool,
            agents,
            artifact_client=artifact_client,
            session=session,
            key=key,
            turn_number=turn_number,
            facilitator_turn=facilitator_turn,
            message=message,
            synthesis_report=synthesis.report,
            synthesis_reference=synthesis_reference,
            prior_state=_decision_state(turns),
            first_output=facilitator.output,
            deadline=deadline,
            correlation_id=correlation_id,
        )
        final_output = summary.output
        delegation_rationale_reply = facilitator.output.reply
    else:
        final_output = facilitator.output
        delegation_rationale_reply = None

    delegation = final_output.delegation
    resolutions = _stamped_resolutions(final_output.resolutions, turn_number)

    outcome = evaluate_gate(
        facilitator_turn=facilitator_turn,
        delegation=delegation,
    )
    turn = await records_store.create_turn_or_get(
        pool,
        TurnRecord(
            session_id=session_id,
            turn_number=turn_number,
            correlation_id=uuid.UUID(correlation_id),
            state="succeeded",
            po_message=message,
            po_accepted=False,
            facilitator_reply=final_output.reply,
            delegation_rationale_reply=delegation_rationale_reply,
            delegation=delegation,
            resolutions=resolutions,
            new_issues=list(final_output.new_issues),
            outcome=outcome,
            produced_artifacts=([synthesis_reference] if synthesis.produced else []),
            created_at=_now(),
            completed_at=_now(),
        ),
    )
    if outcome == "finalize":
        # flow 3 continues synchronously, retaining the turn lock; the
        # facilitator count is durable from the turn record onward so a
        # crash mid-flow-3 cannot lose it
        await records_store.update_session(
            pool, session_id, facilitator_turn_count=facilitator_turn
        )
        turns = await records_store.list_turns(pool, session_id)
        await records_store.set_processing_stage(pool, session_id, "finalizing")
        return await _finalize_and_respond(
            pool,
            settings,
            artifact_client=artifact_client,
            report_client=report_client,
            signer=signer,
            session=session,
            turn=turn,
            turns=turns,
            synthesis_reference=synthesis_reference,
            facilitator_turn_count=facilitator_turn,
            key=key,
            correlation_id=correlation_id,
            deadline=deadline,
        )
    return await _persist_and_respond(
        pool,
        session_id,
        key,
        turn,
        outcome,
        synthesis_reference,
        resolutions,
        facilitator_turn_count=facilitator_turn,
    )


def _merged_decision_state(prior, first_output, turn_number: int):
    """Decision state for the post-delegation summary call (Item G / D21):
    the prior turns' authoritative state PLUS this turn's first output
    (latest-wins resolutions, the pre-delegation open list) — the second
    call reconciles against decisions the first call already made."""
    base = prior or DecisionState(resolutions=[], open_issues=[])
    first_stamped = _stamped_resolutions(first_output.resolutions, turn_number)
    return DecisionState(
        resolutions=latest_resolutions([*base.resolutions, *first_stamped]),
        open_issues=list(first_output.delegation.open_issues),
    )


async def _invoke_summary_facilitator(
    pool: asyncpg.Pool,
    agents: AgentSet,
    *,
    artifact_client: McpClient,
    session,
    key: uuid.UUID,
    turn_number: int,
    facilitator_turn: int,
    message: str,
    synthesis_report,
    synthesis_reference,
    prior_state,
    first_output,
    deadline: float,
    correlation_id: str,
):
    """Second facilitator invocation of a delegated turn (Item G / D21):
    distinct invocation id (own reconciliation + corrective budget), the
    fresh synthesis report/reference, and lineage-fresh evidence
    references (the re-review artifacts just saved). Its output is the
    turn's final one; any delegation it emits executes on the next PO
    turn — orchestration simply does not execute it here."""
    run_references = await lineage.list_run_artifacts(
        artifact_client, session.story_run_id, deadline, correlation_id
    )
    evidence_references = [
        lineage.latest(run_references, "story", None, correlation_id),
        lineage.latest(run_references, "review-business", "business", correlation_id),
        lineage.latest(
            run_references, "review-engineering", "engineering", correlation_id
        ),
    ]
    try:
        summary = await agents.facilitator.invoke(
            FacilitatorInvocation(
                session_id=session.session_id,
                turn_number=facilitator_turn,
                invocation_id=flows.facilitator_summary_invocation_id(
                    key, session.session_id, facilitator_turn
                ),
                po_message=message,
                synthesis_report=synthesis_report,
                synthesis_reference=synthesis_reference,
                evidence_references=evidence_references,
                decision_state=_merged_decision_state(
                    prior_state, first_output, turn_number
                ),
            ),
            deadline=deadline,
        )
    except Exception as exc:
        raise flows._agent_failure(exc, correlation_id, "facilitator") from exc
    await turn_execution.record_run(
        pool,
        key,
        correlation_id,
        session,
        turn_number,
        (
            summary,
            [synthesis_reference],
            [synthesis_reference, *evidence_references],
            "facilitator",
        ),
        run_label=f"facilitator-summary:{turn_number}",
    )
    return summary


def deadline_of(settings: Settings) -> float:
    """Fresh end-to-end deadline for a request body under execution."""
    return time.monotonic() + settings.request_deadline_seconds


def _decision_state(turns):
    """D18: the authoritative decision state for the coming facilitator
    turn, assembled from the durable turn records — the latest-wins
    resolution map (shared helper, same aggregation finalize uses) plus
    the last delegation's open list."""
    if not turns:
        return None  # opening turn: no prior decisions exist
    resolutions = latest_resolutions(
        [item for turn in turns for item in turn.resolutions]
    )
    open_issues: list[str] = []
    for turn in reversed(turns):
        if turn.delegation is not None:
            open_issues = list(turn.delegation.open_issues)
            break
    return DecisionState(resolutions=resolutions, open_issues=open_issues)


def _stamped_resolutions(drafts, turn_number: int):
    """Turn facilitator ResolutionDrafts into durable ResolutionItems,
    stamped with this turn's number (agents.md: the LLM proposes, code
    disposes)."""
    return [
        ResolutionItem(
            issue=draft.issue,
            disposition=draft.disposition,
            explanation=draft.explanation,
            turn_number=turn_number,
        )
        for draft in drafts
    ]


async def _latest_synthesis(
    artifact_client: McpClient, session, deadline: float, correlation_id: str
):
    """The run's latest synthesis reference (final review input)."""
    references = await lineage.list_run_artifacts(
        artifact_client, session.story_run_id, deadline, correlation_id
    )
    return lineage.latest(references, "synthesis", None, correlation_id)


async def _finalize_and_respond(
    pool: asyncpg.Pool,
    settings: Settings,
    *,
    artifact_client: McpClient,
    report_client: McpClient,
    signer: ReportSigner,
    session,
    turn: TurnRecord,
    turns,
    synthesis_reference,
    facilitator_turn_count: int | None,
    key: uuid.UUID,
    correlation_id: str,
    deadline: float,
) -> TurnResponse:
    """Continue a finalizing turn into flow 3 and answer with the
    request's single response (report downloads included).

    The durable turn record exists before any downstream work, so a
    crash mid-flow-3 leaves a recoverable `finalizing` session with its
    acceptance state; the finalize endpoint resumes from there."""
    result = await finalization.run_flow3(
        pool,
        settings,
        artifact_client=artifact_client,
        report_client=report_client,
        session=session,
        turns=turns,
        key=key,
        correlation_id=correlation_id,
        synthesis_reference=synthesis_reference,
        deadline=deadline,
    )
    canonical = CanonicalTurnResult(
        session_id=session.session_id,
        turn_number=turn.turn_number,
        outcome="finalize",
        state="completed",
        facilitator_reply=turn.facilitator_reply,
        delegation_rationale_reply=turn.delegation_rationale_reply,
        issues=turn.delegation.open_issues if turn.delegation else [],
        delegation=turn.delegation,
        synthesis=synthesis_reference,
        report_references=result.report_references,
    )
    async with pool.acquire() as conn:
        async with conn.transaction():
            await records_store.update_session(
                pool,
                session.session_id,
                state="completed",
                facilitator_turn_count=facilitator_turn_count,
                final_review_reference=result.final_review_reference,
                report_references=result.report_references,
                conn=conn,
            )
            await idempotency.complete(
                pool, ROUTE, session.session_id, key,
                canonical.model_dump(mode="json"), conn=conn,
            )
    return _turn_response(canonical, resolutions=turn.resolutions, signer=signer)


def _turn_response(
    canonical: CanonicalTurnResult, *, resolutions, signer: ReportSigner
) -> TurnResponse:
    """The single response for one canonical turn result; report URLs
    are always generated fresh (they expire)."""
    return TurnResponse(
        session_id=canonical.session_id,
        turn_number=canonical.turn_number,
        outcome=canonical.outcome,
        state=canonical.state,
        facilitator_reply=canonical.facilitator_reply,
        delegation_rationale_reply=canonical.delegation_rationale_reply,
        issues=canonical.issues,
        delegation=canonical.delegation,
        resolutions=resolutions,
        synthesis=canonical.synthesis,
        report=(
            signer.downloads(canonical.report_references)
            if canonical.report_references
            else []
        ),
    )


async def _persist_and_respond(
    pool: asyncpg.Pool,
    session_id: str,
    key: uuid.UUID,
    turn: TurnRecord,
    outcome: str,
    synthesis_reference,
    resolutions,
    *,
    facilitator_turn_count: int,
) -> TurnResponse:
    """Atomically apply the session transition (park / count) and complete
    the idempotency claim with the canonical turn result, then build the
    request's single response (resolutions live only in the authoritative
    TurnRecord; replays re-read them). One transaction closes the crash
    window between a parked session and its stored canonical response —
    a same-key retry can never be locked out by SESSION_READ_ONLY."""
    canonical = CanonicalTurnResult(
        session_id=session_id,
        turn_number=turn.turn_number,
        outcome=turn.outcome or "continue",
        state="parked" if outcome == "park" else "active",
        facilitator_reply=turn.facilitator_reply,
        delegation_rationale_reply=turn.delegation_rationale_reply,
        issues=turn.delegation.open_issues if turn.delegation else [],
        delegation=turn.delegation,
        synthesis=synthesis_reference,
        report_references=[],
    )
    async with pool.acquire() as conn:
        async with conn.transaction():
            await records_store.update_session(
                pool,
                session_id,
                state="parked" if outcome == "park" else None,
                facilitator_turn_count=facilitator_turn_count,
                conn=conn,
            )
            await idempotency.complete(
                pool,
                ROUTE,
                session_id,
                key,
                canonical.model_dump(mode="json"),
                conn=conn,
            )
    return TurnResponse(
        session_id=canonical.session_id,
        turn_number=canonical.turn_number,
        outcome=canonical.outcome,
        state=canonical.state,
        facilitator_reply=canonical.facilitator_reply,
        delegation_rationale_reply=canonical.delegation_rationale_reply,
        issues=canonical.issues,
        delegation=canonical.delegation,
        resolutions=resolutions,
        synthesis=canonical.synthesis,
        report=[],
    )


async def _response_from_canonical(
    pool: asyncpg.Pool, canonical: dict, signer: ReportSigner
) -> TurnResponse:
    """Rebuild the single response from the stored canonical result;
    resolutions come from the authoritative TurnRecord, report URLs are
    regenerated fresh."""
    result = CanonicalTurnResult.model_validate_json(json.dumps(canonical))
    turn = await records_store.get_turn(pool, result.session_id, result.turn_number)
    assert turn is not None, "completed claim without its turn record"
    return _turn_response(result, resolutions=turn.resolutions, signer=signer)


def _not_found(correlation_id: str) -> ApiError:
    return ApiError(
        404,
        make_error(
            "SESSION_NOT_FOUND", "no such session", correlation_id, retryable=False
        ),
    )


def _read_only(correlation_id: str, state: str = "parked/completed") -> ApiError:
    hint = (
        "the finalize endpoint recovers it"
        if state == "finalizing"
        else "start a new session on the same story instead"
    )
    return ApiError(
        409,
        make_error(
            "SESSION_READ_ONLY",
            f"the session is {state} and accepts no dialogue turns; {hint}",
            correlation_id,
            retryable=False,
        ),
    )


def map_session_locked(exc: SessionLocked, correlation_id: str) -> ApiError:
    """SESSION_LOCKED 409: wait for the hint, then a new request/key."""
    return ApiError(
        409,
        make_error(
            "SESSION_LOCKED",
            "another request holds the session turn lease; wait for the "
            "hint and submit a new request",
            correlation_id,
            retryable=True,
            retry_after_seconds=exc.retry_after_seconds,
        ),
    )
