"""Report-server and cross-service contracts over the compose wire.

The report server reads the artifact server's bucket layout directly (same
fake-GCS bucket, disjoint prefixes), so a finalized-review saved through the
artifact server must render through the report server — the first test that
exercises two services and their shared storage contract at once.
"""

from __future__ import annotations

from conftest import (
    ARTIFACT_URL,
    BUCKET,
    FAKE_GCS_URL,
    REPORT_URL,
    call_tool,
    error,
    new_key,
    payload,
    run_id,
)


def _render_args(run: str, reference: dict, fmt: str = "md") -> dict:
    return {
        "story_run_id": run,
        "final_review_reference": reference,
        "format": fmt,
    }


def test_render_md_from_live_saved_finalized_review(seeded_finalized):
    run, reference = seeded_finalized()
    result = call_tool(REPORT_URL, "render_report", _render_args(run, reference))
    output = payload(result)
    assert output["created"] is True
    assert output["format"] == "md"
    assert output["reference"]["type"] == "report-md"
    assert output["reference"]["story_run_id"] == run


def test_render_retry_is_idempotent(seeded_finalized):
    run, reference = seeded_finalized()
    first = payload(call_tool(REPORT_URL, "render_report", _render_args(run, reference)))
    second = payload(call_tool(REPORT_URL, "render_report", _render_args(run, reference)))
    assert second["created"] is False
    assert second["reference"]["artifact_id"] == first["reference"]["artifact_id"]


def test_render_pdf(seeded_finalized):
    run, reference = seeded_finalized()
    output = payload(call_tool(REPORT_URL, "render_report", _render_args(run, reference, "pdf")))
    assert output["reference"]["type"] == "report-pdf"


def test_wrong_run_in_render_args_is_error(seeded_finalized):
    run, reference = seeded_finalized()
    result = call_tool(REPORT_URL, "render_report", _render_args(run_id(), reference))
    assert result.is_error


def test_report_lands_in_shared_bucket_prefix(seeded_finalized):
    """Cross-service storage contract: the report server writes into the
    same (fake) bucket under runs/<run>/reports/, while the artifact
    server's listing (runs/<run>/artifacts/) still sees only the seeded
    finalized-review — the prefixes stay disjoint by design."""
    import json
    import urllib.request

    run, reference = seeded_finalized()
    output = payload(call_tool(REPORT_URL, "render_report", _render_args(run, reference)))
    report_id = output["reference"]["artifact_id"]

    with urllib.request.urlopen(f"{FAKE_GCS_URL}/storage/v1/b/{BUCKET}/o?prefix=runs/{run}/reports/") as resp:
        names = [item["name"] for item in json.load(resp)["items"]]
    assert f"runs/{run}/reports/{report_id}.md" in names

    listing = payload(call_tool(ARTIFACT_URL, "list_artifacts", {"story_run_id": run}))
    types = [item["type"] for item in listing["items"]]
    assert types == ["finalized-review"]
