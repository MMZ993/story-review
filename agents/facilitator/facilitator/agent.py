"""Facilitator ADK agent (Phase 5 increment 4).

Builds the session-scoped dialogue LlmAgent from the repo prompt text and
the immutable config.yaml: model + generation settings come only from the
config; the instruction comes only from the prompt file. Read-only MCP
toolsets (story + artifact) and the adapter's lineage tool guard are
injected by the adapter core (`build_facilitator_runner`); structured
output is enforced natively via ADK's `output_schema` with the serving-safe
mirror, and the strict shared `FacilitatorTurnOutput` validates the reply
at the adapter boundary (D13-3, D13 amendment 1).
"""

from __future__ import annotations

from collections.abc import Callable

from google.adk.agents import LlmAgent
from google.genai import types

from agent_kit.config import AgentConfig
from agent_kit.llm_output import ServingSafeFacilitatorTurnOutput
from agent_kit.prompts import LoadedPrompt


def build_agent(
    prompt: LoadedPrompt,
    config: AgentConfig,
    *,
    tools: list | None = None,
    before_tool_callback: Callable | None = None,
) -> LlmAgent:
    """Build the facilitator agent; no I/O, no request is issued."""
    return LlmAgent(
        name="facilitator",
        model=config.model,
        instruction=prompt.text,
        tools=list(tools) if tools else [],
        before_tool_callback=before_tool_callback,
        output_schema=ServingSafeFacilitatorTurnOutput,
        generate_content_config=types.GenerateContentConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
        ),
    )
