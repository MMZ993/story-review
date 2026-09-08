"""Golden snapshot test: preparation output is byte-stable per story file.

The committed snapshots under ``tests/golden/`` were owner-reviewed once
(D10). Any change in the mapping, the flattener, or the dataset itself shows
up as a diff here and must be re-reviewed before the new goldens are
committed (regenerate with ``tests/generate_golden.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

from story_mcp.prepare import prepare_backlog

STORIES_DIR = Path(__file__).resolve().parents[3] / "dataset" / "stories"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def test_every_prepared_story_matches_its_golden_snapshot():
    backlog = prepare_backlog(STORIES_DIR)
    golden_files = sorted(GOLDEN_DIR.glob("*.json"))
    assert len(golden_files) == len(backlog.details) == 45
    for path in golden_files:
        story_id = path.stem
        assert story_id in backlog.details, f"golden {story_id} has no story"
        expected = json.loads(path.read_text())
        assert json.loads(backlog.details[story_id].model_dump_json()) == expected, (
            f"prepared output for {story_id} differs from the golden snapshot"
        )
