"""Tests for the orchestration-side facilitator turn-validation mirror
and the corrective re-prompt loop in the AE facilitator client (D34).

`ae_turn_validation` mirrors `agent_kit.facilitator_input.validate_turn_output`
over the duck-typed `FacilitatorInvocation` (identical field names); drift
between the two is pinned by `shared/agent_kit/tests/test_ae_turn_rule_mirrors.py`.
The corrective loop mirrors the local adapter's `turn_with_corrections`
(≤2 re-prompts, exhaustion → DELEGATION_VALIDATION).
"""

from __future__ import annotations

import pytest

from orchestration.ae_client import AgentCallFailure
from orchestration.ae_turn_validation import (
    TurnInvalid,
    corrective_message,
    validate_facilitator_turn,
)

from .test_ae_client import facilitator_invocation, turn_output_factory


class TestOpeningTurnFence:
    def test_minor_finding_resolution_passes(self) -> None:
        validate_facilitator_turn(
            turn_output_factory(resolutions=[{"issue": "B-1",
                                             "disposition": "resolved",
                                             "explanation": "info only"}]),
            facilitator_invocation(turn_number=1),
        )

    def test_invoke_not_none_fails(self) -> None:
        with pytest.raises(TurnInvalid, match="invoke"):
            validate_facilitator_turn(
                turn_output_factory(invoke="engineering"),
                facilitator_invocation(turn_number=1),
            )

    def test_conflict_or_major_resolution_fails(self) -> None:
        with pytest.raises(TurnInvalid, match="severity fence"):
            validate_facilitator_turn(
                turn_output_factory(resolutions=[{"issue": "C-9",
                                                 "disposition": "resolved",
                                                 "explanation": "too early"}]),
                facilitator_invocation(turn_number=1),
            )

    def test_accepted_disposition_fails(self) -> None:
        with pytest.raises(TurnInvalid, match="severity fence"):
            validate_facilitator_turn(
                turn_output_factory(resolutions=[{"issue": "B-1",
                                                 "disposition": "accepted",
                                                 "explanation": "no PO yet"}]),
                facilitator_invocation(turn_number=1),
            )


class TestLaterTurnRules:
    def test_valid_turn_two_passes(self) -> None:
        validate_facilitator_turn(
            turn_output_factory(invoke="engineering"),
            facilitator_invocation(turn_number=2, po_message="Re-check engineering."),
        )

    def test_minted_id_needs_descriptor(self) -> None:
        with pytest.raises(TurnInvalid, match="F-1"):
            validate_facilitator_turn(
                turn_output_factory(open_issues=["F-1"]),
                facilitator_invocation(turn_number=2, po_message="New concern."),
            )


class TestCorrectiveMessage:
    def test_carries_turn_marker_and_reasons(self) -> None:
        message = corrective_message("boom", turn_number=3)
        assert "This is turn 3" in message
        assert "boom" in message
        assert "FacilitatorTurnOutput" in message


class TestExhaustion:
    def test_client_raises_delegation_validation_after_two_corrections(
        self, monkeypatch
    ) -> None:
        import asyncio

        from orchestration.ae_client import AeFacilitatorClient
        from .test_ae_client import PostRecorder, SessionSeam, make_settings

        bad = turn_output_factory(resolutions=[{"issue": "C-9",
                                               "disposition": "resolved",
                                               "explanation": "too early"}])
        seam = PostRecorder(
            [(200, {"events": [{"author": "facilitator",
                                "content": {"parts": [
                                    {"text": bad.model_dump_json()}]}}]})
             for _ in range(3)]
        )
        client = AeFacilitatorClient(
            "projects/p/locations/e/reasoningEngines/1",
            "facilitator-abc1234",
            make_settings(),
            post=seam.post,
            sleeper=seam.sleep,
            rng=seam.rng,
            list_sessions=SessionSeam().list_sessions,
            create_session=SessionSeam().create_session,
            list_events=SessionSeam().list_events,
        )
        with pytest.raises(AgentCallFailure) as info:
            asyncio.run(client.invoke(facilitator_invocation(turn_number=1)))
        assert info.value.error.code == "DELEGATION_VALIDATION"
        # one initial turn + two corrective re-prompts
        assert len(seam.calls) == 3

    def test_client_corrects_and_counts(self, monkeypatch) -> None:
        import asyncio

        from orchestration.ae_client import AeFacilitatorClient
        from .test_ae_client import PostRecorder, SessionSeam, make_settings

        bad = turn_output_factory(resolutions=[{"issue": "C-9",
                                               "disposition": "resolved",
                                               "explanation": "too early"}])
        good = turn_output_factory()
        events = lambda out: {"events": [
            {"author": "facilitator", "content": {"parts": [
                {"text": out.model_dump_json()}]}}]}
        seam = PostRecorder([(200, events(bad)), (200, events(good))])
        client = AeFacilitatorClient(
            "projects/p/locations/e/reasoningEngines/1",
            "facilitator-abc1234",
            make_settings(),
            post=seam.post,
            sleeper=seam.sleep,
            rng=seam.rng,
            list_sessions=SessionSeam().list_sessions,
            create_session=SessionSeam().create_session,
            list_events=SessionSeam().list_events,
        )
        result = asyncio.run(client.invoke(facilitator_invocation(turn_number=1)))
        assert result.corrective_reprompts == 1
        assert seam.calls[1]["json"]["input"]["message"] != (
            seam.calls[0]["json"]["input"]["message"]
        )
