"""Behavior tests for `GcsArtifactService` against fake GCS.

Covers the mcp-servers.md artifact rules: lineage scoping, idempotency
(keyed per run/type/key, content-mismatch conflict), immutability via
versioning, `(type, perspective, version)` ordering with pagination and
`is_latest`, and canonical checksums.
"""

from __future__ import annotations

import uuid

import pytest

from artifact_mcp.storage import (
    ArtifactNotFound,
    GcsArtifactService,
    IdempotencyKeyReused,
)
from review_schemas.mcp import (
    GetArtifactInput,
    ListArtifactsInput,
    SaveArtifactInput,
)

from tests.conftest import (
    artifact_id,
    business_review,
    engineering_review,
    run_id,
    story_detail,
)


@pytest.fixture()
def service(bucket_name: str, gcs_endpoint: str) -> GcsArtifactService:
    return GcsArtifactService(bucket=bucket_name, endpoint=gcs_endpoint)


def _save_story(service: GcsArtifactService, run: str, key=None, content=None):
    return service.save(
        SaveArtifactInput(
            type="story",
            story_run_id=run,
            content=content or story_detail(),
            idempotency_key=key or uuid.uuid4(),
        )
    )


def test_save_creates_first_version(service: GcsArtifactService):
    run = run_id()
    output = _save_story(service, run)
    assert output.created is True
    assert output.reference.version == 1
    assert output.reference.type == "story"
    assert output.reference.story_run_id == run
    assert output.reference.checksum_sha256  # canonical content checksum
    assert not output.reference.is_latest  # flagged in list results only


def test_retry_same_key_same_content_returns_existing(service: GcsArtifactService):
    run = run_id()
    key = uuid.uuid4()
    first = _save_story(service, run, key=key)
    retry = _save_story(service, run, key=key)
    assert retry.created is False
    assert retry.reference == first.reference


def test_same_key_different_content_is_idempotency_reused(service: GcsArtifactService):
    run = run_id()
    key = uuid.uuid4()
    _save_story(service, run, key=key)
    with pytest.raises(IdempotencyKeyReused):
        _save_story(service, run, key=key, content=story_detail("story-02"))


def test_same_key_different_run_is_independent(service: GcsArtifactService):
    key = uuid.uuid4()
    first = _save_story(service, run_id(), key=key)
    second = _save_story(service, run_id(), key=key)
    assert second.created is True
    assert second.reference.artifact_id != first.reference.artifact_id


def test_re_review_creates_new_version_same_type(service: GcsArtifactService):
    run = run_id()
    key = uuid.uuid4()
    _save_story(service, run, key=key)
    again = _save_story(service, run, key=uuid.uuid4())
    assert again.reference.version == 2


def test_get_round_trips_content(service: GcsArtifactService):
    run = run_id()
    saved = _save_story(service, run)
    got = service.get(
        GetArtifactInput(artifact_id=saved.reference.artifact_id, story_run_id=run)
    )
    assert got.reference == saved.reference
    assert got.content == story_detail()


def test_get_unknown_artifact_is_not_found(service: GcsArtifactService):
    with pytest.raises(ArtifactNotFound):
        service.get(GetArtifactInput(artifact_id=artifact_id(), story_run_id=run_id()))


def test_get_never_crosses_runs(service: GcsArtifactService):
    run = run_id()
    saved = _save_story(service, run)
    with pytest.raises(ArtifactNotFound):
        service.get(
            GetArtifactInput(
                artifact_id=saved.reference.artifact_id, story_run_id=run_id()
            )
        )


def _save_reviews(service: GcsArtifactService, run: str) -> None:
    for perspective, report in (
        ("review-business", business_review()),
        ("review-engineering", engineering_review()),
    ):
        service.save(
            SaveArtifactInput(
                type=perspective,
                story_run_id=run,
                perspective=report.perspective,
                content=report,
                idempotency_key=uuid.uuid4(),
            )
        )


def test_list_orders_by_type_perspective_version(service: GcsArtifactService):
    run = run_id()
    _save_story(service, run)
    _save_reviews(service, run)
    listed = service.list(ListArtifactsInput(story_run_id=run))
    assert [r.type for r in listed.items] == [
        "review-business",
        "review-engineering",
        "story",
    ]
    assert listed.total == 3
    assert all(r.is_latest for r in listed.items)


def test_list_flags_only_latest_per_type_perspective(service: GcsArtifactService):
    run = run_id()
    _save_story(service, run)
    _save_story(service, run)
    listed = service.list(ListArtifactsInput(story_run_id=run))
    assert [r.version for r in listed.items] == [1, 2]
    assert [r.is_latest for r in listed.items] == [False, True]


def test_list_filters_by_type_and_perspective(service: GcsArtifactService):
    run = run_id()
    _save_reviews(service, run)
    listed = service.list(
        ListArtifactsInput(story_run_id=run, type="review-business", perspective="business")
    )
    assert [r.type for r in listed.items] == ["review-business"]
    cross = service.list(
        ListArtifactsInput(story_run_id=run, perspective="business")
    )
    assert [r.type for r in cross.items] == ["review-business"]


def test_list_pagination_limit_offset(service: GcsArtifactService):
    run = run_id()
    _save_reviews(service, run)
    page = service.list(ListArtifactsInput(story_run_id=run, limit=1, offset=1))
    assert [r.type for r in page.items] == ["review-engineering"]
    assert page.total == 2  # run-wide total, not page size


def test_list_other_run_is_empty(service: GcsArtifactService):
    run = run_id()
    _save_story(service, run)
    assert service.list(ListArtifactsInput(story_run_id=run_id())).items == []


def test_checksum_is_canonical(service: GcsArtifactService):
    run = run_id()
    saved = _save_story(service, run)
    again = _save_story(service, run_id(), content=story_detail())
    assert again.reference.checksum_sha256 == saved.reference.checksum_sha256


def test_orphaned_key_writes_missing_record_not_duplicate(service: GcsArtifactService):
    """Crash window: key claimed, record never written — the retry fills the
    record under the claimed id instead of creating a second version."""
    run = run_id()
    key = uuid.uuid4()
    orphan = f"art-{uuid.uuid4()}"
    from artifact_mcp.storage import _IDEM_KEY

    service._bucket().blob(_IDEM_KEY.format(run=run, type="story", key=key)).upload_from_string(
        __import__("json").dumps({"artifact_id": orphan})
    )
    output = _save_story(service, run, key=key)
    assert output.created is True
    assert output.reference.artifact_id == orphan
    assert output.reference.version == 1
    listed = service.list(ListArtifactsInput(story_run_id=run))
    assert listed.total == 1
