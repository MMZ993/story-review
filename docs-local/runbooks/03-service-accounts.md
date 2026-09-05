# Runbook 03 — Service accounts and bootstrap IAM

Second Terraform increment: the nine service accounts from the identity model in
`docs/operations/connectivity-identity.md`, plus the project-level grants that are
valid before any data-plane resource exists. Service accounts and IAM bindings are
free of charge.

Status: EXECUTED 2026-09-05 (planned, applied, verified).

## Scope and guardrails

- New module `infra/modules/service-accounts`; wired into the root next to
  `project-services`.
- Nine accounts: `sa-deployer` plus eight runtime SAs (orchestration,
  facilitator, business-reviewer, engineering-reviewer, synthesis, story-mcp,
  artifact-mcp, report-mcp).
- Grants created here (project level only):
  - `sa-deployer`: `roles/run.admin`, `roles/aiplatform.user`,
    `roles/artifactregistry.writer`, `roles/cloudsql.editor`, and
    `roles/iam.serviceAccountUser` on each runtime SA (actAs at deploy time).
  - `sa-orchestration`: `roles/aiplatform.user` (invoke Agent Engine agents) and
    `roles/iam.serviceAccountTokenCreator` on **itself** (signed URLs, MCP
    audience tokens).
- Deliberately deferred to later increments: `secretAccessor` (secrets don't
  exist yet), Cloud SQL IAM login and instance roles, GCS bucket roles.
- No keys are created for any SA; ADC is the only credential path.
- Note: `roles/cloudsql.editor` on the deployer is broader than strictly needed
  for `run-migrations.sh`; it stays until the Cloud SQL increment can scope it.

## 1. Validate (read-only with respect to Google Cloud)

```bash
terraform -chdir=infra init
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
```

## 2. Produce and review the plan (read-only)

```bash
terraform -chdir=infra plan \
  -var-file=envs/home.tfvars \
  -out=home-service-accounts.tfplan
terraform -chdir=infra show home-service-accounts.tfplan
```

Expected plan: 9 `google_service_account` resources added; 4
`google_project_iam_member` (deployer roles) + 1 (orchestration
`aiplatform.user`); 8 `google_service_account_iam_member` for deployer actAs + 1
for orchestration self token-creator. No changes to the existing ten
`google_project_service` resources.

## 3. Apply (write action — owner approval required)

After the owner reviews the exact plan and explicitly approves this run:

```bash
terraform -chdir=infra apply home-service-accounts.tfplan
```

## 4. Verify and record evidence

```bash
source infra/envs/home.env
gcloud iam service-accounts list \
  --project="$PROJECT_ID" \
  --format='table(email,displayName)'
gcloud projects get-iam-policy "$PROJECT_ID" \
  --format='table(bindings.role,bindings.members)' \
  | grep -E 'sa-(deployer|orchestration)'
terraform -chdir=infra output service_accounts
```

Record the apply date, plan summary, SA list, and IAM policy evidence below and
in `docs-local/runbook.md`.

## Teardown note

Removing these SAs is a destructive action (IAM removals): the owner runs any
such command personally, consequences described first.

## Evidence

- 2026-09-05 — module added, `init`/`fmt -check -recursive`/`validate` passed (one
  `fmt` alignment fix in the new module before check). Plan saved to
  `home-service-accounts.tfplan`, reviewed by the owner.
- 2026-09-05 — owner-approved apply completed: **23 added, 0 changed,
  0 destroyed** — 9 `google_service_account`, 5 `google_project_iam_member`,
  9 `google_service_account_iam_member`. The ten existing API resources were
  untouched.
- Post-apply verification: `gcloud iam service-accounts list` returned all nine
  managed SAs (plus Google-managed default compute and robot accounts);
  `gcloud projects get-iam-policy` grep confirmed `sa-deployer` holds
  `roles/run.admin`, `roles/aiplatform.user`, `roles/artifactregistry.writer`,
  `roles/cloudsql.editor`, and `sa-orchestration` shares
  `roles/aiplatform.user`. `terraform output service_accounts` returned all
  expected emails.
- No propagation delays observed.
- Observation (not acted on): the project's **default compute SA** carries
  `roles/editor` from project creation. Pre-existing, outside this module's
  scope; candidate for tightening in a later reviewed increment.
- Related decision: D6 (local-decisions.md) — the evaluation judge is not a
  deployed agent; deployer SA's `aiplatform.user` covers CI inference calls.

