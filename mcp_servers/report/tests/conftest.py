"""Shared fixtures: fake-GCS endpoint, throwaway bucket, content factories.

The storage-backed tests run against `fsouza/fake-gcs-server` (started by
`make mcp-report-test`, which exports REPORT_TEST_GCS_ENDPOINT). The
finalized-review records are seeded in the artifact server's object layout
(`runs/<run>/artifacts/<id>.json`) — the report server reads that layout
read-only and writes its own `runs/<run>/reports/` prefix, so the two
servers share one bucket without colliding (increment-3 decision).
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage

from review_schemas.facilitator import FinalizedReview
from review_schemas.synthesis import ArtifactReference


def _uuid() -> str:
    return str(uuid.uuid4())


def run_id() -> str:
    return f"run-{uuid.uuid4()}"


def artifact_id() -> str:
    return f"art-{uuid.uuid4()}"


def past_datetime() -> datetime:
    return datetime.now(UTC) - timedelta(minutes=5)


def _checksum(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def synthesis_reference(run: str) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=artifact_id(),
        story_run_id=run,
        type="synthesis",
        version=1,
        created_at=past_datetime(),
        content_type="application/json",
        checksum_sha256="0" * 64,
    )


def finalized_review(run: str, *, po_accepted: bool = True) -> FinalizedReview:
    """A minimal valid FinalizedReview (normal readiness keeps no open
    issues); every referenced id carries a catalog entry (D19)."""
    return FinalizedReview(
        story_id="story-01",
        story_run_id=run,
        synthesis_reference=synthesis_reference(run),
        issues=[
            {
                "issue": "Missing business value statement",
                "title": "Missing business value statement",
                "description": "The story lacks an expected-uptake rationale.",
                "severity": "major",
                "source": "synthesis",
            }
        ],
        resolutions=[
            {
                "issue": "Missing business value statement",
                "disposition": "resolved",
                "explanation": "PO added the expected uptake rationale.",
                "turn_number": 2,
            }
        ],
        remaining_open_issues=[],
        po_accepted=po_accepted,
        final_turn_number=3,
        finalized_at=past_datetime(),
    )


@pytest.fixture(scope="session")
def gcs_endpoint() -> str:
    endpoint = os.environ.get("REPORT_TEST_GCS_ENDPOINT")
    if not endpoint:
        pytest.fail(
            "REPORT_TEST_GCS_ENDPOINT is not set — start fake-gcs-server via "
            "`make mcp-report-test`"
        )
    return endpoint


@pytest.fixture(scope="session")
def bucket_name(gcs_endpoint: str) -> str:
    """A throwaway bucket in the fake GCS server (created once per session)."""
    client = storage.Client(
        project="test-project",
        client_options={"api_endpoint": gcs_endpoint},
        credentials=AnonymousCredentials(),
    )
    bucket = client.create_bucket(f"reports-test-{uuid.uuid4().hex[:10]}")
    return bucket.name


@pytest.fixture()
def seed_finalized(gcs_endpoint: str, bucket_name: str):
    """Write one finalized-review record in the artifact-server layout.

    Returns (ArtifactReference, FinalizedReview) for the seeded record.
    """

    def seed(run: str, review: FinalizedReview | None = None) -> ArtifactReference:
        review = review or finalized_review(run)
        reference = ArtifactReference(
            artifact_id=artifact_id(),
            story_run_id=run,
            type="finalized-review",
            version=1,
            created_at=past_datetime(),
            content_type="application/json",
            checksum_sha256=_checksum(review.model_dump(mode="json")),
        )
        blob = storage.Client(
            project="test-project",
            client_options={"api_endpoint": gcs_endpoint},
            credentials=AnonymousCredentials(),
        ).bucket(bucket_name).blob(f"runs/{run}/artifacts/{reference.artifact_id}.json")
        blob.upload_from_string(
            json.dumps(
                {
                    "reference": reference.model_dump(mode="json"),
                    "content": review.model_dump(mode="json"),
                }
            )
        )
        return reference

    return seed
