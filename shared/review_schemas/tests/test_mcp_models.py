"""Tests for the MCP tool-model group (review_schemas.mcp).

Covers every MCP input/output model and its lineage/type/perspective
validators from docs/design/schemas.md: save/get content exact-type checks,
list filter compatibility, and report reference/format rules. One valid
boundary case plus one observable invalid combination per invariant, using
fixed valid nested fixtures.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from review_schemas.mcp import (
    GetArtifactInput,
    GetArtifactOutput,
    GetStoryInput,
    ListArtifactsInput,
    ListArtifactsOutput,
    ListStoriesInput,
    ListStoriesOutput,
    RenderReportInput,
    RenderReportOutput,
    SaveArtifactInput,
    SaveArtifactOutput,
)
from review_schemas.review import ReviewReport, StoryDetail
from review_schemas.synthesis import SynthesisReport
from review_schemas.facilitator import FinalizedReview

from conftest import FIXED_TS, FIXED_UUID, RUN_ID, artifact_reference

STORY_ID = "story-07"
OTHER_RUN_ID = "run-feedface-1234-4cda-b0de-1f2e3d4c5b6a"


def finding(**overrides) -> dict:
    base = {
        "id": "B-1",
        "title": "missing metric",
        "description": "story lacks an acceptance metric",
        "severity": "minor",
        "category": "completeness",
    }
    return base | overrides


def story_detail() -> dict:
    return {
        "story_id": STORY_ID,
        "title": "Payments retry",
        "status": "ready",
        "description": "full story text",
        "epic_context": "epic",
        "roadmap_context": "roadmap",
    }


def review_report(perspective: str) -> dict:
    prefix = "B" if perspective == "business" else "E"
    return {
        "perspective": perspective,
        "story_id": STORY_ID,
        "summary": "review summary",
        "findings": [finding(id=f"{prefix}-1")],
    }


def synthesis_report() -> dict:
    return {
        "story_id": STORY_ID,
        "summary": "synthesis summary",
        "merged_findings": [finding(id="B-1"), finding(id="E-1", category="security")],
        "conflicts": [],
        "inputs": {
            "business": artifact_reference("review-business"),
            "engineering": artifact_reference("review-engineering"),
        },
    }


def finalized_review() -> dict:
    return {
        "story_id": STORY_ID,
        "story_run_id": RUN_ID,
        "synthesis_reference": artifact_reference("synthesis"),
        "resolutions": [],
        "remaining_open_issues": [],
        "po_accepted": True,
        "final_turn_number": 1,
        "finalized_at": FIXED_TS,
    }


class TestListAndGetStory:
    def test_list_input_filter_optional_and_bounded(self):
        assert ListStoriesInput().filter is None
        assert ListStoriesInput(filter="ready").filter == "ready"
        with pytest.raises(ValidationError):
            ListStoriesInput(filter="x" * 501)

    def test_list_output_defaults_and_max_length(self):
        empty = ListStoriesOutput()
        assert empty.stories == []
        refs = [{"story_id": STORY_ID, "title": "t", "status": "ready"}]
        assert len(ListStoriesOutput(stories=refs * 50).stories) == 50
        with pytest.raises(ValidationError):
            ListStoriesOutput(stories=refs * 51)

    def test_get_story_input(self):
        assert GetStoryInput(story_id=STORY_ID).story_id == STORY_ID
        with pytest.raises(ValidationError):
            GetStoryInput(story_id="story-9")


class TestSaveArtifact:
    def _input(self, type_: str, content: dict, perspective: str | None = None, **overrides):
        return SaveArtifactInput.model_validate(
            {
                "type": type_,
                "story_run_id": RUN_ID,
                "perspective": perspective,
                "content": content,
                "idempotency_key": FIXED_UUID,
            }
            | overrides
        )

    @pytest.mark.parametrize(
        ("type_", "content", "perspective"),
        [
            ("story", story_detail(), None),
            ("review-business", review_report("business"), "business"),
            ("review-engineering", review_report("engineering"), "engineering"),
            ("synthesis", synthesis_report(), None),
            ("finalized-review", finalized_review(), None),
        ],
    )
    def test_valid_saves(self, type_, content, perspective):
        saved = self._input(type_, content, perspective)
        assert saved.type == type_

    def test_content_model_must_match_type(self):
        with pytest.raises(ValidationError, match="content model"):
            self._input("story", review_report("business"))
        with pytest.raises(ValidationError, match="content model"):
            self._input("synthesis", story_detail())

    def test_perspective_must_match_type(self):
        # review types require the matching perspective; non-review reject any
        with pytest.raises(ValidationError, match="perspective does not match artifact type"):
            self._input("review-business", review_report("business"), None)
        with pytest.raises(ValidationError, match="perspective does not match artifact type"):
            self._input("review-business", review_report("business"), "engineering")
        with pytest.raises(ValidationError, match="perspective does not match artifact type"):
            self._input("story", story_detail(), "business")

    def test_review_content_perspective_must_match_type(self):
        with pytest.raises(ValidationError, match="review content perspective"):
            self._input(
                "review-business",
                review_report("engineering"),
                "business",
            )

    def test_finalized_content_must_belong_to_supplied_run(self):
        with pytest.raises(ValidationError, match="another story run"):
            self._input("finalized-review", finalized_review(), story_run_id=OTHER_RUN_ID)

    def test_output(self):
        out = SaveArtifactOutput.model_validate(
            {"reference": artifact_reference("story"), "created": True}
        )
        assert out.created


class TestGetArtifact:
    def test_input(self):
        assert GetArtifactInput(
            artifact_id=f"art-{'12345678-90ab-4cda-b0de-1f2e3d4c5b6a'}",
            story_run_id=RUN_ID,
        ).artifact_id.startswith("art-")
        with pytest.raises(ValidationError):
            GetArtifactInput(artifact_id="bogus", story_run_id=RUN_ID)

    @pytest.mark.parametrize(
        ("ref_type", "content"),
        [
            ("story", story_detail()),
            ("review-business", review_report("business")),
            ("review-engineering", review_report("engineering")),
            ("synthesis", synthesis_report()),
            ("finalized-review", finalized_review()),
        ],
    )
    def test_output_content_matches_reference(self, ref_type, content):
        out = GetArtifactOutput.model_validate(
            {"reference": artifact_reference(ref_type), "content": content}
        )
        assert out.reference.type == ref_type

    def test_output_mismatch_rejected(self):
        with pytest.raises(ValidationError, match="content model"):
            GetArtifactOutput.model_validate(
                {"reference": artifact_reference("story"), "content": review_report("business")}
            )

    def test_output_report_reference_rejected(self):
        with pytest.raises(ValidationError, match="content model"):
            GetArtifactOutput.model_validate(
                {"reference": artifact_reference("report-md"), "content": story_detail()}
            )


class TestListArtifacts:
    def test_defaults(self):
        default = ListArtifactsInput(story_run_id=RUN_ID)
        assert default.type is None
        assert default.perspective is None
        assert default.limit == 100
        assert default.offset == 0

    @pytest.mark.parametrize("limit", [0, 501, -1])
    def test_limit_bounds(self, limit):
        with pytest.raises(ValidationError):
            ListArtifactsInput(story_run_id=RUN_ID, limit=limit)

    @pytest.mark.parametrize("limit", [1, 500])
    def test_limit_boundary_values_accepted(self, limit):
        assert ListArtifactsInput(story_run_id=RUN_ID, limit=limit).limit == limit

    def test_offset_bounds(self):
        with pytest.raises(ValidationError):
            ListArtifactsInput(story_run_id=RUN_ID, offset=-1)

    def test_compatible_filters(self):
        assert (
            ListArtifactsInput(
                story_run_id=RUN_ID, type="review-business", perspective="business"
            ).perspective
            == "business"
        )
        assert ListArtifactsInput(story_run_id=RUN_ID, type="review-business").perspective is None

    def test_perspective_conflicts_with_review_type(self):
        with pytest.raises(ValidationError, match="perspective conflicts"):
            ListArtifactsInput(
                story_run_id=RUN_ID, type="review-business", perspective="engineering"
            )

    @pytest.mark.parametrize("type_", ["story", "synthesis", "finalized-review"])
    def test_perspective_rejected_for_non_review_types(self, type_):
        with pytest.raises(ValidationError, match="cannot filter"):
            ListArtifactsInput(story_run_id=RUN_ID, type=type_, perspective="business")

    def test_output(self):
        empty = ListArtifactsOutput(total=0)
        assert empty.items == []
        assert empty.total == 0
        assert len(ListArtifactsOutput(items=[artifact_reference("story")] * 500, total=500).items) == 500
        with pytest.raises(ValidationError):
            ListArtifactsOutput(items=[artifact_reference("story")] * 501, total=501)


class TestRenderReport:
    def _input(self, **overrides):
        return RenderReportInput.model_validate(
            {
                "story_run_id": RUN_ID,
                "final_review_reference": artifact_reference("finalized-review"),
                "format": "md",
            }
            | overrides
        )

    def test_valid_input(self):
        assert self._input().format == "md"

    def test_reference_must_belong_to_supplied_run(self):
        with pytest.raises(ValidationError, match="finalized-review artifact"):
            self._input(story_run_id=OTHER_RUN_ID)

    def test_reference_must_be_finalized_review(self):
        with pytest.raises(ValidationError, match="finalized-review artifact"):
            self._input(final_review_reference=artifact_reference("synthesis"))

    def test_output_format_matches_reference(self):
        out = RenderReportOutput.model_validate(
            {"reference": artifact_reference("report-md"), "format": "md", "created": True}
        )
        assert out.format == "md"

    def test_output_format_mismatch_rejected(self):
        with pytest.raises(ValidationError, match="does not match artifact reference"):
            RenderReportOutput.model_validate(
                {"reference": artifact_reference("report-md"), "format": "pdf", "created": False}
            )
        with pytest.raises(ValidationError, match="does not match artifact reference"):
            RenderReportOutput.model_validate(
                {
                    "reference": artifact_reference("finalized-review"),
                    "format": "md",
                    "created": False,
                }
            )
