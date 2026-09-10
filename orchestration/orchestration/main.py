"""FastAPI application factory (Phase 6 skeleton).

Increment 0 ships the scaffolding only: a health-check placeholder so the
service is deployable and testable as a package. The nine /api/v1 endpoints
land in increments 1-4 per docs-local/plans/phase-6-orchestration.md.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Build the orchestration FastAPI application."""
    app = FastAPI(title="story-review orchestration", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness scaffolding; downstream reachability flags in increment 1."""
        return {"status": "ok"}

    return app
