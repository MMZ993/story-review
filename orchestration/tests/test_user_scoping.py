"""Per-user scoping tests (Phase 8 increment 1, D24-3, api-contract.md
"X-User-Id"): the header is required (UUID v4) on session-scoped routes,
sessions and story runs belong to one user, the one-active-run-per-story
rule is per user, and another user's session id reads as 404 on every
read and mutation path. Real Postgres, flow-1-created sessions.
"""

from __future__ import annotations

import uuid

import pytest

from .conftest import USER_HEADERS  # noqa: F401  (shared default header)
from .fakes import FakeArtifactMcp  # noqa: F401  (fixture import path)
from .test_create_session_flow import CORR, create_payload, flow_client, make_agents

USER_A = uuid.uuid4()
USER_B = uuid.uuid4()


def _headers(user: uuid.UUID, key: str) -> dict:
    return {
        "Idempotency-Key": key,
        "X-Correlation-Id": CORR,
        "X-User-Id": str(user),
    }


async def _create(client, user: uuid.UUID, key: str, story: str = "story-07"):
    return await client.post(
        "/api/v1/sessions",
        json=create_payload(story),
        headers=_headers(user, key),
    )


@pytest.fixture
def artifact():
    from .fakes import FakeArtifactMcp

    return FakeArtifactMcp()


@pytest.fixture
def settings():
    from .conftest import make_settings

    return make_settings()


async def _client(pool, settings, artifact):
    return flow_client(settings, pool, artifact, make_agents())


# --- header validation -----------------------------------------------------


@pytest.mark.parametrize(
    "header", [None, "not-a-uuid", "12345678-1234-1234-1234-123456789012"]
)
async def test_session_routes_reject_bad_user_header(
    pool, settings, artifact, header
):
    """Missing / malformed / non-v4 X-User-Id is 422 VALIDATION_ERROR on
    every session-scoped route (list shown; the dependency is shared)."""
    from .test_create_session_flow import flow_client as raw_flow_client

    async with raw_flow_client(
        settings, pool, artifact, make_agents(), client_headers={}
    ) as client:
        headers = {"Idempotency-Key": str(uuid.uuid4()), "X-Correlation-Id": CORR}
        if header is not None:
            headers["X-User-Id"] = header
        for method, url in (
            ("post", "/api/v1/sessions"),
            ("get", "/api/v1/sessions"),
            ("get", "/api/v1/sessions/sess-00000000-0000-4000-8000-000000000000"),
        ):
            response = await client.request(method, url, json={}, headers=headers)
            assert response.status_code == 422, (method, url, response.text)
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_stories_browse_needs_no_user_header(pool, settings, artifact):
    """The browse endpoints are the contract's exemption: story reads
    work without X-User-Id (they are user-independent)."""
    from .fakes import story_detail
    from .test_create_session_flow import flow_client, make_agents

    async with flow_client(
        settings, pool, artifact, make_agents(),
        detail=story_detail(), client_headers={},
    ) as client:
        detail = await client.get("/api/v1/stories/story-07")
        assert detail.status_code == 200, detail.text


# --- multi-user isolation --------------------------------------------------


async def test_two_users_same_story_get_independent_sessions(
    pool, settings, artifact
):
    async with await _client(pool, settings, artifact) as client:
        first = await _create(client, USER_A, str(uuid.uuid4()))
        second = await _create(client, USER_B, str(uuid.uuid4()))
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert first.json()["session_id"] != second.json()["session_id"]

        # the one-active-run rule is per user: a third session on the same
        # story is 409 for A but fine for a fresh story
        again = await _create(client, USER_A, str(uuid.uuid4()))
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "STORY_SESSION_ACTIVE"


async def test_lists_are_scoped_per_user(pool, settings, artifact):
    async with await _client(pool, settings, artifact) as client:
        first = await _create(client, USER_A, str(uuid.uuid4()))
        second = await _create(client, USER_B, str(uuid.uuid4()), story="story-07")
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        for user, expected in ((USER_A, 1), (USER_B, 1)):
            listing = await client.get(
                "/api/v1/sessions", headers={"X-User-Id": str(user)}
            )
            assert listing.status_code == 200
            assert len(listing.json()["sessions"]) == expected


async def test_cross_user_session_ids_are_404_everywhere(pool, settings, artifact):
    """B cannot read, turn, finalize, report-fetch, or abandon A's session:
    the ownership filter makes the id read as absent (api-contract)."""
    async with await _client(pool, settings, artifact) as client:
        created = (await _create(client, USER_A, str(uuid.uuid4()))).json()
        session_id = created["session_id"]
        key = str(uuid.uuid4())

        detail = await client.get(
            f"/api/v1/sessions/{session_id}", headers={"X-User-Id": str(USER_B)}
        )
        assert detail.status_code == 404
        assert detail.json()["error"]["code"] == "SESSION_NOT_FOUND"

        for url, json_body in (
            (f"/api/v1/sessions/{session_id}/turns", {"message": "hi"}),
            (f"/api/v1/sessions/{session_id}/finalize", {}),
            (f"/api/v1/sessions/{session_id}/abandon", {}),
        ):
            response = await client.post(
                url, json=json_body, headers=_headers(USER_B, key)
            )
            assert response.status_code == 404, (url, response.text)
            assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"

        report = await client.get(
            f"/api/v1/sessions/{session_id}/report",
            headers={"X-User-Id": str(USER_B)},
        )
        assert report.status_code == 404

        # the owner still sees and mutates it (A's session is untouched)
        owner = await client.get(
            f"/api/v1/sessions/{session_id}", headers={"X-User-Id": str(USER_A)}
        )
        assert owner.status_code == 200
        assert owner.json()["state"] == "active"


async def test_same_create_key_replayed_for_another_user_is_rejected(
    pool, settings, artifact
):
    """The user id joins the idempotency fingerprint: replaying A's
    creation key as B is IDEMPOTENCY_KEY_REUSED, never A's response."""
    async with await _client(pool, settings, artifact) as client:
        key = str(uuid.uuid4())
        first = await _create(client, USER_A, key)
        assert first.status_code == 201, first.text
        replay = await client.post(
            "/api/v1/sessions",
            json=create_payload("story-05"),
            headers=_headers(USER_B, key),
        )
        assert replay.status_code == 409
        assert replay.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
