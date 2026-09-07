"""MCP tool input/output models.

Implements the "MCP tool models and authorization" section of
docs/design/schemas.md verbatim. Every MCP call returns its success model or
`ToolError`; identity is validated at ingress (fixed per-tool authorization,
see that section). Artifact operations are lineage-scoped: the validators here
enforce the reference-to-run and type/perspective/content relationships;
cross-run reads are prevented server-side.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, model_validator

from review_schemas.base import (
    ArtifactId,
    Format,
    IdempotencyKey,
    RunId,
    SaveArtifactType,
    ShortText,
    StoryId,
    StrictModel,
    Perspective,
)
from review_schemas.review import ReviewReport, StoryDetail, StorySummary
from review_schemas.synthesis import ArtifactReference, SynthesisReport
from review_schemas.facilitator import FinalizedReview

#: Exact content model required per save/get artifact type.
CONTENT_MODEL_BY_TYPE = {
    "story": StoryDetail,
    "review-business": ReviewReport,
    "review-engineering": ReviewReport,
    "synthesis": SynthesisReport,
    "finalized-review": FinalizedReview,
}

#: Perspective required (or forbidden) per review artifact type.
PERSPECTIVE_BY_REVIEW_TYPE = {
    "review-business": "business",
    "review-engineering": "engineering",
}


def expected_perspective(artifact_type: str) -> str | None:
    """The only perspective allowed for `artifact_type` (None if not a review)."""
    return PERSPECTIVE_BY_REVIEW_TYPE.get(artifact_type)


def expected_content_model(artifact_type: str):
    """The content model required for `artifact_type`, or None if unknown."""
    return CONTENT_MODEL_BY_TYPE.get(artifact_type)


class ListStoriesInput(StrictModel):
    """`list_stories` call: optional short-text story-status filter."""

    filter: ShortText | None = None


class ListStoriesOutput(StrictModel):
    """`list_stories` result: story summaries, capped at 50; never
    expected-result data."""

    stories: list[StorySummary] = Field(default_factory=list, max_length=50)


class GetStoryInput(StrictModel):
    """`get_story` call: the dataset story to fetch."""

    story_id: StoryId


class SaveArtifactInput(StrictModel):
    """`save_artifact` call (orchestration only): content whose exact model,
    required perspective, and (for final reviews) story run must match the
    artifact type; the idempotency key deduplicates re-saves."""
    type: SaveArtifactType
    story_run_id: RunId
    perspective: Perspective | None = None
    content: StoryDetail | ReviewReport | SynthesisReport | FinalizedReview
    idempotency_key: IdempotencyKey

    @model_validator(mode="after")
    def type_matches_content(self):
        expected_model = CONTENT_MODEL_BY_TYPE[self.type]
        if type(self.content) is not expected_model:
            raise ValueError("artifact type does not match content model")
        expected_perspective_for_type = PERSPECTIVE_BY_REVIEW_TYPE.get(self.type)
        if self.perspective != expected_perspective_for_type:
            raise ValueError("perspective does not match artifact type")
        if (
            isinstance(self.content, ReviewReport)
            and self.content.perspective != expected_perspective_for_type
        ):
            raise ValueError("review content perspective does not match artifact type")
        if (
            isinstance(self.content, FinalizedReview)
            and self.content.story_run_id != self.story_run_id
        ):
            raise ValueError("final review content belongs to another story run")
        return self


class SaveArtifactOutput(StrictModel):
    """`save_artifact` result: the durable reference plus whether the
    idempotency key created a new artifact or returned an existing one."""

    reference: ArtifactReference
    created: bool


class GetArtifactInput(StrictModel):
    """`get_artifact` call: artifact and run ID — reads never cross runs."""

    artifact_id: ArtifactId
    story_run_id: RunId


class GetArtifactOutput(StrictModel):
    """`get_artifact` result: content must be the exact model the reference
    type declares."""
    reference: ArtifactReference
    content: StoryDetail | ReviewReport | SynthesisReport | FinalizedReview

    @model_validator(mode="after")
    def content_matches_reference(self):
        expected_model = CONTENT_MODEL_BY_TYPE.get(self.reference.type)
        if expected_model is None or type(self.content) is not expected_model:
            raise ValueError("reference type does not match content model")
        return self


class ListArtifactsInput(StrictModel):
    """`list_artifacts` call: run-scoped listing; `perspective` may only
    filter review types and must agree with them; paging via
    limit/offset (server orders by type, perspective, version)."""
    story_run_id: RunId
    type: SaveArtifactType | None = None
    perspective: Perspective | None = None
    limit: Annotated[int, Field(ge=1, le=500)] = 100
    offset: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="after")
    def filters_are_compatible(self):
        expected = PERSPECTIVE_BY_REVIEW_TYPE.get(self.type)
        if self.type in {"story", "synthesis", "finalized-review"} and self.perspective is not None:
            raise ValueError("perspective cannot filter a non-review artifact type")
        if expected is not None and self.perspective not in {None, expected}:
            raise ValueError("perspective conflicts with review artifact type")
        return self


class ListArtifactsOutput(StrictModel):
    """`list_artifacts` result: one page of references plus the run-wide
    total for client paging."""

    items: list[ArtifactReference] = Field(default_factory=list, max_length=500)
    total: Annotated[int, Field(ge=0)]


class RenderReportInput(StrictModel):
    """`render_report` call (orchestration only): the finalized-review
    reference must belong to the supplied story run."""
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
    """`render_report` result: the reference must be the `report-<format>`
    artifact produced by this render."""
    reference: ArtifactReference
    format: Format
    created: bool

    @model_validator(mode="after")
    def format_matches_reference(self):
        if self.reference.type != f"report-{self.format}":
            raise ValueError("report format does not match artifact reference")
        return self
