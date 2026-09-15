"""Evidence deterministic assertions: final state, audit rows, MCP use,
persistence probes.

Audit rows carry the real invocation spans (timed invokes recorded by
the flows), so the designed ordering assertions are asserted directly:
within one case, only the two reviewer spans of the same fan-out may
overlap — every other pair of invocations is strictly sequenced
(synthesis after both reviewers, facilitator after synthesis, later
turns after earlier ones).
"""

from __future__ import annotations

from evaluation.assertions._core import AssertionFailure


def assert_final(capture, expected) -> list[AssertionFailure]:
    """Terminal session state + finalized-review + report expectations."""
    failures: list[AssertionFailure] = []
    detail = capture.final_detail
    final = expected.expected_final
    if detail.get("state") != final.state:
        failures.append(
            AssertionFailure(
                "final.state",
                f"expected {final.state}, observed {detail.get('state')}",
            )
        )
    last_turn = capture.turns[-1]["turn_number"] if capture.turns else 0
    if last_turn != final.final_turn_number:
        failures.append(
            AssertionFailure(
                "final.turn_number",
                f"expected {final.final_turn_number}, observed {last_turn}",
            )
        )
    observed_count = detail.get("facilitator_turn_count")
    if observed_count != final.facilitator_turn_count:
        failures.append(
            AssertionFailure(
                "final.facilitator_turn_count",
                f"expected {final.facilitator_turn_count}, "
                f"observed {observed_count}",
            )
        )
    if detail.get("state") != "completed":
        return failures
    failures.extend(_assert_completed_state(capture, final))
    return failures


def _assert_completed_state(capture, final) -> list[AssertionFailure]:
    failures: list[AssertionFailure] = []
    content = capture.artifacts.get("finalized-review#v1")
    if content is None:
        failures.append(
            AssertionFailure(
                "final.finalized_review",
                "finalized-review artifact content not captured",
            )
        )
        return failures
    observed_accepted = content.get("po_accepted")
    if observed_accepted != final.po_accepted:
        failures.append(
            AssertionFailure(
                "final.po_accepted",
                f"expected {final.po_accepted}, observed {observed_accepted}",
            )
        )
    observed_remaining = content.get("remaining_open_issues", [])
    observed_remaining_empty = not observed_remaining
    if observed_remaining_empty != final.remaining_open_issues_empty:
        failures.append(
            AssertionFailure(
                "final.remaining_open_issues_empty",
                f"expected empty={final.remaining_open_issues_empty}, "
                f"observed {len(observed_remaining)} remaining",
            )
        )
    detail = capture.final_detail
    reports = detail.get("reports", [])
    observed_formats = sorted(report.get("format") for report in reports)
    if observed_formats != sorted(final.reports):
        failures.append(
            AssertionFailure(
                "final.report_formats",
                f"expected {sorted(final.reports)}, observed {observed_formats}",
            )
        )
    unsigned = [
        r
        for r in reports
        if not str(r.get("signed_url", "")).startswith("https://")
    ]
    if unsigned:
        failures.append(
            AssertionFailure(
                "final.report_signed_urls",
                f"reports without https signed URLs: {unsigned}",
            )
        )
    return failures


def _base_agent(agent: str) -> str:
    """Normalized agent name: the label before any ``:`` suffix."""
    return agent.split(":")[0]


def assert_agent_runs(capture, expected) -> list[AssertionFailure]:
    """Audit-row integrity: names, success state, version/prompt identity,
    and per-agent row counts mirroring the observed artifact versions."""
    failures: list[AssertionFailure] = []
    rows = capture.agent_runs
    if not rows:
        return [AssertionFailure("agent_runs.present", "no audit rows captured")]
    named_agents = {
        "business-reviewer",
        "engineering-reviewer",
        "synthesis",
        "facilitator",
    }
    for row in rows:
        base = _base_agent(row.agent)
        if base not in named_agents and not base.startswith("facilitator"):
            failures.append(
                AssertionFailure(
                    "agent_runs.agent_names",
                    f"unexpected agent {row.agent!r}",
                )
            )
        if row.state != "succeeded":
            failures.append(
                AssertionFailure(
                    f"agent_runs[{row.agent}].state",
                    f"expected succeeded, observed {row.state}",
                )
            )
        if not row.agent_version or not row.prompt_sha256:
            failures.append(
                AssertionFailure(
                    f"agent_runs[{row.agent}].identity",
                    "missing agent_version or prompt_sha256 "
                    "(local equivalent of the distinct-identity assertion)",
                )
            )
    for review_type, agent in (
        ("review-business", "business-reviewer"),
        ("review-engineering", "engineering-reviewer"),
        ("synthesis", "synthesis"),
    ):
        observed_versions = {
            int(key.split("#v")[1])
            for key in capture.artifacts
            if key.startswith(f"{review_type}#")
        }
        row_count = sum(1 for row in rows if _base_agent(row.agent) == agent)
        if row_count != len(observed_versions):
            failures.append(
                AssertionFailure(
                    f"agent_runs.{agent}.count",
                    f"{len(observed_versions)} {review_type} artifact version(s) "
                    f"but {row_count} audit row(s)",
                )
            )
    facilitator_rows = sum(1 for row in rows if row.agent.startswith("facilitator"))
    if facilitator_rows < (capture.final_detail.get("facilitator_turn_count") or 0):
        failures.append(
            AssertionFailure(
                "agent_runs.facilitator.count",
                "fewer facilitator audit rows than facilitator turns",
            )
        )
    failures.extend(assert_agent_run_ordering(rows))
    return failures


def _spans_overlap(a, b) -> bool:
    """Half-open interval overlap."""
    return a.started_at < b.finished_at and b.started_at < a.finished_at


def assert_agent_run_ordering(rows) -> list[AssertionFailure]:
    """Fan-out/ordering: only the reviewer pair may overlap.

    Every other pair of invocation spans must be strictly sequenced —
    this proves parallel reviewer fan-out, reviewer-before-synthesis,
    synthesis-before-facilitator, and cross-turn ordering in one rule.
    """
    failures: list[AssertionFailure] = []
    reviewer_pair = {"business-reviewer", "engineering-reviewer"}
    for i, first in enumerate(rows):
        for second in rows[i + 1 :]:
            if not _spans_overlap(first, second):
                continue
            pair = {_base_agent(first.agent), _base_agent(second.agent)}
            if pair <= reviewer_pair:
                continue  # the designed parallel fan-out
            failures.append(
                AssertionFailure(
                    "agent_runs.ordering",
                    f"spans of {first.agent} and {second.agent} overlap; only "
                    "the business/engineering reviewer fan-out may run in "
                    "parallel",
                )
            )
    return failures


def assert_mcp_evidence(capture, expected) -> list[AssertionFailure]:
    """Comment scenarios: the facilitator must have issued at least one
    read-only Story-MCP tool call itself (agent-driven MCP use)."""
    if not expected.scenario.startswith("comments"):
        return []
    story_calls = [
        name
        for name in capture.facilitator_tool_calls
        if name in {"get_story", "list_stories"}
    ]
    if not story_calls:
        return [
            AssertionFailure(
                "mcp_evidence.story_tool_call",
                "no facilitator-initiated Story-MCP function call in the ADK "
                f"trace; observed tool calls: {capture.facilitator_tool_calls}",
            )
        ]
    return []


def assert_persistence(capture, expected) -> list[AssertionFailure]:
    """Session restore + same-run artifact read + cross-run rejection."""
    persistence = capture.persistence
    if persistence is None:
        return [
            AssertionFailure("persistence.present", "no persistence probes captured")
        ]
    failures: list[AssertionFailure] = []
    if not persistence.restore_ok:
        failures.append(
            AssertionFailure(
                "persistence.restore",
                f"session restore failed; state={persistence.restore_state}",
            )
        )
    if not persistence.same_run_read_ok:
        failures.append(
            AssertionFailure(
                "persistence.same_run_read", "same-run artifact read failed"
            )
        )
    if not persistence.cross_run_rejected:
        failures.append(
            AssertionFailure(
                "persistence.cross_run_rejected",
                "cross-run artifact read was not rejected",
            )
        )
    return failures
