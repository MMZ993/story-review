# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. Last updated: 2026-09-05 (session 3, in progress).

## Where we are

- Phase: **0 — Environment & bootstrap, in progress**
  (docs-local/development-plan.md)
- Docs design: complete and frozen on branch `docs/initial-frozen`; home-phase
  docs in `docs-local/`.

## Previous Session Summary

- gcloud CLI 583.0.0 via mise; authenticated (user + ADC); quota project set.
- Dedicated GCP project with billing linked; budget alert `trial-80pct` (80% of
  trial credits). Identifiers in gitignored `infra/envs/home.env`.
- Runbooks 00-tooling and 01-gcloud-setup are fully executed and evidenced.
- Runbook 02 is executed and evidenced at
  `docs-local/runbooks/02-terraform-bootstrap.md`. It adds a pinned `infra/`
  Terraform root, an idempotent API-enablement module, ignored
  `infra/envs/home.tfvars`, and tracked provider lockfile. The reviewed apply
  enabled its ten APIs (10 added, 0 changed, 0 destroyed).
- Runbook 03 executed and evidenced (`docs-local/runbooks/03-service-accounts.md`):
  module `infra/modules/service-accounts` creates the nine identity-model SAs
  (deployer + 8 runtime) and the project-level grants valid pre-data-plane
  (deployer: run.admin / aiplatform.user / artifactregistry.writer /
  cloudsql.editor + actAs on each runtime SA; orchestration: aiplatform.user +
  tokenCreator on itself). Applied 2026-09-05: 23 added, 0 changed, 0 destroyed;
  verified via gcloud SA list, IAM policy, and terraform output.
- D6 recorded (local-decisions.md): evaluation judge is not a deployed agent —
  ADC locally, deployer SA's `aiplatform.user` in CI; `sa-evaluator` is a
  documented fallback only.
- Runbook 04 executed and evidenced (`docs-local/runbooks/04-resource-skeletons.md`):
  four new modules — Artifact Registry `service-images`, GCS bucket
  `<project>-artifacts` (report-prefix IAM condition, 90d lifecycle), Cloud SQL
  POSTGRES_16 `db-f1-micro` (ENTERPRISE edition, public IP + IAM auth — the
  documented fallback, decision deferred to Phase 1 spike), 8 empty
  per-service secrets with least-privilege secretAccessor. Net totals across
  three applies (two partial failures: ENTERPRISE_PLUS tier rejection,
  no-connectivity rejection — gotchas in infra-rules): 34 added. All verified
  via outputs and gcloud cross-checks.
- `.gitignore` now protects environment tfvars, Terraform state, build staging,
  and scratch files, while retaining `.terraform.lock.hcl` for reproducibility.
- Working agreement: AGENTS.md + task-specific rules in
  `.agents/development-rules.md` and `.agents/infra-rules.md`.

- Observation pending future increment: project default compute SA holds
  `roles/editor` from project creation.

## Verification and Review (latest)

- Runbook 01 checklist fully evidenced (auth, ADC, project, billing, budget).
- Runbook 02 static checks passed: `terraform -chdir=infra validate` and
  `git diff --check`; no pre-commit configuration exists. The initial
  `fmt -check` identified only alignment in ignored `home.tfvars`; the Runbook 02
  generator is corrected to produce formatted content.
- The owner produced and reviewed `home-api-enable.tfplan`: 10 additions and no
  changes or destroys, exactly the expected API services. Apply completed successfully
  in 4–24 seconds, with no propagation retry required. Post-apply `gcloud services
  list --enabled` and `terraform state list` each confirmed all ten managed services.

- Runbook 04: static checks passed; plan reviewed (34 add / 0 change / 0
  destroy); post-apply gcloud cross-checks for SQL instance, AR repo, bucket,
  and secrets all matched terraform outputs.

## Remaining Tasks

- Next reviewed Terraform increment: Cloud SQL, GCS, Artifact Registry, and
  Secret Manager skeletons in cost-aware increments (deferred grants:
  secretAccessor, Cloud SQL IAM login, GCS bucket roles attach with them;
  optionally tighten default-compute-SA `roles/editor`).
- Makefile skeleton (setup/bootstrap targets).
- Phase 0 exit check: minimal local ADK agent → Gemini via Vertex AI (ADC).

## Next Steps

1. Runbook 05: D1 trial-availability checks + local ADK → Gemini via Vertex AI
   smoke test (Phase 0 exit check), plus the Makefile skeleton.
2. Add the Makefile skeleton, then perform the local ADK/Vertex smoke test
   (Phase 0 exit check) and record D1 trial-availability checks.

## Important Notes

- Deployment pipeline stance: none yet — local scripts + runbook only; pipelines
  written at promotion (local-decisions.md D3).
- Trial credits: 0 used of zł1,114, expire 2026-12-05.
- Old default trial project exists but is unused/ignored.
