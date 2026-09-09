"""Tests for the reviewer invocation message renderer.

The renderer turns the frozen reviewer request fields (story, optional
previous review, optional PO extra context) into the single user message the
reviewer agents receive. It is pure and deterministic — no LLM involvement.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from agent_kit.reviewer_input import ReviewerRequest, render_reviewer_message
from review_schemas import StoryDetail


def make_story(story_id: str = "story-01") -> StoryDetail:
    return StoryDetail.model_validate(
        {
            "story_id": story_id,
            "title": "Invoice PDF in order confirmation email",
            "status": "New",
            "description": "Context: plain-text confirmations lack a price breakdown.",
            "acceptance_criteria": ["Email carries the invoice PDF within 2 minutes."],
            "epic_context": "Epic — Feature",
            "roadmap_context": "Roadmap text.",
            "comments": [],
            "context_stories": [],
        }
    )


def test_request_model_requires_story_and_rejects_unknown_fields():
    request = ReviewerRequest(story=make_story())
    assert request.previous_review is None
    assert request.extra_context is None

    with pytest.raises(ValidationError):
        ReviewerRequest.model_validate(
            {"story": make_story().model_dump(), "unexpected": 1}
        )


def test_message_contains_all_three_sections_when_present():
    request = ReviewerRequest(
        story=make_story(),
        previous_review=None,
        extra_context="PO: B2B only for now.",
    )

    message = render_reviewer_message(request)

    assert "## Story under review" in message
    assert "## Extra context from the Product Owner" in message
    assert "B2B only for now" in message
    assert "Invoice PDF" in message


def test_message_omits_absent_sections():
    message = render_reviewer_message(ReviewerRequest(story=make_story()))

    assert "Extra context" not in message
    assert "Previous review" not in message


def test_story_is_embedded_as_json():
    story = make_story()
    message = render_reviewer_message(ReviewerRequest(story=story))

    fence = message.split("## Story under review", 1)[1].split("```", 2)[1]
    embedded = json.loads(fence.split("\n", 1)[1].rsplit("\n", 1)[0])
    assert embedded == story.model_dump(mode="json")
