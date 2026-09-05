# Runbook 02 — Terraform bootstrap (API enablement)

Creates the reproducible Terraform foundation for home-phase infrastructure. This
first apply enables only the Google APIs required by the planned bootstrap; it
creates no billable runtime resources. Cloud SQL, buckets, registry, service accounts,
IAM, and Secret Manager skeletons are added in later reviewed Terraform changes.

Status: DRAFT. Do not apply until the owner has reviewed the plan and explicitly
approved that apply.

## Scope and guardrails

- Run from the repository root with authenticated ADC from Runbook 01.
- Terraform manages API enablement through
  `infra/modules/project-services`; do not use `gcloud services enable` for these APIs.
- `disable_on_destroy = false` deliberately leaves APIs enabled if Terraform state is
  later destroyed. Disabling shared project APIs can disrupt manually created resources
  and is not appropriate for the home project.
- `billingbudgets.googleapis.com` remains a documented one-off from Runbook 01; it is
  not owned by this module because the budget has already been created.
- API propagation can take about one minute after apply. Retry a dependent command
  rather than adding an ad-hoc enablement command.

## 1. Create the private environment variables file

`home.tfvars` contains the private home project identifier and is ignored by git. Its
values duplicate only the non-secret target selection already kept in `home.env`.

```bash
source infra/envs/home.env
cp infra/envs/home.tfvars.example infra/envs/home.tfvars
python3 - "$PROJECT_ID" <<'PY'
from pathlib import Path
import sys

path = Path("infra/envs/home.tfvars")
path.write_text(
    f'project_id = "{sys.argv[1]}"\nregion     = "europe-west4"\n', encoding="utf-8"
)
PY
```

Verify that no placeholder remains, without printing the identifier:

```bash
if grep -q 'replace-with-your-project-id' infra/envs/home.tfvars; then
  printf '%s\n' 'home.tfvars still contains the placeholder; update project_id.' >&2
else
  printf '%s\n' 'home.tfvars project_id is set.'
fi
```

## 2. Initialize and validate (read-only with respect to Google Cloud)

```bash
terraform -chdir=infra init
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
```

`init` downloads the locked provider selection locally and creates ignored
`.terraform/` and `.terraform.lock.hcl` files. Commit the generated lockfile after
review; never commit `.terraform/` or state files.

## 3. Produce and review the plan (read-only)

```bash
terraform -chdir=infra plan \
  -var-file=envs/home.tfvars \
  -out=home-api-enable.tfplan
terraform -chdir=infra show home-api-enable.tfplan
```

Expected plan: ten `google_project_service` resources added, one each for Vertex AI,
Artifact Registry, Cloud Run, Cloud SQL Admin, Cloud Storage, Secret Manager, IAM,
IAM Credentials, Cloud Resource Manager, and Service Usage. No Cloud SQL instances,
buckets, service accounts, or other billable runtime resources should appear.

## 4. Apply (write action — owner approval required)

After the owner reviews the exact plan and explicitly approves this run:

```bash
terraform -chdir=infra apply home-api-enable.tfplan
```

This enables the ten APIs in the home project. API enablement itself is not a runtime
resource charge, but it permits subsequent creation of billable resources; do not run
unreviewed follow-on provisioning commands.

## 5. Verify and record evidence

```bash
source infra/envs/home.env
gcloud services list \
  --project="$PROJECT_ID" \
  --enabled \
  --format='value(config.name)' \
  | grep -E '^(aiplatform|artifactregistry|cloudresourcemanager|iam|iamcredentials|run|secretmanager|serviceusage|sqladmin|storage)\.googleapis\.com$' \
  | sort
terraform -chdir=infra state list
```

Record the successful apply date, the plan summary, the enabled-service output, and
any propagation delay in this runbook's evidence section and in
`docs-local/runbook.md`.

## Evidence

- 2026-09-05 — owner ran `terraform -chdir=infra init`, `fmt -check -recursive`,
  `validate`, then reviewed `home-api-enable.tfplan`.
- 2026-09-05 — reviewed plan and apply completed: **10 added, 0 changed,
  0 destroyed**. Enabled APIs: Vertex AI, Artifact Registry, Cloud Resource
  Manager, IAM, IAM Credentials, Cloud Run, Secret Manager, Service Usage,
  Cloud SQL Admin, and Cloud Storage.
- API enablement completed in 4–24 seconds. No propagation retry was needed during
  the apply; allow for propagation before a dependent operation if it fails.
- 2026-09-05 — post-apply verification passed. `gcloud services list --enabled`
  returned all ten expected APIs; `terraform -chdir=infra state list` returned the
  corresponding ten `google_project_service` resources.
