"""Engineering-reviewer local adapter: thin configuration of the shared core.

The frozen reviewer invocation contract (assembly, single-turn run, HTTP
shell, error mapping) lives once in `agent_kit.adapter`; this package binds
it to the engineering-reviewer agent, prompt, and config.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from agent_kit.adapter import create_reviewer_app
from engineering_reviewer import load_config
from engineering_reviewer.agent import build_agent

try:
    AGENT_VERSION = version("engineering-reviewer-agent")
except PackageNotFoundError:  # pragma: no cover
    AGENT_VERSION = "0.0.0+unknown"


def create_app():
    """Build the engineering-reviewer adapter app (prompt/config load loudly)."""
    return create_reviewer_app(
        slug="engineering-reviewer",
        perspective="engineering",
        build_agent_fn=build_agent,
        load_config_fn=load_config,
        agent_version=AGENT_VERSION,
    )


__all__ = ["AGENT_VERSION", "create_app"]
