# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. Last updated: 2026-09-06 (session 7 addendum: Cloud Run → Agent Engine leg recorded as deferred test item).

## Where we are

- Phase: **2 — Shared schemas: PLANNED** (`docs-local/plans/phase-2-shared-schemas.md`).
  Phase 1 is complete: its end-to-end trace passed with D8 fallback and all spike
  resources were torn down (Runbook 06 increment 5).
- Docs design: complete and frozen on branch `docs/initial-frozen`; home-phase
  docs in `docs-local/`.
- Git remote `origin` = private GitLab (`mmz-personal/capstone-project`);
  owner pushes (`main` + `docs/initial-frozen`).

## Previous Session Summary

Session 7 addendum (2026-09-06) — identified and recorded a Phase 1 test gap: the **Cloud Run (orchestration) → Agent Engine** direction was never spike-tested (Phase 1 proved only Agent Engine → Cloud Run MCP). Assessed low-risk (outbound call from Cloud Run to a public Google API with ADC); decision: do not reopen Phase 1, fold live proof into Phase 8 exit criteria. `development-plan.md` updated (Phase 1 deferred item + Phase 8 exit criterion incl. `sa-orchestration` `aiplatform.user` and `:streamQuery?alt=sse` checks per Runbook 06 gotchas 3–4).

Session 7 (2026-09-06) — reviewed the completed Phase 1 evidence and wrote the
Phase 2 master implementation plan at `docs-local/plans/phase-2-shared-schemas.md`.
The plan defines the versioned `shared/review_schemas` package layout, dependency
locks, test-first implementation increments, independent-review gate, and zero-cloud
scope. `development-plan.md` now marks Phase 1 done; Cloud SQL status confirmed
`STOPPED/NEVER`. Plan reviewed with the owner: the domain group is split across
`review/synthesis/facilitator/judge` modules (module-size rule), and the development
rules gained a code-reads-like-a-book helper-extraction rule. No application code
changed and no environment action occurred.

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

- Implement Phase 2 from `docs-local/plans/phase-2-shared-schemas.md`: start
  with the failing strict-primitives tests, then create the versioned package and
  locks; request independent review before accepting the shared contract.
- Create a Phase 2 runbook/evidence entry when implementation starts or completes.
- Optional later increment: tighten the default compute SA's `roles/editor`
  (pre-existing from project creation).
- Phase 0 exit criterion "terraform apply reproducible from clean (destroy +
  apply)" was not re-proven by a destroy cycle (destructive, deferred unless
  needed); config is tfvars-driven.

## Next Steps

1. Review and approve `docs-local/plans/phase-2-shared-schemas.md` before code work.
2. Implement its increment 1 test-first, using the frozen schema document as the
   field-level checklist.
3. Keep Cloud SQL paused; Phase 2 has no database or GCP dependency.

## Important Notes

- Deployment pipeline stance: none yet — local scripts + runbook only; pipelines
  written at promotion (local-decisions.md D3).
- Git: push state is the owner's; at last wrap-up several local commits
  (`c728b37`, `44b03ef`, `9d92148`, plus the pending increment-3 commit)
  awaited push — check `git status -sb` before assuming the remote is current.
- Spike resources REMOVED (increment 5, 2026-09-06): Cloud Run service, agent
  engine, AR images, and `spike` schema gone; terraform plan clean (no drift).
  Spike source, tests, and runbook evidence preserved in git.
- Cloud SQL instance is **PAUSED** (`make db-pause`, 2026-09-06, state
  STOPPED/NEVER) — run `make db-resume` before any phase that needs the DB.
  New Make targets `db-pause`/`db-resume`/`db-status` (PROJECT_ID-guarded).
- Trial credits: near-zero used of zł1,114, expire 2026-12-05.
- Old default trial project exists but is unused/ignored.
- `git push` is the owner's; remote added this session, owner pushes both
  branches.
