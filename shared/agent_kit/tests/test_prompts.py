"""Behavior tests for the fail-loud prompt loader (PROMPTS_DIR contract).

Covers the repository-layout.md rules: UTF-8 static file read once at
startup, missing/invalid file aborts loudly, SHA-256 computed over the file
bytes, loaded text immutable.
"""

from __future__ import annotations

import hashlib

import pytest

from agent_kit.prompts import LoadedPrompt, load_prompt


def write_prompt(directory, slug: str, text: str) -> None:
    (directory / f"{slug}.md").write_text(text, encoding="utf-8")


def test_loads_prompt_text_and_sha256_from_explicit_dir(tmp_path):
    write_prompt(tmp_path, "synthesis", "# Synthesis\nYou merge reviews.")

    loaded = load_prompt("synthesis", prompts_dir=tmp_path)

    assert isinstance(loaded, LoadedPrompt)
    assert loaded.slug == "synthesis"
    assert loaded.text == "# Synthesis\nYou merge reviews."
    assert loaded.sha256 == hashlib.sha256(
        (tmp_path / "synthesis.md").read_bytes()
    ).hexdigest()


def test_prompts_dir_env_is_used_when_no_explicit_dir(tmp_path, monkeypatch):
    write_prompt(tmp_path, "facilitator", "You facilitate.")
    monkeypatch.setenv("PROMPTS_DIR", str(tmp_path))

    loaded = load_prompt("facilitator")

    assert loaded.text == "You facilitate."


def test_missing_prompts_dir_env_falls_back_to_app_default(monkeypatch, tmp_path):
    monkeypatch.delenv("PROMPTS_DIR", raising=False)
    monkeypatch.setattr("agent_kit.prompts.DEFAULT_PROMPTS_DIR", tmp_path)
    write_prompt(tmp_path, "synthesis", "fallback")

    assert load_prompt("synthesis").text == "fallback"


def test_missing_prompt_file_fails_loud_with_slug_and_dir(tmp_path):
    with pytest.raises(FileNotFoundError, match=r"synthesis.md"):
        load_prompt("synthesis", prompts_dir=tmp_path)


def test_non_utf8_prompt_file_fails_loud(tmp_path):
    (tmp_path / "synthesis.md").write_bytes(b"\xff\xfe\x00bad")

    with pytest.raises(ValueError, match="UTF-8"):
        load_prompt("synthesis", prompts_dir=tmp_path)


def test_invalid_slug_rejected_before_filesystem_access(tmp_path):
    for bad_slug in ("", "../story", "Synthesis", "syn thesis", "a/b"):
        with pytest.raises(ValueError, match="slug"):
            load_prompt(bad_slug, prompts_dir=tmp_path)


def test_loaded_prompt_is_immutable(tmp_path):
    write_prompt(tmp_path, "synthesis", "text")

    loaded = load_prompt("synthesis", prompts_dir=tmp_path)

    with pytest.raises(Exception):
        loaded.text = "mutated"
