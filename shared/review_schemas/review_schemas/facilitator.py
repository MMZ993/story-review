"""Facilitator models: delegation, resolutions, turns, and final state.

Implements the facilitator part of the domain section of
docs/design/schemas.md: `DelegationDecision`, `ResolutionItem`/`ResolutionDraft`,
`FacilitatorTurnOutput`, `FinalizedReview`, and `ConversationSummary`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from review_schemas.base import RunId, StoryId, StrictModel, Text, UtcDatetime
from review_schemas.synthesis import ArtifactReference


class DelegationDecision(StrictModel):
    """Facilitator's reviewer-invocation decision for the coming turn."""

    invoke: Literal["none", "business", "engineering", "both"] = "none"
    extra_context: Text | None = None
    reuse_previous: bool = False
    open_issues: list[Text] = Field(default_factory=list, max_length=100)
    readiness: Literal["needs_work", "review_requested", "ready"] = "needs_work"

    @model_validator(mode="after")
    def validate_combination(self):
        if self.reuse_previous and self.invoke != "none":
            raise ValueError("reuse_previous requires invoke=none")
        if self.invoke == "none" and self.extra_context is not None:
            raise ValueError("extra_context requires a reviewer invocation")
        return self


Disposition = Literal["resolved", "accepted", "unresolved", "reopened"]


class ResolutionItem(StrictModel):
    """Stamped resolution: the durable form of a facilitator resolution.

    `reopened` marks a regression: a previously resolved/accepted issue
    reappearing in `open_issues` (D18) — latest-wins aggregation makes the
    re-open override the earlier resolution.
    """

    issue: Text
    disposition: Disposition
    explanation: Text
    turn_number: Annotated[int, Field(ge=1)]


class ResolutionDraft(StrictModel):
    """Facilitator-emitted resolution update; orchestration stamps `turn_number`
    when converting it into a `ResolutionItem`."""

    issue: Text
    disposition: Disposition
    explanation: Text


def latest_resolutions(
    resolutions: list[ResolutionItem],
) -> list[ResolutionItem]:
    """Latest-wins aggregation per issue id, in first-seen order (D18).

    One shared implementation behind both the facilitator's per-turn
    decision state and `FinalizedReview.resolutions`, so the agent's turn
    context and the final report provably agree. Input order is turn
    order; the last occurrence of an issue id is its authoritative
    disposition.
    """
    latest: dict[str, ResolutionItem] = {}
    for item in resolutions:
        latest[item.issue] = item
    return list(latest.values())


class FacilitatorTurnOutput(StrictModel):
    """Authoritative typed output of one facilitator turn. Orchestration never
    parses the reply prose; every programmatically consumed field lives here."""

    reply: Text
    delegation: DelegationDecision
    resolutions: list[ResolutionDraft] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def resolutions_are_final(self):
        # dispositions are only meaningful once the PO has answered the opening
        # turn; turn 1 must emit none
        if self.delegation.invoke == "none" and self.delegation.reuse_previous:
            if self.resolutions:
                raise ValueError("re-synthesis-only turns carry no resolution updates")
        return self


class FinalizedReview(StrictModel):
    """The immutable end state of one story run."""

    story_id: StoryId
    story_run_id: RunId
    synthesis_reference: ArtifactReference
    resolutions: list[ResolutionItem] = Field(default_factory=list, max_length=200)
    remaining_open_issues: list[Text] = Field(default_factory=list, max_length=100)
    po_accepted: bool
    final_turn_number: Annotated[int, Field(ge=1)]
    finalized_at: UtcDatetime

    @model_validator(mode="after")
    def validate_final_state(self):
        if (
            self.synthesis_reference.type != "synthesis"
            or self.synthesis_reference.story_run_id != self.story_run_id
        ):
            raise ValueError("final review requires this run's synthesis reference")
        if self.remaining_open_issues and not self.po_accepted:
            raise ValueError("normal readiness cannot retain open issues")
        # D18 backstop: a resolved/accepted issue may only remain open if a
        # later `reopened` overrode it — otherwise the review is
        # self-contradictory and must not be finalized
        latest = {item.issue: item for item in self.resolutions}
        for issue in self.remaining_open_issues:
            if latest.get(issue) is not None and latest[issue].disposition in (
                "resolved",
                "accepted",
            ):
                raise ValueError(
                    "remaining open issue has a resolved/accepted latest "
                    f"disposition: {issue}"
                )
        return self


class ConversationSummary(StrictModel):
    """Recap of one facilitator session (parked or completed)."""

    story_id: StoryId
    story_run_id: RunId
    summary: Text
    unresolved_issues: list[Text] = Field(default_factory=list, max_length=100)
    decisions: list[Text] = Field(default_factory=list, max_length=100)
    artifact_references: list[ArtifactReference] = Field(
        default_factory=list,
        max_length=100,
    )
