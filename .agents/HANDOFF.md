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
- `.gitignore` (env files, terraform state, build staging, trash/).
- Runbooks: 00-tooling, 01-gcloud-setup (fully executed + evidenced).
- Working agreement: AGENTS.md + task-specific rules in
  `.agents/development-rules.md` and `.agents/infra-rules.md`.

## Verification and Review

- Runbook 01 checklist fully evidenced (auth, ADC, project, billing, budget).
- Docs-only changes so far; no code verification applicable.

## Remaining Tasks

- Runbook 02 — terraform skeleton: `infra/` structure, `envs/home.tfvars`, API
  enablement module. No more ad-hoc `gcloud services enable`.
- Makefile skeleton (setup/bootstrap targets).
- Phase 0 exit check: minimal local ADK agent → Gemini via Vertex AI (ADC).

## Next Steps

1. Draft runbook 02 + terraform files (plan first, owner reviews, apply together).
2. Makefile skeleton.
3. ADK/Vertex smoke test to close Phase 0.

## Important Notes

- Deployment pipeline stance: none yet — local scripts + runbook only; pipelines
  written at promotion (local-decisions.md D3).
- Trial credits: 0 used of zł1,114, expire 2026-12-05.
- Old default trial project exists but is unused/ignored.
