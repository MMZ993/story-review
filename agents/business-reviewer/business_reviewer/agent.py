"""Business reviewer ADK agent (Phase 5 increment 1).

Builds the single-turn reviewer LlmAgent from the repo prompt text and the
immutable config.yaml: model + generation settings come only from the
config; the instruction comes only from the prompt file. Structured output
is enforced natively via ADK's `output_schema` backed by the shared strict
`ReviewReport` model (D13-3, serving-safe mirror per D13 amendment 1).
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.genai import types

from agent_kit.config import AgentConfig
from agent_kit.prompts import LoadedPrompt


from agent_kit.llm_output import ServingSafeReviewReport


def build_agent(prompt: LoadedPrompt, config: AgentConfig) -> LlmAgent:
    """Build the business-reviewer agent; no I/O, no request is issued.

    Structured output uses ADK's native `output_schema` with the
    serving-safe mirror; the strict shared `ReviewReport` validates the
    payload at the adapter boundary (D13 amendment 1).
    """
    return LlmAgent(
        name="business_reviewer",
        model=config.model,
        instruction=prompt.text,
        output_schema=ServingSafeReviewReport,
        generate_content_config=types.GenerateContentConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
        ),
    )
