# STATE.md — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. Last updated: 2026-09-05.

## Where we are

- Phase: **0 — Environment & bootstrap, in progress**
  (docs-local/development-plan.md)
- Docs design: complete and frozen on branch `docs/initial-frozen`; home-phase
  docs in `docs-local/`.

## Done

- gcloud CLI 583.0.0 via mise; authenticated (user + ADC); quota project set.
- Dedicated GCP project with billing linked; budget alert `trial-80pct` (80% of
  trial credits). Identifiers in gitignored `infra/envs/home.env`.
- `.gitignore` (env files, terraform state, build staging, trash/).
- Runbooks: 00-tooling, 01-gcloud-setup (fully executed + evidenced).
- AGENTS.md working agreement + this state file.

## Next

1. Runbook 02 — terraform skeleton: `infra/` structure, `envs/home.tfvars`, API
   enablement module (iam, aiplatform, run, sqladmin, storage, artifactregistry,
   secretmanager, ...). No more ad-hoc `gcloud services enable`.
2. Makefile skeleton (setup/bootstrap targets).
3. Phase 0 exit check: minimal local ADK agent → Gemini via Vertex AI (ADC).

## Open questions / notes

- Deployment pipeline stance: none yet — local scripts + runbook only; pipelines
  written at promotion (local-decisions.md D3).
- Trial credits: 0 used of zł1,114, expire 2026-12-05.
