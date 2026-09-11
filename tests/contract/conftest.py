"""Shared helpers for the compose cross-service contract tests.

Each test drives the *running* compose services (make compose-up) over real
HTTP with the `mcp` client SDK — exactly the transport orchestration will
use. Service base URLs come from environment variables with the compose
defaults; a missing service fails loudly here rather than being skipped.

The servers run auth-disabled (local profile only), so caller-allowlist
behavior is NOT covered here — the per-server suites own it.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

STORY_URL = os.environ.get("STORY_URL", "http://127.0.0.1:8101")
ARTIFACT_URL = os.environ.get("ARTIFACT_URL", "http://127.0.0.1:8102")
REPORT_URL = os.environ.get("REPORT_URL", "http://127.0.0.1:8103")
FAKE_GCS_URL = os.environ.get("FAKE_GCS_URL", "http://127.0.0.1:9025")
BUCKET = os.environ.get("ARTIFACT_BUCKET", "artifacts-local")


def call_tool(base_url: str, tool: str, arguments: dict):
    """One MCP round trip against a live service; returns CallToolResult."""

    async def run():
        async with streamable_http_client(f"{base_url}/mcp") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool, arguments)

    return asyncio.run(run())


def list_tools(base_url: str) -> list:
    async def run():
        async with streamable_http_client(f"{base_url}/mcp") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return (await session.list_tools()).tools

    return asyncio.run(run())


def payload(result) -> dict:
    """The structured payload of a successful (non-error) result."""
    assert result.structured_content is not None, result.content
    return dict(result.structured_content)


def error(result) -> dict:
    """The structured ToolError payload of an is_error result."""
    assert result.is_error, result.structured_content
    return dict(result.structured_content)["error"]


def run_id() -> str:
    return f"run-{uuid.uuid4()}"


def new_key() -> str:
    return str(uuid.uuid4())


def checksum(content: dict) -> str:
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.fixture(scope="session")
def finalized_review() -> dict:
    """A minimal valid FinalizedReview payload (same shape as the report
    server's own fixtures): one resolved issue, no open issues, PO accepted."""

    def factory(run: str) -> dict:
        past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        return {
            "story_id": "story-01",
            "story_run_id": run,
            "synthesis_reference": {
                "artifact_id": f"art-{uuid.uuid4()}",
                "story_run_id": run,
                "type": "synthesis",
                "version": 1,
                "created_at": past,
                "content_type": "application/json",
                "checksum_sha256": "0" * 64,
            },
            "issues": [
                {
                    "issue": "Missing business value statement",
                    "title": "Missing business value statement",
                    "description": "The story lacks an expected-uptake rationale.",
                    "severity": "major",
                    "source": "synthesis",
                }
            ],
            "resolutions": [
                {
                    "issue": "Missing business value statement",
                    "disposition": "resolved",
                    "explanation": "PO added the expected uptake rationale.",
                    "turn_number": 2,
                }
            ],
            "remaining_open_issues": [],
            "po_accepted": True,
            "final_turn_number": 3,
            "finalized_at": past,
        }

    return factory


@pytest.fixture(scope="session")
def seeded_finalized(finalized_review):
    """Save a finalized-review artifact through the live artifact server and
    return (run, reference) for report-server render calls."""

    def seed() -> tuple[str, dict]:
        run = run_id()
        result = call_tool(
            ARTIFACT_URL,
            "save_artifact",
            {
                "type": "finalized-review",
                "story_run_id": run,
                "perspective": None,
                "content": finalized_review(run),
                "idempotency_key": new_key(),
            },
        )
        reference = payload(result)["reference"]
        return run, reference

    return seed


def wait_healthy(base_url: str, timeout_s: float = 60.0) -> None:
    """Block until a compose service answers /health (public path)."""
    import time
    import urllib.request

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"service not healthy: {base_url}")


@pytest.fixture(scope="session", autouse=True)
def services_up():
    """Fail loudly (not skip) when the compose stack is not reachable."""
    for url in (STORY_URL, ARTIFACT_URL, REPORT_URL):
        wait_healthy(url)
    yield
