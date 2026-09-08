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

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from review_schemas import StoryId

Template = Annotated[str, StringConstraints(pattern=r"^t[1-6]$")]
Scenario = Annotated[
    str,
    StringConstraints(
        pattern=r"^(clean|business-weak|engineering-weak|conflicting"
        r"|partial-resolution|unresolvable|hidden-conflict)(-2)?$"
    ),
]
CaseId = Annotated[
    str, StringConstraints(pattern=r"^t[1-6]/[a-z][a-z0-9-]*$")
]

# Minimal ADO work-item shape: the fields the review pipeline consumes.
_REQUIRED_WORK_ITEM_FIELDS = (
    "System.Title",
    "System.WorkItemType",
    "System.AreaPath",
    "System.State",
)



class WorkItem(BaseModel):
    """Verbatim `az boards work-item show --expand all` / REST work item."""

    model_config = ConfigDict(extra="allow", strict=False)

    id: int
    fields: dict[str, object]

    def missing_required_fields(self) -> tuple[str, ...]:
        return tuple(
            name
            for name in _REQUIRED_WORK_ITEM_FIELDS
            if self.fields.get(name) in (None, "")
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

    def case_id_matches_components(self) -> bool:
        return self.case_id == f"{self.template}/{self.scenario}"
