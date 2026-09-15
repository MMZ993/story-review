"""Strict judge-config loader for the evaluation suite (Phase 9 increment 0).

Parses tests/evaluation/config.yaml with an exact known key set (the
agent_kit.load_agent_config pattern: no silent defaults, no unknown
drift) and verifies the recorded SHA-256 against the actual judge prompt
file, resolved relative to the repository root.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

_REQUIRED_KEYS = (
    "model",
    "location",
    "temperature",
    "candidate_count",
    "prompt_path",
    "judge_md_sha256",
)


@dataclass(frozen=True)
class JudgeConfig:
    """The pinned judge call configuration plus the verified prompt text."""

    model: str
    location: str
    temperature: float
    candidate_count: int
    prompt_path: str
    judge_md_sha256: str
    prompt_text: str


def load_judge_config(path: Path | str, repo_root: Path | None = None) -> JudgeConfig:
    """Parse and strictly validate the judge config.yaml.

    `prompt_path` is resolved against `repo_root` (default: the repository
    root, i.e. three levels above this file). Raises FileNotFoundError for
    a missing config or prompt file, ValueError for YAML that is not a
    mapping, misses/has unknown keys, wrong-typed values, a
    candidate_count other than 1 (no best-of-N ever), or a SHA-256
    mismatch against the actual prompt file.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"judge config not found: {path}")
    root = repo_root if repo_root is not None else path.resolve().parents[2]

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"judge config {path} must be a YAML mapping")

    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        raise ValueError(f"judge config {path} missing keys: {', '.join(missing)}")
    unknown = [key for key in data if key not in _REQUIRED_KEYS]
    if unknown:
        raise ValueError(
            f"judge config {path} has unknown keys: {', '.join(sorted(unknown))}"
        )
    if data["candidate_count"] != 1:
        raise ValueError(
            f"judge config {path}: candidate_count must be 1 "
            "(best-of-N is prohibited)"
        )

    prompt_file = root / data["prompt_path"]
    if not prompt_file.is_file():
        raise FileNotFoundError(f"judge prompt not found: {prompt_file}")
    prompt_text = prompt_file.read_text(encoding="utf-8")
    actual_sha = hashlib.sha256(prompt_text.encode()).hexdigest()
    if actual_sha != data["judge_md_sha256"]:
        raise ValueError(
            f"judge prompt SHA-256 mismatch for {prompt_file}: "
            f"config records {data['judge_md_sha256']}, file is {actual_sha} "
            "(regenerate the hash after any judge prompt change)"
        )

    return JudgeConfig(prompt_text=prompt_text, **data)
