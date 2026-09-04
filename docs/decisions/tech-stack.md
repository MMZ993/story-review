# Tech Stack

## Core Decisions

| Area | Decision |
|---|---|
| Language | Python |
| Agent framework | Google ADK (Agent Development Kit) |
| Deployment | Google Cloud: **Agent Engine** for agents, **Cloud Run** for MCP servers |
| LLM backend | Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=true`) |
| API layer | FastAPI + **Pydantic** — strict schemas everywhere (agent I/O, delegation decisions, MCP contracts) |
| Interface | TUI (preferred) — terminal chat with the Interaction Facilitator |
| Tooling | All tools exposed via MCP servers |
| Prompts | **Prompts are static data, not code** — kept in a separate `prompts/` directory, one file per agent; loaded at runtime, versioned in git; easy to edit and iterate without touching logic |

## Google Cloud / Vertex AI

Environment variables (single shared Vertex AI connection reused by all agents):

```env
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=<project_id>  # daily-created in work sandbox; stable on trial/permanent account
GOOGLE_CLOUD_LOCATION=europe-west4
```

## environment

**1 day sandbox** — 1-day lifetime; daily procedure: create new project, update `GOOGLE_CLOUD_PROJECT`, re-run `gcloud init` / auth.

## Models

- Models set as variable changed in code and applied on deployment time

## Session

- Cloud SQL (PostgreSQL) as session DB, via ADK `DatabaseSessionService` (`postgresql+asyncpg://...`).
- Why not SQLite: its file lives on ephemeral container disk — lost on restart/scale, not shareable between replicas.
- Also satisfies "full session management and persistence" requirement with a DB we manage ourselves.
- Restore a previous session (conversation history) by session ID from Postgres.

## MCP Strategy

- All tools are exposed via MCP servers — no plain function tools.
- Purpose-scoped servers, each deployed separately on **Cloud Run** over Streamable HTTP:
  - **story server** — story details and roadmap/epic context; attached to the facilitator through ADK `McpToolset`,
  - **artifact server** — saves/retrieves permanent review and synthesis artifacts; attached read-only to the facilitator through ADK `McpToolset`,
  - **report server** — renders final reports (Markdown/PDF) as artifacts; called directly by FastAPI, not attached to an agent.
- Dual consumption pattern (key design point):
  - the **facilitator** can call story and artifact MCP tools through `McpToolset` when the LLM requests supporting evidence,
  - **FastAPI orchestration** calls MCP servers directly via the `mcp` SDK client (`ClientSession.call_tool`) for deterministic reads, artifact persistence, and report generation.
- Artifact delivery: MCP tools save files through `GcsArtifactService`. For a final report, Report MCP returns the persisted GCS artifact reference to FastAPI; FastAPI generates an expiring signed URL, and the UI downloads the PDF/MD directly from GCS.

## Interface

**TUI** — simple terminal client (built first)
**Web UI** — simple web interface later if needed (same FastAPI backend)

- same fastAPI backend for both interfaces
- conversational loop with the Interaction Facilitator (User-in-the-Loop),
- renders the synthesized review report and flagged conflicts,
- save report as a md/pdf file

## Container / Docker Decision

Two different container paths — one per deployment target:

| Target | Method | Container |
|---|---|---|
| Agents → Agent Engine | `adk deploy agent_engine` (standard path) | ADK builds the container from source + `requirements.txt`; no Dockerfile needed |
| MCP servers → Cloud Run | own **Dockerfile** (per server), pushed to Artifact Registry | Standard Python container with FastAPI/`mcp` server, exposed via Streamable HTTP |

Rationale: `adk deploy` is the least-friction, Google-managed path for agents (and keeps agent versioning trivial via separate deployments); MCP servers on Cloud Run are ordinary services where a Dockerfile gives full control. We do **not** use the custom-container (BYOC) path on Agent Engine — nothing in the project needs it.

## CI/CD (Azure DevOps)

- **Repo & pipelines**: Azure DevOps repo + Azure Pipelines for all builds and deployments.
- **Container registry**: **Google Artifact Registry** (not Azure Container Registry).
- **Pipelines**: de-coupled — separate pipelines for MCP servers and agents (no redeploy of the other side needed; MCP tools are discovered at runtime). Each ends with contract/integration smoke tests against staging. Optional combined run via pipeline trigger / checkbox parameter.
- **Pipeline stages** (proposed):
  1. `lint & test` — ruff/pytest, agent evaluation tests,
  2. `build` — build MCP server images, push to Artifact Registry (tagged with build number),
  3. `deploy-staging` — Cloud Run + Agent Engine deployments (also serves agent versioning proof),
  4. `deploy-prod` — optional, manual approval gate; only after the agent reaches end-of-development/go-live.
- **Azure Artifacts**: optional, only if we publish an internal Python package (e.g. shared client library) — otherwise not used.

## FastAPI Role

FastAPI acts as the entry service layer in front of Agent Engine deployments:

- wraps agent sessions / facilitator endpoints,
- serves the interface (TUI calls it; a web UI would too),
- health and observability endpoints.

## Requirement Mapping

| Requirement | Covered by |
|---|---|
| Deploy to Agent Engine | ADK deployment of all agents |
| MCP on Cloud Run | custom MCP servers on Cloud Run |
| Session management & persistence | ADK sessions + Cloud SQL PostgreSQL (`DatabaseSessionService`) |
| Observability | Cloud Logging / tracing on Agent Engine + FastAPI metrics |
| Conversation-length monitoring | callback in facilitator agent |
| Callbacks | delegation & loop-event callbacks |
| Agent versioning | multiple Agent Engine deployments per agent version + git tags |

Implementation details for callbacks, observability, conversation-length monitoring, and agent evaluation tests are specified in the architecture document, not here.
