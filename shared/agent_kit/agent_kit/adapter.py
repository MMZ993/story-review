"""Shared single-turn reviewer adapter core (both reviewer adapters).

Implements the frozen reviewer invocation contract (Phase 5 plan appendix)
once, parameterized by (slug, perspective, agent builder): pure assembly
agreement checks + envelope stamping, the single-turn ADK run (the only
model I/O), and the FastAPI shell with `ErrorEnvelope` error mapping. The
business and engineering adapters in `deploy/compose/adapters/` are thin
configurations of this core.
"""

from __future__ import annotations

import json
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, ValidationError

from agent_kit.config import AgentConfig
from agent_kit.prompts import LoadedPrompt, load_prompt
from agent_kit.reviewer_input import ReviewerRequest, render_reviewer_message
from review_schemas import ErrorBody, ErrorEnvelope, ReviewReport
from review_schemas.base import Sha256, ShortText

PERSPECTIVES = ("business", "engineering")


class ReviewerResponse(BaseModel):
    """Typed single-turn reviewer invocation output (frozen contract)."""

    report: ReviewReport
    agent_version: ShortText
    prompt_sha256: Sha256


class ReportMismatchError(Exception):
    """Model output disagrees with the request; mapped to a structured
    VALIDATION_ERROR by the HTTP shell (which owns the correlation id)."""


class OutputParseError(Exception):
    """The model reply is not valid `ReviewReport` JSON (non-retryable)."""


def assemble_response(
    report: ReviewReport,
    request: ReviewerRequest,
    prompt: LoadedPrompt,
    agent_version: str,
    perspective: str,
) -> ReviewerResponse:
    """Validate request/response agreement and stamp the adapter envelope.

    Raises ReportMismatchError when the model echoed the wrong perspective,
    story id, or a version number without a previous review — the normal
    structured error path (no corrective re-prompt for reviewers, D13-3).
    """
    if report.perspective != perspective:
        raise ReportMismatchError(
            f"report perspective {report.perspective!r} is not {perspective!r}"
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


async def run_reviewer(agent: LlmAgent, user_message: str, app_name: str) -> ReviewReport:
    """One fresh single-turn run; returns the parsed typed report.

    Transport-level failures propagate to the HTTP shell's error mapping; a
    structurally invalid model reply raises OutputParseError (the normal
    structured error path, after ADK's own transport retries).
    """
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id="reviewer-run"
    )
    events = runner.run_async(
        user_id="reviewer-run",
        new_message=types.Content(role="user", parts=[types.Part(text=user_message)]),
        session_id=session.id,
    )
    final_text = ""
    async for event in events:
        for part in event.content.parts if event.content else []:
            if part.text:
                final_text += part.text
    try:
        payload = json.loads(final_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise OutputParseError(f"model reply is not JSON: {exc}") from exc
    try:
        return ReviewReport.model_validate(payload)
    except ValidationError as exc:
        raise OutputParseError(f"model reply fails ReviewReport validation: {exc}") from exc


def error_response(
    status: int, code: str, message: str, agent: str, retry_after: int | None = None
) -> JSONResponse:
    """One `ErrorEnvelope` JSON response with a fresh correlation id."""
    envelope = ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=message[:2000],
            agent=agent,
            correlation_id=uuid.uuid4(),
            retryable=retry_after is not None,
            retry_after_seconds=retry_after,
        )
    )
    return JSONResponse(status_code=status, content=envelope.model_dump(mode="json"))


def create_reviewer_app(
    slug: str,
    perspective: str,
    build_agent_fn,
    load_config_fn,
    agent_version: str,
) -> FastAPI:
    """Build one reviewer adapter app; prompt/config load at startup (loud)."""
    if perspective not in PERSPECTIVES:
        raise ValueError(f"unknown reviewer perspective: {perspective!r}")
    app = FastAPI(title=f"{slug} local adapter", version=agent_version)
    prompt = load_prompt(slug)
    agent = build_agent_fn(prompt, load_config_fn())

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "agent_version": agent_version}

    @app.post("/invoke", response_model=None)
    async def invoke(request: ReviewerRequest) -> ReviewerResponse | JSONResponse:
        try:
            report = await run_reviewer(
                agent, render_reviewer_message(request), app_name=slug
            )
            return assemble_response(
                report, request, prompt, agent_version, perspective
            )
        except (OutputParseError, ReportMismatchError) as exc:
            return error_response(422, "VALIDATION_ERROR", str(exc), agent=slug)
        except Exception as exc:  # model/transport failure after ADK retries
            return error_response(
                503,
                "UPSTREAM_UNAVAILABLE",
                f"model call failed: {exc}",
                agent=slug,
                retry_after=5,
            )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return error_response(400, "VALIDATION_ERROR", str(exc.errors()[:5]), agent=slug)

    return app
