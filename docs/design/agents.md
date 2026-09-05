# Agents

Per-agent specifications. Each agent is a separate Agent Engine deployment.

## Interaction Facilitator (orchestrator, conversation layer)

- **Role**: User-in-the-Loop dialogue with the Product Owner; presents synthesized
  feedback, guides clarification, tracks story readiness.
- **Model config**: model ID and generation settings are versioned in the agent's
  `config.yaml` and immutable for one deployment; environment variables supply only
  infrastructure identifiers (see `../decisions/tech-stack.md`).
- **Tools**: story MCP server (read), artifact MCP server (read previous review artifacts
  as extra context). For artifact reads, orchestration supplies lineage-scoped references;
  the facilitator decides whether supporting evidence is needed and performs the read as
  an LLM-driven MCP tool call. No report tools — final report generation is deterministic
  and owned by orchestration (see data-flow.md).
- **Structured output**: every facilitator turn ends with a **delegation decision** — a
  strict Pydantic model (see below). Orchestration interprets and executes it; the LLM
  proposes, code disposes. Validation failure triggers a corrective LLM re-prompt
  (bounded, distinct from transport retries — see observability.md) and is recorded as
  an observability event. The opening turn always emits `invoke` = none.
- **PO acceptance** is an explicit client action (UI button / API field `po_accepted`),
  recorded by orchestration — never produced by the LLM. It bypasses the facilitator and
  delegated work and enters final report generation immediately.

### Delegation decision schema (fields)

Authoritative model: `DelegationDecision` in [schemas.md](schemas.md) — the prose
below is a summary; the Pydantic validators reject invalid combinations such as
`reuse_previous=true` with a reviewer invocation.

| Field | Meaning |
|---|---|
| `invoke` | which reviewers to run: business, engineering, both, or none |
| `extra_context` | PO clarifications to inject into the invoked reviewers |
| `reuse_previous` | `true` = re-synthesis only, using existing latest artifacts per perspective (`invoke` must be `none` and `extra_context` absent); `false` (default) = run invoked reviewers, pair each new artifact with the latest artifact of the other perspective. A re-synthesis turn always continues so the facilitator can evaluate the new output on the next turn. |
| `open_issues` | currently unresolved issues |
| `readiness` | `needs_work` / `review_requested` / `ready` |

Loop exit condition: all flagged issues resolved, or the PO explicitly accepts. The
facilitator's `readiness = ready` is a **proposal only**. Orchestration finalizes a normal
dialogue turn only when `open_issues` is empty, `invoke` = none, and no synthesis was
produced during that turn. A new synthesis must be evaluated by the facilitator on the
next turn. Explicit PO acceptance finalizes before invoking the facilitator. Turn 10
parks the session instead of evaluating readiness.

## Business Perspective Reviewer (execution layer)

- **Role**: story clarity, user value, business justification; epic/roadmap alignment;
  business-view gaps in acceptance criteria.
- **Input**: story artifact + optional previous review + optional PO extra context
  (assembled by orchestration; see session semantics below).
- **Output**: structured review (Pydantic-validated) persisted as artifact by
  orchestration (direct MCP call — the reviewer itself has no tools and does not write
  artifacts).
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
- **Output**: synthesis report (Pydantic-validated) persisted as artifact by
  orchestration.
- **Tools**: none — all context is passed in.

## Session and invocation semantics

- **Facilitator**: persistent conversation session (Cloud SQL) — the PO dialogue spans
  many turns. Session events are owned by orchestration: after a successful facilitator
  response, FastAPI appends the turn (reply + `DelegationDecision`) to the session
  context keyed by the durable turn ID (unique constraint), so an ambiguous-timeout
  retry can never duplicate dialogue events. Before reinvoking the facilitator after a
  timeout, orchestration checks the session for an event carrying that turn's invocation
  ID and retrieves the existing result instead of invoking again — only genuinely
  missing work is retried (this may still repeat model cost, never state).
- **Reviewers and Synthesis**: always a **fresh single-turn run** — no session state
  carried between invocations. The input is fully assembled by orchestration:
  1. story artifact (persisted once by FastAPI at story selection),
  2. optionally the previous review result (for consecutive reviews),
  3. optionally new information provided by the PO during the dialogue.
- All sessions (including single-turn reviewer runs) are **kept and logged** for audit
  and observability. Each logged invocation carries the agent version label and prompt
  SHA-256 (see schemas.md); retries use idempotent output persistence so a timed-out
  invocation never produces duplicate artifacts.

## Shared contracts

- All inter-agent and agent→orchestration payloads are strict Pydantic models; no free
  prose is parsed programmatically.
- Review and synthesis schemas are defined once and shared between agents and tests.
