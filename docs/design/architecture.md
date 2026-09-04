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
| Artifact MCP server | Cloud Run | save/list/read permanent review artifacts |
| Report MCP server | Cloud Run | render Markdown/PDF reports as artifacts |
| Cloud SQL (PostgreSQL) | Cloud SQL | ADK session store (`DatabaseSessionService`) |
| GCS bucket | Cloud Storage | artifact storage (`GcsArtifactService`) + report files |

## Deployment Model (per-agent deployments)

Each agent is deployed as a **separate Agent Engine resource** (`adk deploy agent_engine`,
one deployment per agent directory). Consequences:

- **Versioning proof**: each agent redeployed independently with version labels; git tags
  map 1:1 to deployed versions.
- **Explicit invocation**: facilitator/orchestration calls reviewer and synthesis
  deployments through the Vertex AI Agent Engine client SDK — agents do not share memory
  by construction; all context passes explicitly.
- **Independent pipelines**: an agent update touches exactly one Agent Engine resource.

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
   only, engineering only, both, or none — and with what extra PO context.
7. Orchestration executes the requested re-review (back to step 2) or continues the
   dialogue. Loop repeats until the explicit readiness exit condition: **all flagged
   issues resolved or PO accepts**.
8. On readiness: final report rendered via report MCP server, delivered to UI as MD/PDF.

Pattern mapping:
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
- **Session lifecycle**: the client can list previous sessions, restore one, re-read its
  history and continue. A session can be marked **completed** — then it is returned
  read-only, with an option to start a **new session on the same story** (e.g. the story
  was updated in the meantime). Retention of old sessions (all, or last X) is handled by
  a separate housekeeping process — to be decided.
- **Timeouts apply to LLM/agent calls, never to the PO** — there is no timeout on waiting
  for the user's answer; the PO takes as long as needed and the session resumes on the
  next client message. Client–server communication details are resolved later.
- **Execution state** (review results, synthesis reports): permanent artifacts in GCS via
  the artifact MCP server — reachable by agents as context for later reviews.
- **Delegation intent**: facilitator returns a structured decision (which agents, extra
  context) that orchestration interprets — the LLM proposes, code disposes.

## Interfaces

- TUI/Web ↔ FastAPI: HTTP (JSON events for dialogue turns; file download for artifacts).
- FastAPI ↔ Agent Engine: Vertex AI Agent Engine client SDK (session-scoped calls).
- Agents ↔ MCP servers: ADK `McpToolset` over Streamable HTTP.
- FastAPI ↔ MCP servers: `mcp` SDK client over Streamable HTTP (direct, no LLM).
- FastAPI ↔ artifacts: `GcsArtifactService` / signed URLs for UI downloads.

## Security

- Service-account based auth: FastAPI → Agent Engine, FastAPI → Cloud Run MCP,
  agents → MCP servers (ingress restricted to service accounts, no public unauthenticated
  access except the FastAPI frontend if required for demo).
- No secrets in code or docs; all identifiers via environment variables.

Resolved design points:

- Structured delegation output: strict Pydantic schema — fields and semantics in
  `agents.md`.
- Retries/timeouts and error handling: shared instrumented client wrapper — policy in
  `observability.md`.
