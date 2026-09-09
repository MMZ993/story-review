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
