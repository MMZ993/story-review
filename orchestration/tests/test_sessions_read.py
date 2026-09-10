"""Sessions read paths (GET list + detail) deterministic tests.

Uses the flow-1 fake stack to create real sessions, then exercises
keyset pagination (limit/cursor, updated_at desc) and SessionDetail
assembly (turns + server-side artifact references), plus 404 mapping.
"""

from __future__ import annotations

import httpx

from .conftest import make_settings
from .fakes import FakeArtifactMcp, story_detail
from .test_create_session_flow import flow_client, make_agents, post_create

KEY_A = "55555555-5555-4555-8555-555555555555"
KEY_B = "66666666-6666-4666-8666-666666666666"


async def create_two(pool, artifact=None):
    artifact = artifact or FakeArtifactMcp()
    agents = make_agents()
    settings = make_settings()
    detail_07 = story_detail("story-07")
    detail_08 = story_detail("story-08")
    async with flow_client(
        settings, pool, artifact, agents, detail=detail_07
    ) as client:
        first = await post_create(
            client, KEY_A, {"story_id": "story-07", "requested_formats": ["md"]}
        )
        assert first.status_code == 201, first.text
    async with flow_client(
        settings, pool, artifact, agents, detail=detail_08
    ) as client:
        second = await post_create(
            client, KEY_B, {"story_id": "story-08", "requested_formats": ["pdf"]}
        )
        assert second.status_code == 201, second.text
    return artifact, first.json(), second.json()


async def test_list_sessions_ordered_desc(pool):
    artifact, first, second = await create_two(pool)
    settings = make_settings()
    async with flow_client(settings, pool, artifact, make_agents()) as client:
        response = await client.get("/api/v1/sessions")
        assert response.status_code == 200
        body = response.json()
        assert [s["session_id"] for s in body["sessions"]] == [
            second["session_id"],
            first["session_id"],
        ]
        assert body["next_cursor"] is None
        assert body["sessions"][1]["requested_formats"] == ["md"]


async def test_list_sessions_limit_and_cursor(pool):
    artifact, first, second = await create_two(pool)
    settings = make_settings()
    async with flow_client(settings, pool, artifact, make_agents()) as client:
        page_one = await client.get("/api/v1/sessions", params={"limit": 1})
        assert page_one.status_code == 200
        body = page_one.json()
        assert [s["session_id"] for s in body["sessions"]] == [second["session_id"]]
        assert body["next_cursor"] is not None
        page_two = await client.get(
            "/api/v1/sessions",
            params={"limit": 1, "cursor": body["next_cursor"]},
        )
        assert page_two.status_code == 200
        body_two = page_two.json()
        assert [s["session_id"] for s in body_two["sessions"]] == [
            first["session_id"]
        ]
        assert body_two["next_cursor"] is None


async def test_session_detail_with_turns_and_artifacts(pool):
    artifact, first, _ = await create_two(pool)
    settings = make_settings()
    async with flow_client(settings, pool, artifact, make_agents()) as client:
        response = await client.get(f"/api/v1/sessions/{first['session_id']}")
        assert response.status_code == 200, response.text
        detail = response.json()
        assert detail["session_id"] == first["session_id"]
        assert detail["facilitator_turn_count"] == 1
        assert len(detail["turns"]) == 1
        turn = detail["turns"][0]
        assert turn["turn_number"] == 1
        assert turn["po_message"] is None
        assert turn["outcome"] == "continue"
        assert turn["delegation"]["invoke"] == "none"
        assert turn["facilitator_reply"] == first["facilitator_reply"]
        # server-side artifact fetch: every run artifact referenced
        assert len(detail["artifact_references"]) == 4
        assert {ref["type"] for ref in detail["artifact_references"]} == {
            "story",
            "review-business",
            "review-engineering",
            "synthesis",
        }
        assert detail["reports"] == []


async def test_unknown_session_404(pool):
    artifact, _, _ = await create_two(pool)
    settings = make_settings()
    async with flow_client(settings, pool, artifact, make_agents()) as client:
        response = await client.get(
            "/api/v1/sessions/sess-" + "deadbeef" * 4
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


async def test_list_rejects_bad_limit(pool):
    artifact, _, _ = await create_two(pool)
    settings = make_settings()
    async with flow_client(settings, pool, artifact, make_agents()) as client:
        response = await client.get("/api/v1/sessions", params={"limit": 0})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_naive_timestamp_cursor_is_422(pool):
    import base64

    artifact, _, _ = await create_two(pool)
    settings = make_settings()
    raw = base64.urlsafe_b64encode(
        b"2026-01-01T00:00:00|sess-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    ).decode().rstrip("=")
    async with flow_client(settings, pool, artifact, make_agents()) as client:
        response = await client.get("/api/v1/sessions", params={"cursor": raw})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
