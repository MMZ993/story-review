"""Mock data source: the frozen dataset export behind one interface (D10).

Loads every story envelope from a configurable location — a local directory
(local tests, compose profile) or a `gs://bucket/prefix/` URI (Cloud Run) —
and runs the preparation pipeline once, in memory, at construction. The
image stays dataset-agnostic; only this module ever fetches dataset content.

The GCS client is injectable so tests can stand in for the network; the
production wiring passes ``None`` and gets a ``google.cloud.storage`` client.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from review_schemas.review import StoryDetail, StorySummary

from story_mcp.backlog import StoryNotFound, apply_filter, check_id_space
from story_mcp.prepare import PreparedBacklog, prepare_backlog


class MockBacklogSource:
    """Serves the prepared frozen backlog; no network after construction."""

    def __init__(self, backlog: PreparedBacklog) -> None:
        if not backlog.details:
            raise ValueError("story dataset location contains no story envelopes")
        self._backlog = backlog

    @classmethod
    def from_location(cls, location: str, *, client=None) -> "MockBacklogSource":
        """Build the source from a directory path or a ``gs://`` URI.

        Raises ValueError for any other location scheme, a missing directory,
        or a location that yields zero prepared stories (fail loud at
        startup — an empty backlog is always a misconfiguration).
        """
        if location.startswith("gs://"):
            stories_dir = _materialize_bucket(location, client)
            try:
                return cls(prepare_backlog(stories_dir))
            finally:
                # The temp copy of the bucket content is disposable; the
                # prepared backlog is fully in memory by now.
                _remove_tree(stories_dir)
        path = Path(location)
        if not path.is_dir():
            raise ValueError(f"unsupported story dataset location: {location!r}")
        return cls(prepare_backlog(path))

    def list_stories(self, status_filter: str | None) -> list[StorySummary]:
        return apply_filter(self._backlog.summaries, status_filter)

    def get_story(self, story_id: str) -> StoryDetail:
        check_id_space("mock", story_id)
        try:
            return self._backlog.details[story_id]
        except KeyError:
            raise StoryNotFound(story_id) from None


def _materialize_bucket(location: str, client) -> Path:
    """Download the dataset files under one prefix into a temp directory."""
    from google.cloud import storage  # imported lazily: server start only

    bucket_name, _, prefix = location[len("gs://") :].partition("/")
    bucket = (client or storage.Client()).bucket(bucket_name)
    target = Path(tempfile.mkdtemp(prefix="story-dataset-"))
    for blob in bucket.list_blobs(prefix=prefix):
        if blob.name == prefix.rstrip("/") + "/":  # directory-marker blob
            continue
        rel = Path(blob.name).relative_to(prefix)
        out = target / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(blob.download_as_text())
    return target


def _remove_tree(root: Path) -> None:
    """Remove the temporary bucket copy (created by this module only)."""
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file() or path.is_symlink():
            path.unlink()
        else:
            path.rmdir()
    root.rmdir()
