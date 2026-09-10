"""Stories API and /health tests (ASGI, fake MCP transports — no network).

Covers the increment-1 endpoints over the app factory with injected
clients: proxy success shapes, orchestration-side title filter, 404/503
error-envelope mapping, and downstream reachability flags.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from review_schemas.errors import ErrorBody

from orchestration.config import Settings
from orchestration.main import create_app
from orchestration.mcp_client import McpClient, McpCallFailure

CORR = "11111111-1111-4111-8111-111111111111"

SUMMARIES = [
    {"story_id": "story-01", "title": "Login rate limiting", "status": "New"},
    {"story_id": "story-02", "title": "Bulk user export", "status": "Active"},
]
DETAIL_01 = {
    "story_id": "story-01",
    "title": "Login rate limiting",
    "status": "New",
    "description": "Add per-account login throttling.",
    "acceptance_criteria": ["Throttle engages after 5 failures."],
    "epic_context": "Platform hardening.",
    "roadmap_context": "Q3 security items.",
}


def error_body(code: str, retryable: bool = False) -> ErrorBody:
    return ErrorBody(
        code=code,
        message="boom",
        correlation_id=uuid.UUID(CORR),
        retryable=retryable,
        retry_after_seconds=5 if retryable else None,
    )


def story_transport(
    summaries: list[dict] | None = None,
    details: dict[str, dict] | None = None,
    fail_calls: bool = False,
):
    """Fake transport: list/get/probe behavior for the story MCP service."""

    async def transport(url, tool, arguments, timeout_s):
        if tool is None:
            if fail_calls:
                raise ConnectionError("down")
            return {"ok": True}
        if fail_calls:
            raise ConnectionError("down")
        if tool == "list_stories":
            return {"stories": summaries or SUMMARIES}
        if tool == "get_story":
            detail = (details or {}).get(arguments["story_id"])
            if detail is None:
                raise McpCallFailure(error_body("STORY_NOT_FOUND"))
            return detail
        raise AssertionError(f"unexpected tool {tool}")

    return transport


def side_transport(*, probe_ok: bool = True):
    """Fake transport for the artifact/report services (probe only)."""

    async def transport(url, tool, arguments, timeout_s):
        if tool is None:
            if not probe_ok:
                raise ConnectionError("down")
            return {"ok": True}
        raise AssertionError(f"unexpected tool {tool}")

    return transport


def make_app(
    story=None, artifact=None, report=None, settings: Settings | None = None
) -> httpx.AsyncClient:
    values = dict(
        db_dsn="postgresql://x",
        story_url="http://story:8080/mcp",
        artifact_url="http://artifact:8080/mcp",
        report_url="http://report:8080/mcp",
        bucket="artifacts-local",
    )
    resolved = settings or Settings(**values)

    def client(url, transport):
        return McpClient(
            url=url, settings=resolved, session_call=transport, sleeper=_no_sleep
        )

    async def _no_sleep(seconds: float) -> None:
        pass

    app = create_app(
        settings=resolved,
        story_client=client(resolved.story_url, story or story_transport()),
        artifact_client=client(
            resolved.artifact_url, artifact or side_transport()
        ),
        report_client=client(resolved.report_url, report or side_transport()),
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    )


async def test_list_stories_proxies_summaries():
    async with make_app() as client:
        response = await client.get("/api/v1/stories")
    assert response.status_code == 200
    assert response.json() == {"stories": SUMMARIES}


async def test_list_stories_filter_is_case_insensitive_title_substring():
    async with make_app() as client:
        response = await client.get("/api/v1/stories", params={"filter": "RATE"})
    assert response.status_code == 200
    assert [s["story_id"] for s in response.json()["stories"]] == ["story-01"]


async def test_story_detail_proxies_full_story():
    async with make_app(story=story_transport(details={"story-01": DETAIL_01})) as client:
        response = await client.get("/api/v1/stories/story-01")
    assert response.status_code == 200
    body = response.json()
    assert body == {**DETAIL_01, "comments": [], "context_stories": []}


async def test_unknown_story_maps_to_404_envelope():
    async with make_app() as client:
        response = await client.get("/api/v1/stories/story-99")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "STORY_NOT_FOUND"
    assert error["retryable"] is False
    assert error["retry_after_seconds"] is None


async def test_upstream_failure_maps_to_retryable_503():
    async with make_app(story=story_transport(fail_calls=True)) as client:
        response = await client.get("/api/v1/stories")
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_UNAVAILABLE"
    assert error["retryable"] is True
    assert error["retry_after_seconds"] >= 1


async def test_responses_carry_correlation_id_and_echo_supplied_one():
    async with make_app() as client:
        generated = await client.get("/api/v1/stories")
        echoed = await client.get(
            "/api/v1/stories", headers={"X-Correlation-Id": CORR}
        )
    assert generated.headers["X-Correlation-Id"]
    assert echoed.headers["X-Correlation-Id"] == CORR


async def test_health_reports_ok_when_all_downstreams_reachable():
    async with make_app() as client:
        response = await client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert {d["name"] for d in payload["dependencies"]} == {
        "story",
        "artifact",
        "report",
    }
    assert all(d["reachable"] for d in payload["dependencies"])


async def test_health_reports_degraded_when_a_downstream_is_down():
    async with make_app(
        report=side_transport(probe_ok=False)
    ) as client:
        response = await client.get("/health")
    payload = response.json()
    assert payload["status"] == "degraded"
    flags = {d["name"]: d["reachable"] for d in payload["dependencies"]}
    assert flags == {"story": True, "artifact": True, "report": False}


async def test_health_never_fails_on_a_down_downstream():
    async with make_app(
        story=story_transport(fail_calls=True), artifact=side_transport(probe_ok=False)
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


async def test_malformed_correlation_id_is_replaced_not_crashed():
    async with make_app(story=story_transport(fail_calls=True)) as client:
        response = await client.get(
            "/api/v1/stories", headers={"X-Correlation-Id": "garbage"}
        )
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_UNAVAILABLE"
    assert error["correlation_id"] == response.headers["X-Correlation-Id"]
