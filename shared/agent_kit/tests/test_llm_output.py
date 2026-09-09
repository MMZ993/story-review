"""Tests for the serving-safe LLM-facing output mirror (D13 amendment 1).

Vertex AI rejects the strict ReviewReport schema for native structured
output (regex patterns, array length limits, bounded ints = "too many
states"). The mirror keeps the exact field names with plain types for the
serving-side constraint, while the shared strict model remains the sole
validation authority: every mirrored payload must still pass
ReviewReport.model_validate unchanged.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_kit.llm_output import MirrorFinding, ServingSafeReviewReport
from review_schemas import ReviewReport

VALID = {
    "perspective": "business",
    "story_id": "story-01",
    "summary": "Solid, well-scoped business story.",
    "findings": [
        {
            "id": "B-1",
            "title": "Success metric missing",
            "description": "No measurable business outcome is stated.",
            "severity": "minor",
            "category": "business-justification",
            "suggestion": "State the target uptake or revenue effect.",
            "references_po_question": False,
        }
    ],
    "risks": ["Adoption risk if invoice format mismatches finance tools."],
    "questions_for_po": ["Which KPI proves this story succeeded?"],
    "based_on_extra_context": None,
    "previous_review_version": None,
}


def test_mirror_accepts_the_canonical_shape_with_plain_types():
    mirror = ServingSafeReviewReport.model_validate(VALID)
    assert mirror.findings[0].id == "B-1"
    assert isinstance(mirror.findings[0].severity, str)


def test_mirror_payload_passes_the_strict_shared_model_unchanged():
    ServingSafeReviewReport.model_validate(VALID)
    report = ReviewReport.model_validate(VALID)  # same payload, no coercion
    assert report.findings[0].severity == "minor"


def test_mirror_does_not_enforce_the_strict_rules():
    # pattern/bounds violations are accepted by the mirror…
    bad = {
        **VALID,
        "findings": [
            {**VALID["findings"][0], "id": "wrong-format", "severity": "huge"}
        ],
    }
    ServingSafeReviewReport.model_validate(bad)
    # …and rejected by the shared model — the validation authority.
    with pytest.raises(ValidationError):
        ReviewReport.model_validate(bad)


def test_finding_mirror_field_names_match_strict_model():
    strict_fields = set(ReviewReport.model_fields["findings"].annotation.__args__[0].model_fields)
    assert set(MirrorFinding.model_fields) == strict_fields


def test_report_mirror_field_names_match_strict_model():
    assert set(ServingSafeReviewReport.model_fields) == set(
        ReviewReport.model_fields
    )
