"""Preparation step: ADO work item → design ``StoryDetail`` (D10 mapping).

One pipeline serves both data sources: the mock dataset (verbatim ADO
work-item JSON in ``dataset/stories/``) and live Azure DevOps REST responses
produce identical work-item shapes. The mock path additionally knows the
dataset envelope identity (``story_id``, parent-chain envelopes, linked
stories); the azure source supplies the same shapes directly.

Mapping (owner-approved session 19, D10):

- ``story_id``: envelope ``story_id`` (mock) — azure mints ``ado-<id>`` at
  its own boundary; never derived from other fields here.
- ``title`` ← ``System.Title``; ``status`` ← ``System.State`` (verbatim).
- ``description`` ← ``System.Description``, HTML-flattened.
- ``acceptance_criteria`` ← ``Microsoft.VSTS.Common.AcceptanceCriteria``,
  HTML-flattened, one entry per block element; empty field → empty list.
- ``epic_context`` ← parent chain: ``"<Epic title> — <Feature title>"`` (a
  non-empty Feature description is appended flattened below).
- ``roadmap_context`` ← the Epic's ``System.Description``, flattened.
- ``comments`` ← comments objects: ``author`` ← ``createdBy.displayName``,
  ``text``, ``created_at`` ← ``createdDate``; sorted by ``created_at``.
- ``context_stories`` ← ``linked_stories`` refs resolved against the peer
  envelopes; ``relation`` from the ADO relation type (Related → related,
  Dependency → depends).

Dataset evaluation metadata (``scenario``, template, expected outcomes) is
never read here and cannot appear in the output.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dataset_loader.envelope import StoryEnvelope, WorkItem, WorkItemComment
from review_schemas.review import ContextStory, StoryComment, StoryDetail, StorySummary

from story_mcp.flatten import html_to_blocks, html_to_text

#: ADO relation type → design ContextStory relation.
_RELATION_BY_ADO_TYPE = {
    "System.LinkTypes.Related": "related",
    "System.LinkTypes.Dependency-Forward": "depends",
    "System.LinkTypes.Dependency-Reverse": "depends",
}

_DESCRIPTION = "System.Description"
_ACCEPTANCE = "Microsoft.VSTS.Common.AcceptanceCriteria"
_PARENT = "System.Parent"


class PreparationError(ValueError):
    """A story could not be prepared: missing or inconsistent ADO data."""


@dataclass(frozen=True)
class ContextIndex:
    """Epic/Feature work items by ADO id (from ``dataset/stories/context/``)."""

    items: dict[int, WorkItem]

    @classmethod
    def from_items(cls, items: list[dict]) -> "ContextIndex":
        # Items are context envelopes (``work_item`` key) or bare work items.
        work_items = (
            item["work_item"] if "work_item" in item else item for item in items
        )
        return cls({wi["id"]: WorkItem.model_validate(wi) for wi in work_items})

    @classmethod
    def from_dir(cls, context_dir: Path) -> "ContextIndex":
        return cls.from_items(
            [__import__("json").loads(p.read_text()) for p in sorted(context_dir.glob("*.json"))]
        )


def _field(item: WorkItem, name: str, *, owner: str) -> str:
    value = item.fields.get(name)
    if not isinstance(value, str):
        raise PreparationError(f"{owner} has no {name}")
    return value


def _epic_and_feature(story: WorkItem, context: ContextIndex) -> tuple[WorkItem, WorkItem]:
    """Resolve the story's parent Feature and grandparent Epic."""
    parent_id = story.fields.get(_PARENT)
    if not isinstance(parent_id, int) or parent_id not in context.items:
        raise PreparationError(f"work item {story.id} has no parent in the context index")
    feature = context.items[parent_id]
    epic_id = feature.fields.get(_PARENT)
    if not isinstance(epic_id, int) or epic_id not in context.items:
        raise PreparationError(f"feature {feature.id} has no epic in the context index")
    return context.items[epic_id], feature


def _epic_context(epic: WorkItem, feature: WorkItem) -> str:
    parts = [
        f"{_field(epic, 'System.Title', owner='epic')} — "
        f"{_field(feature, 'System.Title', owner='feature')}"
    ]
    feature_desc = html_to_text(feature.fields.get(_DESCRIPTION) or "")
    if feature_desc:
        parts.append(feature_desc)
    return "\n".join(parts)


def _comments(raw: list[WorkItemComment]) -> list[StoryComment]:
    mapped = [
        StoryComment(
            author=comment.model_extra["createdBy"]["displayName"],
            text=comment.text,
            created_at=datetime.fromisoformat(
                comment.model_extra["createdDate"].replace("Z", "+00:00")
            ),
        )
        for comment in raw
    ]
    return sorted(mapped, key=lambda c: c.created_at)


def _context_stories(
    story: WorkItem, linked: list[str], peers: dict[str, StoryEnvelope]
) -> list[ContextStory]:
    """Resolve ``linked_stories`` refs into prepared ContextStory entries."""
    relation_by_target: dict[int, str] = {}
    for relation in story.relations or []:
        rel = relation.get("rel")
        target = int(str(relation.get("url", "")).rstrip("/").rsplit("/", 1)[-1])
        if rel in _RELATION_BY_ADO_TYPE:
            relation_by_target[target] = _RELATION_BY_ADO_TYPE[rel]
    stories: list[ContextStory] = []
    for case_id in linked:
        peer = peers.get(case_id)
        if peer is None:
            raise PreparationError(f"linked story {case_id!r} has no peer envelope")
        target = (
            peer if isinstance(peer, StoryEnvelope) else StoryEnvelope.model_validate(peer)
        )
        target_item = target.work_item
        stories.append(
            ContextStory(
                story_id=target.story_id,
                title=_field(target_item, "System.Title", owner=f"linked story {case_id}"),
                relation=relation_by_target.get(target_item.id, "related"),
                description=html_to_text(target_item.fields.get(_DESCRIPTION) or ""),
                acceptance_criteria=html_to_blocks(target_item.fields.get(_ACCEPTANCE) or ""),
                comments=_comments(target.comments),
            )
        )
    return stories


def prepare_story(
    envelope: dict | StoryEnvelope,
    context: ContextIndex,
    *,
    peers: dict[str, StoryEnvelope],
) -> StoryDetail:
    """Map one dataset story envelope to the public ``StoryDetail``."""
    env = envelope if isinstance(envelope, StoryEnvelope) else StoryEnvelope.model_validate(envelope)
    story = env.work_item
    epic, feature = _epic_and_feature(story, context)
    return StoryDetail(
        story_id=env.story_id,
        title=_field(story, "System.Title", owner="story"),
        status=_field(story, "System.State", owner="story"),
        description=html_to_text(story.fields.get(_DESCRIPTION) or ""),
        acceptance_criteria=html_to_blocks(story.fields.get(_ACCEPTANCE) or ""),
        epic_context=_epic_context(epic, feature),
        roadmap_context=html_to_text(epic.fields.get(_DESCRIPTION) or ""),
        comments=_comments(env.comments),
        context_stories=_context_stories(story, env.linked_stories, peers),
    )


@dataclass(frozen=True)
class PreparedBacklog:
    """Prepared stories by id plus the ordered ``list_stories`` summaries."""

    details: dict[str, StoryDetail]
    summaries: list[StorySummary]


def prepare_backlog(stories_dir: Path) -> PreparedBacklog:
    """Load and prepare every story envelope under ``stories_dir``.

    ``stories_dir`` is the dataset root containing the ``t1``–``t6`` template
    folders and the ``context/`` envelopes. Context envelopes never become
    stories; story ids are the dataset envelope ids.
    """
    envelopes: list[StoryEnvelope] = []
    for path in sorted(stories_dir.glob("t[1-6]/*.json")):
        envelopes.append(StoryEnvelope.model_validate_json(path.read_text()))
    context = ContextIndex.from_dir(stories_dir / "context")
    peers = {env.case_id: env for env in envelopes}
    details = {env.story_id: prepare_story(env, context, peers=peers) for env in envelopes}
    summaries = [
        StorySummary(story_id=d.story_id, title=d.title, status=d.status)
        for _, d in sorted(details.items())
    ]
    return PreparedBacklog(details=details, summaries=summaries)
