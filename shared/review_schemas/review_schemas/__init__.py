"""Public API of the review_schemas package.

Deliberate re-exports only: consumers import from `review_schemas`, never from
the internal modules. Every shared model named in docs/design/schemas.md must
appear here before Phase 2 closes. `ArtifactRecord` stays internal to the
persistence layer (importable from `review_schemas.synthesis`, not re-exported).
"""

from review_schemas.base import (
    AgentRunId,
    ArtifactId,
    ArtifactType,
    CorrelationId,
    Format,
    HttpsUrl,
    IdempotencyKey,
    LeaseToken,
    Perspective,
    RecordState,
    RunId,
    SaveArtifactType,
    SessionId,
    SessionState,
    Sha256,
    ShortText,
    StoryId,
    StrictModel,
    Text,
    TurnOutcome,
    UtcDatetime,
)
from review_schemas.errors import (
    ErrorBody,
    ErrorCode,
    ErrorEnvelope,
    ToolError,
)
from review_schemas.review import (
    Finding,
    ReviewReport,
    StoryDetail,
    StorySummary,
)
from review_schemas.synthesis import (
    ArtifactReference,
    ConflictItem,
    SynthesisReport,
)
from review_schemas.facilitator import (
    ConversationSummary,
    DelegationDecision,
    FacilitatorTurnOutput,
    FinalizedReview,
    ResolutionDraft,
    ResolutionItem,
)
from review_schemas.judge import (
    JudgeDimensionScore,
    JudgeIssue,
    JudgeResult,
)
from review_schemas.api import (
    CanonicalOperationResult,
    CanonicalReportResult,
    CanonicalTurnResult,
    CreateSessionRequest,
    CreateSessionResponse,
    FinalizeRequest,
    HealthDependency,
    HealthResponse,
    ListSessionsQuery,
    ListSessionsResponse,
    ListStoriesQuery,
    ListStoriesResponse,
    ReportDownload,
    ReportResponse,
    SessionDetail,
    SessionSummary,
    TurnRequest,
    TurnResponse,
    TurnView,
)
from review_schemas.records import (
    AgentRunRecord,
    SessionRecord,
    StoryRunRecord,
    TurnLeaseRecord,
    TurnRecord,
)
from review_schemas.mcp import (
    GetArtifactInput,
    GetArtifactOutput,
    GetStoryInput,
    ListArtifactsInput,
    ListArtifactsOutput,
    ListStoriesInput,
    ListStoriesOutput,
    RenderReportInput,
    RenderReportOutput,
    SaveArtifactInput,
    SaveArtifactOutput,
)

__all__ = [
    # base
    "AgentRunId",
    "ArtifactId",
    "ArtifactType",
    "CorrelationId",
    "Format",
    "HttpsUrl",
    "IdempotencyKey",
    "LeaseToken",
    "Perspective",
    "RecordState",
    "RunId",
    "SaveArtifactType",
    "SessionId",
    "SessionState",
    "Sha256",
    "ShortText",
    "StoryId",
    "StrictModel",
    "Text",
    "TurnOutcome",
    "UtcDatetime",
    # errors
    "ErrorBody",
    "ErrorCode",
    "ErrorEnvelope",
    "ToolError",
    # review
    "Finding",
    "ReviewReport",
    "StoryDetail",
    "StorySummary",
    # synthesis (ArtifactRecord intentionally internal)
    "ArtifactReference",
    "ConflictItem",
    "SynthesisReport",
    # facilitator
    "ConversationSummary",
    "DelegationDecision",
    "FacilitatorTurnOutput",
    "FinalizedReview",
    "ResolutionDraft",
    "ResolutionItem",
    # judge
    "JudgeDimensionScore",
    "JudgeIssue",
    "JudgeResult",
    # api
    "CanonicalOperationResult",
    "CanonicalReportResult",
    "CanonicalTurnResult",
    "CreateSessionRequest",
    "CreateSessionResponse",
    "FinalizeRequest",
    "HealthDependency",
    "HealthResponse",
    "ListSessionsQuery",
    "ListSessionsResponse",
    "ListStoriesQuery",
    "ListStoriesResponse",
    "ReportDownload",
    "ReportResponse",
    "SessionDetail",
    "SessionSummary",
    "TurnRequest",
    "TurnResponse",
    "TurnView",
    # records (trusted internal consumers: persistence, orchestration)
    "AgentRunRecord",
    "SessionRecord",
    "StoryRunRecord",
    "TurnLeaseRecord",
    "TurnRecord",
    # mcp
    "GetArtifactInput",
    "GetArtifactOutput",
    "GetStoryInput",
    "ListArtifactsInput",
    "ListArtifactsOutput",
    "ListStoriesInput",
    "ListStoriesOutput",
    "RenderReportInput",
    "RenderReportOutput",
    "SaveArtifactInput",
    "SaveArtifactOutput",
]
