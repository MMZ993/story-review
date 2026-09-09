"""Reviewer invocation request model and user-message rendering.

Implements the frozen reviewer part of the Phase 5 local-adapter invocation
contract (plan appendix): one typed single-turn request per reviewer
(`story` with linked context stories, optional `previous_review`, optional
PO `extra_context`) rendered into the single user message the ADK agent
receives. Orchestration owns input assembly; the renderer adds nothing.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from review_schemas import ReviewReport, StoryDetail


class ReviewerRequest(BaseModel):
    """Typed single-turn reviewer invocation input (frozen contract)."""

    model_config = ConfigDict(extra="forbid")

    story: StoryDetail
    previous_review: ReviewReport | None = None
    extra_context: str | None = None


def render_reviewer_message(request: ReviewerRequest) -> str:
    """Render the request into one labeled user message; pure function."""
    sections = [
        "## Story under review",
        "```json\n"
        + request.story.model_dump_json(indent=2)
        + "\n```",
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
