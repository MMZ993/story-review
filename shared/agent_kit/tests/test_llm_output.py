"""Tests for the serving-safe LLM-facing output mirror (D13 amendment 1).

Vertex AI rejects the strict ReviewReport schema for native structured
output (regex patterns, array length limits, bounded ints = "too many
states"). The mirror keeps the exact field names with plain types for the
serving-side constraint, while the shared strict model remains the sole
validation authority: every mirrored payload must still pass
ReviewReport.model_validate unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone

import json

import pytest
from pydantic import ValidationError

from agent_kit.llm_output import (
    MirrorArtifactReference,
    MirrorConflictItem,
    MirrorFinding,
    ServingSafeReviewReport,
    ServingSafeSynthesisReport,
)
from review_schemas import ArtifactReference, ReviewReport, SynthesisReport

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


# --- SynthesisReport mirror (Phase 5 increment 3) ---

REFERENCE = {
    "artifact_id": "art-00000000-0000-0000-0000-000000000001",
    "story_run_id": "run-00000000-0000-0000-0000-000000000001",
    "type": "review-business",
    "perspective": "business",
    "version": 1,
    "created_at": datetime(2026, 9, 12, 10, 0, 0, tzinfo=timezone.utc),
    "content_type": "application/json",
    "checksum_sha256": "0" * 64,
    "is_latest": True,
}

SYNTHESIS_VALID = {
    "story_id": "story-01",
    "summary": "Both reviews align; one merged gap remains.",
    "merged_findings": [],
    "conflicts": [
        {
            "id": "C-1",
            "description": "Business expects reservation; engineering captures immediately.",
            "business_refs": ["B-1"],
            "engineering_refs": ["E-1"],
            "needs_po_clarification": True,
        }
    ],
    "questions_for_po": ["Is payment captured or reserved at placement?"],
    "resolved_from_previous": [],
    "inputs": {
        "business": REFERENCE,
        "engineering": {
            **REFERENCE,
            "artifact_id": "art-00000000-0000-0000-0000-000000000002",
            "type": "review-engineering",
            "perspective": "engineering",
        },
    },
}


def json_payload() -> dict:
    """The payload as it appears on the wire (json mode): datetimes as strings."""
    return json.loads(json.dumps(SYNTHESIS_VALID, default=str))


def test_synthesis_mirror_accepts_the_canonical_shape_with_plain_types():
    mirror = ServingSafeSynthesisReport.model_validate(json_payload())
    assert mirror.conflicts[0].id == "C-1"
    assert isinstance(mirror.inputs.business.version, int)


def test_synthesis_mirror_payload_passes_the_strict_shared_model_unchanged():
    ServingSafeSynthesisReport.model_validate(json_payload())
    report = SynthesisReport.model_validate(SYNTHESIS_VALID)  # no coercion
    assert report.conflicts[0].needs_po_clarification is True


def test_synthesis_mirror_does_not_enforce_the_strict_rules():
    # Pattern violations stay unenforced in the mirror (serving-safe); the
    # min-1 conflict refs are deliberately enforced serving-side (minItems).
    bad = {
        **SYNTHESIS_VALID,
        "story_id": "wrong-format",
        "conflicts": [
            {**SYNTHESIS_VALID["conflicts"][0], "id": "wrong-format"}
        ],
    }
    ServingSafeSynthesisReport.model_validate(json.loads(json.dumps(bad, default=str)))
    with pytest.raises(ValidationError):
        SynthesisReport.model_validate(bad)


def test_synthesis_mirror_field_names_match_strict_model():
    assert set(ServingSafeSynthesisReport.model_fields) == set(
        SynthesisReport.model_fields
    )
    assert set(MirrorConflictItem.model_fields) == set(
        SynthesisReport.model_fields["conflicts"].annotation.__args__[0].model_fields
    )
    assert set(MirrorArtifactReference.model_fields) == set(
        ArtifactReference.model_fields
    )
