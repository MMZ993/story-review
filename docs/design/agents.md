# Agents

Per-agent specifications. Each agent is a separate Agent Engine deployment.

## Interaction Facilitator (orchestrator, conversation layer)

- **Role**: User-in-the-Loop dialogue with the Product Owner; presents synthesized
  feedback, guides clarification, tracks story readiness.
- **Model config**: set via environment at deployment time (see tech-stack).
- **Tools**: story MCP server (read), artifact MCP server (read previous review artifacts
  as extra context), report MCP server (trigger final report).
- **Structured output**: every facilitator turn ends with a **delegation decision** — a
  strict Pydantic model (see below). Orchestration interprets and executes it; the LLM
  proposes, code disposes. Validation failure triggers a corrective retry and is recorded
  as an observability event.

### Delegation decision schema (fields)

| Field | Meaning |
|---|---|
| `invoke` | which reviewers to run: business, engineering, both, or none |
| `extra_context` | PO clarifications to inject into the invoked reviewers |
| `reuse_previous` | build re-synthesis on previous artifacts vs. fresh full review |
| `open_issues` | currently unresolved issues |
| `readiness` | `needs_work` / `review_requested` / `ready` |

Loop exit condition: all flagged issues resolved, or PO explicitly accepts.

## Business Perspective Reviewer (execution layer)

- **Role**: story clarity, user value, business justification; epic/roadmap alignment;
  business-view gaps in acceptance criteria.
- **Input**: story artifact + optional previous review + optional PO extra context
  (assembled by orchestration; see session semantics below).
- **Output**: structured review (Pydantic-validated) persisted as artifact by
  orchestration (direct MCP call — the reviewer itself does not write artifacts).
- **Tools**: none — all context is passed in; no MCP toolsets attached.

## Engineering Perspective Reviewer (execution layer)

- **Role**: technical completeness, missing system behaviors, edge cases, dependencies,
  risks, unknowns, architectural impact.
- **Input/output/tools**: same contract as the Business Reviewer (different perspective).

## Synthesis & Conflict Resolver (execution layer)

- **Role**: merges both review artifacts, detects business/technical contradictions,
  organizes a unified report, flags items requiring PO clarification.
- **Input**: always **the two latest artifacts — one per perspective**. First run uses
  the initial business + engineering reviews; after a single-perspective re-review,
  orchestration pairs the new artifact with the **latest artifact of the other
  perspective**. This catches cases where resolving one conflict creates a new conflict
  or gap on the other side.
- **Output**: synthesis report (Pydantic-validated) persisted as artifact.
- **Tools**: none — all context is passed in.

## Session and invocation semantics

- **Facilitator**: persistent conversation session (Cloud SQL) — the PO dialogue spans
  many turns.
- **Reviewers and Synthesis**: always a **fresh single-turn run** — no session state
  carried between invocations. The input is fully assembled by orchestration:
  1. story artifact (persisted once at story selection on the orchestration level),
  2. optionally the previous review result (for consecutive reviews),
  3. optionally new information provided by the PO during the dialogue.
- All sessions (including single-turn reviewer runs) are **kept and logged** for audit
  and observability.

## Shared contracts

- All inter-agent and agent→orchestration payloads are strict Pydantic models; no free
  prose is parsed programmatically.
- Review and synthesis schemas are defined once and shared between agents and tests.
