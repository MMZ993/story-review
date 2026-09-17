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
    DecisionState,
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
    turn_number: int = 1,
    po_message: str | None = None,
    decision_state: DecisionState | None = None,
) -> FacilitatorRequest:
    return FacilitatorRequest(
        session_id=SESSION,
        turn_number=turn_number,
        invocation_id=uuid.uuid4(),
        po_message=po_message,
        synthesis_report=synth_report(),
        synthesis_reference=synth_reference(),
        evidence_references=[review_reference("business"), review_reference("engineering")],
        decision_state=decision_state,
    )


def decision_state() -> DecisionState:
    """Two resolved issues and one still open (D18 input fixture)."""
    return DecisionState(
        resolutions=[
            {
                "issue": "B-1",
                "disposition": "resolved",
                "explanation": "PO clarified tokens",
                "turn_number": 2,
            },
            {
                "issue": "B-2",
                "disposition": "accepted",
                "explanation": "accepted as is",
                "turn_number": 2,
            },
        ],
        open_issues=["C-1"],
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

    def test_decision_state_optional_and_accepted(self) -> None:
        assert request().decision_state is None
        req = request(turn_number=3, po_message="msg", decision_state=decision_state())
        assert req.decision_state is not None
        assert req.decision_state.resolutions[0].issue == "B-1"

    def test_decision_state_reopened_disposition_accepted(self) -> None:
        state = decision_state()
        state = state.model_copy(deep=True)
        state.resolutions[0] = state.resolutions[0].model_copy(
            update={"disposition": "reopened"}
        )
        assert state.resolutions[0].disposition == "reopened"


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

    def test_decision_state_rendered_when_present(self) -> None:
        message = render_facilitator_message(
            request(
                turn_number=3,
                po_message="Actually the metric is still missing.",
                decision_state=decision_state(),
            )
        )
        assert "Current decision state" in message
        assert "B-1" in message and "resolved" in message
        assert "B-2" in message and "accepted" in message
        assert "C-1" in message

    def test_no_decision_state_section_when_absent(self) -> None:
        assert "decision state" not in render_facilitator_message(request()).lower()


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

    def test_opening_turn_resolves_minor_finding(self) -> None:
        from review_schemas import ResolutionDraft

        output = FacilitatorTurnOutput(
            reply="r",
            delegation={"invoke": "none", "open_issues": ["C-1"]},  # type: ignore[arg-type]
            resolutions=[
                ResolutionDraft(
                    issue="B-2", disposition="resolved", explanation="informational"
                )
            ],
        )
        validate_turn_output(output, request(turn_number=1))

    def test_opening_turn_forbids_conflict_resolutions(self) -> None:
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
        with pytest.raises(FacilitatorTurnInvalid, match="severity fence"):
            validate_turn_output(output, request(turn_number=1))

    def test_opening_turn_forbids_major_finding_resolutions(self) -> None:
        from review_schemas import ResolutionDraft

        report = synth_report().model_copy(deep=True)
        report.merged_findings[0].severity = "major"
        req = FacilitatorRequest(
            session_id=SESSION,
            turn_number=1,
            invocation_id=uuid.uuid4(),
            synthesis_report=report,
            synthesis_reference=synth_reference(),
        )
        output = FacilitatorTurnOutput(
            reply="r",
            delegation={"invoke": "none", "open_issues": []},  # type: ignore[arg-type]
            resolutions=[
                ResolutionDraft(
                    issue="B-2", disposition="resolved", explanation="too early"
                )
            ],
        )
        with pytest.raises(FacilitatorTurnInvalid, match="severity fence"):
            validate_turn_output(output, req)

    def test_opening_turn_forbids_accepted_dispositions(self) -> None:
        from review_schemas import ResolutionDraft

        output = FacilitatorTurnOutput(
            reply="r",
            delegation={"invoke": "none", "open_issues": ["C-1"]},  # type: ignore[arg-type]
            resolutions=[
                ResolutionDraft(
                    issue="B-2", disposition="accepted", explanation="no PO yet"
                )
            ],
        )
        with pytest.raises(FacilitatorTurnInvalid, match="severity fence"):
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


class TestIdentifierLifecycleRule:
    """D18 turn-context rule: a resolved/accepted id reappearing in
    open_issues must be re-opened with `reopened` on the same turn."""

    def _request(self, state: DecisionState | None):
        return request(
            turn_number=3, po_message="New concern came up.", decision_state=state
        )

    def test_reused_resolved_id_requires_reopened(self) -> None:
        output = turn_output(open_issues=["B-1", "C-1"])
        with pytest.raises(FacilitatorTurnInvalid, match="B-1.*reopened"):
            validate_turn_output(output, self._request(decision_state()))

    def test_reused_accepted_id_requires_reopened(self) -> None:
        output = turn_output(open_issues=["B-2"])
        with pytest.raises(FacilitatorTurnInvalid, match="B-2.*reopened"):
            validate_turn_output(output, self._request(decision_state()))

    def test_reopened_draft_on_same_turn_passes(self) -> None:
        from review_schemas import ResolutionDraft

        output = FacilitatorTurnOutput(
            reply="r",
            delegation={"invoke": "none", "open_issues": ["B-1", "C-1"]},  # type: ignore[arg-type]
            resolutions=[
                ResolutionDraft(
                    issue="B-1", disposition="reopened", explanation="regressed"
                )
            ],
        )
        validate_turn_output(output, self._request(decision_state()))

    def test_already_reopened_id_staying_open_passes_without_new_draft(self) -> None:
        state = decision_state().model_copy(deep=True)
        state.resolutions[0] = state.resolutions[0].model_copy(
            update={"disposition": "reopened", "explanation": "regressed at turn 2"}
        )
        output = turn_output(open_issues=["B-1", "C-1"])
        validate_turn_output(output, self._request(state))

    def test_unresolved_ids_in_open_list_pass(self) -> None:
        output = turn_output(open_issues=["C-1"])
        validate_turn_output(output, self._request(decision_state()))

    def test_no_decision_state_skips_rule(self) -> None:
        # B-2 is synthesis-born, so no rule applies without decision state
        output = turn_output(open_issues=["B-2"])
        validate_turn_output(output, self._request(None))

    def test_same_turn_resolved_id_still_open_is_rejected(self) -> None:
        from review_schemas import ResolutionDraft

        output = FacilitatorTurnOutput(
            reply="r",
            delegation={"invoke": "none", "open_issues": ["X"]},  # type: ignore[arg-type]
            resolutions=[
                ResolutionDraft(
                    issue="X", disposition="resolved", explanation="done"
                )
            ],
        )
        with pytest.raises(FacilitatorTurnInvalid, match="X.*open_issues"):
            validate_turn_output(output, self._request(decision_state()))

    def test_same_turn_resolved_id_not_open_passes(self) -> None:
        from review_schemas import ResolutionDraft

        output = FacilitatorTurnOutput(
            reply="r",
            delegation={"invoke": "none", "open_issues": ["C-1"]},  # type: ignore[arg-type]
            resolutions=[
                ResolutionDraft(
                    issue="X", disposition="resolved", explanation="done"
                )
            ],
        )
        validate_turn_output(output, self._request(decision_state()))


class TestIssueDescriptorRule:
    """D19 turn-context rule: an id the facilitator mints (not in the
    synthesis findings/conflicts, not previously seen) must carry an
    IssueDraft on the same turn it first appears in open_issues."""

    def _request(self, state: DecisionState | None):
        return request(
            turn_number=3, po_message="New concern came up.", decision_state=state
        )

    def test_minted_id_without_descriptor_rejected(self) -> None:
        output = turn_output(open_issues=["C-1", "F-1"])
        # D19 amendment: the rejection must carry the inline JSON shape so
        # the corrective re-prompt shows the model exactly what to emit.
        with pytest.raises(
            FacilitatorTurnInvalid,
            match=r'issue F-1 is newly minted.*"new_issues": '
            r'\[\{"issue": "F-1", "title": "\.\.\.", '
            r'"description": "\.\.\."\}\]',
        ):
            validate_turn_output(output, self._request(decision_state()))

    def test_minted_id_with_descriptor_passes(self) -> None:
        from review_schemas import IssueDraft

        output = FacilitatorTurnOutput(
            reply="r",
            delegation={"invoke": "none", "open_issues": ["C-1", "F-1"]},  # type: ignore[arg-type]
            new_issues=[
                IssueDraft(issue="F-1", title="Fraud", description="chargeback flow undefined")
            ],
        )
        validate_turn_output(output, self._request(decision_state()))

    def test_synthesis_born_id_needs_no_descriptor(self) -> None:
        # B-2 is in the request's synthesis merged_findings and carries no
        # decision-state disposition (fresh synthesis-born open id)
        state = decision_state().model_copy(
            update={"resolutions": [decision_state().resolutions[0]]}
        )
        output = turn_output(open_issues=["B-2"])
        validate_turn_output(output, self._request(state))

    def test_previously_minted_id_relisted_needs_no_new_descriptor(self) -> None:
        state = decision_state().model_copy(deep=True)
        state = state.model_copy(update={"open_issues": ["F-1"]})
        output = turn_output(open_issues=["F-1"])
        validate_turn_output(output, self._request(state))

    def test_opening_turn_minted_id_requires_descriptor(self) -> None:
        output = turn_output(open_issues=["B-2", "F-1"])
        with pytest.raises(FacilitatorTurnInvalid, match="F-1"):
            validate_turn_output(output, request(turn_number=1))


class TestResponse:
    def test_response_carries_counters(self) -> None:
        resp = FacilitatorResponse(
            output=turn_output(),
            agent_version="0.1.0",
            prompt_sha256=load_prompt("facilitator", prompts_dir=PROMPTS).sha256,
            corrective_reprompts=1,
        )
        assert resp.corrective_reprompts == 1
