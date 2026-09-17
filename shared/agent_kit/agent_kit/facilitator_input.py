"""Facilitator invocation request model, message renderer, and turn-output
validation.

Implements the frozen facilitator part of the Phase 5 local-adapter
invocation contract (plan appendix): a session-scoped turn request holding
`session_id`, `turn_number`, the PO message when applicable, the latest
synthesis report plus its `ArtifactReference`, and the lineage-scoped
`ArtifactReference` values available for evidence reads. Also defines the
turn-context rules the adapter enforces beyond the strict shared model
(opening turn: `invoke=none` + the D34 severity fence — turn-1
resolutions only for `info`/`minor` synthesis findings) — a violation is
malformed delegation output and enters the bounded corrective re-prompt
loop (D13-3), not the normal structured-error path.

Note: `FacilitatorResponse` additionally reports `corrective_reprompts`
(0–2, observability.md) — a recorded extension of the frozen envelope so
orchestration can persist the counter in `AgentRunRecord`.

Recorded Phase 6 extension (D15-6): the request carries `invocation_id`,
and the adapter persists one completed result per (session_id,
invocation_id) in its session backend and exposes it via
`GET /turn-result/{session_id}/{invocation_id}` — the reconciliation seam
for ambiguous facilitator timeouts (observability.md). A repeated
`POST /turn` for an already-completed invocation returns the stored
result without invoking the model.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent_kit.prompts import LoadedPrompt
from review_schemas import ArtifactReference, FacilitatorTurnOutput, SynthesisReport
from review_schemas.base import SessionId, Sha256, ShortText, Text
from review_schemas.facilitator import ResolutionItem


class DecisionState(BaseModel):
    """Authoritative state of all decisions so far (D18), assembled by
    orchestration from the durable TurnRecords: the latest-wins resolution
    map (one `ResolutionItem` per issue id) plus the last delegation's open
    list. Rendered into the turn message so the facilitator reconciles
    against recorded state instead of reconstructing it from prose; `None`
    means no prior decisions (opening turn or a pre-D18 caller)."""

    model_config = ConfigDict(extra="forbid")

    resolutions: list[ResolutionItem] = Field(default_factory=list, max_length=200)
    open_issues: list[Text] = Field(default_factory=list, max_length=100)


class FacilitatorRequest(BaseModel):
    """Typed session-scoped facilitator turn input (frozen contract).

    The PO dialogue rules of data-flow.md §2 are enforced here: one PO
    message = one request; the opening turn (turn 1) carries no PO message
    and every later turn carries exactly one.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: SessionId
    turn_number: Annotated[int, Field(ge=1, le=10)]
    invocation_id: uuid.UUID
    po_message: Text | None = None
    synthesis_report: SynthesisReport
    synthesis_reference: ArtifactReference
    evidence_references: list[ArtifactReference] = Field(default_factory=list)
    decision_state: DecisionState | None = None

    @model_validator(mode="after")
    def turn_and_message_agree(self):
        if self.turn_number == 1 and self.po_message is not None:
            raise ValueError("the opening turn carries no po_message")
        if self.turn_number > 1 and self.po_message is None:
            raise ValueError("po_message is required from turn 2 onward")
        if self.synthesis_reference.type != "synthesis":
            raise ValueError("synthesis_reference must reference a synthesis artifact")
        lineage = {ref.story_run_id for ref in self.evidence_references}
        lineage.add(self.synthesis_reference.story_run_id)
        if len(lineage) > 1:
            raise ValueError("evidence references must belong to the synthesis run")
        return self

    @property
    def story_id(self) -> str:
        """The story under review, from the synthesis report."""
        return self.synthesis_report.story_id

    @property
    def story_run_id(self) -> str:
        """The lineage every artifact read is scoped to."""
        return self.synthesis_reference.story_run_id


class FacilitatorResponse(BaseModel):
    """Typed session-scoped facilitator turn output (frozen contract +
    `corrective_reprompts` counter)."""

    output: FacilitatorTurnOutput
    agent_version: ShortText
    prompt_sha256: Sha256
    corrective_reprompts: Annotated[int, Field(ge=0, le=2)] = 0


class FacilitatorTurnInvalid(Exception):
    """The model's turn output violates the turn-context rules; retried via
    the bounded corrective re-prompt loop, exhaustion →
    `DELEGATION_VALIDATION`."""


def render_facilitator_message(request: FacilitatorRequest) -> str:
    """Render the turn into one labeled user message; pure function.

    The synthesis report and every artifact reference are embedded verbatim
    so the model can ground its reply and echo lineage-legal ids in tool
    calls; the renderer adds no rules beyond factual labels — behavioural
    rules live in the prompt.
    """
    sections = [
        f"## Turn context",
        f"Story under review: {request.story_id}. "
        f"Story run: {request.story_run_id}. "
        f"This is turn {request.turn_number}"
        + (
            " — the opening turn (no PO message yet)."
            if request.turn_number == 1
            else "."
        ),
    ]
    if request.po_message is not None:
        sections += ["## PO message", request.po_message]
    if request.decision_state is not None and (
        request.decision_state.resolutions or request.decision_state.open_issues
    ):
        state = request.decision_state
        listed = "\n".join(
            f"- {item.issue}: {item.disposition} (turn {item.turn_number}) — "
            + item.explanation
            for item in state.resolutions
        )
        open_listed = ", ".join(state.open_issues) if state.open_issues else "none"
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


def validate_turn_output(
    output: FacilitatorTurnOutput, request: FacilitatorRequest
) -> None:
    """Enforce the turn-context rules beyond the strict model; raises
    `FacilitatorTurnInvalid` (corrective re-prompt path).

    Opening turn (D34): `invoke` must be `none`; resolutions are allowed
    only as severity-fenced housekeeping — `resolved` dispositions for
    synthesis findings of severity `info`/`minor` (mentioned to the PO as
    observations). Conflicts, `major`/`blocker` findings, minted ids, and
    PO-dependent dispositions (`accepted`, `reopened`, `unresolved`)
    need a PO turn first.
    """
    if request.turn_number == 1:
        if output.delegation.invoke != "none":
            raise FacilitatorTurnInvalid(
                "the opening turn must emit delegation.invoke = none"
            )
        _validate_opening_fence(output, request)
    if request.decision_state is not None:
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
                raise FacilitatorTurnInvalid(
                    f"issue {issue} was {recorded.disposition} at turn "
                    f"{recorded.turn_number} — re-appearing in open_issues "
                    "requires a reopened disposition this turn (identifiers "
                    "are immutable; a new concern gets a fresh id)"
                )
        # same-turn self-contradiction: an id resolved or accepted this
        # turn must not simultaneously be on this turn's open list
        settled_now = {
            draft.issue
            for draft in output.resolutions
            if draft.disposition in ("resolved", "accepted")
        }
        for issue in settled_now.intersection(output.delegation.open_issues):
            raise FacilitatorTurnInvalid(
                f"issue {issue} is resolved this turn but still listed in "
                "open_issues — a turn cannot settle and retain the same "
                "issue; either drop it from open_issues or re-open it later"
            )
    _validate_issue_descriptors(output, request)


def _validate_opening_fence(
    output: FacilitatorTurnOutput, request: FacilitatorRequest
) -> None:
    """D34 severity fence for turn-1 resolutions: only `resolved`
    dispositions for `info`/`minor` synthesis findings pass."""
    fenceable = {
        finding.id
        for finding in request.synthesis_report.merged_findings
        if finding.severity in ("info", "minor")
    }
    for draft in output.resolutions:
        if draft.disposition != "resolved" or draft.issue not in fenceable:
            raise FacilitatorTurnInvalid(
                f"opening-turn severity fence: issue {draft.issue} with "
                f"disposition {draft.disposition!r} may not be resolved on "
                "turn 1 — only info/minor synthesis findings with a "
                "`resolved` disposition may be settled before the PO's "
                "first answer; leave it for a later turn"
            )


def _synthesis_issue_ids(request: FacilitatorRequest) -> set[str]:
    """Ids born in the latest synthesis: findings (B-*/E-*) and
    conflicts (C-*) — they already carry title/description there."""
    return (
        {finding.id for finding in request.synthesis_report.merged_findings}
        | {conflict.id for conflict in request.synthesis_report.conflicts}
    )


def _validate_issue_descriptors(
    output: FacilitatorTurnOutput, request: FacilitatorRequest
) -> None:
    """D19: every id the facilitator mints (not synthesis-born, not
    previously seen in the decision state) must carry an IssueDraft on
    the same turn it first appears in open_issues."""
    known: set[str] = _synthesis_issue_ids(request)
    if request.decision_state is not None:
        known |= {item.issue for item in request.decision_state.resolutions}
        known |= set(request.decision_state.open_issues)
    described = {draft.issue for draft in output.new_issues}
    for issue in output.delegation.open_issues:
        if issue not in known and issue not in described:
            raise FacilitatorTurnInvalid(
                f"issue {issue} is newly minted — it needs an IssueDraft in "
                f'new_issues this turn, e.g. "new_issues": [{{"issue": '
                f'"{issue}", "title": "...", "description": "..."}}] '
                "(synthesis-born ids must not be re-described)"
            )
