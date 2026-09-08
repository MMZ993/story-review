"""Tests for the story preparation step (story_mcp.prepare).

Verifies the owner-approved ADO → StoryDetail mapping (D10) against small
synthetic envelopes, plus the evaluation-oracle guard: no scenario or any
other dataset-only metadata may appear in a prepared story. The full 45-file
dataset is pinned separately by the golden snapshot test.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from story_mcp.prepare import ContextIndex, prepare_backlog, prepare_story

STORIES_DIR = pytest.importorskip("pathlib").Path(__file__).resolve().parents[3] / "dataset" / "stories"


def _comment(text: str, when: str, author: str = "Story Author") -> dict:
    return {
        "text": text,
        "createdBy": {"displayName": author, "uniqueName": f"{author}@example.com"},
        "createdDate": when,
    }


def _context_item(ado_id: int, title: str, item_type: str, parent: int | None, desc: str = ""):
    return {
        "id": ado_id,
        "fields": {
            "System.Title": title,
            "System.WorkItemType": item_type,
            "System.State": "New",
            "System.AreaPath": "story-review",
            "System.Description": desc,
            **({"System.Parent": parent} if parent is not None else {}),
        },
    }


def _envelope(
    *,
    case_id="t1/clean",
    story_id="story-01",
    template="t1",
    scenario="clean",
    ado_id=10,
    title="Some title",
    description="<p><b>D</b> &amp; x</p><p>Second</p>",
    ac="<ul><li>a </li><li>b</li></ul>",
    parent=3,
    comments=(),
    linked_stories=(),
) -> dict:
    env = {
        "schema_version": 1,
        "case_id": case_id,
        "story_id": story_id,
        "template": template,
        "scenario": scenario,
        "ado_source_id": ado_id,
        "exported_at": "2026-09-08T00:00:00Z",
        "comments": list(comments),
        "linked_stories": list(linked_stories),
        "work_item": {
            "id": ado_id,
            "fields": {
                "System.Title": title,
                "System.State": "New",
                "System.AreaPath": f"story-review\\{template.upper()}" if template != "t1" else "story-review",
                "System.WorkItemType": "User Story",
                "System.Description": description,
                "Microsoft.VSTS.Common.AcceptanceCriteria": ac,
                "System.Parent": parent,
            },
            "relations": [
                {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": f"https://dev.azure.com/$ADO_ORG/<project-id>/_apis/wit/workItems/{parent}",
                }
            ],
        },
    }
    return env


@pytest.fixture()
def context_index() -> ContextIndex:
    return ContextIndex.from_items(
        [
            _context_item(2, "Epic T", "Epic", None, "<p>Roadmap X</p>"),
            _context_item(3, "Feature T", "Feature", 2),
        ]
    )


class TestPrepareStory:
    def test_maps_core_fields_and_flattens_rich_text(self, context_index):
        detail = prepare_story(_envelope(), context_index, peers={})
        assert detail.story_id == "story-01"
        assert detail.title == "Some title"
        assert detail.status == "New"
        assert detail.description == "D & x\nSecond"
        assert detail.acceptance_criteria == ["a", "b"]

    def test_epic_and_roadmap_context_from_parent_chain(self, context_index):
        detail = prepare_story(_envelope(), context_index, peers={})
        assert detail.epic_context == "Epic T — Feature T"
        assert detail.roadmap_context == "Roadmap X"

    def test_empty_acceptance_criteria_field_yields_empty_list(self, context_index):
        detail = prepare_story(_envelope(ac=""), context_index, peers={})
        assert detail.acceptance_criteria == []

    def test_comments_mapped_sorted_and_capped_fields(self, context_index):
        detail = prepare_story(
            _envelope(
                comments=[
                    _comment("second", "2026-09-08T14:06:00Z"),
                    _comment("first", "2026-09-08T14:05:00Z", author="PO"),
                ]
            ),
            context_index,
            peers={},
        )
        assert [(c.author, c.text) for c in detail.comments] == [
            ("PO", "first"),
            ("Story Author", "second"),
        ]
        assert detail.comments[0].created_at == datetime(
            2026, 9, 8, 14, 5, tzinfo=timezone.utc
        )

    def test_no_dataset_evaluation_metadata_in_output(self, context_index):
        detail = prepare_story(_envelope(scenario="hidden-conflict"), context_index, peers={})
        dumped = detail.model_dump()
        assert "scenario" not in dumped
        assert "quality_class" not in dumped
        assert "template" not in dumped

    def test_missing_parent_chain_is_a_loud_error(self, context_index):
        with pytest.raises(ValueError, match="parent"):
            prepare_story(_envelope(parent=99), context_index, peers={})

    def test_linked_story_resolved_to_context_story(self, context_index):
        target = _envelope(
            case_id="t2/clean",
            story_id="story-02",
            template="t2",
            ado_id=11,
            parent=3,
            comments=[_comment("c", "2026-09-08T14:05:00Z")],
        )
        env = _envelope(linked_stories=["t2/clean"])
        env["work_item"]["relations"].append(
            {
                "rel": "System.LinkTypes.Related",
                "url": "https://dev.azure.com/$ADO_ORG/<project-id>/_apis/wit/workItems/11",
            }
        )
        detail = prepare_story(env, context_index, peers={"t2/clean": target})
        assert len(detail.context_stories) == 1
        ctx = detail.context_stories[0]
        assert ctx.story_id == "story-02"
        assert ctx.relation == "related"
        assert ctx.description == "D & x\nSecond"
        assert ctx.acceptance_criteria == ["a", "b"]
        assert ctx.comments[0].text == "c"

    def test_dependency_relation_maps_to_depends(self, context_index):
        target = _envelope(case_id="t2/clean", story_id="story-02", template="t2", ado_id=11)
        env = _envelope(linked_stories=["t2/clean"])
        env["work_item"]["relations"].append(
            {
                "rel": "System.LinkTypes.Dependency-Forward",
                "url": "https://dev.azure.com/$ADO_ORG/<project-id>/_apis/wit/workItems/11",
            }
        )
        detail = prepare_story(env, context_index, peers={"t2/clean": target})
        assert detail.context_stories[0].relation == "depends"


class TestPrepareBacklog:
    def test_real_dataset_prepares_all_45_stories(self):
        backlog = prepare_backlog(STORIES_DIR)
        assert len(backlog.details) == 45
        assert [s.story_id for s in backlog.summaries] == sorted(backlog.details)
        # Context envelopes (epic/features) never appear as stories.
        assert all(s.story_id.startswith("story-") for s in backlog.summaries)
