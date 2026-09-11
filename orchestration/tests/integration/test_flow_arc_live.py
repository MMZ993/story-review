"""Live integration: flows 1–4 end-to-end arc (main PC, real adapters).

One session walked through every flow: creation with idempotent replay
and key-reuse rejection (flow 1), a re-review dialogue turn with its
own replay (flow 2), a steering-driven gate finalize into flow 3/4
(deterministic finalized-review artifact → rendered reports → signed
URLs → downloaded bytes), the completed-session finalize replay and
report endpoint, and read-only enforcement afterwards. The facilitator
is a real model: the delegation decision on turn 2 is observed, the
finalize is steered (bounded retry) but asserted on observable
outcomes only.
"""

from __future__ import annotations

import json

import httpx
import pytest

from .helpers import idem_key, live_env, post_turn

pytestmark = pytest.mark.skipif(
    live_env() is None,
    reason="live integration env missing — run via make orchestration-integration-test",
)

RE_REVIEW_MESSAGE = (
    "The API limit is 100 rps — we checked with ops. "
    "Please re-review with that constraint in mind."
)

FINALIZE_STEERING = (
    "Every finding from the latest synthesis has been addressed and the "
    "team confirms the resolutions. There are no remaining open issues. "
    "Do not invoke any reviewer and do not use reuse_previous; report "
    "open_issues as an empty list so the session can finalize."
)


async def test_live_flows_1_to_4_arc(live_client):
    """Creation → replay/reuse/conflict → dialogue turn → gate finalize →
    downloaded reports → completed-session replays → read-only 409."""
    client, pool = live_client

    # --- flow 1: creation + idempotency surface -----------------------
    key = idem_key()
    created = await client.post(
        "/api/v1/sessions",
        json={"story_id": "story-07", "requested_formats": ["md", "pdf"]},
        headers={"Idempotency-Key": key},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    session_id = body["session_id"]
    assert body["delegation"]["invoke"] == "none"
    assert body["facilitator_reply"]

    replay = await client.post(
        "/api/v1/sessions",
        json={"story_id": "story-07", "requested_formats": ["md", "pdf"]},
        headers={"Idempotency-Key": key},
    )
    assert replay.status_code == 201
    assert replay.json() == body

    reused = await client.post(
        "/api/v1/sessions",
        json={"story_id": "story-07", "requested_formats": ["md"]},
        headers={"Idempotency-Key": key},
    )
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    conflict = await client.post(
        "/api/v1/sessions",
        json={"story_id": "story-07", "requested_formats": ["md"]},
        headers={"Idempotency-Key": idem_key()},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "STORY_SESSION_ACTIVE"

    # --- read paths ----------------------------------------------------
    detail = await client.get(f"/api/v1/sessions/{session_id}")
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["turns"]) == 1
    page = await client.get("/api/v1/sessions", params={"limit": 1})
    assert page.status_code == 200, page.text
    assert len(page.json()["sessions"]) == 1
    # follow the cursor only when one is emitted (a single session on a
    # fresh DB means no second page); httpx would send cursor=None as an
    # empty string, which the schema rightly rejects
    cursor = page.json()["next_cursor"]
    if cursor is not None:
        next_page = await client.get(
            "/api/v1/sessions", params={"limit": 1, "cursor": cursor}
        )
        assert next_page.status_code == 200, next_page.text

    # --- flow 2: re-review dialogue turn + replay -----------------------
    turn_key = idem_key()
    turn = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"message": RE_REVIEW_MESSAGE, "po_accepted": False},
        headers={"Idempotency-Key": turn_key},
    )
    assert turn.status_code == 200, turn.text
    turn_body = turn.json()
    assert turn_body["turn_number"] == 2
    assert turn_body["outcome"] == "continue", turn_body
    assert turn_body["state"] == "active"

    turn_replay = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"message": RE_REVIEW_MESSAGE, "po_accepted": False},
        headers={"Idempotency-Key": turn_key},
    )
    assert turn_replay.status_code == 200
    assert turn_replay.json() == turn_body

    # --- flows 3+4 via the gate (steered, bounded) -----------------------
    finalized = None
    for _ in range(4):
        response = await post_turn(client, session_id, FINALIZE_STEERING)
        assert response.status_code == 200, response.text
        finalized = response.json()
        if finalized["outcome"] == "finalize":
            break
        assert finalized["outcome"] == "continue", finalized
        assert finalized["state"] == "active"
    assert finalized is not None and finalized["outcome"] == "finalize", finalized
    assert finalized["state"] == "completed"
    assert sorted(entry["format"] for entry in finalized["report"]) == ["md", "pdf"]

    # durable completed state with both report references
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select state, report_references from sessions where session_id = $1",
            session_id,
        )
        assert row["state"] == "completed"
        # asyncpg returns jsonb as a string — decode before counting
        assert len(json.loads(row["report_references"])) == 2

    # the signed URLs actually serve the rendered bytes (self-signed
    # local TLS — relaxed verification is the documented local substitution)
    async with httpx.AsyncClient(verify=False) as downloader:
        for entry in finalized["report"]:
            downloaded = await downloader.get(entry["signed_url"])
            assert downloaded.status_code == 200, downloaded.text
            assert len(downloaded.content) > 0

    # completed-session finalize replay: fresh URLs, no writes
    fin_key = idem_key()
    fin = await client.post(
        f"/api/v1/sessions/{session_id}/finalize",
        headers={"Idempotency-Key": fin_key},
    )
    assert fin.status_code == 200, fin.text
    fin_replay = await client.post(
        f"/api/v1/sessions/{session_id}/finalize",
        headers={"Idempotency-Key": fin_key},
    )
    assert fin_replay.status_code == 200
    # replays regenerate fresh signed URLs (expires_at differs); the
    # durable references are identical and nothing new was written
    def _refs(payload):
        return [
            (entry["format"], entry["reference"]["artifact_id"])
            for entry in payload["report"]
        ]

    assert _refs(fin_replay.json()) == _refs(fin.json())

    reports = await client.get(f"/api/v1/sessions/{session_id}/report")
    assert reports.status_code == 200, reports.text
    assert sorted(e["format"] for e in reports.json()["report"]) == ["md", "pdf"]

    # completed sessions are read-only
    read_only = await post_turn(client, session_id, "anything")
    assert read_only.status_code == 409
    assert read_only.json()["error"]["code"] == "SESSION_READ_ONLY"
