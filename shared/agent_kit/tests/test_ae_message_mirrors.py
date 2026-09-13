"""Renderer-equivalence tests: the orchestration AE mirrors must produce
byte-identical messages to the agent_kit input renderers (Phase 8
increment 4, D25).

The deployed Agent Engine agents receive exactly the messages the
agent_kit renderers produce; orchestration invokes them directly through
its own mirrors (`orchestration/orchestration/ae_messages.py`, duck-typed
over the identical field names). This suite is the drift guard: render
the same request both ways and assert equality. If a renderer changes in
agent_kit without its mirror, this fails.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

from agent_kit.facilitator_input import (
    DecisionState,
    FacilitatorRequest,
    render_facilitator_message,
)
from agent_kit.reviewer_input import ReviewerRequest, render_reviewer_message
from agent_kit.synthesis_input import (
    PerspectivePair,
    SynthesisRequest,
    render_synthesis_message,
)
from review_schemas import ArtifactReference, StoryDetail

_MIRROR_PATH = (
    Path(__file__).resolve().parents[3]
    / "orchestration"
    / "orchestration"
    / "ae_messages.py"
)


def _load_mirrors():
    spec = importlib.util.spec_from_file_location("ae_messages", _MIRROR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("ae_messages", module)
    spec.loader.exec_module(module)
    return module


mirror = _load_mirrors()


def _synthesis():
    from review_schemas import SynthesisReport

    return SynthesisReport(
        story_id="story-07",
        summary="Two findings need PO input.",
        merged_findings=[],
        conflicts=[],
        questions_for_po=["Which rate limit applies?"],
        inputs={
            "business": _ref(
                "art-00000000-0000-4000-8000-0000000000b1",
                "review-business",
                "business",
            ),
            "engineering": _ref(
                "art-00000000-0000-4000-8000-0000000000e1",
                "review-engineering",
                "engineering",
            ),
        },
    )


def _story() -> StoryDetail:
    return StoryDetail(
        story_id="story-07",
        title="Story 07",
        status="New",
        description="As a user I want a feature so that value flows.",
        acceptance_criteria=["Given a story when reviewed then findings appear."],
        epic_context="Epic 3 — reporting.",
        roadmap_context="Q3 reporting milestone.",
    )


def _ref(artifact_id: str, type_: str, perspective: str | None) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=artifact_id,
        story_run_id="run-00000000-0000-4000-8000-000000000001",
        type=type_,
        perspective=perspective,
        version=1,
        created_at=datetime.now(UTC),
        content_type="application/json",
        checksum_sha256="a" * 64,
    )


def _report(perspective: str):
    from review_schemas import ReviewReport

    prefix = "B-" if perspective == "business" else "E-"
    return ReviewReport(
        perspective=perspective,
        story_id="story-07",
        summary=f"{perspective} summary.",
        findings=[
            {
                "id": f"{prefix}1",
                "title": "Gap found",
                "description": "The story misses an important case.",
                "severity": "minor",
                "category": "completeness",
            }
        ],
        risks=[],
        questions_for_po=["Which rate limit applies?"],
    )


def test_reviewer_renderer_equivalent():
    request = ReviewerRequest(story=_story(), extra_context="Focus on retries.")
    assert mirror.render_reviewer_message(request) == render_reviewer_message(
        request
    )


def test_reviewer_renderer_equivalent_with_previous_review():
    request = ReviewerRequest(
        story=_story(), previous_review=_report("business")
    )
    assert mirror.render_reviewer_message(request) == render_reviewer_message(
        request
    )


def test_synthesis_renderer_equivalent():
    request = SynthesisRequest(
        business=PerspectivePair(
            report=_report("business"),
            reference=_ref(
                "art-00000000-0000-4000-8000-0000000000b1",
                "review-business",
                "business",
            ),
        ),
        engineering=PerspectivePair(
            report=_report("engineering"),
            reference=_ref(
                "art-00000000-0000-4000-8000-0000000000e1",
                "review-engineering",
                "engineering",
            ),
        ),
    )
    assert mirror.render_synthesis_message(request) == render_synthesis_message(
        request
    )


def test_facilitator_renderer_equivalent_opening_turn():
    request = FacilitatorRequest(
        session_id="sess-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        turn_number=1,
        invocation_id="00000000-0000-4000-8000-000000000001",
        synthesis_report=_synthesis(),
        synthesis_reference=_ref(
            "art-00000000-0000-4000-8000-000000000051", "synthesis", None
        ),
    )
    assert mirror.render_facilitator_message(
        request
    ) == render_facilitator_message(request)


def test_facilitator_renderer_equivalent_with_state_and_evidence():
    request = FacilitatorRequest(
        session_id="sess-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        turn_number=3,
        invocation_id="00000000-0000-4000-8000-000000000003",
        po_message="B-1 is resolved, keep E-1 open.",
        synthesis_report=_synthesis(),
        synthesis_reference=_ref(
            "art-00000000-0000-4000-8000-000000000051", "synthesis", None
        ),
        evidence_references=[
            _ref(
                "art-00000000-0000-4000-8000-0000000000b1",
                "review-business",
                "business",
            )
        ],
        decision_state=DecisionState(
            resolutions=[
                {
                    "issue": "B-1",
                    "disposition": "resolved",
                    "turn_number": 2,
                    "explanation": "PO confirmed the rate limit.",
                }
            ],
            open_issues=["E-1"],
        ),
    )
    assert mirror.render_facilitator_message(
        request
    ) == render_facilitator_message(request)
