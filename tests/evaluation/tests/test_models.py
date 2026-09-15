"""Unit tests for the suite-local JudgeResult models (Phase 9 increment 0).

Mirrors docs/design/schemas.md §JudgeResult: five dimensions scored 0–4,
the fixed pass rule (every dimension >= 3, mean >= 3.5, no blocker issue),
and `passed` must agree with the rule — a disagreeing payload is invalid.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from evaluation.models import (
    DIMENSIONS,
    JudgeDimensionScore,
    JudgeIssue,
    JudgeResult,
)


def score(dimension: str, value: int = 4) -> JudgeDimensionScore:
    return JudgeDimensionScore(dimension=dimension, score=value, rationale="ok")


def passing_result(**overrides) -> JudgeResult:
    payload = dict(
        case_id="clean-story-05",
        judge_model="gemini-2.5-pro",
        prompt_sha256="a" * 64,
        scores=[score(d) for d in DIMENSIONS],
        issues=[],
        comment="all good",
        passed=True,
    )
    payload.update(overrides)
    return JudgeResult(**payload)


def test_all_fours_with_no_blockers_passes():
    result = passing_result()
    assert result.passed is True


def test_pass_rule_enforced_when_passed_disagrees():
    with pytest.raises(ValidationError, match="passed does not match"):
        passing_result(
            scores=[score(d, 2 if d == "delegation" else 4) for d in DIMENSIONS],
        )


def test_mean_below_threshold_fails_even_with_all_threes():
    # all dimensions = 3 -> min is 3 but mean 3.0 < 3.5 -> passed must be False
    result = passing_result(
        scores=[score(d, 3) for d in DIMENSIONS], passed=False
    )
    assert result.passed is False
    with pytest.raises(ValidationError):
        passing_result(scores=[score(d, 3) for d in DIMENSIONS])


def test_blocker_issue_forces_failure():
    with pytest.raises(ValidationError):
        passing_result(
            issues=[JudgeIssue(severity="blocker", message="missed conflict")]
        )


def test_duplicate_dimension_rejected():
    scores = [score(d) for d in DIMENSIONS]
    scores[1] = score(DIMENSIONS[0])
    with pytest.raises(ValidationError, match="exactly once"):
        passing_result(scores=scores)


def test_missing_dimension_rejected_by_length():
    with pytest.raises(ValidationError):
        passing_result(scores=[score(d) for d in DIMENSIONS[:4]])


def test_score_out_of_range_rejected():
    with pytest.raises(ValidationError):
        score("grounding", 5)


def test_unknown_dimension_rejected():
    with pytest.raises(ValidationError):
        score("tone", 3)


def test_unknown_severity_rejected():
    with pytest.raises(ValidationError):
        JudgeIssue(severity="catastrophic", message="x")
