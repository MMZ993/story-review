# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. Last updated: 2026-09-05 (session 3 close).

## Where we are

- Phase: **0 — Environment & bootstrap: COMPLETE (2026-09-05).**
  Next: **Phase 1 — Connectivity spike** (docs-local/development-plan.md).
- Docs design: complete and frozen on branch `docs/initial-frozen`; home-phase
  docs in `docs-local/`.
- Git remote `origin` = private GitLab (`mmz-personal/capstone-project`);
  owner pushes (`main` + `docs/initial-frozen`).

## Previous Session Summary

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

- Phase 1 connectivity spike implementation plan (write before any execution,
  per the development plan's cross-cutting rule).
- Optional later increment: tighten the default compute SA's `roles/editor`
  (pre-existing from project creation).
- Phase 0 exit criterion "terraform apply reproducible from clean (destroy +
  apply)" was not re-proven by a destroy cycle (destructive, deferred unless
  needed); config is tfvars-driven.

## Next Steps

1. Write the Phase 1 spike implementation plan (docs-local/plans/ or next to
   the development plan): trivial agent + trivial MCP server, exact evidence to
   capture (ingress settings, token audiences, identities, trace).
2. Execute the spike as Runbook 06 in small reviewed steps; teardown after
   evidence.
3. Then Phase 2 (shared schemas package).

## Important Notes

- Deployment pipeline stance: none yet — local scripts + runbook only; pipelines
  written at promotion (local-decisions.md D3).
- Trial credits: near-zero used of zł1,114, expire 2026-12-05. First recurring
  cost now live: Cloud SQL `db-f1-micro` (~$7–10/mo equivalent); can be paused
  with `gcloud sql instances patch --activation-policy NEVER` when idle.
- Old default trial project exists but is unused/ignored.
- `git push` is the owner's; remote added this session, owner pushes both
  branches.
