"""Deterministic test doubles for increment 2 (D15-3).

`FakeArtifactMcp` scripts the McpClient `session_call` seam with real
artifact-service semantics (dedup by `(run, type, idempotency key)`,
per-type versioning, run-scoped listing) so flow tests exercise the
actual MCP call paths without compose. Agent fakes implement the frozen
Phase 5 adapter invocation interface in-process; LLM behavior is never
scripted (D13) — only typed outputs and transport failures.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from review_schemas.errors import ErrorBody
from review_schemas.facilitator import DelegationDecision, FacilitatorTurnOutput
from review_schemas.review import ReviewReport, StoryDetail
from orchestration.mcp_client import McpCallFailure

CONTENT_TYPES = {
    "story": "application/json",
    "review-business": "application/json",
    "review-engineering": "application/json",
    "synthesis": "application/json",
    "finalized-review": "application/json",
    "report-md": "text/markdown",
    "report-pdf": "application/pdf",
}


def story_detail(story_id: str = "story-07") -> StoryDetail:
    """A schema-valid story payload for review input."""
    return StoryDetail(
        story_id=story_id,  # type: ignore[arg-type]
        title=f"Story {story_id}",
        status="New",
        description="As a user I want a feature so that value flows.",
        acceptance_criteria=["Given a story when reviewed then findings appear."],
        epic_context="Epic 3 — reporting.",
        roadmap_context="Q3 reporting milestone.",
    )


def review_report(perspective: str, story_id: str) -> ReviewReport:
    """A schema-valid single-perspective review."""
    prefix = "B-" if perspective == "business" else "E-"
    return ReviewReport(
        perspective=perspective,  # type: ignore[arg-type]
        story_id=story_id,  # type: ignore[arg-type]
        summary=f"{perspective} summary of {story_id}.",
        findings=[
            {
                "id": f"{prefix}1",
                "title": "Gap found",
                "description": "The story misses an important case.",
                "severity": "minor",
                "category": "completeness",
            }
        ],
        risks=[],
        questions_for_po=["Which rate limit applies?"],
    )


def opening_turn_output() -> FacilitatorTurnOutput:
    """A schema-valid opening facilitator turn (invoke=none, no resolutions)."""
    return FacilitatorTurnOutput(
        reply="Opening the review dialogue; two issues need PO input.",
        delegation=DelegationDecision(
            invoke="none",
            open_issues=[
                "Which rate limit applies?",
                "Business value unclear",
            ],
            readiness="needs_work",
        ),
        resolutions=[],
    )


def story_transport(detail: StoryDetail):
    """McpClient session_call seam serving `get_story` for one story."""

    async def transport(url, tool, arguments, timeout_s):
        assert tool == "get_story"
        if arguments["story_id"] != detail.story_id:
            raise McpCallFailure(
                ErrorBody(
                    code="STORY_NOT_FOUND",
                    message=f"unknown story {arguments['story_id']}",
                    correlation_id=uuid.uuid4(),
                    retryable=False,
                )
            )
        return detail.model_dump(mode="json")

    return transport


class FakeArtifactMcp:
    """McpClient session_call seam with artifact-service semantics."""

    def __init__(self) -> None:
        self.save_calls: list[dict] = []
        self._by_slot: dict[tuple[str, str, str], dict] = {}
        self._artifacts: dict[str, dict] = {}

    async def __call__(self, url, tool, arguments, timeout_s):
        if tool == "save_artifact":
            return self._save(arguments)
        if tool == "list_artifacts":
            return self._list(arguments)
        if tool == "get_artifact":
            return self._get(arguments)
        raise AssertionError(f"unexpected artifact tool {tool!r}")

    def _save(self, arguments: dict) -> dict:
        self.save_calls.append(arguments)
        slot = (
            arguments["story_run_id"],
            arguments["type"],
            str(arguments["idempotency_key"]),
        )
        existing = self._by_slot.get(slot)
        if existing is not None:
            reference = dict(existing["reference"])
            reference.pop("is_latest", None)
            return {"reference": reference, "created": False}
        type_ = arguments["type"]
        perspective = arguments.get("perspective")
        version = (
            1
            + sum(
                1
                for artifact in self._artifacts.values()
                if artifact["reference"]["story_run_id"] == arguments["story_run_id"]
                and artifact["reference"]["type"] == type_
                and artifact["reference"].get("perspective") == perspective
            )
        )
        content = arguments["content"]
        checksum = hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()
        artifact_id = "art-" + str(
            uuid.uuid5(uuid.NAMESPACE_URL, "|".join(slot))
        )
        reference = {
            "artifact_id": artifact_id,
            "story_run_id": arguments["story_run_id"],
            "type": type_,
            "perspective": perspective,
            "version": version,
            "created_at": datetime.now(UTC).isoformat(),
            "content_type": CONTENT_TYPES[type_],
            "checksum_sha256": checksum,
        }
        self._by_slot[slot] = {"reference": dict(reference)}
        self._artifacts[artifact_id] = {
            "reference": dict(reference),
            "content": content,
        }
        plain = dict(reference)
        return {"reference": plain, "created": True}

    def _list(self, arguments: dict) -> dict:
        items = [
            dict(a["reference"], is_latest=True)
            for a in self._artifacts.values()
            if a["reference"]["story_run_id"] == arguments["story_run_id"]
        ]
        items.sort(
            key=lambda r: (r["type"], r.get("perspective") or "", r["version"])
        )
        return {"items": items, "total": len(items)}

    def _get(self, arguments: dict) -> dict:
        artifact = self._artifacts.get(arguments["artifact_id"])
        if artifact is None:
            raise McpCallFailure(
                ErrorBody(
                    code="ARTIFACT_NOT_FOUND",
                    message="unknown artifact",
                    correlation_id=uuid.uuid4(),
                    retryable=False,
                )
            )
        reference = dict(artifact["reference"])
        reference.pop("is_latest", None)
        return {"reference": reference, "content": artifact["content"]}
