# Phase 8 — Real GCP deployment & versioning proof plan

## Objective

Deploy the full system to Google Cloud (Cloud Run + Agent Engine + Cloud SQL +
GCS), prove the previously untested Cloud Run → Agent Engine leg, wire the
observability/Item-D facilitator-first slice, prove agent versioning/rollback
per `docs/operations/deployment.md`, and serve the Web UI publicly under the
owner's `mmz.sh` domain — with anonymous multi-user support (D24) added
**before** deployment so the deployed system is multi-user from day one.

Deployments this phase are **make-target/runbook driven from the owner's
machine** (D24-1); no CI/CD pipelines are built.

Per development-plan.md Phase 8 exit criteria: full system works on GCP
including the live CR→AE leg; versioning/rollback evidence recorded;
requirements-coverage rows for deployment/versioning/observability move toward
verified. Folded in: the deferred review minors due before cloud runs
(run-migrations.sh argv credential + startup race), the Item D observability
sub-item (facilitator-first), and the CR→AE test gap.

Cost: the main spend phase — Cloud SQL uptime, Cloud Run, Agent Engine,
Vertex AI. Prune Agent Engine resources per D5/D24-5 after the versioning
proof; pause Cloud SQL whenever not actively used.

## Preconditions

- Phase 7 complete and closed (session 50); D22 code live in the local stack.
- Owner decisions D24 settled (this plan's increment-0 section).
- Main PC: ADC/Vertex, terraform state, `infra/envs/home.env` — all
  cloud-write actions follow infra-rules (plan-before-apply, runbook
  codification, owner approval for tier-2/destructive).

## Increment-0 owner decisions (settled 2026-09-21 — D24)

1. **No CI/CD this phase**: deploys run from the local machine via
   Makefile targets + runbook; the designed `pipelines/*.yml` stay a
   documented intent for later.
2. **Web UI is deployed** as a Cloud Run service, served under the owner's
   Cloudflare-managed `mmz.sh` zone via a subdomain
   (`story-review.mmz.sh` — exact name owner's choice at increment 5).
   Route (Cloud Run custom-domain mapping vs Cloudflare-proxied CNAME)
   settled empirically at increment 5. Orchestration is reached through
   the webui's same-origin `/api` proxy (D17-1 shape).
3. **Anonymous multi-user scoping** (full, as proposed): `user_id` on
   sessions/story runs (migration 0005); one-active-session-per-story
   becomes per user; webui issues a 90-day sliding cookie (auto-refreshed
   on visit), forwarded as a header to orchestration through the proxy;
   artifacts follow per story-run for free. **No auth** for MVP — the
   public URL is backstopped by the budget alert; Cloudflare
   Access/rate-limiting can be added later without schema changes.
   **Retention**: 90 days; cleanup via an owner-run `make` purge command
   (destructive, tier-3), no scheduled job.
4. **Item D scope: facilitator-first** — tool/model/after-agent telemetry
   callbacks + the 50%/75% context-length policy on the facilitator only;
   the three stateless agents adopt the shared helper later.
5. **AE resource retention per D5**: keep at least N-1; superseded
   resources pruned after the versioning proof (owner-run destructive).

## Deliverables

- **User scoping**: `docs/` design change (api-contract: user header +
  scoping semantics; schemas: `user_id` on records + DB constraints),
  frozen cherry-pick; review-schemas bump; migration `0005_user_scoping.sql`;
  orchestration scoping across all endpoints (per-user story-run claim,
  session list/detail, 409 semantics); webui cookie manager + header
  forwarding + per-user picker lists.
- **Deploy fixes**: `deploy/cloud-sql/run-migrations.sh` — no credentialed
  DSN in argv (env-based), small retry around first psql contact.
- **Agent deploys**: `deploy/agents/{facilitator,business-reviewer,
  engineering-reviewer,synthesis}/deploy.sh` — stage from repo root,
  `adk deploy agent_engine`, versioned resource `<agent>-<git-sha>`, per-agent
  smoke script.
- **Orchestration Agent Engine client**: invocation via
  `:streamQuery?alt=sse` behind the frozen Phase-5 adapter contract,
  selected by env (`AGENT_<NAME>_RESOURCE` pointers vs adapter URLs —
  compose path unchanged); reconciliation against the AE session service;
  `sa-orchestration` IAM (`roles/aiplatform.user`) verified.
- **Cloud Run deploys**: `deploy/cloud-run/orchestration/deploy.sh` +
  `deploy/cloud-run/webui/deploy.sh` (+ webui added to
  `docs/operations/deployment.md`, frozen cherry-pick); Cloud SQL connector
  wiring, Secret Manager env, Artifact Registry images.
- **Observability**: structured logs with the correlation fields; Item D
  facilitator callbacks (content-safe before/after tool telemetry,
  model latency/token + 50/75% context policy, after-agent validation
  events); FastAPI gate/park application events; one Cloud Monitoring
  dashboard + alert policies (retry exhaustion, delegation-validation
  failure).
- **Makefile**: deploy/smoke targets per unit, `users-purge` (owner-run),
  versioning-proof helper.
- **Runbook 14** (`docs-local/runbooks/14-gcp-deployment.md`) — sanitized
  commands + evidence per increment.
- `docs/quality/requirements-coverage.md` row updates at close.

## Implementation increments

### 0. Decisions, plan, run-migrations.sh fixes (local)

- Record D24; commit plan + runbook scaffold.
- Fix the two deferred run-migrations.sh minors (test-first where
  practical); `orchestration-test` stays green.

### 1. User scoping (docs-first, test-first, local)

- `docs/` change (api-contract, schemas) + frozen cherry-pick; settle the
  header name and scoping semantics exactly.
- review-schemas bump; migration 0005 (applied to compose Postgres).
- Orchestration: user context through all routes (cookie header via the
  proxy → per-user claims/lists); webui cookie manager.
- Gates: orchestration + webui suites green; deterministic multi-user tests
  (two users, same story, independent sessions); short live check on
  compose.

### 2. Cloud SQL live + migrations (cloud, tier-2 with owner approval)

- `db-resume`; run-migrations.sh against Cloud SQL (IAM auth) applying
  0001–0005; verify schema + IAM db users.
- Orchestration Cloud SQL connectivity validated (connector / unix socket
  `/cloudsql/<instance>`); local run against Cloud SQL smoke-checked, then
  `db-pause` if the next increment doesn't need it.

### 3. Agent Engine deploys (cloud, tier-2)

- Four `deploy/agents/*/deploy.sh`; smoke each deployed agent (schema-valid
  typed output, real Vertex). Record resource ids ↔ git tags.
- Cost note: Agent Engine resources stay up between increments (D5 pruning
  at the end); facilitator ADK sessions in Cloud SQL PostgreSQL via
  `DatabaseSessionService` (IAM login — D24 amendment 1; decide DB/schema
  placement with the records schema at the increment).

### 4. Orchestration AE client + live CR→AE gate (local dev + cloud)

Detailed breakdown (settled with the owner 2026-09-14, recorded as D25;
all four agents go via AE this increment — they are deployed anyway):

1. **AE client behind the existing seams** (`ReviewerClient`,
   `SynthesisClient`, `FacilitatorClient` protocols in
   `agent_clients.py`): wraps SDK `agent_engines.get` + `stream_query`
   (the pattern proven by `deploy/agents/smoke.py`, invoker role
   sa-orchestration); strict-schema validation of replies via the shared
   agent-kit schemas; events' snake_case `function_response` and
   concatenated-JSON quirks handled (Runbook 06 gotcha 4).
2. **Env-selected agent pointers**: `ORCH_AGENT_MODE=http|ae` + four
   engine resource pointers (engine ids + project/region). HTTP mode
   keeps compose/local tests unchanged; AE mode is live-only.
3. **Reconciliation (D25, option B)**: on a doubtful facilitator retry
   (stream died, result unknown), orchestration reads the facilitator's
   ADK session events from the Cloud SQL `facilitator` DB (over
   `:query`, like smoke's `list_sessions`) and matches a recorded reply
   by the rendered turn marker (D25 amendment 1) before re-invoking — true
   at-most-once facilitator execution. Reviewer/synthesis calls are
   single-shot at-least-once retries (a duplicate only wastes cost;
   no conversation state). Orchestration-side TurnRecord dedup
   (option A) is included as the fast path before any AE read-back.
4. **Deterministic tests**: constructed event streams for the AE client
   parser + reconciliation matcher (no LLM cost).
5. **Orchestration Cloud Run deploy**: build/push AR, `gcloud run deploy`
   with AE pointers, Cloud SQL connector (async gotchas from inc 3:
   `connect_async`, explicit `user`, per-call `close_async`), `PGSSLMODE`,
   GCS/signed-URL config; SA sa-orchestration.
6. **Facilitator clean-tree redeploy** (drop the `-dirty` label), smoke
   PASS, becomes the pointer target.
7. **Live gate**: deployed CR invokes all four AE agents (facilitator
   end-to-end proves Cloud SQL persistence); Runbook 06 gotchas 3–4
   checklist evidenced (invoker `aiplatform.user` + empty-stream 403
   symptom, IAM propagation, `:streamQuery?alt=sse`, snake_case events,
   short-prefix correlation-id log search); sanitized trace evidence in
   Runbook 14; identifier check before commit. Closes the CR→AE test
   gap (session 8) as a Phase 8 exit criterion.

- Implement the AE invocation path + env pointers; deterministic tests with
  the same fake-agent seam; reconciliation vs AE.
- Deploy orchestration to Cloud Run; **live gate**: deployed orchestration
  invokes one real AE agent (`:streamQuery?alt=sse`) — the Phase-1-deferred
  reverse leg, with trace evidence (Runbook 06 gotchas 3–4 checklist).

### 5. Web UI deploy + domain + walkthrough (cloud, tier-2)

- Deploy webui Cloud Run + `/api` proxy target; Cloudflare subdomain
  (settle route empirically); TLS verified.
- **Live gate**: example-interaction walkthrough from a browser over the
  public domain, two concurrent users on independent sessions (cookie
  scoping proof).

### 6. Observability + Item D (facilitator-first)

- Structured logging with correlation fields across orchestration + webui.
- Facilitator callbacks per Item D exit criteria (unit tests: attached +
  content-safe; 50% warn; 75% validated summary; validation failure keeps
  history). FastAPI gate/park events already partially exist — complete.
- Cloud Monitoring dashboard + the two designed alert policies.
- Integration trace contains the paired before/after tool events, model
  latency/token data, an after-agent validation event, a FastAPI gate
  event; requirements-coverage callback row moved per evidence.

### 7. Exit gate — versioning/rollback proof + close (cloud + docs)

- Redeploy one agent (facilitator or a reviewer) as `<agent>-<new-sha>`,
  unit-smoke it, re-point the orchestration env pointer, verify live, then
  roll back by re-pointing — evidence: tag↔resource map, before/after
  traces.
- D5 prune of superseded AE resources (owner-run destructive).
- Full-system smoke over the public domain; all suites green; independent
  read-only phase review; requirements-coverage updates; Phase 8 COMPLETE
  in development-plan; wrap-up reminders (`db-pause`, compose down).

## Verification gates

- Per increment: test-first deterministic checks (no LLM cost) where the
  behavior is testable; live cloud gates owner-approved and evidenced in
  Runbook 14 (sanitized — identifier check before any commit with
  evidence).
- Baselines must stay green: orchestration 116+11s, webui 12+vitest 77,
  review-schemas 176, agent-kit 104, facilitator adapter 3+1s, compose
  contract 20 (numbers move as user-scoping/Item-D tests land).
- Independent read-only subagent review per significant increment and at
  phase close.

## Exit criteria (from development-plan.md)

Full system works on GCP; live proof of the Cloud Run → Agent Engine leg
(sa-orchestration IAM incl. `roles/aiplatform.user`; `:streamQuery?alt=sse`
from Cloud Run — Runbook 06 gotchas 3–4); versioning/rollback evidence
recorded; requirements-coverage rows for deployment/versioning/observability
moved toward verified.

## Out of scope

- CI/CD pipelines (`pipelines/*.yml`) — later (D24-1).
- Latency/token callbacks on the stateless agents — later via the shared
  helper (D24-4).
- Real user auth (login), scheduled retention jobs, Cloudflare
  Access/rate-limiting — MVP decisions, revisit post-capstone (D24-3).
- Judge/evaluation — Phase 9.
- Cross-template full-matrix runs — future-extensions Item C.

## Risks and controls

- **Public unauthenticated URL spends Vertex tokens**: budget alert
  backstop; monitor spend at each cloud increment; add Cloudflare
  rate-limiting quickly if abused.
- **AE adapter/AE divergence**: the frozen Phase-5 invocation contract is
  the seam; deterministic fakes already implement it; reconciliation path
  re-verified against AE at increment 4 (as planned in Phase 6).
- **AE session backend for the facilitator**: resolved (D24 amendment 1) — Cloud SQL PostgreSQL `DatabaseSessionService` (IAM login) when deployed, local Postgres for local runs; no change to the adapter's current mechanism.
- **Cloud SQL uptime cost**: resume only for increments that need it;
  `db-pause` at every wrap-up (standing rule).
- **Trial credits**: track spend per increment in Runbook 14; prune AE
  resources at the versioning proof.
- **Cloudflare + Cloud Run TLS interaction**: two viable routes
  pre-identified; settle empirically at increment 5 before touching DNS.

## References

- `docs/operations/deployment.md` (layout, versioning/rollback),
  `docs/operations/connectivity-identity.md` (principals, ingress,
  audiences), `docs/design/observability.md` (timeouts, callbacks,
  dashboards), `docs/design/api-contract.md` / `schemas.md` (user-scoping
  design change), `docs/design/agents.md` (session semantics),
  `docs-local/runbooks/06-connectivity-spike.md` (gotchas 3–4),
  `docs-local/plans/future-extensions.md` Item D,
  `docs-local/local-decisions.md` D5, D17, D24.
