# Runbook 11 — Agents (ADK) + local adapters (Phase 5)

Environment: owner's main PC (ADC + Vertex available). Cloud SQL stays
STOPPED throughout Phase 5 (facilitator sessions use the compose Postgres
substitute). Plan: `docs-local/plans/phase-5-agents.md`; decisions D13/D14.

Verification-state log (append-only):

## Increment 0 — packaging skeleton + invocation interface

**Status: IN PROGRESS (code green; owner prompt review pending before first
commit).**

Owner decisions this increment (recorded as D14 in local-decisions.md):

- four separate uv packages under `agents/<slug>/`, exactly per
  repository-layout.md;
- shared `shared/agent_kit` (`agent-kit` 0.1.0) holds the fail-loud
  `PROMPTS_DIR` loader (UTF-8, SHA-256 over file bytes, immutable
  `LoadedPrompt`; explicit dir → `PROMPTS_DIR` env → `/app/prompts`
  default) and the strict `config.yaml` parser (frozen `AgentConfig`,
  unknown/missing keys rejected);
- `google-adk==2.8.0` (Runbook-06-spike-proven version) in each agent
  `requirements.lock`; `config.yaml` per agent: `gemini-2.5-flash`,
  `europe-west4`, `temperature: 0.0`, `max_output_tokens: 8192`.

What landed:

- `shared/agent_kit/` — package + tests; `make agent-kit-test` (**12
  passed**).
- `agents/{business-reviewer,engineering-reviewer,synthesis,facilitator}/` —
  pyproject (`<slug>-agent` 0.1.0), config.yaml, requirements.in/lock,
  package skeleton (`AGENT_SLUG` + `load_config()`), deterministic
  per-agent tests (config pinned/immutable, prompt loads from repo
  `prompts/` with stable hash); `make agents-test` (**3 passed × 4 = 12**).
- `prompts/{business-reviewer,engineering-reviewer,synthesis,facilitator}.md`
  — minimal functional first drafts per `docs/design/agents.md` role specs.
  **Owner one-time review DONE (2026-09-12, approved unchanged) — D13-6
  satisfied.**
- Makefile: new `agent-kit-test`, `agents-test` targets.

Process note (honesty over ritual): the agent_kit tests and implementation
were written in the same batch instead of strict test-first; the only red
observed was a test-expectation bug (missing-file message matched against a
nonexistent "prompts" substring). One real implementation bug was caught by
the per-agent tests: `load_config()` looked for `config.yaml` inside the
python package dir instead of the agent root (fixed: `_AGENT_DIR`).

Regression at increment close: `make review-schemas-test` **154 passed**
(untouched baseline).

Gotchas:

- `uv run --with-editable .` for an agent package requires ALL local
  path-dependency editables on the same invocation (`--with-editable
  ../../shared/agent_kit --with-editable ../../shared/review_schemas`),
  otherwise uv resolution fails on the undeclared local packages.

No environment actions were taken this increment (no gcloud/terraform
calls beyond the read-only session-start `make db-status`: STOPPED/NEVER).

## Increment 1 — business reviewer (ADK agent + adapter + live gate)

**Status: COMPLETE (2026-09-12). Live Vertex gate PASS.**

What landed:

- `agent_kit.reviewer_input` — frozen reviewer request model + deterministic
  user-message rendering (story JSON, optional previous review, optional PO
  extra context).
- `agents/business-reviewer/business_reviewer/agent.py` — ADK `LlmAgent`
  builder: model/generation settings only from immutable `config.yaml`,
  instruction only from the prompt file, native `output_schema` structured
  output.
- `deploy/compose/adapters/business-reviewer/` — package
  `business-reviewer-adapter` 0.1.0: `assembly.py` (pure agreement checks —
  perspective/story-id echo/version-without-previous — plus
  `agent_version`/`prompt_sha256` stamping), `runner.py` (the only model
  I/O: fresh single-turn `InMemoryRunner` run + strict parse),
  `app.py` (FastAPI `POST /invoke` + `GET /health`, `ErrorEnvelope`
  mapping: 400/422 VALIDATION_ERROR non-retryable, 503
  UPSTREAM_UNAVAILABLE retryable after ADK retries).
- Makefile: `business-reviewer-adapter-test` (deterministic) and
  `business-reviewer-live-test` (sources `home.env`, sets
  `AGENT_LIVE_TESTS=1` + Vertex env).

Checks (main PC):

- `make agent-kit-test` **21 passed**; `make agents-test` **3×4 passed**;
  `make business-reviewer-adapter-test` **6 passed, 2 skipped** (live tests
  skip without the gate env — verified skipped on the deterministic run).
- **Live gate** `make business-reviewer-live-test` → **8 passed** (~30 s,
  2 real gemini-2.5-flash calls, europe-west4, via ADC): golden story-01 →
  schema-valid business `ReviewReport` (`perspective=business`,
  `story_id=story-01`, correct `prompt_sha256`, content sanity: summary
  mentions invoice/email); second call with PO extra context →
  `based_on_extra_context` populated. Cost: 2 flash calls — negligible.

Gotchas learned:

- **Vertex structured-output serving limit (D13 amendment 1)**: the strict
  `ReviewReport` schema is rejected 400 INVALID_ARGUMENT ("too many states
  for serving": patterns, array max_lengths, bounded ints). Fixed with the
  serving-safe mirror in `agent_kit.llm_output`; strict shared validation
  stays authoritative at the adapter boundary. The failure surfaced
  correctly as a retryable-looking 503 ErrorEnvelope before the fix —
  noting that a 400-class model error should map non-retryable eventually
  (minor, deferred; the generic handler currently lumps model failures).
- ADK 2.8.0 uses `output_schema` (+`generate_content_config`); the
  `output_type` parameter is from newer ADK versions.
- Adapter needs its own pyproject (uv `--with-editable .` requires it);
  `pytest.ini` must be INI-format (`[pytest] asyncio_mode = auto`), not
  TOML.
- FastAPI: return-type union with `JSONResponse` requires
  `response_model=None` on the route decorator.
- The mismatch test for `perspective` must use empty findings — the shared
  model itself rejects E-prefixed findings under a business perspective
  before the adapter check runs.

Increment-1 independent review (read-only subagent, 2026-09-12):
**Ready to proceed** — 0 Critical/Important, 6 Minor. Fixed same session:
runner now concatenates multi-part text (was last-part-wins latent fragility);
`business_reviewer.__init__` no longer imports `build_agent` eagerly
(deterministic skeleton tests stay google-adk-free); `ReviewerResponse`
uses the contract's `ShortText`/`Sha256` annotated types. Deferred minors
(recorded in HANDOFF): named-but-unmapped local deps in pyprojects are a
trap for out-of-convention installs; generic 503 handler maps model 400s
retryable; `previous_review_version` echo not cross-checked against the
supplied previous review (contract doesn't require it). All suites re-run
green after the fixes incl. the live gate (8 passed, ~30 s).

## Increment 2 — engineering reviewer

**Status: COMPLETE (2026-09-12). Live Vertex gate PASS.**

- Refactor first: the reviewer invocation contract moved into
  `agent_kit.adapter` (assembly agreement checks, single-turn run, FastAPI
  shell + ErrorEnvelope mapping) parameterized by
  (slug, perspective, build_agent, load_config, version). The
  business-reviewer adapter is now a thin binding (same tests, still green).
- `agents/engineering-reviewer/engineering_reviewer/agent.py` — ADK builder
  (engineering_reviewer, serving-safe mirror output_schema).
- `deploy/compose/adapters/engineering-reviewer/` — thin binding + tests,
  incl. the plan's prompt-distinctness check (engineering vs business
  prompt hashes differ).
- Makefile: `engineering-reviewer-adapter-test`, `engineering-reviewer-live-test`.

Checks (main PC): agent-kit **24** (adapter-core tests added),
agents 3×4, business adapter **6+2 skipped** (post-refactor),
engineering adapter **7+1 skipped** deterministic / **8 passed** live
(~26 s, 1 real model call): golden story-14 (engineering-weak) →
schema-valid engineering `ReviewReport` with ≥1 finding.

No independent review this increment: the change is the reviewed
increment-1 pattern re-bound (thin binding + one new prompt-distinctness
test); threshold per development-rules not met.

Cost so far this session: 5 real flash calls total (2+2+1).
