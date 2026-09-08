"""Shared fixtures: fake-GCS endpoint, throwaway bucket, content factories.

The storage-backed tests run against `fsouza/fake-gcs-server` (the same
substitute the local compose profile uses, per repository-layout.md). The
`make mcp-artifact-test` target starts the container and exports
`ARTIFACT_TEST_GCS_ENDPOINT`; running pytest without it fails loudly here
rather than silently skipping the only tests that exercise GCS.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from google.cloud import storage

from review_schemas.review import ReviewReport, StoryDetail


def _uuid_hex() -> str:
    return uuid.uuid4().hex


def run_id() -> str:
    return f"run-{uuid.uuid4()}"


def artifact_id() -> str:
    return f"art-{uuid.uuid4()}"


@pytest.fixture(scope="session")
def gcs_endpoint() -> str:
    endpoint = os.environ.get("ARTIFACT_TEST_GCS_ENDPOINT")
    if not endpoint:
        pytest.fail(
            "ARTIFACT_TEST_GCS_ENDPOINT is not set — start fake-gcs-server via "
            "`make mcp-artifact-test`"
        )
    return endpoint


@pytest.fixture(scope="session")
def bucket_name(gcs_endpoint: str) -> str:
    """A throwaway bucket in the fake GCS server (created once per session)."""
    client = storage.Client(
        project="test-project", client_options={"api_endpoint": gcs_endpoint}
    )
    bucket = client.create_bucket(f"artifacts-test-{_uuid_hex()[:10]}")
    return bucket.name


def story_detail(story_id: str = "story-01") -> StoryDetail:
    return StoryDetail(
        story_id=story_id,
        title="Invoice PDF in the confirmation email",
        status="New",
        description="Buyers receive the invoice as a PDF attachment.",
        acceptance_criteria=["PDF attached", "Email within 5 minutes"],
        epic_context="Epic — Feature",
        roadmap_context="Roadmap context text.",
    )


def business_review(story_id: str = "story-01") -> ReviewReport:
    return ReviewReport(
        perspective="business",
        story_id=story_id,
        summary="Business review of the invoice PDF story.",
        findings=[],
    )


def engineering_review(story_id: str = "story-01") -> ReviewReport:
    return ReviewReport(
        perspective="engineering",
        story_id=story_id,
        summary="Engineering review of the invoice PDF story.",
        findings=[],
    )


def past_datetime() -> datetime:
    return datetime.now(UTC) - timedelta(minutes=5)
