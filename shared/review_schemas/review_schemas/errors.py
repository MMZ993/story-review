"""Error taxonomy shared by HTTP, MCP, and agent callers.

Implements the "Errors" section of docs/design/schemas.md: `ErrorBody` with the
stable `ErrorCode` taxonomy and the retry-hint invariant, plus the two wrappers
(`ErrorEnvelope` for API responses, `ToolError` for MCP failures).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from review_schemas.base import CorrelationId, ShortText, StrictModel, Text

ErrorCode = Literal[
    "UNAUTHENTICATED",
    "FORBIDDEN",
    "VALIDATION_ERROR",
    "STORY_NOT_FOUND",
    "SESSION_NOT_FOUND",
    "ARTIFACT_NOT_FOUND",
    "SESSION_LOCKED",
    "SESSION_READ_ONLY",
    "STORY_SESSION_ACTIVE",
    "NOT_FINALIZING",
    "REPORT_NOT_READY",
    "IDEMPOTENCY_KEY_REUSED",
    "DELEGATION_VALIDATION",
    "DEADLINE_EXCEEDED",
    "UPSTREAM_UNAVAILABLE",
    "RENDER_FAILED",
    "REPORT_RENDER_FAILED",
    "FINAL_REVIEW_INVALID",
]


class ErrorBody(StrictModel):
    """One machine-readable failure; retryable errors always carry one hint."""

    code: ErrorCode
    message: Text
    agent: ShortText | None = None
    correlation_id: CorrelationId
    retryable: bool
    retry_after_seconds: Annotated[int, Field(ge=1, le=3600)] | None = None

    @model_validator(mode="after")
    def retry_hint_matches_retryability(self):
        if self.retryable != (self.retry_after_seconds is not None):
            raise ValueError("retryable errors require one retry hint")
        return self


class ErrorEnvelope(StrictModel):
    """HTTP failure wrapper: `{"error": {...}}`."""

    error: ErrorBody


class ToolError(StrictModel):
    """MCP failure wrapper: the same `ErrorBody` inside tool results."""

    error: ErrorBody
