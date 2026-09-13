"""Agent Engine entry point for the engineering-reviewer agent (staged by deploy.sh).

Builds root_agent exactly like the local adapter assembly — repo prompt via
PROMPTS_DIR plus the agent's immutable config.yaml — minus the HTTP shell.
"""

from __future__ import annotations

from engineering_reviewer import load_config
from engineering_reviewer.agent import build_agent

from agent_kit.ae_runtime import build_root_agent

root_agent = build_root_agent("engineering-reviewer", build_agent, load_config)
