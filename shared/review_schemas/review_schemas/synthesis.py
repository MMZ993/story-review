"""Synthesis models: artifact references and the merged synthesis report.

Implements the synthesis part of the domain section of
docs/design/schemas.md: `ArtifactReference` (safe immutable reference),
`ArtifactRecord` (internal storage record), `ConflictItem`, and
`SynthesisReport` with the paired-input invariant.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from review_schemas.base import (
    ArtifactId,
    ArtifactType,
    Perspective,
    RunId,
    Sha256,
    ShortText,
    StoryId,
    StrictModel,
    Text,
    UtcDatetime,
)
from review_schemas.review import Finding


class ConflictItem(StrictModel):
    """One business/engineering disagreement needing a decision."""

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
    """Merged two-perspective review with conflicts and follow-up questions."""

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
