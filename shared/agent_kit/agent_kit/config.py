"""Immutable per-agent model configuration (config.yaml) loader.

Per docs/decisions/tech-stack.md, each agent's model ID and generation
settings live in its versioned ``agents/<agent>/config.yaml`` and are
immutable for one deployment. The loader enforces exactly the known key set
(no silent defaults, no unknown drift) and returns a frozen dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_REQUIRED_KEYS = ("model", "location", "temperature", "max_output_tokens")


@dataclass(frozen=True)
class AgentConfig:
    """The pinned model and generation settings for one agent deployment."""

    model: str
    location: str
    temperature: float
    max_output_tokens: int


def load_agent_config(path: Path | str) -> AgentConfig:
    """Parse and strictly validate an agent's config.yaml.

    Raises FileNotFoundError for a missing file and ValueError for YAML that
    is not a mapping, misses a required key, carries an unknown key, or has
    a wrong-typed value.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"agent config not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"agent config {path} must be a YAML mapping")

    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        raise ValueError(f"agent config {path} missing keys: {', '.join(missing)}")
    unknown = [key for key in data if key not in _REQUIRED_KEYS]
    if unknown:
        raise ValueError(f"agent config {path} has unknown keys: {', '.join(sorted(unknown))}")

    return AgentConfig(
        model=str(data["model"]),
        location=str(data["location"]),
        temperature=float(data["temperature"]),
        max_output_tokens=int(data["max_output_tokens"]),
    )
