"""Behavior tests for the mock data source (D10).

Directory location = local tests and the compose profile; `gs://` location =
Cloud Run. Both run the same preparation pipeline at load time. The fake
storage client stands in for the network: same call surface as
`google.cloud.storage`, bytes identical to the dataset files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from story_mcp.backlog import StoryNotFound
from story_mcp.mock_source import MockBacklogSource

STORIES_DIR = Path(__file__).resolve().parents[3] / "dataset" / "stories"


class FakeBlob:
    def __init__(self, path: Path, name: str) -> None:
        self._path = path
        self.name = name

    def download_as_text(self) -> str:  # storage.Blob call surface used
        return self._path.read_text()


class FakeBucket:
    def __init__(self, root: Path) -> None:
        self._root = root

    def list_blobs(self, prefix: str = ""):
        base = self._root / prefix
        for path in sorted(base.rglob("*.json")):
            rel = path.relative_to(self._root).as_posix()
            yield FakeBlob(path, rel)


class FakeStorageClient:
    def __init__(self, root: Path) -> None:
        self._root = root
        self.requested_buckets: list[str] = []
        self.requested_prefixes: list[str] = []

    def bucket(self, bucket_name: str):
        self.requested_buckets.append(bucket_name)
        client = self

        class _PrefixBucket(FakeBucket):
            def list_blobs(self, prefix: str = ""):
                client.requested_prefixes.append(prefix)
                return super().list_blobs(prefix)

        return _PrefixBucket(self._root)


class TestDirectoryLocation:
    def test_loads_full_dataset_at_construction(self):
        source = MockBacklogSource.from_location(str(STORIES_DIR), client=None)
        assert len(source.list_stories(None)) == 45

    def test_get_story_returns_prepared_detail(self):
        source = MockBacklogSource.from_location(str(STORIES_DIR), client=None)
        detail = source.get_story("story-01")
        assert detail.story_id == "story-01"
        assert detail.title  # mapped content, not an empty shell

    def test_ado_ids_are_story_not_found(self):
        source = MockBacklogSource.from_location(str(STORIES_DIR), client=None)
        with pytest.raises(StoryNotFound):
            source.get_story("ado-5")

    def test_unknown_story_id_is_story_not_found(self):
        source = MockBacklogSource.from_location(str(STORIES_DIR), client=None)
        with pytest.raises(StoryNotFound):
            source.get_story("story-99")

    def test_filter_applies_to_status(self):
        source = MockBacklogSource.from_location(str(STORIES_DIR), client=None)
        assert source.list_stories("new") == source.list_stories(None)


class TestBucketLocation:
    def test_gs_uri_uses_bucket_and_prefix(self, tmp_path):
        # Re-publish the dataset files under a bucket-like prefix.
        bucket_root = tmp_path / "bucket"
        for sub in ("t1", "t2", "t3", "t4", "t5", "t6", "context"):
            (bucket_root / "stories" / sub).mkdir(parents=True)
            for path in (STORIES_DIR / sub).glob("*.json"):
                (bucket_root / "stories" / sub / path.name).write_text(path.read_text())

        client = FakeStorageClient(bucket_root)
        source = MockBacklogSource.from_location(
            "gs://example-bucket/stories/", client=client
        )
        assert client.requested_buckets == ["example-bucket"]
        assert client.requested_prefixes == ["stories/"]
        assert len(source.list_stories(None)) == 45
        assert source.get_story("story-07").story_id == "story-07"

    def test_bad_scheme_rejected(self):
        with pytest.raises(ValueError):
            MockBacklogSource.from_location("s3://nope", client=None)
