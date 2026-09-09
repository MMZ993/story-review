"""Behavior tests for the immutable per-agent model config loader.

config.yaml pins model ID + generation settings per agent (tech-stack.md);
the loader enforces known keys, required fields, and returns a frozen
AgentConfig so a deployment cannot drift at runtime.
"""

from __future__ import annotations

import pytest

from agent_kit.config import AgentConfig, load_agent_config


def write_config(directory, body: str) -> None:
    (directory / "config.yaml").write_text(body, encoding="utf-8")


VALID = """\
model: gemini-2.5-flash
location: europe-west4
temperature: 0.0
max_output_tokens: 8192
"""


def test_loads_valid_config_as_frozen_agent_config(tmp_path):
    write_config(tmp_path, VALID)

    config = load_agent_config(tmp_path / "config.yaml")

    assert isinstance(config, AgentConfig)
    assert config.model == "gemini-2.5-flash"
    assert config.location == "europe-west4"
    assert config.temperature == 0.0
    assert config.max_output_tokens == 8192
    with pytest.raises(Exception):
        config.model = "other-model"


def test_missing_config_file_fails_loud(tmp_path):
    with pytest.raises(FileNotFoundError, match="config.yaml"):
        load_agent_config(tmp_path / "config.yaml")


def test_missing_required_key_fails_loud(tmp_path):
    write_config(tmp_path, "model: gemini-2.5-flash\nlocation: europe-west4\n")

    with pytest.raises(ValueError, match="max_output_tokens"):
        load_agent_config(tmp_path / "config.yaml")


def test_unknown_key_fails_loud(tmp_path):
    write_config(tmp_path, VALID + "top_p: 0.5\n")

    with pytest.raises(ValueError, match="top_p"):
        load_agent_config(tmp_path / "config.yaml")


def test_non_map_yaml_fails_loud(tmp_path):
    write_config(tmp_path, "- just\n- a\n- list\n")

    with pytest.raises(ValueError, match="mapping"):
        load_agent_config(tmp_path / "config.yaml")
