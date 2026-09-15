"""Item D telemetry callbacks (facilitator-first slice).

Covers the context-length policy thresholds, content-safe paired tool
events, model latency/token events, and the runner wiring that attaches
them alongside the lineage guard.
"""

from __future__ import annotations

import logging

from contextlib import contextmanager

from agent_kit.telemetry import (
    SUMMARIZE_FRACTION,
    WARN_FRACTION,
    TelemetryCallbacks,
    context_level,
)

LOGGER_BASE = "storyreview.agent"


class CaptureHandler(logging.Handler):
    """Collect records so assertions run against attributes."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextmanager
def capture(logger_name: str):
    handler = CaptureHandler()
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


class FakeTool:
    name = "get_story"


class FakeUsage:
    def __init__(self, prompt_token_count, total_token_count):
        self.prompt_token_count = prompt_token_count
        self.total_token_count = total_token_count


class FakeResponse:
    def __init__(self, usage, model_version="gemini-2.5-flash"):
        self.usage_metadata = usage
        self.model_version = model_version


class FakeRequest:
    model = "gemini-2.5-flash"


# --- context policy -------------------------------------------------------


def test_context_level_thresholds():
    assert context_level(49, 100)[0] == "ok"
    assert context_level(50, 100)[0] == "warn"
    assert context_level(74, 100)[0] == "warn"
    assert context_level(75, 100)[0] == "summarize"
    assert context_level(75, 100)[1] == 0.75
    assert WARN_FRACTION == 0.5
    assert SUMMARIZE_FRACTION == 0.75


# --- tool telemetry -------------------------------------------------------


def test_tool_callbacks_emit_paired_content_safe_events():
    telemetry = TelemetryCallbacks(service="facilitator")
    with capture(f"{LOGGER_BASE}.tool") as handler:
        telemetry.before_tool(FakeTool(), {"story_id": "story-07"}, None)
        telemetry.after_tool(FakeTool(), {"story_id": "story-07"}, None, {"story": {}})

    assert [r.phase for r in handler.records] == ["start", "end"]
    for record in handler.records:
        assert record.tool == "get_story"
        assert record.service == "facilitator"
        # Content safety: no tool arguments or results ride along.
        assert "story_id" not in record.__dict__
    end = handler.records[1]
    assert end.status == "ok"
    assert end.duration_ms >= 0


def test_tool_callback_marks_error_results():
    telemetry = TelemetryCallbacks()
    with capture(f"{LOGGER_BASE}.tool") as handler:
        telemetry.before_tool(FakeTool(), {}, None)
        telemetry.after_tool(FakeTool(), {}, None, {"error": "lineage"})

    assert handler.records[-1].status == "error"


def test_after_tool_accepts_adk_keyword_calling_convention():
    """ADK invokes canonical after_tool callbacks with keyword arguments
    (tool=, args=, tool_context=, tool_response=) — a positional `result`
    parameter is never supplied, raising TypeError live on Agent Engine
    the moment a tool call actually happens (observed at the inc-6 gate
    smoke: facilitator toolsets loaded, first tool call crashed the turn)."""
    telemetry = TelemetryCallbacks()
    telemetry.before_tool(FakeTool(), {}, None)
    with capture(f"{LOGGER_BASE}.tool") as handler:
        telemetry.after_tool(
            tool=FakeTool(),
            args={},
            tool_context=None,
            tool_response={"story": {}},
        )

    assert handler.records[-1].phase == "end"
    assert handler.records[-1].status == "ok"


# --- model telemetry ------------------------------------------------------


def test_model_callbacks_emit_latency_and_token_event_with_context_level():
    telemetry = TelemetryCallbacks(service="facilitator", context_token_limit=1000)
    with capture(f"{LOGGER_BASE}.model") as handler:
        telemetry.before_model(None, FakeRequest())
        telemetry.after_model(None, FakeResponse(FakeUsage(600, 800)))

    assert [r.phase for r in handler.records] == ["start", "end"]
    end = handler.records[1]
    assert end.model == "gemini-2.5-flash"
    assert end.prompt_tokens == 600
    assert end.total_tokens == 800
    assert end.context_level == "warn"
    assert end.context_fraction == 0.6
    assert end.duration_ms >= 0


def test_model_callback_without_usage_logs_none_tokens():
    telemetry = TelemetryCallbacks()
    with capture(f"{LOGGER_BASE}.model") as handler:
        telemetry.before_model(None, FakeRequest())
        telemetry.after_model(None, FakeResponse(None))

    end = handler.records[1]
    assert end.prompt_tokens is None
    assert end.context_level is None


def test_model_callback_reports_summarize_level():
    telemetry = TelemetryCallbacks(context_token_limit=100)
    with capture(f"{LOGGER_BASE}.model") as handler:
        telemetry.before_model(None, FakeRequest())
        telemetry.after_model(None, FakeResponse(FakeUsage(80, 90)))

    assert handler.records[-1].context_level == "summarize"


# --- wiring ---------------------------------------------------------------


from agent_kit.facilitator_adapter import build_facilitator_runner
from agent_kit.telemetry import TelemetryCallbacks

from tests.test_facilitator_input import PROMPTS


def test_runner_attaches_guard_then_telemetry_callbacks(monkeypatch):
    monkeypatch.setenv("PROMPTS_DIR", str(PROMPTS))
    seen: dict = {}

    def build_agent_fn(prompt, config, *, tools=None, **callbacks):
        seen["callbacks"] = callbacks
        return object()

    build_facilitator_runner(
        "facilitator",
        build_agent_fn,
        lambda: None,
        story_url="http://story:8080/mcp",
        artifact_url="http://artifact:8080/mcp",
        db_url="sqlite+aiosqlite:///:memory:",
    )

    before_tool = seen["callbacks"]["before_tool_callback"]
    # The lineage guard stays first: a rejection short-circuits the tool
    # before telemetry's start event can mislead (no end would follow).
    assert callable(before_tool[0])
    assert isinstance(before_tool[1].__self__, TelemetryCallbacks)
    for name in ("after_tool_callback", "before_model_callback", "after_model_callback"):
        assert callable(seen["callbacks"][name])


def test_facilitator_app_configures_json_logging(monkeypatch):
    """The adapter shell attaches the JSON stdout handler so the Item D
    telemetry events reach Cloud Logging as structured entries."""
    import logging
    monkeypatch.setenv("PROMPTS_DIR", str(PROMPTS))

    from agent_kit.facilitator_adapter import create_facilitator_app
    from agent_kit.structured_logging import JsonFormatter

    logger = logging.getLogger("storyreview")
    saved = list(logger.handlers)
    for handler in saved:
        logger.removeHandler(handler)

    app = create_facilitator_app(
        slug="facilitator",
        build_agent_fn=lambda *a, **k: None,
        load_config_fn=lambda: None,
        agent_version="0.1.0",
        runner=object(),
    )

    assert app is not None
    handlers = logger.handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0].formatter, JsonFormatter)
    for handler in handlers:
        logger.removeHandler(handler)
    for handler in saved:
        logger.addHandler(handler)
