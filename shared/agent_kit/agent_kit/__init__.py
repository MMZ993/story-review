"""Shared agent support: prompt loading and model config (Phase 5)."""

from agent_kit.config import AgentConfig, load_agent_config
from agent_kit.prompts import LoadedPrompt, load_prompt

__all__ = [
    "AgentConfig",
    "LoadedPrompt",
    "load_agent_config",
    "load_prompt",
]
