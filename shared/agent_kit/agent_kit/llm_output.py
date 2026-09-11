"""Serving-safe LLM-facing output mirrors (D13 amendment 1).

Vertex AI structured output rejects the strict shared models (regex
patterns on strings, array `max_length`s, bounded integers, date-time
formats — "too many states for serving", Runbook 11 §1). These mirrors keep
the exact field names with plain serving-safe types so ADK's native
`output_schema` enforcement can run against Vertex; the shared strict
models remain the sole validation authority — every model payload is
validated through them unchanged at the adapter boundary, and failures take
the normal structured-error path.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MirrorFinding(BaseModel):
    """Serving-safe mirror of `review_schemas.Finding` (same field names)."""

    id: str
    title: str
    description: str
    severity: str
    category: str
    suggestion: str | None = None
    references_po_question: bool = False


class ServingSafeReviewReport(BaseModel):
    """Serving-safe mirror of `review_schemas.ReviewReport`."""

    perspective: str
    story_id: str
    summary: str
    findings: list[MirrorFinding]
    risks: list[str]
    questions_for_po: list[str]
    based_on_extra_context: str | None = None
    previous_review_version: int | None = None


class MirrorArtifactReference(BaseModel):
    """Serving-safe mirror of `review_schemas.ArtifactReference`."""

    artifact_id: str
    story_run_id: str
    type: str
    perspective: str | None = None
    version: int
    created_at: str
    content_type: str
    checksum_sha256: str
    is_latest: bool = False


class MirrorConflictItem(BaseModel):
    """Serving-safe mirror of `review_schemas.ConflictItem`."""

    id: str
    description: str
    business_refs: list[str] = Field(min_length=1)
    engineering_refs: list[str] = Field(min_length=1)
    needs_po_clarification: bool


class MirrorDelegationDecision(BaseModel):
    """Serving-safe mirror of `review_schemas.DelegationDecision`.

    Combination rules (reuse_previous/invoke, extra_context/invoke) are
    deliberately NOT enforced here — Vertex structured output rejects
    cross-field validators; the strict model enforces them at the adapter
    boundary, where failure triggers the bounded corrective re-prompt loop.
    """

    invoke: str = "none"
    extra_context: str | None = None
    reuse_previous: bool = False
    open_issues: list[str] = Field(default_factory=list)
    readiness: str = "needs_work"


class MirrorResolutionDraft(BaseModel):
    """Serving-safe mirror of `review_schemas.ResolutionDraft`."""

    issue: str
    disposition: str
    explanation: str


class MirrorIssueDraft(BaseModel):
    """Serving-safe mirror of `review_schemas.IssueDraft` (D19: the
    facilitator-minted issue descriptor; must be emittable by Vertex
    structured output on the turn the id is minted)."""

    issue: str
    title: str
    description: str


class ServingSafeFacilitatorTurnOutput(BaseModel):
    """Serving-safe mirror of `review_schemas.FacilitatorTurnOutput`."""

    reply: str
    delegation: MirrorDelegationDecision
    resolutions: list[MirrorResolutionDraft] = Field(default_factory=list)
    new_issues: list[MirrorIssueDraft] = Field(default_factory=list)


class MirrorSynthesisInputs(BaseModel):
    """Serving-safe mirror of the `SynthesisReport.inputs` dict: fixed
    `business`/`engineering` keys so the model cannot invent key names."""

    business: MirrorArtifactReference
    engineering: MirrorArtifactReference


class ServingSafeSynthesisReport(BaseModel):
    """Serving-safe mirror of `review_schemas.SynthesisReport`."""

    story_id: str
    summary: str
    merged_findings: list[MirrorFinding]
    conflicts: list[MirrorConflictItem]
    questions_for_po: list[str]
    resolved_from_previous: list[str]
    inputs: MirrorSynthesisInputs
