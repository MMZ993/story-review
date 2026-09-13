"""Agent Engine entry point for the facilitator agent (staged by deploy.sh).

Builds root_agent like the local runner's assembly — repo prompt, immutable
config, read-only story/artifact MCP toolsets (same tool filters) — with
audience-scoped ID-token auth instead of the compose network. Session
state comes from the cloudsql-iam session service (services.py; D24
amendment 1).
"""

from __future__ import annotations

import os

from facilitator import load_config
from facilitator.agent import build_agent

from agent_kit.ae_runtime import build_facilitator_root_agent

root_agent = build_facilitator_root_agent(
    "facilitator",
    build_agent,
    load_config,
    story_url=os.environ["FACILITATOR_STORY_URL"],
    artifact_url=os.environ["FACILITATOR_ARTIFACT_URL"],
)
