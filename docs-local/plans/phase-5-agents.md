# Phase 5 — Agents (ADK) + local adapters plan

## Objective

Implement the four agents from `docs/design/agents.md` — business-reviewer,
engineering-reviewer, synthesis, facilitator (in that order of increasing
complexity) — each as an ADK agent with a static prompt in `prompts/`, an
immutable model `config.yaml` in `agents/<agent>/`, typed output validated
against `shared/review_schemas`, and a local ADK adapter in
`deploy/compose/adapters/` behind the same invocation interface Agent Engine
will expose (per `docs/decisions/tech-stack.md` and
`docs/operations/repository-layout.md`). Compose gains the `local-agents`
profile; Agent Engine itself is never a compose service.

Per development-plan.md exit criteria: each agent produces schema-valid typed
output against Vertex AI locally; the facilitator's delegation behaves per
`docs/design/example-interaction.md`.

Cost: Vertex AI tokens only. Cloud SQL stays STOPPED throughout (no Phase 5
increment needs it — the facilitator's session backend is the compose
Postgres substitute, runtime state only); Cloud Run stays as-is. Track cost
per live gate in Runbook 11 — the acceptance metric for the model choice is
cost per evaluation run (45 stories × 2 reviewers + synthesis + dialogue
turns) against the trial credits (near-zero used of zł1,114, expire
2026-12-05).

## Preconditions

- Phase 4 complete and closed (completion review 2026-09-10 Ready-to-close;
  D10 amendment 7 recorded). Phase 5 opens strictly after — this plan may be
  written earlier, but no Phase 5 code lands before the Phase 4 close.
- Schemas already in place from Phase 2: `ReviewReport`,
  `SynthesisReport`, `FacilitatorTurnOutput` / `DelegationDecision` /
  `ResolutionDraft`, `AgentRunRecord` (incl. `prompt_sha256`) — Phase 5 is a
  consumer, not a schema author. Any schema gap found during implementation is
  raised with the owner first (docs-first rule), not patched silently.
- Story MCP server's `get_story` returns `StoryDetail` with comments and
  context stories (Phase 4) — the reviewer input contract.
- ADK available in the local toolchain (mise/uv) at the pinned version;
  Vertex AI reachable via ADC from the machine running live smokes
  (**the owner's main PC — the dev server has no ADC and cannot run live
  verification**).

## Machine split (learned constraint)

- **Dev server (no cloud access)**: plan docs, prompt authoring, agent code,
  adapters, compose `local-agents` wiring, all mock-LLM unit tests, reviews.
- **Main PC (ADC + Vertex)**: every live-verification gate (the actual exit
  criterion "schema-valid typed output against Vertex AI locally"), and later
  the Agent Engine deploys (Phase 8, not Phase 5).

Each increment below splits its verification into local (mock) and live
(ADC) gates accordingly.

## Open decisions to settle in increment 0 (owner)

1. **Mock-LLM test strategy** on ADC-less machines: ADK's built-in mock LLM /
  fake model vs a thin scripted stub behind the adapter interface. Working
  assumption: ADK mock model for unit tests of wiring + a small scripted-stub
  layer for adapter contract tests; live gates run only on the main PC.
2. **Model per agent**: Phase 0 evidence is gemini-2.5-flash (europe-west4).
  One model for all four agents (working assumption — simplicity first,
  versioned in each `config.yaml` so they can diverge later), or a stronger
  model for synthesis/facilitator up front? Decide against current Vertex
  catalogue, token pricing, and the trial-credit budget.
3. **Structured-output mechanism**: ADK native output-schema enforcement vs
  prompt-constrained JSON + strict parse. Working assumption: use ADK native
  structured output where it validates against our strict models; either way
  the bounded corrective re-prompt loop (observability.md) stays for
  validation failures and is recorded as an observability event.
4. **Reviewer invocation interface shape** (deliverable of increment 0, needs
  owner approval): the exact single-turn call contract orchestration (Phase 6)
  will use for reviewers/synthesis — input assembly is orchestration's job,
  so Phase 5 must freeze the interface, not just the implementation:
  request fields (story `StoryDetail` JSON, optional previous review, optional
  PO extra context; for synthesis: two latest artifacts one per perspective),
  response (typed report + agent/prompt version labels), error taxonomy
  (structured, incl. validation-failure-after-reprompts).
5. **Facilitator session backend locally**: `DatabaseSessionService` needs
  PostgreSQL; compose `local` profile already plans a `postgres:16`
  substitute. Use it for the facilitator adapter from the start (deployed
  shape parity) vs ADK `InMemorySessionService` in Phase 5 and Postgres in
  Phase 6. Working assumption: Postgres from the start (same interfaces, no
  later rework), migrations deferred to Phase 6 (facilitator sessions are
  runtime state, not the audited application records).
6. **Prompt review workflow**: prompts are owner-reviewed artifacts (golden-
  snapshot precedent from Phase 4). Confirm the same one-time owner review
  per prompt file before first commit.

Recorded outcomes go to `docs-local/local-decisions.md` (expected D13).

## Deliverables

- `prompts/{business-reviewer,engineering-reviewer,synthesis,facilitator}.md`
  (UTF-8 static data; loaded once at startup; `judge.md` stays Phase 9).
- `agents/<agent>/` — ADK agent code + immutable `config.yaml` (model ID +
  generation settings) per repository-layout.md.
- `deploy/compose/adapters/<agent>/` — the four local adapters exposing the
  Agent-Engine-equivalent invocation interface (single-turn run for
  reviewers/synthesis; session-scoped run for the facilitator).
- `deploy/docker-compose.yml` — new `local-agents` profile wiring the
  adapters to the existing `local` MCP stack (story read-only MCP endpoints
  for the facilitator via `McpToolset`; auth disabled local-only as today).
- Makefile: `agents-test` (or per-agent targets) for the mock-LLM suites,
  and `agents-live-smoke` (main PC only) for the Vertex gates.
- Runbook 11 (`docs-local/runbooks/11-agents.md`) — commands and evidence
  per increment, sanitized.

## Implementation increments

### 0. Packaging skeleton + invocation interface + open decisions (local)

- Settle the six open decisions above; record them.
- Draft the **invocation interface contract** (decision 4) as a short spec in
  this plan's appendix or `docs-local/` — it is the Phase 6 hand-off and must
  exist before adapter code.
- uv package layout for the four agents (one package `agents/` with four
  modules vs four small packages — follow repository-layout.md, decide with
  the owner), `requirements.in`/`lock`, `PROMPTS_DIR` loading + UTF-8/missing
  fail-loud helper, `prompt_sha256` computation.
- Test-first: loading/hash/shape tests green locally.

### 1. Business reviewer (local code + mock tests; live gate on main PC)

- `prompts/business-reviewer.md` from agents.md role spec: clarity, user
  value, business justification, epic/roadmap alignment, AC gaps; comments as
  semantic input; context stories framed as related-reference-only. Owner
  reviews the prompt once before commit.
- ADK agent, `config.yaml`, typed `ReviewReport` output validated against
  `shared/review_schemas` (strict) with the bounded corrective re-prompt (max
  2, distinct from transport retries — observability.md).
- Adapter behind the frozen invocation interface; mock-LLM unit tests for
  wiring, validation-failure → re-prompt → structured error.
- **Live gate (main PC)**: one real call against Vertex AI with a T1 dataset
  story (via the compose story server or the dataset loader directly) →
  schema-valid `ReviewReport`; evidence in Runbook 11.

### 2. Engineering reviewer (local + live gate)

- Same contract, `prompts/engineering-reviewer.md`: technical completeness,
  missing behaviors, edge cases, dependencies, risks, unknowns,
  architectural impact.
- Reuse the increment-1 skeleton; tests mirror it plus prompt-distinctness
  checks. Live gate as increment 1.

### 3. Synthesis (local + live gate)

- `prompts/synthesis.md`: input is always the two latest artifacts (one per
  perspective) — pairing is orchestration's job in Phase 6; the Phase 5 test
  harness assembles pairs, including the single-perspective-re-review pairing.
- Typed `SynthesisReport`; hidden-conflict scenario (zero per-perspective
  findings, contradiction flagged in synthesis) is a required test case —
  drafted with a mock LLM locally, proven live on the main PC.

### 4. Facilitator + `local-agents` compose profile (local + live gate)

- `prompts/facilitator.md`: dialogue role, delegation rules, opening turn
  `invoke` = none, `readiness` is proposal-only, PO acceptance never produced
  by the LLM.
- `McpToolset` wiring to the story server (read) + artifact server (read,
  lineage-scoped refs supplied in the prompt context) against the running
  compose `local` stack; no report tools.
- Typed `FacilitatorTurnOutput` (reply + `DelegationDecision` +
  `ResolutionDraft`s) with strict validation; invalid combinations rejected;
  bounded corrective re-prompting recorded as counters.
- Session-scoped runs per decision 5 (Postgres substitute in compose).
- `local-agents` profile in `deploy/docker-compose.yml` + Makefile wiring;
  adapter contract tests over the interface.
- **Live gate (main PC)**: a scripted walkthrough of the
  example-interaction.md conflict-resolution scenario against the local
  stack — delegation decisions (`invoke` both → none, re-synthesis with
  `reuse_previous`, resolution drafts) match the expected arc; evidence in
  Runbook 11. This is the development-plan exit criterion for Phase 5.

## Verification gates

- Every increment: test-first, mock-LLM suites green locally; existing suites
  (review-schemas, dataset, mcp-*, compose contract) stay green (Phase 4
  suite counts are the baseline).
- Live gates run on the main PC only; sanitized evidence into Runbook 11;
  identifier check before any commit containing evidence.
- Independent read-only subagent review per increment and before phase
  close (Phase 2/3/4 pattern), plus the owner's one-time prompt reviews.

## Exit criteria (from development-plan.md)

Each agent produces schema-valid typed output against Vertex AI locally; the
facilitator delegation behaves per example-interaction.md. Both proven with
evidence in Runbook 11.

## Out of scope

- Orchestration (FastAPI), turn leases, gate precedence, idempotent response
  storage, direct-MCP-client wrapper, session reconciliation — Phase 6.
- Agent Engine deployments, versioning/rollback — Phase 8. This includes the
  deferred azure/Secret-Manager story-server wiring (D10 amendment 7).
- Judge agent and `prompts/judge.md` — Phase 9 (and future-extensions item A
  remains a proposal).
- Cloud SQL for application records — Phase 6 (Postgres substitute in compose
  is runtime state only).
- TUI — Phase 7.

## Risks and controls

- **Model drift/cost**: model IDs + settings pinned per agent in
  `config.yaml`; live gates are few-call and cost-recorded; trial-credit
  expiry 2026-12-05 tracked in HANDOFF.
- **Prompt quality**: prompts are repo data with SHA-256 provenance and a
  one-time owner review; the evaluation regression (Phase 9) is the
  systematic guard, increment live gates the interim guard.
- **Adapter/AE interface divergence**: the invocation-interface spec is
  single-sourced, frozen at increment 0, and reviewed; Phase 8 re-verifies
  against the real Agent Engine deployment.
- **Facilitator tool misuse** (wrong id space, artifact reads outside the
  supplied lineage): tool arguments validated adapter-side now,
  orchestration-side in Phase 6.

## References

- `docs/design/agents.md`, `docs/design/schemas.md`,
  `docs/design/example-interaction.md`, `docs/design/observability.md`
- `docs/operations/repository-layout.md` (adapter contract, prompts rules),
  `docs/decisions/tech-stack.md` (model config versioning)
- `docs-local/local-decisions.md` D3 (pipelines deferred), D10 amendment 7
  (azure path stays out of Phases 5–7)
- `shared/review_schemas` (typed outputs), `mcp_servers/story` +
  `mcp_servers/artifact` (facilitator toolset targets)
