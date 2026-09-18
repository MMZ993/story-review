"""Deterministic assertion engine (Phase 9 increment 1, judge OFF).

Public surface: the per-group assertion functions (re-exported for tests)
and ``evaluate_case`` — the full battery in report order. Group modules:
``turns`` (structure + delegation), ``content`` (findings ceiling +
conflicts), ``evidence`` (final state, audit rows, MCP use, persistence).
Pure functions over (CaseCapture, ExpectedCase); no model calls.
"""

from __future__ import annotations

from evaluation.assertions._core import AssertionFailure
from evaluation.assertions.content import (
    assert_conflicts,
    assert_findings_ceiling,
    reclassify_minor_over_info,
)
from evaluation.assertions.evidence import (
    assert_agent_runs,
    assert_final,
    assert_mcp_evidence,
    assert_persistence,
)
from evaluation.assertions.turns import assert_delegation, assert_turn_structure

__all__ = [
    "AssertionFailure",
    "ALL_ASSERTIONS",
    "evaluate_case",
    "assert_turn_structure",
    "assert_delegation",
    "assert_findings_ceiling",
    "reclassify_minor_over_info",
    "assert_conflicts",
    "assert_final",
    "assert_agent_runs",
    "assert_mcp_evidence",
    "assert_persistence",
]

#: The full deterministic battery, in report order.
ALL_ASSERTIONS = (
    ("turn_structure", assert_turn_structure),
    ("delegation", assert_delegation),
    ("findings_ceiling", assert_findings_ceiling),
    ("conflicts", assert_conflicts),
    ("final", assert_final),
    ("agent_runs", assert_agent_runs),
    ("mcp_evidence", assert_mcp_evidence),
    ("persistence", assert_persistence),
)


def evaluate_case(capture, expected) -> list[AssertionFailure]:
    """Run every deterministic assertion; empty list = case passed.

    An assertion that raises is recorded as a failure (``group.error``)
    so one malformed capture cannot abort the whole run.
    """
    failures: list[AssertionFailure] = []
    for name, assertion in ALL_ASSERTIONS:
        try:
            failures.extend(assertion(capture, expected))
        except Exception as exc:  # fail loud per assertion, not per run
            failures.append(
                AssertionFailure(f"{name}.error", f"{type(exc).__name__}: {exc}")
            )
    return failures
