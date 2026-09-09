"""Deterministic adapter tests for the engineering-reviewer binding.

Mirrors the business-reviewer adapter tests: pure assembly agreement checks
(engineering perspective) and the HTTP error boundary. No LLM is involved
— the model path is covered by the main-PC real-model tests (D13-1)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from agent_kit.adapter import ReportMismatchError, assemble_response
from agent_kit.prompts import load_prompt
from engineering_reviewer_adapter import create_app
from review_schemas import ReviewReport

_REPO_ROOT = Path(__file__).resolve().parents[5]
PROMPTS = _REPO_ROOT / "prompts"

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
        "summary": "Retry behavior is under-specified.",
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


def make_request():
    from agent_kit.reviewer_input import ReviewerRequest

    return ReviewerRequest.model_validate({"story": make_story()})


@pytest.fixture
def prompt():
    return load_prompt("engineering-reviewer", prompts_dir=PROMPTS)


class TestAssembly:
    def test_valid_report_is_stamped_with_version_and_prompt_hash(self, prompt):
        response = assemble_response(
            make_report(), make_request(), prompt, AGENT_VERSION,
            perspective="engineering",
        )
        assert response.agent_version == AGENT_VERSION
        assert response.prompt_sha256 == prompt.sha256

    def test_wrong_perspective_rejected(self, prompt):
        with pytest.raises(ReportMismatchError, match="perspective"):
            assemble_response(
                make_report(perspective="business", findings=[]),
                make_request(),
                prompt,
                AGENT_VERSION,
                perspective="engineering",
            )

    def test_wrong_story_id_rejected(self, prompt):
        with pytest.raises(ReportMismatchError, match="story_id"):
            assemble_response(
                make_report(story_id="story-42"), make_request(), prompt,
                AGENT_VERSION, perspective="engineering",
            )

    def test_version_without_previous_review_rejected(self, prompt):
        with pytest.raises(ReportMismatchError, match="previous_review_version"):
            assemble_response(
                make_report(previous_review_version=1), make_request(), prompt,
                AGENT_VERSION, perspective="engineering",
            )


class TestHttpBoundary:
    async def test_health_reports_agent_version(self):
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_invalid_request_body_is_error_envelope(self):
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            response = await client.post("/invoke", json={"story": {"story_id": "x"}})
        assert response.status_code == 400
        body = response.json()["error"]
        assert body["code"] == "VALIDATION_ERROR"
        assert body["retryable"] is False
        uuid.UUID(body["correlation_id"])


class TestPromptDistinctness:
    def test_engineering_prompt_differs_from_business_prompt(self):
        business = load_prompt("business-reviewer", prompts_dir=PROMPTS)
        engineering = load_prompt("engineering-reviewer", prompts_dir=PROMPTS)
        assert engineering.sha256 != business.sha256
        assert "engineering-perspective reviewer" in engineering.text.lower()
