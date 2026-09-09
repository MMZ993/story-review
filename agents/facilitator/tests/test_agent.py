"""Deterministic skeleton tests (Phase 5 increment 0): immutable config and
the agent's prompt load via the PROMPTS_DIR contract. No LLM calls."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from facilitator import AGENT_SLUG, load_config
from agent_kit.prompts import load_prompt

_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_slug_matches_directory():
    assert AGENT_SLUG == "facilitator"


def test_config_is_pinned_and_immutable():
    config = load_config()
    assert config.model == "gemini-2.5-flash"
    assert config.location == "europe-west4"
    with pytest.raises(Exception):
        config.model = "other"


def test_prompt_loads_from_repo_prompts_dir_with_stable_hash():
    loaded = load_prompt("facilitator", prompts_dir=_REPO_ROOT / "prompts")
    raw = (_REPO_ROOT / "prompts" / "facilitator.md").read_bytes()
    assert loaded.text == raw.decode("utf-8")
    assert loaded.sha256 == hashlib.sha256(raw).hexdigest()
