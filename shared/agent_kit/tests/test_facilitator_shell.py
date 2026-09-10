"""Tests for the facilitator adapter HTTP shell.

Deterministic: the session-scoped ADK run is replaced by a scripted fake
(injected via the shell's `runner` seam and a monkeypatched `make_send`),
so these tests pin the HTTP contract — `/health`, `/turn` happy path with
corrective counter, request validation errors, `DELEGATION_VALIDATION`
mapping — without Vertex, Postgres, or MCP servers.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

import agent_kit.facilitator_adapter as fa
from agent_kit.facilitator_adapter import create_facilitator_app
from agent_kit.prompts import LoadedPrompt

from tests.test_facilitator_input import PROMPTS

_REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS = _REPO_ROOT.parent / "prompts"


class FakeRunner:
    """Stands in for the ADK Runner; the send seam is monkeypatched anyway."""


class ScriptedSend:
    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)

    async def __call__(self, message: str) -> str:
        return self.replies.pop(0)


def valid_turn_payload(invoke: str = "none") -> dict:
    return {
        "reply": "Here is the synthesis.",
        "delegation": {
            "invoke": invoke,
            "extra_context": None,
            "reuse_previous": False,
            "open_issues": ["C-1"],
            "readiness": "needs_work",
        },
        "resolutions": [],
    }


@pytest.fixture
def app(monkeypatch):
    def build():
        return create_facilitator_app(
            slug="facilitator",
            build_agent_fn=lambda *a, **k: None,
            load_config_fn=lambda: None,
            agent_version="0.1.0",
            runner=FakeRunner(),
        )

    monkeypatch.setenv("PROMPTS_DIR", str(PROMPTS))
    return build()


def make_client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def turn_body(turn_number: int = 1, po_message: str | None = None) -> dict:
    from tests.test_facilitator_input import synth_reference, review_reference

    body = {
        "session_id": "sess-00000000-0000-0000-0000-000000000001",
        "turn_number": turn_number,
        "po_message": po_message,
        "synthesis_report": None,  # filled below via model dump
        "synthesis_reference": synth_reference().model_dump(mode="json"),
        "evidence_references": [
            review_reference("business").model_dump(mode="json"),
            review_reference("engineering").model_dump(mode="json"),
        ],
    }
    from tests.test_facilitator_input import synth_report

    body["synthesis_report"] = json.loads(synth_report().model_dump_json())
    return body


def test_health(app):
    async def run():
        async with make_client(app) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "agent_version": "0.1.0"}

    asyncio.run(run())


def test_turn_happy_path_stamps_envelope(app, monkeypatch):
    monkeypatch.setattr(
        fa, "make_send", lambda runner, req: ScriptedSend(json.dumps(valid_turn_payload()))
    )

    async def run():
        async with make_client(app) as client:
            resp = await client.post("/turn", json=turn_body())
        assert resp.status_code == 200
        body = resp.json()
        assert body["output"]["delegation"]["invoke"] == "none"
        assert body["corrective_reprompts"] == 0
        assert body["agent_version"] == "0.1.0"
        assert len(body["prompt_sha256"]) == 64

    asyncio.run(run())


def test_turn_counts_corrective_reprompts(app, monkeypatch):
    bad = valid_turn_payload(invoke="engineering")  # opening-turn violation
    monkeypatch.setattr(
        fa,
        "make_send",
        lambda runner, req: ScriptedSend(
            json.dumps(bad), json.dumps(valid_turn_payload())
        ),
    )

    async def run():
        async with make_client(app) as client:
            resp = await client.post("/turn", json=turn_body())
        assert resp.status_code == 200
        assert resp.json()["corrective_reprompts"] == 1

    asyncio.run(run())


def test_delegation_validation_on_exhaustion(app, monkeypatch):
    monkeypatch.setattr(
        fa, "make_send", lambda runner, req: ScriptedSend("junk", "junk", "junk")
    )

    async def run():
        async with make_client(app) as client:
            resp = await client.post("/turn", json=turn_body())
        assert resp.status_code == 422
        error = resp.json()["error"]
        assert error["code"] == "DELEGATION_VALIDATION"
        assert error["agent"] == "facilitator"
        assert error["retryable"] is False

    asyncio.run(run())


def test_invalid_request_is_400_validation_error(app):
    async def run():
        async with make_client(app) as client:
            body = turn_body()
            body["turn_number"] = 2  # po_message still None -> model violation
            resp = await client.post("/turn", json=body)
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    asyncio.run(run())


def test_model_transport_failure_is_503(app, monkeypatch):
    class ExplodingSend:
        async def __call__(self, message: str) -> str:
            raise RuntimeError("vertex unreachable")

    monkeypatch.setattr(fa, "make_send", lambda runner, req: ExplodingSend())

    async def run():
        async with make_client(app) as client:
            resp = await client.post("/turn", json=turn_body())
        assert resp.status_code == 503
        error = resp.json()["error"]
        assert error["code"] == "UPSTREAM_UNAVAILABLE"
        assert error["retryable"] is True

    asyncio.run(run())
