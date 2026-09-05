"""Agent Engine entry point for the disposable connectivity caller.

`root_agent` is a minimal ADK agent with exactly two tools, each making one
ID-token-authenticated call to the deployed Cloud Run MCP endpoint. The
service URL is injected at deployment through `SPIKE_SERVICE_URL`; deployment
fails fast when it is absent. Tool outputs are returned unmodified so the
external trace can compare persisted and restored IDs, markers, and
correlation IDs. Model and tool errors propagate through ADK.
"""

from __future__ import annotations

import os

from google.adk.agents import LlmAgent

from spike_agent.tools import build_tools
from spike_agent.transport import CloudRunMcpTransport


def build_agent(service_url: str) -> LlmAgent:
    """Build the disposable agent for `service_url` without issuing a request."""
    persist_session, restore_session = build_tools(CloudRunMcpTransport(service_url))
    return LlmAgent(
        name="connectivity_spike",
        model="gemini-2.5-flash",
        instruction=(
            "Use only the provided tools. For a persist request, call persist_session. "
            "For a restore request, call restore_session. Forward session_id, marker, "
            "and correlation_id exactly as supplied. Return the tool result without "
            "interpretation or additional data."
        ),
        tools=[persist_session, restore_session],
    )


root_agent = build_agent(os.environ.get("SPIKE_SERVICE_URL", ""))
