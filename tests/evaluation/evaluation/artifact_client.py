"""Minimal MCP client for the artifact service (evaluation evidence).

Implements just what the suite needs: a streamable-HTTP JSON-RPC session
(initialize → notifications/initialized → tools/call) over one connection,
with `get_artifact` and `list_artifacts`. Local compose only (auth
disabled); every failure raises `ArtifactClientError` with the raw body.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

_JSON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


class ArtifactClientError(Exception):
    """Transport or protocol failure talking to the artifact MCP."""


class ArtifactToolFailure(Exception):
    """The artifact MCP returned a structured tool error (is_error)."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _decode_payload(response: httpx.Response) -> dict[str, Any]:
    """Decode a JSON or SSE-framed JSON-RPC response body.

    For SSE bodies with multiple events (e.g. a notification followed by
    the response), the event carrying an ``id``/``result`` member wins.
    """
    content_type = response.headers.get("content-type", "")
    text = response.text
    if "text/event-stream" in content_type:
        payloads = [
            json.loads(line[len("data:") :].strip())
            for line in text.splitlines()
            if line.startswith("data:") and line[len("data:") :].strip()
        ]
        if not payloads:
            raise ArtifactClientError(f"empty SSE body: {text[:200]}")
        for payload in reversed(payloads):
            if "id" in payload or "result" in payload or "error" in payload:
                return payload
        return payloads[-1]
    return json.loads(text)


class ArtifactClient:
    """One tool-call session per instance against the artifact MCP."""

    def __init__(self, transport: httpx.BaseTransport, base_url: str = "http://127.0.0.1:8102"):
        self._client = httpx.Client(transport=transport, base_url=base_url, timeout=60.0)
        self._session_id: str | None = None
        self._next_id = 0

    def initialize(self) -> None:
        """Open the MCP session (initialize + initialized notification)."""
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "evaluation-suite", "version": "0.1"},
            },
        )
        self._session_id = result.headers.get("mcp-session-id")
        self._rpc("notifications/initialized", None)

    def get_artifact(self, artifact_id: str, story_run_id: str) -> dict:
        """Read one artifact's reference + content (run-scoped server-side)."""
        return self._call_tool(
            "get_artifact", {"artifact_id": artifact_id, "story_run_id": story_run_id}
        )

    def close(self) -> None:
        self._client.close()

    # -- internals ----------------------------------------------------------

    def _call_tool(self, name: str, arguments: dict) -> dict:
        """One tools/call; structured tool errors raise ArtifactToolFailure."""
        result = self._rpc(
            "tools/call", {"name": name, "arguments": arguments}
        )
        body = _decode_payload(result)
        if "error" in body:
            raise ArtifactClientError(f"tool {name} RPC error: {body['error']}")
        content = body.get("result", {}).get("content", [])
        structured_error = body.get("result", {}).get("isError", False)
        text = "".join(item.get("text", "") for item in content)
        if structured_error:
            try:
                error = json.loads(text).get("error", {})
            except ValueError:
                error = {"code": "TOOL_ERROR", "message": text[:300]}
            raise ArtifactToolFailure(error.get("code", "TOOL_ERROR"), error.get("message", ""))
        try:
            return json.loads(text)
        except ValueError as exc:
            raise ArtifactClientError(f"tool {name} returned non-JSON: {text[:200]}") from exc

    def _rpc(self, method: str, params: dict | None) -> httpx.Response:
        self._next_id += 1
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not method.startswith("notifications/"):
            message["id"] = self._next_id
        headers = dict(_JSON_HEADERS)
        if self._session_id:
            headers["mcp-session-id"] = self._session_id
        response = self._client.post("/mcp", json=message, headers=headers)
        if response.status_code >= 400:
            raise ArtifactClientError(
                f"{method} -> {response.status_code}: {response.text[:200]}"
            )
        return response
