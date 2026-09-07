"""Judge models for offline evaluation of runs.

Implements the judge part of the domain section of docs/design/schemas.md:
`JudgeIssue`, `JudgeDimensionScore`, and `JudgeResult` with the fixed
pass-threshold rule (min >= 3, average >= 3.5, no blocker issue).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from review_schemas.base import Sha256, ShortText, StrictModel, Text


class JudgeIssue(StrictModel):
    """One problem the judge observed in an evaluated run."""

    severity: Literal["minor", "major", "blocker"]
    message: Text


class JudgeDimensionScore(StrictModel):
    """Score for one evaluation dimension on the 0–4 scale."""

    dimension: Literal[
        "review-coverage",
        "grounding",
        "conflict-resolution",
        "delegation",
        "final-state",
    ]
    score: Annotated[int, Field(ge=0, le=4)]
    rationale: Text


class JudgeResult(StrictModel):
    """Full judge verdict for one evaluation case."""

    case_id: ShortText
    judge_model: ShortText
    prompt_sha256: Sha256
    scores: list[JudgeDimensionScore] = Field(min_length=5, max_length=5)
    issues: list[JudgeIssue] = Field(default_factory=list, max_length=100)
    comment: Text
    passed: bool

    @model_validator(mode="after")
    def validate_pass_rule(self):
        dimensions = {item.dimension for item in self.scores}
        if len(dimensions) != 5:
            raise ValueError("every judge dimension must appear exactly once")
        score_values = [item.score for item in self.scores]
        expected_pass = (
            min(score_values) >= 3
            and sum(score_values) / len(score_values) >= 3.5
            and not any(issue.severity == "blocker" for issue in self.issues)
        )
        if self.passed != expected_pass:
            raise ValueError("passed does not match the fixed judge threshold")
        return self
