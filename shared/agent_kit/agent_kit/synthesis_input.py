"""Synthesis invocation request model, message renderer, and assembly checks.

Implements the frozen synthesis part of the Phase 5 local-adapter invocation
contract (plan appendix): one typed single-turn request holding the latest
business and engineering pairs — each a `ReviewReport` plus its
`ArtifactReference`, both references from one story run — rendered into the
single user message the synthesis agent receives, plus the response
agreement checks applied at the adapter boundary. Pairing is
orchestration's job (Phase 6); the renderer adds nothing.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from agent_kit.prompts import LoadedPrompt
from review_schemas import ArtifactReference, ReviewReport, SynthesisReport
from review_schemas.base import Sha256, ShortText


class PerspectivePair(BaseModel):
    """One perspective's input: its latest review and that artifact's reference."""

    model_config = ConfigDict(extra="forbid")

    report: ReviewReport
    reference: ArtifactReference

    @model_validator(mode="after")
    def reference_matches_report(self):
        if self.reference.perspective != self.report.perspective:
            raise ValueError("reference perspective does not match report perspective")
        expected_type = f"review-{self.report.perspective}"
        if self.reference.type != expected_type:
            raise ValueError("reference type does not match report perspective")
        return self


class SynthesisRequest(BaseModel):
    """Typed single-turn synthesis invocation input (frozen contract)."""

    model_config = ConfigDict(extra="forbid")

    business: PerspectivePair
    engineering: PerspectivePair

    @model_validator(mode="after")
    def pairs_belong_together(self):
        if (
            self.business.report.story_id
            != self.engineering.report.story_id
        ):
            raise ValueError("both reports must be of one story")
        if (
            self.business.reference.story_run_id
            != self.engineering.reference.story_run_id
        ):
            raise ValueError("both references must belong to one story run")
        return self


class SynthesisResponse(BaseModel):
    """Typed single-turn synthesis invocation output (frozen contract)."""

    report: SynthesisReport
    agent_version: ShortText
    prompt_sha256: Sha256


class SynthesisMismatchError(Exception):
    """Model output disagrees with the request; mapped to a structured
    VALIDATION_ERROR by the HTTP shell (normal structured error path)."""


def render_synthesis_message(request: SynthesisRequest) -> str:
    """Render the request into one labeled user message; pure function.

    The input references are embedded verbatim so the model can echo them
    unchanged in its `inputs` field (required by the strict SynthesisReport
    schema and checked by `assemble_synthesis_response`).
    """
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


def assemble_synthesis_response(
    report: SynthesisReport,
    request: SynthesisRequest,
    prompt: LoadedPrompt,
    agent_version: str,
) -> SynthesisResponse:
    """Validate request/response agreement and stamp the adapter envelope.

    Raises SynthesisMismatchError when the model's story id or `inputs`
    echo disagrees with the supplied pair — the normal structured error
    path (no corrective re-prompt for synthesis, D13-3).
    """
    expected_story = request.business.report.story_id
    if report.story_id != expected_story:
        raise SynthesisMismatchError(
            f"report story_id {report.story_id!r} does not match the "
            f"reviewed story {expected_story!r}"
        )
    expected_refs = {
        "business": request.business.reference,
        "engineering": request.engineering.reference,
    }
    for perspective, echoed in report.inputs.items():
        if echoed != expected_refs[perspective]:
            raise SynthesisMismatchError(
                f"inputs.{perspective} does not echo the supplied "
                f"{perspective} artifact reference"
            )
    return SynthesisResponse(
        report=report,
        agent_version=agent_version,
        prompt_sha256=prompt.sha256,
    )
