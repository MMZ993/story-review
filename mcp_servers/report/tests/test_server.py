"""Contract tests for the report MCP server against the ASGI app.

Drives the app exactly as orchestration will: the `mcp` client SDK over
Streamable HTTP (ASGI transport standing in for the network), storage
backed by the session's fake-gcs-server. Covers the single-tool matrix,
orchestration-only authorization, the error taxonomy over the wire,
idempotency, and the ported ingress checks.

Each round trip builds a fresh app: the StreamableHTTP session manager
runs once per instance (same constraint the story/artifact tests hit).
"""

from __future__ import annotations

import asyncio
import uuid

import httpx2
import pytest
from asgi_lifespan import LifespanManager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_ingress.auth import IdTokenAuthMiddleware, _principal

from report_mcp.app import build_app

from tests.conftest import bucket_name, gcs_endpoint, run_id, seed_finalized

ORCH = "orchestration@example.com"
FACI = "facilitator@example.com"


@pytest.fixture()
def make_app(bucket_name: str, gcs_endpoint: str):
    """Local-profile app factory over the session's fake GCS bucket."""

    def factory(orchestration: set[str] | None = None):
        return build_app(
            auth_disabled=True,
            bucket=bucket_name,
            gcs_endpoint=gcs_endpoint,
            orchestration_callers=orchestration,
            http_host="report.test",
        )

    return factory


@pytest.fixture()
def open_app(make_app) -> object:
    """Auth-disabled app with the allowlist bypassed (callers=None)."""
    return make_app(None)


def call_tool(make_app, callers, tool: str, arguments: dict, *, headers: dict | None = None):
    """One MCP round trip on a fresh app; returns the CallToolResult."""

    async def run() -> object:
        app = make_app(callers)
        async with LifespanManager(app):
            http = httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                base_url="http://report.test",
                headers=headers or {},
            )
            async with streamable_http_client(
                "http://report.test/mcp", http_client=http, terminate_on_close=False
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
                base_url="http://report.test",
            )
            async with streamable_http_client(
                "http://report.test/mcp", http_client=http, terminate_on_close=False
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return (await session.list_tools()).tools

    return asyncio.run(run())


def _payload(result) -> dict:
    assert result.structured_content is not None, result.content
    return dict(result.structured_content)


def _render_args(run: str, reference, fmt: str = "md") -> dict:
    return {
        "story_run_id": run,
        "final_review_reference": reference.model_dump(mode="json"),
        "format": fmt,
    }


def test_tool_schema_is_flat_and_exact(open_app):
    tools = {t.name: t for t in list_tools(open_app)}
    assert set(tools) == {"render_report"}
    schema = tools["render_report"].input_schema
    assert schema["properties"].keys() == {
        "story_run_id",
        "final_review_reference",
        "format",
    }
    assert schema.get("required") == ["story_run_id", "final_review_reference", "format"]


def test_render_report_round_trip(make_app, seed_finalized):
    run = run_id()
    reference = seed_finalized(run)
    result = call_tool(make_app, None, "render_report", _render_args(run, reference))
    assert not result.is_error
    payload = _payload(result)
    assert payload["created"] is True
    assert payload["format"] == "md"
    assert payload["reference"]["type"] == "report-md"
    assert payload["reference"]["content_type"] == "text/markdown"


def test_render_retry_is_idempotent_over_the_wire(make_app, seed_finalized):
    run = run_id()
    reference = seed_finalized(run)
    first = _payload(call_tool(make_app, None, "render_report", _render_args(run, reference)))
    retry = _payload(call_tool(make_app, None, "render_report", _render_args(run, reference)))
    assert retry["created"] is False
    assert retry["reference"] == first["reference"]


def test_render_both_formats(make_app, seed_finalized):
    run = run_id()
    reference = seed_finalized(run)
    md = _payload(call_tool(make_app, None, "render_report", _render_args(run, reference, "md")))
    pdf = _payload(call_tool(make_app, None, "render_report", _render_args(run, reference, "pdf")))
    assert md["reference"]["content_type"] == "text/markdown"
    assert pdf["reference"]["content_type"] == "application/pdf"


def test_missing_final_review_is_artifact_not_found(make_app):
    from tests.conftest import artifact_id, past_datetime

    from review_schemas.synthesis import ArtifactReference

    run = run_id()
    ghost = ArtifactReference(
        artifact_id=artifact_id(),
        story_run_id=run,
        type="finalized-review",
        version=1,
        created_at=past_datetime(),
        content_type="application/json",
        checksum_sha256="0" * 64,
    )
    result = call_tool(make_app, None, "render_report", _render_args(run, ghost))
    assert result.is_error
    assert _payload(result)["error"]["code"] == "ARTIFACT_NOT_FOUND"


def test_cross_run_reference_is_validation_error(make_app, seed_finalized):
    reference = seed_finalized(run_id())
    result = call_tool(
        make_app, None, "render_report", _render_args(run_id(), reference)
    )
    assert result.is_error
    assert _payload(result)["error"]["code"] == "VALIDATION_ERROR"


def test_wrong_reference_type_is_validation_error(make_app, seed_finalized):
    run = run_id()
    reference = seed_finalized(run).model_copy(update={"type": "synthesis"})
    result = call_tool(make_app, None, "render_report", _render_args(run, reference))
    assert result.is_error
    assert _payload(result)["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_field_is_validation_error(make_app, seed_finalized):
    run = run_id()
    reference = seed_finalized(run)
    args = _render_args(run, reference)
    args["unexpected"] = 1
    result = call_tool(make_app, None, "render_report", args)
    assert result.is_error
    assert _payload(result)["error"]["code"] == "VALIDATION_ERROR"


def test_facilitator_is_forbidden(make_app, seed_finalized):
    run = run_id()
    reference = seed_finalized(run)
    token = _principal.set(FACI)
    try:
        result = call_tool(make_app, {ORCH}, "render_report", _render_args(run, reference))
        assert result.is_error
        assert _payload(result)["error"]["code"] == "FORBIDDEN"
    finally:
        _principal.reset(token)


def test_orchestration_caller_is_allowed(make_app, seed_finalized):
    run = run_id()
    reference = seed_finalized(run)
    token = _principal.set(ORCH)
    try:
        result = call_tool(make_app, {ORCH}, "render_report", _render_args(run, reference))
        assert not result.is_error
    finally:
        _principal.reset(token)


def test_missing_principal_with_roles_fails_unauthenticated(make_app, seed_finalized):
    run = run_id()
    reference = seed_finalized(run)
    result = call_tool(make_app, {ORCH}, "render_report", _render_args(run, reference))
    assert result.is_error
    assert _payload(result)["error"]["code"] == "UNAUTHENTICATED"


def test_correlation_id_propagates_into_errors(make_app):
    from tests.conftest import artifact_id, past_datetime

    from review_schemas.synthesis import ArtifactReference

    run = run_id()
    ghost = ArtifactReference(
        artifact_id=artifact_id(),
        story_run_id=run,
        type="finalized-review",
        version=1,
        created_at=past_datetime(),
        content_type="application/json",
        checksum_sha256="0" * 64,
    )
    correlation = str(uuid.uuid4())
    result = call_tool(
        make_app,
        None,
        "render_report",
        _render_args(run, ghost),
        headers={"x-correlation-id": correlation},
    )
    assert _payload(result)["error"]["correlation_id"] == correlation


def test_unexpected_internal_error_is_not_retryable():
    from uuid import uuid4

    from report_mcp.errors import error_for

    payload = error_for(RuntimeError("boom"), uuid4())
    assert payload.error.code == "UPSTREAM_UNAVAILABLE"
    assert payload.error.retryable is False
    assert payload.error.retry_after_seconds is None


# -- ingress middleware (ported from the artifact-server contract tests) ---


def _fake_verifier(email: str):
    def verify(token: str, audience: str) -> dict:
        assert token == "good-token"
        return {"email": email}

    return verify


def _ingress_post(app):
    async def scenario():
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(
            transport=transport, base_url="http://report.test"
        ) as c:
            return await c.post(
                "http://report.test/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )

    return asyncio.run(scenario())


def _ingress_get(app, path="/health"):
    async def scenario():
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(
            transport=transport, base_url="http://report.test"
        ) as c:
            return await c.get(f"http://report.test{path}")

    return asyncio.run(scenario())


def test_missing_token_is_rejected_at_ingress(make_app):
    app = IdTokenAuthMiddleware(make_app(None), _fake_verifier(ORCH), "https://report.test")
    assert _ingress_post(app).status_code == 401


def test_invalid_token_is_rejected_at_ingress(make_app):
    def bad(token: str, audience: str) -> dict:
        raise ValueError("bad token")

    app = IdTokenAuthMiddleware(make_app(None), bad, "https://report.test")
    assert _ingress_post(app).status_code == 401


def test_missing_audience_fails_closed(make_app):
    app = IdTokenAuthMiddleware(make_app(None), _fake_verifier(ORCH), "")
    assert _ingress_post(app).status_code == 503


def test_health_is_public(make_app):
    app = IdTokenAuthMiddleware(make_app(None), _fake_verifier(ORCH), "https://report.test")
    assert _ingress_get(app).status_code == 200


def test_verified_allowlisted_caller_succeeds(make_app, seed_finalized):
    run = run_id()
    reference = seed_finalized(run)

    def authed_factory(callers):
        return IdTokenAuthMiddleware(
            make_app({ORCH}), _fake_verifier(ORCH), "https://report.test"
        )

    result = call_tool(
        authed_factory,
        {ORCH},
        "render_report",
        _render_args(run, reference),
        headers={"Authorization": "Bearer good-token"},
    )
    assert not result.is_error
