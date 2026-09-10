"""Tests for the synthesis invocation request model and message renderer.

The frozen synthesis part of the Phase 5 adapter contract: the request is
the latest business and engineering pairs (each a ReviewReport plus its
ArtifactReference), both references from one story run; the renderer turns
it into the single user message the synthesis agent receives. Pure and
deterministic — no LLM involvement.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_kit.prompts import load_prompt
from agent_kit.synthesis_input import (
    SynthesisMismatchError,
    SynthesisRequest,
    SynthesisResponse,
    assemble_synthesis_response,
    render_synthesis_message,
)
from review_schemas import ReviewReport, SynthesisReport

_REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS = _REPO_ROOT.parent / "prompts"

RUN = "run-00000000-0000-0000-0000-000000000001"


def reference(perspective: str, version: int = 1) -> dict:
    suffix = "01" if perspective == "business" else "02"
    return {
        "artifact_id": f"art-00000000-0000-0000-0000-0000000000{suffix}",
        "story_run_id": RUN,
        "type": f"review-{perspective}",
        "perspective": perspective,
        "version": version,
        "created_at": datetime(2026, 9, 12, 10, 0, 0, tzinfo=timezone.utc),
        "content_type": "application/json",
        "checksum_sha256": "0" * 64,
        "is_latest": True,
    }


def report(perspective: str, story_id: str = "story-01", **overrides) -> ReviewReport:
    payload = {
        "perspective": perspective,
        "story_id": story_id,
        "summary": f"{perspective} summary.",
        "findings": [],
        "risks": [],
        "questions_for_po": [],
    }
    payload.update(overrides)
    return ReviewReport.model_validate(payload)


def make_request(business_ref=None, engineering_ref=None) -> SynthesisRequest:
    return SynthesisRequest.model_validate(
        {
            "business": {
                "report": report("business").model_dump(),
                "reference": business_ref or reference("business"),
            },
            "engineering": {
                "report": report("engineering").model_dump(),
                "reference": engineering_ref or reference("engineering"),
            },
        }
    )


class TestRequestModel:
    def test_valid_pairs_parse(self):
        request = make_request()
        assert request.business.reference.story_run_id == RUN

    def test_reports_must_share_one_story(self):
        payload = make_request().model_dump()
        payload["engineering"]["report"]["story_id"] = "story-42"
        with pytest.raises(ValidationError, match="one story"):
            SynthesisRequest.model_validate(payload)

    def test_references_must_belong_to_one_run(self):
        other = reference("engineering")
        other["story_run_id"] = RUN.replace("0001", "0002")
        with pytest.raises(ValidationError, match="one story run"):
            SynthesisRequest.model_validate(
                {
                    "business": {
                        "report": report("business").model_dump(),
                        "reference": reference("business"),
                    },
                    "engineering": {
                        "report": report("engineering").model_dump(),
                        "reference": other,
                    },
                }
            )

    def test_report_perspective_must_match_slot(self):
        payload = make_request().model_dump()
        payload["business"]["report"]["perspective"] = "engineering"
        with pytest.raises(ValidationError):
            SynthesisRequest.model_validate(payload)

    def test_unknown_fields_rejected(self):
        payload = make_request().model_dump()
        payload["unexpected"] = 1
        with pytest.raises(ValidationError):
            SynthesisRequest.model_validate(payload)


class TestRenderer:
    def test_message_contains_both_reports_and_references(self):
        message = render_synthesis_message(make_request())
        assert "## Business review" in message
        assert "## Engineering review" in message
        assert "## Your task" in message

    def test_reports_embedded_as_json(self):
        message = render_synthesis_message(make_request())
        fence = message.split("## Business review", 1)[1].split("```", 2)[1]
        embedded = json.loads(fence.split("\n", 1)[1].rsplit("\n", 1)[0])
        assert embedded["perspective"] == "business"


class TestAssembly:
    def make_synthesis(self, **overrides) -> SynthesisReport:
        request = make_request()
        payload = {
            "story_id": "story-01",
            "summary": "Aligned.",
            "merged_findings": [],
            "conflicts": [],
            "questions_for_po": [],
            "resolved_from_previous": [],
            "inputs": {
                "business": request.business.reference.model_dump(),
                "engineering": request.engineering.reference.model_dump(),
            },
        }
        payload.update(overrides)
        return SynthesisReport.model_validate(payload)

    def test_valid_report_is_stamped(self):
        request = make_request()
        prompt = load_prompt("synthesis", prompts_dir=PROMPTS)
        response = assemble_synthesis_response(
            self.make_synthesis(), request, prompt, "0.1.0"
        )
        assert isinstance(response, SynthesisResponse)
        assert response.agent_version == "0.1.0"
        assert response.prompt_sha256 == prompt.sha256

    def test_wrong_story_id_rejected(self):
        prompt = load_prompt("synthesis", prompts_dir=PROMPTS)
        with pytest.raises(SynthesisMismatchError, match="story_id"):
            assemble_synthesis_response(
                self.make_synthesis(story_id="story-42"),
                make_request(),
                prompt,
                "0.1.0",
            )

    def test_inputs_must_echo_supplied_references(self):
        prompt = load_prompt("synthesis", prompts_dir=PROMPTS)
        payload = self.make_synthesis().model_dump()
        payload["inputs"]["business"]["version"] = 7
        with pytest.raises(SynthesisMismatchError, match="inputs"):
            assemble_synthesis_response(
                SynthesisReport.model_validate(payload), make_request(), prompt, "0.1.0"
            )
