"""Contract tests for the artifact MCP server against the ASGI app.

Drives the app exactly as orchestration/facilitator will: the `mcp` client
SDK over Streamable HTTP (ASGI transport standing in for the network),
storage backed by the session's fake-gcs-server. Covers the tool matrix,
per-tool authorization (save is orchestration-only; facilitator
read-only), the error taxonomy over the wire, and idempotency semantics.

Each round trip builds a fresh app: the StreamableHTTP session manager
runs once per instance (same constraint the story-server tests hit).
"""

from __future__ import annotations

import asyncio
import uuid

import httpx2
import pytest
from asgi_lifespan import LifespanManager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from artifact_mcp.app import build_app
from artifact_mcp.auth import _principal
from artifact_mcp.server import CallerRoles

from tests.conftest import run_id, story_detail

ORCH = "orchestration@example.com"
FACI = "facilitator@example.com"


def _roles() -> CallerRoles:
    return CallerRoles(orchestration={ORCH}, facilitator={FACI})


@pytest.fixture()
def make_app(bucket_name: str, gcs_endpoint: str):
    """Local-profile app factory over the session's fake GCS bucket."""

    def factory(roles: CallerRoles | None = None):
        return build_app(
            auth_disabled=True,
            bucket=bucket_name,
            gcs_endpoint=gcs_endpoint,
            roles=roles,
            http_host="artifact.test",
        )

    return factory


@pytest.fixture()
def open_app(make_app) -> object:
    """Auth-disabled app with the allowlists bypassed (roles=None)."""
    return make_app(None)


def call_tool(make_app, roles, tool: str, arguments: dict, *, headers: dict | None = None):
    """One MCP round trip on a fresh app; returns the CallToolResult."""

    async def run() -> object:
        app = make_app(roles)
        async with LifespanManager(app):
            http = httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                base_url="http://artifact.test",
                headers=headers or {},
            )
            async with streamable_http_client(
                "http://artifact.test/mcp", http_client=http, terminate_on_close=False
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(tool, arguments)

    return asyncio.run(run())


def list_tools(open_app) -> list:
    async def run() -> list:
        async with LifespanManager(open_app):
            http = httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=open_app),
                base_url="http://artifact.test",
            )
            async with streamable_http_client(
                "http://artifact.test/mcp", http_client=http, terminate_on_close=False
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return (await session.list_tools()).tools

    return asyncio.run(run())


def _payload(result) -> dict:
    assert result.structured_content is not None, result.content
    return dict(result.structured_content)


def _save_args(run: str, key: uuid.UUID | None = None) -> dict:
    return {
        "type": "story",
        "story_run_id": run,
        "perspective": None,
        "content": story_detail().model_dump(mode="json"),
        "idempotency_key": str(key or uuid.uuid4()),
    }


def test_tool_schemas_are_flat_and_exact(open_app):
    tools = {t.name: t for t in list_tools(open_app)}
    assert set(tools) == {"save_artifact", "get_artifact", "list_artifacts"}
    assert tools["save_artifact"].input_schema["properties"].keys() == {
        "type",
        "story_run_id",
        "perspective",
        "content",
        "idempotency_key",
    }
    assert tools["get_artifact"].input_schema["properties"].keys() == {
        "artifact_id",
        "story_run_id",
    }
    assert tools["list_artifacts"].input_schema.get("required") == ["story_run_id"]


def test_save_get_round_trip(make_app):
    run = run_id()
    saved = call_tool(make_app, None, "save_artifact", _save_args(run))
    payload = _payload(saved)
    assert not saved.is_error
    assert payload["created"] is True
    assert payload["reference"]["version"] == 1

    got = call_tool(
        make_app,
        None,
        "get_artifact",
        {"artifact_id": payload["reference"]["artifact_id"], "story_run_id": run},
    )
    content = _payload(got)["content"]
    assert content == story_detail().model_dump(mode="json")


def test_save_retry_is_idempotent_over_the_wire(make_app):
    run = run_id()
    key = uuid.uuid4()
    first = _payload(call_tool(make_app, None, "save_artifact", _save_args(run, key)))
    retry = _payload(call_tool(make_app, None, "save_artifact", _save_args(run, key)))
    assert retry["created"] is False
    assert retry["reference"] == first["reference"]


def test_idempotency_key_reused_is_structured_error(make_app):
    run = run_id()
    key = uuid.uuid4()
    call_tool(make_app, None, "save_artifact", _save_args(run, key))
    args = _save_args(run, key)
    args["content"]["title"] = "A different story title"
    result = call_tool(make_app, None, "save_artifact", args)
    error = _payload(result)["error"]
    assert result.is_error
    assert error["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert error["retryable"] is False


def test_cross_run_get_is_artifact_not_found(make_app):
    run = run_id()
    saved = _payload(call_tool(make_app, None, "save_artifact", _save_args(run)))
    result = call_tool(
        make_app,
        None,
        "get_artifact",
        {
            "artifact_id": saved["reference"]["artifact_id"],
            "story_run_id": run_id(),
        },
    )
    assert result.is_error
    assert _payload(result)["error"]["code"] == "ARTIFACT_NOT_FOUND"


def test_unknown_field_is_validation_error(make_app):
    result = call_tool(
        make_app, None, "list_artifacts", {"story_run_id": run_id(), "unexpected": 1}
    )
    assert result.is_error
    assert _payload(result)["error"]["code"] == "VALIDATION_ERROR"


def test_facilitator_can_read_but_not_save(make_app):
    roles = _roles()
    run = run_id()
    # set the verified principal directly (the middleware's job in prod)
    token = _principal.set(FACI)
    try:
        listing = call_tool(make_app, roles, "list_artifacts", {"story_run_id": run})
        assert not listing.is_error
        assert _payload(listing)["total"] == 0

        denied = call_tool(make_app, roles, "save_artifact", _save_args(run))
        assert denied.is_error
        assert _payload(denied)["error"]["code"] == "FORBIDDEN"
    finally:
        _principal.reset(token)


def test_unknown_caller_is_forbidden_on_every_tool(make_app, monkeypatch):
    roles = _roles()
    token = _principal.set("stranger@example.com")
    try:
        result = call_tool(make_app, roles, "list_artifacts", {"story_run_id": run_id()})
        assert result.is_error
        assert _payload(result)["error"]["code"] == "FORBIDDEN"
    finally:
        _principal.reset(token)


def test_review_save_requires_matching_perspective(make_app):
    args = _save_args(run_id())
    args["type"] = "review-business"
    args["perspective"] = "engineering"
    result = call_tool(make_app, None, "save_artifact", args)
    assert result.is_error
    assert _payload(result)["error"]["code"] == "VALIDATION_ERROR"


def test_correlation_id_propagates_into_errors(make_app):
    correlation = str(uuid.uuid4())
    result = call_tool(
        make_app,
        None,
        "get_artifact",
        {"artifact_id": f"art-{uuid.uuid4()}", "story_run_id": run_id()},
        headers={"x-correlation-id": correlation},
    )
    assert _payload(result)["error"]["correlation_id"] == correlation


def test_list_orders_and_flags_latest(make_app):
    run = run_id()
    call_tool(make_app, None, "save_artifact", _save_args(run))
    call_tool(make_app, None, "save_artifact", _save_args(run))
    result = call_tool(make_app, None, "list_artifacts", {"story_run_id": run})
    items = _payload(result)["items"]
    assert [item["version"] for item in items] == [1, 2]
    assert [item["is_latest"] for item in items] == [False, True]


# -- ingress middleware (ported from the story-server contract tests) --------


def _fake_verifier(email: str):
    def verify(token: str, audience: str) -> dict:
        assert token == "good-token"
        return {"email": email}

    return verify


def _authed(make_app, verifier, audience="https://artifact.test"):
    """The production shape: middleware-wrapped app with auth enabled."""
    from artifact_mcp.app import IdTokenAuthMiddleware

    app = make_app(None)
    return IdTokenAuthMiddleware(app, verifier, audience)


def _ingress_post(app):
    import asyncio

    async def scenario():
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://artifact.test") as c:
            return await c.post(
                "http://artifact.test/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )

    return asyncio.run(scenario())


def _ingress_get(app, path="/healthz"):
    import asyncio

    async def scenario():
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://artifact.test") as c:
            return await c.get(f"http://artifact.test{path}")

    return asyncio.run(scenario())


def test_missing_token_is_rejected_at_ingress(make_app):
    assert _ingress_post(_authed(make_app, _fake_verifier(ORCH))).status_code == 401


def test_invalid_token_is_rejected_at_ingress(make_app):
    def bad(token: str, audience: str) -> dict:
        raise ValueError("bad token")

    assert _ingress_post(_authed(make_app, bad)).status_code == 401


def test_missing_audience_fails_closed(make_app):
    assert (
        _ingress_post(_authed(make_app, _fake_verifier(ORCH), audience="")).status_code
        == 503
    )


def test_healthz_is_public(make_app):
    assert _ingress_get(_authed(make_app, _fake_verifier(ORCH))).status_code == 200


def test_verified_allowlisted_caller_succeeds(make_app):
    from artifact_mcp.app import IdTokenAuthMiddleware

    def authed(roles):
        return IdTokenAuthMiddleware(
            make_app(roles), _fake_verifier(ORCH), "https://artifact.test"
        )

    headers = {"Authorization": "Bearer good-token"}
    result = call_tool(
        authed, _roles(), "list_artifacts", {"story_run_id": run_id()}, headers=headers
    )
    assert not result.is_error


def test_unexpected_internal_error_is_not_retryable(make_app):
    """Last-resort errors carry no retry hint (a retry is not safe)."""
    from artifact_mcp.errors import error_for

    payload = error_for(RuntimeError("boom"), uuid.uuid4())
    assert payload.error.code == "UPSTREAM_UNAVAILABLE"
    assert payload.error.retryable is False
    assert payload.error.retry_after_seconds is None
