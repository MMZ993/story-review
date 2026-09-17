"""Validator-equivalence tests: the orchestration AE mirror must accept
and reject exactly what `agent_kit.facilitator_input.validate_turn_output`
does (D34).

Orchestration cannot import `agent_kit` (its package `__init__` drags the
ADK), so the AE-side corrective loop validates through a duck-typed mirror
(`orchestration/orchestration/ae_turn_validation.py`). This suite is the
drift guard, same pattern as the renderer mirrors: for a battery of
(request, output) pairs — valid and rule-violating — both validators must
agree on the verdict and on the human-readable reason text (the reason is
the corrective re-prompt body; divergent text would mean divergent agent
behavior on the two paths).
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest

from agent_kit.facilitator_input import (
    FacilitatorTurnInvalid,
    validate_turn_output,
)
from review_schemas import FacilitatorTurnOutput, ResolutionDraft

from test_facilitator_input import decision_state, request

_MIRROR_PATH = (
    Path(__file__).resolve().parents[3]
    / "orchestration"
    / "orchestration"
    / "ae_turn_validation.py"
)


def _load_mirror():
    spec = importlib.util.spec_from_file_location("ae_turn_validation", _MIRROR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("ae_turn_validation", module)
    spec.loader.exec_module(module)
    return module


mirror = _load_mirror()


def _verdict(validator, output, req):
    try:
        validator(output, req)
        return None
    except Exception as exc:  # FacilitatorTurnInvalid / mirror TurnInvalid
        return str(exc)


def _out(resolutions=None, **delegation) -> FacilitatorTurnOutput:
    base = {"invoke": "none", "reuse_previous": False, "open_issues": ["C-1"],
            "readiness": "needs_work"}
    base.update(delegation)
    return FacilitatorTurnOutput(
        reply="r",
        delegation=base,  # type: ignore[arg-type]
        resolutions=[
            ResolutionDraft.model_validate(r) for r in (resolutions or [])
        ],
    )


def _request_major():
    """Turn-1 request whose synthesis carries a major B-2 (fence should
    reject a turn-1 resolution of it)."""
    from agent_kit.facilitator_input import FacilitatorRequest

    report = request(turn_number=1).synthesis_report.model_copy(deep=True)
    report.merged_findings[0].severity = "major"
    base = request(turn_number=1)
    return FacilitatorRequest(
        session_id=base.session_id,
        turn_number=1,
        invocation_id=base.invocation_id,
        synthesis_report=report,
        synthesis_reference=base.synthesis_reference,
        evidence_references=base.evidence_references,
    )


def _cases():
    """(label, output, request) pairs covering every mirrored rule."""
    return [
        ("opening_invoke_none_ok", _out(), request(turn_number=1)),
        ("opening_minor_resolved_ok",
         _out(resolutions=[{"issue": "B-2", "disposition": "resolved",
                            "explanation": "info"}]),
         request(turn_number=1)),
        ("opening_invoke_violation", _out(invoke="engineering"),
         request(turn_number=1)),
        ("opening_fence_conflict",
         _out(resolutions=[{"issue": "C-1", "disposition": "resolved",
                            "explanation": "x"}]),
         request(turn_number=1)),
        ("opening_fence_major_finding",
         _out(resolutions=[{"issue": "B-2", "disposition": "resolved",
                            "explanation": "x"}]),
         _request_major()),
        ("opening_fence_reopened_disposition",
         _out(resolutions=[{"issue": "B-2", "disposition": "reopened",
                            "explanation": "x"}]),
         request(turn_number=1)),
        ("opening_fence_minted_id",
         _out(resolutions=[{"issue": "F-9", "disposition": "resolved",
                            "explanation": "x"}]),
         request(turn_number=1)),
        ("opening_fence_accepted",
         _out(resolutions=[{"issue": "B-2", "disposition": "accepted",
                            "explanation": "x"}]),
         request(turn_number=1)),
        ("later_valid", _out(invoke="engineering"),
         request(turn_number=2, po_message="Use PSP tokens.")),
        ("later_resolution_of_conflict_ok",
         _out(open_issues=[], resolutions=[{"issue": "C-1",
                                            "disposition": "resolved",
                                            "explanation": "decided"}]),
         request(turn_number=2, po_message="Use PSP tokens.")),
        ("later_minted_undescribed", _out(open_issues=["F-1"]),
         request(turn_number=2, po_message="New concern.")),
        ("reused_resolved_id", _out(open_issues=["B-1"]),
         request(turn_number=3, po_message="Again.",
                 decision_state=decision_state())),
        ("reused_resolved_id_reopened_ok",
         _out(open_issues=["B-1"], resolutions=[
             {"issue": "B-1", "disposition": "reopened",
              "explanation": "regressed"}]),
         request(turn_number=3, po_message="Again.",
                 decision_state=decision_state())),
        ("settled_and_still_open",
         _out(open_issues=["B-1"], resolutions=[
             {"issue": "B-1", "disposition": "resolved",
              "explanation": "done"}]),
         request(turn_number=3, po_message="Again.",
                 decision_state=decision_state())),
    ]


@pytest.mark.parametrize("label,output,req", _cases(), ids=[c[0] for c in _cases()])
def test_mirror_agrees_with_agent_kit(label, output, req):
    assert _verdict(validate_turn_output, output, req) == _verdict(
        mirror.validate_facilitator_turn, output, req
    )
