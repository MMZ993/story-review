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
  context stories (Phase 4) — the reviewer input contract. Note: linked
  context stories exist **only** inside that single `get_story` response —
  the story MCP server derives them from the internal Azure DevOps work-item
  relations (Related/Depends). There is deliberately no separate
  linked-story tool, UI command, or agent-side retrieval step; reviewers
  receive them as part of the `story` input and never fetch them
  themselves.
- ADK available in the local toolchain (mise/uv) at the pinned version;
  Vertex AI reachable via ADC from the machine running live smokes
  (**the owner's main PC — the dev server has no ADC and cannot run live
  verification**).

## Machine split (learned constraint)

- **Dev server (no cloud access)**: plan docs, prompt authoring, agent code,
  adapters, compose `local-agents` wiring, deterministic non-LLM tests (such
  as prompt loading and hashing), reviews.
- **Main PC (ADC + Vertex)**: all agent-behavior tests and live-verification
  gates use a real low-cost Gemini model, and later the Agent Engine deploys
  (Phase 8, not Phase 5).

Each increment below splits deterministic local checks from real-model ADC
verification accordingly.

## Increment 0 owner decisions (settled)

1. **LLM test strategy — decided (D13)**: do not mock or script LLM
  responses. Agent-behavior and adapter tests call a real low-cost Gemini
  model through Vertex AI on the main PC. Deterministic tests remain limited
  to non-LLM behavior such as prompt loading and hashing; the dev server does
  not run agent-behavior tests.
2. **Model per agent — decided (D13)**: `gemini-2.5-flash` in
  `europe-west4` for all four agents. Phase 0 already proved it; one model
  keeps cost and behavior simple. Pin it in each immutable `config.yaml` so
  later versions can diverge if evidence warrants it.
3. **Structured-output mechanism — decided (D13)**: use ADK native
  structured-output enforcement backed by the shared strict Pydantic models.
  Only malformed facilitator delegation output gets the bounded corrective
  re-prompt loop from observability.md; it is recorded as an observability
  event. Reviewer and synthesis output failures follow the normal structured
  error path after transport retries.
4. **Reviewer invocation interface shape — decided (D13)**: separate typed
  single-turn interfaces for each reviewer and synthesis agent; a separate
  session-scoped interface for the facilitator. Orchestration owns input
  assembly. The approved request/response fields are frozen in the
  increment-0 hand-off spec below: story `StoryDetail` (including linked
  `context_stories`), optional previous review and PO context for reviewers;
  two latest perspective artifacts for synthesis; typed report plus
  agent/prompt-version labels; structured errors. Only facilitator
  delegation-validation exhaustion follows corrective re-prompts.
5. **Facilitator session backend locally — decided (D13)**: use
  `DatabaseSessionService` with the compose `postgres:16` substitute from the
  start, for deployed-shape parity and no later backend rework. Migrations for
  audited application records remain Phase 6; facilitator sessions are runtime
  state only in Phase 5.
6. **Prompt review workflow — decided (D13)**: prompts remain centrally
  accessible static data in `prompts/`. Create minimal functional initial
  prompts; the owner reviews all four together before their first commit.
  Later prompt iterations are evidence-driven once the full application
  exists, rather than attempting premature prompt optimization in Phase 5.

Recorded outcomes are in `docs-local/local-decisions.md` (D13).

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
- Makefile: deterministic non-LLM test targets plus real-model agent test
  targets (main PC only) for Vertex gates.
- Runbook 11 (`docs-local/runbooks/11-agents.md`) — commands and evidence
  per increment, sanitized.

## Implementation increments

### 0. Packaging skeleton + invocation interface + open decisions (local)

- Status: in progress (2026-09-12). Packaging decided with the owner as
  **D14**: four separate packages under `agents/<slug>/` + shared
  `shared/agent_kit` for PROMPTS_DIR loading/hashing and strict config.yaml
  parsing.

- Settle the six open decisions above; record them.
- Draft the **invocation interface contract** (decision 4) as a short spec in
  this plan's appendix or `docs-local/` — it is the Phase 6 hand-off and must
  exist before adapter code.
- uv package layout for the four agents (one package `agents/` with four
  modules vs four small packages — follow repository-layout.md, decide with
  the owner), `requirements.in`/`lock`, `PROMPTS_DIR` loading + UTF-8/missing
  fail-loud helper, `prompt_sha256` computation.
- Test-first: loading/hash/shape tests green locally; agent behavior is
  tested against the real model on the main PC.

### 1. Business reviewer (local code + mock tests; live gate on main PC)

- `prompts/business-reviewer.md` from agents.md role spec: clarity, user
  value, business justification, epic/roadmap alignment, AC gaps; comments as
  semantic input; context stories framed as related-reference-only. Owner
  reviews the prompt once before commit.
- ADK agent, `config.yaml`, typed `ReviewReport` output validated against
  `shared/review_schemas` (strict). Validation failures return structured
  errors; only normal transport retries apply (observability.md).
- Adapter behind the frozen invocation interface; real-model tests on the
  main PC for wiring and structured validation failures.
- **Live gate (main PC)**: one real call against Vertex AI with a T1 dataset
  story (via the compose story server or the dataset loader directly) →
  schema-valid `ReviewReport`; evidence in Runbook 11.

### 2. Engineering reviewer (local + live gate)

- Same real-model test approach and contract:
  `prompts/engineering-reviewer.md` covers technical completeness, missing
  behaviors, edge cases, dependencies, risks, unknowns, and architectural
  impact.
- Reuse the increment-1 skeleton; tests mirror it plus prompt-distinctness
  checks. Live gate as increment 1.

### 3. Synthesis (local + live gate)

- `prompts/synthesis.md`: input is always the two latest artifacts (one per
  perspective) — pairing is orchestration's job in Phase 6; the Phase 5 test
  harness assembles pairs, including the single-perspective-re-review pairing.
- Typed `SynthesisReport`; hidden-conflict scenario (zero per-perspective
  findings, contradiction flagged in synthesis) is a required real-model test
  case on the main PC.

### 4. Facilitator + `local-agents` compose profile (local + live gate)

- `prompts/facilitator.md`: dialogue role, delegation rules, opening turn
  `invoke` = none, `readiness` is proposal-only, PO acceptance never produced
  by the LLM.
- `McpToolset` wiring to the story server (read) + artifact server (read,
  lineage-scoped refs supplied in the prompt context) against the running
  compose `local` stack; no report tools.
- Typed `FacilitatorTurnOutput` (reply + `DelegationDecision` +
  `ResolutionDraft`s) with strict validation; invalid combinations rejected;
  malformed delegation output gets at most two corrective re-prompts, recorded
  as counters.
- Session-scoped runs per decision 5 (Postgres substitute in compose).
- `local-agents` profile in `deploy/docker-compose.yml` + Makefile wiring;
  adapter contract tests over the interface.
- **Live gate (main PC)**: a scripted walkthrough of the
  example-interaction.md conflict-resolution scenario against the local
  stack — delegation decisions (`invoke` both → none, re-synthesis with
  `reuse_previous`, resolution drafts) match the expected arc; evidence in
  Runbook 11. This is the development-plan exit criterion for Phase 5.

## Verification gates

- Every increment: test-first deterministic non-LLM checks locally and
  real-model agent-behavior tests on the main PC; existing suites
  (review-schemas, dataset, mcp-*, compose contract) stay green (Phase 4
  suite counts are the baseline).
- Vertex gates run on the main PC only; sanitized evidence into Runbook 11;
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

## Appendix — frozen local-adapter invocation contract (increment 0)

All adapter request and response DTOs are strict Pydantic models. The adapters
are local representations of the Agent Engine invocation boundary; they do not
change the shared domain schemas. Orchestration assembles every request and
persists outputs.

### Reviewers

Each reviewer adapter exposes one single-turn invocation. Its request contains:

- `story: StoryDetail` — including `context_stories` when linked stories exist;
- `previous_review: ReviewReport | None`; and
- `extra_context: Text | None`.

Its response contains `report: ReviewReport`, `agent_version: ShortText`, and
`prompt_sha256: Sha256`. Reviewers have no MCP tools. Invalid typed output is a
structured error after normal transport retries; it does not cause a corrective
model re-prompt.

### Synthesis

The synthesis adapter exposes one single-turn invocation. Its request contains
the latest business and engineering pairs, each consisting of a `ReviewReport`
and its `ArtifactReference`; both references must belong to one story run. Its
response contains `report: SynthesisReport`, `agent_version: ShortText`, and
`prompt_sha256: Sha256`.

### Facilitator

The facilitator adapter exposes a session-scoped turn invocation. Its request
contains `session_id: SessionId`, `turn_number`, the PO message when applicable,
the latest synthesis report and its `ArtifactReference`, and the
lineage-scoped `ArtifactReference` values available for evidence reads. Its
ADK session state is held in PostgreSQL. The configured MCP tools are read-only
story and artifact tools; the facilitator never invokes reviewers or synthesis
as tools. Its response contains `output: FacilitatorTurnOutput`,
`agent_version: ShortText`, and `prompt_sha256: Sha256`.

For all adapters, failures use the existing `ErrorEnvelope` taxonomy. Only a
malformed facilitator delegation output receives up to two corrective
re-prompts; exhaustion returns `DELEGATION_VALIDATION`.
