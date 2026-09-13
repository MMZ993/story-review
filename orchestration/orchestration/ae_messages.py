"""Agent Engine user-message renderers (mirrors of the agent_kit ones).

Orchestration cannot import `agent_kit` (its package `__init__` drags the
ADK), but the deployed Agent Engine agents receive exactly the messages
the agent_kit input renderers produce (the adapters render them today).
These mirrors reproduce those pure renderers over the same
`review_schemas` payloads; equivalence is pinned by
`shared/agent_kit/tests/test_ae_message_mirrors.py`, which renders both
ways and asserts byte-identical output — drift is a failing test, not a
silent divergence.

The functions are duck-typed over the orchestration invocation models
(`ReviewerInvocation`, `SynthesisInvocation`, `FacilitatorInvocation` in
`agent_clients.py`) and the agent_kit request models alike: identical
field names, so the equivalence test passes agent_kit requests straight
through.
"""

from __future__ import annotations


def render_reviewer_message(request) -> str:
    """Render a reviewer invocation into one labeled user message."""
    sections = [
        "## Story under review",
        "```json\n" + request.story.model_dump_json(indent=2) + "\n```",
    ]
    if request.previous_review is not None:
        sections += [
            "## Previous review of this story (re-review baseline)",
            "```json\n"
            + request.previous_review.model_dump_json(indent=2)
            + "\n```",
        ]
    if request.extra_context is not None:
        sections += [
            "## Extra context from the Product Owner",
            request.extra_context,
        ]
    sections += [
        "## Your task",
        "Produce the structured review of the story above, following your "
        "instructions.",
    ]
    return "\n\n".join(sections)


def render_synthesis_message(request) -> str:
    """Render a synthesis invocation into one labeled user message."""
    sections = []
    for label, pair in (
        ("Business review", request.business),
        ("Engineering review", request.engineering),
    ):
        sections += [
            f"## {label}",
            "```json\n" + pair.report.model_dump_json(indent=2) + "\n```",
            f"### Artifact reference for the {label.lower()} (echo unchanged in `inputs`)",
            "```json\n" + pair.reference.model_dump_json(indent=2) + "\n```",
        ]
    sections += [
        "## Your task",
        "Merge the two reviews above into one synthesis report, following "
        "your instructions. Echo the two supplied artifact references "
        "unchanged as your `inputs`.",
    ]
    return "\n\n".join(sections)


def render_facilitator_message(request) -> str:
    """Render a facilitator turn into one labeled user message."""
    story_id = request.synthesis_report.story_id
    story_run_id = request.synthesis_reference.story_run_id
    sections = [
        "## Turn context",
        f"Story under review: {story_id}. "
        f"Story run: {story_run_id}. "
        f"This is turn {request.turn_number}"
        + (
            " — the opening turn (no PO message yet)."
            if request.turn_number == 1
            else "."
        ),
    ]
    if request.po_message is not None:
        sections += ["## PO message", request.po_message]
    decision_state = request.decision_state
    if decision_state is not None and (
        decision_state.resolutions or decision_state.open_issues
    ):
        listed = "\n".join(
            f"- {item.issue}: {item.disposition} (turn {item.turn_number}) — "
            + item.explanation
            for item in decision_state.resolutions
        )
        open_listed = (
            ", ".join(decision_state.open_issues)
            if decision_state.open_issues
            else "none"
        )
        sections += [
            "## Current decision state",
            "Latest recorded disposition per issue (authoritative — reconcile "
            "against this, not the conversation):\n"
            + (listed if listed else "- none"),
            f"Currently open issues: {open_listed}",
        ]
    sections += [
        "## Latest synthesis report",
        "```json\n" + request.synthesis_report.model_dump_json(indent=2) + "\n```",
        "### Synthesis artifact reference",
        "```json\n"
        + request.synthesis_reference.model_dump_json(indent=2)
        + "\n```",
    ]
    if request.evidence_references:
        listed = "\n".join(
            f"- `{ref.artifact_id}` ({ref.type}"
            + (f", {ref.perspective}" if ref.perspective else "")
            + f", v{ref.version})"
            for ref in request.evidence_references
        )
        sections += [
            "## Artifact references available as evidence (this story run only)",
            listed,
        ]
    else:
        sections += [
            "## Artifact references available as evidence",
            "None — no artifacts are readable this turn.",
        ]
    sections += [
        "## Your task",
        "Produce this turn's `FacilitatorTurnOutput` following your "
        "instructions. Artifact reads are limited to the references listed "
        "above.",
    ]
    return "\n\n".join(sections)
