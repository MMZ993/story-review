# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. Last updated: 2026-09-05.

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
- `.gitignore` now protects environment tfvars, Terraform state, build staging,
  and scratch files, while retaining `.terraform.lock.hcl` for reproducibility.
- Working agreement: AGENTS.md + task-specific rules in
  `.agents/development-rules.md` and `.agents/infra-rules.md`.

## Verification and Review

- Runbook 01 checklist fully evidenced (auth, ADC, project, billing, budget).
- Runbook 02 static checks passed: `terraform -chdir=infra validate` and
  `git diff --check`; no pre-commit configuration exists. The initial
  `fmt -check` identified only alignment in ignored `home.tfvars`; the Runbook 02
  generator is corrected to produce formatted content.
- The owner produced and reviewed `home-api-enable.tfplan`: 10 additions and no
  changes or destroys, exactly the expected API services. Apply completed successfully
  in 4–24 seconds, with no propagation retry required. Post-apply `gcloud services
  list --enabled` and `terraform state list` each confirmed all ten managed services.

## Remaining Tasks

- Expand Terraform bootstrap with the planned service accounts/IAM, Cloud SQL, GCS,
  Artifact Registry, and Secret Manager skeletons in reviewed increments.
- Makefile skeleton (setup/bootstrap targets).
- Phase 0 exit check: minimal local ADK agent → Gemini via Vertex AI (ADC).

## Next Steps

1. Design the next reviewed Terraform increment: service accounts and least-privilege IAM.
2. Continue the Terraform bootstrap with Cloud SQL, GCS, Artifact Registry, and Secret
   Manager skeletons in cost-aware increments.
3. Add the Makefile skeleton, then perform the local ADK/Vertex smoke test.

## Important Notes

- Deployment pipeline stance: none yet — local scripts + runbook only; pipelines
  written at promotion (local-decisions.md D3).
- Trial credits: 0 used of zł1,114, expire 2026-12-05.
- Old default trial project exists but is unused/ignored.
