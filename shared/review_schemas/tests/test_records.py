"""Tests for the durable record models (review_schemas.records).

Covers the observable contracts from docs/design/schemas.md "Durable Cloud SQL
records": session completion requirements, final-review reference rules, turn
state machine fields, and agent-run attempt limits. SQL-level constraints are
out of scope (Phase 6); only the model validators are tested here.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from review_schemas.records import (
    AgentRunRecord,
    SessionRecord,
    StoryRunRecord,
    TurnLeaseRecord,
    TurnRecord,
)

from conftest import FIXED_TS, FIXED_UUID, RUN_ID, SESSION_ID, artifact_reference

STORY_ID = "story-05"
AGENT_RUN_ID = f"arun-12345678-90ab-4cda-b0de-1f2e3d4c5b6a"


class TestStoryRunAndLease:
    def test_story_run_record(self):
        record = StoryRunRecord.model_validate(
            {
                "story_run_id": RUN_ID,
                "story_id": STORY_ID,
                "state": "active",
                "created_at": FIXED_TS,
                "updated_at": FIXED_TS,
            }
        )
        assert record.state == "active"

    def test_lease_record(self):
        lease = TurnLeaseRecord.model_validate(
            {
                "session_id": SESSION_ID,
                "lease_token": FIXED_UUID,
                "acquired_at": FIXED_TS,
                "expires_at": FIXED_TS,
            }
        )
        assert lease.lease_token == FIXED_UUID


class TestSessionRecord:
    def _record(self, **overrides) -> SessionRecord:
        base = {
            "session_id": SESSION_ID,
            "story_run_id": RUN_ID,
            "story_id": STORY_ID,
            "state": "active",
            "requested_formats": ["md"],
            "created_at": FIXED_TS,
            "updated_at": FIXED_TS,
        }
        return SessionRecord.model_validate(base | overrides)

    def test_active_session_defaults(self):
        record = self._record()
        assert record.facilitator_turn_count == 0
        assert record.report_references == []

    def test_formats_must_be_unique(self):
        with pytest.raises(ValidationError, match="unique"):
            self._record(requested_formats=["md", "md"])

    def test_final_review_reference_must_belong_to_run(self):
        other_run = artifact_reference("finalized-review", story_run_id="run-ffffffff-90ab-4cda-b0de-1f2e3d4c5b6a")
        with pytest.raises(ValidationError, match="final review"):
            self._record(final_review_reference=other_run)
        with pytest.raises(ValidationError, match="final review"):
            self._record(final_review_reference=artifact_reference("synthesis"))

    def test_report_references_only_report_types(self):
        with pytest.raises(ValidationError, match="only report"):
            self._record(report_references=[artifact_reference("synthesis")])

    def test_report_reference_formats_must_be_unique(self):
        with pytest.raises(ValidationError, match="unique"):
            self._record(
                report_references=[
                    artifact_reference("report-md"),
                    artifact_reference("report-md"),
                ]
            )

    def test_completed_requires_final_review_and_all_formats(self):
        with pytest.raises(ValidationError, match="completed session requires"):
            self._record(state="completed")
        with pytest.raises(ValidationError, match="completed session requires"):
            self._record(
                state="completed",
                final_review_reference=artifact_reference("finalized-review"),
                report_references=[artifact_reference("report-md")],
                requested_formats=["md", "pdf"],
            )
        ok = self._record(
            state="completed",
            final_review_reference=artifact_reference("finalized-review"),
            report_references=[artifact_reference("report-md"), artifact_reference("report-pdf")],
            requested_formats=["md", "pdf"],
        )
        assert ok.state == "completed"


class TestTurnRecord:
    def _record(self, **overrides) -> TurnRecord:
        base = {
            "session_id": SESSION_ID,
            "turn_number": 2,
            "correlation_id": FIXED_UUID,
            "state": "pending",
            "po_message": "hello",
            "created_at": FIXED_TS,
        }
        return TurnRecord.model_validate(base | overrides)

    def test_pending_turn_valid(self):
        assert self._record().state == "pending"

    def test_po_action_rule_for_later_turns(self):
        for bad in ({"po_message": None, "po_accepted": False}, {"po_message": "m", "po_accepted": True}):
            with pytest.raises(ValidationError, match="exactly one"):
                self._record(**bad)

    def test_succeeded_requires_outcome_and_completion(self):
        with pytest.raises(ValidationError, match="outcome and completion"):
            self._record(state="succeeded")
        ok = self._record(state="succeeded", outcome="continue", completed_at=FIXED_TS)
        assert ok.outcome == "continue"


class TestAgentRunRecord:
    def _record(self, **overrides) -> AgentRunRecord:
        base = {
            "agent_run_id": AGENT_RUN_ID,
            "agent": "business-reviewer",
            "agent_version": "1.0.0",
            "prompt_sha256": "ab" * 32,
            "story_run_id": RUN_ID,
            "correlation_id": FIXED_UUID,
            "started_at": FIXED_TS,
        }
        return AgentRunRecord.model_validate(base | overrides)

    def test_defaults(self):
        record = self._record()
        assert record.state == "pending"
        assert record.transport_attempts == 0

    def test_facilitator_transport_limit(self):
        assert self._record(agent="facilitator", transport_attempts=2).transport_attempts == 2
        with pytest.raises(ValidationError, match="two transport"):
            self._record(agent="facilitator", transport_attempts=3)

    def test_corrective_reprompts_only_for_facilitator(self):
        assert self._record(agent="facilitator", corrective_reprompts=2).corrective_reprompts == 2
        with pytest.raises(ValidationError, match="facilitator"):
            self._record(corrective_reprompts=1)

    def test_finished_states_require_finished_at(self):
        for state in ("succeeded", "failed"):
            with pytest.raises(ValidationError, match="finished_at"):
                self._record(state=state)
            assert self._record(state=state, finished_at=FIXED_TS).state == state
