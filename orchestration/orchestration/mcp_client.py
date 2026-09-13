"""Direct MCP client wrapper with the observability.md transport policy.

One wrapper instance per MCP service URL. Every call is a fresh streamable
HTTP session (initialize + one request), bounded by:

- short-call timeout 60 s / at most 3 attempts (settings),
- jittered exponential backoff 1 s, 2 s between attempts (half jitter:
  base delay scaled by 0.5 + rng()*0.5),
- retry only on connection failure, timeout, or a retryable tool error
  (UPSTREAM_UNAVAILABLE / RENDER_FAILED); never on 4xx-class tool errors,
  schema validation, authorization, or idempotency mismatch,
- remaining-deadline clamping: per-attempt timeout is
  min(short-call timeout, remaining budget - RESPONSE_CLEANUP_RESERVE_SECONDS)
  and an attempt that cannot fit is never started (DeadlineExceededError).

`session_call` is the injectable transport seam used by tests; `tool=None`
means a reachability probe (initialize-only) used by /health.
"""

from __future__ import annotations

import uuid

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult
from review_schemas.errors import ErrorBody

from .config import Settings

#: Budget kept aside for response persistence/cleanup after the last
#: downstream attempt (clamping reserve per observability.md).
RESPONSE_CLEANUP_RESERVE_SECONDS: float = 5.0

#: Tool-error codes that count as retryable upstream 5xx equivalents.
RETRYABLE_TOOL_ERROR_CODES = frozenset({"UPSTREAM_UNAVAILABLE", "RENDER_FAILED"})

#: Backoff base delays between the three short-call attempts.
BACKOFF_BASE_DELAYS = (1.0, 2.0)


def _tool_error_is_retryable(failure: "McpCallFailure") -> bool:
    """Retryable tool errors: the upstream-5xx-equivalent codes only."""
    return (
        failure.error.code in RETRYABLE_TOOL_ERROR_CODES
        and failure.error.retryable
    )


def _first_leaf(group: BaseExceptionGroup) -> BaseException:
    """Depth-first first leaf exception of a (possibly nested) group."""
    current: BaseException = group
    while isinstance(current, BaseExceptionGroup):
        current = current.exceptions[0]
    return current


class McpTransportError(Exception):
    """All transport attempts failed (connection/timeout) — maps to 503."""


class McpCallFailure(Exception):
    """The MCP tool returned a terminal structured error."""

    def __init__(self, error: ErrorBody):
        super().__init__(error.code)
        self.error = error


class DeadlineExceededError(Exception):
    """Remaining request budget cannot fit another attempt."""


class SessionCall(Protocol):
    async def __call__(
        self, url: str, tool: str | None, arguments: dict, timeout_s: float
    ) -> dict: ...


def parse_call_result(result: CallToolResult) -> dict:
    """Classify one CallToolResult into a success payload or a failure.

    Success requires structured content (every project tool returns it);
    errors require a parseable ErrorBody. Anything else is a contract
    violation surfaced as a non-retryable McpCallFailure.
    """
    if result.is_error:
        raw = result.structured_content or {}
        try:
            fields = dict(raw["error"])
            fields["correlation_id"] = uuid.UUID(fields["correlation_id"])
            error = ErrorBody.model_validate(fields)
        except Exception:
            error = ErrorBody(
                code="UPSTREAM_UNAVAILABLE",
                message="malformed tool error payload",
                correlation_id=uuid.UUID("00000000-0000-4000-8000-000000000000"),
                retryable=False,
            )
        raise McpCallFailure(error)
    if result.structured_content is None:
        raise McpCallFailure(
            ErrorBody(
                code="UPSTREAM_UNAVAILABLE",
                message="tool result missing structured content",
                correlation_id=uuid.UUID("00000000-0000-4000-8000-000000000000"),
                retryable=False,
            )
        )
    return dict(result.structured_content)


async def _streamable_http_call(
    url: str, tool: str | None, arguments: dict, timeout_s: float,
    headers: dict[str, str] | None = None,
) -> dict:
    """One real MCP round trip over streamable HTTP, wall-clock bounded."""

    async def run() -> dict:
        async with streamable_http_client(url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                if tool is None:
                    return {"ok": True}
                result: CallToolResult = await session.call_tool(tool, arguments)
                return parse_call_result(result)

    return await asyncio.wait_for(run(), timeout=timeout_s)


class McpClient:
    """Policy-wrapped client for one MCP service endpoint."""

    def __init__(
        self,
        url: str,
        settings: Settings,
        *,
        session_call: SessionCall = _streamable_http_call,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: Callable[[], float] = random.random,
        auth_headers: Callable[[], dict[str, str]] | None = None,
    ):
        self._url = url
        self._settings = settings
        self._session_call = session_call
        self._sleep = sleeper
        self._rng = rng
        self._auth_headers = auth_headers

    def _call_kwargs(self) -> dict:
        """Headers kwarg only when MCP ingress auth is wired (keeps the
        4-argument SessionCall seam contract for local/unauthenticated
        transports and their test fakes)."""
        if self._auth_headers is None:
            return {}
        return {"headers": self._auth_headers()}

    async def call(
        self, tool: str, arguments: dict, *, deadline: float | None = None
    ) -> dict:
        """Call `tool` under the short-call retry policy.

        Returns the validated structured payload. Raises McpCallFailure
        (terminal tool error), McpTransportError (retry exhaustion), or
        DeadlineExceededError (budget cannot fit an attempt).
        """
        attempts = self._settings.short_call_attempts
        deadline_at = (
            deadline
            if deadline is not None
            else time.monotonic() + self._settings.request_deadline_seconds
        )
        last_transport_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            timeout_s = self._clamped_timeout(deadline_at)
            try:
                return await self._attempt(tool, arguments, timeout_s)
            except McpCallFailure as failure:
                if attempt < attempts and _tool_error_is_retryable(failure):
                    await self._backoff(attempt)
                    continue
                raise
            except Exception as exc:  # connection/timeout transport failure
                last_transport_error = exc
                if attempt < attempts:
                    await self._backoff(attempt)
                    continue
                raise McpTransportError(str(exc)) from exc
        raise McpTransportError(str(last_transport_error))

    async def _attempt(self, tool: str, arguments: dict, timeout_s: float) -> dict:
        """One transport attempt, unwrapping tool errors from TaskGroups."""
        try:
            return await self._session_call(
                self._url, tool, arguments, timeout_s, **self._call_kwargs()
            )
        except* McpCallFailure as group:
            raise _first_leaf(group) from None

    async def probe(self, timeout_s: float | None = None) -> bool:
        """Single-attempt reachability check for /health (never raises)."""
        if timeout_s is None:
            timeout_s = float(self._settings.health_probe_timeout_seconds)
        try:
            await self._session_call(
                self._url, None, {}, timeout_s, **self._call_kwargs()
            )
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "health probe failed for %s: %s: %s",
                self._url, type(exc).__name__, exc,
            )
            return False

    def _clamped_timeout(self, deadline_at: float) -> float:
        """min(short-call timeout, remaining budget - reserve); never 0."""
        remaining = deadline_at - time.monotonic() - RESPONSE_CLEANUP_RESERVE_SECONDS
        if remaining <= 0:
            raise DeadlineExceededError("request deadline budget exhausted")
        return min(float(self._settings.short_call_timeout_seconds), remaining)

    async def _backoff(self, attempt: int) -> None:
        base = BACKOFF_BASE_DELAYS[min(attempt - 1, len(BACKOFF_BASE_DELAYS) - 1)]
        await self._sleep(base * (0.5 + self._rng()))
