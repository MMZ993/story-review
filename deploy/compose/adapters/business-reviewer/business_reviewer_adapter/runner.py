"""Single-turn ADK run for a reviewer agent (the only I/O in the adapter).

Runs the built LlmAgent through an `InMemoryRunner` (reviewers are fresh
single-turn runs by design — no session state), extracts the final model
text, and parses it into the shared strict `ReviewReport`. Transport-level
failures propagate to the HTTP shell's error mapping; a structurally invalid
model reply raises `OutputParseError` (the normal structured error path,
after ADK's own transport retries).
"""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import ValidationError

from agent_kit.reviewer_input import render_reviewer_message
from review_schemas import ReviewReport


class OutputParseError(Exception):
    """The model reply is not valid `ReviewReport` JSON (non-retryable)."""


async def run_reviewer(
    agent: LlmAgent, user_message: str, app_name: str
) -> ReviewReport:
    """One fresh single-turn run; returns the parsed typed report."""
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id="reviewer-run"
    )
    events = runner.run_async(
        user_id="reviewer-run",
        new_message=types.Content(role="user", parts=[types.Part(text=user_message)]),
        session_id=session.id,
    )
    final_text = ""
    async for event in events:
        for part in event.content.parts if event.content else []:
            if part.text:
                final_text += part.text
    try:
        payload = json.loads(final_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise OutputParseError(f"model reply is not JSON: {exc}") from exc
    try:
        return ReviewReport.model_validate(payload)
    except ValidationError as exc:
        raise OutputParseError(f"model reply fails ReviewReport validation: {exc}") from exc


async def run_business_reviewer(agent: LlmAgent, message: str) -> ReviewReport:
    """Convenience wrapper pinning the app name for the business reviewer."""
    return await run_reviewer(agent, message, app_name="business-reviewer")
