"""Authenticated Cloud Run MCP transport for the disposable Agent Engine caller.

The transport obtains a Google ID token for the configured Cloud Run service URL
and supplies it to the MCP streamable-HTTP client. `CloudRunMcpTransport` is
stateless: every tool call opens, initializes, calls, and closes a client
session. This is deliberate for the two-request connectivity proof.

Inputs: a Cloud Run service URL, an MCP tool name, and JSON-compatible tool
arguments. Outputs: the MCP tool's structured JSON payload. Side effects: token
minting and an authenticated HTTPS request. Errors from Google credentials, the
MCP client, or malformed tool results propagate to ADK unchanged.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol



class McpInvoker(Protocol):
    """Execute one MCP tool call with an already-minted ID token."""

    def __call__(self, token: str, tool_name: str, arguments: dict) -> Awaitable[dict]: ...


TokenProvider = Callable[[str], str]


def google_id_token(audience: str) -> str:
    """Mint an ID token for `audience` using the active workload credentials.

    This uses Agent Engine's runtime service account in deployment and ADC only
    for local diagnostics. Credential acquisition errors propagate unchanged.
    """
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    return id_token.fetch_id_token(Request(), audience)


class CloudRunMcpTransport:
    """Call the spike MCP endpoint with a Cloud Run audience-bound ID token."""

    def __init__(
        self,
        service_url: str,
        token_provider: TokenProvider = google_id_token,
        invoker: McpInvoker | None = None,
    ) -> None:
        """Configure the target URL and optional test seams without performing I/O."""
        if not service_url:
            raise ValueError("SPIKE_SERVICE_URL must be set")
        self._service_url = service_url.rstrip("/")
        self._token_provider = token_provider
        self._invoker = invoker or self._invoke_mcp

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Mint a service-audience token and return one MCP tool payload verbatim."""
        token = self._token_provider(self._service_url)
        return await self._invoker(token, tool_name, arguments)

    async def _invoke_mcp(self, token: str, tool_name: str, arguments: dict) -> dict:
        """Execute one initialized streamable-HTTP MCP tool call over HTTPS."""
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        # mcp 2.1.1 takes headers only through a custom httpx client
        # (the `headers=` kwarg was removed from streamable_http_client).
        async with streamable_http_client(
            f"{self._service_url}/mcp",
            http_client=httpx.AsyncClient(
                headers={"Authorization": f"Bearer {token}"}
            ),
        ) as streams:
            read_stream, write_stream = streams[0], streams[1]
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                if result.structured_content is not None:
                    return dict(result.structured_content)
                # mcp 2.1.1 servers without an output schema serialize dict
                # results as JSON text content; mirror spike_mcp.tool_payload.
                for item in result.content:
                    text = getattr(item, "text", None)
                    if text:
                        import json

                        return json.loads(text)
                raise ValueError("MCP tool result carries no structured payload")
