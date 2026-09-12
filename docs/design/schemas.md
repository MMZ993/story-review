# Shared schema specification

This document defines the authoritative Pydantic v2 contracts shared by HTTP clients,
agents, orchestration, MCP servers, persistence code, and tests. The implementation lives
in `shared/review_schemas`; changing one of these models is a contract change and requires
a shared-package version bump.

## Strict base types

All timestamps are timezone-aware UTC values. JSON requests may encode UUIDs and
timestamps as strings; after JSON decoding, Pydantic rejects unknown fields, invalid
formats, and unintended coercion.

```python
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    UUID4,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


StorySource = Literal["azure", "mock"]

StoryId = Annotated[
    str,
    StringConstraints(
        pattern=r"^(story-[0-9]{2}|ado-[0-9]{1,8})$", min_length=5, max_length=12
    ),
]
# `story-NN` ids come from the frozen mock dataset; `ado-N` ids are live
# Azure DevOps work items (story MCP server source selection). The two
# id spaces never mix within a call or a story run.
RunId = Annotated[
    str,
    StringConstraints(
        pattern=r"^run-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        min_length=40,
        max_length=40,
    ),
]
SessionId = Annotated[
    str,
    StringConstraints(
        pattern=r"^sess-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        min_length=41,
        max_length=41,
    ),
]
ArtifactId = Annotated[
    str,
    StringConstraints(
        pattern=r"^art-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        min_length=40,
        max_length=40,
    ),
]
AgentRunId = Annotated[
    str,
    StringConstraints(
        pattern=r"^arun-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        min_length=41,
        max_length=41,
    ),
]
# A bare UUID v4 supplied by the client via the X-User-Id header; it groups a
# user's sessions/story runs and is not a prefixed resource id.
UserId = UUID4
Text = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000),
]
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
HttpsUrl = Annotated[
    str,
    StringConstraints(pattern=r"^https://", min_length=9, max_length=4096),
]
UtcDatetime = AwareDatetime
IdempotencyKey = UUID4
CorrelationId = UUID4
LeaseToken = UUID4

Format = Literal["md", "pdf"]
Perspective = Literal["business", "engineering"]
ArtifactType = Literal[
    "story",
    "review-business",
    "review-engineering",
    "synthesis",
    "finalized-review",
    "report-md",
    "report-pdf",
]
SaveArtifactType = Literal[
    "story",
    "review-business",
    "review-engineering",
    "synthesis",
    "finalized-review",
]
SessionState = Literal[
    "active",
    "parked",
    "finalizing",
    "completed",
]
TurnOutcome = Literal["continue", "park", "finalize"]
RecordState = Literal["pending", "running", "succeeded", "failed"]
```

## Identifiers and lineage

| ID | Format | Created by | Scope / meaning |
|---|---|---|---|
| `correlation_id` | UUID v4 | FastAPI, at first client call of a request | one HTTP request end-to-end (propagated to agents and MCP calls) |
| `story_id` | `story-NN` (dataset) | dataset | backlog identity, stable across sessions |
| `story_run_id` | `run-{uuid}` | FastAPI, once at story selection (`POST /sessions`) | one full review lifecycle of a story; scopes all artifacts of that run |
| `session_id` | `sess-{uuid}` | FastAPI, at facilitator-session creation | facilitator ↔ PO conversation; exactly one per story run |
| `agent_run_id` | `arun-{uuid}` | FastAPI, before each agent invocation | one invocation of one agent deployment (audit unit) |
| `artifact_id` | `art-{uuid}` | artifact MCP server, at `save_artifact` | immutable artifact identity |
| `version` | integer ≥ 1 | artifact MCP server, monotonically per (`story_run_id`, `type`) | ordering within a run |
| `idempotency_key` | UUID (client-supplied) | client | deduplicates retried writes |
| `user_id` | UUID v4 (client-supplied via `X-User-Id`) | client, once per client install | groups the user's sessions and story runs; ownership key for reads/writes (not authentication) |

Lineage rules:

- A **story run** is created exactly once, at story selection; everything the initial
  flow and the dialogue loop produce belongs to that `story_run_id`.
- **Session lineage = story run**: artifact lookups for a session are always scoped to
  its own `story_run_id` — never a global "latest" (see [mcp-servers.md](mcp-servers.md)).
- **Artifact versioning**: artifacts are immutable; each `save_artifact` with a new
  idempotency key appends `version = max(existing) + 1` for its
  (`story_run_id`, `type`). The **latest per perspective** is the highest `version`
  with that type in the run; `list_artifacts` flags `is_latest`, and the caller derives
  "latest" deterministically as the maximum `version`.
- **Cross-run reads are not permitted** (decided): a new story run on the same story
  never reads prior-run artifacts; session restore continues the original run.
- A **new session on the same story** (after park/complete) creates a **new** story run;
  the old run and session remain immutable and restorable.
- **User scoping**: sessions and story runs belong to the user whose `X-User-Id`
  created them; listing, reads, and writes are scoped to that user, and the
  one-active-run-per-story rule applies per user. Artifacts need no separate rule —
  their lineage is the story run, which is already user-owned.

## Errors

`ErrorCode` is the stable taxonomy. API failures wrap `ErrorBody` in `ErrorEnvelope`;
MCP failures wrap the same body in `ToolError`. A retryable error always includes a
retry hint.

```python
ErrorCode = Literal[
    "UNAUTHENTICATED",
    "FORBIDDEN",
    "VALIDATION_ERROR",
    "STORY_NOT_FOUND",
    "SESSION_NOT_FOUND",
    "ARTIFACT_NOT_FOUND",
    "SESSION_LOCKED",
    "SESSION_READ_ONLY",
    "STORY_SESSION_ACTIVE",
    "NOT_FINALIZING",
    "REPORT_NOT_READY",
    "IDEMPOTENCY_KEY_REUSED",
    "DELEGATION_VALIDATION",
    "DEADLINE_EXCEEDED",
    "UPSTREAM_UNAVAILABLE",
    "RENDER_FAILED",
    "REPORT_RENDER_FAILED",
    "FINAL_REVIEW_INVALID",
]


class ErrorBody(StrictModel):
    code: ErrorCode
    message: Text
    agent: ShortText | None = None
    correlation_id: CorrelationId
    retryable: bool
    retry_after_seconds: Annotated[int, Field(ge=1, le=3600)] | None = None

    @model_validator(mode="after")
    def retry_hint_matches_retryability(self):
        if self.retryable != (self.retry_after_seconds is not None):
            raise ValueError("retryable errors require one retry hint")
        return self


class ErrorEnvelope(StrictModel):
    error: ErrorBody


class ToolError(StrictModel):
    error: ErrorBody
```

| Code | HTTP | Retry behavior |
|---|---:|---|
| `UNAUTHENTICATED` | 401 | Service/caller identity missing or invalid. |
| `FORBIDDEN` | 403 | Caller lacks endpoint/tool permission. |
| `VALIDATION_ERROR`, `DELEGATION_VALIDATION` | 422 | Correct the input or produce a new PO turn. |
| `*_NOT_FOUND` | 404 | Resource does not exist. |
| `SESSION_LOCKED` | 409 | Wait for the hint, then submit a new request/key. |
| Other state/idempotency conflicts | 409 | Do not retry unchanged input. |
| `DEADLINE_EXCEEDED`, `UPSTREAM_UNAVAILABLE`, `REPORT_RENDER_FAILED` | 503 | Replay the same operation/key after the hint. |
| `RENDER_FAILED` | MCP only | Orchestration applies the report retry policy. |
| `FINAL_REVIEW_INVALID` | 503 | Non-retryable (D18): the finalized review is self-contradictory (a resolved/accepted issue remains open without a later `reopened`) — re-engage the dialogue (re-open or resolve the conflicting issue), then accept again. |

## Story, review, synthesis, and delegation models

```python
class StorySummary(StrictModel):
    story_id: StoryId
    title: ShortText
    status: ShortText


class StoryComment(StrictModel):
    author: ShortText  # anonymized persona (e.g. "Story Author", "PO")
    text: Text
    created_at: UtcDatetime


class ContextStory(StrictModel):
    story_id: StoryId
    title: ShortText
    relation: Literal["related", "depends"]
    description: Text
    acceptance_criteria: list[Text] = Field(default_factory=list, max_length=100)
    comments: list[StoryComment] = Field(default_factory=list, max_length=50)


class StoryDetail(StorySummary):
    description: Text
    acceptance_criteria: list[Text] = Field(default_factory=list, max_length=100)
    epic_context: Text
    roadmap_context: Text
    comments: list[StoryComment] = Field(default_factory=list, max_length=50)
    context_stories: list[ContextStory] = Field(default_factory=list, max_length=5)


class Finding(StrictModel):
    id: Annotated[
        str,
        StringConstraints(pattern=r"^[BE]-[1-9][0-9]*$", max_length=32),
    ]
    title: ShortText
    description: Text
    severity: Literal["info", "minor", "major", "blocker"]
    category: Annotated[
        str,
        StringConstraints(
            pattern=r"^[a-z][a-z0-9-]*$", min_length=1, max_length=64
        ),
    ]
    suggestion: Text | None = None
    references_po_question: bool = False


class ReviewReport(StrictModel):
    perspective: Perspective
    story_id: StoryId
    summary: Text
    findings: list[Finding] = Field(default_factory=list, max_length=200)
    risks: list[Text] = Field(default_factory=list, max_length=100)
    questions_for_po: list[Text] = Field(default_factory=list, max_length=100)
    based_on_extra_context: Text | None = None
    previous_review_version: Annotated[int, Field(ge=1)] | None = None

    @model_validator(mode="after")
    def finding_prefix_matches_perspective(self):
        prefix = "B-" if self.perspective == "business" else "E-"
        if any(not finding.id.startswith(prefix) for finding in self.findings):
            raise ValueError("finding ID prefix does not match review perspective")
        return self
```

`StorySummary` and `StoryDetail` contain only story content and stable identity
available to a runtime caller. Dataset-only scenario and expected-result metadata is
never part of these public contracts.

Story-detail extensions (additive, both default empty — stories without them
are unaffected):

- `comments` — backlog discussion attached to the story; **semantic review
  input**, not display decoration: comment content can resolve or create
  findings. Authors are anonymized personas (dataset concern). No truncation
  or summarization in v1 — the list cap (`50`) is the only limit.
- `context_stories` — linked related/depends items surfaced as a separate
  structured list (never merged into the main story or `epic_context`).
  Capped at 5. Context stories are reference material for the review of the
  **main** story; they are never reviewed themselves. They carry their own
  description-level content (and comments when present) so reviewers can
  extract context that was not copied into the main story.

```python

class ConflictItem(StrictModel):
    id: Annotated[
        str,
        StringConstraints(pattern=r"^C-[1-9][0-9]*$", max_length=32),
    ]
    description: Text
    business_refs: list[ShortText] = Field(min_length=1, max_length=100)
    engineering_refs: list[ShortText] = Field(min_length=1, max_length=100)
    needs_po_clarification: bool


class ArtifactReference(StrictModel):
    """Safe immutable reference returned to clients and agents."""

    artifact_id: ArtifactId
    story_run_id: RunId
    type: ArtifactType
    perspective: Perspective | None = None
    version: Annotated[int, Field(ge=1)]
    created_at: UtcDatetime
    content_type: Literal[
        "application/json",
        "text/markdown",
        "application/pdf",
    ]
    checksum_sha256: Sha256
    is_latest: bool = False  # server-flagged in list results; informational

    @model_validator(mode="after")
    def perspective_matches_type(self):
        expected = {
            "review-business": "business",
            "review-engineering": "engineering",
        }.get(self.type)
        if self.perspective != expected:
            raise ValueError("perspective must exactly match the artifact type")
        expected_content_type = {
            "story": "application/json",
            "review-business": "application/json",
            "review-engineering": "application/json",
            "synthesis": "application/json",
            "finalized-review": "application/json",
            "report-md": "text/markdown",
            "report-pdf": "application/pdf",
        }[self.type]
        if self.content_type != expected_content_type:
            raise ValueError("content_type does not match artifact type")
        return self


class ArtifactRecord(ArtifactReference):
    """Internal storage record; never returned through HTTP or to an agent."""

    gcs_uri: Annotated[
        str,
        StringConstraints(pattern=r"^gs://", min_length=6, max_length=2048),
    ]


class SynthesisReport(StrictModel):
    story_id: StoryId
    summary: Text
    merged_findings: list[Finding] = Field(default_factory=list, max_length=400)
    conflicts: list[ConflictItem] = Field(default_factory=list, max_length=200)
    questions_for_po: list[Text] = Field(default_factory=list, max_length=100)
    resolved_from_previous: list[ShortText] = Field(
        default_factory=list,
        max_length=400,
    )
    inputs: dict[Perspective, ArtifactReference] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_paired_inputs(self):
        if set(self.inputs) != {"business", "engineering"}:
            raise ValueError("both perspective keys are required")
        expected_types = {
            "business": "review-business",
            "engineering": "review-engineering",
        }
        for perspective, reference in self.inputs.items():
            if reference.type != expected_types[perspective]:
                raise ValueError("input reference type does not match its perspective")
            if reference.perspective != perspective:
                raise ValueError("input reference perspective does not match its key")
        if len({reference.story_run_id for reference in self.inputs.values()}) != 1:
            raise ValueError("synthesis inputs must belong to one story run")
        return self


class DelegationDecision(StrictModel):
    invoke: Literal["none", "business", "engineering", "both"] = "none"
    extra_context: Text | None = None
    reuse_previous: bool = False
    open_issues: list[Text] = Field(default_factory=list, max_length=100)
    readiness: Literal["needs_work", "review_requested", "ready"] = "needs_work"

    @model_validator(mode="after")
    def validate_combination(self):
        if self.reuse_previous and self.invoke != "none":
            raise ValueError("reuse_previous requires invoke=none")
        if self.invoke == "none" and self.extra_context is not None:
            raise ValueError("extra_context requires a reviewer invocation")
        return self


class ResolutionItem(StrictModel):
    issue: Text
    # `reopened`: a previously resolved/accepted issue regressed — emitted
    # when the concern reappears in `open_issues`; latest disposition wins
    # in aggregation, so a re-open overrides the earlier resolution
    disposition: Literal["resolved", "accepted", "unresolved", "reopened"]
    explanation: Text
    turn_number: Annotated[int, Field(ge=1)]


class ResolutionDraft(StrictModel):
    """Facilitator-emitted resolution update; orchestration stamps `turn_number`
    when converting it into a `ResolutionItem`."""

    issue: Text
    disposition: Literal["resolved", "accepted", "unresolved", "reopened"]
    explanation: Text


class IssueDraft(StrictModel):
    """Facilitator-minted issue descriptor (D19): required whenever the
    facilitator adds an issue id to `open_issues` that does not appear in
    the latest synthesis findings/conflicts — synthesis-born ids already
    carry title/description there; minted ids have no other home."""

    issue: Text
    title: Text
    description: Text


class FacilitatorTurnOutput(StrictModel):
    """Authoritative typed output of one facilitator turn. Orchestration never
    parses the reply prose; every programmatically consumed field lives here.

    On a delegated turn the facilitator produces two of these (Item G / D21):
    the pre-delegation output (its `reply` is the delegation rationale and is
    not shown to the PO) and, after the re-review and re-synthesis complete,
    the post-delegation summary output — the turn's final and gate-authoritative
    one. The second call cannot request a new delegation for the same turn;
    any delegation it emits executes on the next PO turn."""

    reply: Text
    delegation: DelegationDecision
    resolutions: list[ResolutionDraft] = Field(default_factory=list, max_length=100)
    new_issues: list[IssueDraft] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def resolutions_are_final(self):
        # dispositions are only meaningful once the PO has answered the opening
        # turn; turn 1 must emit none
        if self.delegation.invoke == "none" and self.delegation.reuse_previous:
            if self.resolutions:
                raise ValueError("re-synthesis-only turns carry no resolution updates")
        return self

    @model_validator(mode="after")
    def new_issues_are_open(self):
        # a descriptor exists only for ids actually on this turn's open
        # list; one descriptor per id
        described = [draft.issue for draft in self.new_issues]
        if len(set(described)) != len(described):
            raise ValueError("new_issues must be unique per issue id")
        for issue in described:
            if issue not in set(self.delegation.open_issues):
                raise ValueError(
                    f"new_issues describes an id not on this turn's open list: {issue}"
                )
        return self


class IssueEntry(StrictModel):
    """One entry of the finalized review's issue catalog (D19): the
    descriptive record behind every issue id the report references."""

    issue: Text
    title: Text
    description: Text
    severity: Literal["info", "minor", "major", "blocker"] | None = None
    source: Literal["synthesis", "facilitator"]


class FinalizedReview(StrictModel):
    story_id: StoryId
    story_run_id: RunId
    synthesis_reference: ArtifactReference
    issues: list[IssueEntry] = Field(default_factory=list, max_length=400)
    resolutions: list[ResolutionItem] = Field(default_factory=list, max_length=200)
    remaining_open_issues: list[Text] = Field(default_factory=list, max_length=100)
    po_accepted: bool
    final_turn_number: Annotated[int, Field(ge=1)]
    finalized_at: UtcDatetime

    @model_validator(mode="after")
    def validate_final_state(self):
        if (
            self.synthesis_reference.type != "synthesis"
            or self.synthesis_reference.story_run_id != self.story_run_id
        ):
            raise ValueError("final review requires this run's synthesis reference")
        if self.remaining_open_issues and not self.po_accepted:
            raise ValueError("normal readiness cannot retain open issues")
        # deterministic backstop for issue-identifier lifecycle: a resolved or
        # accepted issue may only remain open if a later `reopened` disposition
        # overrode it (latest-wins aggregation); otherwise the review is
        # self-contradictory and must not be finalized
        latest = {item.issue: item for item in self.resolutions}
        for issue in self.remaining_open_issues:
            if latest.get(issue) is not None and latest[issue].disposition in (
                "resolved",
                "accepted",
            ):
                raise ValueError(
                    "remaining open issue has a resolved/accepted latest "
                    f"disposition: {issue}"
                )
        # D19 completeness: every id the report references (resolutions,
        # remaining open) must have a catalog entry — no bare unexplained
        # identifiers can reach a rendered report
        catalog = {entry.issue for entry in self.issues}
        referenced = set(latest) | set(self.remaining_open_issues)
        missing = referenced - catalog
        if missing:
            raise ValueError(
                f"issues referenced without a catalog entry: {sorted(missing)}"
            )
        return self


class ConversationSummary(StrictModel):
    story_id: StoryId
    story_run_id: RunId
    summary: Text
    unresolved_issues: list[Text] = Field(default_factory=list, max_length=100)
    decisions: list[Text] = Field(default_factory=list, max_length=100)
    artifact_references: list[ArtifactReference] = Field(
        default_factory=list,
        max_length=100,
    )


class JudgeIssue(StrictModel):
    severity: Literal["minor", "major", "blocker"]
    message: Text


class JudgeDimensionScore(StrictModel):
    dimension: Literal[
        "review-coverage",
        "grounding",
        "conflict-resolution",
        "delegation",
        "final-state",
    ]
    score: Annotated[int, Field(ge=0, le=4)]
    rationale: Text


class JudgeResult(StrictModel):
    case_id: ShortText
    judge_model: ShortText
    prompt_sha256: Sha256
    scores: list[JudgeDimensionScore] = Field(min_length=5, max_length=5)
    issues: list[JudgeIssue] = Field(default_factory=list, max_length=100)
    comment: Text
    passed: bool

    @model_validator(mode="after")
    def validate_pass_rule(self):
        dimensions = {item.dimension for item in self.scores}
        if len(dimensions) != 5:
            raise ValueError("every judge dimension must appear exactly once")
        score_values = [item.score for item in self.scores]
        expected_pass = (
            min(score_values) >= 3
            and sum(score_values) / len(score_values) >= 3.5
            and not any(issue.severity == "blocker" for issue in self.issues)
        )
        if self.passed != expected_pass:
            raise ValueError("passed does not match the fixed judge threshold")
        return self
```

The opening facilitator turn must produce `invoke="none"`; orchestration asserts this
in addition to model validation. `readiness` is advisory and is deliberately ignored by
the finalization gate, which uses `open_issues`, `invoke`, whether synthesis was
produced this turn, explicit PO acceptance, and the turn cap.

**Issue-identifier lifecycle.** Issue identifiers are immutable for one session: a
regressed concern (a previously resolved/accepted issue reappearing in
`open_issues`) must be re-opened with a `reopened` disposition on the same turn —
never by silently re-using the resolved id as if it were still open, and never by
issuing a new id for the same concern. The facilitator adapter enforces this as a
turn-context rule (corrective re-prompt on violation), and `FinalizedReview` rejects a
self-contradictory final state as the deterministic backstop.

**Issue catalog (D19).** Every issue id a report references must carry a
descriptive record. Ids born in the synthesis (findings `B-*`/`E-*`, conflicts
`C-*`) take title/description/severity from the synthesis — **union across
all synthesis versions the session produced, latest version winning** on
collision: a later synthesis legitimately drops findings both reviewers
stopped reporting, but a resolved issue still referenced by the report must
keep its descriptor; ids the facilitator mints itself must be described at
birth via `new_issues`
(`IssueDraft`, emitted on the same turn the id first appears in `open_issues` —
the adapter enforces this as a turn-context rule, since it holds the synthesis
report in the request and can distinguish synthesis-born from minted ids).
Orchestration accumulates the drafts into the turn records and assembles
`FinalizedReview.issues` at finalize; its validator rejects any referenced id
without a catalog entry. Rendering presents the catalog as the report's
Issues section and annotates resolution/open-issue rows with issue titles.

## HTTP API models

Correlation and idempotency headers are validated as FastAPI header parameters, not
body fields: `X-Correlation-Id` is UUID v4 when supplied, and every mutating POST
requires a UUID-v4 `Idempotency-Key`.

```python
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


class AbandonSessionResponse(StrictModel):
    """`POST /sessions/{id}/abandon` — explicit park-now of an active/finalizing
    session (client-side escape for a session stuck without an exit; see
    api-contract.md). The transition also parks the story run, releasing the
    story for a new session."""

    session_id: SessionId
    state: Literal["parked"]


ProcessingStage = Literal["reviewing", "synthesizing", "facilitator", "delegating", "finalizing"]

`SessionSummary.processing_stage` (and therefore `SessionDetail.processing_stage`)
exposes live pipeline progress for a session whose flow-1/flow-2/flow-3 request is
currently executing server-side: `reviewing` (flow-1 reviewer fan-out),
`synthesizing`, `facilitator` (a facilitator turn — twice on a delegated turn: before
and after the delegated re-review/synthesis), `delegating` (delegated re-review),
`finalizing` (report rendering). It is `null` whenever no request for the session is
in flight. It is advisory only — clients poll `GET /sessions` / `GET /sessions/{id}`
for it while their synchronous POST is outstanding; no correctness decision may be
based on it.


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
```

Before constructing `TurnResponse` or `ReportResponse`, orchestration validates that the
unique returned report-format set exactly equals the persisted
`SessionRecord.requested_formats`; `SessionRecord` enforces the same invariant when it
enters `completed`.

The opening facilitator call is facilitator turn 1 and counts toward the cap of 10.
Explicit PO acceptance does not invoke the facilitator and therefore does not increment
`facilitator_turn_count`; its persisted API turn number remains the next chronological
turn number. A delegated turn still counts as **one** facilitator turn despite its two
invocations (Item G / D21): the second (post-delegation summary) call is part of the
same PO turn — `facilitator_turn_count` increments once per turn, not per invocation.
Each invocation carries its own invocation id and its own bounded corrective re-prompt
budget; reconciliation on an ambiguous timeout is per invocation id.

## Durable Cloud SQL records

These records sit beside ADK `DatabaseSessionService` tables. Public response models do
not inherit from them, preventing owner IDs, operation IDs, lease tokens, and canonical
response JSON from leaking through the API.

The `sessions` table additionally carries an ephemeral `processing_stage` column
(the advisory stage marker of `SessionSummary`/`SessionDetail`): written and cleared
by the running flow, `null` for every session at rest, and deliberately **not** part
of `SessionRecord` — it is live view state, not durable truth.

```python
class StoryRunRecord(StrictModel):
    story_run_id: RunId
    story_id: StoryId
    user_id: UserId
    state: SessionState
    created_at: UtcDatetime
    updated_at: UtcDatetime


class SessionRecord(StrictModel):
    session_id: SessionId
    story_run_id: RunId
    story_id: StoryId
    user_id: UserId
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
    session_id: SessionId
    lease_token: LeaseToken
    acquired_at: UtcDatetime
    expires_at: UtcDatetime


class TurnRecord(StrictModel):
    session_id: SessionId
    turn_number: Annotated[int, Field(ge=1)]
    correlation_id: CorrelationId
    state: RecordState
    po_message: Text | None = None
    po_accepted: bool = False
    facilitator_reply: Text | None = None
    delegation_rationale_reply: Text | None = None
    delegation: DelegationDecision | None = None
    resolutions: list[ResolutionItem] = Field(default_factory=list, max_length=100)
    new_issues: list[IssueDraft] = Field(default_factory=list, max_length=100)
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


```

Database constraints:

- one run and one session per `story_run_id`;
- at most one non-`completed`/non-`parked` run per (`user_id`, `story_id`);
- idempotency keys unique per route (`IDEMPOTENCY_KEY_REUSED` on body mismatch);
- turn unique on `(session_id, turn_number)`;
- one lease row per `session_id`, and only its `lease_token` holder may renew/release it;
- artifact save unique on `(story_run_id, type, idempotency_key)`; and
- one `finalized-review` artifact per story run, plus one report per
  `(story_run_id, format)`.

Every mutating request stores its idempotency key, request fingerprint, and canonical
logical response (never a signed URL). A replay with the same key and body returns the
stored response and regenerates any signed URLs; a different body yields
`IDEMPOTENCY_KEY_REUSED`. Turn writes are serialized by the session turn lease; a
timed-out agent call may have completed remotely, so retries rely on idempotent
artifact saves — a repeated invocation can duplicate model cost but never duplicate
durable artifacts, dialogue events, or reports.

## MCP tool models and authorization

Every MCP call returns its success model directly or `ToolError`. Service identity is
validated at ingress. Artifact operations are lineage-scoped: references are supplied by
orchestration for the caller's own story run, the server validates the
reference-to-run relationship, and reads never cross story runs.

The story server tools carry an optional `source` (`azure` | `mock`, default
`None`). `None` means "use the deployment default" (`STORY_SOURCE` env); an
explicit value is set by orchestration only — the field is transparent to
agents, whose schemas never mention it. A call never mixes sources; a story
run is pinned to one source by the deployment it executes in (evaluation and
regression runs always use `mock`; `azure` is the production/demo path).

```python
class ListStoriesInput(StrictModel):
    filter: ShortText | None = None
    source: StorySource | None = None


class ListStoriesOutput(StrictModel):
    stories: list[StorySummary] = Field(default_factory=list, max_length=50)


class GetStoryInput(StrictModel):
    story_id: StoryId
    source: StorySource | None = None


class SaveArtifactInput(StrictModel):
    type: SaveArtifactType
    story_run_id: RunId
    perspective: Perspective | None = None
    content: StoryDetail | ReviewReport | SynthesisReport | FinalizedReview
    idempotency_key: IdempotencyKey

    @model_validator(mode="after")
    def type_matches_content(self):
        expected_model = {
            "story": StoryDetail,
            "review-business": ReviewReport,
            "review-engineering": ReviewReport,
            "synthesis": SynthesisReport,
            "finalized-review": FinalizedReview,
        }[self.type]
        if type(self.content) is not expected_model:
            raise ValueError("artifact type does not match content model")
        expected_perspective = {
            "review-business": "business",
            "review-engineering": "engineering",
        }.get(self.type)
        if self.perspective != expected_perspective:
            raise ValueError("perspective does not match artifact type")
        if (
            isinstance(self.content, ReviewReport)
            and self.content.perspective != expected_perspective
        ):
            raise ValueError("review content perspective does not match artifact type")
        if (
            isinstance(self.content, FinalizedReview)
            and self.content.story_run_id != self.story_run_id
        ):
            raise ValueError("final review content belongs to another story run")
        return self


class SaveArtifactOutput(StrictModel):
    reference: ArtifactReference
    created: bool


class GetArtifactInput(StrictModel):
    artifact_id: ArtifactId
    story_run_id: RunId


class GetArtifactOutput(StrictModel):
    reference: ArtifactReference
    content: StoryDetail | ReviewReport | SynthesisReport | FinalizedReview

    @model_validator(mode="after")
    def content_matches_reference(self):
        expected_model = {
            "story": StoryDetail,
            "review-business": ReviewReport,
            "review-engineering": ReviewReport,
            "synthesis": SynthesisReport,
            "finalized-review": FinalizedReview,
        }.get(self.reference.type)
        if expected_model is None or type(self.content) is not expected_model:
            raise ValueError("reference type does not match content model")
        return self


class ListArtifactsInput(StrictModel):
    story_run_id: RunId
    type: SaveArtifactType | None = None
    perspective: Perspective | None = None
    limit: Annotated[int, Field(ge=1, le=500)] = 100
    offset: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="after")
    def filters_are_compatible(self):
        expected = {
            "review-business": "business",
            "review-engineering": "engineering",
        }.get(self.type)
        if self.type in {"story", "synthesis", "finalized-review"} and self.perspective is not None:
            raise ValueError("perspective cannot filter a non-review artifact type")
        if expected is not None and self.perspective not in {None, expected}:
            raise ValueError("perspective conflicts with review artifact type")
        return self


class ListArtifactsOutput(StrictModel):
    items: list[ArtifactReference] = Field(default_factory=list, max_length=500)
    total: Annotated[int, Field(ge=0)]


class RenderReportInput(StrictModel):
    story_run_id: RunId
    final_review_reference: ArtifactReference
    format: Format

    @model_validator(mode="after")
    def validate_final_review_reference(self):
        if (
            self.final_review_reference.story_run_id != self.story_run_id
            or self.final_review_reference.type != "finalized-review"
        ):
            raise ValueError("input must be this run's finalized-review artifact")
        return self


class RenderReportOutput(StrictModel):
    reference: ArtifactReference
    format: Format
    created: bool

    @model_validator(mode="after")
    def format_matches_reference(self):
        if self.reference.type != f"report-{self.format}":
            raise ValueError("report format does not match artifact reference")
        return self
```

Tool authorization is fixed per tool:

| Tool | Authorized identities and scope |
|---|---|
| `list_stories`, `get_story` | Orchestration and facilitator service accounts. Expected-result data is never returned. |
| `save_artifact` | Orchestration service account only; the save tool is never exposed to the facilitator. |
| `get_artifact`, `list_artifacts` | Orchestration and facilitator (read-only) service accounts. |
| `render_report` | Orchestration service account only; the finalized-review reference must belong to the supplied run. |

`list_artifacts` orders deterministically by `(type, perspective, version)` and pages
with `limit`/`offset` (`total` supports client paging). The server flags `is_latest` on
the highest-version item per `(type, perspective)`; the caller derives “latest” as the
maximum `version`. There is no cross-run lookup.
