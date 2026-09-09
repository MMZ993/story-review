"""Serving-safe LLM-facing output mirrors (D13 amendment 1).

Vertex AI structured output rejects the strict shared models (regex
patterns on strings, array `max_length`s, bounded integers, date-time
formats — "too many states for serving", Runbook 11 §1). These mirrors keep
the exact field names with plain serving-safe types so ADK's native
`output_schema` enforcement can run against Vertex; the shared strict
models remain the sole validation authority — every model payload is
validated through them unchanged at the adapter boundary, and failures take
the normal structured-error path.
"""

from __future__ import annotations

from pydantic import BaseModel


class MirrorFinding(BaseModel):
    """Serving-safe mirror of `review_schemas.Finding` (same field names)."""

    id: str
    title: str
    description: str
    severity: str
    category: str
    suggestion: str | None = None
    references_po_question: bool = False


class ServingSafeReviewReport(BaseModel):
    """Serving-safe mirror of `review_schemas.ReviewReport`."""

    perspective: str
    story_id: str
    summary: str
    findings: list[MirrorFinding]
    risks: list[str]
    questions_for_po: list[str]
    based_on_extra_context: str | None = None
    previous_review_version: int | None = None
