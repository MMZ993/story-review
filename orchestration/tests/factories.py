"""Factories for schema-valid durable records (docs/design/schemas.md
"Durable Cloud SQL records") used across the repository tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from review_schemas.facilitator import DelegationDecision, ResolutionItem
from review_schemas.records import (
    AgentRunRecord,
    SessionRecord,
    StoryRunRecord,
    TurnRecord,
)
from review_schemas.synthesis import ArtifactReference

def now() -> datetime:
    """Public test clock helper (aware UTC)."""
    return datetime.now(UTC)


_now = now


def _suffix() -> str:
    return str(uuid.uuid4())


def run_id() -> str:
    return f"run-{_suffix()}"


def session_id() -> str:
    return f"sess-{_suffix()}"


def agent_run_id() -> str:
    return f"arun-{_suffix()}"


def artifact_id() -> str:
    return f"art-{_suffix()}"


def story_run(story_id: str = "story-07", state: str = "active") -> StoryRunRecord:
    return StoryRunRecord(
        story_run_id=run_id(),
        story_id=story_id,
        state=state,
        created_at=_now(),
        updated_at=_now(),
    )


def session(
    story_run_record: StoryRunRecord | None = None,
    requested_formats: list[str] | None = None,
) -> SessionRecord:
    story_run_record = story_run_record or story_run()
    return SessionRecord(
        session_id=session_id(),
        story_run_id=story_run_record.story_run_id,
        story_id=story_run_record.story_id,
        state="active",
        requested_formats=requested_formats or ["md"],
        created_at=_now(),
        updated_at=_now(),
    )


def delegation() -> DelegationDecision:
    return DelegationDecision(
        invoke="both",
        extra_context="Check the rate limit against ops data.",
        open_issues=["B-1"],
        readiness="needs_work",
    )


def resolution(turn_number: int = 2) -> ResolutionItem:
    return ResolutionItem(
        issue="B-1",
        disposition="resolved",
        explanation="Ops confirmed 100 rps.",
        turn_number=turn_number,
    )


_CONTENT_TYPES = {
    "report-md": "text/markdown",
    "report-pdf": "application/pdf",
}


def artifact_reference(
    story_run_id: str, type_: str = "synthesis", perspective: str | None = None
) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=artifact_id(),
        story_run_id=story_run_id,
        type=type_,  # type: ignore[arg-type]
        perspective=perspective,  # type: ignore[arg-type]
        version=1,
        created_at=now(),
        content_type=_CONTENT_TYPES.get(type_, "application/json"),  # type: ignore[arg-type]
        checksum_sha256="a" * 64,
    )


def turn(
    session_record: SessionRecord,
    turn_number: int = 1,
    *,
    po_message: str | None = None,
    po_accepted: bool = False,
    with_delegation: bool = False,
    delegation_rationale_reply: str | None = None,
) -> TurnRecord:
    if turn_number == 1:
        po_message, po_accepted = None, False
    elif po_accepted:
        po_message = None
    elif po_message is None:
        po_message = "Please check the API limit."
    return TurnRecord(
        session_id=session_record.session_id,
        turn_number=turn_number,
        correlation_id=uuid.uuid4(),
        state="succeeded",
        po_message=po_message,
        po_accepted=po_accepted,
        facilitator_reply="Understood, delegating.",
        delegation_rationale_reply=delegation_rationale_reply,
        delegation=delegation() if with_delegation else None,
        resolutions=[resolution(turn_number)] if turn_number > 1 else [],
        outcome="continue",
        produced_artifacts=[
            artifact_reference(session_record.story_run_id)
        ],
        created_at=_now(),
        completed_at=_now(),
    )


def agent_run(
    session_record: SessionRecord | None = None,
    agent: str = "synthesis",
) -> AgentRunRecord:
    session_record = session_record or session()
    return AgentRunRecord(
        agent_run_id=agent_run_id(),
        agent=agent,  # type: ignore[arg-type]
        agent_version="0.1.0",
        prompt_sha256="b" * 64,
        story_run_id=session_record.story_run_id,
        session_id=session_record.session_id,
        correlation_id=uuid.uuid4(),
        state="succeeded",
        transport_attempts=1,
        started_at=_now(),
        finished_at=_now(),
    )
