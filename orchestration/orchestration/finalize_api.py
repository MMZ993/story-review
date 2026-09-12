"""Finalization endpoints (api-contract.md flow 3/4, increment 4):

- `POST /sessions/{id}/finalize` — the four-state finalization retry
  (`finalizing` reacquire+render+complete, `completed` read-only replay,
  `active` 409 `NOT_FINALIZING`, `parked` 409 `SESSION_READ_ONLY`);
- `GET /sessions/{id}/report` — fresh signed URLs for a completed
  session's persisted reports (`REPORT_NOT_READY` 409 otherwise; never
  changes session state).
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, Header, Request
from review_schemas.api import ReportResponse

from . import finalization, flows, idempotency, lease, lineage, records_store, turns_flow
from .api_errors import ApiError, make_error
from .errors import IdempotencyKeyReused, SessionLocked
from .users import require_user_id

router = APIRouter(prefix="/api/v1/sessions/{session_id}", tags=["finalize"])


def _correlation(request: Request) -> str:
    return request.state.correlation_id


def _not_found(correlation_id: str) -> ApiError:
    return ApiError(
        404,
        make_error(
            "SESSION_NOT_FOUND", "no such session", correlation_id, retryable=False
        ),
    )


def _not_finalizing(correlation_id: str) -> ApiError:
    return ApiError(
        409,
        make_error(
            "NOT_FINALIZING",
            "the session is active; submit a turn instead",
            correlation_id,
            retryable=False,
        ),
    )


def _read_only(correlation_id: str) -> ApiError:
    return ApiError(
        409,
        make_error(
            "SESSION_READ_ONLY",
            "the session is parked; start a new session on the same story "
            "instead",
            correlation_id,
            retryable=False,
        ),
    )


@router.post("/finalize", response_model=ReportResponse)
async def post_finalize(
    session_id: str,
    request: Request,
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
    user_id: uuid.UUID = Depends(require_user_id),
):
    """Finalization retry / completion recovery (data-flow.md §3)."""
    correlation_id = _correlation(request)
    try:
        return await _finalize(request, session_id, idempotency_key, correlation_id, user_id)
    except SessionLocked as exc:
        raise turns_flow.map_session_locked(exc, correlation_id) from exc
    except IdempotencyKeyReused as exc:
        raise finalization.map_idempotency_reused(exc, correlation_id) from exc


async def _finalize(
    request: Request,
    session_id: str,
    idempotency_key: uuid.UUID,
    correlation_id: str,
    user_id: uuid.UUID,
) -> ReportResponse:
    """Dispatch on session state (api-contract four-state table)."""
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
    session = await records_store.get_session(pool, session_id, user_id=user_id)
    if session is None:
        raise _not_found(correlation_id)
    signer = request.app.state.signer
    if session.state == "completed":
        # read-only: persisted references + fresh URLs, no writes
        return finalization.report_response(
            session.session_id, session.report_references, signer
        )
    if session.state == "active":
        raise _not_finalizing(correlation_id)
    if session.state == "parked":
        raise _read_only(correlation_id)
    assert session.state == "finalizing"
    return await _resume_finalizing(
        request,
        session=session,
        key=idempotency_key,
        correlation_id=correlation_id,
        user_id=user_id,
    )


async def _resume_finalizing(
    request: Request,
    *,
    session,
    key: uuid.UUID,
    correlation_id: str,
    user_id: uuid.UUID,
) -> ReportResponse:
    """The `finalizing` path: reacquire the turn lease, resume flow 3
    (idempotent downstream work), complete atomically."""
    pool = request.app.state.pool
    token = await lease.acquire(pool, session.session_id)
    try:
        # re-read under the lease: the previous holder may have completed
        # between the outer state read and this acquisition (the completed
        # state is read-only — no writes, just fresh URLs)
        fresh = await records_store.get_session(
            pool, session.session_id, user_id=user_id
        )
        assert fresh is not None
        if fresh.state == "completed":
            return finalization.report_response(
                fresh.session_id, fresh.report_references, request.app.state.signer
            )
        if fresh.state == "active":
            # the previous holder rolled back before releasing the lease
            raise _not_finalizing(correlation_id)
        if fresh.state != "finalizing":
            raise _read_only(correlation_id)
        claim = await idempotency.claim(
            pool,
            finalization.ROUTE,
            session.session_id,
            key,
            flows.fingerprint({}),
        )
        if claim.outcome is idempotency.ClaimOutcome.REPLAY:
            assert claim.canonical_response is not None
            return finalization.replay_report_response(
                claim.canonical_response, request.app.state.signer
            )
        deadline = time.monotonic() + request.app.state.settings.request_deadline_seconds
        turns = await records_store.list_turns(pool, fresh.session_id)
        assert turns, "finalizing session without a durable turn record"
        references = await lineage.list_run_artifacts(
            request.app.state.artifact_client,
            fresh.story_run_id,
            deadline,
            correlation_id,
        )
        synthesis_reference = lineage.latest(
            references, "synthesis", None, correlation_id
        )
        await records_store.set_processing_stage(
            pool, fresh.session_id, "finalizing"
        )
        result = await finalization.run_flow3(
            pool,
            request.app.state.settings,
            artifact_client=request.app.state.artifact_client,
            report_client=request.app.state.report_client,
            session=fresh,
            turns=turns,
            key=key,
            correlation_id=correlation_id,
            synthesis_reference=synthesis_reference,
            deadline=deadline,
        )
        canonical = finalization.canonical_report(
            fresh.session_id, result.report_references
        )
        await finalization.complete_session(
            pool,
            route=finalization.ROUTE,
            session_id=fresh.session_id,
            key=key,
            canonical=canonical.model_dump(mode="json"),
            result=result,
        )
        return finalization.report_response(
            fresh.session_id, result.report_references, request.app.state.signer
        )
    finally:
        await records_store.set_processing_stage(pool, session.session_id, None)
        await lease.release(pool, session.session_id, token)


@router.get("/report", response_model=ReportResponse)
async def get_report(
    session_id: str,
    *,
    request: Request,
    user_id: uuid.UUID = Depends(require_user_id),
):
    """Regenerate expiring signed URLs for a completed session's reports."""
    correlation_id = _correlation(request)
    record = await records_store.get_session(
        request.app.state.pool, session_id, user_id=user_id
    )
    if record is None:
        raise _not_found(correlation_id)
    if record.state != "completed":
        raise ApiError(
            409,
            make_error(
                "REPORT_NOT_READY",
                "reports exist only for completed sessions",
                correlation_id,
                retryable=False,
            ),
        )
    return finalization.report_response(
        record.session_id, record.report_references, request.app.state.signer
    )
