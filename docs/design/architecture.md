# Architecture

## Overview

Two-layer system: a **conversation layer** where the Interaction Facilitator talks to the
Product Owner, and an **execution layer** of independently deployed review agents and MCP
services. Orchestration code (Python, inside FastAPI) wires the layers together and performs
deterministic calls (parallel fan-out, artifact persistence) without LLM involvement.

```
┌─────────┐    ┌──────────────────────────────────────────────┐
│ TUI/Web │──▶│ FastAPI orchestration service (Cloud Run)    │
└─────────┘    │  - session mgmt, artifact delivery to UI     │
               │  - parallel reviewer invocation (async)      │
               │  - direct MCP client calls (no LLM)          │
               └───────┬───────────────┬──────────────┬───────┘
                       │               │              │
                       │ Agent Engine  │ Agent Engine │ MCP (Streamable HTTP)
                       │               │              │
               ┌───────▼──────┐ ┌──────▼───────┐ ┌────▼─────────────────────┐
               │ Facilitator  │ │ Reviewers    │ │ MCP servers (Cloud Run)  │
               │ (Agent Eng.) │ │ + Synthesis  │ │ story / artifact / report│
               └──────────────┘ │ (Agent Eng.) │ └──────────┬───────────────┘
                                └──────────────┘            │
                                                  Cloud SQL │ GCS artifacts
```

## Components

| Component | Runtime | Role |
|---|---|---|
| TUI / Web UI | client | PO dialogue, report display, PDF/MD download |
| FastAPI orchestration | Cloud Run | entry point; session handling; parallel fan-out; direct MCP calls; artifact delivery |
| Facilitator agent | Agent Engine (own deployment) | User-in-the-Loop dialogue, LLM-driven delegation decisions, readiness tracking |
| Business Reviewer | Agent Engine (own deployment) | business-perspective story analysis |
| Engineering Reviewer | Agent Engine (own deployment) | technical-perspective story analysis |
| Synthesis & Conflict Resolver | Agent Engine (own deployment) | merges reviewer outputs, detects conflicts |
| Story MCP server | Cloud Run | backlog access (mock data store): list available/loaded stories, story details, epic/roadmap context |
| Artifact MCP server | Cloud Run | save/list/read permanent review artifacts (incl. the finalized-review artifact) |
| Report MCP server | Cloud Run | deterministically render Markdown/PDF reports from the finalized-review artifact |
| Cloud SQL (PostgreSQL) | Cloud SQL | ADK session store (`DatabaseSessionService`), session lifecycle, and agent-run audit records |
| GCS bucket | Cloud Storage | artifact storage (`GcsArtifactService`) + report files |

## Deployment Model (per-agent deployments)

Each agent is deployed as a **separate Agent Engine resource** (`adk deploy agent_engine`,
one deployment per agent directory). Its deploy script stages the agent source, prompt,
and shared schemas into a self-contained build context before deployment (see
`../operations/repository-layout.md`). Consequences:

- **Versioning proof**: each agent redeployed independently with version labels; git tags
  map 1:1 to deployed versions.
- **Explicit invocation**: FastAPI orchestration exclusively calls reviewer, synthesis,
  and facilitator deployments through the Vertex AI Agent Engine client SDK. The
  facilitator emits structured delegation decisions but never calls another agent;
  agents do not share memory and all context passes explicitly.
- **Independent pipelines**: an agent release creates exactly one new versioned Agent
  Engine resource; the orchestration env pointer switches to it after its smoke test,
  and prior-version resources are retained for rollback (see
  `../operations/deployment.md`).

## Orchestration and Control Flow

1. PO lists/loads a story in the TUI/Web UI (story MCP server reads from the backlog — a
   mock data store for the capstone); selecting a story **triggers the initial flow**.
2. Orchestration (FastAPI) invokes Business + Engineering Reviewer deployments **in
   parallel** (`asyncio.gather`) — deterministic fan-out, no LLM decides this step.
3. Reviewer outputs are persisted as artifacts via **direct MCP client calls** (no LLM).
4. Orchestration invokes the Synthesis deployment with both review artifacts; the
   synthesized report is persisted as an artifact.
5. The **Facilitator agent** receives the synthesis summary as context and opens the
   User-in-the-Loop dialogue with the PO.
6. Facilitator decides (LLM-driven delegation) whether a re-review is needed — business
   only, engineering only, both, or none — and with what extra PO context. It can use its
   MCP tools to retrieve supporting evidence through orchestration-supplied,
   lineage-scoped references.
7. Orchestration executes the requested re-review and re-synthesis or continues the
   dialogue. Any turn that produces synthesis must continue so the facilitator evaluates
   the new output on the next turn. A normal turn finalizes only when no issues remain and
   no work was requested; explicit PO acceptance bypasses facilitator/delegated work.
8. On readiness, orchestration first persists a deterministic **`FinalizedReview`
   artifact** — the latest synthesis combined with the dialogue resolutions and the PO
   acceptance state — via the artifact MCP server. The report MCP server then renders
   the final MD/PDF report **from that artifact** before the turn's single response.
   Turn 10 parks the session instead of evaluating readiness.

Pattern mapping:
- **Pattern 1**: orchestration explicitly invokes the separately deployed agents
  (Agent Engine client SDK) in sequence inside the loop.
- **Pattern 2**: steps 2–5 form the sequential base with parallel fan-out; steps 5–7 form
  the loop.
- **Pattern 3**: facilitator performs LLM-driven delegation (step 6) inside a
  User-in-the-Loop conversation; the invoked reviewer→synthesis chain is the simple
  sequential part of the hierarchy.

## Session and State

- **Conversation sessions** (facilitator ↔ PO): ADK sessions persisted in Cloud SQL
  PostgreSQL. The **server is stateless** — the client (TUI/Web) holds the session ID
  and every interaction resumes the session server-side with a new prompt. The session
  ID is generated at the start and persisted on the client side.
- **Session lifecycle**: session states are `active`, `parked`, `finalizing`, and
  `completed`. The client can list sessions and restore their history. Active sessions
  can continue; parked and completed sessions are read-only, with an option to start a
  **new session on the same story**. Reading a completed session can regenerate an
  expiring URL for its persisted report without changing session state. A retryable
  report failure leaves a session in `finalizing` so the idempotent finalization
  request can be retried; the retry atomically reacquires the session turn lease
  before rendering. A non-retryable finalization failure rolls the session back to
  `active` so it is never permanently stuck (see data-flow.md §3). Retention of old sessions (all, or
  last X) is handled by a separate housekeeping process — to be decided.
- **Timeouts apply to active request processing, never to the PO** — there is no timeout
  while waiting for the user's next message. A PO turn has a hard five-minute deadline;
  per-call retry limits are maxima and are clamped to the remaining request budget.
- **Execution state** (review results, synthesis reports): permanent artifacts in GCS via
  the artifact MCP server — reachable by agents as context for later reviews.
- **Delegation intent**: facilitator returns a structured decision (which agents, extra
  context) that orchestration interprets — the LLM proposes, code disposes.

## Interfaces

- TUI/Web ↔ FastAPI: HTTP (JSON events for dialogue turns; file download for artifacts).
- FastAPI ↔ Agent Engine: Vertex AI Agent Engine client SDK (session-scoped calls).
- Facilitator ↔ story/artifact MCP servers: ADK `McpToolset` over Streamable HTTP.
- FastAPI ↔ MCP servers: `mcp` SDK client over Streamable HTTP (direct, no LLM).
- FastAPI generates expiring signed URLs from final-report GCS references; the UI uses
  those URLs to download directly from GCS.

## Security

- Service-account based auth: FastAPI → Agent Engine, FastAPI → Cloud Run MCP,
  agents → MCP servers (ingress restricted to service accounts, no public unauthenticated
  access except the FastAPI frontend if required for demo).
- No secrets in code or docs; all identifiers via environment variables.

Resolved design points:

- Structured delegation output: strict Pydantic schema — fields and semantics in
  [agents.md](agents.md).
- Retries/timeouts and error handling: shared instrumented client wrapper — policy in
  [observability.md](observability.md).
