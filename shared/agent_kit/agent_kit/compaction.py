"""75% context compaction (Item D remainder — decision D28).

Facilitator-side mechanism per D28: a ``before_model`` callback that,
when the post-response telemetry classified the context as ``summarize``
(>= 75% of the model's context limit), produces a **typed** conversation
summary (``ConversationSummary``), validates it, and replaces the older
conversational contents of the model request with the summary plus the
most recent turns.

Design notes (deviations recorded in local-decisions D28):

- The validated summary checkpoint is stored in ADK session state and
  re-applied on later model calls while no new uncheckpointed turns
  exist; when the context grows again past the checkpoint, a fresh
  summary is produced (never silently dropped, per
  docs/design/observability.md). The underlying session-store events
  are **not deleted** — they remain the audit record, while the model's
  effective context is compacted.
- On summarizer or validation failure the original request contents are
  left untouched and a structured ``compaction_failed`` event is logged;
  the turn proceeds on full history instead of a retryable error (the
  failure mode here can only *skip* compaction, never drop context).

Pure decision logic; the model call itself is injected (``summarizer``)
so the deterministic tier needs no LLM.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic import BaseModel, Field

#: How many most-recent contents survive compaction after the summary.
KEEP_RECENT_TURNS = 4

#: ADK session-state keys (written by telemetry, read here).
STATE_CONTEXT_LEVEL = "context_level"
STATE_COMPACTION = "compaction"


class ConversationSummary(BaseModel):
    """Typed summary that must preserve everything the dialogue needs.

    Fields per docs/design/observability.md: unresolved issues, prior
    decisions, story/run IDs, and referenced artifact IDs — plus the
    open points the PO is still pursuing. Non-empty where the design
    demands retention.
    """

    unresolved_issues: list[str] = Field(min_length=1)
    decisions: list[str] = Field(min_length=1)
    story_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    artifact_references: list[str] = Field(min_length=1)
    open_points: list[str] = Field(min_length=1)


def _summary_lines(summary: ConversationSummary) -> list[str]:
    return [
        "[conversation summary — replaces all earlier turns]",
        f"story: {summary.story_id} (run {summary.run_id})",
        "unresolved issues: " + ", ".join(summary.unresolved_issues),
        "decisions: " + "; ".join(summary.decisions),
        "artifacts: " + ", ".join(summary.artifact_references),
        "open points: " + "; ".join(summary.open_points),
    ]


def _summary_content(summary: ConversationSummary, prototype: Any) -> Any:
    """Model-request content carrying the summary (a plain user turn).

    Matches the shape of the contents already in the request: a genai
    ``types.Content`` next to genai contents, a dict next to dict-shaped
    contents (deterministic tests)."""
    text = "\n".join(_summary_lines(summary))
    if isinstance(prototype, dict):
        return {"role": "user", "parts": [{"text": text}]}
    from google.genai import types

    return types.Content(role="user", parts=[types.Part(text=text)])


def _texts(contents: list) -> str:
    """Flatten contents to text for the summarizer input.

    Non-text parts (tool calls/responses) are excluded on purpose: the
    artifact evidence they carried is already reflected in the dialogue
    turns; recorded in D28."""

    def gen():
        for c in contents:
            parts = c.get("parts") if isinstance(c, dict) else getattr(c, "parts", None)
            for part in parts or []:
                text = (
                    part.get("text")
                    if isinstance(part, dict)
                    else getattr(part, "text", None)
                )
                if text:
                    yield text

    return "\n".join(gen())


def _load_checkpoint(state: Any) -> dict | None:
    """Return a well-formed checkpoint dict, or None (corrupt/partial
    checkpoints fall through to fresh summarization, never raise)."""
    raw = state.get(STATE_COMPACTION)
    try:
        summary = ConversationSummary.model_validate(raw["summary"])
        count = raw["source_content_count"]
        if not isinstance(count, int) or count < 0:
            return None
    except Exception:
        return None
    return {"summary": summary, "source_content_count": count}


def genai_summarizer(model: str, location: str | None = None) -> Callable[[str], ConversationSummary]:
    """Live summarizer: one structured-output model call (google-genai,
    ADC/Vertex like the agents themselves). Returns a validated
    ``ConversationSummary``; raises on any API or schema failure (the
    callback converts that into a kept-context outcome)."""
    _client = None

    def _summarize(text: str) -> ConversationSummary:
        nonlocal _client
        from google import genai
        from google.genai import types

        if _client is None:
            _client = genai.Client(location=location) if location else genai.Client()
        response = _client.models.generate_content(
            model=model,
            contents=text,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=ConversationSummary,
            ),
        )
        if not response.text:
            raise RuntimeError("summarizer returned no text")
        return ConversationSummary.model_validate_json(response.text)

    return _summarize


class CompactionCallbacks:
    """ADK before_model callback performing the 75% compaction.

    Expects the telemetry ``after_model`` callback to have stored the
    context classification under ``state[STATE_CONTEXT_LEVEL]``.
    """

    def __init__(
        self,
        service: str,
        summarizer: Callable[[str], ConversationSummary],
        keep_recent_turns: int = KEEP_RECENT_TURNS,
    ):
        self._service = service
        self._summarizer = summarizer
        self._keep = keep_recent_turns
        self._logger = logging.getLogger("storyreview.agent.compaction")

    def _fail(self, exc: Exception) -> None:
        self._logger.error(
            "compaction_failed",
            extra={"service": self._service, "error_type": type(exc).__name__},
        )

    def before_model(self, callback_context: Any, llm_request: Any) -> None:
        """Compact the request contents at the ``summarize`` level."""
        state = getattr(callback_context, "state", None)
        level = state.get(STATE_CONTEXT_LEVEL) if state is not None else None
        if level != "summarize":
            return None
        contents = list(llm_request.contents)
        # Re-apply the stored checkpoint only while it still covers the
        # current history; new uncheckpointed turns past the kept window
        # force a fresh summary (no silent context loss).
        checkpoint = _load_checkpoint(state) if state is not None else None
        if checkpoint is not None and len(contents) <= (
            checkpoint["source_content_count"] + self._keep
        ):
            summary = checkpoint["summary"]
        else:
            try:
                summary = ConversationSummary.model_validate(
                    self._summarizer(_texts(contents))
                )
            except Exception as exc:  # summarizer or validation failure
                self._fail(exc)
                return None
            if state is not None:
                state[STATE_COMPACTION] = {
                    "summary": summary.model_dump(),
                    "source_content_count": len(contents),
                }
            self._logger.info(
                "compaction_applied",
                extra={"service": self._service},
            )
        llm_request.contents = [
            _summary_content(summary, contents[0] if contents else None),
            *contents[-self._keep :],
        ]
        return None


__all__ = [
    "CompactionCallbacks",
    "ConversationSummary",
    "KEEP_RECENT_TURNS",
    "genai_summarizer",
]
