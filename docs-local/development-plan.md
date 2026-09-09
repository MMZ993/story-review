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

## Phase 5 — Agents — planned

Scope: business-reviewer and engineering-reviewer → synthesis → facilitator, in that
order. Prompts in `prompts/`, config.yaml per agent, local ADK adapters in compose
(same invocation interface as Agent Engine). Facilitator last: McpToolset wiring,
typed `FacilitatorTurnOutput`, delegation validation + corrective re-prompting.

Exit criteria: each agent produces schema-valid typed output against Vertex AI
locally; facilitator delegation behaves per example-interaction.md scenario.

Cost: Vertex AI tokens only.

## Phase 6 — Orchestration (FastAPI) — planned

Scope: API contract (all endpoints), flows 1–3, gate precedence, turn leases,
idempotency (stored canonical responses), Cloud SQL records, direct MCP client
wrapper (timeouts/retries per observability.md), session reconciliation.

Exit criteria: integration tests against compose stack (local adapters) cover flows
1–4, gate outcomes, park-at-10, PO-acceptance path, idempotent retries.

Cost: Vertex AI tokens only.

## Phase 7 — TUI — planned

Scope: client state machine per api-contract.md; session-ID persistence, spinner,
idempotency-key replay, report download via signed URLs.

Exit criteria: the example-interaction.md walkthrough playable end-to-end from the
TUI against the local stack.

Cost: Vertex AI tokens only.

## Phase 8 — Real GCP deployment & versioning proof — planned

Scope: deploy all units to Cloud Run + Agent Engine via runbook/Makefile; env
pointers; smoke tests; observability wiring (structured logs, traces, dashboards,
alerts); versioning proof: redeploy one agent as a new versioned resource, re-point,
roll back.

Exit criteria: full system works on GCP; **including live proof of the
Cloud Run (orchestration) → Agent Engine leg, untested in Phase 1** (verify
`sa-orchestration` IAM incl. `roles/aiplatform.user` for session create, and
`:streamQuery?alt=sse` from Cloud Run — see Runbook 06 gotchas 3–4); versioning/rollback
evidence recorded;
requirements-coverage rows for deployment/versioning/observability move toward
verified.

Cost: the main spend phase — Agent Engine resources, Cloud Run, Cloud SQL uptime,
Vertex AI. Prune Agent Engine resources per D5 after evidence.

## Phase 9 — Evaluation suite & demo — planned

Scope: judge config + `prompts/judge.md`; expected-file test runner with
deterministic assertions; run modes (local compose preferred); demo script using the
same stories; update requirements-coverage.md statuses with evidence.

Exit criteria: all required dataset cases pass (deterministic + judged) locally and
against dev; demo rehearsed; coverage table updated.

Cost: Vertex AI tokens (agents + judge) across cases.

## Cross-cutting

- Git tags per release from Phase 4 onward — the 1:1 tag↔resource mapping is the
  versioning proof's raw material.
- Runbook updated at every phase that touches deploy or environment.
- Implementation plan written per phase before it starts; kept next to this file or
  in `docs-local/plans/`.
