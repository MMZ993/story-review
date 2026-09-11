"""Tests for the story/review/synthesis/facilitator/judge domain group.

One group spanning review_schemas.{review,synthesis,facilitator,judge}, per the
Phase 2 plan. Every cross-field validator gets one valid boundary case and one
observable invalid combination, using fixed valid nested fixtures.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from review_schemas.facilitator import (
    ConversationSummary,
    DelegationDecision,
    FacilitatorTurnOutput,
    FinalizedReview,
    IssueDraft,
    IssueEntry,
    ResolutionDraft,
    ResolutionItem,
    latest_resolutions,
)
from review_schemas.judge import JudgeDimensionScore, JudgeIssue, JudgeResult
from review_schemas.review import (
    ContextStory,
    Finding,
    ReviewReport,
    StoryComment,
    StoryDetail,
    StorySummary,
)
from review_schemas.synthesis import (
    ArtifactRecord,
    ArtifactReference,
    ConflictItem,
    SynthesisReport,
)

from conftest import FIXED_TS, FIXED_UUID, RUN_ID, artifact_reference

STORY_ID = "story-07"
OTHER_RUN_ID = "run-ffffffff-90ab-4cda-b0de-1f2e3d4c5b6a"


def finding(**overrides) -> dict:
    base = {
        "id": "B-1",
        "title": "missing metric",
        "description": "story lacks an acceptance metric",
        "severity": "minor",
        "category": "completeness",
    }
    return base | overrides


class TestStoryModels:
    def test_summary_and_detail(self):
        summary = StorySummary.model_validate(
            {"story_id": STORY_ID, "title": "Payments retry", "status": "ready"}
        )
        assert isinstance(summary, StorySummary)
        detail = StoryDetail.model_validate(
            summary.model_dump()
            | {
                "description": "full story text",
                "epic_context": "epic",
                "roadmap_context": "roadmap",
            }
        )
        assert detail.acceptance_criteria == []
        assert detail.comments == []
        assert detail.context_stories == []

    def test_public_story_models_reject_dataset_evaluation_metadata(self):
        """Story API and MCP payloads must not expose the dataset-only label."""
        summary = {
            "story_id": STORY_ID,
            "title": "Payments retry",
            "status": "ready",
            "quality_class": "business-weak",
        }
        with pytest.raises(ValidationError):
            StorySummary.model_validate(summary)
        with pytest.raises(ValidationError):
            StoryDetail.model_validate(
                summary
                | {
                    "description": "full story text",
                    "epic_context": "epic",
                    "roadmap_context": "roadmap",
                }
            )

    def test_detail_accepts_comments_and_context_stories(self):
        comment = {
            "author": "Story Author",
            "text": "clarifies the retry cap",
            "created_at": FIXED_TS,
        }
        context = {
            "story_id": "story-08",
            "title": "Retry queue design",
            "relation": "depends",
            "description": "engineering design the retry depends on",
            "acceptance_criteria": ["queue drains within 5 min"],
            "comments": [comment],
        }
        detail = StoryDetail.model_validate(
            {
                "story_id": STORY_ID,
                "title": "t",
                "status": "s",
                "description": "d",
                "epic_context": "e",
                "roadmap_context": "r",
                "comments": [comment],
                "context_stories": [context],
            }
        )
        assert detail.comments[0] == StoryComment.model_validate(comment)
        assert detail.context_stories[0].relation == "depends"

    def test_comment_requires_exact_fields(self):
        for payload in (
            {"text": "t", "created_at": FIXED_TS},  # missing author
            {"author": "a", "created_at": FIXED_TS},  # missing text
            {"author": "a", "text": "t"},  # missing created_at
            {"author": "a", "text": "t", "created_at": FIXED_TS, "bogus": 1},
        ):
            with pytest.raises(ValidationError):
                StoryComment.model_validate(payload)

    def test_context_story_relation_is_constrained(self):
        def context(relation):
            return {
                "story_id": "story-08",
                "title": "t",
                "relation": relation,
                "description": "d",
            }

        assert ContextStory.model_validate(context("related")).relation == "related"
        with pytest.raises(ValidationError):
            ContextStory.model_validate(context("blocks"))
        with pytest.raises(ValidationError):
            ContextStory.model_validate(context("related") | {"bogus": 1})

    def test_list_caps_comments_50_and_context_5(self):
        base = {
            "story_id": STORY_ID,
            "title": "t",
            "status": "s",
            "description": "d",
            "epic_context": "e",
            "roadmap_context": "r",
        }
        comment = {"author": "a", "text": "t", "created_at": FIXED_TS}
        context = {
            "story_id": "story-08",
            "title": "t",
            "relation": "related",
            "description": "d",
        }
        assert StoryDetail.model_validate(
            base | {"comments": [comment] * 50, "context_stories": [context] * 5}
        )
        with pytest.raises(ValidationError):
            StoryDetail.model_validate(base | {"comments": [comment] * 51})
        with pytest.raises(ValidationError):
            StoryDetail.model_validate(base | {"context_stories": [context] * 6})

    def test_detail_rejects_extra_fields(self):
        payload = {
            "story_id": STORY_ID,
            "title": "t",
            "status": "s",
            "description": "d",
            "epic_context": "e",
            "roadmap_context": "r",
            "bogus": 1,
        }
        with pytest.raises(ValidationError):
            StoryDetail.model_validate(payload)

    def test_finding_id_pattern(self):
        assert Finding.model_validate(finding(id="E-42")).id == "E-42"
        for bad in ("B-0", "B-01", "X-1", "b-1", "B-1x"):
            with pytest.raises(ValidationError):
                Finding.model_validate(finding(id=bad))


class TestReviewReport:
    def _report(self, **overrides) -> dict:
        base = {
            "perspective": "business",
            "story_id": STORY_ID,
            "summary": "review summary",
            "findings": [finding()],
        }
        return base | overrides

    def test_valid_business_report_with_matching_prefix(self):
        report = ReviewReport.model_validate(self._report())
        assert report.findings[0].id == "B-1"

    def test_wrong_finding_prefix_rejected(self):
        with pytest.raises(ValidationError, match="prefix"):
            ReviewReport.model_validate(
                self._report(perspective="business", findings=[finding(id="E-1")])
            )
        with pytest.raises(ValidationError, match="prefix"):
            ReviewReport.model_validate(
                self._report(
                    perspective="engineering",
                    findings=[finding(id="B-1")],
                )
            )


class TestArtifactReference:
    def test_perspective_required_for_reviews(self):
        ref = ArtifactReference.model_validate(artifact_reference("review-business"))
        assert ref.perspective == "business"
        with pytest.raises(ValidationError, match="perspective"):
            ArtifactReference.model_validate(artifact_reference("review-business", perspective="engineering"))
        with pytest.raises(ValidationError, match="perspective"):
            ArtifactReference.model_validate(artifact_reference("review-business", perspective=None))

    def test_non_review_types_reject_any_perspective(self):
        with pytest.raises(ValidationError, match="perspective"):
            ArtifactReference.model_validate(artifact_reference("synthesis", perspective="business"))

    @pytest.mark.parametrize(
        ("type_", "content_type"),
        [
            ("story", "text/markdown"),
            ("synthesis", "text/markdown"),
            ("report-md", "application/json"),
            ("report-pdf", "text/markdown"),
        ],
    )
    def test_content_type_must_match_type(self, type_, content_type):
        with pytest.raises(ValidationError, match="content_type"):
            ArtifactReference.model_validate(artifact_reference(type_, content_type=content_type))

    def test_artifact_record_internal(self):
        record = ArtifactRecord.model_validate(
            artifact_reference("story") | {"gcs_uri": "gs://bucket/story.json"}
        )
        assert record.gcs_uri.startswith("gs://")
        with pytest.raises(ValidationError):
            ArtifactRecord.model_validate(artifact_reference("story") | {"gcs_uri": "s3://nope"})


class TestSynthesisReport:
    def _synthesis(self, **overrides) -> SynthesisReport:
        payload = {
            "story_id": STORY_ID,
            "summary": "synthesis summary",
            "merged_findings": [finding(id="B-1"), finding(id="E-1")],
            "conflicts": [
                {
                    "id": "C-1",
                    "description": "conflicting non-functional needs",
                    "business_refs": ["B-1"],
                    "engineering_refs": ["E-1"],
                    "needs_po_clarification": True,
                }
            ],
            "inputs": {
                "business": artifact_reference("review-business"),
                "engineering": artifact_reference("review-engineering"),
            },
        }
        return SynthesisReport.model_validate(payload | overrides)

    def test_valid_synthesis(self):
        report = self._synthesis()
        assert set(report.inputs) == {"business", "engineering"}

    def test_missing_perspective_key_rejected(self):
        # A single key is rejected by the field constraint (dict min_length=2)
        # before the paired-input validator runs — spec-conformant either way.
        with pytest.raises(ValidationError, match="too_short|both perspective"):
            self._synthesis(inputs={"business": artifact_reference("review-business")})

    def test_wrong_reference_type_rejected(self):
        with pytest.raises(ValidationError, match="reference type"):
            self._synthesis(
                inputs={
                    "business": artifact_reference("review-engineering"),
                    "engineering": artifact_reference("review-engineering"),
                }
            )

    def test_cross_run_inputs_rejected(self):
        other_run = artifact_reference("review-engineering", story_run_id=OTHER_RUN_ID)
        with pytest.raises(ValidationError, match="one story run"):
            self._synthesis(
                inputs={"business": artifact_reference("review-business"), "engineering": other_run}
            )

    def test_conflict_refs_required(self):
        bad_conflict = {
            "id": "C-1",
            "description": "d",
            "business_refs": [],
            "engineering_refs": ["E-1"],
            "needs_po_clarification": False,
        }
        with pytest.raises(ValidationError):
            self._synthesis(conflicts=[bad_conflict])


class TestDelegationDecision:
    def test_defaults_and_valid_combinations(self):
        assert DelegationDecision.model_validate({}).invoke == "none"
        assert DelegationDecision.model_validate(
            {"invoke": "both", "extra_context": "extra"}
        ).invoke == "both"
        assert DelegationDecision.model_validate({"reuse_previous": True}).reuse_previous

    def test_reuse_previous_requires_invoke_none(self):
        with pytest.raises(ValidationError, match="reuse_previous"):
            DelegationDecision.model_validate({"reuse_previous": True, "invoke": "business"})

    def test_extra_context_requires_invocation(self):
        with pytest.raises(ValidationError, match="extra_context"):
            DelegationDecision.model_validate({"invoke": "none", "extra_context": "why"})


class TestFacilitatorTurnOutput:
    def _turn(self, **overrides) -> FacilitatorTurnOutput:
        payload = {
            "reply": "here is the facilitator reply",
            "delegation": {},
        }
        return FacilitatorTurnOutput.model_validate(payload | overrides)

    def test_plain_turn_valid(self):
        turn = self._turn()
        assert turn.delegation.invoke == "none"

    def test_reuse_only_turn_must_not_resolve(self):
        payload = {
            "reply": "r",
            "delegation": {"reuse_previous": True},
            "resolutions": [
                {"issue": "i", "disposition": "resolved", "explanation": "e"}
            ],
        }
        with pytest.raises(ValidationError, match="no resolution"):
            FacilitatorTurnOutput.model_validate(payload)

    def test_resolution_drafts_accepted_on_delegating_turns(self):
        turn = self._turn(
            delegation={"invoke": "both"},
            resolutions=[{"issue": "i", "disposition": "accepted", "explanation": "e"}],
        )
        assert isinstance(turn.resolutions[0], ResolutionDraft)

    def test_new_issues_describing_open_id_accepted(self):
        turn = self._turn(
            delegation={"open_issues": ["E-7"]},
            new_issues=[
                {"issue": "E-7", "title": "Perf", "description": "order < 5s"}
            ],
        )
        assert turn.new_issues[0].issue == "E-7"

    def test_new_issues_for_id_not_open_rejected(self):
        with pytest.raises(ValidationError, match="not on this turn's open list"):
            self._turn(
                delegation={"open_issues": ["B-1"]},
                new_issues=[
                    {"issue": "E-7", "title": "Perf", "description": "order < 5s"}
                ],
            )

    def test_duplicate_new_issues_rejected(self):
        with pytest.raises(ValidationError, match="unique"):
            self._turn(
                delegation={"open_issues": ["E-7"]},
                new_issues=[
                    {"issue": "E-7", "title": "a", "description": "d"},
                    {"issue": "E-7", "title": "b", "description": "d"},
                ],
            )

    def test_reuse_only_turn_must_not_mint_issues(self):
        with pytest.raises(ValidationError, match="no new issues"):
            self._turn(
                delegation={"reuse_previous": True, "open_issues": ["E-7"]},
                new_issues=[
                    {"issue": "E-7", "title": "a", "description": "d"}
                ],
            )


class TestFinalizedReview:
    def _finalized(self, **overrides) -> FinalizedReview:
        payload = {
            "story_id": STORY_ID,
            "story_run_id": RUN_ID,
            "synthesis_reference": artifact_reference("synthesis"),
            "resolutions": [
                {
                    "issue": "i",
                    "disposition": "resolved",
                    "explanation": "e",
                    "turn_number": 2,
                }
            ],
            "po_accepted": True,
            "final_turn_number": 3,
            "finalized_at": FIXED_TS,
        }
        merged = payload | overrides
        # D19: every referenced id gets a catalog entry by default; tests
        # that want the completeness failure strip the catalog explicitly
        ids = {r["issue"] for r in merged.get("resolutions", [])} | set(
            merged.get("remaining_open_issues", [])
        )
        merged.setdefault(
            "issues",
            [
                {
                    "issue": issue,
                    "title": f"title {issue}",
                    "description": "d",
                    "source": "synthesis",
                }
                for issue in ids
            ],
        )
        return FinalizedReview.model_validate(merged)

    def test_valid_finalized_review(self):
        final = self._finalized()
        assert isinstance(final.resolutions[0], ResolutionItem)

    def test_synthesis_reference_must_be_this_runs_synthesis(self):
        with pytest.raises(ValidationError, match="synthesis reference"):
            self._finalized(synthesis_reference=artifact_reference("story"))
        with pytest.raises(ValidationError, match="synthesis reference"):
            self._finalized(
                synthesis_reference=artifact_reference(
                    "synthesis", story_run_id=OTHER_RUN_ID
                )
            )

    def test_open_issues_require_po_acceptance(self):
        with pytest.raises(ValidationError, match="open issues"):
            self._finalized(po_accepted=False, remaining_open_issues=["one"])

    def test_reopened_disposition_accepted(self):
        final = self._finalized(
            resolutions=[
                {
                    "issue": "i",
                    "disposition": "resolved",
                    "explanation": "e",
                    "turn_number": 2,
                },
                {
                    "issue": "i",
                    "disposition": "reopened",
                    "explanation": "regressed",
                    "turn_number": 4,
                },
            ],
            remaining_open_issues=["i"],
        )
        assert final.resolutions[-1].disposition == "reopened"

    def test_remaining_open_contradicts_resolved_disposition(self):
        with pytest.raises(ValidationError, match="resolved/accepted"):
            self._finalized(remaining_open_issues=["i"])

    def test_remaining_open_contradicts_accepted_disposition(self):
        payload = {
            "story_id": STORY_ID,
            "story_run_id": RUN_ID,
            "synthesis_reference": artifact_reference("synthesis"),
            "resolutions": [
                {
                    "issue": "B-2",
                    "disposition": "accepted",
                    "explanation": "e",
                    "turn_number": 2,
                }
            ],
            "remaining_open_issues": ["B-2"],
            "po_accepted": True,
            "final_turn_number": 3,
            "finalized_at": FIXED_TS,
        }
        with pytest.raises(ValidationError, match="B-2"):
            FinalizedReview.model_validate(payload)

    def test_remaining_open_without_any_resolution_is_valid(self):
        final = self._finalized(
            resolutions=[], remaining_open_issues=["never-resolved"]
        )
        assert final.remaining_open_issues == ["never-resolved"]

    def _with_catalog(self, final: FinalizedReview) -> FinalizedReview:
        """Give every referenced id a catalog entry (D19 completeness)."""
        ids = {i.issue for i in final.resolutions} | set(final.remaining_open_issues)
        return final.model_copy(update={
            "issues": [
                IssueEntry(
                    issue=issue, title=f"title {issue}", description="d",
                    source="synthesis",
                )
                for issue in ids
            ]
        })

    def test_referenced_id_without_catalog_entry_rejected(self):
        payload = {
            "story_id": STORY_ID,
            "story_run_id": RUN_ID,
            "synthesis_reference": artifact_reference("synthesis"),
            "resolutions": [
                {
                    "issue": "i",
                    "disposition": "resolved",
                    "explanation": "e",
                    "turn_number": 2,
                }
            ],
            "po_accepted": True,
            "final_turn_number": 3,
            "finalized_at": FIXED_TS,
        }
        with pytest.raises(ValidationError, match="without a catalog entry"):
            FinalizedReview.model_validate(payload)

    def test_complete_catalog_accepted(self):
        final = self._finalized(
            resolutions=[
                {
                    "issue": "i",
                    "disposition": "resolved",
                    "explanation": "e",
                    "turn_number": 2,
                }
            ],
            remaining_open_issues=["E-7"],
        )
        validated = self._with_catalog(final)
        assert {e.issue for e in validated.issues} == {"i", "E-7"}

    def test_catalog_entries_without_references_are_allowed(self):
        # the catalog may describe issues never dispositioned nor listed
        final = self._with_catalog(self._finalized())
        extra = final.model_copy(update={
            "issues": [*final.issues, IssueEntry(
                issue="B-9", title="t", description="d",
                severity="major", source="facilitator",
            )]
        })
        assert "B-9" in {e.issue for e in extra.issues}

    def test_duplicate_catalog_entries_rejected(self):
        final = self._with_catalog(self._finalized())
        duplicated = final.model_copy(update={
            "issues": [*final.issues, final.issues[0]]
        })
        with pytest.raises(ValidationError, match="unique"):
            FinalizedReview.model_validate(duplicated.model_dump())


class TestLatestResolutions:
    """The shared latest-wins aggregation behind both the facilitator's
    decision state and FinalizedReview (D18): one implementation so turn
    context and the final report provably agree."""

    def _item(self, issue: str, disposition: str, turn: int) -> ResolutionItem:
        return ResolutionItem.model_validate(
            {
                "issue": issue,
                "disposition": disposition,
                "explanation": "e",
                "turn_number": turn,
            }
        )

    def test_latest_disposition_wins_in_first_seen_order(self):
        result = latest_resolutions(
            [
                self._item("A-1", "resolved", 2),
                self._item("B-1", "resolved", 2),
                self._item("A-1", "reopened", 4),
            ]
        )
        assert [(i.issue, i.disposition) for i in result] == [
            ("A-1", "reopened"),
            ("B-1", "resolved"),
        ]

    def test_empty_input_returns_empty_list(self):
        assert latest_resolutions([]) == []

    def test_single_occurrence_passes_through(self):
        items = [self._item("A-1", "unresolved", 3)]
        assert latest_resolutions(items) == items


class TestConversationSummary:
    def test_summary_with_references(self):
        summary = ConversationSummary.model_validate(
            {
                "story_id": STORY_ID,
                "story_run_id": RUN_ID,
                "summary": "conversation recap",
                "artifact_references": [artifact_reference("synthesis")],
            }
        )
        assert summary.decisions == []


class TestJudgeModels:
    def scores(self, values=(4, 4, 4, 3, 4)) -> list[dict]:
        dimensions = [
            "review-coverage",
            "grounding",
            "conflict-resolution",
            "delegation",
            "final-state",
        ]
        return [
            {"dimension": d, "score": v, "rationale": "why"}
            for d, v in zip(dimensions, values, strict=True)
        ]

    def _result(self, **overrides) -> dict:
        base = {
            "case_id": "case-01",
            "judge_model": "gemini-2.5-flash",
            "prompt_sha256": "ef" * 32,
            "scores": self.scores(),
            "comment": "overall fine",
            "passed": True,
        }
        return base | overrides

    def test_pass_rule_min_and_average(self):
        # min=3, avg=3.8 -> pass
        assert JudgeResult.model_validate(self._result()).passed is True
        # min=2 -> expected fail; declaring fail validates, declaring pass raises
        failing = self._result(scores=self.scores((2, 4, 4, 4, 4)), passed=False)
        assert JudgeResult.model_validate(failing).passed is False
        with pytest.raises(ValidationError, match="threshold"):
            JudgeResult.model_validate(self._result(scores=self.scores((2, 4, 4, 4, 4)), passed=True))
        # min ok but average < 3.5 -> expected fail; mismatch with passed=True raises
        avg_fail = self.scores((3, 3, 3, 3, 4))  # avg = 3.2
        assert JudgeResult.model_validate(self._result(scores=avg_fail, passed=False)).passed is False
        with pytest.raises(ValidationError, match="threshold"):
            JudgeResult.model_validate(self._result(scores=avg_fail, passed=True))

    def test_blocker_issue_forces_fail(self):
        with pytest.raises(ValidationError, match="threshold"):
            JudgeResult.model_validate(
                self._result(issues=[{"severity": "blocker", "message": "m"}], passed=True)
            )
        ok = JudgeResult.model_validate(
            self._result(issues=[{"severity": "major", "message": "m"}], passed=True)
        )
        assert isinstance(ok.issues[0], JudgeIssue)

    def test_duplicate_dimension_rejected(self):
        scores = self.scores()
        scores[1]["dimension"] = scores[0]["dimension"]
        with pytest.raises(ValidationError, match="exactly once"):
            JudgeResult.model_validate(self._result(scores=scores))

    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            JudgeDimensionScore.model_validate(
                {"dimension": "grounding", "score": 5, "rationale": "r"}
            )
