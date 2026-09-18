"""Reviewer output fence (D35) tests: pure-function fence rules plus
regression against recorded evaluation captures.

Rule 1 (scope-settlement invalidation) and Rule 2 (re-review downgrade
clamp) are behavior-tested on hand-built reports and then re-run against
the real Phase 9 captures in tests/evaluation/artifacts/cases — the
thresholds must fire there (that is their calibration contract).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from review_schemas.review import Finding, ReviewReport, StoryDetail

from orchestration.agent_clients import ReviewerResult
from orchestration.flows import _fence_result

from orchestration.reviewer_output_fence import (
    apply_fence,
    story_plain_text,
    _settling_clauses,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _finding(fid: str, title: str, description: str, severity: str = "minor") -> Finding:
    return Finding(
        id=fid,
        title=title,
        description=description,
        severity=severity,  # type: ignore[arg-type]
        category="completeness",
    )


def _report(findings: list[Finding]) -> ReviewReport:
    return ReviewReport(
        perspective="business",
        story_id="story-01",
        summary="summary",
        findings=findings,
    )


def _story(text: str) -> StoryDetail:
    return StoryDetail(
        story_id="story-01",
        title="S",
        status="New",
        description=text,
        acceptance_criteria=[],
        epic_context="e",
        roadmap_context="r",
    )


CLEAN_SCOPE = (
    "Invoice content is exactly the order data returned by the endpoint "
    "(line items, unit prices, VAT rates, totals) — no additional "
    "branding, legal, or localization requirements in this story."
)

BRANDING_FINDING = _finding(
    "B-1",
    "Invoice may need branding beyond order data",
    "If customers require additional branding, legal text, or localized "
    "invoice content, the order data alone will not deliver the intended "
    "value.",
)


# ---------------------------------------------------------------- rule 1


class TestSettlingClauses:
    def test_marks_only_settling_sentences(self):
        text = (
            "The story adds rendering. Out of scope: credit notes. "
            "Invoices are single-language and single-currency (EUR)."
        )
        clauses = _settling_clauses(text)
        assert len(clauses) == 1
        assert "credit notes" in clauses[0]

    def test_recognizes_all_documented_markers(self):
        for marker in (
            "out of scope",
            "no additional",
            "exactly",
            "handled by the existing",
            "not in scope",
            "excluded",
            "no story-specific",
        ):
            assert _settling_clauses(f"Something before. The matter is {marker} here.") == [
                f"The matter is {marker} here."
            ]


class TestScopeSettlementDrop:
    def test_drops_finding_overlapping_settling_clause(self):
        report, events = apply_fence(
            _report([BRANDING_FINDING]),
            story_text=f"The story adds invoice rendering. {CLEAN_SCOPE}",
        )
        assert report.findings == []
        assert [e.rule for e in events] == ["scope_settlement"]
        assert events[0].finding_id == "B-1"
        assert "no additional" in events[0].reference
        assert events[0].similarity >= 0.35

    def test_keeps_unrelated_finding(self):
        unrelated = _finding(
            "B-1",
            "Retry timing is undefined",
            "The story never states how long the confirmation email job "
            "may take before a hard bounce is recorded.",
        )
        report, events = apply_fence(
            _report([unrelated]), story_text=f"The story adds rendering. {CLEAN_SCOPE}"
        )
        assert report.findings == [unrelated]
        assert events == []


# ---------------------------------------------------------------- rule 2


PREV_MAJOR = _finding(
    "B-3",
    "Concurrency hazard during retry",
    "The story does not specify how to prevent the customer from "
    "manually resubmitting the payment while a retry is in flight, "
    "which could cause a double charge.",
    severity="major",
)
EXTRA = (
    "The retry policy is max 3 attempts with 1s/5s/25s backoff, using a "
    "PSP idempotency key, and a 5-minute cart hold."
)
MATCHING_FINDING = _finding(
    "B-1",
    "Concurrency hazard during retry",
    "The provided context states an idempotency key will be used, which "
    "mitigates the risk, but the story does not prevent a manual retry "
    "resubmitting the payment while the automatic retry is in flight.",
)


class TestClamp:
    def test_clamps_previous_major_with_context_to_minor(self):
        previous = _report([PREV_MAJOR])
        report, events = apply_fence(
            _report([MATCHING_FINDING]),
            story_text="unrelated text",
            previous_review=previous,
            extra_context=EXTRA,
        )
        assert [f.severity for f in report.findings] == ["minor"]
        assert [e.rule for e in events] == ["re_review_clamp"]
        assert e0_reference_is_previous_id(events)

    def test_no_clamp_without_extra_context(self):
        previous = _report([PREV_MAJOR])
        report, events = apply_fence(
            _report([MATCHING_FINDING]),
            story_text="unrelated text",
            previous_review=previous,
        )
        assert [f.severity for f in report.findings] == ["minor"]  # unchanged
        assert events == []

    def test_previous_info_with_context_drops(self):
        previous = _report(
            [_finding("B-3", "Concurrency hazard during retry",
                      PREV_MAJOR.description, severity="info")]
        )
        report, events = apply_fence(
            _report([MATCHING_FINDING]),
            story_text="unrelated text",
            previous_review=previous,
            extra_context=EXTRA,
        )
        assert report.findings == []
        assert [e.rule for e in events] == ["re_review_clamp"]


def e0_reference_is_previous_id(events) -> bool:
    return events[0].reference == "B-3"


# ---------------------------------------------------------------- shape


class TestReportShape:
    def test_empty_findings_pass_through(self):
        report = _report([])
        fenced, events = apply_fence(report, story_text=CLEAN_SCOPE)
        assert fenced is report
        assert events == []

    def test_fence_preserves_other_fields_and_clones_models(self):
        report = _report([BRANDING_FINDING])
        fenced, _ = apply_fence(report, story_text=CLEAN_SCOPE)
        assert fenced.perspective == report.perspective
        assert fenced.summary == report.summary
        assert fenced.model_copy is not None
        assert fenced is not report
        # untouched findings keep identity of the source models
        kept = _finding("B-1", "Retry timing is undefined", "unrelated detail")
        fenced2, _ = apply_fence(_report([kept]), story_text=CLEAN_SCOPE)
        assert fenced2.findings[0] is kept


# ---------------------------------------------------------------- captures


class TestFenceResultWiring:
    """The choke-point helper: replaces the report, keeps audit
    metadata, emits one app event per fence action."""

    def test_replaces_report_and_emits_events(self):
        result = ReviewerResult(
            report=_report([BRANDING_FINDING]),
            agent_version="v1",
            prompt_sha256="sha",
        )
        captured: list[logging.LogRecord] = []
        handler = type("H", (logging.Handler,), {"emit": lambda self, r: captured.append(r)})()
        logger = logging.getLogger("storyreview.app")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            fenced = _fence_result(
                result, "business", CLEAN_SCOPE, correlation_id="cid-1"
            )
        finally:
            logger.removeHandler(handler)
        assert fenced.report.findings == []
        assert fenced.agent_version == "v1"
        assert fenced.prompt_sha256 == "sha"
        records = [r for r in captured if r.event == "reviewer_output_fence"]
        assert len(records) == 1
        assert records[0].correlation_id == "cid-1"
        assert records[0].perspective == "business"
        assert records[0].finding_id == "B-1"
        assert records[0].rule == "scope_settlement"


class TestTimedResultWrapper:
    def test_fenced_timed_result_keeps_span_and_metadata(self, caplog):
        """The re-review path wraps reviewer results in TimedResult; the
        fence must rebuild the inner result without losing the audit span
        (regression: 500 via dataclasses.replace on the wrapper)."""
        from orchestration.agent_clients import TimedResult
        from datetime import UTC, datetime

        inner = ReviewerResult(
            report=_report([BRANDING_FINDING]),
            agent_version="v1",
            prompt_sha256="sha",
        )
        wrapped = TimedResult(
            inner, datetime.now(UTC), datetime.now(UTC)
        )
        fenced = _fence_result(
            wrapped, "business", CLEAN_SCOPE, correlation_id="cid-2"
        )
        assert isinstance(fenced, TimedResult)
        assert fenced.report.findings == []
        assert fenced.agent_version == "v1"
        assert fenced.started_at == wrapped.started_at


def _load_case(name: str) -> dict:
    """Committed D35 fixtures (run-27 mint classes, pinned because the
    artifacts/ captures are overwritten by every suite run)."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


class TestCapturedCases:
    def test_t1_clean_b1_dropped(self):
        case = _load_case("d35_clean_case")
        story_text = story_plain_text(StoryDetail.model_validate(case["story"]))
        review = ReviewReport.model_validate(case["review"])
        fenced, events = apply_fence(review, story_text=story_text)
        dropped = {e.finding_id for e in events if e.rule == "scope_settlement"}
        assert "B-1" in dropped
        assert all(f.id != "B-1" for f in fenced.findings)

    def test_t1_engineering_weak_clamp_fires_on_v2(self):
        case = _load_case("d35_engineering_weak_case")
        story_text = story_plain_text(
            StoryDetail.model_validate(case["story"])
        )
        previous = ReviewReport.model_validate(case["previous"])
        current = ReviewReport.model_validate(case["current"])
        fenced, events = apply_fence(
            current,
            story_text=story_text,
            previous_review=previous,
            extra_context=case["extra_context"],
        )
        clamped = {e.finding_id for e in events if e.rule == "re_review_clamp"}
        # E-1 re-lists the in-flight-retry UX finding (prev E-2 major)
        # while citing the extra-context backoff policy.
        assert "E-1" in clamped
        by_id = {f.id: f for f in fenced.findings}
        assert by_id["E-1"].severity == "minor"
