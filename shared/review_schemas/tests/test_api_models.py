"""Tests for the HTTP API model group (review_schemas.api).

Covers the observable contracts from docs/design/schemas.md "HTTP API models":
unique requested formats, exact-one turn action, outcome/state alignment,
report/reference rules, completion requirements, and health models. Header
parameters (correlation/idempotency) are FastAPI-level, not body fields —
tested indirectly via the body contracts that use the same primitives.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from review_schemas.api import (
    AbandonSessionResponse,
    CanonicalReportResult,
    CanonicalTurnResult,
    CreateSessionRequest,
    CreateSessionResponse,
    FinalizeRequest,
    HealthDependency,
    HealthResponse,
    ListSessionsQuery,
    ListSessionsResponse,
    ListStoriesQuery,
    ListStoriesResponse,
    ReportDownload,
    ReportResponse,
    SessionDetail,
    SessionSummary,
    TurnRequest,
    TurnResponse,
    TurnView,
)
from review_schemas.review import StorySummary

from conftest import FIXED_TS, RUN_ID, SESSION_ID, artifact_reference

STORY_ID = "story-03"


def report_download(format_: str) -> dict:
    return {
        "reference": artifact_reference(f"report-{format_}"),
        "format": format_,
        "signed_url": "https://storage.example.com/report",
        "expires_at": FIXED_TS,
    }


class TestQueryAndPathModels:
    def test_list_models_defaults(self):
        assert ListStoriesQuery.model_validate({}).filter is None
        assert ListStoriesResponse.model_validate({}).stories == []
        assert ListSessionsQuery.model_validate({}).limit == 50
        assert ListSessionsResponse.model_validate({}).next_cursor is None

    def test_limit_bounds(self):
        assert ListSessionsQuery.model_validate({"limit": 1}).limit == 1
        with pytest.raises(ValidationError):
            ListSessionsQuery.model_validate({"limit": 101})

    def test_story_summary_list(self):
        response = ListStoriesResponse.model_validate(
            {"stories": [{"story_id": STORY_ID, "title": "t", "status": "s"}]}
        )
        assert isinstance(response.stories[0], StorySummary)


class TestCreateSession:
    def test_request_formats_must_be_unique(self):
        assert CreateSessionRequest.model_validate(
            {"story_id": STORY_ID, "requested_formats": ["md", "pdf"]}
        ).requested_formats == ["md", "pdf"]
        with pytest.raises(ValidationError, match="unique"):
            CreateSessionRequest.model_validate(
                {"story_id": STORY_ID, "requested_formats": ["md", "md"]}
            )
        with pytest.raises(ValidationError):
            CreateSessionRequest.model_validate(
                {"story_id": STORY_ID, "requested_formats": []}
            )

    def test_opening_response_valid(self):
        response = CreateSessionResponse.model_validate(
            {
                "session_id": SESSION_ID,
                "story_run_id": RUN_ID,
                "state": "active",
                "opening_turn_number": 1,
                "facilitator_reply": "hello",
                "delegation": {"invoke": "none", "open_issues": ["i1"]},
                "issues": ["i1"],
                "synthesis": artifact_reference("synthesis"),
                "artifact_references": [artifact_reference("story")],
            }
        )
        assert response.opening_turn_number == 1
        assert response.state == "active"

    def test_opening_cannot_delegate(self):
        with pytest.raises(ValidationError, match="delegate"):
            CreateSessionResponse.model_validate(
                {
                    "session_id": SESSION_ID,
                    "story_run_id": RUN_ID,
                    "state": "active",
                    "opening_turn_number": 1,
                    "facilitator_reply": "hello",
                    "delegation": {"invoke": "both"},
                    "issues": [],
                    "synthesis": artifact_reference("synthesis"),
                    "artifact_references": [],
                }
            )

    def test_issues_must_mirror_delegation(self):
        with pytest.raises(ValidationError, match="mirror"):
            CreateSessionResponse.model_validate(
                {
                    "session_id": SESSION_ID,
                    "story_run_id": RUN_ID,
                    "state": "active",
                    "opening_turn_number": 1,
                    "facilitator_reply": "hello",
                    "delegation": {"invoke": "none", "open_issues": ["i1"]},
                    "issues": ["other"],
                    "synthesis": artifact_reference("synthesis"),
                    "artifact_references": [],
                }
            )

    def test_synthesis_reference_type_enforced(self):
        with pytest.raises(ValidationError, match="synthesis"):
            CreateSessionResponse.model_validate(
                {
                    "session_id": SESSION_ID,
                    "story_run_id": RUN_ID,
                    "state": "active",
                    "opening_turn_number": 1,
                    "facilitator_reply": "hello",
                    "delegation": {},
                    "issues": [],
                    "synthesis": artifact_reference("story"),
                    "artifact_references": [],
                }
            )


class TestTurnModels:
    def test_turn_request_requires_exactly_one_action(self):
        assert TurnRequest.model_validate({"message": "hi"}).message == "hi"
        assert TurnRequest.model_validate({"po_accepted": True}).po_accepted
        for bad in ({}, {"message": "hi", "po_accepted": True}):
            with pytest.raises(ValidationError, match="exactly one"):
                TurnRequest.model_validate(bad)

    def test_finalize_request_is_empty(self):
        assert FinalizeRequest.model_validate({}).model_dump() == {}

    def test_turn_view_valid_and_action_rule(self):
        ok = TurnView.model_validate({"turn_number": 2, "po_message": "hi", "outcome": "continue"})
        assert ok.po_accepted is False
        for bad in (
            {"turn_number": 2, "outcome": "continue"},  # neither action
            {"turn_number": 2, "po_message": "hi", "po_accepted": True, "outcome": "continue"},
        ):
            with pytest.raises(ValidationError, match="exactly one"):
                TurnView.model_validate(bad)
        # turn 1 (facilitator opening) may carry neither
        assert TurnView.model_validate({"turn_number": 1, "outcome": "continue"}).turn_number == 1

    def _turn_response(self, **overrides) -> dict:
        base = {
            "session_id": SESSION_ID,
            "turn_number": 2,
            "outcome": "continue",
            "state": "active",
            "facilitator_reply": "reply",
            "delegation": {"open_issues": ["i1"]},
            "issues": ["i1"],
        }
        return base | overrides

    def test_turn_response_state_matches_outcome(self):
        assert TurnResponse.model_validate(self._turn_response()).state == "active"
        with pytest.raises(ValidationError, match="state does not match"):
            TurnResponse.model_validate(self._turn_response(outcome="park", state="active"))

    def test_reports_only_on_finalize(self):
        with pytest.raises(ValidationError, match="report"):
            TurnResponse.model_validate(self._turn_response(report=[report_download("md")]))
        final = TurnResponse.model_validate(
            self._turn_response(outcome="finalize", state="completed", facilitator_reply=None)
            | {"report": [report_download("md"), report_download("pdf")]}
        )
        assert len(final.report) == 2
        with pytest.raises(ValidationError, match="unique"):
            TurnResponse.model_validate(
                self._turn_response(outcome="finalize", state="completed", facilitator_reply=None)
                | {"report": [report_download("md"), report_download("md")]}
            )

    def test_non_finalize_requires_delegation_and_reply(self):
        with pytest.raises(ValidationError, match="delegation is required"):
            TurnResponse.model_validate(
                self._turn_response(delegation=None, issues=[], facilitator_reply="r")
            )
        with pytest.raises(ValidationError, match="facilitator reply"):
            TurnResponse.model_validate(self._turn_response(facilitator_reply=None))

    def test_issues_mirror_delegation_open_issues(self):
        with pytest.raises(ValidationError, match="mirror"):
            TurnResponse.model_validate(self._turn_response(issues=["i1", "extra"]))

    def test_delegation_rationale_reply_field(self):
        """Item G / D21: the pre-delegation reply rides on TurnResponse,
        TurnView, and CanonicalTurnResult (default None, optional)."""
        response = TurnResponse.model_validate(
            self._turn_response(delegation_rationale_reply="why delegating")
        )
        assert response.delegation_rationale_reply == "why delegating"
        assert (
            TurnResponse.model_validate(self._turn_response()).delegation_rationale_reply
            is None
        )
        view = TurnView.model_validate(
            {"turn_number": 2, "po_message": "hi", "outcome": "continue",
             "delegation_rationale_reply": "why delegating"}
        )
        assert view.delegation_rationale_reply == "why delegating"
        assert TurnView.model_validate(
            {"turn_number": 2, "po_message": "hi", "outcome": "continue"}
        ).delegation_rationale_reply is None
        canonical = CanonicalTurnResult.model_validate(
            {
                "session_id": SESSION_ID,
                "turn_number": 2,
                "outcome": "continue",
                "state": "active",
                "delegation_rationale_reply": "why delegating",
            }
        )
        assert canonical.delegation_rationale_reply == "why delegating"

    def test_synthesis_reference_must_be_synthesis_type(self):
        with pytest.raises(ValidationError, match="synthesis"):
            TurnResponse.model_validate(
                self._turn_response(synthesis=artifact_reference("story"))
            )


class TestSessionModels:
    def _summary(self, **overrides) -> dict:
        base = {
            "session_id": SESSION_ID,
            "story_run_id": RUN_ID,
            "story_id": STORY_ID,
            "state": "active",
            "requested_formats": ["md", "pdf"],
            "created_at": FIXED_TS,
            "updated_at": FIXED_TS,
        }
        return base | overrides

    def test_summary_formats_unique(self):
        assert SessionSummary.model_validate(self._summary()).state == "active"
        with pytest.raises(ValidationError, match="unique"):
            SessionSummary.model_validate(self._summary(requested_formats=["md", "md"]))

    def test_processing_stage_optional_and_bounded(self):
        assert SessionSummary.model_validate(self._summary()).processing_stage is None
        staged = SessionSummary.model_validate(
            self._summary(processing_stage="synthesizing")
        )
        assert staged.processing_stage == "synthesizing"
        assert (
            SessionDetail.model_validate(
                self._summary(facilitator_turn_count=1, processing_stage="reviewing")
            ).processing_stage
            == "reviewing"
        )
        with pytest.raises(ValidationError, match="processing_stage"):
            SessionSummary.model_validate(self._summary(processing_stage="daydreaming"))

    def test_detail_reports_only_when_completed(self):
        detail = SessionDetail.model_validate(self._summary(facilitator_turn_count=1))
        assert detail.reports == []
        with pytest.raises(ValidationError, match="only completed"):
            SessionDetail.model_validate(
                self._summary(facilitator_turn_count=1, reports=[report_download("md")])
            )

    def test_completed_detail_requires_all_requested_formats(self):
        payload = self._summary(state="completed", facilitator_turn_count=3)
        with pytest.raises(ValidationError, match="every requested format"):
            SessionDetail.model_validate(payload | {"reports": [report_download("md")]})
        ok = SessionDetail.model_validate(
            payload | {"reports": [report_download("md"), report_download("pdf")]}
        )
        assert len(ok.reports) == 2
        with pytest.raises(ValidationError, match="unique"):
            SessionDetail.model_validate(
                payload | {"reports": [report_download("md"), report_download("md")]}
            )


class TestReportAndCanonicalModels:
    def test_report_download_format_must_match_reference(self):
        assert ReportDownload.model_validate(report_download("md")).format == "md"
        mismatch = report_download("md")
        mismatch["reference"] = artifact_reference("report-pdf")
        with pytest.raises(ValidationError, match="format"):
            ReportDownload.model_validate(mismatch)

    def test_report_response_unique_formats(self):
        ok = ReportResponse.model_validate(
            {"session_id": SESSION_ID, "report": [report_download("md"), report_download("pdf")]}
        )
        assert len(ok.report) == 2
        with pytest.raises(ValidationError, match="unique"):
            ReportResponse.model_validate(
                {"session_id": SESSION_ID, "report": [report_download("md"), report_download("md")]}
            )

    def _canonical_turn(self, **overrides) -> dict:
        base = {
            "session_id": SESSION_ID,
            "turn_number": 2,
            "outcome": "continue",
            "state": "active",
        }
        return base | overrides

    def test_canonical_turn_requires_report_references_only_on_finalize(self):
        assert CanonicalTurnResult.model_validate(self._canonical_turn()).state == "active"
        with pytest.raises(ValidationError, match="report references"):
            CanonicalTurnResult.model_validate(
                self._canonical_turn(report_references=[artifact_reference("report-md")])
            )
        final = CanonicalTurnResult.model_validate(
            self._canonical_turn(outcome="finalize", state="completed")
            | {
                "report_references": [
                    artifact_reference("report-md"),
                    artifact_reference("report-pdf"),
                ]
            }
        )
        assert len(final.report_references) == 2

    def test_canonical_turn_state_matches_outcome(self):
        with pytest.raises(ValidationError, match="state does not match"):
            CanonicalTurnResult.model_validate(
                self._canonical_turn(outcome="park", state="active")
            )

    def test_canonical_turn_report_references_must_be_unique(self):
        with pytest.raises(ValidationError, match="unique"):
            CanonicalTurnResult.model_validate(
                self._canonical_turn(outcome="finalize", state="completed")
                | {
                    "report_references": [
                        artifact_reference("report-md"),
                        artifact_reference("report-md"),
                    ]
                }
            )

    def test_canonical_turn_rejects_non_report_references(self):
        with pytest.raises(ValidationError, match="only report"):
            CanonicalTurnResult.model_validate(
                self._canonical_turn(outcome="finalize", state="completed")
                | {"report_references": [artifact_reference("synthesis")]}
            )

    def test_canonical_report_result_rules(self):
        ok = CanonicalReportResult.model_validate(
            {"session_id": SESSION_ID, "report_references": [artifact_reference("report-md")]}
        )
        assert len(ok.report_references) == 1
        with pytest.raises(ValidationError, match="only report"):
            CanonicalReportResult.model_validate(
                {"session_id": SESSION_ID, "report_references": [artifact_reference("synthesis")]}
            )
        with pytest.raises(ValidationError, match="unique"):
            CanonicalReportResult.model_validate(
                {
                    "session_id": SESSION_ID,
                    "report_references": [
                        artifact_reference("report-md"),
                        artifact_reference("report-md"),
                    ],
                }
            )


class TestAbandonSessionResponse:
    def test_valid_response(self):
        ok = AbandonSessionResponse.model_validate(
            {"session_id": SESSION_ID, "state": "parked"}
        )
        assert ok.state == "parked"

    def test_state_is_parked_only(self):
        with pytest.raises(ValidationError):
            AbandonSessionResponse.model_validate(
                {"session_id": SESSION_ID, "state": "active"}
            )

    def test_requires_both_fields(self):
        with pytest.raises(ValidationError):
            AbandonSessionResponse.model_validate({"session_id": SESSION_ID})


class TestHealth:
    def test_health_models(self):
        ok = HealthResponse.model_validate({"status": "ok", "dependencies": [{"name": "db", "reachable": True}]})
        assert ok.dependencies[0].name == "db"
        with pytest.raises(ValidationError):
            HealthResponse.model_validate({"status": "down"})
