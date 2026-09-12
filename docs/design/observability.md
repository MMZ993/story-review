# Observability

This document defines telemetry, callback, timeout, retry, and recovery behavior for
FastAPI, Agent Engine, and MCP calls.

## Telemetry and tracing

- **Logging:** Cloud Logging receives structured events from FastAPI, each Agent Engine
  deployment, and each Cloud Run MCP service.
- **Correlation:** every event carries correlation ID and, once available, story run,
  session, agent name/version, transport-attempt number, corrective-reprompt number,
  and `prompt_sha256`.
- **Tracing:** one trace covers one HTTP request/turn. Long-lived story runs are connected
  with `story_run_id`, session attributes, and trace links rather than one trace held open
  while waiting for the PO. Child spans cover each agent invocation, model call, and MCP
  call.
- **Metrics:** dialogue turns, delegation selections, loop iterations, agent/MCP latency,
  overlapping reviewer spans, token use, transport retries, corrective re-prompts,
  idempotency conflicts, lease contention, render failures, and retry exhaustion.
- **Version evidence:** each agent event includes deployed git tag/SHA and prompt hash so
  multiple deployed versions and the exact prompt can be distinguished.

## Callbacks and application events

| Hook | Kind | Purpose |
|---|---|---|
| Before/after tool | ADK callback | Trace MCP tool input metadata, result status, and duration without logging capabilities or content. |
| Before/after model | ADK callback | Track latency/token use and run the post-response context-length check. |
| After agent | ADK callback | Validate and record typed output; emit delegation-validation events. |
| Turn/loop iteration | FastAPI application event, not an ADK callback | Increment the persisted facilitator count and emit gate/park decisions. |

Conversation token/message count is measured after each facilitator model response using
the deployed model's tokenizer and context limit. Warn at 50%. At 75%, create a typed
summary that must retain unresolved issues, prior decisions, story/run IDs, and referenced
artifact IDs; validate it before replacing older conversational events. If validation
fails, preserve the original history and return a structured retryable error rather than
silently dropping context.

## Timeouts and transport retries

The shared instrumented client wrapper is used for FastAPI→Agent Engine and
deterministic FastAPI→MCP calls.

| Parameter | Policy |
|---|---|
| Short-call timeout | 60 seconds for reviewers, synthesis, and MCP calls |
| Facilitator timeout | 120 seconds per model attempt |
| Short-call attempts | At most 3 total attempts |
| Facilitator attempts | At most 2 total attempts, subject to reconciliation below |
| Short-call backoff | Jittered exponential delay for the two intervals between the three attempts: based on 1 s, then 2 s |
| Facilitator backoff | 5 seconds before the second attempt |
| Retry on | Connection failure, timeout, or retryable upstream 5xx |
| Never transport-retry | 4xx, schema validation, authorization, idempotency mismatch, or terminal state conflict |

`transport_attempts` and `corrective_reprompts` are separate counters. A malformed
`DelegationDecision` allows at most two corrective model re-prompts; these are not
transport retries. Exhaustion returns `DELEGATION_VALIDATION`.

The initial story-selection request and every PO turn have a hard five-minute
end-to-end deadline, including finalization. Before an attempt, orchestration clamps its
timeout to the remaining budget minus a response-cleanup reserve and does not start an
attempt that cannot fit. The deadline never runs while waiting for PO input.

## Turn leases and finalization

A timeout is ambiguous — the lease serializes local database mutation but does not
prove a remote agent failed to finish. Retries therefore rely on stable idempotency
keys for all writes: a repeated reviewer/synthesis invocation may repeat model cost,
but artifact saves are idempotent, so a retried turn never produces duplicate
artifacts, dialogue events, or reports. For the stateful facilitator, exactly one
authoritative `TurnRecord` per turn number exists: the ADK runtime appends raw
session events tagged with the invocation ID, FastAPI writes the application turn
record only after success, and a retry first checks the ADK session for that
invocation ID to retrieve an already-completed result instead of reinvoking it
(see agents.md § Session and invocation semantics).

A session turn lease has a six-minute TTL, one minute longer than the HTTP deadline. It
is acquired with the idempotent operation claim, renewed only by its token holder,
and released before a normal response. A crashed holder expires without permanently
locking the session.

Contention returns `SESSION_LOCKED` with `retry_after_seconds`. Because the rejected
operation never owned the lease, the client waits and submits a new key; recovery of an
operation that did own the lease uses the same key. A finalizing session remains
`finalizing` until all requested report
formats and references are persisted; render failure is retryable. Retry exhaustion
returns a structured error to the PO in the dialogue — no silent failures.

## Loop safety and dashboards

The opening facilitator call is turn 1. Each later request that invokes the facilitator
increments the count once — a delegated turn still counts once despite its two
invocations (Item G / D21); explicit PO acceptance does not. Facilitator turn 10 parks
the session before readiness evaluation and emits a cap event.

Built-in Cloud Monitoring dashboards show per-agent latency/error/token use, retry and
validation exhaustion, idempotency mismatch/in-progress rates, lock waits, ambiguous
recoveries, and report failures. Alert policies cover retry exhaustion and delegation
validation failure. Evaluation runs use the same correlation structure and publish
judged cases and per-turn traces as Azure pipeline artifacts.
