# Tech Stack

## Core decisions

| Area | Decision |
|---|---|
| Language | Python |
| Agent framework | Google ADK |
| Deployment | Agent Engine for the four agents; Cloud Run for MCP services and FastAPI |
| LLM backend | Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=true`) |
| API layer | FastAPI + Pydantic strict schemas |
| Interface | Simple Web UI (minimal chat MVP: story picker with preview, dialogue, report download) calling the FastAPI service. Design change from "TUI first" 2026-09-11 (D16) |
| Tooling | All tools exposed through MCP servers |
| Prompts | UTF-8 static data in `prompts/`, loaded once at startup, never inline code |
| Model configuration | Versioned per agent in `agents/<agent>/config.yaml`; immutable for one deployment |

## Google Cloud / Vertex AI

```env
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=<project_id>
GOOGLE_CLOUD_LOCATION=europe-west4
```

The work sandbox lasts one day. Its daily procedure creates a project, updates
`GOOGLE_CLOUD_PROJECT`, runs bootstrap and migrations, then invokes the independent
deploy manifests.

## Prompt, package, and image boundaries

Canonical agent slugs are `facilitator`, `business-reviewer`,
`engineering-reviewer`, and `synthesis`; their prompt files use the same names. Each
agent's model ID and generation settings live in its versioned `config.yaml`; deployment
environment variables supply infrastructure identifiers, not model behavior. The
separate `judge.md` is evaluation-only and is not an Agent Engine deployment.

Agent deployment scripts stage a root-context build containing the agent source, that
agent's prompt, and the versioned `shared/review_schemas` package before calling
`adk deploy agent_engine`. The deployed runtime uses the absolute
`PROMPTS_DIR=/app/prompts`, fails startup for a missing/non-UTF-8 prompt, and holds the
loaded text/hash immutable per process. `AgentRunRecord` includes the required
`prompt_sha256` audit field along with the deployment git SHA. Each unit's
`requirements.lock` installs the staged shared package at its version pinned for that
image; a schema change bumps the shared package and rebuilds consumers.

Cloud Run builds also use repository-root context. Each service image copies only its
source and the shared package; no image copies dataset content — the story service
fetches the mock dataset from GCS (or reads Azure DevOps) at startup. Complete
path and staging rules are in
`../operations/repository-layout.md`.

## Session and MCP strategy

- Cloud SQL PostgreSQL backs ADK `DatabaseSessionService`
  (`postgresql+asyncpg://...`) and FastAPI audit records. SQLite is unsuitable because
  container disk is ephemeral and unshared. It also satisfies the "full session
  management and persistence" requirement with a DB we manage ourselves; sessions are
  restored by session ID from Postgres.
- MCP servers are independent Cloud Run Streamable-HTTP services: `story`, `artifact`,
  and `report`.
- **Dual consumption pattern (key design point)**: the **facilitator** can call story
  and artifact MCP tools through ADK `McpToolset` (read-only) when the LLM requests
  supporting evidence; **FastAPI orchestration** calls all MCP servers directly via
  the `mcp` SDK client (`ClientSession.call_tool`) for deterministic reads, artifact
  persistence, and report generation. The facilitator never invokes another agent —
  all agent invocations are owned by FastAPI (see pattern-decisions.md).
- Artifact delivery uses GCS references and FastAPI-issued expiring signed URLs.

## Container and local-development decision

| Target | Method |
|---|---|
| Agents → Agent Engine | staged root-context source passed to `adk deploy agent_engine`; no custom Agent Engine Dockerfile |
| MCP/FastAPI → Cloud Run | per-service Dockerfile built with repository-root context and deployed by its script |
| Local evaluation | Compose runs local ADK adapters, PostgreSQL substitute, and GCS-compatible substitute; Vertex AI is external |

Compose does not run Agent Engine. It uses the adapters in
`deploy/compose/adapters/` so the local interfaces match the separately deployed
agents.

## CI/CD (Azure DevOps)

One pipeline exists for each deployable unit: four `agents-*.yml` files and four
`services-*.yml` files under `pipelines/`. Their exact names and include-path filters are
specified in [repository-layout.md](../operations/repository-layout.md); all deploy to `dev`, not staging. A unit change
does not redeploy runtime-discovered peers; an optional combined run is available via
pipeline trigger / checkbox parameter. Prompt/model/agent-code changes also invoke
`evaluation.yml`; a `judge.md`-only change invokes evaluation only.

Pipelines authenticate to GCP via a service-account key stored in Azure Pipeline
secret variables and deploy with a dedicated least-privilege GCP deployment service
account. Cloud Run images go to Google Artifact Registry. The normal flow
is test → build where applicable → deploy-dev → smoke; evaluation results are retained
as artifacts. Production is deferred behind manual approval. The authoritative
pipeline-stage definitions are in `../operations/deployment.md`.

**Azure Artifacts**: optional, only if we publish an internal Python package (e.g. the
shared schema library) — otherwise not used.

## Requirement mapping

| Requirement | Covered by |
|---|---|
| Deploy to Agent Engine | independently staged ADK deployment of all four agents |
| MCP on Cloud Run | independently deployed MCP services |
| Session management & persistence | ADK sessions + Cloud SQL PostgreSQL |
| Observability and versioning | Cloud logging/tracing, git labels, prompt SHA-256 audit |
| Callbacks | delegation & loop-event callbacks |
| Conversation-length monitoring | callback in the facilitator agent |
| Agent versioning | new versioned Agent Engine resource per release (git-tagged, N-1 retained) + env-pointer switching |
| Local evaluation | Compose adapters with local PostgreSQL/GCS substitutes |

Implementation details for callbacks, observability, and conversation-length
monitoring are specified in [observability.md](../design/observability.md);
evaluation-test details are in
[evaluation-tests.md](../quality/evaluation-tests.md).
