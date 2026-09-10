"""Flow 1 — session creation (data-flow.md §1).

Story selection runs the deterministic initial pipeline: idempotency
claim → get_story → story run creation → idempotent story-artifact save →
parallel reviewer fan-out → review-artifact saves + AgentRunRecords →
synthesis → save + record → facilitator opening turn (turn 1, invoke =
none) → TurnRecord + canonical response persistence.

Crash/retry convergence: `story_run_id`, `session_id`, and every
`agent_run_id` are derived deterministically from the client's
Idempotency-Key (uuid5 — the id patterns pin only lowercase hex), and the
same key is passed to every artifact `save_artifact` (dedup scope is
`(story run, type, key)`). A re-executed partial flow therefore rewrites
the same logical rows instead of duplicating side effects; a taken-over
in-progress claim converges to the stored canonical response.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from datetime import UTC, datetime

import asyncpg
from review_schemas.api import CreateSessionResponse
from review_schemas.mcp import GetStoryInput, SaveArtifactInput, SaveArtifactOutput
from review_schemas.records import (
    AgentRunRecord,
    SessionRecord,
    StoryRunRecord,
    TurnRecord,
)
from review_schemas.review import StoryDetail
from review_schemas.synthesis import ArtifactReference

from . import idempotency, records_store
from .agent_clients import (
    AgentCallFailure,
    AgentSet,
    AgentTransportError,
    FacilitatorInvocation,
    DeadlineExceeded as AgentDeadlineExceeded,
    PerspectivePair,
    ReviewerInvocation,
    SynthesisInvocation,
)
from .api_errors import ApiError, make_error
from .config import Settings
from .errors import ConstraintViolation, IdempotencyKeyReused
from .mcp_client import (
    DeadlineExceededError,
    McpCallFailure,
    McpClient,
    McpTransportError,
)

#: Deterministic-id namespace for flow replay convergence.
FLOW_NAMESPACE = uuid.UUID("6f4f4f0a-0d63-4f4f-9f4f-2f5f5f5f5f5f")

ROUTE = "POST /api/v1/sessions"


def _derived(key: uuid.UUID, label: str) -> str:
    """Deterministic lowercase-hex id suffix derived from the idempotency key."""
    return str(uuid.uuid5(FLOW_NAMESPACE, f"{key}|{label}"))


def fingerprint(payload: dict) -> str:
    """Stable request-body fingerprint for the idempotency claim."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _agent_run_id(key: uuid.UUID, agent: str) -> str:
    return f"arun-{_derived(key, f'agent:{agent}')}"


async def _save_artifact(
    artifact_client: McpClient,
    *,
    type_: str,
    story_run_id: str,
    content,
    key: uuid.UUID,
    deadline: float,
    correlation_id: str,
) -> ArtifactReference:
    """One idempotent save_artifact call; returns the durable reference."""
    perspective = {"review-business": "business", "review-engineering": "engineering"}.get(type_)
    payload = SaveArtifactInput(
        type=type_,  # type: ignore[arg-type]
        story_run_id=story_run_id,  # type: ignore[arg-type]
        perspective=perspective,  # type: ignore[arg-type]
        content=content,
        idempotency_key=key,
    )
    try:
        raw = await artifact_client.call(
            "save_artifact", payload.model_dump(mode="json"), deadline=deadline
        )
        output = SaveArtifactOutput.model_validate_json(json.dumps(raw))
    except McpCallFailure as failure:
        raise _tool_failure(failure, correlation_id) from failure
    except (McpTransportError, DeadlineExceededError) as failure:
        raise _upstream("artifact MCP unavailable", correlation_id) from failure
    return output.reference


def _upstream(message: str, correlation_id: str) -> ApiError:
    return ApiError(
        503,
        make_error("UPSTREAM_UNAVAILABLE", message, correlation_id, retryable=True),
    )


def _tool_failure(failure: McpCallFailure, correlation_id: str) -> ApiError:
    error = failure.error
    if error.code == "STORY_NOT_FOUND":
        return ApiError(
            404,
            make_error(
                "STORY_NOT_FOUND", error.message, correlation_id, retryable=False
            ),
        )
    return ApiError(
        503,
        make_error(error.code, error.message, correlation_id, retryable=error.retryable),
    )


def _agent_failure(exc: Exception, correlation_id: str, agent: str) -> ApiError:
    """Map one downstream agent-invocation failure to the API error."""
    if isinstance(exc, AgentCallFailure):
        error = exc.error
        status = 422 if error.code in {"VALIDATION_ERROR", "DELEGATION_VALIDATION"} else 503
        return ApiError(
            status,
            make_error(
                error.code, error.message, correlation_id,
                retryable=error.retryable, agent=agent,
            ),
        )
    return _upstream(f"{agent} invocation failed", correlation_id)


async def run_create_session(
    pool: asyncpg.Pool,
    settings: Settings,
    *,
    story_client: McpClient,
    artifact_client: McpClient,
    agents: AgentSet,
    payload: dict,
    key: uuid.UUID,
    correlation_id: str,
) -> CreateSessionResponse:
    """Execute flow 1 for one (already validated) request body."""
    fingerprint_value = fingerprint(payload)
    claim = await idempotency.claim(pool, ROUTE, "", key, fingerprint_value)
    if claim.outcome is idempotency.ClaimOutcome.REPLAY:
        assert claim.canonical_response is not None
        return CreateSessionResponse.model_validate_json(
            json.dumps(claim.canonical_response)
        )
    # IN_PROGRESS (crashed holder): deterministic ids make takeover safe.

    deadline = time.monotonic() + settings.request_deadline_seconds
    story = await _get_story(
        story_client, payload["story_id"], deadline, correlation_id
    )
    run_id = f"run-{_derived(key, 'run')}"
    session_id = f"sess-{_derived(key, 'session')}"

    story_run = await records_store.create_story_run_or_get(
        pool,
        StoryRunRecord(
            story_run_id=run_id,
            story_id=story.story_id,
            state="active",
            created_at=_now(),
            updated_at=_now(),
        ),
    )

    session_record = await records_store.create_session_or_get(
        pool,
        SessionRecord(
            session_id=session_id,
            story_run_id=run_id,
            story_id=story.story_id,
            state="active",
            requested_formats=payload["requested_formats"],
            facilitator_turn_count=1,
            created_at=_now(),
            updated_at=_now(),
        ),
    )

    story_reference = await _save_artifact(
        artifact_client,
        type_="story",
        story_run_id=run_id,
        content=story,
        key=key,
        deadline=deadline,
        correlation_id=correlation_id,
    )

    try:
        reviews = await _fan_out_reviewers(agents, story, deadline)
    except Exception as exc:
        raise _agent_failure(exc, correlation_id, "reviewer") from exc
    business_review, engineering_review = reviews
    business_reference = await _save_artifact(
        artifact_client,
        type_="review-business",
        story_run_id=run_id,
        content=business_review.report,
        key=key,
        deadline=deadline,
        correlation_id=correlation_id,
    )
    engineering_reference = await _save_artifact(
        artifact_client,
        type_="review-engineering",
        story_run_id=run_id,
        content=engineering_review.report,
        key=key,
        deadline=deadline,
        correlation_id=correlation_id,
    )
    await _record_agent_runs(
        pool,
        key,
        correlation_id,
        run_id,
        session_id,
        [
            (business_review, [business_reference], [story_reference], "business-reviewer"),
            (engineering_review, [engineering_reference], [story_reference], "engineering-reviewer"),
        ],
    )

    try:
        synthesis = await agents.synthesis.invoke(
            SynthesisInvocation(
                business=PerspectivePair(
                    report=business_review.report,
                    reference=business_reference,
                ),
                engineering=PerspectivePair(
                    report=engineering_review.report,
                    reference=engineering_reference,
                ),
            ),
            deadline=deadline,
        )
    except Exception as exc:
        raise _agent_failure(exc, correlation_id, "synthesis") from exc
    synthesis_reference = await _save_artifact(
        artifact_client,
        type_="synthesis",
        story_run_id=run_id,
        content=synthesis.report,
        key=key,
        deadline=deadline,
        correlation_id=correlation_id,
    )
    await _record_agent_runs(
        pool,
        key,
        correlation_id,
        run_id,
        session_id,
        [
            (
                synthesis,
                [synthesis_reference],
                [business_reference, engineering_reference],
                "synthesis",
            )
        ],
    )

    evidence = [story_reference, business_reference, engineering_reference]
    try:
        facilitator = await agents.facilitator.invoke(
            FacilitatorInvocation(
                session_id=session_record.session_id,
                turn_number=1,
                po_message=None,
                synthesis_report=synthesis.report,
                synthesis_reference=synthesis_reference,
                evidence_references=evidence,
            ),
            deadline=deadline,
        )
    except AgentCallFailure as exc:
        raise _agent_failure(exc, correlation_id, "facilitator") from exc
    except (AgentTransportError, AgentDeadlineExceeded) as exc:
        raise _upstream("facilitator invocation failed", correlation_id) from exc

    _assert_opening_turn(facilitator.output, correlation_id)
    turn = await records_store.create_turn_or_get(
        pool,
        TurnRecord(
            session_id=session_record.session_id,
            turn_number=1,
            correlation_id=uuid.UUID(correlation_id),
            state="succeeded",
            po_message=None,
            po_accepted=False,
            facilitator_reply=facilitator.output.reply,
            delegation=facilitator.output.delegation,
            resolutions=[],
            outcome="continue",
            produced_artifacts=[synthesis_reference],
            created_at=_now(),
            completed_at=_now(),
        ),
    )
    await _record_agent_runs(
        pool,
        key,
        correlation_id,
        run_id,
        session_record.session_id,
        [
            (
                facilitator,
                [synthesis_reference],
                [synthesis_reference, *evidence],
                "facilitator",
            )
        ],
    )
    await records_store.touch_session(pool, session_record.session_id)

    response = CreateSessionResponse(
        session_id=session_record.session_id,
        story_run_id=story_run.story_run_id,
        state="active",
        opening_turn_number=1,
        facilitator_reply=turn.facilitator_reply or "",
        issues=turn.delegation.open_issues if turn.delegation else [],
        delegation=turn.delegation,  # type: ignore[arg-type]
        synthesis=synthesis_reference,
        artifact_references=[
            story_reference,
            business_reference,
            engineering_reference,
            synthesis_reference,
        ],
    )
    await idempotency.complete(
        pool, ROUTE, "", key, response.model_dump(mode="json")
    )
    return response


async def _get_story(
    story_client: McpClient,
    story_id: str,
    deadline: float,
    correlation_id: str,
) -> StoryDetail:
    """Fetch the story (with epic/roadmap context) via the story MCP."""
    payload = GetStoryInput(story_id=story_id).model_dump(mode="json")
    try:
        raw = await story_client.call("get_story", payload, deadline=deadline)
        return StoryDetail.model_validate_json(json.dumps(raw))
    except McpCallFailure as failure:
        raise _tool_failure(failure, correlation_id) from failure
    except (McpTransportError, DeadlineExceededError) as failure:
        raise _upstream("story MCP unavailable", correlation_id) from failure


def _assert_opening_turn(output, correlation_id: str) -> None:
    """Turn-1 invariants beyond schema validation (schemas.md): invoke =
    none and no resolution updates; a violation is structured 422, never
    an unenveloped response-construction failure."""
    if output.delegation.invoke != "none" or output.resolutions:
        raise ApiError(
            422,
            make_error(
                "DELEGATION_VALIDATION",
                "the opening facilitator turn must emit invoke=none and no "
                "resolution updates",
                correlation_id,
                retryable=False,
                agent="facilitator",
            ),
        )


async def _fan_out_reviewers(agents: AgentSet, story: StoryDetail, deadline: float):
    """Parallel single-turn reviewer invocations; on the first failure the
    sibling attempt is cancelled (no orphaned model cost)."""
    request = ReviewerInvocation(story=story)
    tasks = [
        asyncio.create_task(agents.business.invoke(request, deadline=deadline)),
        asyncio.create_task(agents.engineering.invoke(request, deadline=deadline)),
    ]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


async def _record_agent_runs(
    pool: asyncpg.Pool,
    key: uuid.UUID,
    correlation_id: str,
    run_id: str,
    session_id: str,
    runs: list[tuple],
) -> None:
    """Persist the audit AgentRunRecords for completed agent invocations.

    Each entry is (result, output_references, input_references, agent) so
    the audit record captures exactly what the agent consumed (agents.md:
    synthesis consumes both perspective artifacts, reviewers the story).
    """
    for result, output_references, input_references, agent in runs:
        corrective = getattr(result, "corrective_reprompts", 0)
        await records_store.create_agent_run_or_get(
            pool,
            AgentRunRecord(
                agent_run_id=_agent_run_id(key, agent),
                agent=agent,  # type: ignore[arg-type]
                agent_version=result.agent_version,
                prompt_sha256=result.prompt_sha256,
                story_run_id=run_id,
                session_id=session_id,
                correlation_id=uuid.UUID(correlation_id),
                input_references=input_references,
                output_references=output_references,
                state="succeeded",
                transport_attempts=result.transport_attempts,
                corrective_reprompts=corrective,
                started_at=_now(),
                finished_at=_now(),
            ),
        )


def map_constraint_violation(
    exc: ConstraintViolation, correlation_id: str
) -> ApiError:
    """Translate a DB invariant breach to its API error."""
    if exc.constraint == "one_active_run_per_story":
        return ApiError(
            409,
            make_error(
                "STORY_SESSION_ACTIVE",
                "the story already has an active session; restore it instead",
                correlation_id,
                retryable=False,
            ),
        )
    if isinstance(exc.__cause__, asyncpg.UniqueViolationError):
        return ApiError(
            409,
            make_error(
                "IDEMPOTENCY_KEY_REUSED",
                "conflicting durable state for this request",
                correlation_id,
                retryable=False,
            ),
        )
    return _upstream("durable-state write rejected", correlation_id)


def map_idempotency_reused(exc: IdempotencyKeyReused, correlation_id: str) -> ApiError:
    return ApiError(
        409,
        make_error(
            "IDEMPOTENCY_KEY_REUSED", str(exc), correlation_id, retryable=False
        ),
    )
