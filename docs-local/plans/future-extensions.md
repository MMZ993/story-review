# Future Extensions Plan (DRAFT — owner decisions pending)

Proposed additions to the home-phase development plan. This document is a
**proposal only**: `docs-local/development-plan.md` is intentionally untouched
(Phase 4 is in progress in a parallel session). Once the owner approves scope
and ordering, the accepted items move into `development-plan.md` (and, where
they are fundamental design changes rather than home-phase variants, into
`docs/` per the docs-first rule and the doc-vs-docs-local split).

Status legend for items: proposed / accepted / rejected (+ reason).

## Item A — Evaluator/judge agent for automated test-result checking (Phase 9 amendment)

**Status: proposed.**

### Motivation

Phase 9 already includes a judge for evaluating agent output quality
(`prompts/judge.md`, judge config, judged assertions on expected files). This
item adds a second, distinct evaluator role: an agent that checks **test
results themselves** — i.e. after a full run of the evaluation suite, it
reviews the pass/fail outcomes and judge scores and produces a structured
verdict (systemic failure patterns, flaky cases, suspected expected-file
drift, confidence in the pass), so a human does not have to eyeball long test
output.

### Scope (sketch)

- One more agent (same packaging pattern as Phase 5 agents: `prompts/`,
  `config.yaml`, ADK, typed output via `shared/review_schemas` extension or a
  new small schema group).
- Input: evaluation-suite result summary (per-case deterministic + judged
  outcomes, run metadata).
- Output: typed `EvaluationVerdict`-style model — overall verdict, per-category
  findings, recommended action (pass / investigate / fix expected files).
- Runs only on demand (make target), never in the request path.

### Exit criteria

- Suite-results input validates; verdict output is schema-valid against a
  local Vertex AI run.
- One dry run against a real (partial) evaluation-suite output reviewed by
  the owner.

### Cost

- Vertex AI tokens only; negligible.

### Design notes / decisions needed

- New schema group location: extend `shared/review_schemas` (versioned) vs a
  separate package — follow the Phase 2 patterns and D9 history.
- Where it runs: local compose only, or also registered for dev (Phase 8
  pattern)? Proposal: local only until proven useful.
- Relationship to the existing Phase 9 judge: separate prompt, separate
  model role; do not conflate.

## Item B — Web interface

**Status: superseded (2026-09-11) — folded into Phase 7 as the Web UI (D16).**
The TUI was dropped in favour of a minimal web client; see
`development-plan.md` Phase 7 and D16. The sketch below is retained for
history: the accepted Phase 7 scope matches it (thin client, API consumed
as-is, same idempotency-key semantics).

### Motivation

The original design had a TUI (Phase 7) as the primary client. A web
interface widens the demo audience and removes local-tooling prerequisites.

### Scope (sketch)

- Thin web client over the existing FastAPI orchestration API
  (`api-contract.md`) — **no new server-side flows**; the API contract is
  consumed as-is, or extended only via an owner-approved design change in
  `docs/`.
- Session start / story selection, live (SSE or polling) facilitator turn
  view, PO acceptance action, report download via signed URLs.
- Same idempotency-key semantics as the client.

### Exit criteria

- The example-interaction.md walkthrough playable end-to-end from the browser
  against the local stack; and against dev after a Phase 8-style deploy if
  accepted.

### Cost

- Cloud Run service (min 0) if deployed; otherwise local only.

### Design notes / decisions needed

- Framework choice (plain SSR vs SPA) — keep minimal; this is a capstone demo,
  not a product.
- Auth: local unauthenticated vs IAP/OIDC for dev.
- Where the design lives if accepted: web UI is arguably beyond the frozen
  `docs/` scope → likely a `docs/` design change (owner approval) rather than
  a docs-local-only deviation.

## Item C — Phase 11: Full cross-template integration run

**Status: proposed.**

### Motivation

Phase 9's evaluation covers required dataset cases, but a *complete* matrix
run — all 45+ stories across templates T1–T6 and all seven scenarios,
end-to-end through the deployed stack — has not been scheduled anywhere. It
will be long and token-costly; it needs its own phase with budgeting,
checkpointing, and resume semantics.

### Scope (sketch)

- Run the full evaluation matrix (every story × every expected case), local
  compose and/or dev environment (decision needed).
- Checkpointing: per-case results persisted so an interrupted run resumes
  instead of restarting.
- Retry policy for transient Vertex/upstream failures, distinguished from
  genuine failures.
- Output: full coverage matrix report; feed into Item A's evaluator agent.
- Estimated duration and token cost computed from a small sample run
  (e.g. one template column) before committing to the full run.

### Exit criteria

- One complete, resumable full-matrix run with a persisted results artifact
  and coverage matrix; results summarized (ideally checked by the Item A
  evaluator agent).

### Cost

- The largest Vertex AI token spend after Phase 8: N stories × agent turns ×
  reviewer calls + judge calls. Must be estimated from a sample and approved
  by the owner before the full run.

### Design notes / decisions needed

- Environment: local compose (cheaper, no Agent Engine) vs dev on GCP (proves
  the real deployment). Proposal: full matrix locally, representative subset
  on dev.
- Rate limits and concurrency caps for Vertex AI.
- Whether Item A must land first (recommended — the whole point of the long
  run is automated result assessment).

## Item D — Callback and observability completion (Phase 6/8 remediation)

**Status: proposed. This is required design completion, not an optional product
extension.**

### Motivation

`docs/source/evaluation.md` requires callbacks for a chosen purpose. The
implemented facilitator has one ADK `before_tool_callback`: it prevents
out-of-lineage artifact reads and orchestration-only story-source overrides.
The broader callback design in `docs/design/observability.md` remains
unimplemented: before/after tool and model telemetry, post-response
conversation-length monitoring, after-agent typed-output and
validation-event recording, and FastAPI turn/loop application events.

### Scope (sketch)

- Keep facilitator tool-call authorization in
  `shared/agent_kit/agent_kit/facilitator_adapter.py`; extend its ADK callback
  seam with content-safe before/after tool telemetry (metadata, status, and
  duration only).
- Add reusable callback helpers in `shared/agent_kit/agent_kit/`, injected by
  agent builders, for model latency/token measurements. Apply the
  post-response context-length policy to the facilitator: warn at 50%; at 75%
  create and validate the required typed conversation summary before replacing
  older history.
- Add after-agent handling for typed-output validation and
  delegation-validation events. The existing corrective re-prompt loop remains
  responsible for bounded recovery; callbacks record the outcome rather than
  parse reply prose.
- Add FastAPI application events in the Phase 6 session/turn service, not in
  ADK callbacks, to persist facilitator turn counts and emit gate/park events.
- Emit structured events with the observability correlation fields and without
  prompt, tool capability, story, or artifact content.

### Exit criteria

- Unit tests prove each configured callback is attached and emits the expected
  content-safe structured event.
- Facilitator tests cover 50% warning, 75% validated-summary success, and
  summary-validation failure without loss of original history.
- An integration/evaluation trace contains paired before/after facilitator MCP
  tool events, model latency/token data, an after-agent validation event, and a
  FastAPI loop/gate event.
- `docs/quality/requirements-coverage.md` can move the callback row from
  designed to implemented/verified only after the evidence is recorded.

### Cost

Local deterministic callback tests have no model cost. Facilitator integration
and evaluation evidence uses the existing Vertex AI test budget.

### Design notes / decisions needed

- Decide whether the reusable model callbacks attach to all four agents from
  Phase 6, or the facilitator first with the remaining agents completed in
  Phase 8 observability wiring. Recommendation: use the facilitator first
  because it owns the persistent conversation; use all agents for latency and
  token telemetry once the shared helper is proven.
- Confirm the ADK callback API and event/token fields against the pinned
  `google-adk` version before implementation; do not invent callback
  signatures.
- Keep the FastAPI turn/loop events separate from ADK callbacks, exactly as
  `docs/design/observability.md` specifies.

## Proposed ordering

1. Item D is planned with the active Phase 6/Phase 8 work before the Phase 9
   evaluation gate; it closes an existing technical requirement.
2. Item A lands as a Phase 9 amendment (small, needed by C).
3. Phase 10 (web interface) after Phase 9 — independent of A/C.
4. Phase 11 (full integration run) last, after A and a green Phase 9 — it
   consumes everything and is the final proof.

Open question for the owner: whether the web interface (B) or the full
integration run (C) matters more for the capstone demo — this sets 10 vs 11.
