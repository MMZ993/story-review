"""Unit tests for the judge configuration loader (Phase 9 increment 0).

The loader parses tests/evaluation/config.yaml strictly (exact known key
set, like agent_kit.load_agent_config) and verifies that the recorded
SHA-256 matches the actual prompts/judge.md — a drifted judge prompt must
fail loudly before any model call.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from evaluation.judge_config import JudgeConfig, load_judge_config

REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = REPO_ROOT / "tests" / "evaluation"


def write_case(tmp_path: Path, prompt_text: str, config_body: str) -> Path:
    """Materialize a mini repo layout (config + prompts/judge.md).

    The config sits two levels below the repo root, exactly like the
    shipped tests/evaluation/config.yaml (the loader resolves prompt_path
    against config.parents[2]).
    """
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "judge.md").write_text(prompt_text, encoding="utf-8")
    eval_dir = tmp_path / "tests" / "evaluation"
    eval_dir.mkdir(parents=True)
    config_path = eval_dir / "config.yaml"
    config_path.write_text(config_body, encoding="utf-8")
    return tmp_path


PROMPT = "# judge prompt\nscores five dimensions.\n"

GOOD_BODY = (
    "model: gemini-2.5-pro\n"
    "location: europe-west4\n"
    "temperature: 0.0\n"
    "candidate_count: 1\n"
    "prompt_path: prompts/judge.md\n"
    f"judge_md_sha256: {hashlib.sha256(PROMPT.encode()).hexdigest()}\n"
)


def test_repo_config_loads_and_sha_matches(tmp_path):
    root = write_case(tmp_path, PROMPT, GOOD_BODY)
    cfg = load_judge_config(root / "tests" / "evaluation" / "config.yaml")
    assert cfg == JudgeConfig(
        model="gemini-2.5-pro",
        location="europe-west4",
        temperature=0.0,
        candidate_count=1,
        prompt_path="prompts/judge.md",
        judge_md_sha256=hashlib.sha256(PROMPT.encode()).hexdigest(),
        prompt_text=PROMPT,
    )
    assert cfg.prompt_text == PROMPT


def test_sha_mismatch_raises(tmp_path):
    body = GOOD_BODY.replace("a" * 0, "")  # keep body, corrupt the hash below
    body = body.rsplit("judge_md_sha256: ", 1)[0] + "judge_md_sha256: " + "0" * 64 + "\n"
    write_case(tmp_path, PROMPT, body)
    with pytest.raises(ValueError, match="judge prompt SHA-256 mismatch"):
        load_judge_config(tmp_path / "tests" / "evaluation" / "config.yaml")


def test_missing_key_raises(tmp_path):
    write_case(tmp_path, PROMPT, GOOD_BODY.replace("temperature: 0.0\n", ""))
    with pytest.raises(ValueError, match="missing keys: temperature"):
        load_judge_config(tmp_path / "tests" / "evaluation" / "config.yaml")


def test_unknown_key_raises(tmp_path):
    write_case(tmp_path, PROMPT, GOOD_BODY + "best_of: 3\n")
    with pytest.raises(ValueError, match="unknown keys: best_of"):
        load_judge_config(tmp_path / "tests" / "evaluation" / "config.yaml")


def test_candidate_count_must_be_one(tmp_path):
    write_case(tmp_path, PROMPT, GOOD_BODY.replace("candidate_count: 1", "candidate_count: 3"))
    with pytest.raises(ValueError, match="candidate_count"):
        load_judge_config(tmp_path / "tests" / "evaluation" / "config.yaml")


def test_shipped_repo_config_loads():
    cfg = load_judge_config(EVAL_DIR / "config.yaml")
    assert cfg.model == "gemini-2.5-pro"
    assert cfg.temperature == 0.0
    assert cfg.candidate_count == 1
    assert cfg.prompt_text == (REPO_ROOT / "prompts" / "judge.md").read_text(
        encoding="utf-8"
    )
