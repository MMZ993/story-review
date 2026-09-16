"""Deterministic-assertion unit tests (Phase 9 increment 1).

Fixtures are hand-built captures incl. deliberate failure mutations —
no model calls, no network. Each test asserts both the passing shape and
at least one failure mode per assertion group, per development-rules
test-first discipline.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from dataset_loader.expected import ConflictStub, ExpectedConflicts, ExpectedCase
from evaluation.assertions import (
    assert_agent_runs,
    assert_conflicts,
    assert_delegation,
    assert_final,
    assert_findings_ceiling,
    assert_mcp_evidence,
    assert_persistence,
    assert_turn_structure,
    evaluate_case,
)
from evaluation.capture import (
    AgentRunEvidence,
    CaseCapture,
    PersistenceEvidence,
    artifact_key,
)

# --- fixture builders -----------------------------------------------------


def expected_case(**overrides) -> ExpectedCase:
    """A minimal valid clean-scenario contract, overridable per test."""
    data = {
        "schema_version": 1,
        "scenario": "clean",
        "requested_formats": ["md", "pdf"],
        "po_script": [{"po_accepted": True}],
        "expected_turns": [
            {
                "turn_number": 1,
                "outcome": "continue",
                "state_after": "active",
                "delegation": {
                    "invoke": "none",
                    "reuse_previous": False,
                    "extra_context_expected": False,
                    "open_issues_empty": True,
                },
                "produced_artifacts": [
                    {"type": "review-business", "version": 1},
                    {"type": "review-engineering", "version": 1},
                    {"type": "synthesis", "version": 1},
                ],
            },
            {
                "turn_number": 2,
                "outcome": "finalize",
                "state_after": "completed",
                "delegation": None,
                "produced_artifacts": [
                    {"type": "finalized-review", "version": 1},
                    {"type": "report-md", "version": 1},
                    {"type": "report-pdf", "version": 1},
                ],
            },
        ],
        "expected_findings": {
            "review-business": {"max_severity": "info", "required": []},
            "review-engineering": {"max_severity": "info", "required": []},
        },
        "expected_conflicts": {"at_turn_1": [], "later": []},
        "expected_final": {
            "state": "completed",
            "final_turn_number": 2,
            "facilitator_turn_count": 1,
            "po_accepted": True,
            "remaining_open_issues_empty": True,
            "reports": ["md", "pdf"],
        },
        "invariance": {},
    }
    data.update(overrides)
    return ExpectedCase.model_validate(data)


def agent_run(agent: str, started: str, finished: str | None = None) -> AgentRunEvidence:
    return AgentRunEvidence(
        agent=agent,
        agent_version="test-1",
        prompt_sha256="0" * 64,
        state="succeeded",
        transport_attempts=1,
        corrective_reprompts=0,
        started_at=datetime.fromisoformat(started),
        finished_at=datetime.fromisoformat(finished or started),
    )


def passing_capture() -> CaseCapture:
    """A capture that satisfies every assertion of `expected_case()`."""
    return CaseCapture(
        case_id="t1/clean",
        scenario="clean",
        template="t1",
        story_id="story-01",
        session_id="sess-00000000-0000-0000-0000-000000000000",
        story_run_id="run-00000000-0000-0000-0000-000000000000",
        turns=[
            {
                "turn_number": 1,
                "outcome": "continue",
                "delegation": {"invoke": "none", "reuse_previous": False,
                               "extra_context": None, "open_issues": []},
                "produced_artifacts": [
                    {"type": "review-business", "version": 1},
                    {"type": "review-engineering", "version": 1},
                    {"type": "synthesis", "version": 1},
                ],
            },
            {
                "turn_number": 2,
                "outcome": "finalize",
                "delegation": None,
                "produced_artifacts": [
                    {"type": "finalized-review", "version": 1},
                    {"type": "report-md", "version": 1},
                    {"type": "report-pdf", "version": 1},
                ],
            },
        ],
        final_detail={
            "state": "completed",
            "facilitator_turn_count": 1,
            "reports": [
                {"format": "md", "signed_url": "https://example.test/md"},
                {"format": "pdf", "signed_url": "https://example.test/pdf"},
            ],
        },
        artifacts={
            artifact_key("review-business", 1): {"findings": []},
            artifact_key("review-engineering", 1): {"findings": []},
            artifact_key("synthesis", 1): {"conflicts": []},
            artifact_key("finalized-review", 1): {
                "po_accepted": True,
                "remaining_open_issues": [],
            },
        },
        agent_runs=[
            # parallel fan-out overlaps; everything else is sequenced
            agent_run("business-reviewer", "2026-01-01T10:00:00+00:00", "2026-01-01T10:00:02+00:00"),
            agent_run("engineering-reviewer", "2026-01-01T10:00:01+00:00", "2026-01-01T10:00:03+00:00"),
            agent_run("synthesis", "2026-01-01T10:00:03+00:00", "2026-01-01T10:00:04+00:00"),
            agent_run("facilitator", "2026-01-01T10:00:04+00:00", "2026-01-01T10:00:05+00:00"),
        ],
        facilitator_tool_calls=[],
        persistence=PersistenceEvidence(
            restore_ok=True,
            restore_state="completed",
            same_run_read_ok=True,
            cross_run_rejected=True,
        ),
    )


def failure_details(failures):
    return [failure.assertion for failure in failures]


# --- turn structure -------------------------------------------------------


def test_turn_structure_passes_on_matching_capture():
    assert assert_turn_structure(passing_capture(), expected_case()) == []


def test_turn_structure_fails_on_wrong_outcome():
    capture = passing_capture()
    capture.turns[1]["outcome"] = "continue"
    failures = assert_turn_structure(capture, expected_case())
    assert "turn[2].outcome" in failure_details(failures)


def test_turn_structure_fails_on_artifact_version_drift():
    capture = passing_capture()
    capture.turns[0]["produced_artifacts"][2] = {"type": "synthesis", "version": 2}
    failures = assert_turn_structure(capture, expected_case())
    assert "turn[1].produced_artifacts" in failure_details(failures)


def test_turn_structure_fails_on_missing_turn():
    capture = passing_capture()
    capture.turns = capture.turns[:1]
    failures = assert_turn_structure(capture, expected_case())
    assert "turn[2].present" in failure_details(failures)


def _unpinned_case_and_capture():
    """An unresolvable-style case: turn 2 artifacts unpinned (null)."""
    case = expected_case(
        scenario="unresolvable",
        po_script=[{"message": "go on"}],
        expected_turns=[
            {
                "turn_number": 1,
                "outcome": "continue",
                "state_after": "active",
                "delegation": {"open_issues_empty": False},
                "produced_artifacts": [
                    {"type": "review-business", "version": 1},
                    {"type": "review-engineering", "version": 1},
                    {"type": "synthesis", "version": 1},
                ],
            },
            {
                "turn_number": 2,
                "outcome": "park",
                "state_after": "parked",
                "delegation": {"open_issues_empty": False},
                "produced_artifacts": None,
            },
        ],
        expected_final={
            "state": "parked",
            "final_turn_number": 2,
            "facilitator_turn_count": 2,
            "finalized": False,
            "po_accepted": False,
            "remaining_open_issues_empty": False,
            "reports": [],
        },
        requested_formats=["md"],
    )
    capture = passing_capture()
    capture.turns[1] = {
        "turn_number": 2,
        "outcome": "park",
        "delegation": {"invoke": "both", "open_issues": ["B-1: x"]},
        "produced_artifacts": [
            {"type": "review-business", "version": 2},
            {"type": "review-engineering", "version": 2},
            {"type": "synthesis", "version": 2},
        ],
    }
    return case, capture


def test_unpinned_artifacts_tolerated_with_version_continuity():
    case, capture = _unpinned_case_and_capture()
    capture.artifacts[artifact_key("review-business", 2)] = {"findings": []}
    capture.artifacts[artifact_key("review-engineering", 2)] = {"findings": []}
    capture.artifacts[artifact_key("synthesis", 2)] = {"conflicts": []}
    failures = assert_turn_structure(capture, case)
    assert failures == []


def test_unpinned_artifacts_fail_on_version_gap():
    case, capture = _unpinned_case_and_capture()
    capture.turns[1]["produced_artifacts"][0] = {
        "type": "review-business",
        "version": 3,
    }
    failures = assert_turn_structure(capture, case)
    assert "artifacts.version_continuity" in failure_details(failures)


# --- delegation -----------------------------------------------------------


def test_delegation_passes_when_pinned_fields_match():
    assert assert_delegation(passing_capture(), expected_case()) == []


def test_delegation_fails_on_wrong_invoke():
    case, capture = delegated_case_and_capture()
    # engineering re-ran instead of business
    capture.turns[1]["produced_artifacts"][0] = {
        "type": "review-engineering", "version": 2
    }
    capture.artifacts[artifact_key("review-engineering", 2)] = {
        "findings": [],
        "based_on_extra_context": "token flow details",
    }
    failures = assert_delegation(capture, case)
    assert "turn[2].delegation.invoke" in failure_details(failures)


def test_delegation_fails_on_unexpected_extra_context():
    case, capture = delegated_case_and_capture()
    case = case.model_copy(deep=True)
    case.expected_turns[1].delegation.extra_context_expected = False
    failures = assert_delegation(capture, case)
    assert "turn[2].delegation.extra_context" in failure_details(failures)


def test_delegation_open_issues_emptiness_is_asserted():
    capture = passing_capture()
    capture.turns[0]["delegation"]["open_issues"] = ["B-1: something"]
    failures = assert_delegation(capture, expected_case())
    assert "turn[1].delegation.open_issues_empty" in failure_details(failures)


# --- findings ceiling -----------------------------------------------------


def test_findings_ceiling_passes_within_ceiling():
    capture = passing_capture()
    capture.artifacts[artifact_key("review-business", 1)] = {
        "findings": [
            {"id": "B-1", "severity": "minor"},
            {"id": "B-2", "severity": "info"},
        ]
    }
    case = expected_case(
        expected_findings={
            "review-business": {"max_severity": "minor", "required": []},
            "review-engineering": {"max_severity": "info", "required": []},
        }
    )
    assert assert_findings_ceiling(capture, case) == []


def test_findings_ceiling_fails_above_ceiling_across_versions():
    capture = passing_capture()
    capture.artifacts[artifact_key("review-business", 2)] = {
        "findings": [{"id": "B-3", "severity": "blocker"}]
    }
    case = expected_case(
        expected_findings={
            "review-business": {"max_severity": "major", "required": []},
            "review-engineering": {"max_severity": "info", "required": []},
        }
    )
    failures = assert_findings_ceiling(capture, case)
    assert "findings[review-business].max_severity" in failure_details(failures)


def test_findings_ceiling_fails_when_no_review_content():
    capture = passing_capture()
    capture.artifacts.pop(artifact_key("review-engineering", 1))
    failures = assert_findings_ceiling(capture, expected_case())
    assert "findings[review-engineering].present" in failure_details(failures)


# --- conflicts ------------------------------------------------------------


def conflict_case() -> ExpectedCase:
    return expected_case(
        scenario="conflicting",
        po_script=[{"message": "resolve it"}],
        expected_turns=[
            {
                "turn_number": 1,
                "outcome": "continue",
                "state_after": "active",
                "delegation": {"invoke": "none", "open_issues_empty": False},
                "produced_artifacts": [
                    {"type": "review-business", "version": 1},
                    {"type": "review-engineering", "version": 1},
                    {"type": "synthesis", "version": 1},
                ],
            },
            {
                "turn_number": 2,
                "outcome": "finalize",
                "state_after": "completed",
                "delegation": None,
                "produced_artifacts": [
                    {"type": "finalized-review", "version": 1},
                    {"type": "report-md", "version": 1},
                ],
            },
        ],
        expected_conflicts={
            "at_turn_1": [
                {
                    "key": "C-1",
                    "kind": "needs_po_clarification",
                    "topic": "selection step",
                    "resolved_at_turn": 2,
                }
            ],
            "later": [],
        },
        expected_final={
            "state": "completed",
            "final_turn_number": 2,
            "facilitator_turn_count": 2,
            "po_accepted": False,
            "remaining_open_issues_empty": True,
            "reports": ["md"],
        },
        requested_formats=["md"],
    )


def conflict_capture() -> CaseCapture:
    capture = passing_capture()
    capture.scenario = "conflicting"
    capture.artifacts[artifact_key("synthesis", 1)] = {
        "conflicts": [
            {
                "id": "C-1",
                "needs_po_clarification": True,
                "business_refs": ["B-1"],
                "engineering_refs": ["E-1"],
            }
        ]
    }
    capture.artifacts[artifact_key("finalized-review", 1)] = {
        "po_accepted": False,
        "remaining_open_issues": [],
    }
    capture.final_detail["facilitator_turn_count"] = 2
    capture.final_detail["reports"] = [
        {"format": "md", "signed_url": "https://example.test/md"}
    ]
    return capture


def test_conflicts_pass_when_pinned_conflict_present_and_resolved():
    assert assert_conflicts(conflict_capture(), conflict_case()) == []


def test_conflicts_fail_when_key_missing():
    capture = conflict_capture()
    capture.artifacts[artifact_key("synthesis", 1)] = {"conflicts": []}
    failures = assert_conflicts(capture, conflict_case())
    assert "conflict[C-1].present" in failure_details(failures)


def test_conflicts_fail_on_wrong_kind():
    capture = conflict_capture()
    capture.artifacts[artifact_key("synthesis", 1)]["conflicts"][0][
        "needs_po_clarification"
    ] = False
    failures = assert_conflicts(capture, conflict_case())
    assert "conflict[C-1].kind" in failure_details(failures)


def test_conflicts_fail_when_still_open_in_latest_synthesis():
    capture = conflict_capture()
    capture.artifacts[artifact_key("synthesis", 2)] = {
        "conflicts": [
            {"id": "C-1", "needs_po_clarification": True}
        ]
    }
    failures = assert_conflicts(capture, conflict_case())
    assert "conflict[C-1].resolved" in failure_details(failures)


def test_later_conflict_pinning_falls_back_to_capture_synthesis():
    """Unpinned artifact turns: the conflict is located via the observed
    synthesis version of its first_seen turn, not the expected file."""
    case, capture = _unpinned_case_and_capture()
    case = case.model_copy(deep=True)
    case.expected_conflicts = ExpectedConflicts(
        later=[
            ConflictStub(
                key="C-1",
                kind="needs_po_clarification",
                topic="scope",
                first_seen_turn=2,
                resolved_at_turn=None,
            )
        ]
    )
    capture.artifacts[artifact_key("synthesis", 2)] = {
        "conflicts": [
            {"id": "C-1", "needs_po_clarification": True}
        ]
    }
    assert assert_conflicts(capture, case) == []


# --- final ----------------------------------------------------------------


def test_final_passes_on_matching_completed_state():
    assert assert_final(passing_capture(), expected_case()) == []


def test_final_fails_on_wrong_facilitator_turn_count():
    capture = passing_capture()
    capture.final_detail["facilitator_turn_count"] = 2
    failures = assert_final(capture, expected_case())
    assert "final.facilitator_turn_count" in failure_details(failures)


def test_final_fails_on_po_acceptance_mismatch():
    capture = passing_capture()
    capture.artifacts[artifact_key("finalized-review", 1)]["po_accepted"] = False
    failures = assert_final(capture, expected_case())
    assert "final.po_accepted" in failure_details(failures)


def test_final_fails_on_missing_report_format():
    capture = passing_capture()
    capture.final_detail["reports"] = capture.final_detail["reports"][:1]
    failures = assert_final(capture, expected_case())
    assert "final.report_formats" in failure_details(failures)


def test_final_fails_on_unsigned_report_url():
    capture = passing_capture()
    capture.final_detail["reports"][0]["signed_url"] = "http://insecure.test/md"
    failures = assert_final(capture, expected_case())
    assert "final.report_signed_urls" in failure_details(failures)


# --- agent runs -----------------------------------------------------------


def test_agent_runs_pass_when_counts_mirror_artifacts():
    assert assert_agent_runs(passing_capture(), expected_case()) == []


def test_agent_runs_fail_on_missing_reviewer_row():
    capture = passing_capture()
    capture.agent_runs = [
        r for r in capture.agent_runs if r.agent != "business-reviewer"
    ]
    failures = assert_agent_runs(capture, expected_case())
    assert "agent_runs.business-reviewer.count" in failure_details(failures)


def test_agent_runs_fail_on_failed_run_state():
    capture = passing_capture()
    capture.agent_runs[0].state = "failed"
    failures = assert_agent_runs(capture, expected_case())
    assert "agent_runs[business-reviewer].state" in failure_details(failures)


def test_agent_runs_fail_on_missing_identity_fields():
    capture = passing_capture()
    capture.agent_runs[2].prompt_sha256 = ""
    failures = assert_agent_runs(capture, expected_case())
    assert "agent_runs[synthesis].identity" in failure_details(failures)


def test_agent_runs_accepts_summary_label_variant():
    capture = passing_capture()
    capture.agent_runs.append(
        agent_run(
            "facilitator-summary:2",
            "2026-01-01T10:00:05+00:00",
            "2026-01-01T10:00:06+00:00",
        )
    )
    assert assert_agent_runs(capture, expected_case()) == []


def test_agent_runs_fail_when_synthesis_overlaps_a_reviewer():
    capture = passing_capture()
    capture.agent_runs[2].started_at = datetime.fromisoformat(
        "2026-01-01T10:00:02+00:00"
    )  # inside the business reviewer span
    failures = assert_agent_runs(capture, expected_case())
    assert "agent_runs.ordering" in failure_details(failures)


def test_agent_runs_fail_when_facilitator_overlaps_synthesis():
    capture = passing_capture()
    capture.agent_runs[3].started_at = datetime.fromisoformat(
        "2026-01-01T10:00:03+00:00"
    )
    failures = assert_agent_runs(capture, expected_case())
    assert "agent_runs.ordering" in failure_details(failures)


def test_agent_runs_reviewer_pair_overlap_is_allowed():
    capture = passing_capture()
    # make the reviewer spans overlap maximally — still passes
    capture.agent_runs[1].started_at = capture.agent_runs[0].started_at
    assert assert_agent_runs(capture, expected_case()) == []


# --- MCP evidence ---------------------------------------------------------


def test_mcp_evidence_skipped_for_non_comment_scenarios():
    assert assert_mcp_evidence(passing_capture(), expected_case()) == []


def test_mcp_evidence_fails_without_story_tool_call():
    capture = passing_capture()
    case = expected_case(scenario="comments-benign")
    failures = assert_mcp_evidence(capture, case)
    assert failures and failures[0].assertion == "mcp_evidence.story_tool_call"


def test_mcp_evidence_passes_with_get_story_call():
    capture = passing_capture()
    capture.facilitator_tool_calls = ["get_story"]
    assert assert_mcp_evidence(capture, expected_case(scenario="comments-benign")) == []


# --- persistence ----------------------------------------------------------


def test_persistence_passes_when_all_probes_ok():
    assert assert_persistence(passing_capture(), expected_case()) == []


def test_persistence_fails_per_probe():
    for field, assertion in (
        ("restore_ok", "persistence.restore"),
        ("same_run_read_ok", "persistence.same_run_read"),
        ("cross_run_rejected", "persistence.cross_run_rejected"),
    ):
        capture = passing_capture()
        setattr(capture.persistence, field, False)
        failures = assert_persistence(capture, expected_case())
        assert assertion in failure_details(failures), field


# --- battery --------------------------------------------------------------


def test_evaluate_case_collects_across_groups_and_never_crashes():
    capture = passing_capture()
    capture.turns[0]["outcome"] = "park"
    capture.persistence = None
    failures = evaluate_case(capture, expected_case())
    assert "turn[1].outcome" in failure_details(failures)
    assert "persistence.present" in failure_details(failures)


def test_evaluate_case_passing_capture_is_clean():
    assert evaluate_case(passing_capture(), expected_case()) == []


@pytest.mark.parametrize(
    "mutation, expected_assertion",
    [
        (lambda c: c.turns[0].update(outcome="park"), "turn[1].outcome"),
        (lambda c: c.agent_runs.clear(), "agent_runs.present"),
    ],
)
def test_evaluate_case_flagpole_mutations(mutation, expected_assertion):
    capture = passing_capture()
    mutation(capture)
    assert expected_assertion in failure_details(evaluate_case(capture, expected_case()))


# --- delegation routing from executed evidence (increment 3) --------------


def delegated_case_and_capture():
    """Turn 2 expects a business-only delegation with extra context; the
    turn record carries the post-delegation summary output (invoke=none,
    per the Item G/D21 design) while the re-review actually executed."""
    case = expected_case(
        expected_turns=[
            {
                "turn_number": 1,
                "outcome": "continue",
                "state_after": "active",
                "delegation": {
                    "invoke": "none",
                    "reuse_previous": False,
                    "extra_context_expected": False,
                    "open_issues_empty": True,
                },
                "produced_artifacts": [
                    {"type": "review-business", "version": 1},
                    {"type": "review-engineering", "version": 1},
                    {"type": "synthesis", "version": 1},
                ],
            },
            {
                "turn_number": 2,
                "outcome": "finalize",
                "state_after": "completed",
                "delegation": {
                    "invoke": "business",
                    "reuse_previous": False,
                    "extra_context_expected": True,
                    "open_issues_empty": True,
                },
                "produced_artifacts": [
                    {"type": "review-business", "version": 2},
                    {"type": "synthesis", "version": 2},
                    {"type": "finalized-review", "version": 1},
                    {"type": "report-md", "version": 1},
                ],
            },
        ]
    )
    capture = passing_capture()
    capture.turns[1]["delegation"] = {
        "invoke": "none", "reuse_previous": False,
        "extra_context": None, "open_issues": [],
    }
    capture.turns[1]["produced_artifacts"] = [
        {"type": "review-business", "version": 2},
        {"type": "synthesis", "version": 2},
        {"type": "finalized-review", "version": 1},
        {"type": "report-md", "version": 1},
    ]
    capture.artifacts[artifact_key("review-business", 2)] = {
        "findings": [],
        "based_on_extra_context": "+2pp Android conversion metric",
    }
    capture.artifacts[artifact_key("synthesis", 2)] = {"conflicts": []}
    return case, capture


def test_delegation_invoke_read_from_executed_re_reviews():
    case, capture = delegated_case_and_capture()
    assert assert_delegation(capture, case) == []


def test_delegation_invoke_fails_when_wrong_reviewer_ran():
    case, capture = delegated_case_and_capture()
    # engineering also re-ran → observed invoke "both"
    capture.turns[1]["produced_artifacts"].insert(
        1, {"type": "review-engineering", "version": 2}
    )
    failures = assert_delegation(capture, case)
    assert "turn[2].delegation.invoke" in failure_details(failures)


def test_delegation_invoke_fails_when_no_re_review_executed():
    case, capture = delegated_case_and_capture()
    capture.turns[1]["produced_artifacts"] = [
        {"type": "finalized-review", "version": 1},
        {"type": "report-md", "version": 1},
    ]
    failures = assert_delegation(capture, case)
    assert "turn[2].delegation.invoke" in failure_details(failures)


def test_delegation_extra_context_read_from_re_review_evidence():
    case, capture = delegated_case_and_capture()
    capture.artifacts[artifact_key("review-business", 2)] = {"findings": []}
    failures = assert_delegation(capture, case)
    assert "turn[2].delegation.extra_context" in failure_details(failures)


def test_delegation_reuse_observed_from_synthesis_only_turn():
    case, capture = delegated_case_and_capture()
    case = case.model_copy(deep=True)
    case.expected_turns[1].delegation.invoke = "none"
    case.expected_turns[1].delegation.reuse_previous = True
    case.expected_turns[1].delegation.extra_context_expected = False
    case.expected_turns[1].produced_artifacts = [
        {"type": "synthesis", "version": 2},
    ]
    capture.turns[1]["produced_artifacts"] = [
        {"type": "synthesis", "version": 2},
    ]
    assert assert_delegation(capture, case) == []
