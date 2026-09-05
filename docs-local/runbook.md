# Runbook (home phase)

Living document. Every procedure that touches the environment, deployment, or money
gets written here as soon as it exists — the phase plans reference these entries.
Pipeline translation at promotion reads this file.

Detailed commands live in [runbooks/](runbooks/) — this file stays the checklist.

## One-time setup (Phase 0)

- [x] Install gcloud via mise (runbooks/00-tooling.md; 2026-09-05)
- [x] gcloud auth + ADC (runbooks/01-gcloud-setup.md; 2026-09-05)
- [x] Set project + region config (2026-09-05)
- [x] Budget alert at 80% of trial credits (2026-09-05)
- [x] `terraform init && terraform apply` (API-enablement bootstrap; 2026-09-05)
- [x] Service accounts + bootstrap IAM, 9 SAs / 23 resources (runbooks/03-service-accounts.md; 2026-09-05)
- [x] Resource skeletons: AR repo, GCS bucket, Cloud SQL, 8 secrets / 34 resources (runbooks/04-resource-skeletons.md; 2026-09-05)
- [x] Record trial-account availability check results (runbooks/05-phase0-exit-checks.md; 2026-09-05 — Vertex/billing evidenced; Agent Engine deferred to Phase 1 spike)

## Local development loop

- [ ] `make compose-up` — orchestration + MCP services + adapters + substitutes
- [ ] `make compose-down`
- [x] Vertex AI env: `GOOGLE_GENAI_USE_VERTEXAI=true`,
      `GOOGLE_CLOUD_PROJECT=<home-project-id>`, `GOOGLE_CLOUD_LOCATION=europe-west4`
      (wrapped by `make smoke-vertex`; 2026-09-05)
- [x] Spike tests: `make spike-connectivity-test` — offline deterministic
      store/contract/agent-probe tests (runbooks/06-connectivity-spike.md §1; 2026-09-05)

## Maintenance procedures

- [x] Cloud SQL admin bootstrap (`make spike-db-bootstrap`, one-time schema +
      grants via Cloud SQL Python Connector; runbooks/06-connectivity-spike.md §2.2; 2026-09-05)
- [ ] Cloud SQL admin password rotation (owner-run, interactive;
      runbooks/06-connectivity-spike.md §2.5; rotate at phase end or on machine sharing — D7)

## Deploy procedures (fill in per phase)

- [ ] Cloud Run: story / artifact / report / orchestration
- [ ] Agent Engine: facilitator / business-reviewer / engineering-reviewer / synthesis
- [ ] Cloud SQL migrations: `deploy/cloud-sql/run-migrations.sh`
- [ ] Env-pointer switching + rollback
- [ ] Smoke tests per unit

## Teardown / cost control

- [ ] Prune superseded Agent Engine resources (keep N-1, after evidence recorded)
- [ ] Stop/scale-down Cloud SQL when idle for extended periods
- [ ] `terraform destroy` for full teardown (recreate via apply + migrations)

## Evidence log

Append entries: date, phase, what was proven, artifact path / correlation ID.

- 2026-09-05 — Phase 0 — Terraform API-enablement bootstrap applied and verified:
  ten expected services enabled; Terraform state lists ten managed
  `google_project_service` resources. Evidence:
  `runbooks/02-terraform-bootstrap.md`.
- 2026-09-05 — Phase 1 — connectivity spike increment 1: interfaces confirmed
  (adk 2.8.0, mcp 2.1.1, Agent Engine runtime-SA support), 14 deterministic
  tests passing. Evidence: `runbooks/06-connectivity-spike.md` §1.
- 2026-09-05 — Phase 1 — connectivity spike increment 2: IAM db auth enabled
  (+flag, 4 IAM users; Terraform), spike schema/table/grants applied via
  admin session. Evidence: `runbooks/06-connectivity-spike.md` §2.
