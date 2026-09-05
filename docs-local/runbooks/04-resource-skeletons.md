# Runbook 04 — Resource skeletons: Artifact Registry, GCS, Cloud SQL, Secret Manager

Third Terraform increment: the remaining Phase 0 bootstrap resources in
cost-aware form, plus the resource-scoped grants deferred from Runbook 03.

Status: EXECUTED 2026-09-05 — complete and verified.

- **Connectivity decision (deferred to Phase 1 spike):** public IP stays until
  the spike proves private IP is usable end-to-end (Cloud Run **and** Agent
  Engine); private would additionally cost a serverless VPC connector
  (~double the recurring bill). If proven, one reviewed increment flips
  `ipv4_enabled = false` + `private_network` with the servicenetworking
  peering; if not, public + IAM auth is the accepted sandbox posture
  (identity is the boundary, per connectivity-identity.md). Owner agreed
  2026-09-05.

## Cost notice (billed resources — flag before creation, per infra rules)

- **Cloud SQL `db-f1-micro`** is the main recurring cost (~$7–10/month equivalent
  in trial credits). ZONAL availability, no backups, 10 GB disk, no public IP.
  It can be stopped when idle for extended periods (see runbook.md teardown).
- Artifact Registry, GCS bucket (empty), and Secret Manager (8 empty secrets)
  are effectively free at this scale.

## Scope and guardrails

- Four new modules, each idempotent and independently reviewable:
  - `modules/artifact-registry` — one Docker repository `service-images` in the
    region. `immutable_tags = false` while deployment scripts iterate.
  - `modules/storage` — one bucket `<project>-artifacts` (uniform bucket-level
    access, `EU` multi-region): orchestration `objectViewer`; artifact MCP
    `objectAdmin`; report MCP `objectAdmin` **conditioned to the `reports/`
    prefix**; `reports/` objects lifecycle-delete after 90 days.
    `force_destroy = true` as a home-phase convenience (documented deviation).
  - `modules/cloud-sql` — `POSTGRES_16`, `db-f1-micro` (ENTERPRISE edition),
    ZONAL, backups off, public IP with empty authorized networks (the design's
    documented fallback until the Phase 1 spike decides; IAM auth only — no
    password). `deletion_protection = false` (trial sandbox; deliberate,
    reproducible via Terraform + migrations). Grants `roles/cloudsql.instanceUser`
    to orchestration, facilitator,
    artifact-mcp, report-mcp (project-level prerequisite for IAM database
    login; database-level grants are applied by migrations later).
  - `modules/secrets` — 8 empty per-service `<project>-<service>-config`
    secrets; the owning runtime SA gets `secretAccessor` on **only its own**
    secret; the deployer SA gets `secretAccessor` on all (deploy-time values).
- Names derive from `project_id` (never literals in docs/git beyond tfvars).
- Resource IDs for deploy env templates come from new root outputs
  (`artifact_registry_url`, `artifact_bucket_name`, `cloud_sql`,
  `service_secret_ids`).
- Nothing from Runbooks 02/03 changes.

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
  -out=home-resource-skeletons.tfplan
terraform -chdir=infra show home-resource-skeletons.tfplan
```

Expected plan (approximate): 1 Artifact Registry repository, 1 bucket, 3 bucket
IAM bindings, 1 Cloud SQL instance, 4 project IAM bindings
(`cloudsql.instanceUser`), 8 secrets, 16 secret IAM bindings — ~34 to add,
0 to change, 0 to destroy. Cloud SQL instance creation can take several minutes.

## 3. Apply (write action — owner approval required)

After the owner reviews the exact plan and explicitly approves this run:

```bash
terraform -chdir=infra apply home-resource-skeletons.tfplan
```

## 4. Verify and record evidence

```bash
source infra/envs/home.env
gcloud artifacts repositories list --project="$PROJECT_ID" \
  --format='table(name,format,location)'
gcloud storage buckets list --project="$PROJECT_ID" \
  --format='table(name,location,uniformBucketLevelAccess.enabled)'
gcloud sql instances list --project="$PROJECT_ID" \
  --format='table(name,databaseVersion,settings.tier,connectionName)'
gcloud secrets list --project="$PROJECT_ID" --format='value(name)' | sort
terraform -chdir=infra output
```

Record the apply date, plan summary, and verification outputs below and in
`docs-local/runbook.md`. Phase 0's "trial-account availability checks" (D1) are
recorded separately in Runbook 05 (ADK/Vertex smoke test).

## Teardown notes

- Cloud SQL deletion and bucket `force_destroy` are destructive (tier 3): the
  owner runs them personally; consequences described first.
- Cloud SQL can be stopped (`gcloud sql instances patch --activation-policy
  NEVER`) instead of deleted for idle periods.

## Evidence

- 2026-09-05 — four modules added; `init`/`fmt`/`validate` passed (one `fmt`
  alignment pass). Plan reviewed by the owner: **34 to add, 0 change, 0 destroy**.
- **Apply attempt 1 (partial):** failed on Cloud SQL with Error 400 *Invalid
  Tier (db-f1-micro) for (ENTERPRISE_PLUS) Edition*; the other 33 resources
  (AR repo, bucket + 3 bindings, 8 secrets + 16 secret bindings, 4
  instanceUser bindings) were created and recorded in state. Fixed by
  `settings.edition = "ENTERPRISE"`; gotcha appended to infra-rules.
- **Apply attempt 2 (partial):** failed on Cloud SQL with Error 400 *At least
  one of Public IP or Private IP or PSC connectivity must be enabled*. Fixed
  by enabling public IP with empty authorized networks — the design's
  documented fallback until the Phase 1 spike decides the connectivity path
  (private IP would require VPC peering / servicenetworking). This apply also
  reconciled the AR repo's `immutable_tags` to `false` (no further diff).
  Gotcha appended to infra-rules.
- **Apply attempt 3: complete** — SQL instance created after 9m01s. Final
  totals across the three applies: **34 added, 0 changed, 0 destroyed**.
- Outputs confirm: bucket `<project>-artifacts`, repo
  `europe-west4-docker.pkg.dev/.../service-images`, SQL instance
  `<project>-sessions` (POSTGRES_16, db-f1-micro, ENTERPRISE edition, public
  IP, connection name as in outputs), and the 8
  `<project>-<service>-config` secrets.
- gcloud cross-checks (§4), all 2026-09-05: `gcloud sql instances list`
  confirmed `<project>-sessions` / POSTGRES_16 / db-f1-micro / connection name
  as in outputs; `gcloud artifacts repositories list` confirmed `service-images`
  DOCKER in europe-west4; `gcloud storage buckets list` confirmed
  `<project>-artifacts` in EU (the `uniformBucketLevelAccess.enabled` table
  column renders blank — format-key quirk; the attribute is set by Terraform);
  `gcloud secrets list` returned all eight `<project>-<service>-config`
  secrets sorted as expected.


