"""Deterministic binding tests for the facilitator adapter (no LLM, no
network): env validation at startup and the thin binding of the shared
core. Live walkthrough lives in test_live_walkthrough.py (main PC only).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

_REPO_ROOT = Path(__file__).resolve().parents[5]
PROMPTS = _REPO_ROOT / "prompts"

_DUMMY_ENV = {
    "PROMPTS_DIR": str(PROMPTS),
    "FACILITATOR_STORY_URL": "http://story:8080/mcp",
    "FACILITATOR_ARTIFACT_URL": "http://artifact:8080/mcp",
    "FACILITATOR_DB_URL": "postgresql+asyncpg://fac:fac@postgres:5432/facilitator",
}


def test_missing_env_fails_loud(monkeypatch):
    for name, value in _DUMMY_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("FACILITATOR_DB_URL")
    from facilitator_adapter import create_app

    with pytest.raises(RuntimeError, match="FACILITATOR_DB_URL"):
        create_app()


def test_health_with_env(monkeypatch):
    for name, value in _DUMMY_ENV.items():
        monkeypatch.setenv(name, value)
    from facilitator_adapter import AGENT_VERSION, create_app

    app = create_app()

    async def call():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "agent_version": AGENT_VERSION}

    import asyncio

    asyncio.run(call())


def test_turn_via_binding_with_scripted_model(monkeypatch):
    """End-to-end through the binding's app with the model seam scripted:
    pins env plumbing into the shared shell."""
    for name, value in _DUMMY_ENV.items():
        monkeypatch.setenv(name, value)
    import asyncio

    import agent_kit.facilitator_adapter as fa
    from facilitator_adapter import create_app

    reply = {
        "reply": "Opening turn.",
        "delegation": {
            "invoke": "none",
            "extra_context": None,
            "reuse_previous": False,
            "open_issues": ["C-1"],
            "readiness": "needs_work",
        },
        "resolutions": [],
    }

    class Scripted:
        async def __call__(self, message: str) -> str:
            return json.dumps(reply)

    monkeypatch.setattr(fa, "make_send", lambda runner, req: Scripted())

    from agent_kit.facilitator_adapter import InMemoryTurnResultStore

    import facilitator_adapter as binding

    monkeypatch.setattr(
        binding, "PostgresTurnResultStore", lambda dsn: InMemoryTurnResultStore()
    )
    app = create_app()

    async def call():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            body = {
                "session_id": "sess-00000000-0000-0000-0000-000000000001",
                "turn_number": 1,
                "invocation_id": "12345678-1234-4789-8901-123456789abc",
                "po_message": None,
                "synthesis_report": json.loads(synth_report_json()),
                "synthesis_reference": synth_reference_json(),
                "evidence_references": [],
            }
            turn = await c.post("/turn", json=body)
            assert turn.status_code == 200, turn.text
            assert turn.json()["output"]["delegation"]["invoke"] == "none"
            stored = await c.get(
                "/turn-result/"
                f"{body['session_id']}/{body['invocation_id']}"
            )
            assert stored.status_code == 200
            assert stored.json() == turn.json()
            health = await c.get("/health")
            assert health.status_code == 200

    asyncio.run(call())


def synth_report_json() -> str:
    from tests.test_facilitator_input import synth_report

    return synth_report().model_dump_json()


def synth_reference_json() -> dict:
    from tests.test_facilitator_input import synth_reference

    return json.loads(synth_reference().model_dump_json())
