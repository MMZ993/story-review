"""Shared synthesis adapter core.

Implements the frozen synthesis invocation contract (Phase 5 plan
appendix): the single-turn ADK run (the only model I/O) and the FastAPI
shell with `ErrorEnvelope` error mapping. Request/response models and
assembly checks live in `agent_kit.synthesis_input`; the HTTP error
mapping helpers are reused from `agent_kit.adapter`. The synthesis adapter
in `deploy/compose/adapters/synthesis` is a thin binding of this core.
"""

from __future__ import annotations

import json

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import ValidationError

from agent_kit.adapter import error_response
from agent_kit.prompts import LoadedPrompt, load_prompt
from agent_kit.synthesis_input import (
    SynthesisMismatchError,
    SynthesisRequest,
    SynthesisResponse,
    assemble_synthesis_response,
    render_synthesis_message,
)
from review_schemas import SynthesisReport


class SynthesisOutputParseError(Exception):
    """The model reply is not valid `SynthesisReport` JSON (non-retryable)."""


async def run_synthesis(
    agent: LlmAgent, user_message: str, app_name: str
) -> SynthesisReport:
    """One fresh single-turn run; returns the parsed typed report.

    Transport-level failures propagate to the HTTP shell's error mapping; a
    structurally invalid model reply raises SynthesisOutputParseError (the
    normal structured error path, after ADK's own transport retries).
    """
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id="synthesis-run"
    )
    events = runner.run_async(
        user_id="synthesis-run",
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
        raise SynthesisOutputParseError(f"model reply is not JSON: {exc}") from exc
    try:
        return SynthesisReport.model_validate_json(final_text)
    except ValidationError as exc:
        raise SynthesisOutputParseError(
            f"model reply fails SynthesisReport validation: {exc}"
        ) from exc


def create_synthesis_app(
    slug: str, build_agent_fn, load_config_fn, agent_version: str
) -> FastAPI:
    """Build the synthesis adapter app; prompt/config load at startup (loud)."""
    app = FastAPI(title=f"{slug} local adapter", version=agent_version)
    prompt: LoadedPrompt = load_prompt(slug)
    agent = build_agent_fn(prompt, load_config_fn())

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "agent_version": agent_version}

    @app.post("/invoke", response_model=None)
    async def invoke(request: Request) -> SynthesisResponse | JSONResponse:
        """Validate the raw body in JSON mode: strict models still parse
        ISO datetimes from JSON strings (python-mode would reject them)."""
        try:
            parsed = SynthesisRequest.model_validate_json(await request.body())
        except ValidationError as exc:
            return error_response(400, "VALIDATION_ERROR", str(exc.errors()[:5]), agent=slug)
        try:
            report = await run_synthesis(
                agent, render_synthesis_message(parsed), app_name=slug
            )
            return assemble_synthesis_response(report, parsed, prompt, agent_version)
        except (SynthesisOutputParseError, SynthesisMismatchError) as exc:
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
