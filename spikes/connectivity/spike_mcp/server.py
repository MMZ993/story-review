"""Minimal MCP HTTP service exposing the two connectivity-spike tools.

Tools: `persist_session` and `restore_session`, both returning structured
JSON and requiring a verified caller. The caller's principal is resolved by a
provider callable; production wiring verifies a Google ID token (added with
the Cloud Run deployment increment), tests inject a fake verified principal.
Every request's correlation ID is logged.

This module intentionally has no database, GCS, Secret Manager, or production
schema dependencies.
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Protocol

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult
from pydantic import ValidationError

from spike_mcp.principal import Principal
from spike_mcp.store import (
    AlreadyStoredError,
    InMemorySessionMarkerStore,
    PersistSessionRequest,
    RestoreSessionRequest,
    SessionMarkerStore,
)

logger = logging.getLogger("spike_mcp.server")

PrincipalProvider = Callable[[], Principal | None]


class AuthRequiredError(Exception):
    """No verified caller principal was available for the request."""


class SessionMarkerServer:
    """Owns the MCP server, the store, and the principal provider."""

    def __init__(self, store: SessionMarkerStore | None = None) -> None:
        self._store: SessionMarkerStore = store if store is not None else InMemorySessionMarkerStore()
        self._principal_provider: PrincipalProvider | None = None
        self._mcp = MCPServer("connectivity-spike")
        self._register_tools()

    def app(self) -> MCPServer:
        """The MCP server object (usable directly as an in-memory transport)."""
        return self._mcp

    def set_principal_provider(self, provider: PrincipalProvider) -> None:
        """Install the principal resolution hook (verified token in production)."""
        self._principal_provider = provider

    def _require_principal(self) -> Principal:
        provider = self._principal_provider
        principal = provider() if provider is not None else None
        if principal is None:
            raise AuthRequiredError("unauthenticated: no verified caller principal")
        return principal

    def _register_tools(self) -> None:
        mcp = self._mcp
        store = self._store

        @mcp.tool()
        async def persist_session(
            session_id: str, marker: str, correlation_id: str
        ) -> dict:
            """Store one marker under a session ID (persist-once semantics)."""
            principal = self._require_principal()
            logger.info(
                "persist_session correlation_id=%s principal=%s",
                correlation_id,
                principal.email,
            )
            request = PersistSessionRequest(
                session_id=session_id, marker=marker, correlation_id=correlation_id
            )
            result = await store.persist(request)
            return result.model_dump()

        @mcp.tool()
        async def restore_session(session_id: str, correlation_id: str) -> dict:
            """Return the marker stored under a session ID, or a not-found result."""
            principal = self._require_principal()
            logger.info(
                "restore_session correlation_id=%s principal=%s",
                correlation_id,
                principal.email,
            )
            result = await store.restore(
                RestoreSessionRequest(
                    session_id=session_id, correlation_id=correlation_id
                )
            )
            return result.model_dump()


def create_server() -> SessionMarkerServer:
    """Build the spike server with the in-memory reference store."""
    return SessionMarkerServer()


def tool_payload(result: CallToolResult) -> dict:
    """Extract the structured JSON payload from an MCP tool result.

    Prefers `structuredContent` when present, otherwise parses the first
    JSON text content item.
    """
    if result.structured_content is not None:
        return dict(result.structured_content)
    for item in result.content:
        text = getattr(item, "text", None)
        if text:
            return json.loads(text)
    raise ValueError("tool result carries no payload")
