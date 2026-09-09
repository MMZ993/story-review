"""Shared agent support: prompt loading and model config (Phase 5)."""

from agent_kit.config import AgentConfig, load_agent_config
from agent_kit.prompts import LoadedPrompt, load_prompt
from agent_kit.reviewer_input import ReviewerRequest, render_reviewer_message

__all__ = [
    "AgentConfig",
    "LoadedPrompt",
    "ReviewerRequest",
    "load_agent_config",
    "load_prompt",
    "render_reviewer_message",
]
