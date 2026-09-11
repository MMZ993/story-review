"""Deterministic renderer tests (no GCS).

MD and PDF are pure functions of the FinalizedReview content: identical
input must produce byte-identical output (the design's determinism rule),
and the rendered document must carry the finalized review's facts.
"""

from __future__ import annotations

from tests.conftest import finalized_review, run_id

from report_mcp.render import render_markdown, render_pdf
from review_schemas.facilitator import IssueEntry


def _review() -> object:
    return finalized_review(run_id())


def test_markdown_is_deterministic() -> None:
    review = _review()
    assert render_markdown(review) == render_markdown(review)


def test_markdown_carries_the_finalized_facts() -> None:
    text = render_markdown(_review())
    assert "story-01" in text
    assert "Resolutions" in text
    assert "Missing business value statement" in text
    assert "resolved" in text
    assert "PO acceptance" in text
    assert "accepted" in text


def test_markdown_lists_remaining_open_issues() -> None:
    review = finalized_review(run_id(), po_accepted=True)
    review = review.model_copy(
        update={
            "remaining_open_issues": ["B-2"],
            "issues": [
                *review.issues,
                IssueEntry(
                    issue="B-2",
                    title="Localization scope unresolved",
                    description="No target locales agreed.",
                    source="synthesis",
                ),
            ],
        }
    )
    text = render_markdown(review)
    assert "Localization scope unresolved" in text


def test_markdown_renders_the_issue_catalog() -> None:
    review = _review()
    text = render_markdown(review)
    assert "## Issues" in text
    # every catalog entry: id, title, severity where known, source
    assert "Missing business value statement" in text
    assert "from synthesis" in text or "raised by facilitator" in text


def test_markdown_annotates_ids_with_catalog_titles() -> None:
    review = finalized_review(run_id(), po_accepted=True)
    review = review.model_copy(
        update={
            "remaining_open_issues": ["B-2"],
            "issues": [
                *review.issues,
                IssueEntry(
                    issue="B-2",
                    title="Localization scope unresolved",
                    description="No target locales agreed.",
                    severity="major",
                    source="facilitator",
                ),
            ],
        }
    )
    text = render_markdown(review)
    # remaining-open bullets carry the title next to the id
    assert "- B-2 — Localization scope unresolved" in text


def test_markdown_with_no_resolutions_renders_a_placeholder() -> None:
    review = finalized_review(run_id()).model_copy(update={"resolutions": []})
    text = render_markdown(review)
    assert "None" in text


def test_pdf_is_deterministic() -> None:
    review = _review()
    assert render_pdf(review) == render_pdf(review)


def test_pdf_is_a_pdf() -> None:
    assert render_pdf(_review()).startswith(b"%PDF-")


def test_pdf_differs_for_different_content() -> None:
    review = _review()
    other = review.model_copy(update={"po_accepted": False, "remaining_open_issues": []})
    assert render_pdf(review) != render_pdf(other)
