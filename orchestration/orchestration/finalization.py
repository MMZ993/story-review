"""Flow 3 — readiness: the final report (data-flow.md §3).

Entered synchronously from flow 2 while the turn lock is held (gate
outcome `finalize`, or an explicit `po_accepted` client action), or
resumed directly by `POST /sessions/{id}/finalize` when a finalizing
session needs its retry.

Steps (mcp-servers.md report server, schemas.md FinalizedReview): mark
the session `finalizing` (idempotent marker for retry routing) → persist
the deterministic `finalized-review` artifact (latest synthesis +
dialogue resolutions + PO acceptance state) → `render_report` per
requested format (idempotent per `(run, format)`) → the *caller* closes
with one transaction (report references + `completed` + idempotency
completion).

Failure semantics (data-flow.md §3 failure table): retryable failures
(transport, deadline, retryable upstream) leave the session `finalizing`
and the turn lock is released by the caller's normal path — retry the
same key or the finalize endpoint. Non-retryable failures (deterministic
`RENDER_FAILED`, validation) roll the session back to `active` so no
session is permanently stuck; the acceptance turn record remains (the
PO action is durable), and a later PO turn can finalize again.
"""

from __future__ import annotations

from dataclasses import dataclass

import json

import asyncpg
import pydantic
from review_schemas.api import CanonicalReportResult, ReportResponse
from review_schemas.facilitator import FinalizedReview, ResolutionItem
from review_schemas.mcp import RenderReportInput, RenderReportOutput
from review_schemas.synthesis import ArtifactReference

from . import flows, idempotency, records_store
from .api_errors import ApiError, make_error
from .config import Settings
from .errors import IdempotencyKeyReused
from .mcp_client import (
    DeadlineExceededError,
    McpCallFailure,
    McpClient,
    McpTransportError,
)
from .signed_urls import ReportSigner

ROUTE = "POST /api/v1/sessions/{}/finalize"


class FinalizationFailed(Exception):
    """One downstream finalization failure, classified for state handling.

    `retryable` follows data-flow.md §3: True keeps the session
    `finalizing` (503 retryable); False rolls it back to `active`.
    """

    def __init__(self, api_error: ApiError, *, retryable: bool):
        super().__init__(api_error.error.code)
        self.api_error = api_error
        self.retryable = retryable


@dataclass(frozen=True)
class FinalizationResult:
    """What flow 3 produced; the caller closes the durable state."""

    final_review_reference: ArtifactReference
    report_references: list[ArtifactReference]


def aggregate_resolutions(turns) -> list[ResolutionItem]:
    """Dialogue resolutions for the final review: the latest recorded
    disposition per issue, in first-seen order (schemas.md caps 200)."""
    latest: dict[str, ResolutionItem] = {}
    for turn in turns:
        for item in turn.resolutions:
            latest[item.issue] = item
    return list(latest.values())[:200]


def remaining_open_issues(turns, *, po_accepted: bool) -> list[str]:
    """Open issues retained at acceptance (schemas.md: only an explicit
    acceptance may retain them); gate-finalize turns have none by rule 4."""
    if not po_accepted:
        return []
    for turn in reversed(turns):
        if turn.delegation is not None:
            return list(turn.delegation.open_issues)
    return []


def acceptance_state(turns) -> tuple[bool, int]:
    """(po_accepted, final_turn_number) reconstructed from the durable
    turn history — the finalize-endpoint recovery path has an empty body."""
    last = turns[-1]
    return bool(last.po_accepted), last.turn_number


async def run_flow3(
    pool: asyncpg.Pool,
    settings: Settings,
    *,
    artifact_client: McpClient,
    report_client: McpClient,
    session,
    turns,
    key,
    correlation_id: str,
    synthesis_reference: ArtifactReference,
    deadline: float,
) -> FinalizationResult:
    """Execute flow 3's downstream work for one finalizing session.

    The session is marked `finalizing` first (idempotent), then the
    finalized-review artifact is saved and every requested format is
    rendered. Rendering and saving are idempotent, so a retry after any
    failure converges without duplicate side effects; durable completion
    stays with the caller's transaction.
    """
    po_accepted, final_turn_number = acceptance_state(turns)
    review = FinalizedReview(
        story_id=session.story_id,
        story_run_id=session.story_run_id,
        synthesis_reference=synthesis_reference,
        resolutions=aggregate_resolutions(turns),
        remaining_open_issues=remaining_open_issues(
            turns, po_accepted=po_accepted
        ),
        po_accepted=po_accepted,
        final_turn_number=final_turn_number,
        finalized_at=_now(),
    )
    try:
        await records_store.update_session(
            pool, session.session_id, state="finalizing"
        )
        final_reference = await _save_final_review(
            artifact_client, session=session, review=review, key=key,
            deadline=deadline, correlation_id=correlation_id,
        )
        report_references = [
            await _render(
                report_client,
                session=session,
                final_review_reference=final_reference,
                format_name=format_name,
                deadline=deadline,
                correlation_id=correlation_id,
            )
            for format_name in session.requested_formats
        ]
    except FinalizationFailed as failure:
        if not failure.retryable:
            await records_store.update_session(
                pool, session.session_id, state="active"
            )
        raise
    return FinalizationResult(
        final_review_reference=final_reference,
        report_references=report_references,
    )


async def _save_final_review(
    artifact_client: McpClient,
    *,
    session,
    review: FinalizedReview,
    key,
    deadline: float,
    correlation_id: str,
) -> ArtifactReference:
    """Save the finalized-review artifact, classifying failures per the
    flow-3 table (retryable keeps `finalizing`, non-retryable rolls back
    to `active`) — `flows._save_artifact` raises plain ApiError."""
    try:
        return await flows._save_artifact(
            artifact_client,
            type_="finalized-review",
            story_run_id=session.story_run_id,
            content=review,
            key=key,
            deadline=deadline,
            correlation_id=correlation_id,
        )
    except ApiError as error:
        raise FinalizationFailed(
            error, retryable=error.error.retryable
        ) from error


async def _render(
    report_client: McpClient,
    *,
    session,
    final_review_reference: ArtifactReference,
    format_name: str,
    deadline: float,
    correlation_id: str,
) -> ArtifactReference:
    """One `render_report` call; failure classification per flow 3."""
    payload = RenderReportInput(
        story_run_id=session.story_run_id,  # type: ignore[arg-type]
        final_review_reference=final_review_reference,
        format=format_name,  # type: ignore[arg-type]
    ).model_dump(mode="json")
    try:
        raw = await report_client.call(
            "render_report", payload, deadline=deadline
        )
        output = RenderReportOutput.model_validate_json(json.dumps(raw))
    except pydantic.ValidationError as failure:
        # deterministic malformed output: never retried, rolls back
        raise FinalizationFailed(
            ApiError(
                503,
                make_error(
                    "UPSTREAM_UNAVAILABLE",
                    "malformed render_report output",
                    correlation_id,
                    retryable=False,
                ),
            ),
            retryable=False,
        ) from failure
    except McpCallFailure as failure:
        raise FinalizationFailed(
            ApiError(
                503,
                make_error(
                    failure.error.code,
                    failure.error.message,
                    correlation_id,
                    retryable=failure.error.retryable,
                ),
            ),
            retryable=failure.error.retryable,
        ) from failure
    except (McpTransportError, DeadlineExceededError) as failure:
        raise FinalizationFailed(
            ApiError(
                503,
                make_error(
                    "UPSTREAM_UNAVAILABLE",
                    "report MCP unavailable",
                    correlation_id,
                    retryable=True,
                ),
            ),
            retryable=True,
        ) from failure
    return output.reference


async def complete_session(
    pool: asyncpg.Pool,
    *,
    route: str,
    session_id: str,
    key,
    canonical: dict,
    result: FinalizationResult,
) -> None:
    """Atomically persist report references + `completed` and store the
    canonical response (schemas.md: completed only after every reference
    is persisted — one transaction closes the crash window)."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await records_store.update_session(
                pool,
                session_id,
                state="completed",
                final_review_reference=result.final_review_reference,
                report_references=result.report_references,
                conn=conn,
            )
            await idempotency.complete(
                pool, route, session_id, key, canonical, conn=conn
            )


def report_response(
    session_id: str, references: list[ArtifactReference], signer: ReportSigner
) -> ReportResponse:
    """Build the ReportResponse with fresh signed URLs from references."""
    return ReportResponse(
        session_id=session_id, report=signer.downloads(references)
    )


def canonical_report(session_id: str, references) -> CanonicalReportResult:
    return CanonicalReportResult(
        session_id=session_id, report_references=references
    )


def replay_report_response(
    canonical: dict, signer: ReportSigner
) -> ReportResponse:
    """Rebuild a finalize-endpoint response from its stored canonical
    result; URLs are regenerated, never stored (they expire)."""
    result = CanonicalReportResult.model_validate(canonical)
    return report_response(result.session_id, result.report_references, signer)


def map_idempotency_reused(exc: IdempotencyKeyReused, correlation_id: str) -> ApiError:
    return ApiError(
        409,
        make_error(
            "IDEMPOTENCY_KEY_REUSED", str(exc), correlation_id, retryable=False
        ),
    )


def _now():
    from datetime import UTC, datetime

    return datetime.now(UTC)
