"""Turns endpoint (api-contract.md "POST /sessions/{id}/turns",
increment 3): lease + idempotency + flow 2 execution, with the structured
error mappings for contention, read-only sessions, and idempotency reuse.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, Request
from review_schemas.api import TurnRequest, TurnResponse

from . import flows, turns_flow
from .api_errors import ApiError, make_error
from .errors import IdempotencyKeyReused, SessionLocked
from .finalization import FinalizationFailed

router = APIRouter(prefix="/api/v1/sessions/{session_id}", tags=["turns"])


def _correlation(request: Request) -> str:
    return request.state.correlation_id


@router.post("/turns", response_model=TurnResponse)
async def post_turn(
    session_id: str,
    payload: TurnRequest,
    request: Request,
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
):
    """One PO action = one dialogue turn (data-flow.md §2)."""
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
        return await turns_flow.run_turn(
            request.app.state.pool,
            request.app.state.settings,
            story_client=request.app.state.story_client,
            artifact_client=request.app.state.artifact_client,
            report_client=request.app.state.report_client,
            agents=request.app.state.agents,
            signer=request.app.state.signer,
            session_id=session_id,
            payload=payload.model_dump(mode="json"),
            key=idempotency_key,
            correlation_id=correlation_id,
        )
    except FinalizationFailed as exc:
        raise exc.api_error from exc
    except SessionLocked as exc:
        raise turns_flow.map_session_locked(exc, correlation_id) from exc
    except IdempotencyKeyReused as exc:
        raise flows.map_idempotency_reused(exc, correlation_id) from exc
