"""Story and review models.

Implements the story/review part of the domain section of
docs/design/schemas.md: `StorySummary`/`StoryDetail` (dataset payloads),
`Finding` (one review observation), and `ReviewReport` (one perspective's
review of a story, with the finding-prefix invariant).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from review_schemas.base import (
    Perspective,
    ShortText,
    StoryId,
    StrictModel,
    Text,
    UtcDatetime,
)


class StorySummary(StrictModel):
    """Backlog-level story identity shown in lists."""

    story_id: StoryId
    title: ShortText
    status: ShortText
    quality_class: ShortText


class StoryComment(StrictModel):
    """One backlog discussion comment attached to a story; semantic review
    input (anonymized author persona)."""

    author: ShortText
    text: Text
    created_at: UtcDatetime


class ContextStory(StrictModel):
    """A linked related/depends story surfaced as separate context; never
    merged into the main story's own content."""

    story_id: StoryId
    title: ShortText
    relation: Literal["related", "depends"]
    description: Text
    acceptance_criteria: list[Text] = Field(default_factory=list, max_length=100)
    comments: list[StoryComment] = Field(default_factory=list, max_length=50)


class StoryDetail(StorySummary):
    """Full dataset story payload used as review input."""

    description: Text
    acceptance_criteria: list[Text] = Field(default_factory=list, max_length=100)
    epic_context: Text
    roadmap_context: Text
    comments: list[StoryComment] = Field(default_factory=list, max_length=50)
    context_stories: list[ContextStory] = Field(default_factory=list, max_length=5)


class Finding(StrictModel):
    """One review observation; ID prefix encodes the perspective."""

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
    """One perspective's review of a story within a run."""

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
