"""Facilitator invocation request model, message renderer, and turn-output
validation.

Implements the frozen facilitator part of the Phase 5 local-adapter
invocation contract (plan appendix): a session-scoped turn request holding
`session_id`, `turn_number`, the PO message when applicable, the latest
synthesis report plus its `ArtifactReference`, and the lineage-scoped
`ArtifactReference` values available for evidence reads. Also defines the
turn-context rules the adapter enforces beyond the strict shared model
(opening turn = `invoke=none` and no resolutions) — a violation is
malformed delegation output and enters the bounded corrective re-prompt
loop (D13-3), not the normal structured-error path.

Note: `FacilitatorResponse` additionally reports `corrective_reprompts`
(0–2, observability.md) — a recorded extension of the frozen envelope so
orchestration can persist the counter in `AgentRunRecord`.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent_kit.prompts import LoadedPrompt
from review_schemas import ArtifactReference, FacilitatorTurnOutput, SynthesisReport
from review_schemas.base import SessionId, Sha256, ShortText, Text


class FacilitatorRequest(BaseModel):
    """Typed session-scoped facilitator turn input (frozen contract).

    The PO dialogue rules of data-flow.md §2 are enforced here: one PO
    message = one request; the opening turn (turn 1) carries no PO message
    and every later turn carries exactly one.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: SessionId
    turn_number: Annotated[int, Field(ge=1, le=10)]
    po_message: Text | None = None
    synthesis_report: SynthesisReport
    synthesis_reference: ArtifactReference
    evidence_references: list[ArtifactReference] = Field(default_factory=list)

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
    `FacilitatorTurnInvalid` (corrective re-prompt path)."""
    if request.turn_number == 1:
        if output.delegation.invoke != "none":
            raise FacilitatorTurnInvalid(
                "the opening turn must emit delegation.invoke = none"
            )
        if output.resolutions:
            raise FacilitatorTurnInvalid(
                "the opening turn must not emit resolution updates"
            )
