"""Agent Engine entry point for the synthesis agent (staged by deploy.sh).

Builds root_agent exactly like the local adapter assembly — repo prompt via
PROMPTS_DIR plus the agent's immutable config.yaml — minus the HTTP shell.
"""

from __future__ import annotations

from synthesis import load_config
from synthesis.agent import build_agent

from agent_kit.ae_runtime import build_root_agent

root_agent = build_root_agent("synthesis", build_agent, load_config)
