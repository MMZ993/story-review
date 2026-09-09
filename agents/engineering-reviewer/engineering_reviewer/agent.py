"""Engineering reviewer ADK agent (Phase 5 increment 2).

Builds the single-turn reviewer LlmAgent from the repo prompt text and the
immutable config.yaml: model + generation settings come only from the
config; the instruction comes only from the prompt file. Structured output
is enforced natively via ADK's `output_schema` with the serving-safe
mirror; the strict shared `ReviewReport` model validates the payload at
the adapter boundary (D13-3, D13 amendment 1).
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.genai import types

from agent_kit.config import AgentConfig
from agent_kit.llm_output import ServingSafeReviewReport
from agent_kit.prompts import LoadedPrompt


def build_agent(prompt: LoadedPrompt, config: AgentConfig) -> LlmAgent:
    """Build the engineering-reviewer agent; no I/O, no request is issued."""
    return LlmAgent(
        name="engineering_reviewer",
        model=config.model,
        instruction=prompt.text,
        output_schema=ServingSafeReviewReport,
        generate_content_config=types.GenerateContentConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
        ),
    )
