"""Story MCP server: `list_stories` and `get_story` over the shared models.

Every tool call returns its success model (`ListStoriesOutput` /
`StoryDetail`) as structured content, or a `ToolError(ErrorBody)` payload
with `is_error` set — the taxonomy never leaks as free text. Tool schemas
are flat and match the shared input models exactly; unknown fields are
rejected with `VALIDATION_ERROR` by comparing the raw call arguments against
the model fields (the framework's own arg model is permissive here, so the
strictness is ours to enforce).

Authorization: the verified caller (set by the ingress middleware) must be
in the per-tool allowlist — both story tools serve orchestration and the
facilitator. With auth disabled (local profile only) the principal is
absent and the allowlist is bypassed.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent

from review_schemas.mcp import GetStoryInput, ListStoriesInput, ListStoriesOutput
from review_schemas.review import StoryDetail

from mcp_ingress.auth import current_principal
from story_mcp.backlog import BacklogLike, resolve_source
from story_mcp.errors import (
    SourceNotConfigured,
    correlation_id_from_header,
    error_for,
    forbidden,
    unauthenticated,
)

logger = logging.getLogger("story_mcp.server")

_CORRELATION_HEADER = "x-correlation-id"


class StoryServer:
    """Owns the MCP server, the configured sources, and the allowlist."""

    def __init__(
        self,
        *,
        sources: dict[str, BacklogLike],
        default_source: str,
        allowed_callers: set[str] | None = None,
    ) -> None:
        self._sources = sources
        self._default_source = default_source
        self._allowed_callers = allowed_callers
        self._mcp = MCPServer("story")
        self._register_tools()

    def mcp(self) -> MCPServer:
        """The MCP server object (mount via `streamable_http_app`)."""
        return self._mcp

    def _register_tools(self) -> None:
        mcp = self._mcp

        @mcp.tool()
        async def list_stories(
            filter: str | None = None, source: str | None = None, context: Context = None
        ) -> CallToolResult:
            """List backlog stories; optional status filter and source override."""
            return await self._dispatch(
                "list_stories",
                {"filter", "source"},
                {"filter": filter, "source": source},
                ListStoriesInput,
                context,
                self._list_stories,
            )

        @mcp.tool()
        async def get_story(
            story_id: str, source: str | None = None, context: Context = None
        ) -> CallToolResult:
            """Fetch one story's full detail by id (`story-NN` or `ado-N`)."""
            return await self._dispatch(
                "get_story",
                {"story_id", "source"},
                {"story_id": story_id, "source": source},
                GetStoryInput,
                context,
                self._get_story,
            )

    async def _dispatch(
        self,
        tool: str,
        fields: frozenset[str] | set[str],
        arguments: dict[str, Any],
        input_model,
        context: Context,
        handler,
    ) -> CallToolResult:
        correlation_id = _correlation_id(context)
        try:
            _authorize(self._allowed_callers, correlation_id)
            _reject_unknown_fields(tool, _raw_arguments(context), fields, correlation_id)
            request = input_model.model_validate(arguments)
            output = handler(request)
            payload = (
                output if isinstance(output, dict) else output.model_dump(mode="json")
            )
            return _result(payload)
        except _ToolFailure as failure:
            logger.info(
                "tool %s rejected caller correlation_id=%s",
                tool,
                correlation_id,
            )
            return _error_result(failure.payload)
        except Exception as exc:  # noqa: BLE001 — taxonomy boundary, see below
            logger.warning(
                "tool %s failed correlation_id=%s error=%r",
                tool,
                correlation_id,
                str(exc),
            )
            return _error_result(error_for(exc, correlation_id))

    def _resolve(self, override: str | None) -> BacklogLike:
        name = resolve_source(override, self._default_source)
        try:
            return self._sources[name]
        except KeyError:
            raise SourceNotConfigured(
                f"source {name!r} is not configured in this deployment"
            ) from None

    def _list_stories(self, request: ListStoriesInput) -> ListStoriesOutput:
        source = self._resolve(request.source)
        return ListStoriesOutput(stories=source.list_stories(request.filter))

    def _get_story(self, request: GetStoryInput) -> StoryDetail:
        source = self._resolve(request.source)
        return source.get_story(request.story_id)


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


def _authorize(allowed: set[str] | None, correlation_id) -> None:
    """Enforce the caller allowlist; absent principal + enabled auth fails."""
    if allowed is None:
        return  # local profile (auth disabled): no principal to check
    principal = current_principal()
    if principal is None:
        raise _ToolFailure(unauthenticated(correlation_id))
    if principal not in allowed:
        raise _ToolFailure(forbidden(principal, correlation_id))


class _ToolFailure(Exception):
    """Carries an already-built ToolError payload through the dispatch."""

    def __init__(self, payload) -> None:
        super().__init__(payload.error.code)
        self.payload = payload


def _reject_unknown_fields(tool: str, raw: dict, fields: set[str], correlation_id) -> None:
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
