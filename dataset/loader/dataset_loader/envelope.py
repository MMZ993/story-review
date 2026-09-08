"""Strict models for the dataset story envelope (D9 export format).

One story file = envelope metadata + the verbatim ADO work-item JSON under
``work_item``. The envelope carries the stable dataset identity
(``case_id``, ``story_id``, ``template``, ``scenario``); the ADO id is
provenance only (``ado_source_id``).

Validation is deliberately minimal on the verbatim ``work_item`` payload:
it must be a work-item-shaped dict with the fields the review pipeline
reads (title, type, area, state). Fidelity/trimming decisions belong to a
separate preparation step, not here (D9).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ado_wire import WorkItem, WorkItemComment  # noqa: F401  (re-export)
from review_schemas import StoryId

Template = Annotated[str, StringConstraints(pattern=r"^t[1-6]$")]
Scenario = Annotated[
    str,
    StringConstraints(
        pattern=r"^(clean|business-weak|engineering-weak|conflicting"
        r"|partial-resolution|unresolvable|hidden-conflict)(-2)?$"
        r"|^(comments-benign|comments-clarify-business"
        r"|comments-complete-engineering)$"
    ),
]
CaseId = Annotated[
    str, StringConstraints(pattern=r"^t[1-6]/[a-z][a-z0-9-]*$")
]


# T1-only comment scenarios (D9 amendment 3): valid scenario slugs that
# must never appear outside template t1.
T1_ONLY_SCENARIOS = frozenset(
    {"comments-benign", "comments-clarify-business",
     "comments-complete-engineering"}
)


class StoryEnvelope(BaseModel):
    """Dataset story file envelope (see dataset/README.md)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    case_id: CaseId
    story_id: StoryId
    template: Template
    scenario: Scenario
    ado_source_id: int = Field(ge=1)
    exported_at: str = Field(min_length=1)
    work_item: WorkItem
    # Extension fields (additive, D9 amendment 3): backlog discussion and
    # linked context stories. Both default empty — pre-extension story files
    # (the 42 canonical cases) are unaffected.
    comments: list[WorkItemComment] = Field(
        default_factory=list, max_length=50
    )
    # References to other story FILES in the dataset (case ids), never
    # embedded content. Cross-file resolution is enforced by the loader.
    linked_stories: list[CaseId] = Field(
        default_factory=list, max_length=5, unique=True
    )

    @model_validator(mode="after")
    def linked_stories_are_unique(self):
        if len(set(self.linked_stories)) != len(self.linked_stories):
            raise ValueError("linked_stories contains duplicates")
        return self

    @model_validator(mode="after")
    def t1_only_scenario_stays_in_t1(self):
        if self.scenario in T1_ONLY_SCENARIOS and self.template != "t1":
            raise ValueError(
                f"scenario {self.scenario!r} is t1-only "
                f"but exported from {self.template}"
            )
        return self

    def case_id_matches_components(self) -> bool:
        return self.case_id == f"{self.template}/{self.scenario}"
