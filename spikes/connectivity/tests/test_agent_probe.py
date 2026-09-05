"""Agent-side probe tests.

The probe generates the correlation ID, forwards it with every MCP request,
and returns the tool result without interpreting it.
"""

import json
import uuid

from spike_agent.session_probe import SessionProbe, generate_correlation_id
from spike_agent.tools import build_tools
from spike_agent.transport import CloudRunMcpTransport


class FakeTransport:
    """Records requests and returns canned MCP tool-result payloads."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.requests: list[dict] = []

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        self.requests.append({"tool": tool_name, "arguments": dict(arguments)})
        return self._responses.pop(0)


def test_correlation_id_is_caller_generated_with_uuid_shape() -> None:
    value = generate_correlation_id()
    parsed = uuid.UUID(value)
    assert parsed.hex == value


async def test_persist_probe_carries_correlation_id_and_returns_payload_verbatim() -> None:
    response = {"stored": True, "session_id": "session-1", "correlation_id": "corr-1"}
    transport = FakeTransport([response])
    probe = SessionProbe(transport=transport)

    result = await probe.persist_session(session_id="session-1", marker="marker-1")

    sent = transport.requests[0]
    assert sent["tool"] == "persist_session"
    assert sent["arguments"]["session_id"] == "session-1"
    assert sent["arguments"]["marker"] == "marker-1"
    assert sent["arguments"]["correlation_id"] == probe.correlation_id
    # The probe exposes the payload without interpretation.
    assert result == response


async def test_restore_probe_reuses_the_same_correlation_id() -> None:
    response = {
        "found": True,
        "session_id": "session-1",
        "marker": "marker-1",
        "correlation_id": "corr-1",
    }
    transport = FakeTransport([response, response])
    probe = SessionProbe(transport=transport)

    await probe.persist_session(session_id="session-1", marker="marker-1")
    result = await probe.restore_session(session_id="session-1")

    correlation_ids = {r["arguments"]["correlation_id"] for r in transport.requests}
    assert correlation_ids == {probe.correlation_id}
    assert result == response


def test_probe_payload_is_json_serializable_for_logging() -> None:
    probe = SessionProbe(transport=FakeTransport([{"stored": True}]))
    record = probe.describe()
    json.dumps(record)  # must not raise
    assert "correlation_id" in record


async def test_cloud_run_transport_uses_service_url_as_token_audience() -> None:
    requested_audiences: list[str] = []
    received_tokens: list[str] = []

    async def invoke(token: str, tool_name: str, arguments: dict) -> dict:
        received_tokens.append(token)
        assert tool_name == "restore_session"
        assert arguments == {"session_id": "session-1", "correlation_id": "corr-1"}
        return {"found": False, "session_id": "session-1", "correlation_id": "corr-1"}

    transport = CloudRunMcpTransport(
        service_url="https://spike.example",
        token_provider=lambda audience: requested_audiences.append(audience) or "id-token",
        invoker=invoke,
    )

    result = await transport.call_tool(
        "restore_session", {"session_id": "session-1", "correlation_id": "corr-1"}
    )

    assert requested_audiences == ["https://spike.example"]
    assert received_tokens == ["id-token"]
    assert result["found"] is False


async def test_agent_persist_tool_forwards_marker_and_correlation_id() -> None:
    transport = FakeTransport(
        [{"stored": True, "session_id": "session-1", "correlation_id": "corr-1"}]
    )
    persist_session = build_tools(transport)[0]

    result = await persist_session(
        session_id="session-1", marker="marker-1", correlation_id="corr-1"
    )

    assert transport.requests == [
        {
            "tool": "persist_session",
            "arguments": {
                "session_id": "session-1",
                "marker": "marker-1",
                "correlation_id": "corr-1",
            },
        }
    ]
    assert result["stored"] is True


async def test_agent_restore_tool_forwards_caller_correlation_id() -> None:
    transport = FakeTransport(
        [{"found": True, "session_id": "session-1", "marker": "marker-1", "correlation_id": "corr-1"}]
    )
    restore_session = build_tools(transport)[1]

    result = await restore_session(session_id="session-1", correlation_id="corr-1")

    assert transport.requests == [
        {
            "tool": "restore_session",
            "arguments": {"session_id": "session-1", "correlation_id": "corr-1"},
        }
    ]
    assert result["marker"] == "marker-1"
