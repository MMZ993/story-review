# Pattern Decisions

## Decision

We implement a single workflow that fulfills **all three required patterns**: Pattern 1
and Pattern 2 by the core pipeline, Pattern 3 by the facilitator's delegation behavior.

## Architecture Overview

Two-layer design:

1. **Orchestration layer** — Interaction Facilitator agent in a dialogue loop with the Product Owner, holding session context across the whole story lifecycle.
2. **Execution layer** — the review pipeline: Business Reviewer + Engineering Reviewer in parallel, followed by the Synthesis & Conflict Resolver.

The facilitator invokes the execution layer dynamically, based on the PO conversation.

## Pattern 1 Fulfillment (via per-agent deployments)

| Requirement | How we fulfill it |
|---|---|
| Sequential | Reviewers → Synthesis → Facilitator chain across separately deployed agents |
| Loop agent | Facilitator ↔ PO dialogue iterates until the story reaches an explicit "ready" exit condition |
| Explicit Invocation of separately deployed agents | Each agent is its own Agent Engine deployment; the **orchestration layer** invokes them via the Agent Engine client SDK — no shared memory, all context passed explicitly |

> **Design decision (interview position)**: invocation is owned by the deterministic
> orchestration layer (application layer), not by one agent calling another. This keeps
> agents decoupled, independently deployable and testable; the facilitator agent still
> performs LLM-driven delegation (Pattern 3) by emitting the structured decision that
> orchestration executes. We consider explicit invocation from a well-defined app layer
> a stronger realization of the pattern than agent-to-agent coupling.

## Pattern 2 Fulfillment (primary)

| Requirement | How we fulfill it |
|---|---|
| Sequential | Reviewers → Synthesis → Facilitator base pipeline |
| Parallel agent use | Business and Engineering Reviewers run independently on the same story |
| Loop agent | Facilitator ↔ PO dialogue iterates until the story reaches an explicit "ready" exit condition |

## Pattern 3 Fulfillment (bonus)

| Requirement | How we fulfill it |
|---|---|
| LLM-Driven Delegation | Facilitator decides per iteration whether to invoke the business review, technical review, both, or neither — enriched with extra context from the PO dialogue. The routing decision must come from actual LLM reasoning, not hardcoded rules. |
| User-in-the-Loop | The PO clarification dialogue with the facilitator |
| Simple sequential agents in the hierarchy | Reviewer(s) → Synthesis chain invoked from the orchestration layer |

## Delegation Behavior

- Facilitator may invoke the whole pipeline or only part of it (business / technical).
- Extra context from the PO dialogue is passed to the invoked reviewers.
- Re-evaluation and re-synthesis can start fresh or build on top of a previous facilitator–PO conversation (session context reuse).

## Interview Talking Points

- **AI Workflow Designer**: trade-offs of parallelism vs. LLM-driven delegation; loop termination design.
- **AI Engineer**: delegation prompting, loop exit conditions, agent misbehavior handling.
- **AI DevOps Engineer**: session persistence, observability of the loop and delegation events.

## Requirement Coverage Notes

This design naturally exercises the following technical requirements:

- Full session management and persistence (facilitator session across story lifecycle)
- Session context (re-synthesis on top of previous conversations)
- Callbacks (delegation/loop events)
- Observability (loop iterations, delegation decisions)
- Conversation-length monitoring (PO dialogue)
