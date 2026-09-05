# Runbook (home phase)

Living document. Every procedure that touches the environment, deployment, or money
gets written here as soon as it exists — the phase plans reference these entries.
Pipeline translation at promotion reads this file.

## One-time setup (Phase 0)

- [ ] Create trial GCP account; apply credits; create project `<home-project-id>`
- [ ] Set budget alert (~80% of trial credits)
- [ ] `gcloud auth login` + `gcloud auth application-default login`
- [ ] Confirm Vertex AI + Agent Engine available in `europe-west4`
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
