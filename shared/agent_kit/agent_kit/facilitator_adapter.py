"""Shared facilitator adapter core (session-scoped turns).

Implements the frozen facilitator invocation contract (Phase 5 plan
appendix): one session-scoped ADK run per turn against the injected
session service (DatabaseSessionService on the compose Postgres in the
local-agents profile), a bounded corrective re-prompt loop for malformed
delegation output (at most two, per observability.md; exhaustion returns
`DELEGATION_VALIDATION`), and the adapter-side tool-argument guard (story
id space; artifact reads limited to the supplied lineage). The FastAPI
shell reuses the `ErrorEnvelope` mapping from `agent_kit.adapter`.

The model I/O boundary is the `send` callable (message -> final reply
text), so the correction loop and guard are deterministically testable;
the HTTP shell wires `send` to the real ADK Runner.

Phase 6 extension (D15-6): completed turn results are persisted per
(session_id, invocation_id) in a `TurnResultStore` (the binding layer
backs it with the session-backend Postgres) and exposed via
`GET /turn-result/{session_id}/{invocation_id}`; a repeated `POST /turn`
for a completed invocation returns the stored result without a model run
— the reconciliation seam for ambiguous facilitator timeouts.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, get_args, Protocol

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StreamableHTTPConnectionParams,
)
from google.genai import types
from pydantic import StringConstraints, ValidationError

from agent_kit.adapter import error_response
from agent_kit.config import AgentConfig
from agent_kit.prompts import LoadedPrompt, load_prompt
from agent_kit.facilitator_input import (
    FacilitatorRequest,
    FacilitatorResponse,
    FacilitatorTurnInvalid,
    render_facilitator_message,
    validate_turn_output,
)
from agent_kit.telemetry import TelemetryCallbacks
from agent_kit.structured_logging import configure_logging
from review_schemas import FacilitatorTurnOutput
from review_schemas.base import StoryId

CORRECTIVE_MAX = 2

_STORY_PATTERN = next(
    a.pattern for a in get_args(StoryId) if isinstance(a, StringConstraints)
)


class TurnResultStore(Protocol):
    """Reconciliation seam (D15-6): one stored response per completed
    (session_id, invocation_id); a lookup miss means the run never
    completed remotely and may be re-invoked."""

    async def save(
        self, session_id: str, invocation_id: uuid.UUID, response: FacilitatorResponse
    ) -> None: ...

    async def lookup(
        self, session_id: str, invocation_id: uuid.UUID
    ) -> FacilitatorResponse | None: ...


class InMemoryTurnResultStore:
    """Deterministic in-process store (tests and no-database shells)."""

    def __init__(self) -> None:
        self._results: dict[tuple[str, uuid.UUID], FacilitatorResponse] = {}

    async def save(
        self, session_id: str, invocation_id: uuid.UUID, response: FacilitatorResponse
    ) -> None:
        self._results.setdefault((session_id, invocation_id), response)

    async def lookup(
        self, session_id: str, invocation_id: uuid.UUID
    ) -> FacilitatorResponse | None:
        return self._results.get((session_id, invocation_id))


def _result_store_lifespan(result_store: TurnResultStore | None):
    """Lifespan that opens/closes the result store when it owns
    resources (Postgres pool); stateless stores are left alone."""

    @asynccontextmanager
    async def _lifespan(_: FastAPI):
        if result_store is not None and hasattr(result_store, "startup"):
            await result_store.startup()
        try:
            yield
        finally:
            if result_store is not None and hasattr(result_store, "shutdown"):
                await result_store.shutdown()

    return _lifespan


class DelegationValidationError(Exception):
    """Corrective re-prompts exhausted without a valid turn output; mapped
    to HTTP 422 `DELEGATION_VALIDATION` (non-retryable: produce a new PO
    turn)."""


def _parse_turn_output(reply: str) -> FacilitatorTurnOutput:
    """Strict parse of one model reply into a validated turn output.

    Raises ValidationError (not valid strict FacilitatorTurnOutput JSON)
    or FacilitatorTurnInvalid (turn-context rules) — both are malformed
    delegation output and enter the corrective loop.
    """
    try:
        payload = json.loads(reply)
    except (json.JSONDecodeError, TypeError) as exc:
        raise FacilitatorTurnInvalid(f"reply is not JSON: {exc}") from exc
    return FacilitatorTurnOutput.model_validate(payload)


def _invalid_reasons(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5]
        )
    return str(exc)


def corrective_message(reasons: str) -> str:
    """The re-prompt appended after a malformed turn output (pure)."""
    return (
        "Your previous reply was not a valid FacilitatorTurnOutput:\n"
        f"{reasons}\n\n"
        "Reply again with a single corrected FacilitatorTurnOutput as JSON "
        "only — no prose outside the JSON object."
    )


async def turn_with_corrections(
    send: Send, request: FacilitatorRequest
) -> tuple[FacilitatorTurnOutput, int]:
    """Run one turn, re-prompting malformed delegation output at most
    `CORRECTIVE_MAX` times.

    Returns the validated output and the corrective-reprompt count. Raises
    DelegationValidationError on exhaustion (after the initial attempt plus
    at most CORRECTIVE_MAX corrective runs).

    Corrective messages are appended to the persistent ADK session (the
    dialogue memory keeps the rejected replies and the correction request —
    deliberate, per observability.md: corrective re-prompts are recorded,
    not hidden).
    """
    message = render_facilitator_message(request)
    corrections = 0
    while True:
        reply = await send(message)
        try:
            output = _parse_turn_output(reply)
            validate_turn_output(output, request)
            return output, corrections
        except (ValidationError, FacilitatorTurnInvalid) as exc:
            if corrections >= CORRECTIVE_MAX:
                raise DelegationValidationError(
                    f"no valid turn output after {CORRECTIVE_MAX} corrective "
                    f"re-prompts: {_invalid_reasons(exc)}"
                ) from exc
            corrections += 1
            message = corrective_message(_invalid_reasons(exc))


def lineage_tool_guard(tool: Any, args: dict, request: FacilitatorRequest | None):
    """Adapter-side tool-argument validation (plan: risks and controls).

    Returns None when the call may proceed, or an error dict that becomes
    the tool's result (the model sees the rejection and can correct).
    Story tools are open to the public id space but may not override the
    data source (orchestration-only); artifact reads are lineage-scoped to
    the current request's story run and the supplied references.
    """
    if request is None:
        return {"error": "no facilitator turn is active"}
    name = getattr(tool, "name", str(tool))
    if name in ("get_story", "list_stories"):
        if args.get("source") is not None:
            return {"error": "source override is orchestration-only; omit it"}
        story_id = args.get("story_id")
        if story_id is not None and not re.match(
            f"^(?:{_STORY_PATTERN})$", str(story_id)
        ):
            return {"error": f"invalid story id {story_id!r}"}
        return None
    if name in ("get_artifact", "list_artifacts"):
        run_id = args.get("story_run_id")
        if run_id != request.story_run_id:
            return {
                "error": "artifact reads are lineage-scoped to the current "
                f"story run {request.story_run_id}"
            }
        artifact_id = args.get("artifact_id")
        if artifact_id is not None:
            allowed = {ref.artifact_id for ref in request.evidence_references}
            allowed.add(request.synthesis_reference.artifact_id)
            if artifact_id not in allowed:
                return {
                    "error": "artifact is not in this turn's lineage: use "
                    "only the references supplied in the turn context"
                }
        return None
    return {"error": f"tool {name!r} is not permitted for the facilitator"}


# --- HTTP shell -----------------------------------------------------------

Send = Callable[[str], Awaitable[str]]

_current_request: ContextVar[FacilitatorRequest | None] = ContextVar(
    "facilitator_current_request", default=None
)

STORY_TOOLS = ["get_story", "list_stories"]
ARTIFACT_READ_TOOLS = ["get_artifact", "list_artifacts"]


def _guarded_tool_call(tool, args, tool_context=None, **_):
    """`before_tool_callback` binding of `lineage_tool_guard` to the
    current turn's request (set per HTTP request via contextvar)."""
    return lineage_tool_guard(tool, args, _current_request.get())


def make_send(runner: Runner, request: FacilitatorRequest) -> Send:
    """Bind one session-scoped ADK run to the corrective loop.

    Each call appends the message to the facilitator session (ADK session
    id = request.session_id, user_id fixed) and returns the final reply
    text of the run — the text of the LAST event carrying text (intermediate
    partials must not pollute the strict JSON parse).
    """
    user_id = "po"

    async def send(message: str) -> str:
        events = runner.run_async(
            user_id=user_id,
            new_message=types.Content(
                role="user", parts=[types.Part(text=message)]
            ),
            session_id=request.session_id,
        )
        final_text = ""
        async for event in events:
            event_text = "".join(
                part.text
                for part in event.content.parts
                if event.content and part.text
            )
            if event_text:
                final_text = event_text
        return final_text

    return send


def build_facilitator_runner(
    slug: str,
    build_agent_fn,
    load_config_fn,
    *,
    story_url: str,
    artifact_url: str,
    db_url: str,
    context_token_limit: int | None = None,
) -> Runner:
    """Assemble the session-scoped runner: agent with read-only MCP
    toolsets (story + artifact), DatabaseSessionService on the configured
    PostgreSQL, auto-created sessions keyed by the request's session id.

    The lineage guard runs before telemetry's before-tool callback: a
    rejection short-circuits the tool call, so no start event may be
    emitted for a call that then never ends."""
    prompt: LoadedPrompt = load_prompt(slug)
    config: AgentConfig = load_config_fn()
    toolsets = [
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=story_url, timeout=10.0),
            tool_filter=STORY_TOOLS,
        ),
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=artifact_url, timeout=10.0
            ),
            tool_filter=ARTIFACT_READ_TOOLS,
        ),
    ]
    telemetry = TelemetryCallbacks(
        service=slug, context_token_limit=context_token_limit
    )
    agent: LlmAgent = build_agent_fn(
        prompt,
        config,
        tools=toolsets,
        before_tool_callback=[
            _guarded_tool_call,
            telemetry.before_tool,
        ],
        after_tool_callback=telemetry.after_tool,
        before_model_callback=telemetry.before_model,
        after_model_callback=telemetry.after_model,
    )
    return Runner(
        agent=agent,
        app_name=slug,
        session_service=DatabaseSessionService(db_url=db_url),
        auto_create_session=True,
    )


def create_facilitator_app(
    slug: str,
    build_agent_fn,
    load_config_fn,
    agent_version: str,
    *,
    runner: Runner | None = None,
    db_url: str = "",
    story_url: str = "",
    artifact_url: str = "",
    result_store: TurnResultStore | None = None,
) -> FastAPI:
    """Build the facilitator adapter app; prompt/config/toolsets load at
    startup (loud). `runner` injection keeps deterministic tests free of
    ADK/Vertex/Postgres; `result_store` defaults to an in-memory store (the
    binding layer supplies the Postgres-backed one)."""
    configure_logging(slug)
    app = FastAPI(
        title=f"{slug} local adapter",
        version=agent_version,
        lifespan=_result_store_lifespan(result_store),
    )
    if runner is None:
        runner = build_facilitator_runner(
            slug,
            build_agent_fn,
            load_config_fn,
            story_url=story_url,
            artifact_url=artifact_url,
            db_url=db_url,
        )
    prompt: LoadedPrompt = load_prompt(slug)
    results: TurnResultStore = result_store or InMemoryTurnResultStore()

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "agent_version": agent_version}

    @app.get("/turn-result/{session_id}/{invocation_id}", response_model=None)
    async def turn_result(session_id: str, invocation_id: str) -> JSONResponse:
        """Reconciliation lookup: the stored response for one completed
        invocation, or 404 when it never completed (observability.md)."""
        try:
            invocation = uuid.UUID(invocation_id)
        except ValueError:
            return error_response(
                400, "VALIDATION_ERROR", "invocation id is not a UUID", agent=slug
            )
        stored = await results.lookup(session_id, invocation)
        if stored is None:
            return error_response(
                404,
                "SESSION_NOT_FOUND",
                f"no completed turn for invocation {invocation_id} "
                f"in session {session_id}",
                agent=slug,
            )
        return JSONResponse(content=stored.model_dump(mode="json"))

    @app.post("/turn", response_model=None)
    async def turn(request: Request) -> JSONResponse:
        try:
            parsed = FacilitatorRequest.model_validate_json(await request.body())
        except ValidationError as exc:
            return error_response(
                400, "VALIDATION_ERROR", str(exc.errors()[:5]), agent=slug
            )
        token = _current_request.set(parsed)
        try:
            stored = await results.lookup(parsed.session_id, parsed.invocation_id)
            if stored is not None:
                # completed earlier (ambiguous-timeout replay): no model run
                return JSONResponse(content=stored.model_dump(mode="json"))
            # NOTE: two truly concurrent POSTs for the same invocation can
            # both miss the lookup and both run the model; `save` is
            # first-wins, so the second runner's response may differ from
            # the stored one (a later replay then returns the stored body).
            # At-most-once storage holds; at-most-once work holds for the
            # retry pattern orchestration uses (sequential attempts).
            output, corrections = await turn_with_corrections(
                make_send(runner, parsed), parsed
            )
            response = FacilitatorResponse(
                output=output,
                agent_version=agent_version,
                prompt_sha256=prompt.sha256,
                corrective_reprompts=corrections,
            )
            await results.save(parsed.session_id, parsed.invocation_id, response)
            return JSONResponse(content=response.model_dump(mode="json"))
        except DelegationValidationError as exc:
            return error_response(422, "DELEGATION_VALIDATION", str(exc), agent=slug)
        except Exception as exc:  # model/transport failure after ADK retries
            return error_response(
                503,
                "UPSTREAM_UNAVAILABLE",
                f"model call failed: {exc}",
                agent=slug,
                retry_after=5,
            )
        finally:
            _current_request.reset(token)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return error_response(
            400, "VALIDATION_ERROR", str(exc.errors()[:5]), agent=slug
        )

    return app
