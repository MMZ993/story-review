"""75% context compaction (Item D remainder, D28) — deterministic tier.

The compaction callback is tested with fake contents/summarizer/state:
threshold trigger, keep-tail rewrite, re-apply after a stored checkpoint,
and both failure modes keeping the original context untouched.
"""

from __future__ import annotations

import logging

import pytest

from agent_kit.compaction import (
    KEEP_RECENT_TURNS,
    CompactionCallbacks,
    ConversationSummary,
)

LOGGER_BASE = "storyreview.agent"


def _content(text: str, role: str = "user") -> dict:
    return {"role": role, "parts": [{"text": text}]}


class _FakeState(dict):
    def __init__(self):
        super().__init__()


class _FakeLlmRequest:
    def __init__(self, contents):
        self.contents = list(contents)


class _FakeCallbackContext:
    def __init__(self, state=None):
        self.state = _FakeState() if state is None else state


class _FakeTool:
    name = "get_story"


def _summary(**over) -> ConversationSummary:
    fields = {
        "unresolved_issues": ["B-2"],
        "decisions": ["E-4 resolved as wontfix"],
        "story_id": "story-07",
        "run_id": "run-0001",
        "artifact_references": ["art-00000000-0000-4000-8000-0000000000a1"],
        "open_points": ["confirm edit window with ops"],
    }
    fields.update(over)
    return ConversationSummary(**fields)


class TestConversationSummary:
    def test_rejects_empty_required_lists(self):
        with pytest.raises(ValueError):
            ConversationSummary(
                unresolved_issues=[],
                decisions=[],
                story_id="story-07",
                run_id="run-0001",
                artifact_references=[],
                open_points=[],
            )


class TestCompactionCallbacks:
    def test_summarize_level_rewrites_contents_keeping_tail(self):
        cb = CompactionCallbacks(
            service="facilitator",
            summarizer=lambda contents: _summary(),
        )
        contents = [_content(f"turn {i}") for i in range(6)]
        request = _FakeLlmRequest(contents)
        ctx = _FakeCallbackContext({"context_level": "summarize"})

        cb.before_model(ctx, request)

        assert request.contents[0]["role"] == "user"
        assert "unresolved issues" in request.contents[0]["parts"][0]["text"]
        tail = request.contents[1:]
        assert tail == contents[-KEEP_RECENT_TURNS:]

    def test_ok_and_warn_levels_are_no_ops(self):
        cb = CompactionCallbacks(
            service="facilitator",
            summarizer=lambda contents: _summary(),
        )
        for level in ("ok", "warn"):
            contents = [_content("turn 0"), _content("turn 1")]
            request = _FakeLlmRequest(contents)
            ctx = _FakeCallbackContext({"context_level": level})
            cb.before_model(ctx, request)
            assert request.contents == contents

    def test_stored_checkpoint_reapplies_without_resummarizing(self):
        calls = []

        def summarizer(contents):
            calls.append(contents)
            return _summary()

        cb = CompactionCallbacks(service="facilitator", summarizer=summarizer)
        ctx = _FakeCallbackContext(
            {
                "context_level": "summarize",
                "compaction": {
                    "summary": _summary().model_dump(),
                    "source_content_count": 6,
                },
            }
        )
        contents = [_content(f"turn {i}") for i in range(6)]
        request = _FakeLlmRequest(contents)

        cb.before_model(ctx, request)

        assert calls == []  # checkpoint reused, no second summary cost
        assert "unresolved issues" in request.contents[0]["parts"][0]["text"]
        assert request.contents[1:] == contents[-KEEP_RECENT_TURNS:]

    def test_summarizer_failure_keeps_original_context(self, caplog):
        def summarizer(contents):
            raise RuntimeError("model unavailable")

        cb = CompactionCallbacks(service="facilitator", summarizer=summarizer)
        contents = [_content("turn 0"), _content("turn 1")]
        request = _FakeLlmRequest(contents)
        ctx = _FakeCallbackContext({"context_level": "summarize"})

        with caplog.at_level(logging.ERROR, logger=f"{LOGGER_BASE}.compaction"):
            cb.before_model(ctx, request)

        assert request.contents == contents
        assert "compaction" not in ctx.state
        assert any(
            r.getMessage() == "compaction_failed" for r in caplog.records
        )

    def test_invalid_summary_keeps_original_context(self):
        cb = CompactionCallbacks(
            service="facilitator",
            summarizer=lambda contents: "not a summary",
        )
        contents = [_content("turn 0"), _content("turn 1")]
        request = _FakeLlmRequest(contents)
        ctx = _FakeCallbackContext({"context_level": "summarize"})

        cb.before_model(ctx, request)

        assert request.contents == contents
        assert "compaction" not in ctx.state

    def test_second_trigger_with_new_turns_resummarizes(self):
        """After a first compaction, new turns past the kept window must
        produce a fresh summary — never silently dropped (review finding)."""
        calls = []

        def summarizer(text):
            calls.append(text)
            return _summary(open_points=[f"point {len(calls)}"])

        cb = CompactionCallbacks(service="facilitator", summarizer=summarizer)
        ctx = _FakeCallbackContext({"context_level": "summarize"})

        # first compaction over 6 turns
        request = _FakeLlmRequest([_content(f"turn {i}") for i in range(6)])
        cb.before_model(ctx, request)

        # context grew again: 6 checkpointed + 6 new contents
        grown = [_content(f"turn {i}") for i in range(12)]
        request = _FakeLlmRequest(grown)
        cb.before_model(ctx, request)

        assert len(calls) == 2
        assert "turn 11" in calls[1]
        assert request.contents[1:] == grown[-KEEP_RECENT_TURNS:]

    def test_corrupt_checkpoint_falls_through_to_fresh_summary(self):
        cb = CompactionCallbacks(
            service="facilitator",
            summarizer=lambda text: _summary(),
        )
        ctx = _FakeCallbackContext(
            {
                "context_level": "summarize",
                "compaction": {"summary": {"unresolved_issues": []}},
            }
        )
        contents = [_content("turn 0"), _content("turn 1")]
        request = _FakeLlmRequest(contents)

        cb.before_model(ctx, request)

        assert "unresolved issues" in request.contents[0]["parts"][0]["text"]

    def test_compaction_applied_event_logged(self, caplog):
        cb = CompactionCallbacks(
            service="facilitator",
            summarizer=lambda text: _summary(),
        )
        ctx = _FakeCallbackContext({"context_level": "summarize"})
        request = _FakeLlmRequest([_content("turn 0")] * 6)

        with caplog.at_level(logging.INFO, logger=f"{LOGGER_BASE}.compaction"):
            cb.before_model(ctx, request)

        assert any(
            r.getMessage() == "compaction_applied" for r in caplog.records
        )

    def test_missing_state_is_a_no_op(self):
        cb = CompactionCallbacks(
            service="facilitator",
            summarizer=lambda text: _summary(),
        )
        contents = [_content("turn 0")]
        request = _FakeLlmRequest(contents)

        cb.before_model(_FakeCallbackContext(), request)

        assert request.contents == contents
