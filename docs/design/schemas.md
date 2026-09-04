# Shared Schema Specification

Single source of truth for all structured payloads: the exact Pydantic models shared by
agents, orchestration, MCP servers, and tests (single shared package — see
`../operations/repository-layout.md`). Rendered as field-level contracts here; the
Python package is authoritative for validation. Any change to these models is a
contract change and bumps the shared package version.

Contents:

1. Common identifiers and lineage model
2. Artifact models
3. Delegation decision
4. Review and synthesis schemas
5. Session and audit records
6. Error taxonomy
7. MCP tool field-level contracts

## 1. Identifiers and lineage model

### Identifier types

| ID | Format | Created by | Scope / meaning |
|---|---|---|---|
| `correlation_id` | UUID v4 | FastAPI, at first client call of a request | one HTTP request end-to-end (propagated to agents and MCP calls) |
| `story_id` | `story-NN` (dataset) | dataset | backlog identity, stable across sessions |
| `story_run_id` | `run-{uuid}` | FastAPI, once at story selection (`POST /sessions`) | one full review lifecycle of a story; scopes all artifacts of that run |
| `session_id` | ADK session ID | FastAPI, at facilitator-session creation | facilitator ↔ PO conversation; exactly one per story run |
| `agent_run_id` | `arun-{uuid}` | FastAPI, before each agent invocation | one invocation of one agent deployment (audit unit) |
| `artifact_id` | `art-{uuid}` | artifact MCP server, at `save_artifact` | immutable artifact identity |
| `version` | integer ≥ 1 | artifact MCP server, monotonically per (`story_run_id`, `type`) | ordering within a run |
| `idempotency_key` | UUID (client-supplied) | client | deduplicates retried writes |

### Lineage rules

- A **story run** is created exactly once, at story selection. Everything the initial
  flow and the dialogue loop produce (story snapshot, reviews, synthesis, reports)
  belongs to that `story_run_id`.
- **Session lineage = story run**: the facilitator session is created inside the story
  run and references it. Artifact lookups performed for that session are always scoped
  to its `story_run_id` — never a global "latest" (see `mcp-servers.md`).
- **Artifact versioning**: artifacts are immutable; each `save_artifact` with a new
  idempotency key appends `version = max(existing) + 1` for its
  (`story_run_id`, `type`) pair. The **latest artifact per perspective** is therefore
  exactly: the highest `version` with that `type` (`review-business` /
  `review-engineering`) in the run. Ordering is deterministic and derived by callers
  from returned references; the server additionally flags `is_latest` per type in
  `list_artifacts` results.
- **Cross-run reads**: whether a new story run on the same story may read prior-run
  artifacts is an open decision tracked in the documentation audit (B4); until decided,
  the artifact server enforces strict same-run scoping.
- A **new session on the same story** (after park/complete) creates a **new** story run;
  the old run and session remain immutable and restorable.

## 2. Artifact models

```python
Perspective = Literal["business", "engineering"]
ArtifactType = Literal[
    "story",                  # story snapshot persisted at selection
    "review-business",        # business reviewer output
    "review-engineering",     # engineering reviewer output
    "synthesis",              # synthesis & conflict resolver output
    "report-md", "report-pdf" # rendered final reports
]

class ArtifactReference(BaseModel):
    artifact_id: str            # immutable, server-assigned
    story_run_id: str
    type: ArtifactType
    perspective: Perspective | None = None   # reviews only
    version: int
    created_at: datetime        # UTC, server-assigned
    content_type: str           # "application/json" | "text/markdown" | "application/pdf"
    checksum_sha256: str        # of stored bytes
    gcs_uri: str                # internal; never exposed as download (signed URLs only)
    is_latest: bool             # server-flagged in list results; informational
```

Artifact content payloads are the review/synthesis schemas below (JSON), or rendered
MD/PDF bytes for reports.

## 3. Delegation decision (facilitator structured output)

Emitted at the end of every facilitator turn; the LLM proposes, orchestration disposes.

```python
InvokeSelection = Literal["none", "business", "engineering", "both"]
Readiness = Literal["needs_work", "review_requested", "ready"]

class DelegationDecision(BaseModel):
    invoke: InvokeSelection = "none"
    extra_context: str | None = None       # PO clarifications injected into invoked reviewers
    reuse_previous: bool = False           # True ⇒ re-synthesis only; invoke must be "none"
    open_issues: list[str] = []            # currently unresolved issue descriptions
    readiness: Readiness = "needs_work"    # proposal only — the finalize gate ignores it
```

Validation constraints (enforced at parse time; violations trigger bounded corrective
re-prompt, see `observability.md`):

- `reuse_previous = true` requires `invoke = "none"` and `extra_context is None`.
- The opening turn always emits `invoke = "none"` (orchestration-asserted).
- `readiness` is advisory: the finalize gate uses only `open_issues`, `invoke`, and
  whether synthesis was produced this turn (gate precedence in `data-flow.md` flow 2).

## 4. Review and synthesis schemas

Shared between the two reviewers (same contract, different perspective), synthesis, the
prompts, and the evaluation judge.

```python
Severity = Literal["info", "minor", "major", "blocker"]

class Finding(BaseModel):
    id: str                              # stable within one review, e.g. "B-3" / "E-3"
    title: str
    description: str
    severity: Severity
    category: str                        # free-but-bounded: e.g. "clarity", "edge-case", "value"
    suggestion: str | None = None
    references_po_question: bool = False # needs PO clarification

class ReviewReport(BaseModel):
    perspective: Perspective
    story_id: str
    summary: str
    findings: list[Finding] = []
    risks: list[str] = []
    questions_for_po: list[str] = []
    based_on_extra_context: str | None = None   # echoed PO input, if any
    previous_review_version: int | None = None  # version of prior artifact of this perspective

class ConflictItem(BaseModel):
    id: str
    description: str                     # the contradiction, stated neutrally
    business_refs: list[str]             # Finding.id values from the business review
    engineering_refs: list[str]          # Finding.id values from the engineering review
    needs_po_clarification: bool

class SynthesisReport(BaseModel):
    story_id: str
    summary: str
    merged_findings: list[Finding] = []  # unified, de-duplicated view
    conflicts: list[ConflictItem] = []
    questions_for_po: list[str] = []
    resolved_from_previous: list[str] = []   # Finding.ids / ConflictItem.ids now resolved
    inputs: dict[str, ArtifactReference]     # {"business": ref, "engineering": ref}
```

Reviewer/synthesis agents return only these models (plus the shared envelope); they
never write artifacts themselves — orchestration persists outputs via direct MCP calls.

## 5. Session and audit records (Cloud SQL)

Lay alongside ADK's own session tables (`DatabaseSessionService`); owned by FastAPI.

```python
SessionState = Literal["active", "parked", "finalizing", "completed"]
TurnOutcome = Literal["continue", "park", "finalize"]

class SessionRecord(BaseModel):
    session_id: str
    story_run_id: str
    story_id: str
    state: SessionState
    facilitator_turn_count: int = 0       # park gate at 10
    created_at: datetime
    updated_at: datetime
    report_references: list[ArtifactReference] = []   # set at completion

class TurnRecord(BaseModel):
    session_id: str
    turn_number: int
    correlation_id: str
    po_message: str | None
    po_accepted: bool = False
    facilitator_reply: str | None
    delegation: DelegationDecision | None
    outcome: TurnOutcome
    produced_artifacts: list[ArtifactReference] = []

class AgentRunRecord(BaseModel):          # audit unit — one per agent invocation
    agent_run_id: str
    agent: Literal["facilitator", "business-reviewer", "engineering-reviewer", "synthesis"]
    agent_version: str                    # deployed version label (git tag/SHA)
    story_run_id: str
    session_id: str | None                # None for initial-flow reviewer runs
    correlation_id: str
    input_references: list[ArtifactReference] = []
    output_references: list[ArtifactReference] = []
    status: Literal["ok", "error", "validation-error"] = "ok"
    attempts: int = 1                     # transport attempts incl. corrective re-prompts
    started_at: datetime
    finished_at: datetime | None
```

Invariants: session state transitions only `active → finalizing → completed` and
`active → parked` (parked/finalizing reachable only once); `completed` is set only
after the report reference is persisted; turn writes are serialized by the session
turn lease (see `data-flow.md` flow 2).

## 6. Error taxonomy

One structured model for PO-facing API errors, logs, and metrics (per `observability.md`):

```python
class ErrorBody(BaseModel):
    code: str                # stable machine code, e.g. "SESSION_LOCKED"
    message: str             # human-readable
    agent: str | None        # originating component/agent, if applicable
    correlation_id: str
    retryable: bool
```

| Code | HTTP | Retryable | Meaning |
|---|---|---|---|
| `STORY_NOT_FOUND` / `SESSION_NOT_FOUND` | 404 | no | unknown story/session |
| `SESSION_LOCKED` | 409 | after lease expiry | turn lease held by another request |
| `SESSION_READ_ONLY` | 409 | no | parked/completed session |
| `STORY_SESSION_ACTIVE` | 409 | no | active session exists for the story |
| `NOT_FINALIZING` | 409 | no | finalize on a non-finalizing state |
| `DELEGATION_VALIDATION` | 422 | no (new input, not same retry) | structured output invalid after re-prompt bound |
| `DEADLINE_EXCEEDED` | 503 | yes (same idempotency key) | 5-min request budget exhausted |
| `UPSTREAM_UNAVAILABLE` | 503 | yes | retry-exhausted agent/MCP failure |
| `REPORT_RENDER_FAILED` | 503 | yes (finalize retry; session stays `finalizing`) | report generation failed |

MCP tool errors reuse `ErrorBody` (without HTTP status) as the tool error result.

## 7. MCP tool contracts (field level)

Consumers: facilitator (story + artifact servers, read path), FastAPI (all three, direct
client). All inputs/outputs are Pydantic-validated JSON. Servers are stateless;
timeouts/retries are client-side (`observability.md`).

### Story server (read-only)

- `list_stories(filter: str | None = None) -> {stories: list[StorySummary]}`
  - `StorySummary {story_id: str, title: str, status: str, quality_class: str}`
  - `filter` — case-insensitive substring on title; optional.
  - Result size is bounded by the dataset (≤ 50); **no pagination** required.
  - Errors: `ErrorBody` (`UPSTREAM_UNAVAILABLE` only — dataset is local/immutable).
- `get_story(story_id: str) -> StoryDetail`
  - `StoryDetail {story_id, title, description, acceptance_criteria: list[str],
    epic_context: str, roadmap_context: str}`
  - Errors: `STORY_NOT_FOUND` (not retryable).
  - Authorization: any authenticated service principal (orchestration, facilitator).
    Expected outcomes from the dataset are **never** returned.

### Artifact server

- `save_artifact(type: ArtifactType, story_run_id: str, perspective: Perspective | None,
  content: ReviewReport | SynthesisReport | StoryDetail (JSON per type),
  idempotency_key: str) -> ArtifactReference`
  - Idempotent per (`story_run_id`, `type`, `idempotency_key`): a retry returns the
    existing reference with `created: false` semantics (same body).
  - `perspective` required iff `type` starts with `review-`.
  - Version assigned server-side (see §1). Authorization: **orchestration only**
    (service-account); the facilitator's toolset exposes no save tool.
- `get_artifact(artifact_id: str) -> {reference: ArtifactReference, content: JSON}`
  - Lineage-scoped by construction: the facilitator only receives IDs supplied by
    orchestration for its own story run. Errors: `ARTIFACT_NOT_FOUND` (not retryable).
- `list_artifacts(story_run_id: str, type: ArtifactType | None = None,
  perspective: Perspective | None = None, limit: int = 100, offset: int = 0)
  -> {items: list[ArtifactReference], total: int}`
  - Same-`story_run_id` scope only (cross-run reads undecided — §1). Ordered by
    `(type, perspective, version)` ascending. **Pagination** via `limit` (max 500) /
    `offset`; `total` supports client paging.
  - `is_latest` is flagged on the highest-version item per `(type, perspective)` in the
    returned set; callers derive "latest" deterministically as max `version`.
  - Errors: validation error on bad `type`/`perspective` (not retryable).

### Report server

- `render_report(story_run_id: str, synthesis_references: list[ArtifactReference],
  format: Literal["md", "pdf"]) -> ArtifactReference`
  - Requires ≥ 1 `synthesis` reference from the same `story_run_id`; content is derived
    from synthesis artifacts only (no LLM).
  - Idempotent per (`story_run_id`, `format`): a retry returns the existing reference.
  - Errors: `ARTIFACT_NOT_FOUND` (bad reference), validation error (empty/mixed-run
    inputs), `RENDER_FAILED` (retryable). Authorization: **orchestration only**.
    Never issues signed URLs — that is FastAPI's job.
