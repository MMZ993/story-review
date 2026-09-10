"""FastAPI application factory (Phase 6).

Wires settings, MCP clients, correlation-ID middleware, structured error
envelope handlers, and the increment routers (stories, health). Endpoint
ownership per docs-local/plans/phase-6-orchestration.md increments 1-4.
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from review_schemas.api import HealthResponse

from . import stories
from .api_errors import ApiError, make_error
from .config import Settings
from .health import Downstream, dependencies_state
from .mcp_client import McpClient


def create_app(
    settings: Settings | None = None,
    *,
    story_client: McpClient | None = None,
    artifact_client: McpClient | None = None,
    report_client: McpClient | None = None,
) -> FastAPI:
    """Build the orchestration app; tests may inject settings and clients."""
    resolved = settings or Settings.from_env()
    app = FastAPI(title="story-review orchestration", version="0.1.0")
    app.state.settings = resolved
    app.state.story_client = story_client or McpClient(
        resolved.story_url, resolved
    )
    app.state.artifact_client = artifact_client or McpClient(
        resolved.artifact_url, resolved
    )
    app.state.report_client = report_client or McpClient(
        resolved.report_url, resolved
    )

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):
        """Echo or mint the X-Correlation-Id on every response (a malformed
        supplied value is replaced by a minted UUID, never surfaced as 500)."""
        supplied = request.headers.get("X-Correlation-Id", "")
        try:
            request.state.correlation_id = str(uuid.UUID(supplied))
        except ValueError:
            request.state.correlation_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = request.state.correlation_id
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error.model_dump(mode="json")},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        body = make_error(
            "VALIDATION_ERROR",
            "malformed request",
            getattr(request.state, "correlation_id", str(uuid.uuid4())),
            retryable=False,
        )
        return JSONResponse(
            status_code=422, content={"error": body.model_dump(mode="json")}
        )

    app.include_router(stories.router)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Liveness + downstream reachability flags (single probe each)."""
        return await dependencies_state(
            [
                Downstream("story", app.state.story_client),
                Downstream("artifact", app.state.artifact_client),
                Downstream("report", app.state.report_client),
            ]
        )

    return app
