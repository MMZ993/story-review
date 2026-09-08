# MCP Servers

Three purpose-scoped MCP servers, each a separate Cloud Run service speaking MCP over
Streamable HTTP. All tool inputs, successful outputs, and failures are exactly the
strict Pydantic models in [schemas.md](schemas.md); successful calls return their named
output model, failures return `ToolError` (`ErrorBody`). No tool accepts unknown
fields. Consumers: the facilitator agent (story + artifact servers, read tools only,
via ADK `McpToolset`) and FastAPI orchestration (all three, via direct `mcp` SDK
client — deterministic, no LLM).

## Story server

Serves the mock backlog (data store). Read-only; no agent state involved. Designated as
the simple MCP server fulfilling the technical requirement.

| Tool | Input | Output | Authorized callers |
|---|---|---|---|
| `list_stories` | `ListStoriesInput` | `ListStoriesOutput` | orchestration, facilitator |
| `get_story` | `GetStoryInput` | `StoryDetail` | orchestration, facilitator |

- Backed by the mock dataset (see `../quality/mock-data.md`); expected outcomes are
  **not** exposed through this server.
- `get_story` returns the full `StoryDetail`, including `comments` and
  `context_stories` when the story has them (both default empty — dataset
  stories without them are unaffected). No truncation or summarization in v1;
  the schema list caps (50 comments, 5 context stories) are the only limits.
- `list_stories` lists test-case stories only — context-only stories
  (referenced solely as `context_stories` of a main story) do not appear in
  the list; they are reachable only through `get_story` of the main story
  (or directly by id).
- No writes; versioned with the dataset.

## Artifact server

Persistent store for story snapshots, review artifacts, synthesis reports, and the
finalized-review artifact (GCS via `GcsArtifactService`). This is where "permanent
artifacts" live — written deterministically by orchestration, read by the facilitator
as LLM-driven extra context.

| Tool | Input | Output | Authorized callers |
|---|---|---|---|
| `save_artifact` | `SaveArtifactInput` | `SaveArtifactOutput` | orchestration only |
| `get_artifact` | `GetArtifactInput` | `GetArtifactOutput` | orchestration, facilitator (read-only) |
| `list_artifacts` | `ListArtifactsInput` | `ListArtifactsOutput` | orchestration, facilitator (read-only) |

Key rules:

- **Lineage scoping**: every artifact belongs to exactly one story run (session
  lineage); lookups never cross runs. The server validates the
  reference-to-run relationship; it does not trust an agent-supplied ID outside the
  caller's own run.
- **Idempotency**: `save_artifact` is keyed uniquely per
  `(story_run_id, type, idempotency_key)`. A retried save returns the existing
  reference with `created = false`; reusing the same key with **different canonical
  content** returns `IDEMPOTENCY_KEY_REUSED` instead of silently duplicating.
- **Immutability**: artifacts are never modified; a re-review creates a new version.
  `list_artifacts` orders deterministically by `(type, perspective, version)` with
  `limit`/`offset` pagination and flags `is_latest` per type/perspective; the caller
  derives "latest" as the maximum `version` (see schemas.md §1).
- **Finalized review**: immediately before report rendering, orchestration saves one
  deterministic `finalized-review` artifact — the latest synthesis reference, dialogue
  resolutions, remaining issues, and the explicit PO acceptance state.
- Facilitator access is **read-only** (`get_artifact` / `list_artifacts` with
  orchestration-supplied, lineage-scoped references only).
- Artifact records carry the internal GCS URI; tools expose only `ArtifactReference`,
  never the raw storage location for download.

## Report server

Renders final reports. Called only by FastAPI (deterministic finalization, flow 3) —
not attached to any agent.

| Tool | Input | Output | Authorized callers |
|---|---|---|---|
| `render_report` | `RenderReportInput` | `RenderReportOutput` | orchestration only |

- Requires exactly one same-run `finalized-review` artifact reference; content (MD/PDF)
  is rendered deterministically from that artifact — no LLM in this server.
- Idempotent per `(story_run_id, format)`: a retry returns the existing reference with
  `created = false`; reusing that identity with a different finalized-review reference
  is an idempotency conflict.

## Cross-cutting

| Concern | Approach |
|---|---|
| Transport | MCP Streamable HTTP |
| Deployment | one Cloud Run service per server, own Dockerfile, own pipeline |
| Auth | service-account-only ingress; no public unauthenticated access |
| Authorization | per-tool caller allowlist (tables above); save/report tools are orchestration-only |
| Schemas | shared Pydantic models (single source, reused by agents, orchestration, tests) |
| Errors | `ToolError(ErrorBody)` — structured error taxonomy (error code, retryable flag) per [observability.md](observability.md); stable codes include `UNAUTHENTICATED`, `FORBIDDEN`, `VALIDATION_ERROR`, `ARTIFACT_NOT_FOUND`, `IDEMPOTENCY_KEY_REUSED`, `RENDER_FAILED`; retry hints only where a retry is safe |
| Timeouts/retries | client-side, per the shared instrumented wrapper — servers stay stateless |
| Observability | every tool call logged + traced with correlation ID |

Signed download URLs for reports are generated by **FastAPI** from GCS references — the
report server never issues URLs.
