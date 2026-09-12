"""Abandon endpoint (D22, api-contract.md "explicit park-now"):

`POST /sessions/{session_id}/abandon` — a client-side escape for a session
stuck without an exit (permanently broken upstream, missing lineage
artifacts): it parks an `active` or `finalizing` session immediately — no
facilitator/model call, no report. One atomic transition (session + story
run + idempotency completion) parks both, releasing the story for a new
session; the dialogue history stays readable. Terminal states are read-only
(409); an in-progress turn/finalization claim under the session lease is
409 SESSION_LOCKED retryable (wait for lease expiry, then abandon).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Request
from review_schemas.api import AbandonSessionResponse

from . import flows, idempotency, lease, records_store, turns_flow
from .api_errors import ApiError, make_error
from .errors import IdempotencyKeyReused, SessionLocked
from .users import require_user_id

router = APIRouter(prefix="/api/v1/sessions/{session_id}", tags=["abandon"])

ROUTE = "POST /api/v1/sessions/{}/abandon"


def _correlation(request: Request) -> str:
    return request.state.correlation_id


def _not_found(correlation_id: str) -> ApiError:
    return ApiError(
        404,
        make_error(
            "SESSION_NOT_FOUND", "no such session", correlation_id, retryable=False
        ),
    )


def _read_only(correlation_id: str) -> ApiError:
    return ApiError(
        409,
        make_error(
            "SESSION_READ_ONLY",
            "the session is already parked or completed; it is read-only",
            correlation_id,
            retryable=False,
        ),
    )


@router.post("/abandon", response_model=AbandonSessionResponse)
async def abandon_session(
    session_id: str,
    request: Request,
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
    user_id: uuid.UUID = Depends(require_user_id),
):
    """Explicit park-now of an active/finalizing session (state table in
    api-contract.md)."""
    correlation_id = _correlation(request)
    if idempotency_key.version != 4:
        raise ApiError(
            422,
            make_error(
                "VALIDATION_ERROR",
                "Idempotency-Key must be a UUID v4",
                correlation_id,
                retryable=False,
            ),
        )
    pool = request.app.state.pool
    if await records_store.get_session(pool, session_id, user_id=user_id) is None:
        raise _not_found(correlation_id)
    try:
        token = await lease.acquire(pool, session_id)
    except SessionLocked as exc:
        raise turns_flow.map_session_locked(exc, correlation_id) from exc
    try:
        return await _park_now(
            pool, session_id, idempotency_key, correlation_id, user_id
        )
    except IdempotencyKeyReused as exc:
        raise flows.map_idempotency_reused(exc, correlation_id) from exc
    finally:
        # a stuck finalization may have left the advisory stage marker set
        await records_store.set_processing_stage(pool, session_id, None)
        await lease.release(pool, session_id, token)


async def _park_now(
    pool,
    session_id: str,
    key: uuid.UUID,
    correlation_id: str,
    user_id: uuid.UUID,
) -> AbandonSessionResponse:
    """Under the lease: claim the idempotency slot, re-read the state
    (the previous lease holder may have transitioned it), park atomically."""
    claim = await idempotency.claim(
        pool, ROUTE, session_id, key, flows.fingerprint({})
    )
    if claim.outcome is idempotency.ClaimOutcome.REPLAY:
        assert claim.canonical_response is not None
        return AbandonSessionResponse.model_validate(claim.canonical_response)

    session = await records_store.get_session(pool, session_id, user_id=user_id)
    assert session is not None  # re-read under the lease of a known session
    if session.state not in ("active", "finalizing"):
        # a new key on a read-only session: release the fresh claim row so
        # a later retry of this key starts clean
        await idempotency.release(pool, ROUTE, session_id, key)
        raise _read_only(correlation_id)

    canonical = {"session_id": session.session_id, "state": "parked"}
    async with pool.acquire() as conn:
        async with conn.transaction():
            await records_store.update_session(
                pool, session.session_id, state="parked", conn=conn
            )
            await idempotency.complete(
                pool, ROUTE, session.session_id, key, canonical, conn=conn
            )
    return AbandonSessionResponse.model_validate(canonical)
