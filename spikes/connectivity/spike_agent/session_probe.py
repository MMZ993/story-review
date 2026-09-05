"""Agent-side session probe for the connectivity spike.

Purpose: the smallest testable core of the disposable ADK agent. The probe
generates a caller-side correlation ID, forwards it with every MCP request
through an injected transport, and returns each tool's payload without
interpreting it. The deployed agent wires the transport to the authenticated
Cloud Run MCP endpoint (ID token, service URL as audience) in a later
increment; nothing here performs I/O.

Errors: transport failures propagate unchanged; the probe adds no
interpretation of tool outcomes.
"""

from __future__ import annotations

import uuid
from typing import Protocol


class McpTransport(Protocol):
    """Transport contract: deliver one MCP tool call, return its payload."""

    async def call_tool(self, tool_name: str, arguments: dict) -> dict: ...  # pragma: no cover


def generate_correlation_id() -> str:
    """Return a fresh caller-generated correlation ID (unique per probe)."""
    return uuid.uuid4().hex


class SessionProbe:
    """Persists and restores one session marker through an MCP transport."""

    def __init__(self, transport: McpTransport, correlation_id: str | None = None) -> None:
        self._transport = transport
        self.correlation_id = correlation_id or generate_correlation_id()

    async def persist_session(self, session_id: str, marker: str) -> dict:
        """Store `marker` under `session_id`; return the tool payload verbatim."""
        return await self._transport.call_tool(
            "persist_session",
            {
                "session_id": session_id,
                "marker": marker,
                "correlation_id": self.correlation_id,
            },
        )

    async def restore_session(self, session_id: str) -> dict:
        """Retrieve the marker stored under `session_id`, payload verbatim."""
        return await self._transport.call_tool(
            "restore_session",
            {"session_id": session_id, "correlation_id": self.correlation_id},
        )

    def describe(self) -> dict:
        """JSON-serializable description for logs/traces."""
        return {"probe": "session-probe", "correlation_id": self.correlation_id}
