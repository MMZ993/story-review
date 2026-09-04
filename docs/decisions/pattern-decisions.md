# Pattern Decisions

## Decision

We implement a single workflow that fulfills **Pattern 2 (primary)** and **Pattern 3 (bonus)**.

## Architecture Overview

Two-layer design:

1. **Orchestration layer** — Interaction Facilitator agent in a dialogue loop with the Product Owner, holding session context across the whole story lifecycle.
2. **Execution layer** — the review pipeline: Business Reviewer + Engineering Reviewer in parallel, followed by the Synthesis & Conflict Resolver.

The facilitator invokes the execution layer dynamically, based on the PO conversation.

## Pattern 2 Fulfillment (primary)

| Requirement | How we fulfill it |
|---|---|
| Sequential | Reviewers → Synthesis → Facilitator base pipeline |
| Parallel agent use | Business and Engineering Reviewers run independently on the same story |
| Loop agent | Facilitator ↔ PO dialogue iterates until the story reaches an explicit "ready" exit condition (all flagged issues resolved or PO accepts) |

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
