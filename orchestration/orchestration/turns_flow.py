"""Flow 2 — dialogue turns (data-flow.md §2).

One PO message = one request: turn-lease acquisition → idempotency claim →
lineage-scoped input assembly → facilitator session-scoped invocation →
TurnRecord persistence → delegation execution per DelegationDecision (see
`turn_execution`) → at-most-once synthesis per turn → gate precedence →
one TurnResponse.

Gate precedence (evaluated before the response is sent): park at
facilitator turn 10; continue whenever a synthesis was produced this turn;
finalize only when `open_issues` is empty and `invoke` = none — otherwise
continue. Increment-3 scope decision (owner-approved): the two finalize
paths (`po_accepted`, gate outcome finalize) continue into flow 3, which
lands in increment 4 — until then both are answered with a retryable 503
and persist no turn state.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime

import asyncpg
from review_schemas.api import CanonicalTurnResult, TurnResponse
from review_schemas.facilitator import ResolutionItem
from review_schemas.records import TurnRecord
from review_schemas.synthesis import SynthesisReport

from . import flows, idempotency, lease, lineage, records_store, turn_execution
from .agent_clients import AgentSet, FacilitatorInvocation
from .api_errors import ApiError, make_error
from .config import Settings
from .errors import SessionLocked
from .mcp_client import McpClient

ROUTE = "POST /api/v1/sessions/{}/turns"

#: Facilitator turn cap: turn 10 parks the session (observability.md).
PARK_TURN = 10


def _now() -> datetime:
    return datetime.now(UTC)


def evaluate_gate(
    *, facilitator_turn: int, synthesis_produced: bool, delegation
) -> str:
    """Gate precedence, pure (data-flow.md §2 "Gate precedence")."""
    if facilitator_turn >= PARK_TURN:
        return "park"
    if synthesis_produced:
        return "continue"
    if not delegation.open_issues and delegation.invoke == "none":
        return "finalize"
    return "continue"


def _finalize_gap(correlation_id: str) -> ApiError:
    """Increment-3 boundary: finalization is increment 4 (flow 3)."""
    return ApiError(
        503,
        make_error(
            "UPSTREAM_UNAVAILABLE",
            "the turn reached finalization, which is not implemented in "
            "this increment (increment 4 wires flow 3); retry the same "
            "request with the same Idempotency-Key once finalization is "
            "deployed",
            correlation_id,
            retryable=True,
        ),
    )


async def run_turn(
    pool: asyncpg.Pool,
    settings: Settings,
    *,
    story_client: McpClient,
    artifact_client: McpClient,
    agents: AgentSet,
    session_id: str,
    payload: dict,
    key: uuid.UUID,
    correlation_id: str,
) -> TurnResponse:
    """Execute flow 2 for one (already validated) request body."""
    session = await records_store.get_session(pool, session_id)
    if session is None:
        raise _not_found(correlation_id)

    token = await lease.acquire(pool, session_id)
    try:
        return await _execute(
            pool,
            settings,
            story_client=story_client,
            artifact_client=artifact_client,
            agents=agents,
            session_id=session_id,
            payload=payload,
            key=key,
            correlation_id=correlation_id,
        )
    finally:
        await lease.release(pool, session_id, token)


async def _execute(
    pool: asyncpg.Pool,
    settings: Settings,
    *,
    story_client: McpClient,
    artifact_client: McpClient,
    agents: AgentSet,
    session_id: str,
    payload: dict,
    key: uuid.UUID,
    correlation_id: str,
) -> TurnResponse:
    """Turn body under the lease (claim, agents, gate, persistence)."""
    claim = await idempotency.claim(
        pool, ROUTE, session_id, key, flows.fingerprint(payload)
    )
    if claim.outcome is idempotency.ClaimOutcome.REPLAY:
        assert claim.canonical_response is not None
        return await _response_from_canonical(pool, claim.canonical_response)

    session = await records_store.get_session(pool, session_id)
    assert session is not None
    if session.state in ("parked", "completed"):
        # new key on a read-only session (park + completion are stored
        # atomically with the canonical response, so a same-key retry of
        # the parking turn always hits the REPLAY branch above)
        raise _read_only(correlation_id)
    if payload["po_accepted"]:
        # finalize path (flow 3) — increment 4
        raise _finalize_gap(correlation_id)
    deadline = time.monotonic() + settings.request_deadline_seconds
    message = payload["message"]

    turns = await records_store.list_turns(pool, session_id)
    turn_number = (turns[-1].turn_number if turns else 0) + 1
    facilitator_turn = session.facilitator_turn_count + 1
    assert facilitator_turn <= PARK_TURN, "active sessions cannot exceed turn 10"

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

    synthesis_reference, synthesis_produced = await turn_execution.maybe_synthesize(
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

    outcome = evaluate_gate(
        facilitator_turn=facilitator_turn,
        synthesis_produced=synthesis_produced,
        delegation=delegation,
    )
    if outcome == "finalize":
        # flow 3 continues here once increment 4 lands
        raise _finalize_gap(correlation_id)

    turn = await records_store.create_turn_or_get(
        pool,
        TurnRecord(
            session_id=session_id,
            turn_number=turn_number,
            correlation_id=uuid.UUID(correlation_id),
            state="succeeded",
            po_message=message,
            po_accepted=False,
            facilitator_reply=facilitator.output.reply,
            delegation=delegation,
            resolutions=resolutions,
            outcome=outcome,
            produced_artifacts=([synthesis_reference] if synthesis_produced else []),
            created_at=_now(),
            completed_at=_now(),
        ),
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
        issues=canonical.issues,
        delegation=canonical.delegation,
        resolutions=resolutions,
        synthesis=canonical.synthesis,
        report=[],
    )


async def _response_from_canonical(
    pool: asyncpg.Pool, canonical: dict
) -> TurnResponse:
    """Rebuild the single response from the stored canonical result;
    resolutions come from the authoritative TurnRecord."""
    result = CanonicalTurnResult.model_validate_json(json.dumps(canonical))
    assert not result.report_references, "finalize replays arrive in increment 4"
    turn = await records_store.get_turn(pool, result.session_id, result.turn_number)
    assert turn is not None, "completed claim without its turn record"
    return TurnResponse(
        session_id=result.session_id,
        turn_number=result.turn_number,
        outcome=result.outcome,
        state=result.state,
        facilitator_reply=result.facilitator_reply,
        issues=result.issues,
        delegation=result.delegation,
        resolutions=turn.resolutions,
        synthesis=result.synthesis,
        report=[],
    )


def _not_found(correlation_id: str) -> ApiError:
    return ApiError(
        404,
        make_error(
            "SESSION_NOT_FOUND", "no such session", correlation_id, retryable=False
        ),
    )


def _read_only(correlation_id: str) -> ApiError:
    return ApiError(
        409,
        make_error(
            "SESSION_READ_ONLY",
            "the session is parked or completed; start a new session on "
            "the same story instead",
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
