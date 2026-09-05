# Runbook (home phase)

Living document. Every procedure that touches the environment, deployment, or money
gets written here as soon as it exists — the phase plans reference these entries.
Pipeline translation at promotion reads this file.

Detailed commands live in [runbooks/](runbooks/) — this file stays the checklist.

## One-time setup (Phase 0)

- [ ] Install gcloud via mise (runbooks/00-tooling.md)
- [ ] gcloud auth + ADC (runbooks/01-gcloud-setup.md)
- [ ] Set project + region config
- [ ] Budget alert at 80% of trial credits
- [ ] `terraform init && terraform apply` (infra bootstrap)
- [ ] Record trial-account availability check results

## Local development loop

- [ ] `make compose-up` — orchestration + MCP services + adapters + substitutes
- [ ] `make compose-down`
- [ ] Vertex AI env: `GOOGLE_GENAI_USE_VERTEXAI=true`,
      `GOOGLE_CLOUD_PROJECT=<home-project-id>`, `GOOGLE_CLOUD_LOCATION=europe-west4`

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
