"""Callable ADK tools for the connectivity-spike Agent Engine resource.

`build_tools` binds the disposable MCP transport to two explicit tool
functions. Inputs are validated by the MCP service; the functions forward
JSON-compatible IDs and return the service payload without interpretation.
Their only side effects are the authenticated MCP calls made by the transport.
Transport and service errors deliberately propagate to ADK.
"""

from __future__ import annotations

from spike_agent.session_probe import McpTransport


def build_tools(transport: McpTransport) -> tuple:
    """Return persist and restore tools bound to `transport` without I/O."""

    async def persist_session(session_id: str, marker: str, correlation_id: str) -> dict:
        """Persist one marker and return the MCP payload verbatim."""
        return await transport.call_tool(
            "persist_session",
            {"session_id": session_id, "marker": marker, "correlation_id": correlation_id},
        )

    async def restore_session(session_id: str, correlation_id: str) -> dict:
        """Restore one marker and return the MCP payload verbatim."""
        return await transport.call_tool(
            "restore_session",
            {"session_id": session_id, "correlation_id": correlation_id},
        )

    return persist_session, restore_session
