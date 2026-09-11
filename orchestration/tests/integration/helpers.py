"""Shared helpers for the live integration suite: env gating, key
generation, and flow-1/flow-2 request helpers over HTTP."""

from __future__ import annotations

import os
import uuid

import httpx

REQUIRED_ENV = (
    "ORCH_LIVE_STORY_URL",
    "ORCH_LIVE_ARTIFACT_URL",
    "ORCH_LIVE_REPORT_URL",
    "ORCH_LIVE_BUSINESS_URL",
    "ORCH_LIVE_ENGINEERING_URL",
    "ORCH_LIVE_SYNTHESIS_URL",
    "ORCH_LIVE_FACILITATOR_URL",
    "ORCH_LIVE_DB_DSN",
    "ORCH_LIVE_BUCKET",
)


def live_env() -> dict[str, str] | None:
    """The ORCH_LIVE_* environment when complete, else None (suite skips)."""
    values = {name: os.environ.get(name, "").strip() for name in REQUIRED_ENV}
    return values if all(values.values()) else None


def idem_key() -> str:
    """A fresh v4 idempotency key (v4 is enforced)."""
    return str(uuid.uuid4())


async def create_session(client: httpx.AsyncClient, story_id: str) -> dict:
    """Create a real session (flow 1) and return the CreateSessionResponse."""
    response = await client.post(
        "/api/v1/sessions",
        json={"story_id": story_id, "requested_formats": ["md", "pdf"]},
        headers={"Idempotency-Key": idem_key()},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def post_turn(
    client: httpx.AsyncClient, session_id: str, message: str | None
) -> httpx.Response:
    """One dialogue turn (flow 2) under a fresh idempotency key."""
    return await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"message": message, "po_accepted": False},
        headers={"Idempotency-Key": idem_key()},
    )
