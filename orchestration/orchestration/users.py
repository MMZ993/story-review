"""X-User-Id request dependency (api-contract.md conventions).

Every /api/v1 request except story-browse and health carries the
(unauthenticated) user identifier: a UUID v4 the client generates once and
persists. It is an opaque grouping key — sessions and story runs are
scoped per user; it is never a proof of identity (no authentication, see
deployment.md). A missing, malformed, or non-v4 header is a structured
422 VALIDATION_ERROR.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Header, Request

from .api_errors import ApiError, make_error


def require_user_id(
    request: Request,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> uuid.UUID:
    """Parse and validate the X-User-Id header; 422 on any defect."""
    try:
        parsed = uuid.UUID(x_user_id or "")
        if parsed.version != 4:
            raise ValueError("not version 4")
        return parsed
    except ValueError:
        raise ApiError(
            422,
            make_error(
                "VALIDATION_ERROR",
                "X-User-Id must be a UUID v4",
                request.state.correlation_id,
                retryable=False,
            ),
        ) from None
