"""Orchestration-side facilitator turn-validation mirror (D34).

The Agent Engine facilitator has no adapter around it: the raw LlmAgent
serves turns, so the turn-context rules that the local adapter enforces
(`agent_kit.facilitator_input.validate_turn_output` + the bounded
corrective re-prompt loop) have no AE-side enforcement point inside the
engine. This module mirrors that validation over the duck-typed
`FacilitatorInvocation` (field-identical to agent_kit's
`FacilitatorRequest`, same pattern as the renderer mirrors in
`ae_messages.py`), and `AeFacilitatorClient` re-prompts with
`corrective_message` on violation — at most twice, exhaustion raises
`DELEGATION_VALIDATION` (non-retryable), exactly like the local
adapter's `turn_with_corrections`. Drift between the mirror and the
agent_kit original is pinned by
`shared/agent_kit/tests/test_ae_turn_rule_mirrors.py`.

The corrective message embeds the turn marker ("This is turn <n>") so the
D25 reconciliation matcher (`recovered_turn_reply`) still attributes the
corrective exchange's reply to this invocation.
"""

from __future__ import annotations

CORRECTIVE_MAX = 2


class TurnInvalid(Exception):
    """The turn output violates a turn-context rule; the caller re-prompts
    (bounded) or, on exhaustion, fails with `DELEGATION_VALIDATION`."""


def corrective_message(reasons: str, turn_number: int) -> str:
    """The re-prompt sent after a rule-violating turn output; carries the
    turn marker so session-event reconciliation stays attributable."""
    return (
        f"This is turn {turn_number} (corrective re-prompt, same turn).\n\n"
        "Your previous reply was not a valid FacilitatorTurnOutput:\n"
        f"{reasons}\n\n"
        "Reply again with a single corrected FacilitatorTurnOutput as JSON "
        "only — no prose outside the JSON object."
    )


def validate_facilitator_turn(output, request) -> None:
    """Mirror of `agent_kit.facilitator_input.validate_turn_output`.

    Raises TurnInvalid with a human-readable reason (the corrective
    re-prompt body). `output` is a `FacilitatorTurnOutput`; `request` is
    duck-typed over the agent_kit `FacilitatorRequest` field names.
    """
    if request.turn_number == 1:
        validate_opening_turn(output, request.synthesis_report)
    if request.decision_state is not None:
        _validate_identifier_lifecycle(output, request)
    _validate_issue_descriptors(output, request)


def validate_opening_turn(output, synthesis_report) -> None:
    """Turn-1 rules only (invoke = none + the D34 severity fence) over a
    bare synthesis report — the deterministic 422 backstop reused by the
    session-creation flow, independent of a full invocation."""
    if output.delegation.invoke != "none":
        raise TurnInvalid("the opening turn must emit delegation.invoke = none")
    _validate_opening_fence(output, synthesis_report)


def _validate_opening_fence(output, synthesis_report) -> None:
    """D34 severity fence: turn-1 resolutions may only be `resolved`
    dispositions for `info`/`minor` synthesis findings."""
    fenceable = {
        finding.id
        for finding in synthesis_report.merged_findings
        if finding.severity in ("info", "minor")
    }
    for draft in output.resolutions:
        if draft.disposition != "resolved" or draft.issue not in fenceable:
            raise TurnInvalid(
                f"opening-turn severity fence: issue {draft.issue} with "
                f"disposition {draft.disposition!r} may not be resolved on "
                "turn 1 — only info/minor synthesis findings with a "
                "`resolved` disposition may be settled before the PO's "
                "first answer; leave it for a later turn"
            )


def _validate_identifier_lifecycle(output, request) -> None:
    """D18 rules: a resolved/accepted id reappearing in open_issues needs a
    `reopened` disposition this turn; a turn cannot settle an id and keep
    it on its own open list."""
    reopened = {
        draft.issue
        for draft in output.resolutions
        if draft.disposition == "reopened"
    }
    latest = {item.issue: item for item in request.decision_state.resolutions}
    for issue in output.delegation.open_issues:
        recorded = latest.get(issue)
        if (
            recorded is not None
            and recorded.disposition in ("resolved", "accepted")
            and issue not in reopened
        ):
            raise TurnInvalid(
                f"issue {issue} was {recorded.disposition} at turn "
                f"{recorded.turn_number} — re-appearing in open_issues "
                "requires a reopened disposition this turn (identifiers "
                "are immutable; a new concern gets a fresh id)"
            )
    settled_now = {
        draft.issue
        for draft in output.resolutions
        if draft.disposition in ("resolved", "accepted")
    }
    for issue in settled_now.intersection(output.delegation.open_issues):
        raise TurnInvalid(
            f"issue {issue} is resolved this turn but still listed in "
            "open_issues — a turn cannot settle and retain the same "
            "issue; either drop it from open_issues or re-open it later"
        )


def _validate_issue_descriptors(output, request) -> None:
    """D19: every id the facilitator mints (not synthesis-born, not
    previously seen in the decision state) needs an IssueDraft on the turn
    it first appears in open_issues."""
    known = (
        {finding.id for finding in request.synthesis_report.merged_findings}
        | {conflict.id for conflict in request.synthesis_report.conflicts}
    )
    if request.decision_state is not None:
        known |= {item.issue for item in request.decision_state.resolutions}
        known |= set(request.decision_state.open_issues)
    described = {draft.issue for draft in output.new_issues}
    for issue in output.delegation.open_issues:
        if issue not in known and issue not in described:
            raise TurnInvalid(
                f"issue {issue} is newly minted — it needs an IssueDraft in "
                f'new_issues this turn, e.g. "new_issues": [{{"issue": '
                f'"{issue}", "title": "...", "description": "..."}}] '
                "(synthesis-born ids must not be re-described)"
            )
