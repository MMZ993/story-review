# Story Review — Parallel Business & Engineering Review Team

Demo project; created for learing and exploration purposes; deployed on GCP

A multi-agent system that reviews user stories from
**business** and **engineering** perspectives in parallel, synthesizes the findings,
and resolves remaining conflicts with the Product Owner in the loop through a
conversational facilitator.

## Live demo

**https://story-review.mmz.sh**

> Note: the demo runs on a private trial Google Cloud account and may be turned off
> at any time — either the whole page or the backing database (Cloud SQL) can go
> down without notice.

## Architecture (high level)

Two layers: a **conversation layer** (facilitator ↔ Product Owner) and an
**execution layer** (reviewer agents + MCP services). A FastAPI orchestration
service wires them together and performs all deterministic steps (fan-out,
persistence) without LLM involvement.

```
┌─────────┐    ┌────────────────────────────────────┐
│ Web UI  │──▶│ FastAPI orchestration (Cloud Run)  │
└─────────┘    │  sessions, fan-out, MCP calls      │
               └───┬──────────┬──────────┬──────────┘
                   │          │          │
           ┌───────▼───┐ ┌────▼─────┐ ┌──▼──────────────────────┐
           │Facilitator│ │Reviewers │ │ MCP servers (Cloud Run) │
           │ (Agent    │ │+ Synth.  │ │ story / artifact /      │
           │  Engine)  │ │(Agent    │ │ report                  │
           └───────────┘ │ Engine)  │ └──────┬──────────────────┘
                         └──────────┘        │
                                   Cloud SQL │ GCS
```

Flow in brief:

1. PO selects a story in the Web UI → orchestration (FastAPI service) invokes **Business** and
   **Engineering Reviewer** agents in parallel (Agent Engine deployments).
2. Reviewer outputs are persisted as artifacts via **MCP servers**; the
   **Synthesis** agent merges them and detects conflicts.
3. The **Facilitator** agent opens a User-in-the-Loop dialogue with the PO; it can
   decide (LLM-driven delegation) to re-run reviews with extra PO context.
4. On readiness the finalized review is persisted and a Markdown/PDF report is
   rendered deterministically by the report MCP server.

## Design in brief

- **Everything is persisted and auditable.** Agent conversation sessions (ADK
  `DatabaseSessionService`) and agent-run audit records live in **Cloud SQL**
  (PostgreSQL); every review artifact — reviewer outputs, synthesis, dialogue
  resolutions, the finalized review — is stored in a **Cloud Storage** bucket and
  referenced by lineage-scoped IDs. The report is rendered from the persisted
  `FinalizedReview` artifact, never regenerated from memory.
- **Stateless server, stateful sessions.** The client holds the session ID;
  the server resumes sessions from Cloud SQL. Sessions have an explicit
  lifecycle (active → parked/finalizing → completed) and are retained whole.
- **Deterministic core, LLM at the edges.** All orchestration logic (parallel
  fan-out, artifact persistence, gates, finalization) is plain code; LLM
  reasoning is confined to the four agents. Agents are isolated deployments —
  no shared memory, all context passes explicitly.
- **Google Cloud services used:** Cloud Run (orchestration, Web UI backend,
  three MCP servers), Vertex AI Agent Engine (four per-agent deployments,
  Gemini models), Cloud SQL (PostgreSQL sessions + audit), Cloud Storage
  (artifacts and rendered reports), Secret Manager, Artifact Registry,
  Cloud Monitoring / Logging, IAM with per-service service accounts and
  ID-token-authenticated service-to-service calls.
- **AI-first SDLC.** The whole project — design docs, code, tests, prompts,
  infrastructure, and runbooks — was developed with an AI coding agent working
  from an authoritative docs-first design set, with an LLM-as-judge regression
  suite gating prompt and agent changes. Full traceability: the git history of
  the handoff file doubles as a session log, and every LLM decision and executed
  action is recorded in decision records and runbooks (`docs-local/`).

## Documentation

- Design (authoritative): [`docs/`](docs/index.md)
- Home-phase development (local decisions, runbooks): [`docs-local/`](docs-local/index.md)
- Current state: [`.agents/HANDOFF.md`](.agents/HANDOFF.md)
