"""Artifact MCP client unit tests (SSE handling, session threading)."""

from __future__ import annotations

import json

import httpx
import pytest

from evaluation.artifact_client import (
    ArtifactClient,
    ArtifactClientError,
    ArtifactToolFailure,
)


def make_client(handler) -> ArtifactClient:
    return ArtifactClient(transport=httpx.MockTransport(handler))


def test_initialize_threads_session_id_header_into_tool_calls():
    seen_headers: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(request.headers))
        body = json.loads(request.content)
        if body["method"] == "initialize":
            return httpx.Response(
                200,
                headers={"mcp-session-id": "sess-abc", "content-type": "application/json"},
                json={"jsonrpc": "2.0", "id": body["id"], "result": {}},
            )
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {"content": [{"text": json.dumps({"content": {}})}]},
            },
        )

    client = make_client(handler)
    client.initialize()
    client.get_artifact("art-1", "run-1")
    # initialize carried no session header; the tool call carried it
    assert "mcp-session-id" not in seen_headers[0]
    assert seen_headers[-1]["mcp-session-id"] == "sess-abc"


def test_decode_prefers_response_event_over_notification_in_sse():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sse = (
            "event: message\n"
            'data: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n'
            "event: message\n"
            "data: "
            + json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {"content": [{"text": '{"ok": true}'}]},
                }
            )
            + "\n\n"
        )
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=sse.encode()
        )

    client = make_client(handler)
    client.initialize = lambda: None  # skip handshake for this unit check
    assert client.get_artifact("art-1", "run-1") == {"ok": True}


def test_structured_tool_error_raises_tool_failure_with_code():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        error_text = json.dumps({"error": {"code": "ARTIFACT_NOT_FOUND",
                                           "message": "no such artifact"}})
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {"isError": True, "content": [{"text": error_text}]},
            },
        )

    client = make_client(handler)
    client.initialize = lambda: None
    with pytest.raises(ArtifactToolFailure) as excinfo:
        client.get_artifact("art-1", "run-other")
    assert excinfo.value.code == "ARTIFACT_NOT_FOUND"


def test_http_error_status_raises_client_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not here")

    client = make_client(handler)
    with pytest.raises(ArtifactClientError):
        client.initialize()
