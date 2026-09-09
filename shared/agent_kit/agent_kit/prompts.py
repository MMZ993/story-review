"""Fail-loud prompt loader implementing the PROMPTS_DIR contract.

Repository-layout rules (docs/operations/repository-layout.md): an agent
loads only ``PROMPTS_DIR/<agent>.md``; ``PROMPTS_DIR`` defaults to the
runtime-safe absolute path ``/app/prompts``. Startup reads the required
UTF-8 file, fails fast when absent or invalid, computes its SHA-256 over the
file bytes, and returns an immutable record. Agents retain that record for
the life of the process and report ``prompt_sha256`` per invocation.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PROMPTS_DIR = Path("/app/prompts")

# Canonical agent slugs plus the evaluation-only judge; the loader itself is
# slug-agnostic beyond the syntax check, so new slugs need no code change.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class LoadedPrompt:
    """An immutable prompt record: slug, exact text, and its SHA-256."""

    slug: str
    text: str
    sha256: str


def _resolve_prompts_dir(prompts_dir: Path | str | None) -> Path:
    """Explicit argument wins, then PROMPTS_DIR, then the /app default."""
    if prompts_dir is not None:
        return Path(prompts_dir)
    env_dir = os.environ.get("PROMPTS_DIR")
    if env_dir:
        return Path(env_dir)
    return DEFAULT_PROMPTS_DIR


def load_prompt(slug: str, prompts_dir: Path | str | None = None) -> LoadedPrompt:
    """Load and hash ``<prompts_dir>/<slug>.md``; fail loud on any problem.

    Raises ValueError for an invalid slug or a non-UTF-8 file, and
    FileNotFoundError when the prompt is absent — startup aborts, never
    silently degrades.
    """
    if not slug or not _SLUG_RE.match(slug):
        raise ValueError(f"invalid agent slug: {slug!r}")

    directory = _resolve_prompts_dir(prompts_dir)
    path = directory / f"{slug}.md"
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"prompt file {path} is not valid UTF-8: {exc}") from exc
    return LoadedPrompt(slug=slug, text=text, sha256=hashlib.sha256(raw).hexdigest())
