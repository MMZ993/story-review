"""FastAPI application factory (Phase 6).

Wires settings, the asyncpg pool (lifecycle-owned unless injected), MCP
clients, agent adapter clients, correlation-ID middleware, structured
error envelope handlers, and the increment routers (stories, sessions,
health). Endpoint ownership per
docs-local/plans/phase-6-orchestration.md increments 1-4.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from review_schemas.api import HealthDependency, HealthResponse

from . import db, finalize_api, sessions_api, stories, turns_api
from .agent_clients import AgentSet, default_agent_set
from .api_errors import ApiError, make_error
from .config import Settings
from .health import Downstream, dependencies_state
from .mcp_client import McpClient
from .signed_urls import ReportSigner


def create_app(
    settings: Settings | None = None,
    *,
    story_client: McpClient | None = None,
    artifact_client: McpClient | None = None,
    report_client: McpClient | None = None,
    agents: AgentSet | None = None,
    signer: ReportSigner | None = None,
    pool: asyncpg.Pool | None = None,
) -> FastAPI:
    """Build the orchestration app; tests may inject settings, clients,
    agent fakes, and an existing pool (which suppresses the lifespan)."""
    resolved = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Own the record pool when none was injected."""
        app.state.pool = pool
        if pool is None:
            app.state.pool = await db.open_pool(resolved.db_dsn)
        try:
            yield
        finally:
            if pool is None:
                await app.state.pool.close()

    app = FastAPI(
        title="story-review orchestration", version="0.1.0", lifespan=lifespan
    )
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
    app.state.agents = agents or default_agent_set(resolved)
    app.state.signer = signer or ReportSigner.from_settings(resolved)
    app.state.signer.warm_up()
    app.state.pool = pool

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
    app.include_router(sessions_api.router)
    app.include_router(turns_api.router)
    app.include_router(finalize_api.router)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Liveness + database and downstream reachability flags."""
        database = await dependencies_state(
            [
                Downstream("story", app.state.story_client),
                Downstream("artifact", app.state.artifact_client),
                Downstream("report", app.state.report_client),
            ]
        )
        reachable = await _database_reachable(app)
        database.dependencies.append(
            HealthDependency(name="database", reachable=reachable)
        )
        if not reachable:
            database.status = "degraded"
        return database

    return app


async def _database_reachable(app: FastAPI) -> bool:
    """Single `select 1` probe; never raises (health stays 200)."""
    pool = getattr(app.state, "pool", None)
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("select 1")
        return True
    except Exception:
        return False
