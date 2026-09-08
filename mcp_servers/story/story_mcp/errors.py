"""Tool failure payloads: every failure is a `ToolError(ErrorBody)`.

Maps the story server's internal exceptions to the stable codes from
mcp-servers.md / observability.md and pins the retry-hint invariant
(retryable errors always carry exactly one hint).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from review_schemas.errors import ErrorBody, ToolError

from story_mcp.azure_source import SourceUnavailable
from story_mcp.backlog import InvalidSourceOverride, StoryNotFound


class SourceNotConfigured(Exception):
    """A source was selected that this deployment does not serve."""


def correlation_id_from_header(value: str | None) -> UUID:
    """The caller's UUID-v4 correlation id, or a fresh one when absent/invalid.

    Per schemas.md, `X-Correlation-Id` is UUID v4 *when supplied* — a
    malformed header is replaced, not rejected (the caller's payload is
    still processable).
    """
    if value:
        try:
            candidate = UUID(value)
            if candidate.version == 4:
                return candidate
        except ValueError:
            pass
    return uuid4()


def _error(code: str, message: str, correlation_id: UUID, *, retryable: bool = False) -> ToolError:
    return ToolError(
        error=ErrorBody(
            code=code,
            message=message,
            correlation_id=correlation_id,
            retryable=retryable,
            retry_after_seconds=30 if retryable else None,
        )
    )


def validation_error(message: str, correlation_id: UUID) -> ToolError:
    return _error("VALIDATION_ERROR", message, correlation_id)


def story_not_found(exc: StoryNotFound, correlation_id: UUID) -> ToolError:
    return _error("STORY_NOT_FOUND", str(exc), correlation_id)


def upstream_unavailable(message: str, correlation_id: UUID, *, retryable: bool = False) -> ToolError:
    return _error("UPSTREAM_UNAVAILABLE", message, correlation_id, retryable=retryable)


def unauthenticated(correlation_id: UUID) -> ToolError:
    return _error("UNAUTHENTICATED", "no verified caller principal", correlation_id)


def forbidden(caller: str, correlation_id: UUID) -> ToolError:
    return _error("FORBIDDEN", f"caller {caller!r} is not authorized for this tool", correlation_id)


def internal_error(correlation_id: UUID) -> ToolError:
    """Last-resort wrapper: unexpected exceptions never leak details."""
    return _error("UPSTREAM_UNAVAILABLE", "unexpected internal error", correlation_id)


def error_for(exc: Exception, correlation_id: UUID) -> ToolError:
    """Map one internal exception to its ToolError payload."""
    if isinstance(exc, StoryNotFound):
        return story_not_found(exc, correlation_id)
    if isinstance(exc, (InvalidSourceOverride, ValueError)):
        return validation_error(str(exc), correlation_id)
    if isinstance(exc, SourceNotConfigured):
        return upstream_unavailable(str(exc), correlation_id)
    if isinstance(exc, SourceUnavailable):
        return upstream_unavailable(str(exc), correlation_id, retryable=True)
    return internal_error(correlation_id)
