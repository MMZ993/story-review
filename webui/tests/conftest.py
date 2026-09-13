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


@pytest.fixture
def upstream_auth(monkeypatch):
    """App with proxy auth enabled and the token minter replaced by a
    deterministic fake (Phase 8 increment 5). Exposes ``client``, the
    upstream ``handler`` holder, and ``fail_mint`` to simulate metadata
    failures."""
    holder = {"handler": None, "fail_mint": False}

    def fake_minter(audience):
        """Stands in for the metadata-server mint; audience-checked."""
        assert audience == "https://orchestration"
        if holder["fail_mint"]:
            raise OSError("metadata identity endpoint unreachable")
        return {"Authorization": "Bearer minted-token-for-test"}

    from webui import id_tokens

    monkeypatch.setattr(id_tokens, "metadata_id_token", fake_minter)

    def handler(request: httpx.Request) -> httpx.Response:
        if holder["handler"] is None:
            return httpx.Response(404, json={"error": "no handler installed"})
        return holder["handler"](request)

    from webui.config import Settings
    from webui.main import create_app

    application = create_app(
        Settings(
            orchestration_base_url="https://orchestration",
            orchestration_id_token_auth=True,
        ),
        transport=httpx.MockTransport(handler),
    )
    with TestClient(application) as test_client:
        holder["client"] = test_client
        yield holder
