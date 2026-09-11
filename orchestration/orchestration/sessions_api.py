"""Sessions endpoints (api-contract.md "Sessions" section, increment 2):
POST /api/v1/sessions (flow 1), GET /api/v1/sessions (keyset list),
GET /api/v1/sessions/{session_id} (SessionDetail with server-side
artifact fetching via the artifact MCP).
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
import time
import uuid

from fastapi import APIRouter, Header, Request
from review_schemas.api import (
    CreateSessionRequest,
    CreateSessionResponse,
    ListSessionsQuery,
    ListSessionsResponse,
    SessionDetail,
    SessionSummary,
    TurnView,
)
from review_schemas.mcp import ListArtifactsInput, ListArtifactsOutput
from review_schemas.synthesis import ArtifactReference

from . import finalization, flows, records_store
from .api_errors import ApiError, make_error
from .errors import ConstraintViolation, IdempotencyKeyReused
from .mcp_client import (
    DeadlineExceededError,
    McpCallFailure,
    McpTransportError,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _correlation(request: Request) -> str:
    return request.state.correlation_id


def _deadline(request: Request) -> float:
    return time.monotonic() + request.app.state.settings.request_deadline_seconds


def _not_found(correlation_id: str) -> ApiError:
    return ApiError(
        404,
        make_error(
            "SESSION_NOT_FOUND", "no such session", correlation_id, retryable=False
        ),
    )


def encode_cursor(record) -> str:
    """Opaque keyset cursor = (updated_at, session_id) of the last row."""
    raw = f"{record.updated_at.isoformat()}|{record.session_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    """Inverse of encode_cursor; raises ValueError on garbage cursors."""
    padded = cursor + "=" * (-len(cursor) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode()).decode()
    updated_at, _, session_id = decoded.partition("|")
    if not updated_at or not session_id:
        raise ValueError("malformed cursor")
    moment = datetime.fromisoformat(updated_at)
    if moment.tzinfo is None:  # asyncpg rejects naive datetimes (envelope 422)
        raise ValueError("cursor timestamp must be timezone-aware")
    return moment, session_id


@router.post("", status_code=201, response_model=CreateSessionResponse)
async def create_session(
    payload: CreateSessionRequest,
    request: Request,
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
):
    """Select a story and run the initial flow (data-flow.md §1)."""
    correlation_id = _correlation(request)
    if idempotency_key.version != 4:  # schemas.md: idempotency keys are UUID v4
        raise ApiError(
            422,
            make_error(
                "VALIDATION_ERROR",
                "Idempotency-Key must be a UUID v4",
                correlation_id,
                retryable=False,
            ),
        )
    try:
        return await flows.run_create_session(
            request.app.state.pool,
            request.app.state.settings,
            story_client=request.app.state.story_client,
            artifact_client=request.app.state.artifact_client,
            agents=request.app.state.agents,
            payload=payload.model_dump(mode="json"),
            key=idempotency_key,
            correlation_id=correlation_id,
        )
    except IdempotencyKeyReused as exc:
        raise flows.map_idempotency_reused(exc, correlation_id) from exc
    except ConstraintViolation as exc:
        raise flows.map_constraint_violation(exc, correlation_id) from exc


@router.get("", response_model=ListSessionsResponse)
async def list_sessions(
    limit: int = 50,
    cursor: str | None = None,
    *,
    request: Request,
):
    """List restorable sessions, newest update first."""
    try:
        query = ListSessionsQuery(limit=limit, cursor=cursor)
    except ValueError as exc:
        raise ApiError(
            422,
            make_error(
                "VALIDATION_ERROR",
                "invalid limit or cursor",
                _correlation(request),
                retryable=False,
            ),
        ) from exc
    correlation_id = _correlation(request)
    before = None
    if query.cursor is not None:
        try:
            before = decode_cursor(query.cursor)
        except ValueError as exc:
            raise ApiError(
                422,
                make_error(
                    "VALIDATION_ERROR",
                    "malformed cursor",
                    correlation_id,
                    retryable=False,
                ),
            ) from exc
    page, more = await records_store.list_sessions(
        request.app.state.pool, limit=query.limit, before=before
    )
    sessions = [
        SessionSummary(
            session_id=record.session_id,
            story_run_id=record.story_run_id,
            story_id=record.story_id,
            state=record.state,
            requested_formats=record.requested_formats,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        for record in page
    ]
    return ListSessionsResponse(
        sessions=sessions,
        next_cursor=encode_cursor(page[-1]) if more and page else None,
    )


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, *, request: Request):
    """History replay incl. artifact references (fetched server-side)."""
    correlation_id = _correlation(request)
    record = await records_store.get_session(
        request.app.state.pool, session_id
    )
    if record is None:
        raise _not_found(correlation_id)
    turns = await records_store.list_turns(request.app.state.pool, session_id)
    references = await _run_artifacts(request, record.story_run_id)
    reports = (
        finalization.report_response(
            record.session_id, record.report_references, request.app.state.signer
        ).report
        if record.state == "completed"
        else []
    )
    return SessionDetail(
        session_id=record.session_id,
        story_run_id=record.story_run_id,
        story_id=record.story_id,
        state=record.state,
        requested_formats=record.requested_formats,
        created_at=record.created_at,
        updated_at=record.updated_at,
        facilitator_turn_count=record.facilitator_turn_count,
        turns=[
            TurnView(
                turn_number=turn.turn_number,
                po_message=turn.po_message,
                po_accepted=turn.po_accepted,
                facilitator_reply=turn.facilitator_reply,
                delegation=turn.delegation,
                resolutions=turn.resolutions,
                outcome=turn.outcome,
                produced_artifacts=turn.produced_artifacts,
            )
            for turn in turns
        ],
        artifact_references=references,
        reports=reports,
    )


async def _run_artifacts(request: Request, story_run_id: str) -> list[ArtifactReference]:
    """Server-side artifact fetch for SessionDetail (artifact MCP)."""
    payload = ListArtifactsInput(story_run_id=story_run_id, limit=500).model_dump(
        mode="json"
    )
    try:
        raw = await request.app.state.artifact_client.call(
            "list_artifacts", payload, deadline=_deadline(request)
        )
        output = ListArtifactsOutput.model_validate_json(json.dumps(raw))
    except McpCallFailure as failure:
        if failure.error.code.endswith("_NOT_FOUND"):
            raise ApiError(
                404,
                make_error(
                    failure.error.code,
                    failure.error.message,
                    _correlation(request),
                    retryable=False,
                ),
            ) from failure
        raise ApiError(
            503,
            make_error(
                failure.error.code,
                failure.error.message,
                _correlation(request),
                retryable=failure.error.retryable,
            ),
        ) from failure
    except (McpTransportError, DeadlineExceededError) as failure:
        raise ApiError(
            503,
            make_error(
                "UPSTREAM_UNAVAILABLE",
                "artifact MCP unavailable",
                _correlation(request),
                retryable=True,
            ),
        ) from failure
    return output.items
