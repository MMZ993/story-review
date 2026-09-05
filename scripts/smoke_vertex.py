"""Phase 0 exit check: a minimal ADK agent calls Gemini via Vertex AI using ADC.

No deployed infrastructure: the agent runs in-process with an in-memory session.
Success = a model response is produced through the ADK Runner over Vertex AI.

Usage (from the repository root):
    GOOGLE_GENAI_USE_VERTEXAI=true \
    GOOGLE_CLOUD_PROJECT=<project-id> \
    GOOGLE_CLOUD_LOCATION=europe-west4 \
    SMOKE_MODEL=gemini-2.5-flash \
    uv run --with google-adk python scripts/smoke_vertex.py
"""

import asyncio
import os
import sys

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

PROMPT = "Reply with exactly: phase-0-exit-ok"


def build_agent() -> LlmAgent:
    return LlmAgent(
        name="smoke_agent",
        model=os.environ.get("SMOKE_MODEL", "gemini-2.5-flash"),
        instruction="You are a smoke-test agent. Follow the user's instruction literally.",
    )


async def run_once() -> str:
    runner = InMemoryRunner(agent=build_agent(), app_name="smoke")
    session = await runner.session_service.create_session(
        app_name="smoke", user_id="smoke-user"
    )
    events = runner.run_async(
        user_id="smoke-user",
        new_message=types.Content(role="user", parts=[types.Part(text=PROMPT)]),
        session_id=session.id,
    )
    final = ""
    async for event in events:
        for part in event.content.parts if event.content else []:
            if part.text:
                final = part.text.strip()
    return final


def main() -> int:
    for var in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"):
        if not os.environ.get(var):
            print(f"missing required env var: {var}", file=sys.stderr)
            return 2
    reply = asyncio.run(run_once())
    if not reply:
        print("no model response received", file=sys.stderr)
        return 1
    print(f"model replied: {reply}")
    print("phase 0 exit check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
