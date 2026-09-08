"""Regenerate the preparation golden snapshots (owner-reviewed, D10).

Usage (from ``mcp_servers/story``):

    uv run --no-project --with pytest --with ../../shared/review_schemas \
        --with ../../dataset/loader --with-editable . \
        python tests/generate_golden.py

Writes one ``<story_id>.json`` per prepared story to ``tests/golden/``.
Any diff after a mapping change must be owner-reviewed before committing.
"""

from __future__ import annotations

import json
from pathlib import Path

from story_mcp.prepare import prepare_backlog

STORIES_DIR = Path(__file__).resolve().parents[3] / "dataset" / "stories"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def main() -> None:
    backlog = prepare_backlog(STORIES_DIR)
    GOLDEN_DIR.mkdir(exist_ok=True)
    for story_id, detail in sorted(backlog.details.items()):
        path = GOLDEN_DIR / f"{story_id}.json"
        path.write_text(detail.model_dump_json(indent=2) + "\n")
    print(f"wrote {len(backlog.details)} golden snapshots to {GOLDEN_DIR}")


if __name__ == "__main__":
    main()
