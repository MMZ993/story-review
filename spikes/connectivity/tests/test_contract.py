"""MCP service contract tests over the in-memory MCP transport.

The contract: exactly two tools, structured JSON responses, correlation ID in
every response, and an authenticated-caller requirement. The local test adapter
supplies a fake verified principal through the server's principal-provider
hook; the deployed code never disables the authorization boundary.
"""

import pytest
from mcp import Client
from mcp.types import CallToolResult

import spike_mcp.server as spike_server
from spike_mcp.principal import Principal


async def _call_tool(client: Client, name: str, arguments: dict) -> CallToolResult:
    result = await client.call_tool(name, arguments)
    assert not result.is_error, f"unexpected tool error: {result.content}"
    return result


@pytest.fixture
def server_with_fake_principal() -> spike_server.SessionMarkerServer:
    server = spike_server.create_server()
    server.set_principal_provider(lambda: Principal(email="fake@spike.iam.gserviceaccount.com"))
    return server


async def test_persist_then_restore_round_trip(server_with_fake_principal) -> None:
    async with Client(server_with_fake_principal.app()) as client:
        stored = await _call_tool(
            client,
            "persist_session",
            {"session_id": "session-1", "marker": "marker-1", "correlation_id": "corr-1"},
        )
        payload = spike_server.tool_payload(stored)
        assert payload == {
            "stored": True,
            "session_id": "session-1",
            "correlation_id": "corr-1",
        }

        restored = await _call_tool(
            client, "restore_session", {"session_id": "session-1", "correlation_id": "corr-1"}
        )
        payload = spike_server.tool_payload(restored)
        assert payload["found"] is True
        assert payload["session_id"] == "session-1"
        assert payload["marker"] == "marker-1"
        assert payload["correlation_id"] == "corr-1"


async def test_restore_unknown_session_is_defined_not_found(server_with_fake_principal) -> None:
    async with Client(server_with_fake_principal.app()) as client:
        result = await _call_tool(
            client, "restore_session", {"session_id": "missing", "correlation_id": "corr-2"}
        )
        payload = spike_server.tool_payload(result)
        assert payload == {
            "found": False,
            "session_id": "missing",
            "marker": None,
            "correlation_id": "corr-2",
        }


async def test_unauthenticated_caller_is_rejected() -> None:
    server = spike_server.create_server()
    # No principal provider installed: every call must be rejected.
    async with Client(server.app()) as client:
        result = await client.call_tool(
            "persist_session",
            {"session_id": "session-1", "marker": "marker-1", "correlation_id": "corr-1"},
        )
        assert result.is_error

    # A subsequent authenticated restore must find nothing: the rejected
    # call did not mutate the store.
    server.set_principal_provider(
        lambda: Principal(email="fake@spike.iam.gserviceaccount.com")
    )
    async with Client(server.app()) as client:
        result = await _call_tool(
            client, "restore_session", {"session_id": "session-1", "correlation_id": "corr-r"}
        )
        assert spike_server.tool_payload(result)["found"] is False


async def test_invalid_request_is_rejected_as_tool_error(server_with_fake_principal) -> None:
    async with Client(server_with_fake_principal.app()) as client:
        result = await client.call_tool(
            "persist_session",
            {"session_id": "", "marker": "marker-1", "correlation_id": "corr-1"},
        )
        assert result.is_error
