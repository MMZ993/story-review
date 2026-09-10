"""API-layer error mapping to the shared structured error envelope.

Routers raise ApiError; the FastAPI exception handlers in main.py render
ErrorEnvelope JSON with the right HTTP status. Correlation IDs come from the
middleware; retry hints are mandatory on retryable errors (ErrorBody).
"""

from __future__ import annotations

import uuid

from review_schemas.errors import ErrorBody

#: Hint served with retryable 503s (short client backoff).
RETRY_AFTER_SECONDS = 5


class ApiError(Exception):
    """One structured API failure to render as an ErrorEnvelope."""

    def __init__(self, status_code: int, error: ErrorBody):
        super().__init__(error.code)
        self.status_code = status_code
        self.error = error


def make_error(
    code: str,
    message: str,
    correlation_id: str,
    *,
    retryable: bool,
    agent: str | None = None,
    retry_after_seconds: int | None = None,
) -> ErrorBody:
    """Build an ErrorBody, applying the retry hint when retryable."""
    return ErrorBody(
        code=code,
        message=message,
        agent=agent,
        correlation_id=uuid.UUID(correlation_id),
        retryable=retryable,
        retry_after_seconds=RETRY_AFTER_SECONDS if retryable else retry_after_seconds,
    )


def upstream_failure(
    code: str, message: str, correlation_id: str
) -> ApiError:
    """Retryable 503 (retry-exhausted upstream or deadline exhaustion)."""
    return ApiError(
        503,
        make_error(code, message, correlation_id, retryable=True),
    )


def tool_failure(error: ErrorBody, correlation_id: str) -> ApiError:
    """Map a terminal MCP tool error: 404 for missing stories, else 503."""
    if error.code == "STORY_NOT_FOUND":
        return ApiError(
            404,
            make_error(
                "STORY_NOT_FOUND",
                error.message,
                correlation_id,
                retryable=False,
            ),
        )
    return ApiError(
        503,
        make_error(
            error.code,
            error.message,
            correlation_id,
            retryable=error.retryable,
        ),
    )
