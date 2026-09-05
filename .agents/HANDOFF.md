# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. Last updated: 2026-09-05 (session 6, Phase 1 in progress;
increments 1–4 done; increment 5 remains).

## Where we are

- Phase: **1 — Connectivity spike: IN PROGRESS** (Runbook 06,
  `docs-local/runbooks/06-connectivity-spike.md`). Increments 1–4 done;
  increment 5 (decision-gate record + owner-run teardown) remains.
- Docs design: complete and frozen on branch `docs/initial-frozen`; home-phase
  docs in `docs-local/`.
- Git remote `origin` = private GitLab (`mmz-personal/capstone-project`);
  owner pushes (`main` + `docs/initial-frozen`).

## Previous Session Summary

Session 6 (2026-09-05, evening) — Runbook 06 increment 4 EXECUTED, PASS:
Agent Engine caller (`spike_agent/{agent,tools,transport}` +
`deploy-agent.sh`/`run-agent-trace.sh`) deployed and proven with the two-request
persist/restore trace (engine `3787430529595342848`, correlation
`1fe5d7f691e84ff689a2c9ba73b49dbf`; PASS asserted by jq guards). **Ingress
gate: internal ingress FAILED from Agent Engine (edge 404, no request logs);
approved fallback applied** — ingress `INGRESS_TRAFFIC_ALL` + mandatory
ID-token audience auth + invoker-only IAM, recorded as **D8** in
local-decisions.md. Extra applies during debugging: sa-facilitator →
roles/aiplatform.user (sessions permission), two MCP image rollouts (final
`spike-connectivity-mcp:20260905-2204-d0e9a43`, adds `requests`). Eight
gotchas recorded in Runbook 06 §Increment 4 (adk agent_engine_id update-only
400 + exit-0-on-failure; aiplatform.sessions.create needed; `:streamQuery`
not `:query` + snake_case events + JSON-not-SSE body; mcp 2.1.1 headers
kwarg removal; missing `requests` package; structuredContent fallback;
log-line wrapping vs correlation-ID search). Superseded agent engines deleted
by owner; spike code/tests/docs updated but NOT yet committed.

Session 5 (2026-09-05) — Runbook 06 increment 1: confirmed
interfaces (google-adk 2.8.0, mcp 2.1.1, google-cloud-aiplatform 2.1.0;
Agent Engine runtime SA via `.agent_engine_config.json` → `service_account=`);
14 deterministic tests for store/MCP-contract/agent-probe, implemented
`spikes/connectivity/{spike_mcp,spike_agent}` with locks and
`make spike-connectivity-test`; independent review findings fixed.
Increment 2: enabled `cloudsql.iam_authentication` + 4 IAM db users (Terraform;
two gotchas: flag name dot, SA username without `.gserviceaccount.com`);
applied spike schema/table/grants via one-time postgres admin session through
the Cloud SQL Python Connector on port 3307 (5432 blocked here; postgres
cannot SET ROLE to IAM roles). D7: admin password lives in gitignored
`home.env`, rotation procedure in Runbook 06 §2.5; Alembic rejected (D2 note).
Increment 2 committed as `9d92148`.
Increment 3 (same session, later block): Cloud Run MCP service —
`spike_mcp/{store_sql,auth_middleware,app,main}.py` (asyncpg over the
`/cloudsql` unix socket with IAM-db-auth token; pure-ASGI ID-token
middleware, fail-closed 503 on unset audience; stateless streamable-HTTP
app + `/healthz`), Dockerfile + `deploy-mcp.sh`, 12 new tests (26 total),
Terraform module `infra/modules/connectivity-spike` (count-gated on
`spike_mcp_image`) + root wiring. Independent review finding (check order)
fixed. Deployed via owner-run two-step apply (image
`spike-connectivity-mcp:20260905-1616-1bba7f7`, revision ...-00002) and
verified read-only via the Cloud Run v2 API. Commit pending at wrap-up.

Session 4 (2026-09-05) — verified the live Phase 0 inventory against Terraform:
project ACTIVE, billing enabled, all required APIs enabled, expected resource
counts present, and `terraform plan -detailed-exitcode` reported no drift. The
sanitized evidence is in Runbook 05. Wrote the Phase 1 implementation plan:
`docs-local/plans/phase-1-connectivity-spike.md`. It scopes the disposable
Agent Engine → authenticated Cloud Run MCP → Cloud SQL persist/restore proof,
initial internal-ingress test, permitted ID-token-authenticated fallback, exact
evidence, cost guardrails, and owner-run teardown.

Session 3 (2026-09-05) — finished the whole Phase 0 bootstrap in three
reviewed, evidenced Terraform/check increments, each committed atomically:

- **Runbook 03** (`docs-local/runbooks/03-service-accounts.md`):
  `infra/modules/service-accounts` — nine identity-model SAs (deployer + 8
  runtime) with pre-data-plane grants (deployer: run.admin / aiplatform.user /
  artifactregistry.writer / cloudsql.editor + actAs on each runtime SA;
  orchestration: aiplatform.user + tokenCreator on itself). Apply: 23 added.
  Commit `3c580d8`.
- **Runbook 04** (`docs-local/runbooks/04-resource-skeletons.md`): four new
  modules — Artifact Registry `service-images`; GCS bucket `<project>-artifacts`
  (report-prefix IAM condition, 90d report lifecycle); Cloud SQL POSTGRES_16
  `db-f1-micro`, ENTERPRISE edition, public IP + IAM-db-auth (fallback; final
  connectivity deferred to the Phase 1 spike — owner agreed); 8 empty
  per-service `<project>-<service>-config` secrets with least-privilege
  secretAccessor (own secret per runtime SA; deployer on all). Net: 34 added
  across three applies (two partial failures, gotchas recorded). Commit
  `f09bbf8`.
- **Runbook 05** (`docs-local/runbooks/05-phase0-exit-checks.md`):
  `scripts/smoke_vertex.py` (ADK LlmAgent + InMemoryRunner → Vertex via ADC) +
  Makefile skeleton (`smoke-vertex`, `terraform-plan/apply`, compose stubs).
  `make smoke-vertex` PASS (`gemini-2.5-flash`, europe-west4). Commit `1be8442`.
- **D6** (local-decisions.md): evaluation judge is not a deployed agent — ADC
  locally, deployer SA's aiplatform.user in CI; `sa-evaluator` is fallback only.
- Earlier sessions (context): runbooks 00–02 (tooling, gcloud setup/auth/ADC/
  billing/budget, Terraform API-enablement root + ten APIs).

## Verification and Review

- All three runbooks: `init`/`fmt -check -recursive`/`validate` passed; plans
  reviewed by the owner before each apply; applies matched expected counts.
- Runbook 03: gcloud SA list, project IAM policy, and terraform outputs matched
  the plan exactly; no drift.
- Runbook 04: gcloud cross-checks (SQL instance, AR repo, bucket, 8 secrets)
  matched terraform outputs. Gotchas recorded in `.agents/infra-rules.md`:
  Cloud SQL ENTERPRISE edition required for `db-f1-micro`; Cloud SQL requires
  at least one connectivity path.
- Runbook 05: billing re-confirmed (`billingEnabled=True`); smoke test failed
  once on an ADK API detail (`create_session` requires `user_id`), fixed,
  then PASS. D1 checks 1–2 evidenced; Agent Engine bullets deferred to the
  Phase 1 spike by design (recorded in the runbook and development-plan).

## Remaining Tasks

- Runbook 06 increment 5: record the ingress decision outcome (D8 already
  drafted), owner-run teardown of spike resources (Cloud Run module,
  `spike_mcp_image=""` apply, agent engine `3787430529595342848`, AR images,
  DB marker rows), and final cost check.
- Commit session-6 changes (spike agent code/scripts, terraform spike module,
  runbook 06, D8, HANDOFF) when the owner asks.
- First recurring costs now live: Cloud SQL `db-f1-micro` (~$7–10/mo) plus
  per-request Cloud Run + Agent Engine usage (min instances 0) and the AR
  image (negligible).
- Optional later increment: tighten the default compute SA's `roles/editor`
  (pre-existing from project creation).
- Phase 0 exit criterion "terraform apply reproducible from clean (destroy +
  apply)" was not re-proven by a destroy cycle (destructive, deferred unless
  needed); config is tfvars-driven.

## Next Steps

1. (done at session-6 wrap-up: changes committed as one atomic increment-4
   commit; owner pushes.)
2. Fresh session: Runbook 06 increment 5 per
   `docs-local/plans/phase-1-connectivity-spike.md` — confirm the D8 record,
   owner-run teardown (agent engine `3787430529595342848`, spike module via
   `spike_mcp_image=""` apply, AR images, DB marker rows), final cost check.

## Important Notes

- Deployment pipeline stance: none yet — local scripts + runbook only; pipelines
  written at promotion (local-decisions.md D3).
- Git: push state is the owner's; at last wrap-up several local commits
  (`c728b37`, `44b03ef`, `9d92148`, plus the pending increment-3 commit)
  awaited push — check `git status -sb` before assuming the remote is current.
- Spike resources live (removed in increment 5): Cloud Run service
  `spike-connectivity-mcp` (image `…:20260905-2204-d0e9a43`, ingress ALL per
  D8), agent engine `3787430529595342848`, AR images (3 tags),
  `roles/cloudsql.client` + `roles/aiplatform.user` grants for spike SAs.
- Trial credits: near-zero used of zł1,114, expire 2026-12-05. First recurring
  cost now live: Cloud SQL `db-f1-micro` (~$7–10/mo equivalent); can be paused
  with `gcloud sql instances patch --activation-policy NEVER` when idle.
- Old default trial project exists but is unused/ignored.
- `git push` is the owner's; remote added this session, owner pushes both
  branches.
