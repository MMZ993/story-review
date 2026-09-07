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
    ResolutionDraft,
    ResolutionItem,
)
from review_schemas.judge import JudgeDimensionScore, JudgeIssue, JudgeResult
from review_schemas.review import Finding, ReviewReport, StoryDetail, StorySummary
from review_schemas.synthesis import (
    ArtifactRecord,
    ArtifactReference,
    ConflictItem,
    SynthesisReport,
)

from conftest import FIXED_TS, FIXED_UUID, RUN_ID, UUID_STR

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


def artifact_reference(type_: str, **overrides) -> dict:
    """A valid ArtifactReference payload for the given artifact type."""
    perspectives = {"review-business": "business", "review-engineering": "engineering"}
    content_types = {
        "story": "application/json",
        "review-business": "application/json",
        "review-engineering": "application/json",
        "synthesis": "application/json",
        "finalized-review": "application/json",
        "report-md": "text/markdown",
        "report-pdf": "application/pdf",
    }
    base = {
        "artifact_id": f"art-{UUID_STR}",
        "story_run_id": RUN_ID,
        "type": type_,
        "version": 1,
        "created_at": FIXED_TS,
        "content_type": content_types[type_],
        "checksum_sha256": "cd" * 32,
    }
    if type_ in perspectives:
        base["perspective"] = perspectives[type_]
    return base | overrides


class TestStoryModels:
    def test_summary_and_detail(self):
        summary = StorySummary.model_validate(
            {"story_id": STORY_ID, "title": "Payments retry", "status": "ready", "quality_class": "B"}
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

    def test_detail_rejects_extra_fields(self):
        payload = {
            "story_id": STORY_ID,
            "title": "t",
            "status": "s",
            "quality_class": "q",
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
        return FinalizedReview.model_validate(payload | overrides)

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
