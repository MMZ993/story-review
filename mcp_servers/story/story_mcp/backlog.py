"""Backlog core shared by both data sources (D10).

Owns the rules that are source-independent:

- **Id spaces never mix**: mock serves `story-NN`, azure serves `ado-N`;
  a cross-source lookup is `STORY_NOT_FOUND` (`StoryNotFound`), not an error
  of the other kind.
- **Filter**: `list_stories` `filter` is a case-insensitive substring match
  on the story status (schemas.md: "optional short-text story-status
  filter").
- **Source resolution**: `None` (the default) means the deployment default
  (`STORY_SOURCE` env); an explicit value is the orchestration-only
  override. Only `azure` and `mock` exist.
"""

from __future__ import annotations

import re
from typing import Protocol

from review_schemas.review import StoryDetail, StorySummary

#: Dataset (mock) story ids: two zero-padded digits.
MOCK_ID_PATTERN = re.compile(r"^story-[0-9]{2}$")

#: Live Azure DevOps work-item ids: 1–8 digits.
AZURE_ID_PATTERN = re.compile(r"^ado-[0-9]{1,8}$")

VALID_SOURCES = ("azure", "mock")


class StoryNotFound(Exception):
    """The story id does not exist in the selected source's id space."""

    def __init__(self, story_id: str) -> None:
        super().__init__(f"story {story_id!r} not found in this source")
        self.story_id = story_id


class InvalidSourceOverride(Exception):
    """A source name outside the `azure` | `mock` vocabulary."""


class BacklogLike(Protocol):
    """What both data sources offer the server (structural typing)."""

    def list_stories(self, status_filter: str | None) -> list[StorySummary]: ...

    def get_story(self, story_id: str) -> StoryDetail: ...


def check_id_space(source: str, story_id: str) -> None:
    """Raise `StoryNotFound` when `story_id` belongs to the other id space."""
    pattern = MOCK_ID_PATTERN if source == "mock" else AZURE_ID_PATTERN
    if not pattern.fullmatch(story_id):
        raise StoryNotFound(story_id)


def apply_filter(
    stories: list[StorySummary], status_filter: str | None
) -> list[StorySummary]:
    """Keep summaries whose status contains `status_filter` (case-insensitive)."""
    if status_filter is None:
        return stories
    needle = status_filter.lower()
    return [s for s in stories if needle in s.status.lower()]


def resolve_source(override: str | None, deployment_default: str) -> str:
    """Apply the D10 selection rule: explicit override, else deployment default."""
    source = override if override is not None else deployment_default
    if source not in VALID_SOURCES:
        raise InvalidSourceOverride(source)
    return source
