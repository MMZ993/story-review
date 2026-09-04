# Observability

## Telemetry sources

- **Cloud Logging**: FastAPI, Agent Engine deployments, Cloud Run MCP servers.
- **Correlation IDs**: every request carries session ID, story ID, agent name, attempt
  number; propagated through Agent Engine and MCP calls.
- **Tracing (Cloud Trace / OpenTelemetry)**: one trace per story run; spans per agent
  invocation and MCP call, linked by the correlation ID — full distributed tracing from
  TUI turn to tool call.
- **Metrics (counters)**: dialogue turns, delegation decisions (per `invoke`
  combination), loop iterations per story, review/synthesis durations, MCP tool calls,
  retry attempts, failures, retry exhaustion, validation failures of delegation output,
  per-agent token usage (cost tracking).
- **Agent version labeling**: every log entry and metric carries the deployed agent
  version — doubles as runtime evidence for the versioning requirement (multiple
  versions observable side by side).
- **Conversation-length monitoring**: token/message count per facilitator session;
  warn at 50% of model context, act (compaction or summary handover) at 75%.

## Callbacks (ADK)

| Callback | Purpose |
|---|---|
| Before/after tool (MCP) | log tool invocations and durations; detect MCP misbehavior |
| After agent (facilitator) | record delegation decision + validate schema; observability event on validation failure |
| After model | conversation-length check for the facilitator session |
| Loop-iteration callback | record each facilitator loop iteration toward readiness |

## Retry, timeout and error handling policy

Implemented once as a shared client wrapper, used for both FastAPI→Agent Engine and
FastAPI→MCP paths. All attempts are logged (correlation ID, attempt no.) and counted as
metrics.

| Parameter | Value |
|---|---|
| Call timeout | 60 s (dialogue turns: 120 s) |
| Attempts | 3 for short calls (reviewers, synthesis, MCP); 2 for dialogue turns |
| Backoff | exponential with jitter (1 s / 2 s / 4 s short calls; 5 s for dialogue) |
| Retry on | transient errors only (5xx, timeout, connection) |
| No retry on | 4xx, schema/validation errors — surfaced immediately |

"Dialogue turn timeout" = the time allowed for one facilitator ↔ PO conversational LLM
call (one turn of the User-in-the-Loop dialogue); it is longer than single-shot
review/synthesis calls because the facilitator prompt + session history is larger.
With 120 s dialogue timeouts, dialogue retries are capped at 2 attempts to bound worst-case
wait (~4 min) — short calls keep 3 attempts (~3 min worst case).

Additional policies:

- **End-to-end request deadline**: 5 min per PO turn — covers the facilitator call,
  delegated reviews, synthesis and their retries (individual retry budgets are bounded
  so the total fits the deadline; the deadline is never applied to waiting for PO
  input).
- **Session turn locks**: lease-based with 5 min TTL; released after the response; a
  crashed holder expires with the lease — no permanently locked sessions.
- **Corrective LLM re-prompt** (e.g. DelegationDecision schema violation) is *not* a
  transport retry: bounded to 2 re-prompts, then surfaced as a structured validation
  error. Transport retries never apply to validation errors.

Retry exhaustion returns a structured error to the PO in the dialogue — no silent
failures.

## Loop safety cap

- Max facilitator loop iterations per story: **10**.
- Hitting the cap emits an explicit event and forces a "park the story" decision in the
  dialogue — no unbounded loops burning quota.

## Error taxonomy

- All errors use one structured model (error code, agent, correlation ID, retryable
  flag) — PO-facing errors, logs and metrics derive from the same schema.

## Link to evaluation tests

- Agent evaluation test runs are logged with the same correlation structure, so a failed
  evaluation case can be traced to the exact agent turns that produced it.
- Evaluation tests run as a **separate pipeline**, triggered only when agent prompts,
  models, or agent code change (not on every deployment) — to control token cost.
- Test run logs (judged cases, per-turn traces) are published as **pipeline artifacts**
  for post-run inspection.

## Dashboards / checks

- Reuse **built-in Cloud Monitoring dashboards and alerting** — no custom dashboard
  applications.
- Per-agent error and latency views from existing metrics/logs.
- Alerts on retry-exhaustion rate and validation-failure rate (Cloud Monitoring alert
  policies).
