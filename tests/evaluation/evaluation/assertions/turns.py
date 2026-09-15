"""Turn-level deterministic assertions: structure + delegation.

Split out of the original single-module engine (file-size guideline):
each submodule keeps its assertion group; ``__init__`` composes the
battery. See ``_core`` for the shared ``AssertionFailure`` record.
"""

from __future__ import annotations

from dataset_loader.expected import ExpectedCase
from evaluation.assertions._core import AssertionFailure, _turn_view

#: Artifact types a TurnView may legitimately report.
_TURN_ARTIFACT_TYPES = frozenset(
    {
        "review-business",
        "review-engineering",
        "synthesis",
        "finalized-review",
        "report-md",
        "report-pdf",
        "story",
    }
)


def _produced_set(turn: dict) -> set[tuple[str, int]]:
    refs = turn.get("produced_artifacts", [])
    unknown = [
        ref["type"] for ref in refs if ref.get("type") not in _TURN_ARTIFACT_TYPES
    ]
    if unknown:
        raise ValueError(f"unknown artifact types on turn: {unknown}")
    return {(ref["type"], ref["version"]) for ref in refs}


def assert_turn_structure(
    capture, expected: ExpectedCase
) -> list[AssertionFailure]:
    """Per expected turn: outcome and the exact (type, version) artifact set."""
    failures: list[AssertionFailure] = []
    for expected_turn in expected.expected_turns:
        number = expected_turn.turn_number
        turn = _turn_view(capture, number)
        if turn is None:
            failures.append(
                AssertionFailure(
                    f"turn[{number}].present",
                    f"no persisted turn {number}; turns seen: "
                    f"{[t.get('turn_number') for t in capture.turns]}",
                )
            )
            continue
        if turn.get("outcome") != expected_turn.outcome:
            failures.append(
                AssertionFailure(
                    f"turn[{number}].outcome",
                    f"expected {expected_turn.outcome}, "
                    f"observed {turn.get('outcome')}",
                )
            )
        expected_artifacts = {
            (item.type, item.version) for item in expected_turn.produced_artifacts
        }
        observed_artifacts = _produced_set(turn)
        if observed_artifacts != expected_artifacts:
            failures.append(
                AssertionFailure(
                    f"turn[{number}].produced_artifacts",
                    f"expected {sorted(expected_artifacts)}, "
                    f"observed {sorted(observed_artifacts)}",
                )
            )
    return failures


def assert_delegation(
    capture, expected: ExpectedCase
) -> list[AssertionFailure]:
    """Delegation decision exactness, only where the expected file pins it."""
    failures: list[AssertionFailure] = []
    for expected_turn in expected.expected_turns:
        expectation = expected_turn.delegation
        if expectation is None:
            continue
        number = expected_turn.turn_number
        turn = _turn_view(capture, number)
        if turn is None:
            continue  # already reported by turn-structure
        delegation = turn.get("delegation") or {}
        if expectation.invoke is not None:
            observed_invoke = delegation.get("invoke")
            if observed_invoke != expectation.invoke:
                failures.append(
                    AssertionFailure(
                        f"turn[{number}].delegation.invoke",
                        f"expected {expectation.invoke}, observed {observed_invoke}",
                    )
                )
        if expectation.reuse_previous is not None:
            observed_reuse = delegation.get("reuse_previous", False)
            if observed_reuse != expectation.reuse_previous:
                failures.append(
                    AssertionFailure(
                        f"turn[{number}].delegation.reuse_previous",
                        f"expected {expectation.reuse_previous}, "
                        f"observed {observed_reuse}",
                    )
                )
        if expectation.extra_context_expected is not None:
            observed_extra = delegation.get("extra_context") is not None
            if observed_extra != expectation.extra_context_expected:
                failures.append(
                    AssertionFailure(
                        f"turn[{number}].delegation.extra_context",
                        f"expected presence={expectation.extra_context_expected}, "
                        f"observed presence={observed_extra}",
                    )
                )
        if expectation.open_issues_empty is not None:
            open_issues = delegation.get("open_issues", [])
            observed_empty = not open_issues
            if observed_empty != expectation.open_issues_empty:
                failures.append(
                    AssertionFailure(
                        f"turn[{number}].delegation.open_issues_empty",
                        f"expected empty={expectation.open_issues_empty}, "
                        f"observed {len(open_issues)} open issue(s)",
                    )
                )
    return failures
