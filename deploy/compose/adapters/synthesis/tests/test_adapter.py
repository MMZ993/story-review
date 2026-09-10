"""Deterministic adapter tests for the synthesis binding.

Mirrors the reviewer adapter tests: pure assembly agreement checks and the
HTTP error boundary. No LLM is involved — the model path is covered by the
main-PC real-model tests (D13-1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from agent_kit.prompts import load_prompt
from agent_kit.synthesis_input import (
    SynthesisMismatchError,
    SynthesisRequest,
    assemble_synthesis_response,
)
from review_schemas import ReviewReport, SynthesisReport
from synthesis_adapter import create_app

_REPO_ROOT = Path(__file__).resolve().parents[5]
PROMPTS = _REPO_ROOT / "prompts"

AGENT_VERSION = "0.1.0"
RUN = "run-00000000-0000-0000-0000-000000000001"


def reference(perspective: str) -> dict:
    suffix = "01" if perspective == "business" else "02"
    return {
        "artifact_id": f"art-00000000-0000-0000-0000-0000000000{suffix}",
        "story_run_id": RUN,
        "type": f"review-{perspective}",
        "perspective": perspective,
        "version": 1,
        "created_at": datetime(2026, 9, 12, 10, 0, 0, tzinfo=timezone.utc),
        "content_type": "application/json",
        "checksum_sha256": "0" * 64,
        "is_latest": True,
    }


def report(perspective: str, story_id: str = "story-07") -> ReviewReport:
    return ReviewReport.model_validate(
        {
            "perspective": perspective,
            "story_id": story_id,
            "summary": f"{perspective} summary.",
            "findings": [],
            "risks": [],
            "questions_for_po": [],
        }
    )


def make_request() -> SynthesisRequest:
    return SynthesisRequest.model_validate(
        {
            "business": {
                "report": report("business").model_dump(),
                "reference": reference("business"),
            },
            "engineering": {
                "report": report("engineering").model_dump(),
                "reference": reference("engineering"),
            },
        }
    )


def make_synthesis(request: SynthesisRequest) -> SynthesisReport:
    return SynthesisReport.model_validate(
        {
            "story_id": "story-07",
            "summary": "Aligned with one conflict.",
            "merged_findings": [],
            "conflicts": [
                {
                    "id": "C-1",
                    "description": "Reservation vs immediate capture contradiction.",
                    "business_refs": ["B-1"],
                    "engineering_refs": ["E-1"],
                    "needs_po_clarification": True,
                }
            ],
            "questions_for_po": [],
            "resolved_from_previous": [],
            "inputs": {
                "business": request.business.reference.model_dump(),
                "engineering": request.engineering.reference.model_dump(),
            },
        }
    )


@pytest.fixture
def prompt():
    return load_prompt("synthesis", prompts_dir=PROMPTS)


class TestAssembly:
    def test_valid_report_is_stamped_with_version_and_prompt_hash(self, prompt):
        req = make_request()
        response = assemble_synthesis_response(
            make_synthesis(req), req, prompt, AGENT_VERSION
        )
        assert response.agent_version == AGENT_VERSION
        assert response.prompt_sha256 == prompt.sha256

    def test_wrong_story_id_rejected(self, prompt):
        req = make_request()
        payload = make_synthesis(req).model_dump()
        payload["story_id"] = "story-42"
        with pytest.raises(SynthesisMismatchError, match="story_id"):
            assemble_synthesis_response(
                SynthesisReport.model_validate(payload), req, prompt, AGENT_VERSION
            )

    def test_inputs_not_echoed_rejected(self, prompt):
        req = make_request()
        payload = make_synthesis(req).model_dump()
        payload["inputs"]["engineering"]["version"] = 9
        with pytest.raises(SynthesisMismatchError, match="inputs"):
            assemble_synthesis_response(
                SynthesisReport.model_validate(payload), req, prompt, AGENT_VERSION
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
            response = await client.post("/invoke", json={"business": {}})
        assert response.status_code == 400
        body = response.json()["error"]
        assert body["code"] == "VALIDATION_ERROR"
        assert body["retryable"] is False
        uuid.UUID(body["correlation_id"])

    async def test_cross_run_pairs_rejected_at_request_boundary(self):
        app = create_app()
        request = make_request().model_dump(mode="json")
        request["engineering"]["reference"]["story_run_id"] = RUN.replace(
            "000000000001", "000000000002"
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            response = await client.post("/invoke", json=request)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


class TestPromptDistinctness:
    def test_synthesis_prompt_differs_from_reviewer_prompts(self):
        business = load_prompt("business-reviewer", prompts_dir=PROMPTS)
        synthesis = load_prompt("synthesis", prompts_dir=PROMPTS)
        assert synthesis.sha256 != business.sha256
        assert "conflict" in synthesis.text.lower()
