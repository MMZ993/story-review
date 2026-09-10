"""Session-lineage input assembly (data-flow.md §2).

Deterministic helpers that fetch the story and the run's artifact lineage
via the artifact/story MCP seams and parse artifact content back into the
shared strict models — never a global "latest": every reference is scoped
to the session's story run.
"""

from __future__ import annotations

import json

from review_schemas.review import StoryDetail
from review_schemas.synthesis import ArtifactReference
from review_schemas.mcp import (
    GetArtifactInput,
    ListArtifactsInput,
    ListArtifactsOutput,
)

from . import flows
from .mcp_client import McpClient


def parse_content(model, content):
    """Strict-parse artifact content (StrictModel needs the JSON path)."""
    raw = content if isinstance(content, str) else json.dumps(content)
    return model.model_validate_json(raw)


async def list_run_artifacts(
    artifact_client: McpClient, story_run_id: str, deadline: float, correlation_id: str
) -> list[ArtifactReference]:
    """All artifact references of the run (lineage scope)."""
    payload = ListArtifactsInput(story_run_id=story_run_id, limit=500).model_dump(
        mode="json"
    )
    try:
        raw = await artifact_client.call("list_artifacts", payload, deadline=deadline)
        return ListArtifactsOutput.model_validate_json(json.dumps(raw)).items
    except Exception as failure:
        raise flows._upstream("artifact MCP unavailable", correlation_id) from failure


def latest(
    references: list[ArtifactReference],
    type_: str,
    perspective: str | None,
    correlation_id: str = "",
) -> ArtifactReference:
    """Latest artifact of one slot (max version) — session lineage only."""
    matches = [
        ref
        for ref in references
        if ref.type == type_ and ref.perspective == perspective
    ]
    if not matches:
        raise flows._upstream(
            f"missing {type_} artifact in the session lineage", correlation_id
        )  # pragma: no cover - flow 1 always seeds all slots
    return max(matches, key=lambda ref: ref.version)


async def artifact_content(
    artifact_client: McpClient,
    reference: ArtifactReference,
    deadline: float,
    correlation_id: str,
) -> dict:
    """Fetch one artifact's content as a JSON dict (model input)."""
    payload = GetArtifactInput(
        artifact_id=reference.artifact_id, story_run_id=reference.story_run_id
    ).model_dump(mode="json")
    try:
        raw = await artifact_client.call("get_artifact", payload, deadline=deadline)
    except Exception as failure:
        raise flows._upstream("artifact MCP unavailable", correlation_id) from failure
    content = raw["content"]
    if hasattr(content, "model_dump"):
        content = content.model_dump(mode="json")
    return content


async def assemble_inputs(
    story_client: McpClient,
    artifact_client: McpClient,
    session,
    deadline: float,
    correlation_id: str,
) -> tuple[StoryDetail, list[ArtifactReference]]:
    """Deterministic input assembly: story + the run's artifact lineage."""
    story = await flows._get_story(
        story_client, session.story_id, deadline, correlation_id
    )
    references = await list_run_artifacts(
        artifact_client, session.story_run_id, deadline, correlation_id
    )
    return story, references
