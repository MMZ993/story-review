"""HTTP API request and response models.

Implements the "HTTP API models" section of docs/design/schemas.md. Header
parameters (correlation/idempotency) are FastAPI-level, not body fields; the
canonical operation-result union is what idempotent replays store and return.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from review_schemas.base import (
    Format,
    HttpsUrl,
    RunId,
    SessionId,
    SessionState,
    ShortText,
    StoryId,
    StrictModel,
    Text,
    TurnOutcome,
    UtcDatetime,
)
from review_schemas.facilitator import DelegationDecision, ResolutionItem
from review_schemas.review import StorySummary
from review_schemas.synthesis import ArtifactReference


class ListStoriesQuery(StrictModel):
    filter: ShortText | None = None


class ListStoriesResponse(StrictModel):
    stories: list[StorySummary] = Field(default_factory=list, max_length=50)


class GetStoryPath(StrictModel):
    story_id: StoryId


class ListSessionsQuery(StrictModel):
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    cursor: ShortText | None = None


class CreateSessionRequest(StrictModel):
    story_id: StoryId
    requested_formats: list[Format] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def formats_are_unique(self):
        if len(set(self.requested_formats)) != len(self.requested_formats):
            raise ValueError("requested_formats must be unique")
        return self


class TurnRequest(StrictModel):
    message: Text | None = None
    po_accepted: bool = False

    @model_validator(mode="after")
    def validate_action(self):
        if self.po_accepted == (self.message is not None):
            raise ValueError("provide exactly one of message or po_accepted=true")
        return self


class FinalizeRequest(StrictModel):
    pass


class ReportDownload(StrictModel):
    reference: ArtifactReference
    format: Format
    signed_url: HttpsUrl
    expires_at: UtcDatetime

    @model_validator(mode="after")
    def format_matches_reference(self):
        if self.reference.type != f"report-{self.format}":
            raise ValueError("download format does not match report reference")
        return self


class TurnView(StrictModel):
    turn_number: Annotated[int, Field(ge=1)]
    po_message: Text | None = None
    po_accepted: bool = False
    facilitator_reply: Text | None = None
    # Pre-delegation facilitator reply (Item G / D21): present only on turns
    # that ran a delegation / re-synthesis; `facilitator_reply` is then the
    # final post-delegation summary reply. Clients show only the final reply
    # in the default chat view; this field is audit/appendix material.
    delegation_rationale_reply: Text | None = None
    delegation: DelegationDecision | None = None
    resolutions: list[ResolutionItem] = Field(default_factory=list, max_length=100)
    outcome: TurnOutcome
    produced_artifacts: list[ArtifactReference] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_action(self):
        if self.turn_number > 1 and self.po_accepted == (self.po_message is not None):
            raise ValueError("PO turns contain exactly one message or acceptance action")
        return self


class SessionSummary(StrictModel):
    session_id: SessionId
    story_run_id: RunId
    story_id: StoryId
    state: SessionState
    requested_formats: list[Format] = Field(min_length=1, max_length=2)
    # advisory live-progress marker; null whenever no request is in flight
    processing_stage: ProcessingStage | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @model_validator(mode="after")
    def formats_are_unique(self):
        if len(set(self.requested_formats)) != len(self.requested_formats):
            raise ValueError("requested_formats must be unique")
        return self


class CreateSessionResponse(StrictModel):
    session_id: SessionId
    story_run_id: RunId
    state: Literal["active"]
    opening_turn_number: Literal[1]
    facilitator_reply: Text
    issues: list[Text] = Field(default_factory=list, max_length=100)
    delegation: DelegationDecision
    synthesis: ArtifactReference
    artifact_references: list[ArtifactReference] = Field(max_length=20)

    @model_validator(mode="after")
    def validate_opening(self):
        if self.delegation.invoke != "none":
            raise ValueError("opening turn cannot delegate re-review")
        if self.issues != self.delegation.open_issues:
            raise ValueError("issues must mirror delegation.open_issues")
        if self.synthesis.type != "synthesis":
            raise ValueError("synthesis must reference a synthesis artifact")
        return self


class TurnResponse(StrictModel):
    session_id: SessionId
    turn_number: Annotated[int, Field(ge=2)]
    outcome: TurnOutcome
    state: Literal["active", "parked", "completed"]
    facilitator_reply: Text | None = None
    # Pre-delegation reply when the turn ran a delegation (Item G / D21);
    # see TurnView — `facilitator_reply` above is always the final reply.
    delegation_rationale_reply: Text | None = None
    issues: list[Text] = Field(default_factory=list, max_length=100)
    delegation: DelegationDecision | None = None
    resolutions: list[ResolutionItem] = Field(default_factory=list, max_length=100)
    synthesis: ArtifactReference | None = None
    report: list[ReportDownload] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def response_matches_outcome(self):
        expected_state = {
            "continue": "active",
            "park": "parked",
            "finalize": "completed",
        }[self.outcome]
        if self.state != expected_state:
            raise ValueError("state does not match outcome")
        if (self.outcome == "finalize") != bool(self.report):
            raise ValueError("report downloads are required for a finalized turn and forbidden otherwise")
        if len({report.format for report in self.report}) != len(self.report):
            raise ValueError("report formats must be unique")
        if self.delegation is not None and self.issues != self.delegation.open_issues:
            raise ValueError("issues must mirror delegation.open_issues")
        if self.delegation is None and self.outcome != "finalize":
            raise ValueError("delegation is required unless the turn finalizes")
        if self.outcome != "finalize" and self.facilitator_reply is None:
            raise ValueError("continued and parked turns require a facilitator reply")
        if self.synthesis is not None and self.synthesis.type != "synthesis":
            raise ValueError("synthesis must reference a synthesis artifact")
        return self


class ListSessionsResponse(StrictModel):
    sessions: list[SessionSummary] = Field(default_factory=list, max_length=100)
    next_cursor: ShortText | None = None


#: Advisory pipeline stage of an in-flight flow-1/2/3 request (schemas.md).
ProcessingStage = Literal[
    "reviewing",
    "synthesizing",
    "facilitator",
    "delegating",
    "finalizing",
]


class SessionDetail(SessionSummary):
    facilitator_turn_count: Annotated[int, Field(ge=0, le=10)]
    turns: list[TurnView] = Field(default_factory=list, max_length=100)
    artifact_references: list[ArtifactReference] = Field(
        default_factory=list,
        max_length=1000,
    )
    reports: list[ReportDownload] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def reports_match_requested_formats(self):
        report_formats = [report.format for report in self.reports]
        if len(set(report_formats)) != len(report_formats):
            raise ValueError("report formats must be unique")
        if self.state == "completed" and set(report_formats) != set(self.requested_formats):
            raise ValueError("completed session must expose every requested format")
        if self.state != "completed" and self.reports:
            raise ValueError("only completed sessions expose report downloads")
        return self


class AbandonSessionResponse(StrictModel):
    """`POST /sessions/{id}/abandon` — explicit park-now of an active/
    finalizing session (client-side escape for a session stuck without an
    exit; see api-contract.md). The transition also parks the story run,
    releasing the story for a new session."""

    session_id: SessionId
    state: Literal["parked"]


class ReportResponse(StrictModel):
    session_id: SessionId
    report: list[ReportDownload] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def report_formats_are_unique(self):
        if len({report.format for report in self.report}) != len(self.report):
            raise ValueError("report formats must be unique")
        return self


class CanonicalTurnResult(StrictModel):
    session_id: SessionId
    turn_number: Annotated[int, Field(ge=2)]
    outcome: TurnOutcome
    state: Literal["active", "parked", "completed"]
    facilitator_reply: Text | None = None
    # Pre-delegation reply when the turn ran a delegation (Item G / D21);
    # see TurnView above.
    delegation_rationale_reply: Text | None = None
    issues: list[Text] = Field(default_factory=list, max_length=100)
    delegation: DelegationDecision | None = None
    synthesis: ArtifactReference | None = None
    report_references: list[ArtifactReference] = Field(
        default_factory=list,
        max_length=2,
    )

    @model_validator(mode="after")
    def validate_canonical_turn(self):
        expected_state = {
            "continue": "active",
            "park": "parked",
            "finalize": "completed",
        }[self.outcome]
        if self.state != expected_state:
            raise ValueError("state does not match outcome")
        if (self.outcome == "finalize") != bool(self.report_references):
            raise ValueError("report references are required only on finalization")
        report_types = [reference.type for reference in self.report_references]
        if any(type_name not in {"report-md", "report-pdf"} for type_name in report_types):
            raise ValueError("canonical turn accepts only report artifacts")
        if len(set(report_types)) != len(report_types):
            raise ValueError("report reference formats must be unique")
        return self


class CanonicalReportResult(StrictModel):
    session_id: SessionId
    report_references: list[ArtifactReference] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def report_formats_are_unique(self):
        report_types = [reference.type for reference in self.report_references]
        if any(type_name not in {"report-md", "report-pdf"} for type_name in report_types):
            raise ValueError("canonical report result accepts only report artifacts")
        if len(set(report_types)) != len(report_types):
            raise ValueError("report reference formats must be unique")
        return self


CanonicalOperationResult = (
    CreateSessionResponse | CanonicalTurnResult | CanonicalReportResult
)


class HealthDependency(StrictModel):
    name: ShortText
    reachable: bool


class HealthResponse(StrictModel):
    status: Literal["ok", "degraded"]
    dependencies: list[HealthDependency] = Field(default_factory=list, max_length=20)
