"""Deterministic session-marker store for the connectivity spike.

Purpose: back the `persist_session` / `restore_session` MCP tools with
validated, structured requests and defined outcomes, independent of the
transport or database. `InMemorySessionMarkerStore` is the reference
implementation used by tests and local runs; a Cloud SQL-backed
implementation (same interface) is added in a later spike increment.

Inputs/outputs: Pydantic request/result models; no I/O here. Errors:
`AlreadyStoredError` when a different marker already exists for a session.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field, model_validator


class PersistSessionRequest(BaseModel):
    """Request to store one marker under a session ID.

    All fields must be non-empty.
    """

    session_id: str = Field(min_length=1)
    marker: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class RestoreSessionRequest(BaseModel):
    """Request to retrieve the stored marker for a session ID."""

    session_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class PersistSessionResult(BaseModel):
    """Confirmation that a marker is stored for the session."""

    stored: bool
    session_id: str
    correlation_id: str


class RestoreSessionResult(BaseModel):
    """Stored marker for a session, or a defined not-found outcome.

    `marker` is None exactly when `found` is False.
    """

    found: bool
    session_id: str
    marker: str | None = None
    correlation_id: str | None = None

    @model_validator(mode="after")
    def _marker_iff_found(self) -> "RestoreSessionResult":
        if self.found == (self.marker is None):
            raise ValueError("marker must be set iff found is true")
        return self


class AlreadyStoredError(Exception):
    """A different marker is already stored for the session."""


class SessionMarkerStore(Protocol):
    """Storage interface shared by the in-memory and Cloud SQL backends."""

    async def persist(self, request: PersistSessionRequest) -> PersistSessionResult:
        ...  # pragma: no cover - protocol

    async def restore(self, request: RestoreSessionRequest) -> RestoreSessionResult:
        ...  # pragma: no cover - protocol


class InMemorySessionMarkerStore:
    """Reference store: one marker per session, persist-once semantics.

    Re-persisting the identical marker is idempotent; persisting a different
    marker for the same session raises `AlreadyStoredError`.
    """

    def __init__(self) -> None:
        self._rows: dict[str, tuple[str, str]] = {}

    async def persist(self, request: PersistSessionRequest) -> PersistSessionResult:
        existing = self._rows.get(request.session_id)
        if existing is not None and existing[0] != request.marker:
            raise AlreadyStoredError(request.session_id)
        self._rows[request.session_id] = (request.marker, request.correlation_id)
        return PersistSessionResult(
            stored=True,
            session_id=request.session_id,
            correlation_id=request.correlation_id,
        )

    async def restore(self, request: RestoreSessionRequest) -> RestoreSessionResult:
        existing = self._rows.get(request.session_id)
        if existing is None:
            return RestoreSessionResult(
                found=False, session_id=request.session_id, correlation_id=request.correlation_id
            )
        marker, correlation_id = existing
        return RestoreSessionResult(
            found=True,
            session_id=request.session_id,
            marker=marker,
            correlation_id=correlation_id,
        )
