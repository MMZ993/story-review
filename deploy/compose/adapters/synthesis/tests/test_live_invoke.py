"""Real-model test of the synthesis adapter (main PC only, D13-1).

Calls the actual gemini-2.5-flash model through Vertex AI via the full
adapter path. Skipped unless AGENT_LIVE_TESTS=1 with the Vertex env present
— the dev server cannot run this.

Required case (Phase 5 plan increment 3): the hidden-conflict scenario —
two individually positive reviews (zero findings each) whose claims
contradict each other; synthesis must flag the contradiction as a conflict.
Second case: the single-perspective-re-review pairing (engineering is a
re-review with a previous version; business is the unchanged initial
artifact), mirroring how orchestration pairs artifacts after a re-review.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from agent_kit.prompts import load_prompt
from synthesis_adapter import create_app

pytestmark = pytest.mark.skipif(
    os.environ.get("AGENT_LIVE_TESTS") != "1"
    or not os.environ.get("GOOGLE_CLOUD_PROJECT"),
    reason="live agent gate: main PC with ADC + Vertex env only",
)

_REPO_ROOT = Path(__file__).resolve().parents[5]
PROMPTS = _REPO_ROOT / "prompts"

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


def report(perspective: str, story_id: str, summary: str, **overrides) -> dict:
    payload = {
        "perspective": perspective,
        "story_id": story_id,
        "summary": summary,
        "findings": [],
        "risks": [],
        "questions_for_po": [],
    }
    payload.update(overrides)
    return payload


@pytest.fixture(scope="module")
def app():
    return create_app()


async def invoke(client, request: dict):
    wire = json.loads(json.dumps(request, default=lambda o: o.isoformat()))
    response = await client.post("/invoke", json=wire)
    assert response.status_code == 200, response.text
    return response.json()


class TestLiveSynthesis:
    async def test_hidden_conflict_flagged_from_two_positive_reviews(self, app):
        """story-07 scenario: both reviews individually positive, but the
        business review describes payment reservation while the engineering
        review describes immediate capture — a contradiction synthesis must
        flag as a conflict with zero merged findings to carry it."""
        request = {
            "business": {
                "report": report(
                    "business",
                    "story-07",
                    "Strong story: a 30-minute order edit window gives "
                    "customers flexibility at no cost — payment is only "
                    "reserved at order placement and releasing it is free.",
                ),
                "reference": reference("business"),
            },
            "engineering": {
                "report": report(
                    "engineering",
                    "story-07",
                    "Clean implementation: the order edit window is "
                    "straightforward because payment is captured immediately "
                    "at order placement, so edits only adjust the follow-up "
                    "record.",
                ),
                "reference": reference("engineering"),
            },
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            body = await invoke(client, request)

        report_body = body["report"]
        assert report_body["story_id"] == "story-07"
        assert body["prompt_sha256"] == load_prompt(
            "synthesis", prompts_dir=PROMPTS
        ).sha256
        # the required behavior: a contradiction is flagged
        assert len(report_body["conflicts"]) >= 1
        conflict = report_body["conflicts"][0]
        assert conflict["business_refs"] and conflict["engineering_refs"]
        # positive reviews carry nothing to merge — findings stay empty
        assert report_body["merged_findings"] == []

    async def test_single_perspective_re_review_pairing(self, app):
        """After an engineering re-review, orchestration pairs the new
        engineering artifact with the unchanged business artifact; the
        engineering report resolves its earlier question (version 2)."""
        request = {
            "business": {
                "report": report(
                    "business",
                    "story-01",
                    "Well-scoped story with a measurable outcome.",
                ),
                "reference": reference("business", version=1),
            },
            "engineering": {
                "report": report(
                    "engineering",
                    "story-01",
                    "Re-review: the previously missing retry bound is now "
                    "specified; no open findings remain.",
                    previous_review_version=1,
                ),
                "reference": reference("engineering", version=2),
            },
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            body = await invoke(client, request)

        report_body = body["report"]
        assert report_body["story_id"] == "story-01"
        assert report_body["inputs"]["engineering"]["version"] == 2
        assert report_body["inputs"]["business"]["version"] == 1
        assert report_body["conflicts"] == []
