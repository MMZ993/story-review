"""Durable Cloud SQL record models.

Implements the "Durable Cloud SQL records" section of docs/design/schemas.md.
These sit beside ADK DatabaseSessionService tables and are never returned
through the API: response models do not inherit from them, so owner IDs,
operation IDs, lease tokens, and canonical response JSON cannot leak.
SQL-level uniqueness constraints are Phase 6; these are the validation
contracts only.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from review_schemas.base import (
    AgentRunId,
    CorrelationId,
    Format,
    LeaseToken,
    RecordState,
    RunId,
    SessionId,
    SessionState,
    Sha256,
    ShortText,
    StoryId,
    StrictModel,
    Text,
    TurnOutcome,
    UtcDatetime,
)
from review_schemas.facilitator import DelegationDecision, ResolutionItem
from review_schemas.synthesis import ArtifactReference


class StoryRunRecord(StrictModel):
    """One full review lifecycle of a story (created at story selection)."""

    story_run_id: RunId
    story_id: StoryId
    state: SessionState
    created_at: UtcDatetime
    updated_at: UtcDatetime


class SessionRecord(StrictModel):
    """The facilitator<->PO session; enforces the completion contract."""

    session_id: SessionId
    story_run_id: RunId
    story_id: StoryId
    state: SessionState
    requested_formats: list[Format] = Field(min_length=1, max_length=2)
    facilitator_turn_count: Annotated[int, Field(ge=0, le=10)] = 0
    final_review_reference: ArtifactReference | None = None
    report_references: list[ArtifactReference] = Field(
        default_factory=list,
        max_length=2,
    )
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @model_validator(mode="after")
    def validate_formats_and_artifacts(self):
        if len(set(self.requested_formats)) != len(self.requested_formats):
            raise ValueError("requested_formats must be unique")
        if self.final_review_reference is not None and (
            self.final_review_reference.type != "finalized-review"
            or self.final_review_reference.story_run_id != self.story_run_id
        ):
            raise ValueError("final review reference must belong to this story run")
        report_formats = [reference.type for reference in self.report_references]
        if any(
            type_name not in {"report-md", "report-pdf"}
            for type_name in report_formats
        ):
            raise ValueError("report_references accepts only report artifacts")
        if len(set(report_formats)) != len(report_formats):
            raise ValueError("report reference formats must be unique")
        expected_types = {
            f"report-{format_name}" for format_name in self.requested_formats
        }
        if self.state == "completed" and (
            self.final_review_reference is None
            or set(report_formats) != expected_types
        ):
            raise ValueError("completed session requires final review and every report")
        return self


class TurnLeaseRecord(StrictModel):
    """Turn-serialization lease; only the token holder may renew/release."""

    session_id: SessionId
    lease_token: LeaseToken
    acquired_at: UtcDatetime
    expires_at: UtcDatetime


class TurnRecord(StrictModel):
    """One persisted API turn (PO action + facilitator outcome)."""

    session_id: SessionId
    turn_number: Annotated[int, Field(ge=1)]
    correlation_id: CorrelationId
    state: RecordState
    po_message: Text | None = None
    po_accepted: bool = False
    facilitator_reply: Text | None = None
    delegation: DelegationDecision | None = None
    resolutions: list[ResolutionItem] = Field(default_factory=list, max_length=100)
    outcome: TurnOutcome | None = None
    produced_artifacts: list[ArtifactReference] = Field(
        default_factory=list,
        max_length=20,
    )
    created_at: UtcDatetime
    completed_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def validate_turn_state(self):
        if self.turn_number > 1 and self.po_accepted == (self.po_message is not None):
            raise ValueError("PO turns contain exactly one message or acceptance action")
        if self.state == "succeeded" and (
            self.outcome is None or self.completed_at is None
        ):
            raise ValueError("succeeded turn requires outcome and completion time")
        return self


class AgentRunRecord(StrictModel):
    """Audit unit for one invocation of one agent deployment."""

    agent_run_id: AgentRunId
    agent: Literal[
        "facilitator",
        "business-reviewer",
        "engineering-reviewer",
        "synthesis",
    ]
    agent_version: ShortText
    prompt_sha256: Sha256
    story_run_id: RunId
    session_id: SessionId | None = None
    correlation_id: CorrelationId
    input_references: list[ArtifactReference] = Field(
        default_factory=list,
        max_length=20,
    )
    output_references: list[ArtifactReference] = Field(
        default_factory=list,
        max_length=20,
    )
    state: RecordState = "pending"
    # field bound is the global maximum (short calls, 3 attempts); the
    # facilitator-specific limit of 2 is enforced by the validator below
    transport_attempts: Annotated[int, Field(ge=0, le=3)] = 0
    corrective_reprompts: Annotated[int, Field(ge=0, le=2)] = 0
    started_at: UtcDatetime
    finished_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def validate_attempt_limits(self):
        if self.agent == "facilitator" and self.transport_attempts > 2:
            raise ValueError("facilitator allows at most two transport attempts")
        if self.agent != "facilitator" and self.corrective_reprompts:
            raise ValueError("corrective re-prompts apply only to the facilitator")
        if self.state in {"succeeded", "failed"} and self.finished_at is None:
            raise ValueError("finished agent run requires finished_at")
        return self
