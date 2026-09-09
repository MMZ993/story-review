"""Business-reviewer local adapter: pure invocation assembly (no I/O).

Implements the frozen reviewer invocation contract (Phase 5 plan appendix)
on the response side: cross-checks the model-produced `ReviewReport` against
the request (perspective, story echo, previous-review version) and stamps
the adapter response (`report`, `agent_version`, `prompt_sha256`). The HTTP
shell and the ADK run live in `app.py`/`runner.py`; everything here is
deterministic and unit-testable without a model.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from agent_kit.prompts import LoadedPrompt
from agent_kit.reviewer_input import ReviewerRequest
from review_schemas import ReviewReport
from review_schemas.base import Sha256, ShortText


class ReviewerResponse(BaseModel):
    """Typed single-turn reviewer invocation output (frozen contract)."""

    model_config = ConfigDict(extra="forbid")

    report: ReviewReport
    agent_version: ShortText
    prompt_sha256: Sha256


class ReportMismatchError(Exception):
    """Model output disagrees with the request; mapped to a structured
    VALIDATION_ERROR by the HTTP shell (which owns the correlation id)."""


def assemble_response(
    report: ReviewReport,
    request: ReviewerRequest,
    prompt: LoadedPrompt,
    agent_version: str,
) -> ReviewerResponse:
    """Validate request/response agreement and stamp the adapter envelope.

    Raises ReportMismatchError when the model echoed the wrong perspective,
    story id, or a version echo without a previous review — the normal structured
    error path (no corrective re-prompt for reviewers, per D13-3).
    """
    if report.perspective != "business":
        raise ReportMismatchError(
            f"report perspective {report.perspective!r} is not 'business'"
        )
    if report.story_id != request.story.story_id:
        raise ReportMismatchError(
            f"report story_id {report.story_id!r} does not match requested "
            f"story {request.story.story_id!r}"
        )
    if request.previous_review is None and report.previous_review_version is not None:
        raise ReportMismatchError(
            "report carries previous_review_version without a previous review"
        )
    return ReviewerResponse(
        report=report,
        agent_version=agent_version,
        prompt_sha256=prompt.sha256,
    )
