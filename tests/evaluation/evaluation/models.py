"""Suite-local judge result models (Phase 9 evaluation suite).

Mirrors `docs/design/schemas.md` §JudgeResult exactly (five dimensions
scored 0–4, the fixed pass rule). Kept suite-local per the Phase 9 plan:
no other unit consumes JudgeResult today; if that changes it moves to
`shared/review_schemas` unchanged.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

DIMENSIONS = (
    "review-coverage",
    "grounding",
    "conflict-resolution",
    "delegation",
    "final-state",
)

Dimension = Literal[
    "review-coverage",
    "grounding",
    "conflict-resolution",
    "delegation",
    "final-state",
]


class JudgeIssue(BaseModel):
    """One judge-identified problem with the evaluated case behavior."""

    severity: Literal["minor", "major", "blocker"]
    message: str


class JudgeDimensionScore(BaseModel):
    """A 0–4 score for one evaluation dimension, with rationale."""

    dimension: Dimension
    score: int = Field(ge=0, le=4)
    rationale: str


class JudgeResult(BaseModel):
    """The judge's typed verdict for one case (strict JSON contract).

    `passed` must agree with the fixed threshold: every dimension >= 3,
    arithmetic mean >= 3.5, and no blocker-severity issue.
    """

    case_id: str
    judge_model: str
    prompt_sha256: str
    scores: list[JudgeDimensionScore] = Field(min_length=5, max_length=5)
    issues: list[JudgeIssue] = Field(default_factory=list, max_length=100)
    comment: str
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
