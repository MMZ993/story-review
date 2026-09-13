"""Audience-scoped ID-token headers for deployed MCP calls (inc 4).

Deterministic: the metadata fetch is injected. Also covers the McpClient
header-forwarding seam and the config switch.
"""

from __future__ import annotations

import pytest

from orchestration import id_tokens
from orchestration.config import Settings
from orchestration.mcp_client import McpClient


def make_settings(**overrides) -> Settings:
    values = dict(
        db_dsn="postgresql://x",
        story_url="http://story:8080/mcp",
        artifact_url="http://artifact:8080/mcp",
        report_url="http://report:8080/mcp",
        bucket="b",
        business_url="http://b",
        engineering_url="http://e",
        synthesis_url="http://s",
        facilitator_url="http://f",
    )
    values.update(overrides)
    return Settings(**values)


def env_settings(**env) -> Settings:
    """Settings.from_env with the full mandatory ORCH_* set."""
    return Settings.from_env(
        dict(
            ORCH_DB_DSN="postgresql://x",
            ORCH_STORY_URL="http://story:8080/mcp",
            ORCH_ARTIFACT_URL="http://artifact:8080/mcp",
            ORCH_REPORT_URL="http://report:8080/mcp",
            ORCH_BUCKET="b",
            ORCH_BUSINESS_URL="http://b",
            ORCH_ENGINEERING_URL="http://e",
            ORCH_SYNTHESIS_URL="http://s",
            ORCH_FACILITATOR_URL="http://f",
            **env,
        )
    )


class TestMetadataIdToken:
    def test_mints_and_caches_per_audience(self, monkeypatch):
        calls = []

        def fetch(url):
            calls.append(url)
            return "tok-1", "3600"

        now = [0.0]
        headers = id_tokens.metadata_id_token(
            "https://svc/mcp", _fetch=fetch, _now=lambda: now[0]
        )
        assert headers == {"Authorization": "Bearer tok-1"}
        assert "https%3A%2F%2Fsvc%2Fmcp" in calls[0]
        # Second call inside the lifetime: served from cache.
        now[0] = 100.0
        id_tokens.metadata_id_token("https://svc/mcp", _fetch=fetch, _now=lambda: now[0])
        assert len(calls) == 1

    def test_re_mints_near_expiry(self, monkeypatch):
        id_tokens._cache.clear()

        def fetch(url):
            return "tok-2", "3600"

        now = [0.0]
        id_tokens.metadata_id_token(
            "https://svc2/mcp", _fetch=fetch, _now=lambda: now[0]
        )
        now[0] = 3600.0 - id_tokens._EXPIRY_MARGIN_SECONDS
        headers = id_tokens.metadata_id_token(
            "https://svc2/mcp", _fetch=fetch, _now=lambda: now[0]
        )
        assert headers == {"Authorization": "Bearer tok-2"}

    def test_no_metadata_server_raises(self):
        id_tokens._cache.clear()

        def broken_fetch(url):
            raise OSError("no metadata server")

        with pytest.raises(OSError):
            id_tokens.metadata_id_token(
                "https://svc/mcp", _fetch=broken_fetch, _now=lambda: 0.0
            )


class TestConfigSwitch:
    def test_default_off(self):
        assert make_settings().mcp_id_token_auth is False

    def test_opt_in(self):
        assert env_settings(ORCH_MCP_ID_TOKEN_AUTH="1").mcp_id_token_auth is True


class TestMcpClientHeaderForwarding:
    async def test_no_auth_by_default_passes_no_headers(self):
        seen = {}

        async def session_call(url, tool, arguments, timeout_s, **kwargs):
            seen.update(kwargs)

        client = McpClient(
            "http://story:8080/mcp", make_settings(), session_call=session_call
        )
        await client.call("list_stories", {})
        assert seen == {}

    async def test_auth_factory_headers_reach_the_transport(self):
        seen = {}

        async def session_call(url, tool, arguments, timeout_s, **kwargs):
            seen.update(kwargs)
            return {"ok": True}

        client = McpClient(
            "https://svc/mcp",
            make_settings(),
            session_call=session_call,
            auth_headers=lambda: {"Authorization": "Bearer tok"},
        )
        await client.call("list_stories", {})
        assert seen == {"headers": {"Authorization": "Bearer tok"}}

    async def test_probe_forwards_headers_too(self):
        seen = {}

        async def session_call(url, tool, arguments, timeout_s, **kwargs):
            seen.update(kwargs)
            return {"ok": True}

        client = McpClient(
            "https://svc/mcp",
            make_settings(),
            session_call=session_call,
            auth_headers=lambda: {"Authorization": "Bearer tok"},
        )
        assert await client.probe() is True
        assert seen == {"headers": {"Authorization": "Bearer tok"}}


class TestStreamableTransportAuthInjection:
    """Pin the mcp 2.1.1 seam: auth headers ride an injected
    caller-owned httpx client (streamable_http_client has no headers
    parameter in 2.1.1)."""

    async def test_headers_travel_via_injected_http_client(self, monkeypatch):
        import contextlib

        from orchestration import mcp_client as mod

        seen = {}

        @contextlib.asynccontextmanager
        async def fake_transport(url, **kwargs):
            seen["url"] = url
            seen["kwargs"] = kwargs

            yield object(), object()

        monkeypatch.setattr(mod, "streamable_http_client", fake_transport)

        @contextlib.asynccontextmanager
        async def fake_session(read, write):
            class S:
                async def initialize(self):
                    pass

                async def call_tool(self, tool, args):
                    seen["tool"] = tool
                    from mcp.types import CallToolResult

                    return CallToolResult(
                        content=[], structured_content={"ok": True},
                        is_error=False,
                    )

            yield S()

        monkeypatch.setattr(mod, "ClientSession", fake_session)
        result = await mod._streamable_http_call(
            "https://svc/mcp",
            "list_stories",
            {},
            timeout_s=5,
            headers={"Authorization": "Bearer tok"},
        )
        assert result == {"ok": True}
        http_client = seen["kwargs"]["http_client"]
        assert http_client.headers.get("Authorization") == "Bearer tok"
        await http_client.aclose()  # caller-owned; closed by the transport

    async def test_no_headers_no_injected_client(self, monkeypatch):
        import contextlib

        from orchestration import mcp_client as mod

        seen = {}

        @contextlib.asynccontextmanager
        async def fake_transport(url, **kwargs):
            seen["kwargs"] = kwargs

            yield object(), object()

        monkeypatch.setattr(mod, "streamable_http_client", fake_transport)

        @contextlib.asynccontextmanager
        async def fake_session(read, write):
            class S:
                async def initialize(self):
                    pass

            yield S()

        monkeypatch.setattr(mod, "ClientSession", fake_session)
        await mod._streamable_http_call("https://svc/mcp", None, {}, timeout_s=5)
        assert "http_client" not in seen["kwargs"]
