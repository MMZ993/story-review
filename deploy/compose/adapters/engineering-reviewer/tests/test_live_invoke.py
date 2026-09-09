"""Real-model test of the engineering-reviewer adapter (main PC only, D13-1).

Calls the actual gemini-2.5-flash model through Vertex AI via the full
adapter path. Skipped unless AGENT_LIVE_TESTS=1 with the Vertex env present
— the dev server cannot run this. Uses golden story-14 (engineering-weak
scenario) so the engineering perspective has real material to find.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from agent_kit.prompts import load_prompt
from engineering_reviewer_adapter import create_app

pytestmark = pytest.mark.skipif(
    os.environ.get("AGENT_LIVE_TESTS") != "1"
    or not os.environ.get("GOOGLE_CLOUD_PROJECT"),
    reason="live agent gate: main PC with ADC + Vertex env only",
)

_REPO_ROOT = Path(__file__).resolve().parents[5]
GOLDEN_STORY = (
    _REPO_ROOT / "mcp_servers" / "story" / "tests" / "golden" / "story-14.json"
)


@pytest.fixture(scope="module")
def story_payload() -> dict:
    return json.loads(GOLDEN_STORY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def app():
    return create_app()


class TestLiveEngineeringReviewer:
    async def test_t1_story_yields_schema_valid_engineering_report(
        self, app, story_payload
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post("/invoke", json={"story": story_payload})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["report"]["perspective"] == "engineering"
        assert body["report"]["story_id"] == story_payload["story_id"]
        assert body["prompt_sha256"] == load_prompt(
            "engineering-reviewer", prompts_dir=_REPO_ROOT / "prompts"
        ).sha256
        # sanity: engineering-weak scenario must surface at least one finding
        assert len(body["report"]["findings"]) >= 1
