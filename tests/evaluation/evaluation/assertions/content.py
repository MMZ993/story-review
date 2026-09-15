"""Artifact-content deterministic assertions: findings ceiling + conflicts.

Finding stub coverage is judge-matched by contract (runtime finding IDs
are never pinned); only the severity ceiling is deterministic. Conflict
stubs carry ``deterministically_pinned`` keys (C-n ids are stable within
a case run) and are asserted set-based against synthesis versions.
"""

from __future__ import annotations

from evaluation.assertions._core import AssertionFailure, severity_rank


def _review_findings(artifacts: dict[str, dict], review_type: str) -> list[dict]:
    findings: list[dict] = []
    for key, content in artifacts.items():
        if key.startswith(f"{review_type}#"):
            findings.extend(content.get("findings", []))
    return findings


def assert_findings_ceiling(capture, expected) -> list[AssertionFailure]:
    """No finding of either review perspective may exceed the pinned
    ``max_severity`` ceiling, across every artifact version of the run."""
    failures: list[AssertionFailure] = []
    for view_name, view in expected.expected_findings.items():
        versions = [key for key in capture.artifacts if key.startswith(f"{view_name}#")]
        if not versions:
            failures.append(
                AssertionFailure(
                    f"findings[{view_name}].present",
                    "no review artifact content captured for this perspective",
                )
            )
            continue
        findings = _review_findings(capture.artifacts, view_name)
        ceiling = severity_rank(view.max_severity)
        over = [
            finding
            for finding in findings
            if severity_rank(finding.get("severity", "")) > ceiling
        ]
        if over:
            failures.append(
                AssertionFailure(
                    f"findings[{view_name}].max_severity",
                    f"ceiling {view.max_severity} exceeded by: "
                    f"{[(f.get('id'), f.get('severity')) for f in over]}",
                )
            )
    return failures


def _synthesis_conflicts(artifacts: dict[str, dict], version: int) -> list[dict]:
    content = artifacts.get(f"synthesis#v{version}")
    if content is None:
        raise ValueError(f"synthesis v{version} content not captured")
    return content.get("conflicts", [])


def _synthesis_version_of_turn(expected, turn_number: int) -> int | None:
    """Synthesis version produced on a turn per the expected file."""
    for turn in expected.expected_turns:
        if turn.turn_number == turn_number:
            for artifact in turn.produced_artifacts:
                if artifact.type == "synthesis":
                    return artifact.version
    return None


def _check_conflict_stub(
    capture, stub, synthesis_version: int, latest: int
) -> list[AssertionFailure]:
    failures: list[AssertionFailure] = []
    try:
        conflicts = _synthesis_conflicts(capture.artifacts, synthesis_version)
    except ValueError as exc:
        return [AssertionFailure(f"conflict[{stub.key}].content", str(exc))]
    matching = [c for c in conflicts if c.get("id") == stub.key]
    if not matching:
        failures.append(
            AssertionFailure(
                f"conflict[{stub.key}].present",
                f"synthesis v{synthesis_version} conflicts: "
                f"{[c.get('id') for c in conflicts]}",
            )
        )
        return failures
    observed_kind = (
        "needs_po_clarification"
        if matching[0].get("needs_po_clarification")
        else "resolvable"
    )
    if observed_kind != stub.kind:
        failures.append(
            AssertionFailure(
                f"conflict[{stub.key}].kind",
                f"expected {stub.kind}, observed {observed_kind}",
            )
        )
    if stub.resolved_at_turn is not None and latest > synthesis_version:
        still = [
            c
            for c in _synthesis_conflicts(capture.artifacts, latest)
            if c.get("id") == stub.key
        ]
        if still:
            failures.append(
                AssertionFailure(
                    f"conflict[{stub.key}].resolved",
                    f"still listed as open in synthesis v{latest}",
                )
            )
    return failures


def assert_conflicts(capture, expected) -> list[AssertionFailure]:
    """Pinned conflict keys: present in the pinned synthesis version,
    resolved stubs absent from the latest synthesis version."""
    failures: list[AssertionFailure] = []
    conflicts_spec = expected.expected_conflicts
    if conflicts_spec is None:
        return failures
    latest_synthesis = max(
        (
            int(key.split("#v")[1])
            for key in capture.artifacts
            if key.startswith("synthesis#")
        ),
        default=0,
    )
    for stub in conflicts_spec.at_turn_1:
        failures.extend(
            _check_conflict_stub(capture, stub, synthesis_version=1, latest=latest_synthesis)
        )
    for stub in conflicts_spec.later:
        first_seen = stub.first_seen_turn or 2
        version = _synthesis_version_of_turn(expected, first_seen)
        if version is None:
            failures.append(
                AssertionFailure(
                    f"conflict[{stub.key}].pinning",
                    f"no synthesis artifact pinned on turn {first_seen}; "
                    "cannot locate the conflict deterministically",
                )
            )
            continue
        failures.extend(
            _check_conflict_stub(capture, stub, synthesis_version=version, latest=latest_synthesis)
        )
    return failures
