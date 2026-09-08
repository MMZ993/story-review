"""Report MCP server: `render_report` (orchestration-only).

Same dispatch skeleton as the story/artifact servers (Runbook 10 gotchas):
strict shared input model, unknown-field rejection from the raw call
arguments, every failure a structured `ToolError(ErrorBody)` with
`is_error`. The single tool's caller allowlist is the orchestration set
only (mcp-servers.md caller table; there is no read path for agents).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent

from review_schemas.mcp import RenderReportInput, RenderReportOutput

from mcp_ingress.auth import current_principal

from report_mcp.errors import (
    correlation_id_from_header,
    error_for,
    forbidden,
    unauthenticated,
)
from report_mcp.storage import ReportStore

logger = logging.getLogger("report_mcp.server")

_CORRELATION_HEADER = "x-correlation-id"


class ReportServer:
    """Owns the MCP server, the report store, and the caller allowlist."""

    def __init__(
        self,
        *,
        store: ReportStore,
        orchestration_callers: set[str] | None = None,
    ) -> None:
        self._store = store
        self._orchestration_callers = orchestration_callers
        self._mcp = MCPServer("report")
        self._register_tools()

    def mcp(self) -> MCPServer:
        """The MCP server object (mount via `streamable_http_app`)."""
        return self._mcp

    def _register_tools(self) -> None:
        @self._mcp.tool()
        async def render_report(
            story_run_id: str,
            final_review_reference: dict[str, Any],
            format: str,
            context: Context = None,
        ) -> CallToolResult:
            """Render the run's finalized review to MD/PDF and store it;
            idempotent per (story_run_id, format)."""
            return await self._dispatch(
                "render_report",
                {"story_run_id", "final_review_reference", "format"},
                {
                    "story_run_id": story_run_id,
                    "final_review_reference": final_review_reference,
                    "format": format,
                },
                context,
            )

    async def _dispatch(
        self,
        tool: str,
        fields: set[str],
        arguments: dict[str, Any],
        context: Context,
    ) -> CallToolResult:
        correlation_id = _correlation_id(context)
        try:
            self._authorize(tool, correlation_id)
            _reject_unknown_fields(tool, _raw_arguments(context), fields)
            # strict=False: wire JSON carries UUIDs/dates as strings; the
            # shared models stay strict at construction time.
            request = RenderReportInput.model_validate(arguments, strict=False)
            output = self._store.render_report(request)
            return _result(output.model_dump(mode="json"))
        except _ToolFailure as failure:
            logger.info("tool %s rejected caller correlation_id=%s", tool, correlation_id)
            return _error_result(failure.payload)
        except Exception as exc:  # noqa: BLE001 — taxonomy boundary
            logger.warning(
                "tool %s failed correlation_id=%s error=%r", tool, correlation_id, str(exc)
            )
            return _error_result(error_for(exc, correlation_id))

    def _authorize(self, tool: str, correlation_id) -> None:
        """Orchestration-only allowlist; absent principal fails closed."""
        if self._orchestration_callers is None:
            return  # local profile (auth disabled): no principal to check
        principal = current_principal()
        if principal is None:
            raise _ToolFailure(unauthenticated(correlation_id))
        if principal not in self._orchestration_callers:
            raise _ToolFailure(forbidden(principal, correlation_id))


class _ToolFailure(Exception):
    """Carries an already-built ToolError payload through the dispatch."""

    def __init__(self, payload) -> None:
        super().__init__(payload.error.code)
        self.payload = payload


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
