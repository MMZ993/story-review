"""HTTP shell of the business-reviewer local adapter.

Exposes the frozen single-turn reviewer invocation as `POST /invoke` on the
local-agents compose profile, mirroring the Agent Engine invocation
boundary. The shell owns error mapping into the shared `ErrorEnvelope`
taxonomy and stamps correlation ids; all model I/O is delegated to
`runner.py`, all pure assembly to `assembly.py`.
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from agent_kit.prompts import load_prompt
from agent_kit.reviewer_input import ReviewerRequest, render_reviewer_message
from business_reviewer import load_config
from business_reviewer.agent import build_agent
from review_schemas import ErrorBody, ErrorEnvelope

from business_reviewer_adapter.assembly import (
    ReportMismatchError,
    ReviewerResponse,
    assemble_response,
)
from business_reviewer_adapter.runner import (
    OutputParseError,
    run_business_reviewer,
)

try:  # pragma: no cover - trivial version lookup
    from importlib.metadata import version as _pkg_version

    AGENT_VERSION = _pkg_version("business-reviewer-agent")
except Exception:  # pragma: no cover
    AGENT_VERSION = "0.0.0+unknown"


def error_response(
    status: int, code: str, message: str, retry_after: int | None = None
) -> JSONResponse:
    """One `ErrorEnvelope` JSON response with a fresh correlation id."""
    envelope = ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=message[:2000],
            agent="business-reviewer",
            correlation_id=uuid.uuid4(),
            retryable=retry_after is not None,
            retry_after_seconds=retry_after,
        )
    )
    return JSONResponse(status_code=status, content=envelope.model_dump(mode="json"))


def create_app() -> FastAPI:
    """Build the adapter app; prompt and config load at startup (loud)."""
    app = FastAPI(title="business-reviewer local adapter", version=AGENT_VERSION)
    prompt = load_prompt("business-reviewer")
    agent = build_agent(prompt, load_config())

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "agent_version": AGENT_VERSION}

    @app.post("/invoke", response_model=None)
    async def invoke(request: ReviewerRequest) -> ReviewerResponse | JSONResponse:
        try:
            report = await run_business_reviewer(
                agent, render_reviewer_message(request)
            )
            return assemble_response(report, request, prompt, AGENT_VERSION)
        except (OutputParseError, ReportMismatchError) as exc:
            return error_response(422, "VALIDATION_ERROR", str(exc))
        except Exception as exc:  # model/transport failure after ADK retries
            return error_response(
                503, "UPSTREAM_UNAVAILABLE", f"model call failed: {exc}", retry_after=5
            )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return error_response(400, "VALIDATION_ERROR", str(exc.errors()[:5]))

    return app
