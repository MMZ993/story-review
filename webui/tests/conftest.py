"""Shared fixtures for the webui deterministic suite."""

import httpx
import pytest
from fastapi.testclient import TestClient

from webui.config import Settings
from webui.main import create_app


@pytest.fixture
def app():
    """App wired to a mock upstream that tests replace per call."""
    holder = {"handler": None}

    def handler(request: httpx.Request) -> httpx.Response:
        """Dispatch to the test-installed handler; default 404."""
        if holder["handler"] is None:
            return httpx.Response(404, json={"error": "no handler installed"})
        return holder["handler"](request)

    application = create_app(
        Settings(orchestration_base_url="http://orchestration"),
        transport=httpx.MockTransport(handler),
    )
    application.state.upstream = holder
    return application


@pytest.fixture
def client(app):
    """Synchronous test client over the app (lifespan-managed)."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def upstream(app):
    """Install a per-test upstream handler: ``upstream(fn)`` then request."""
    return app.state.upstream
