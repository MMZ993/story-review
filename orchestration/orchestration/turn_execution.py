"""Delegation execution for one dialogue turn (data-flow.md §2).

Runs the reviewers the DelegationDecision invokes (previous review + PO
extra context, parallel with sibling cancellation), saves their artifacts
idempotently, records the audit AgentRunRecords, and performs the
at-most-once per-turn synthesis (latest artifact per perspective pairing,
including the `reuse_previous` re-synthesis-only path).
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import asyncpg
from review_schemas.records import AgentRunRecord
from review_schemas.review import ReviewReport
from review_schemas.synthesis import ArtifactReference, SynthesisReport

from . import flows, lineage, records_store
from .agent_clients import (
    AgentSet,
    PerspectivePair,
    ReviewerInvocation,
    SynthesisInvocation,
    timed_invoke,
)
from .mcp_client import McpClient
from .reviewer_output_fence import story_plain_text


def _now() -> datetime:
    return datetime.now(UTC)


async def execute_delegation(
    pool: asyncpg.Pool,
    artifact_client: McpClient,
    agents: AgentSet,
    *,
    session,
    story,
    references: list[ArtifactReference],
    delegation,
    key: uuid.UUID,
    turn_number: int,
    deadline: float,
    correlation_id: str,
) -> list[ArtifactReference]:
    """Run the invoked reviewers, save their artifacts, record the runs.

    Returns the references of artifacts newly saved this turn (empty for
    invoke=none and reuse_previous turns).
    """
    invoke = delegation.invoke
    if invoke == "none":
        return []
    perspectives = ["business", "engineering"] if invoke == "both" else [invoke]
    requests = {}
    for perspective in perspectives:
        previous_reference = lineage.latest(
            references, f"review-{perspective}", perspective, correlation_id
        )
        previous = lineage.parse_content(
            ReviewReport,
            await lineage.artifact_content(
                artifact_client, previous_reference, deadline, correlation_id
            ),
        )
        requests[perspective] = ReviewerInvocation(
            story=story,
            previous_review=previous,
            extra_context=delegation.extra_context,
        )

    clients = {"business": agents.business, "engineering": agents.engineering}
    tasks = {
        perspective: asyncio.create_task(
            timed_invoke(
                clients[perspective].invoke, request, deadline=deadline
            )
        )
        for perspective, request in requests.items()
    }
    try:
        results = {}
        for perspective, task in tasks.items():
            results[perspective] = await task
    except Exception as exc:
        for task in tasks.values():
            task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        raise flows._agent_failure(exc, correlation_id, "reviewer") from exc

    story_text = story_plain_text(story)
    for perspective, result in results.items():
        request = requests[perspective]
        results[perspective] = flows._fence_result(
            result,
            perspective,
            story_text,
            correlation_id=correlation_id,
            previous_review=request.previous_review,
            extra_context=request.extra_context,
        )

    new_references = []
    for perspective, result in results.items():
        reference = await flows._save_artifact(
            artifact_client,
            type_=f"review-{perspective}",
            story_run_id=session.story_run_id,
            content=result.report,
            key=key,
            deadline=deadline,
            correlation_id=correlation_id,
        )
        new_references.append(reference)
        await record_run(
            pool,
            key,
            correlation_id,
            session,
            turn_number,
            (
                result,
                [reference],
                [
                    lineage.latest(
                        references, f"review-{perspective}", perspective
                    )
                ],
                f"{perspective}-reviewer",
            ),
        )
    return new_references


async def maybe_synthesize(
    pool: asyncpg.Pool,
    artifact_client: McpClient,
    agents: AgentSet,
    *,
    session,
    new_review_references: list[ArtifactReference],
    reuse_previous: bool,
    key: uuid.UUID,
    turn_number: int,
    deadline: float,
    correlation_id: str,
    fallback_synthesis: ArtifactReference,
) -> SynthesisOutcome:
    """At-most-once synthesis per turn: only when new artifacts exist or
    reuse_previous; pairs the latest artifact per perspective. Returns the
    (possibly new) synthesis reference, the fresh report when one was
    produced (the post-delegation summary call's input), and whether the
    synthesis ran this turn."""
    if not new_review_references and not reuse_previous:
        return SynthesisOutcome(fallback_synthesis, None, False)

    references = await lineage.list_run_artifacts(
        artifact_client, session.story_run_id, deadline, correlation_id
    )
    pairs = {}
    for perspective in ("business", "engineering"):
        reference = lineage.latest(
            references, f"review-{perspective}", perspective, correlation_id
        )
        report = lineage.parse_content(
            ReviewReport,
            await lineage.artifact_content(
                artifact_client, reference, deadline, correlation_id
            ),
        )
        pairs[perspective] = PerspectivePair(report=report, reference=reference)

    try:
        result = await timed_invoke(agents.synthesis.invoke,
            SynthesisInvocation(
                business=pairs["business"], engineering=pairs["engineering"]
            ),
            deadline=deadline,
        )
    except Exception as exc:
        raise flows._agent_failure(exc, correlation_id, "synthesis") from exc
    reference = await flows._save_artifact(
        artifact_client,
        type_="synthesis",
        story_run_id=session.story_run_id,
        content=result.report,
        key=key,
        deadline=deadline,
        correlation_id=correlation_id,
    )
    await record_run(
        pool,
        key,
        correlation_id,
        session,
        turn_number,
        (
            result,
            [reference],
            [pairs["business"].reference, pairs["engineering"].reference],
            "synthesis",
        ),
    )
    return SynthesisOutcome(reference, result.report, True)


@dataclass(frozen=True)
class SynthesisOutcome:
    """Result of `maybe_synthesize`: the turn's synthesis reference, the
    fresh report when produced (None otherwise), and whether it ran."""

    reference: ArtifactReference
    report: SynthesisReport | None
    produced: bool


async def record_run(
    pool: asyncpg.Pool,
    key: uuid.UUID,
    correlation_id: str,
    session,
    turn_number: int,
    run: tuple,
    run_label: str | None = None,
) -> None:
    """Persist one agent invocation's audit AgentRunRecord (per turn).

    `run_label` overrides the deterministic agent-run id label when one
    turn holds two invocations of the same agent (Item G / D21: the
    facilitator's post-delegation summary call uses label
    `facilitator-summary:<turn>` so the two runs stay distinct)."""
    result, output_references, input_references, agent = run
    await records_store.create_agent_run_or_get(
        pool,
        AgentRunRecord(
            agent_run_id=flows._agent_run_id(
                key, run_label or f"{agent}:{turn_number}"
            ),
            agent=agent,  # type: ignore[arg-type]
            agent_version=result.agent_version,
            prompt_sha256=result.prompt_sha256,
            story_run_id=session.story_run_id,
            session_id=session.session_id,
            correlation_id=uuid.UUID(correlation_id),
            input_references=input_references,
            output_references=output_references,
            state="succeeded",
            transport_attempts=result.transport_attempts,
            corrective_reprompts=getattr(result, "corrective_reprompts", 0),
            started_at=getattr(result, "started_at", None) or _now(),
            finished_at=getattr(result, "finished_at", None) or _now(),
        ),
    )
