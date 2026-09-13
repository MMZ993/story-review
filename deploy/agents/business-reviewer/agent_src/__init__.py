"""Agent Engine entry point for the business-reviewer agent (staged by deploy.sh).

Builds root_agent exactly like the local adapter assembly — repo prompt via
PROMPTS_DIR plus the agent's immutable config.yaml — minus the HTTP shell.
"""

from __future__ import annotations

from business_reviewer import load_config
from business_reviewer.agent import build_agent

from agent_kit.ae_runtime import build_root_agent

root_agent = build_root_agent("business-reviewer", build_agent, load_config)
