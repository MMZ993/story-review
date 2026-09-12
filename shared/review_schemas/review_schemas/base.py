"""Strict base types for all shared schema models.

Implements the "Strict base types" section of docs/design/schemas.md verbatim:
`StrictModel` (unknown fields forbidden, strict mode) plus the constrained
identifier/text aliases and literal unions every other module builds on.

Errors raised: pydantic.ValidationError on any boundary violation; nothing here
performs I/O or normalization beyond what the annotations declare.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    StringConstraints,
    UUID4,
)


class StrictModel(BaseModel):
    """Base for every shared model: no extra fields, no implicit coercion."""

    model_config = ConfigDict(extra="forbid", strict=True)


StoryId = Annotated[
    str,
    StringConstraints(
        pattern=r"^(story-[0-9]{2}|ado-[0-9]{1,8})$", min_length=5, max_length=12
    ),
]
# `story-NN` = frozen mock dataset; `ado-N` = live Azure DevOps work item
# (story MCP server dual source). The id spaces never mix within a call or
# story run.
StorySource = Literal["azure", "mock"]
RunId = Annotated[
    str,
    StringConstraints(
        pattern=r"^run-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        min_length=40,
        max_length=40,
    ),
]
SessionId = Annotated[
    str,
    StringConstraints(
        pattern=r"^sess-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        min_length=41,
        max_length=41,
    ),
]
ArtifactId = Annotated[
    str,
    StringConstraints(
        pattern=r"^art-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        min_length=40,
        max_length=40,
    ),
]
AgentRunId = Annotated[
    str,
    StringConstraints(
        pattern=r"^arun-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        min_length=41,
        max_length=41,
    ),
]
Text = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000),
]
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
HttpsUrl = Annotated[
    str,
    StringConstraints(pattern=r"^https://", min_length=9, max_length=4096),
]
UtcDatetime = AwareDatetime
IdempotencyKey = UUID4
CorrelationId = UUID4
# Anonymous per-user scoping key (X-User-Id): an opaque grouping key the
# client generates once — never a proof of identity (api-contract.md).
UserId = UUID4
LeaseToken = UUID4

Format = Literal["md", "pdf"]
Perspective = Literal["business", "engineering"]
ArtifactType = Literal[
    "story",
    "review-business",
    "review-engineering",
    "synthesis",
    "finalized-review",
    "report-md",
    "report-pdf",
]
SaveArtifactType = Literal[
    "story",
    "review-business",
    "review-engineering",
    "synthesis",
    "finalized-review",
]
SessionState = Literal[
    "active",
    "parked",
    "finalizing",
    "completed",
]
TurnOutcome = Literal["continue", "park", "finalize"]
RecordState = Literal["pending", "running", "succeeded", "failed"]
