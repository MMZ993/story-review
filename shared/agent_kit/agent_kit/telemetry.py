"""Item D observability callbacks (facilitator-first slice).

Content-safe ADK telemetry per docs/design/observability.md: paired
before/after tool events (tool name, result status, duration — never
arguments, tool capability, story, or artifact content), before/after
model events (latency and token use), and the post-response
context-length policy: ``warn`` at 50% of the context limit,
``summarize`` at 75%.

Events are logged to the ``storyreview.agent.*`` loggers as structured
extras (message + severity + service + fields); the serving shell
attaches a JSON handler so Cloud Run captures them as Cloud Logging
entries.

The 75% compaction action itself (typed summary validated before older
history is replaced) is deliberately not here: callbacks only record.
Compaction operates on the ADK session store and is an open Item D
mechanism decision; the ``summarize`` level marks where it triggers.
"""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from typing import Any

#: Context-length policy thresholds (fractions of the context limit).
WARN_FRACTION = 0.5
SUMMARIZE_FRACTION = 0.75

#: Default context limit for the configured model family (gemini-2.5-
#: flash, per agents/<agent>/config.yaml); used when no explicit limit
#: is injected, so the policy is live by default rather than dormant.
DEFAULT_CONTEXT_TOKEN_LIMIT = 1_048_576


def context_level(prompt_tokens: int, limit: int) -> tuple[str, float]:
    """Classify one prompt token count against the context limit.

    Returns ``(level, fraction)`` where level is ``"ok"``, ``"warn"``
    (>= 50%), or ``"summarize"`` (>= 75%). Pure; no side effects.
    """
    fraction = prompt_tokens / limit
    if fraction >= SUMMARIZE_FRACTION:
        return "summarize", fraction
    if fraction >= WARN_FRACTION:
        return "warn", fraction
    return "ok", fraction


class TelemetryCallbacks:
    """ADK callback bundle emitting content-safe structured events.

    Args:
        service: service name for the ``service`` field (agent slug).
        context_token_limit: deployed model context limit in tokens; when
            given, after-model events carry the context level and used
            fraction from the reported prompt token count.

    The callbacks return ``None``/pass-through results: telemetry never
    alters the agent run. Start timestamps live in a context-local dict
    keyed per call (``tool:<name>`` / ``model:<name>``) so concurrent
    runs in one process cannot cross-contaminate durations. Calls of the
    same kind never nest (the model loop is strictly sequential), so one
    start slot per kind (``tool`` / ``model``) is sufficient.
    """

    def __init__(
        self, service: str = "", context_token_limit: int | None = None
    ) -> None:
        self.service = service
        self.context_token_limit = context_token_limit
        self._tool_logger = logging.getLogger("storyreview.agent.tool")
        self._model_logger = logging.getLogger("storyreview.agent.model")
        self._starts: ContextVar[dict[str, float]] = ContextVar(
            "telemetry_starts", default={}
        )

    # --- tool callbacks (ADK BeforeToolCallback / AfterToolCallback) ----

    def before_tool(
        self, tool: Any, args: dict, tool_context: Any = None, **_
    ) -> None:
        """Record a tool call start (tool name only — args are content)."""
        name = getattr(tool, "name", str(tool))
        self._note_start("tool")
        self._tool_logger.info(
            "tool_call",
            extra={"service": self.service, "tool": name, "phase": "start"},
        )
        return None

    def after_tool(
        self,
        tool: Any,
        args: dict,
        tool_context: Any = None,
        result: dict = None,
        **_,
    ) -> None:
        """Record a tool call end with duration and error/ok status.

        ADK invokes canonical after-tool callbacks with keyword arguments
        (tool_response=, never positional ``result``) — both are accepted."""
        response = _.pop("tool_response", result)
        name = getattr(tool, "name", str(tool))
        self._tool_logger.info(
            "tool_call",
            extra={
                "service": self.service,
                "tool": name,
                "phase": "end",
                "status": "error"
                if isinstance(response, dict) and response.get("error")
                else "ok",
                "duration_ms": self._elapsed("tool"),
            },
        )
        return None

    # --- model callbacks (ADK Before/AfterModelCallback) ----------------

    def before_model(self, callback_context: Any, llm_request: Any) -> None:
        """Record a model call start for the requested model."""
        model = getattr(llm_request, "model", "") or ""
        self._note_start("model")
        self._model_logger.info(
            "model_call",
            extra={"service": self.service, "model": model, "phase": "start"},
        )
        return None

    def after_model(self, callback_context: Any, llm_response: Any) -> None:
        """Record a model call end: latency, token use, context level.

        Partial (streaming) responses are skipped: only the final
        response of one model call carries complete usage metadata.
        """
        if getattr(llm_response, "partial", False):
            return None
        model = getattr(llm_response, "model_version", "") or ""
        usage = getattr(llm_response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", None)
        total_tokens = getattr(usage, "total_token_count", None)
        level: str | None = None
        fraction: float | None = None
        if prompt_tokens is not None and self.context_token_limit:
            level, fraction = context_level(prompt_tokens, self.context_token_limit)
            # Persist the classification in session state: the D28
            # compaction callback reads it at the next model call.
            state = getattr(callback_context, "state", None)
            if state is not None:
                state["context_level"] = level
        self._model_logger.info(
            "model_call",
            extra={
                "service": self.service,
                "model": model,
                "phase": "end",
                "duration_ms": self._elapsed("model"),
                "prompt_tokens": prompt_tokens,
                "total_tokens": total_tokens,
                "context_level": level,
                "context_fraction": fraction,
            },
        )
        return None

    # --- internals --------------------------------------------------------

    def _note_start(self, key: str) -> None:
        starts = dict(self._starts.get())
        starts[key] = time.perf_counter()
        self._starts.set(starts)

    def _elapsed(self, key: str) -> float:
        started = self._starts.get().get(key)
        if started is None:
            return -1.0
        return round((time.perf_counter() - started) * 1000, 1)
