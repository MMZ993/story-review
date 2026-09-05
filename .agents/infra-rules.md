# Infra rules — Google Cloud, terraform, and deployment

Load this file when a session touches terraform, gcloud, Cloud Run / Agent Engine
deployment, Cloud SQL, IAM, or any environment action. Linked from AGENTS.md.

## Command tiers

| Tier | Examples | Rule |
|---|---|---|
| 1 — read-only | `terraform plan/validate`, `gcloud ... describe/list`, `gsutil ls`, `git log` | Run freely (with explanation, per AGENTS.md protocol) |
| 2 — write | `terraform apply`, `gcloud services enable`, deploys, `run-migrations.sh`, creating billable resources | Explicit owner approval per run; state exactly what will change first |
| 3 — destructive | `terraform destroy`, `gcloud projects delete`, resource/DB deletion, IAM removals | **Owner runs it personally** (AGENTS.md safety rules); consequences described first |

## Principles

- **IaC only**: manual console/CLI changes are not "done" until codified in
  `infra/` terraform or a runbook. Exception: one-off setup actions (auth, budget)
  live in runbooks by design.
- **Plan before apply**: never `terraform apply` without showing/summarizing the
  plan to the owner first.
- Idempotent modules; explicit names; versions pinned; least-privilege IAM.
- Identifiers and secrets per AGENTS.md: `infra/envs/home.env` + `$VARS`;
  ADC credentials; no keys, no literals in git.
- Every environment action gets a runbook entry with commands, gotchas, and
  evidence — including the failures (propagation delays, wrong flags).
- Cost awareness: prefer min-scale settings; anything that starts billing gets
  flagged to the owner before creation; teardown steps documented next to setup
  steps.

## Terraform layout (home phase)

- `infra/` modules; `infra/envs/home.tfvars` is the home trial project;
  a future `company.tfvars` switches environments without module changes.
- App releases (Agent Engine deploys, Cloud Run service updates) are scripts
  (`deploy/**/deploy.sh`) per local-decisions.md D2 — terraform owns the
  surroundings, not the app versions.

## Gotchas learned (append as discovered)

- gcloud API enablement → subsequent calls may fail ~1 min (propagation); retry.
- `gcloud billing budgets create` has no `--budget-file`; use individual flags.
- `gcloud projects create` has no billing flag; link separately.
- Cloud SQL: `db-f1-micro` is rejected on the provider's ENTERPRISE_PLUS default
  edition (Error 400 Invalid Tier); set `settings.edition = "ENTERPRISE"`.
- Cloud SQL: an instance with no connectivity is rejected (Error 400: "At least
  one of Public IP or Private IP or PSC connectivity must be enabled"); private
  IP implies VPC peering/servicenetworking — the Phase 1 spike decides the final
  path.
- ADC consent must include all requested scopes; re-run login if unticked.
