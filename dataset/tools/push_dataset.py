#!/usr/bin/env python3
"""Publish the frozen mock dataset to the story-dataset bucket (D10).

Uploads ``dataset/stories/`` — story envelopes (t1–t6) and the context
envelopes — to ``gs://$PROJECT_ID-story-dataset/stories/``. Expected files
(``dataset/expected/``) are never uploaded; the script refuses to run if it
finds any. Idempotent: re-running overwrites the same object names.

Usage (after ``source infra/envs/home.env``):
    python dataset/tools/push_dataset.py --dry-run   # list what would upload
    python dataset/tools/push_dataset.py             # actual upload
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from google.cloud import storage

DATASET_DIR = Path(__file__).resolve().parents[1]
STORIES_DIR = DATASET_DIR / "stories"
PREFIX = "stories/"


def object_names() -> list[str]:
    return [PREFIX + p.relative_to(STORIES_DIR).as_posix() for p in sorted(STORIES_DIR.rglob("*.json"))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="list objects, upload nothing")
    parser.add_argument("--bucket", help="override bucket name (default $PROJECT_ID-story-dataset)")
    args = parser.parse_args()

    project_id = os.environ.get("PROJECT_ID", "")
    bucket_name = args.bucket or (f"{project_id}-story-dataset" if project_id else "")
    if not bucket_name:
        print("ERROR: PROJECT_ID is not set — source infra/envs/home.env", file=sys.stderr)
        return 2

    if not STORIES_DIR.is_dir():
        print(f"ERROR: {STORIES_DIR} not found", file=sys.stderr)
        return 2

    names = object_names()
    # Defense in depth: only story/context envelopes under stories/ ever
    # upload (expected files live outside this tree by construction).
    assert all(name.startswith(PREFIX) and ".." not in name for name in names)
    print(f"{len(names)} story/context objects → gs://{bucket_name}/{PREFIX}")
    if args.dry_run:
        for name in names:
            print(f"  gs://{bucket_name}/{name}")
        return 0

    client = storage.Client(project=project_id or None)
    bucket = client.bucket(bucket_name)
    for path, name in zip(sorted(STORIES_DIR.rglob("*.json")), names, strict=True):
        bucket.blob(name).upload_from_filename(path, content_type="application/json")
        print(f"  uploaded gs://{bucket_name}/{name}")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
