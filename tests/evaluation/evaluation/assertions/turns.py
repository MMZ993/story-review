"""Turn-level deterministic assertions: structure + delegation.

Split out of the original single-module engine (file-size guideline):
each submodule keeps its assertion group; ``__init__`` composes the
battery. See ``_core`` for the shared ``AssertionFailure`` record.
"""

from __future__ import annotations

from dataset_loader.expected import ExpectedCase
from evaluation.assertions._core import AssertionFailure, _turn_view
from evaluation.capture import artifact_key

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


def _assert_version_continuity(capture) -> list[AssertionFailure]:
    """With any unpinned turn: per artifact type, observed versions across
    turns must be strictly increasing by exactly 1 (no gaps, no repeats)."""
    seen: dict[str, int] = {}
    failures: list[AssertionFailure] = []
    for turn in sorted(capture.turns, key=lambda t: t.get("turn_number", 0)):
        number = turn.get("turn_number")
        for ref in turn.get("produced_artifacts", []):
            kind, version = ref.get("type"), int(ref.get("version", 0))
            previous = seen.get(kind)
            if previous is not None and version != previous + 1:
                failures.append(
                    AssertionFailure(
                        "artifacts.version_continuity",
                        f"turn[{number}]: {kind} version {version} follows "
                        f"version {previous}; expected {previous + 1}",
                    )
                )
            seen[kind] = version
    return failures


def assert_turn_structure(
    capture, expected: ExpectedCase
) -> list[AssertionFailure]:
    """Per expected turn: outcome and the exact (type, version) artifact set.

    Turns whose expected ``produced_artifacts`` is null are unpinned: their
    artifact set is free (delegation is not deterministically pinned), and a
    session-wide version-continuity check replaces the exact-set assertion.
    """
    failures: list[AssertionFailure] = []
    unpinned_seen = False
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
        if expected_turn.produced_artifacts is None:
            unpinned_seen = True
            continue
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
    if unpinned_seen:
        failures.extend(_assert_version_continuity(capture))
    return failures


def _observed_delegation(
    turn: dict, capture, number: int
) -> tuple[str, bool, bool]:
    """Delegation routing as *executed* on this turn (Item G/D21: the
    turn record's ``delegation`` is the post-delegation summary output,
    whose own invocation is a next-turn intent — not what ran).

    Returns ``(invoke, reuse_previous, extra_context_seen)`` where invoke
    is derived from the review versions produced this turn, reuse means
    a synthesis version with no reviewer re-runs, and extra-context
    presence comes from the re-reviews' ``based_on_extra_context``.
    """
    produced = _produced_set(turn)
    review_sides = sorted(
        ref_type.removeprefix("review-")
        for ref_type, version in produced
        if ref_type.startswith("review-") and version >= 2
    )
    synthesis_ran = any(ref_type == "synthesis" for ref_type, _ in produced)
    if review_sides:
        invoke = (
            review_sides[0]
            if len(review_sides) == 1
            else "both" if len(review_sides) == 2
            else "none"
        )
        reuse = False
    else:
        invoke = "none"
        # turn 1 always runs the initial fan-out + synthesis; reuse means a
        # synthesis-only later turn
        reuse = synthesis_ran and number != 1
    extra_context_seen = any(
        (capture.artifacts.get(artifact_key(ref_type, version)) or {}).get(
            "based_on_extra_context"
        )
        is not None
        for ref_type, version in produced
        if ref_type.startswith("review-") and version >= 2
    )
    return invoke, reuse, extra_context_seen


def assert_delegation(
    capture, expected: ExpectedCase
) -> list[AssertionFailure]:
    """Delegation exactness, only where the expected file pins it.

    Routing (invoke, reuse, extra-context presence) is asserted from the
    executed evidence of the turn (produced review versions and their
    ``based_on_extra_context``), per evaluation-tests.md "selected
    reviewer routing exactly matches the scripted PO clarification";
    ``open_issues`` is asserted from the turn record's final output —
    that field is gate-authoritative by design.
    """
    failures: list[AssertionFailure] = []
    for expected_turn in expected.expected_turns:
        expectation = expected_turn.delegation
        if expectation is None:
            continue
        number = expected_turn.turn_number
        turn = _turn_view(capture, number)
        if turn is None:
            continue  # already reported by turn-structure
        observed_invoke, observed_reuse, observed_extra = _observed_delegation(
            turn, capture, number
        )
        if expectation.invoke is not None:
            if observed_invoke != expectation.invoke:
                failures.append(
                    AssertionFailure(
                        f"turn[{number}].delegation.invoke",
                        f"expected {expectation.invoke}, observed {observed_invoke}",
                    )
                )
        if expectation.reuse_previous is not None:
            if observed_reuse != expectation.reuse_previous:
                failures.append(
                    AssertionFailure(
                        f"turn[{number}].delegation.reuse_previous",
                        f"expected {expectation.reuse_previous}, "
                        f"observed {observed_reuse}",
                    )
                )
        if expectation.extra_context_expected is not None:
            if observed_extra != expectation.extra_context_expected:
                failures.append(
                    AssertionFailure(
                        f"turn[{number}].delegation.extra_context",
                        f"expected presence={expectation.extra_context_expected}, "
                        f"observed presence={observed_extra}",
                    )
                )
        if expectation.open_issues_empty is not None:
            open_issues = (turn.get("delegation") or {}).get("open_issues", [])
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
