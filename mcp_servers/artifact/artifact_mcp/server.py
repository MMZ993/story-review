"""Artifact MCP server: `save_artifact`, `get_artifact`, `list_artifacts`.

Same dispatch skeleton as the story server (Runbook 10 gotchas): strict
shared input models, unknown-field rejection from the raw call arguments,
every failure a structured `ToolError(ErrorBody)` with `is_error`.

Authorization is per tool (mcp-servers.md caller table): `save_artifact`
is orchestration-only; `get_artifact`/`list_artifacts` also serve the
facilitator. With auth disabled (local profile only) the principal is
absent and the allowlists are bypassed.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent

from review_schemas.mcp import (
    GetArtifactInput,
    GetArtifactOutput,
    ListArtifactsInput,
    ListArtifactsOutput,
    SaveArtifactInput,
    SaveArtifactOutput,
)

from artifact_mcp.auth import current_principal
from artifact_mcp.errors import (
    correlation_id_from_header,
    error_for,
    unauthenticated,
    forbidden,
)
from artifact_mcp.storage import GcsArtifactService

logger = logging.getLogger("artifact_mcp.server")

_CORRELATION_HEADER = "x-correlation-id"


class CallerRoles:
    """Per-tool caller sets: `orchestration` and the read-only `facilitator`."""

    def __init__(self, *, orchestration: set[str], facilitator: set[str] | None = None) -> None:
        self.orchestration = orchestration
        self.facilitator = facilitator or set()

    def read_allowed(self, caller: str) -> bool:
        return caller in self.orchestration or caller in self.facilitator


class ArtifactServer:
    """Owns the MCP server, the storage service, and the caller roles."""

    def __init__(
        self,
        *,
        service: GcsArtifactService,
        roles: CallerRoles | None = None,
    ) -> None:
        self._service = service
        self._roles = roles
        self._mcp = MCPServer("artifact")
        self._register_tools()

    def mcp(self) -> MCPServer:
        """The MCP server object (mount via `streamable_http_app`)."""
        return self._mcp

    def _register_tools(self) -> None:
        mcp = self._mcp

        @mcp.tool()
        async def save_artifact(
            type: str,
            story_run_id: str,
            perspective: str | None,
            content: dict[str, Any],
            idempotency_key: str,
            context: Context = None,
        ) -> CallToolResult:
            """Persist one artifact (orchestration only); idempotent per
            (story_run_id, type, idempotency_key)."""
            return await self._dispatch(
                "save_artifact",
                {"type", "story_run_id", "perspective", "content", "idempotency_key"},
                {
                    "type": type,
                    "story_run_id": story_run_id,
                    "perspective": perspective,
                    "content": content,
                    "idempotency_key": idempotency_key,
                },
                SaveArtifactInput,
                context,
                self._service.save,
                write=True,
            )

        @mcp.tool()
        async def get_artifact(
            artifact_id: str, story_run_id: str, context: Context = None
        ) -> CallToolResult:
            """Read one artifact's reference and content, run-scoped."""
            return await self._dispatch(
                "get_artifact",
                {"artifact_id", "story_run_id"},
                {"artifact_id": artifact_id, "story_run_id": story_run_id},
                GetArtifactInput,
                context,
                self._service.get,
            )

        @mcp.tool()
        async def list_artifacts(
            story_run_id: str,
            type: str | None = None,
            perspective: str | None = None,
            limit: int = 100,
            offset: int = 0,
            context: Context = None,
        ) -> CallToolResult:
            """List a run's artifacts ordered by (type, perspective, version)."""
            return await self._dispatch(
                "list_artifacts",
                {"story_run_id", "type", "perspective", "limit", "offset"},
                {
                    "story_run_id": story_run_id,
                    "type": type,
                    "perspective": perspective,
                    "limit": limit,
                    "offset": offset,
                },
                ListArtifactsInput,
                context,
                self._service.list,
            )

    async def _dispatch(
        self,
        tool: str,
        fields: set[str],
        arguments: dict[str, Any],
        input_model,
        context: Context,
        handler,
        *,
        write: bool = False,
    ) -> CallToolResult:
        correlation_id = _correlation_id(context)
        try:
            _authorize(self._roles, write, correlation_id)
            _reject_unknown_fields(tool, _raw_arguments(context), fields)
            # strict=False: wire JSON carries UUIDs/dates as strings; the
            # shared models stay strict at construction time.
            request = input_model.model_validate(arguments, strict=False)
            output = handler(request)
            return _result(output.model_dump(mode="json"))
        except _ToolFailure as failure:
            logger.info("tool %s rejected caller correlation_id=%s", tool, correlation_id)
            return _error_result(failure.payload)
        except Exception as exc:  # noqa: BLE001 — taxonomy boundary
            logger.warning(
                "tool %s failed correlation_id=%s error=%r", tool, correlation_id, str(exc)
            )
            return _error_result(error_for(exc, correlation_id))


def _result(payload: dict) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
        structured_content=payload,
        is_error=False,
    )


def _error_result(error) -> CallToolResult:
    payload = error.model_dump(mode="json")
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
        structured_content=payload,
        is_error=True,
    )


def _correlation_id(context: Context):
    headers = context.headers or {}
    return correlation_id_from_header(headers.get(_CORRELATION_HEADER))


def _authorize(roles: CallerRoles | None, write: bool, correlation_id) -> None:
    """Per-tool allowlist; absent principal + enabled auth fails closed."""
    if roles is None:
        return  # local profile (auth disabled): no principal to check
    principal = current_principal()
    if principal is None:
        raise _ToolFailure(unauthenticated(correlation_id))
    allowed = principal in roles.orchestration or (
        not write and roles.read_allowed(principal)
    )
    if not allowed:
        raise _ToolFailure(forbidden(principal, correlation_id))


class _ToolFailure(Exception):
    """Carries an already-built ToolError payload through the dispatch."""

    def __init__(self, payload) -> None:
        super().__init__(payload.error.code)
        self.payload = payload


def _reject_unknown_fields(tool: str, raw: dict, fields: set[str]) -> None:
    unknown = sorted(set(raw) - fields)
    if unknown:
        raise ValueError(
            f"unknown field(s) {', '.join(unknown)}; accepted: {', '.join(sorted(fields))}"
        )


def _raw_arguments(context: Context) -> dict:
    """The caller's raw (unvalidated) tool arguments, unknown fields included."""
    params = getattr(context.request_context, "params", None)
    if params is None:
        return {}
    arguments = params.get("arguments") if hasattr(params, "get") else getattr(params, "arguments", None)
    return dict(arguments) if arguments is not None else {}
