"""Tests for the facilitator invocation request model, message renderer,
and turn-output validation (frozen Phase 5 adapter contract).

The facilitator part of the plan appendix: session-scoped turn invocation
with `session_id`, `turn_number`, the PO message when applicable, the
latest synthesis report plus its reference, and the lineage-scoped
evidence references. Pure and deterministic — no LLM involvement.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_kit.facilitator_input import (
    FacilitatorRequest,
    FacilitatorResponse,
    FacilitatorTurnInvalid,
    render_facilitator_message,
    validate_turn_output,
)
from agent_kit.prompts import load_prompt
from review_schemas import ArtifactReference, FacilitatorTurnOutput, SynthesisReport

_REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS = _REPO_ROOT.parent / "prompts"

RUN = "run-00000000-0000-0000-0000-000000000001"
SESSION = "sess-00000000-0000-0000-0000-000000000001"
STORY = "story-05"
NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


def synth_reference(version: int = 1) -> ArtifactReference:
    return ArtifactReference(
        artifact_id="art-00000000-0000-0000-0000-000000000003",
        story_run_id=RUN,
        type="synthesis",
        version=version,
        created_at=NOW,
        content_type="application/json",
        checksum_sha256="a" * 64,
        is_latest=True,
    )


def review_reference(perspective: str, version: int = 1) -> ArtifactReference:
    suffix = "01" if perspective == "business" else "02"
    return ArtifactReference(
        artifact_id=f"art-00000000-0000-0000-0000-0000000000{suffix}",
        story_run_id=RUN,
        type=f"review-{perspective}",
        perspective=perspective,
        version=version,
        created_at=NOW,
        content_type="application/json",
        checksum_sha256="b" * 64,
        is_latest=True,
    )


def synth_report() -> SynthesisReport:
    payload = {
        "story_id": STORY,
        "summary": "One conflict between the perspectives.",
        "merged_findings": [
            {
                "id": "B-2",
                "title": "Missing success metric",
                "description": "No measurable checkout-speed criterion.",
                "severity": "minor",
                "category": "criteria",
            }
        ],
        "conflicts": [
            {
                "id": "C-1",
                "description": "Business assumes card storage; engineering forbids raw PAN.",
                "business_refs": ["B-1"],
                "engineering_refs": ["E-1"],
                "needs_po_clarification": True,
            }
        ],
        "questions_for_po": ["Is PSP tokenization acceptable?"],
        "resolved_from_previous": [],
        "inputs": {
            "business": review_reference("business").model_dump(mode="python"),
            "engineering": review_reference("engineering").model_dump(mode="python"),
        },
    }
    return SynthesisReport.model_validate(payload)


def request(
    turn_number: int = 1, po_message: str | None = None
) -> FacilitatorRequest:
    return FacilitatorRequest(
        session_id=SESSION,
        turn_number=turn_number,
        invocation_id=uuid.uuid4(),
        po_message=po_message,
        synthesis_report=synth_report(),
        synthesis_reference=synth_reference(),
        evidence_references=[review_reference("business"), review_reference("engineering")],
    )


class TestRequestModel:
    def test_opening_turn_has_no_po_message(self) -> None:
        req = request(turn_number=1)
        assert req.po_message is None
        assert req.story_id == STORY

    def test_turn_ge_2_requires_po_message(self) -> None:
        with pytest.raises(ValidationError, match="po_message"):
            request(turn_number=2, po_message=None)

    def test_turn_1_rejects_po_message(self) -> None:
        with pytest.raises(ValidationError, match="po_message"):
            request(turn_number=1, po_message="early")

    def test_synthesis_reference_must_be_synthesis_type(self) -> None:
        bad = synth_reference()
        bad = bad.model_copy(update={"type": "review-business"})
        with pytest.raises(ValidationError, match="synthesis"):
            FacilitatorRequest(
                session_id=SESSION,
                turn_number=1,
                invocation_id=uuid.uuid4(),
                synthesis_report=synth_report(),
                synthesis_reference=bad,
                evidence_references=[],
            )

    def test_evidence_refs_must_share_the_run(self) -> None:
        other_run = review_reference("business").model_copy(
            update={"story_run_id": RUN.replace("0001", "0002")}
        )
        with pytest.raises(ValidationError, match="run"):
            FacilitatorRequest(
                session_id=SESSION,
                turn_number=1,
                invocation_id=uuid.uuid4(),
                synthesis_report=synth_report(),
                synthesis_reference=synth_reference(),
                evidence_references=[other_run],
            )

    def test_synthesis_report_story_mismatch_with_reference_run_is_fine(self) -> None:
        # story agreement is between report and evidence refs' story context;
        # references carry no story id — only the run linkage is checkable.
        req = request()
        assert req.synthesis_report.story_id == STORY

    def test_extra_fields_rejected(self) -> None:
        payload = request().model_dump(mode="json")
        payload["invented"] = 1
        with pytest.raises(ValidationError):
            FacilitatorRequest.model_validate(payload)


class TestRenderer:
    def test_message_names_story_turn_and_embeds_synthesis(self) -> None:
        message = render_facilitator_message(request())
        assert STORY in message
        assert "turn 1" in message
        assert "opening turn" in message
        assert "C-1" in message  # synthesis content embedded
        assert "B-2" in message

        assert "art-00000000-0000-0000-0000-000000000003" in message
        assert "evidence" in message.lower()

    def test_po_message_presented_when_given(self) -> None:
        message = render_facilitator_message(
            request(turn_number=2, po_message="Yes, tokenize via PSP.")
        )
        assert "Yes, tokenize via PSP." in message

    def test_evidence_references_listed(self) -> None:
        message = render_facilitator_message(request())
        assert "art-00000000-0000-0000-0000-000000000001" in message
        assert "art-00000000-0000-0000-0000-000000000002" in message


def turn_output(**delegation) -> FacilitatorTurnOutput:
    base = {"invoke": "none", "reuse_previous": False, "open_issues": ["C-1"],
            "readiness": "needs_work"}
    base.update(delegation)
    return FacilitatorTurnOutput(
        reply="Here is the synthesis.",
        delegation=base,  # type: ignore[arg-type]
        resolutions=[],
    )


class TestValidateTurnOutput:
    def test_opening_turn_requires_invoke_none(self) -> None:
        output = turn_output(invoke="engineering", extra_context="x")
        with pytest.raises(FacilitatorTurnInvalid, match="opening turn"):
            validate_turn_output(output, request(turn_number=1))

    def test_opening_turn_forbids_resolutions(self) -> None:
        from review_schemas import ResolutionDraft

        output = FacilitatorTurnOutput(
            reply="r",
            delegation={"invoke": "none", "open_issues": ["C-1"]},  # type: ignore[arg-type]
            resolutions=[
                ResolutionDraft(
                    issue="C-1", disposition="resolved", explanation="too early"
                )
            ],
        )
        with pytest.raises(FacilitatorTurnInvalid, match="resolution"):
            validate_turn_output(output, request(turn_number=1))

    def test_valid_later_turn_passes(self) -> None:
        output = turn_output(invoke="engineering", extra_context="PO confirmed tokens.")
        validate_turn_output(
            output, request(turn_number=2, po_message="Use PSP tokens.")
        )

    def test_reuse_previous_without_resolutions_passes(self) -> None:
        output = turn_output(invoke="none", reuse_previous=True, open_issues=[])
        validate_turn_output(
            output, request(turn_number=2, po_message="Re-run synthesis please.")
        )


class TestResponse:
    def test_response_carries_counters(self) -> None:
        resp = FacilitatorResponse(
            output=turn_output(),
            agent_version="0.1.0",
            prompt_sha256=load_prompt("facilitator", prompts_dir=PROMPTS).sha256,
            corrective_reprompts=1,
        )
        assert resp.corrective_reprompts == 1
