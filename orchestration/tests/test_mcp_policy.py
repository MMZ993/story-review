"""Unit tests for the MCP client wrapper policy (observability.md).

The transport is injected, so these are pure policy checks: retry
classification, attempt cap, jittered backoff shape, and deadline clamping
(including the "attempt not started when it cannot fit" rule). No network,
no LLM.
"""

from __future__ import annotations

import asyncio

import uuid

import pytest
from mcp.types import CallToolResult
from review_schemas.errors import ErrorBody

from orchestration.config import Settings
from orchestration.mcp_client import (
    DeadlineExceededError,
    McpCallFailure,
    McpClient,
    McpTransportError,
    RESPONSE_CLEANUP_RESERVE_SECONDS,
    parse_call_result,
)


def make_settings(**overrides) -> Settings:
    values = dict(
        db_dsn="postgresql://x",
        story_url="http://story:8080/mcp",
        artifact_url="http://artifact:8080/mcp",
        report_url="http://report:8080/mcp",
        bucket="artifacts-local",
        business_url="http://business:8080",
        engineering_url="http://engineering:8080",
        synthesis_url="http://synthesis:8080",
        facilitator_url="http://facilitator:8080",
    )
    values.update(overrides)
    return Settings(**values)


def make_client(transport, settings: Settings | None = None) -> tuple[McpClient, list, list]:
    """Client with injected transport, recorded sleeps, deterministic rng=0."""
    sleeps: list[float] = []
    timeouts: list[float] = []

    async def sleeper(seconds: float) -> None:
        sleeps.append(seconds)

    async def recording_transport(url, tool, arguments, timeout_s):
        timeouts.append(timeout_s)
        return await transport(url, tool, arguments, timeout_s)

    client = McpClient(
        url="http://story:8080/mcp",
        settings=settings or make_settings(),
        session_call=recording_transport,
        sleeper=sleeper,
        rng=lambda: 0.0,
    )
    return client, sleeps, timeouts


def body(code: str, retryable: bool = False) -> ErrorBody:
    return ErrorBody(
        code=code,
        message="boom",
        correlation_id=uuid.UUID("00000000-0000-4000-8000-000000000000"),
        retryable=retryable,
        retry_after_seconds=5 if retryable else None,
    )


async def test_success_first_attempt_returns_payload():
    async def transport(url, tool, arguments, timeout_s):
        return {"stories": []}

    client, sleeps, timeouts = make_client(transport)
    assert await client.call("list_stories", {}) == {"stories": []}
    assert sleeps == [] and len(timeouts) == 1


async def test_connection_error_is_retried_then_succeeds():
    attempts = {"n": 0}

    async def transport(url, tool, arguments, timeout_s):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise ConnectionError("reset")
        return {"ok": True}

    client, sleeps, _ = make_client(transport)
    assert await client.call("get_story", {"story_id": "story-01"}) == {"ok": True}
    # backoff = 1s base with half-jitter at rng=0 -> 0.5s
    assert sleeps == [0.5]


async def test_retryable_tool_error_is_retried():
    attempts = {"n": 0}

    async def transport(url, tool, arguments, timeout_s):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise McpCallFailure(body("UPSTREAM_UNAVAILABLE", retryable=True))
        return {"ok": True}

    client, sleeps, _ = make_client(transport)
    assert await client.call("list_artifacts", {"story_run_id": "run-1"}) == {"ok": True}
    assert attempts["n"] == 2


async def test_non_retryable_tool_error_is_not_retried():
    attempts = {"n": 0}

    async def transport(url, tool, arguments, timeout_s):
        attempts["n"] += 1
        raise McpCallFailure(body("STORY_NOT_FOUND"))

    client, sleeps, _ = make_client(transport)
    with pytest.raises(McpCallFailure) as exc_info:
        await client.call("get_story", {"story_id": "story-99"})
    assert exc_info.value.error.code == "STORY_NOT_FOUND"
    assert attempts["n"] == 1 and sleeps == []


async def test_transport_exhaustion_after_three_attempts():
    attempts = {"n": 0}

    async def transport(url, tool, arguments, timeout_s):
        attempts["n"] += 1
        raise ConnectionError("reset")

    client, sleeps, _ = make_client(transport)
    with pytest.raises(McpTransportError):
        await client.call("list_stories", {})
    assert attempts["n"] == 3
    # two backoffs: 1s base then 2s base, half-jitter at rng=0
    assert sleeps == [0.5, 1.0]


async def test_deadline_exhaustion_never_starts_attempt():
    async def transport(url, tool, arguments, timeout_s):  # pragma: no cover
        raise AssertionError("attempt must not start")

    client, _, timeouts = make_client(transport)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + RESPONSE_CLEANUP_RESERVE_SECONDS - 0.1
    with pytest.raises(DeadlineExceededError):
        await client.call("render_report", {}, deadline=deadline)
    assert timeouts == []


async def test_attempt_timeout_is_clamped_to_remaining_budget_minus_reserve():
    async def transport(url, tool, arguments, timeout_s):
        assert timeout_s == pytest.approx(10.0, abs=0.1)
        return {"ok": True}

    client, _, timeouts = make_client(transport)
    loop = asyncio.get_running_loop()
    await client.call("list_stories", {}, deadline=loop.time() + 15.0)
    assert len(timeouts) == 1


def test_parse_call_result_success_payload():
    result = CallToolResult(structured_content={"stories": [{"story_id": "story-01"}]}, content=[])
    assert parse_call_result(result) == {"stories": [{"story_id": "story-01"}]}


def test_parse_call_result_error_payload_becomes_call_failure():
    error = body("STORY_NOT_FOUND").model_dump(mode="json")
    result = CallToolResult(is_error=True, structured_content={"error": error}, content=[])
    with pytest.raises(McpCallFailure) as exc_info:
        parse_call_result(result)
    assert exc_info.value.error.code == "STORY_NOT_FOUND"


def test_parse_call_result_malformed_success_is_failure():
    result = CallToolResult(content=[])
    with pytest.raises(McpCallFailure):
        parse_call_result(result)
