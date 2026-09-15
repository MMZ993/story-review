# Development Plan (home phase)

High-level, risk-first ordering. Each phase lists scope, exit criteria, and cost
notes. Before a phase starts, write its implementation plan (files, commands,
verification) — this document stays one level above that. Update the status inline
as work proceeds.

Status legend: planned / in progress / done (+ evidence).

## Phase 0 — Environment & bootstrap — done (2026-09-05; runbooks 00–05)

Scope: trial project with billing; budget alert; Terraform bootstrap module (APIs,
service accounts + IAM grants per connectivity-identity.md, Cloud SQL instance, GCS
buckets, Artifact Registry repo, Secret Manager skeletons); ADC setup; Makefile
skeleton; runbook started.

Exit criteria:
- an ADK agent runs locally and calls Gemini via Vertex AI (ADC, no deployed infra) — done (runbooks/05; gemini-2.5-flash, europe-west4, PASS),
- `terraform apply` reproducible from clean (destroy + apply) with only tfvars
  changing — not re-proven by a destroy cycle (destructive; deferred unless
  needed), config is tfvars-driven,
- trial-account availability checks from local-decisions.md D1 recorded — done
  (billing + Vertex evidenced; Agent Engine bullets deferred to the Phase 1
  spike by design).

Cost: negligible (Vertex AI tokens only).

## Phase 1 — Connectivity spike (blocking prerequisite) — done (2026-09-06; Runbook 06)

Scope: the documented spike — Agent Engine agent → authenticated Cloud Run MCP →
Cloud SQL session persist → restore. Minimal throwaway services (one trivial agent,
one trivial MCP server). Record exact ingress settings, token audiences, identities,
passing trace.

Exit criteria: the full chain works end-to-end with evidence; or a documented,
simplified fallback decided per connectivity-identity.md (e.g. default ingress with
mandatory ID-token auth) — done: end-to-end trace passed with the D8 default-ingress,
ID-token-authenticated fallback; all disposable resources were torn down.

Cost: small — one Agent Engine resource, one Cloud Run service, Cloud SQL already up.
Teardown after recording evidence.

Deferred item (recorded 2026-09-06): the reverse leg — Cloud Run (orchestration)
→ Agent Engine — was **not** spike-tested (Phase 1 tested Agent Engine → Cloud Run
MCP only). Assessed low-risk (outbound call from Cloud Run to a public Google API
with ADC); live proof is folded into Phase 8 exit criteria rather than reopening
Phase 1.

## Phase 2 — Shared schemas package — done (2026-09-06; Runbook 07; post-reviewed session 11, suite 147)

Scope: `shared/review_schemas` implementing docs/design/schemas.md exactly (strict
models, validators, error taxonomy) + unit tests.

Exit criteria: model/validator unit tests pass; package installable from
`requirements.lock` by path.

Cost: none.

## Phase 3 — Mock dataset — done (2026-09-07/09; Runbook 08 + 09; completion review session 16, dataset 28 / schemas 147 passed)

Scope: `dataset/stories/` + `dataset/expected/` — seven scenario types
(clean, business-weak, engineering-weak, conflicting, partial-resolution,
unresolvable, hidden-conflict) across templates T1–T6, with scenario-canonical
expected-file contracts per quality/mock-data.md (D9 amendment 2).

Exit criteria: expected files validate against the Phase 2 schemas; stories load
through a trivial harness. Met: `make dataset-test` 28 passed;
`make review-schemas-test` 147 passed; independent read-only completion review
(session 16): Ready to close — 0 Critical/Important, 3 Minor doc-drift findings
all fixed (docs expected-file contract realigned; story-templates matrix
corrected to seven scenarios; canonical-facts T5 cross-reference added).

Cost: none.

## Phase 4 — MCP servers — COMPLETE (sessions 17–25; increments 0–5, both exit gates green, completion review 2026-09-10 Ready-to-close with D10 amendment 7; plan in plans/phase-4-mcp-servers.md)

Scope: story → artifact → report (increasing complexity), each with Dockerfile,
deploy script, and contract tests; local compose service definitions. Story image
copies only `dataset/stories/`.

Exit criteria: contract tests pass against local compose services; each deploys to
Cloud Run via Makefile target and answers a smoke call.

Cost: Cloud Run (min 0) + GCS for smoke tests; minimal.

## Phase 5 — Agents — COMPLETE (sessions 27–31; increments 0–4 all green, exit gate (example-interaction walkthrough over compose HTTP) PASS, completion review 2026-09-12 Ready-to-close — 1 Important Makefile ADC-guard fix applied same session; plan in plans/phase-5-agents.md, evidence in runbooks/11-agents.md)

Scope: business-reviewer and engineering-reviewer → synthesis → facilitator, in that
order. Prompts in `prompts/`, config.yaml per agent, local ADK adapters in compose
(same invocation interface as Agent Engine). Facilitator last: McpToolset wiring,
typed `FacilitatorTurnOutput`, delegation validation + corrective re-prompting.

Exit criteria: each agent produces schema-valid typed output against Vertex AI
locally; facilitator delegation behaves per example-interaction.md scenario.

Cost: Vertex AI tokens only.

## Phase 6 — Orchestration (FastAPI) — COMPLETE (sessions 32–38; increments 0–5 all green, exit gate (live integration suite over compose, 3 passed in 367 s) PASS, phase-close review 2026-09-13 Ready-to-close with 2 minors fixed same session; plan in plans/phase-6-orchestration.md, decisions D15 + amendments 1–3, evidence in runbooks/12-orchestration.md)

Scope: API contract (all endpoints), flows 1–3, gate precedence, turn leases,
idempotency (stored canonical responses), Cloud SQL records, direct MCP client
wrapper (timeouts/retries per observability.md), session reconciliation.

Exit criteria: integration tests against compose stack (local adapters) cover flows
1–4, gate outcomes, park-at-10, PO-acceptance path, idempotent retries.

Cost: Vertex AI tokens only.

## Phase 7 — Web UI (minimal chat MVP) — COMPLETE (sessions 39–50; increments 0–4 all green, walkthrough gate PASS, D18–D22 implemented, phase-close review 2026-09-20 Ready-to-proceed with 1 Important (missing public export) + 2 minors fixed same session; plan in plans/phase-7-webui.md, decisions D16–D22, evidence in runbooks/13-webui.md)

Scope: simple web client over the orchestration API (design change from TUI,
D16): pre-conversation story picker (list with hover preview / story detail
render before confirming selection), chat-style dialogue view for facilitator
turns (POST /turns with idempotency-key replay), report download via signed
URLs. Minimal MVP — no animations, no styling beyond basic usability. Consumes
the API contract as-is; no new server-side flows.

Exit criteria: the example-interaction.md walkthrough playable end-to-end from
a browser against the local stack.

Cost: Vertex AI tokens only.

## Phase 8 — Real GCP deployment & versioning proof — **COMPLETE** (closed 2026-09-16; plan: plans/phase-8-gcp-deployment.md, decisions D24; evidence: Runbook 14 increments 0–7)

Scope: deploy all units to Cloud Run + Agent Engine via runbook/Makefile; env
pointers; smoke tests; observability wiring (structured logs, traces, dashboards,
alerts); versioning proof: redeploy one agent as a new versioned resource, re-point,
roll back.

Exit criteria (all met): full system live on GCP over the public domain
(webui → orchestration → Agent Engine → MCP, CR→AE leg proven increment 4);
versioning/rollback proof live — facilitator redeployed as `facilitator-747d9d1`,
orchestration re-pointed forward/rollback/forward with a live flow-1 turn verified
on each revision (Runbook 14 §Increment 7); requirements-coverage rows for
deployment/versioning/observability moved to verified/implemented. Independent
phase-close review Ready-to-proceed (findings codified in Runbook 14 §Increment 7).
Deferred minors recorded there (env-pointer/version cross-check, two compaction
test nits, per-call summarizer client). D5 engine prune pending (owner-run).

## Phase 9 — Evaluation suite & tuning — planned

Scope: judge config + `prompts/judge.md`; expected-file test runner with
deterministic assertions; run modes (local compose preferred); **tuning loop over the
dataset stories and agent prompts until all required cases pass (D29)**; update
requirements-coverage.md statuses with evidence. Plan:
`docs-local/plans/phase-9-evaluation.md`.

Exit criteria: all required dataset cases pass (deterministic + judged) locally and
against dev; demo **deferred until the evaluation is complete (D29-1)**; coverage
table updated.

Cost: Vertex AI tokens (agents + judge) across cases.

## Cross-cutting

- Git tags per release from Phase 4 onward — the 1:1 tag↔resource mapping is the
  versioning proof's raw material.
- Runbook updated at every phase that touches deploy or environment.
- Implementation plan written per phase before it starts; kept next to this file or
  in `docs-local/plans/`.
