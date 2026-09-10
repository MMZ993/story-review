"""Phase 5 exit gate: example-interaction walkthrough over compose HTTP
(main PC only, D13-1).

Replays the conflict-resolution arc of docs/design/example-interaction.md
(story-05, partial-resolution scenario) against the RUNNING local-agents
compose stack: this test stands in for Phase-6 orchestration only — it
drives the four adapter services over real HTTP, saves reviewer artifacts
to the artifact MCP server (so the facilitator's lineage-scoped evidence
reads are real), and asserts the facilitator's delegation arc:

- turn 1 (opening): `invoke = none`, no resolutions;
- turn 2 (PO clarifies): a reviewer delegation (engineering or both) with
  `extra_context`, mirrored single-perspective re-review + re-synthesis
  pairing the untouched business artifact;
- turn 3 (PO resolves conversationally): `invoke = none` and at least one
  resolution draft.

Skipped unless AGENT_LIVE_TESTS=1 and the adapter URLs answer /health —
requires `make agents-compose-up` and ADC + Vertex env (main PC).
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

pytestmark = pytest.mark.skipif(
    os.environ.get("AGENT_LIVE_TESTS") != "1",
    reason="live agent gate: main PC with the local-agents compose stack",
)

_REPO_ROOT = Path(__file__).resolve().parents[5]
GOLDEN_STORY = (
    _REPO_ROOT / "mcp_servers" / "story" / "tests" / "golden" / "story-05.json"
)

BUSINESS_URL = os.environ.get("BUSINESS_REVIEWER_URL", "http://127.0.0.1:8111")
ENGINEERING_URL = os.environ.get("ENGINEERING_REVIEWER_URL", "http://127.0.0.1:8112")
SYNTHESIS_URL = os.environ.get("SYNTHESIS_URL", "http://127.0.0.1:8113")
FACILITATOR_URL = os.environ.get("FACILITATOR_URL", "http://127.0.0.1:8114")
ARTIFACT_MCP_URL = os.environ.get("ARTIFACT_MCP_URL", "http://127.0.0.1:8102/mcp")

STORY_ID = "story-05"


def _require_stack():
    """Fail loud (not skip) when the gate is enabled but the stack is down."""
    for url in (BUSINESS_URL, ENGINEERING_URL, SYNTHESIS_URL, FACILITATOR_URL):
        try:
            assert httpx.get(f"{url}/health", timeout=5).status_code == 200
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                f"adapter not reachable at {url} — run `make agents-compose-up`"
            ) from exc


@pytest.fixture(scope="module")
def story() -> dict:
    return json.loads(GOLDEN_STORY.read_text(encoding="utf-8"))


def invoke_reviewer(
    url: str, story: dict, extra: dict | None = None, previous: dict | None = None
) -> dict:
    body = {"story": story, "previous_review": previous, "extra_context": extra}
    resp = httpx.post(f"{url}/invoke", json=body, timeout=300)
    assert resp.status_code == 200, resp.text
    return resp.json()["report"]


def save_artifact(artifact_type: str, run_id: str, perspective, content: dict) -> dict:
    """Orchestration stand-in: persist a review artifact, get its reference."""

    async def run() -> dict:
        async with streamable_http_client(ARTIFACT_MCP_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "save_artifact",
                    {
                        "type": artifact_type,
                        "story_run_id": run_id,
                        "perspective": perspective,
                        "content": content,
                        "idempotency_key": str(uuid.uuid4()),
                    },
                )
                assert not result.isError, result.content
                return dict(result.structuredContent)["reference"]

    return asyncio.run(run())


def invoke_synthesis(business: dict, engineering: dict) -> dict:
    body = {
        "business": {"report": business["report"], "reference": business["reference"]},
        "engineering": {
            "report": engineering["report"],
            "reference": engineering["reference"],
        },
    }
    resp = httpx.post(f"{SYNTHESIS_URL}/invoke", json=body, timeout=300)
    assert resp.status_code == 200, resp.text
    return resp.json()["report"]


def facilitator_turn(
    session_id: str,
    turn_number: int,
    po_message: str | None,
    synthesis: dict,
    synthesis_reference: dict,
    evidence: list[dict],
) -> dict:
    body = {
        "session_id": session_id,
        "turn_number": turn_number,
        "po_message": po_message,
        "synthesis_report": synthesis,
        "synthesis_reference": synthesis_reference,
        "evidence_references": evidence,
    }
    resp = httpx.post(f"{FACILITATOR_URL}/turn", json=body, timeout=600)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["output"]["delegation"]["invoke"] is not None
    return payload


class TestExampleInteractionWalkthrough:
    def test_full_arc(self, story):
        _require_stack()
        run_id = f"run-{uuid.uuid4()}"
        session_id = f"sess-{uuid.uuid4()}"

        # --- initial parallel review (example §1) -------------------------
        business_report = invoke_reviewer(BUSINESS_URL, story)
        engineering_report = invoke_reviewer(ENGINEERING_URL, story)
        assert business_report["perspective"] == "business"
        assert engineering_report["perspective"] == "engineering"
        for report in (business_report, engineering_report):
            assert report["story_id"] == STORY_ID

        business = {
            "report": business_report,
            "reference": save_artifact(
                "review-business", run_id, "business", business_report
            ),
        }
        engineering = {
            "report": engineering_report,
            "reference": save_artifact(
                "review-engineering", run_id, "engineering", engineering_report
            ),
        }

        # --- synthesis detects the conflict (example §2) ------------------
        synthesis = invoke_synthesis(business, engineering)
        assert synthesis["story_id"] == STORY_ID
        synthesis_reference = save_artifact(
            "synthesis", run_id, None, synthesis
        )

        # --- facilitator opening turn (example §2) ------------------------
        evidence = [business["reference"], engineering["reference"]]
        opening = facilitator_turn(
            session_id, 1, None, synthesis, synthesis_reference, evidence
        )
        assert opening["output"]["delegation"]["invoke"] == "none"
        assert opening["output"]["resolutions"] == []
        assert opening["corrective_reprompts"] <= 2

        # --- PO clarifies; facilitator delegates one side (example §3) ----
        po_clarification = (
            "Yes — store a token from our PSP, never the raw card number. "
            "Success = checkout under 30 seconds for returning customers."
        )
        second = facilitator_turn(
            session_id, 2, po_clarification, synthesis, synthesis_reference, evidence
        )
        delegation = second["output"]["delegation"]
        assert delegation["invoke"] in ("engineering", "both"), delegation
        assert delegation["extra_context"]  # PO clarification injected

        # mirrored single-perspective re-review with the extra context
        re_review = invoke_reviewer(
            ENGINEERING_URL,
            story,
            extra=delegation["extra_context"],
            previous=engineering["report"],
        )
        assert re_review["previous_review_version"] == 1
        assert re_review["based_on_extra_context"]
        engineering_v2 = {
            "report": re_review,
            "reference": save_artifact(
                "review-engineering", run_id, "engineering", re_review
            ),
        }
        # re-synthesis pairs business v1 with engineering v2 (untouched side reused)
        synthesis_v2 = invoke_synthesis(business, engineering_v2)
        synthesis_v2_reference = save_artifact(
            "synthesis", run_id, None, synthesis_v2
        )
        evidence_v2 = [
            business["reference"],
            engineering["reference"],
            engineering_v2["reference"],
        ]

        # --- second clarification resolves without delegation (example §4)
        po_resolution = (
            "Add the 30-second criterion to the story's acceptance criteria. "
            "We keep cards 24 months max, noted in the consent text."
        )
        third = facilitator_turn(
            session_id,
            3,
            po_resolution,
            synthesis_v2,
            synthesis_v2_reference,
            evidence_v2,
        )
        final = third["output"]["delegation"]
        assert final["invoke"] == "none", final
        assert third["output"]["resolutions"], "expected resolution drafts"
        for draft in third["output"]["resolutions"]:
            assert draft["disposition"] in ("resolved", "accepted", "unresolved")
        assert third["corrective_reprompts"] <= 2
