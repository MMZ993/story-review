"""Strict models for verbatim Azure DevOps wire payloads.

Extracted from the dataset-loader envelope module so the wire shapes can
be shared by the story-MCP preparation step (live ADO REST responses) and
the frozen dataset export wrapper alike. Code moved verbatim (D9/D10).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorkItemComment(BaseModel):
    """Verbatim ADO comments-API comment (sanitized at export).

    Minimal validation — the ``text`` must exist. Mapping to the design's
    ``StoryComment`` (author/text/created_at) is the Phase 4 story-MCP
    preparation step, not the loader's (D9: export stays verbatim).
    """

    model_config = ConfigDict(extra="allow", strict=False)

    text: str = Field(min_length=1)


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
