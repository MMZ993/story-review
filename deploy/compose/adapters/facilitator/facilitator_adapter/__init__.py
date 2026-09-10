"""Facilitator local adapter: thin binding of the shared facilitator core.

The frozen session-scoped invocation contract (corrective re-prompt loop,
lineage tool guard, HTTP shell, error mapping) lives once in
`agent_kit.facilitator_adapter`; this package binds it to the facilitator
agent, prompt, config, and the local MCP stack endpoints. Environment
(local-agents compose profile only):

- `FACILITATOR_STORY_URL` — story MCP server streamable-HTTP endpoint;
- `FACILITATOR_ARTIFACT_URL` — artifact MCP server streamable-HTTP endpoint;
- `FACILITATOR_DB_URL` — PostgreSQL session backend (DatabaseSessionService).

All three are required and validated at startup, fail-loud.
"""

from __future__ import annotations

import os

from importlib.metadata import PackageNotFoundError, version

from agent_kit.facilitator_adapter import create_facilitator_app
from facilitator import load_config
from facilitator.agent import build_agent

try:
    AGENT_VERSION = version("facilitator-agent")
except PackageNotFoundError:  # pragma: no cover
    AGENT_VERSION = "0.0.0+unknown"

_ENV_VARS = (
    "FACILITATOR_STORY_URL",
    "FACILITATOR_ARTIFACT_URL",
    "FACILITATOR_DB_URL",
)


def create_app():
    """Build the facilitator adapter app (env validated loudly)."""
    missing = [name for name in _ENV_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"facilitator adapter requires env: {', '.join(missing)}"
        )
    return create_facilitator_app(
        slug="facilitator",
        build_agent_fn=build_agent,
        load_config_fn=load_config,
        agent_version=AGENT_VERSION,
        story_url=os.environ["FACILITATOR_STORY_URL"],
        artifact_url=os.environ["FACILITATOR_ARTIFACT_URL"],
        db_url=os.environ["FACILITATOR_DB_URL"],
    )


__all__ = ["AGENT_VERSION", "create_app"]
