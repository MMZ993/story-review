"""Domain exceptions for orchestration persistence primitives.

These are repository-level outcomes; routers translate them into the shared
structured error envelope with the right HTTP status (IDEMPOTENCY_KEY_REUSED
and SESSION_READ_ONLY 409, SESSION_LOCKED 409 with retry_after_seconds,
upstream conflicts 503) at the API layer (increments 1-4).
"""

from __future__ import annotations


class OrchestrationError(Exception):
    """Base class for orchestration domain errors."""


class IdempotencyKeyReused(OrchestrationError):
    """Same idempotency key resubmitted with a different request body."""


class SessionLocked(OrchestrationError):
    """The session turn lease is held by another request.

    The rejected caller never owned the lease; it should wait
    retry_after_seconds and retry with a NEW idempotency key.
    """

    def __init__(self, retry_after_seconds: int):
        super().__init__(f"session locked; retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


class ConstraintViolation(OrchestrationError):
    """A database-level invariant rejected the write (e.g. duplicate turn
    number or a second active run for a story)."""
