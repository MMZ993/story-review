"""Synthesis local adapter: thin binding of the shared synthesis core.

The frozen synthesis invocation contract (single-turn run, HTTP shell,
error mapping) lives once in `agent_kit.synthesis_adapter`; this package
binds it to the synthesis agent, prompt, and config.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from agent_kit.synthesis_adapter import create_synthesis_app
from synthesis import load_config
from synthesis.agent import build_agent

try:
    AGENT_VERSION = version("synthesis-agent")
except PackageNotFoundError:  # pragma: no cover
    AGENT_VERSION = "0.0.0+unknown"


def create_app():
    """Build the synthesis adapter app (prompt/config load loudly)."""
    return create_synthesis_app(
        slug="synthesis",
        build_agent_fn=build_agent,
        load_config_fn=load_config,
        agent_version=AGENT_VERSION,
    )


__all__ = ["AGENT_VERSION", "create_app"]
