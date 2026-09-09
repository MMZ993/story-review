"""Business perspective reviewer agent — Phase 5 skeleton (slug, immutable config)."""

from __future__ import annotations

from pathlib import Path

from agent_kit.config import AgentConfig, load_agent_config

AGENT_SLUG = "business-reviewer"

_AGENT_DIR = Path(__file__).resolve().parent.parent


def load_config() -> AgentConfig:
    """Load this agent's immutable config.yaml; fails loud when absent/invalid."""
    return load_agent_config(_AGENT_DIR / "config.yaml")
