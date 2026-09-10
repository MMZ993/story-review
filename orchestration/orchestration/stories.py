"""Stories browse endpoints (api-contract.md "Stories" section).

GET /api/v1/stories proxies story MCP `list_stories` (no MCP status filter —
the API `filter` is a case-insensitive title substring applied here);
GET /api/v1/stories/{story_id} proxies `get_story`. Unknown story → 404
envelope; any other downstream failure → retryable 503.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Request
from pydantic import ValidationError
from review_schemas.api import ListStoriesResponse
from review_schemas.mcp import ListStoriesOutput
from review_schemas.review import StoryDetail, StorySummary

from .api_errors import ApiError, tool_failure, upstream_failure
from .mcp_client import (
    DeadlineExceededError,
    McpCallFailure,
    McpTransportError,
)

router = APIRouter(prefix="/api/v1/stories", tags=["stories"])


def title_filter(
    stories: list[StorySummary], needle: str | None
) -> list[StorySummary]:
    """Case-insensitive title substring filter (api-contract.md)."""
    if needle is None:
        return stories
    lowered = needle.lower()
    return [s for s in stories if lowered in s.title.lower()]


def _correlation(request: Request) -> str:
    """Middleware-validated correlation ID (echoed or minted)."""
    return request.state.correlation_id


def _deadline(request: Request) -> float:
    return time.monotonic() + request.app.state.settings.request_deadline_seconds


@router.get("", response_model=ListStoriesResponse)
async def list_stories(filter: str | None = None, *, request: Request):  # noqa: A002
    """Browse the mock backlog (dataset-bounded, no pagination)."""
    client = request.app.state.story_client
    try:
        payload = await client.call("list_stories", {}, deadline=_deadline(request))
        output = ListStoriesOutput.model_validate(payload)
    except McpCallFailure as failure:
        raise tool_failure(failure.error, _correlation(request)) from failure
    except ValidationError as failure:
        raise upstream_failure(
            "UPSTREAM_UNAVAILABLE",
            "story MCP returned an invalid list_stories payload",
            _correlation(request),
        ) from failure
    except (McpTransportError, DeadlineExceededError) as failure:
        raise upstream_failure(
            "UPSTREAM_UNAVAILABLE", "story MCP unavailable", _correlation(request)
        ) from failure
    return ListStoriesResponse(stories=title_filter(output.stories, filter))


@router.get("/{story_id}", response_model=StoryDetail)
async def get_story(story_id: str, *, request: Request):
    """Story detail incl. epic/roadmap context, comments, context stories."""
    client = request.app.state.story_client
    try:
        payload = await client.call(
            "get_story", {"story_id": story_id}, deadline=_deadline(request)
        )
        return StoryDetail.model_validate(payload)
    except McpCallFailure as failure:
        raise tool_failure(failure.error, _correlation(request)) from failure
    except ValidationError as failure:
        raise upstream_failure(
            "UPSTREAM_UNAVAILABLE",
            "story MCP returned an invalid get_story payload",
            _correlation(request),
        ) from failure
    except (McpTransportError, DeadlineExceededError) as failure:
        raise upstream_failure(
            "UPSTREAM_UNAVAILABLE", "story MCP unavailable", _correlation(request)
        ) from failure
