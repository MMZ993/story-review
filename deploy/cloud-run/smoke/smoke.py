# Phase 4 increment 5 smoke tests: authenticated calls against the deployed
# Cloud Run MCP services, using an ID token minted for sa-orchestration
# (audience = the target service URL). Mirrors the compose contract tests'
# call shapes, but standalone and token-authenticated.
#
# Usage (token minted by the Makefile targets):
#   MCP_ID_TOKEN=... python smoke.py story    <story-url>   [story_id]
#   MCP_ID_TOKEN=... python smoke.py artifact <artifact-url>
#   MCP_ID_TOKEN=... python smoke.py report   <report-url> <artifact-url>
#
# Exit 0 + "smoke ok: ..." on success; non-zero with the failure printed.
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def _call(base_url: str, token: str, tool: str, arguments: dict):
    async def run():
        # mcp 2.x: auth headers go on the injected httpx client.
        async with streamable_http_client(
            f"{base_url}/mcp",
            http_client=httpx2.AsyncClient(
                headers={"authorization": f"Bearer {token}"}, timeout=60.0
            ),
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool, arguments)

    return asyncio.run(run())


def _payload(result) -> dict:
    if result.is_error:
        error = dict(result.structured_content or {}).get("error", result.content)
        raise AssertionError(f"tool error: {error}")
    assert result.structured_content is not None, result.content
    return dict(result.structured_content)


def _error(result) -> dict:
    assert result.is_error, result.structured_content
    return dict(result.structured_content)["error"]


def smoke_story(url: str, story_id: str = "story-01") -> str:
    listed = _payload(_call(url, _token(url), "list_stories", {}))
    ids = {s["story_id"] for s in listed["stories"]}
    assert story_id in ids, f"{story_id} missing from list_stories ({len(ids)} stories)"
    detail = _payload(_call(url, _token(url), "get_story", {"story_id": story_id}))
    assert detail["story_id"] == story_id and detail["title"]
    miss = _error(_call(url, _token(url), "get_story", {"story_id": "story-99"}))
    assert miss["code"] == "STORY_NOT_FOUND"
    return f"story: {len(ids)} stories listed, {story_id} detail ok, STORY_NOT_FOUND ok"


def smoke_artifact(url: str) -> str:
    run = f"run-{uuid.uuid4()}"
    key = str(uuid.uuid4())
    content = {
        "story_id": "story-01",
        "title": "Smoke test story",
        "status": "New",
        "description": "Phase 4 increment 5 smoke roundtrip.",
        "acceptance_criteria": ["smoke passes"],
        "epic_context": "Epic — Feature",
        "roadmap_context": "Roadmap context text.",
        "comments": [],
        "context_stories": [],
    }
    args = {
        "type": "story",
        "story_run_id": run,
        "perspective": None,
        "content": content,
        "idempotency_key": key,
    }
    saved = _payload(_call(url, _token(url), "save_artifact", args))
    assert saved["created"] is True
    ref = saved["reference"]
    got = _payload(
        _call(url, _token(url), "get_artifact", {"story_run_id": run, "artifact_id": ref["artifact_id"]})
    )
    assert got["content"] == content
    return f"artifact: save/get roundtrip ok (run {run})"


def smoke_report(url: str, artifact_url: str) -> str:
    # Seed a finalized-review through the live artifact server, then render.
    run = f"run-{uuid.uuid4()}"
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    finalized = {
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
    saved = _payload(
        _call(
            artifact_url,
            _token(artifact_url),
            "save_artifact",
            {
                "type": "finalized-review",
                "story_run_id": run,
                "perspective": None,
                "content": finalized,
                "idempotency_key": str(uuid.uuid4()),
            },
        )
    )
    reference = saved["reference"]
    out = _payload(
        _call(
            url,
            _token(url),
            "render_report",
            {"story_run_id": run, "final_review_reference": reference, "format": "md"},
        )
    )
    assert out["created"] is True and out["reference"]["type"] == "report-md"
    return f"report: md rendered from live-saved finalized review (run {run})"


def _token(url: str) -> str:
    """Token for the given service (per-service audiences; exact match)."""
    name = "MCP_ID_TOKEN_ARTIFACT" if url == os.environ.get("MCP_ARTIFACT_URL", "") else "MCP_ID_TOKEN"
    token = os.environ.get(name, "")
    assert token, f"{name} not set — mint one via the make mcp-*-smoke target"
    return token


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if mode == "story":
            message = smoke_story(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "story-01")
        elif mode == "artifact":
            message = smoke_artifact(sys.argv[2])
        elif mode == "report":
            message = smoke_report(sys.argv[2], sys.argv[3])
        else:
            print(__doc__)
            return 2
    except Exception as exc:  # noqa: BLE001 — smoke prints any failure
        print(f"smoke FAILED ({mode}): {exc}")
        return 1
    print(f"smoke ok: {message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
