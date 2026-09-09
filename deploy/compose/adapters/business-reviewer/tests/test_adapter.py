"""Deterministic adapter tests: pure assembly agreement checks and the HTTP
error boundary. No LLM is involved — the model path is covered by the
main-PC real-model tests (D13-1)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from agent_kit.prompts import load_prompt
from agent_kit.reviewer_input import ReviewerRequest
from business_reviewer_adapter.app import create_app
from business_reviewer_adapter.assembly import (
    ReportMismatchError,
    assemble_response,
)
from review_schemas import ReviewReport

_REPO_ROOT = Path(__file__).resolve().parents[5]
PROMPTS = _REPO_ROOT / "prompts"

AGENT_VERSION = "0.1.0"


def make_story() -> dict:
    return {
        "story_id": "story-01",
        "title": "Invoice PDF in order confirmation email",
        "status": "New",
        "description": "Context: plain-text confirmation without prices.",
        "acceptance_criteria": ["Email carries the invoice PDF within 2 minutes."],
        "epic_context": "Epic — Feature",
        "roadmap_context": "Roadmap text.",
        "comments": [],
        "context_stories": [],
    }


def make_report(**overrides) -> ReviewReport:
    payload = {
        "perspective": "business",
        "story_id": "story-01",
        "summary": "Solid, well-scoped business story.",
        "findings": [
            {
                "id": "B-1",
                "title": "Success metric missing",
                "description": "No measurable business outcome is stated.",
                "severity": "minor",
                "category": "business-justification",
            }
        ],
        "risks": [],
        "questions_for_po": [],
    }
    payload.update(overrides)
    return ReviewReport.model_validate(payload)


def make_request() -> ReviewerRequest:
    return ReviewerRequest.model_validate({"story": make_story()})


@pytest.fixture
def prompt():
    return load_prompt("business-reviewer", prompts_dir=PROMPTS)


class TestAssembly:
    def test_valid_report_is_stamped_with_version_and_prompt_hash(self, prompt):
        request = make_request()
        response = assemble_response(make_report(), request, prompt, AGENT_VERSION)

        assert response.agent_version == AGENT_VERSION
        assert response.prompt_sha256 == prompt.sha256
        assert response.report.story_id == "story-01"

    def test_wrong_perspective_rejected(self, prompt):
        request = make_request()
        with pytest.raises(ReportMismatchError, match="perspective"):
            assemble_response(
                make_report(perspective="engineering", findings=[]),
                request,
                prompt,
                AGENT_VERSION,
            )

    def test_wrong_story_id_rejected(self, prompt):
        request = make_request()
        with pytest.raises(ReportMismatchError, match="story_id"):
            assemble_response(
                make_report(story_id="story-42"), request, prompt, AGENT_VERSION
            )

    def test_version_without_previous_review_rejected(self, prompt):
        request = make_request()
        with pytest.raises(ReportMismatchError, match="previous_review_version"):
            assemble_response(
                make_report(previous_review_version=1), request, prompt, AGENT_VERSION
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
