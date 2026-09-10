"""Interaction facilitator agent — Phase 5 skeleton (slug, immutable config)."""

from __future__ import annotations

from pathlib import Path

from agent_kit.config import AgentConfig, load_agent_config

AGENT_SLUG = "facilitator"

_PKG_DIR = Path(__file__).resolve().parent
_AGENT_ROOT = _PKG_DIR.parent


def _config_path() -> Path:
    """Wheel installs carry config.yaml inside the package; editable
    source trees keep it at the agent root."""
    for candidate in (_PKG_DIR / "config.yaml", _AGENT_ROOT / "config.yaml"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"agent config not found near {_PKG_DIR}")


def load_config() -> AgentConfig:
    """Load this agent's immutable config.yaml; fails loud when absent/invalid."""
    return load_agent_config(_config_path())
