"""ReportStore tests against fake GCS (same bucket as the artifact server).

Covers: render-and-save, retry idempotency per (run, format), conflict on
a different finalized-review reference, cross-format independence, missing
finalized review, and md/pdf content types on the references.
"""

from __future__ import annotations

import json

import pytest
from google.cloud import storage

from review_schemas.mcp import RenderReportInput

from report_mcp.storage import (
    FinalizedReviewNotFound,
    IdempotencyConflict,
    ReportStore,
)

from tests.conftest import bucket_name, gcs_endpoint, run_id, seed_finalized


@pytest.fixture()
def store(gcs_endpoint: str, bucket_name: str) -> ReportStore:
    return ReportStore(bucket=bucket_name, endpoint=gcs_endpoint)


def _request(run: str, reference, fmt: str) -> RenderReportInput:
    return RenderReportInput(
        story_run_id=run,
        final_review_reference=reference,
        format=fmt,
    )


def _bucket(gcs_endpoint, bucket_name):
    return storage.Client(
        project="test-project", client_options={"api_endpoint": gcs_endpoint}
    ).bucket(bucket_name)


def test_render_saves_report_artifact(store, seed_finalized, gcs_endpoint, bucket_name):
    import hashlib

    run = run_id()
    reference = seed_finalized(run)
    output = store.render_report(_request(run, reference, "md"))
    assert output.created is True
    assert output.format == "md"
    assert output.reference.type == "report-md"
    assert output.reference.content_type == "text/markdown"
    assert output.reference.version == 1
    blob = _bucket(gcs_endpoint, bucket_name).blob(
        f"runs/{run}/reports/{output.reference.artifact_id}.md"
    )
    rendered = blob.download_as_bytes()
    assert b"story-01" in rendered
    assert (
        hashlib.sha256(rendered).hexdigest() == output.reference.checksum_sha256
    ), "the stored bytes must match the reference checksum"


def test_retry_same_final_review_is_idempotent(store, seed_finalized):
    run = run_id()
    reference = seed_finalized(run)
    first = store.render_report(_request(run, reference, "md"))
    retry = store.render_report(_request(run, reference, "md"))
    assert retry.created is False
    assert retry.reference == first.reference


def test_different_final_review_same_format_conflicts(store, seed_finalized):
    run = run_id()
    first_ref = seed_finalized(run)
    second_ref = seed_finalized(run)
    store.render_report(_request(run, first_ref, "pdf"))
    with pytest.raises(IdempotencyConflict):
        store.render_report(_request(run, second_ref, "pdf"))


def test_md_and_pdf_are_independent(store, seed_finalized):
    run = run_id()
    reference = seed_finalized(run)
    md = store.render_report(_request(run, reference, "md"))
    pdf = store.render_report(_request(run, reference, "pdf"))
    assert md.created and pdf.created
    assert md.reference.content_type == "text/markdown"
    assert pdf.reference.content_type == "application/pdf"
    assert md.reference.artifact_id != pdf.reference.artifact_id


def test_runs_are_isolated(store, seed_finalized):
    run_a, run_b = run_id(), run_id()
    reference = seed_finalized(run_a)
    store.render_report(_request(run_a, reference, "md"))
    other = seed_finalized(run_b)
    output = store.render_report(_request(run_b, other, "md"))
    assert output.created is True  # same format, different run: no conflict


def test_missing_final_review_raises_not_found(store):
    from tests.conftest import artifact_id, past_datetime

    from review_schemas.synthesis import ArtifactReference

    run = run_id()
    ghost = ArtifactReference(
        artifact_id=artifact_id(),
        story_run_id=run,
        type="finalized-review",
        version=1,
        created_at=past_datetime(),
        content_type="application/json",
        checksum_sha256="0" * 64,
    )
    with pytest.raises(FinalizedReviewNotFound):
        store.render_report(_request(run, ghost, "md"))


def test_record_with_wrong_type_is_not_a_finalized_review(
    store, seed_finalized, gcs_endpoint, bucket_name
):
    run = run_id()
    reference = seed_finalized(run)
    # Corrupt the seeded record's reference type (story, not finalized-review).
    key = f"runs/{run}/artifacts/{reference.artifact_id}.json"
    blob = _bucket(gcs_endpoint, bucket_name).blob(key)
    record = json.loads(blob.download_as_bytes())
    record["reference"]["type"] = "story"
    blob.upload_from_string(json.dumps(record))
    with pytest.raises(FinalizedReviewNotFound):
        store.render_report(_request(run, reference, "md"))


def test_orphaned_content_object_is_completed_on_retry(
    store, seed_finalized, gcs_endpoint, bucket_name
):
    """Crash window: idem key + content blob written, meta missing.

    The retry must finish the record (deterministic bytes agree) instead of
    failing forever on the content object's generation-0 precondition.
    """
    import hashlib
    import json as _json

    from report_mcp.render import render_markdown

    from tests.conftest import finalized_review

    run = run_id()
    review = finalized_review(run)
    reference = seed_finalized(run, review)
    # Simulate the crash: claim the key and write only the content object.
    orphan_id = "art-00000000-0000-0000-0000-00000000cafe"
    bucket = _bucket(gcs_endpoint, bucket_name)
    bucket.blob(f"runs/{run}/report-idem/md").upload_from_string(
        _json.dumps(
            {
                "artifact_id": orphan_id,
                "final_review_artifact_id": reference.artifact_id,
                "final_review_checksum": reference.checksum_sha256,
            }
        )
    )
    bucket.blob(f"runs/{run}/reports/{orphan_id}.md").upload_from_string(
        render_markdown(review).encode("utf-8")
    )
    output = store.render_report(_request(run, reference, "md"))
    assert output.created is True
    assert output.reference.artifact_id == orphan_id
    meta = bucket.blob(f"runs/{run}/reports/{orphan_id}.json")
    assert meta.exists(), "the retry must complete the missing meta record"


def test_checksum_mismatch_against_stored_record_is_rejected(
    store, seed_finalized
):
    run = run_id()
    reference = seed_finalized(run)
    stale = reference.model_copy(update={"checksum_sha256": "f" * 64})
    with pytest.raises(ValueError, match="checksum"):
        store.render_report(_request(run, stale, "md"))
