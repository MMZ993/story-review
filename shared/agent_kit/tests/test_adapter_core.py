"""Tests for the shared reviewer-adapter core (generic over perspective).

The same frozen single-turn reviewer contract serves both reviewers; the
core is parameterized by (slug, perspective, agent builder). These tests
pin the generic behavior: agreement checks, envelope stamping, error
mapping, and that the assembled app is per-perspective correct.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from agent_kit.adapter import (
    ReportMismatchError,
    ReviewerResponse,
    assemble_response,
)
from review_schemas import ReviewReport

AGENT_VERSION = "0.1.0"


def make_story() -> dict:
    return {
        "story_id": "story-14",
        "title": "Automatic payment retry on PSP failure",
        "status": "New",
        "description": "Context: transient PSP failures drop payments.",
        "acceptance_criteria": ["Retries run at most 3 times with backoff."],
        "epic_context": "Epic — Feature",
        "roadmap_context": "Roadmap text.",
        "comments": [],
        "context_stories": [],
    }


def make_report(**overrides) -> ReviewReport:
    payload = {
        "perspective": "engineering",
        "story_id": "story-14",
        "summary": "Technically under-specified retry story.",
        "findings": [
            {
                "id": "E-1",
                "title": "Backoff bounds undefined",
                "description": "No maximum delay or jitter is specified.",
                "severity": "major",
                "category": "edge-case",
            }
        ],
        "risks": [],
        "questions_for_po": [],
    }
    payload.update(overrides)
    return ReviewReport.model_validate(payload)


class FakePrompt:
    slug = "engineering-reviewer"
    text = "instruction"
    sha256 = "0" * 64


@pytest.fixture
def prompt():
    return FakePrompt()


def test_assemble_stamps_envelope_for_matching_report(prompt):
    request = make_request()
    response = assemble_response(
        make_report(), request, prompt, AGENT_VERSION, perspective="engineering"
    )
    assert response.agent_version == AGENT_VERSION
    assert response.prompt_sha256 == prompt.sha256


def test_foreign_perspective_rejected(prompt):
    request = make_request()
    with pytest.raises(ReportMismatchError, match="perspective"):
        assemble_response(
            make_report(perspective="business", findings=[]),
            request,
            prompt,
            AGENT_VERSION,
            perspective="engineering",
        )


def test_story_echo_and_version_rules_enforced(prompt):
    request = make_request()
    with pytest.raises(ReportMismatchError, match="story_id"):
        assemble_response(
            make_report(story_id="story-01"),
            request,
            prompt,
            AGENT_VERSION,
            perspective="engineering",
        )
    with pytest.raises(ReportMismatchError, match="previous_review_version"):
        assemble_response(
            make_report(previous_review_version=1),
            request,
            prompt,
            AGENT_VERSION,
            perspective="engineering",
        )


def make_request():
    from agent_kit.reviewer_input import ReviewerRequest

    return ReviewerRequest.model_validate({"story": make_story()})
