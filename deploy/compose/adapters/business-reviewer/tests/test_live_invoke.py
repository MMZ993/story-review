"""Real-model test of the business-reviewer adapter (main PC only, D13-1).

Calls the actual gemini-2.5-flash model through Vertex AI via the full
adapter path (prompt + config + ADK output_schema + assembly). Skipped
unless the live gate is explicitly enabled via AGENT_LIVE_TESTS=1 with the
Vertex env vars present — the dev server cannot run this.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from agent_kit.prompts import load_prompt
from business_reviewer_adapter import create_app

pytestmark = pytest.mark.skipif(
    os.environ.get("AGENT_LIVE_TESTS") != "1"
    or not os.environ.get("GOOGLE_CLOUD_PROJECT"),
    reason="live agent gate: main PC with ADC + Vertex env only",
)

_REPO_ROOT = Path(__file__).resolve().parents[5]
GOLDEN_STORY = (
    _REPO_ROOT / "mcp_servers" / "story" / "tests" / "golden" / "story-01.json"
)


@pytest.fixture(scope="module")
def story_payload() -> dict:
    return json.loads(GOLDEN_STORY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def app():
    return create_app()


class TestLiveBusinessReviewer:
    async def test_t1_story_yields_schema_valid_business_report(
        self, app, story_payload
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post(
                "/invoke", json={"story": story_payload}
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["report"]["perspective"] == "business"
        assert body["report"]["story_id"] == story_payload["story_id"]
        assert body["agent_version"]
        assert body["prompt_sha256"] == load_prompt(
            "business-reviewer", prompts_dir=_REPO_ROOT / "prompts"
        ).sha256
        # sanity: the model actually reviewed this story's content
        summary = body["report"]["summary"].lower()
        assert "invoice" in summary or "email" in summary

    async def test_extra_context_is_carried_into_the_report(
        self, app, story_payload
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post(
                "/invoke",
                json={
                    "story": story_payload,
                    "extra_context": "PO clarification: this feature targets "
                    "B2B customers only in the first release.",
                },
            )

        assert response.status_code == 200, response.text
        report = response.json()["report"]
        assert report["based_on_extra_context"] is not None
