# Service accounts and bootstrap IAM.
#
# Implements the identity model from docs/operations/connectivity-identity.md.
# Only project-level grants that are meaningful before the data-plane resources
# exist are defined here; secret-, Cloud SQL-, and bucket-scoped grants are added
# by the increments that create those resources (Secret Manager, Cloud SQL, GCS).

terraform {
  required_version = ">= 1.16.0, < 2.0.0"
}

# Runtime service accounts, one per deployed unit. The deployment SA is defined
# separately because its grants differ structurally from the runtime set.
locals {
  runtime_accounts = [
    "sa-orchestration",
    "sa-facilitator",
    "sa-business-reviewer",
    "sa-engineering-reviewer",
    "sa-synthesis",
    "sa-story-mcp",
    "sa-artifact-mcp",
    "sa-report-mcp",
  ]
}

resource "google_service_account" "deployer" {
  account_id   = "sa-deployer"
  display_name = "Deployment SA (pipelines)"
  description  = "Deploy-time identity: creates services, writes images, runs migrations. No runtime data access."
}

resource "google_service_account" "runtime" {
  for_each = toset(local.runtime_accounts)

  account_id   = each.value
  display_name = "Runtime SA ${each.value}"
  description  = "Runtime identity for one deployed unit; data-plane grants attach with their resources."
}

# --- Deployment SA grants (project level) ---

resource "google_project_iam_member" "deployer_roles" {
  for_each = toset([
    "roles/run.admin",       # create/update Cloud Run services
    "roles/aiplatform.user", # create/update Agent Engine deployments
    "roles/artifactregistry.writer",
    "roles/cloudsql.editor", # run-migrations.sh
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Deployer attaches a runtime SA when deploying; actAs is serviceAccountUser on
# the runtime account, not a project-wide user role.
resource "google_service_account_iam_member" "deployer_actas" {
  for_each = google_service_account.runtime

  service_account_id = each.value.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

# --- Orchestration runtime grants ---

# Invokes the Agent Engine agent deployments.
# The four agent runtime SAs run their Agent Engine containers with their
# own identity and call Vertex for every model request — they need the
# same role (Phase 8 increment 3: deployed containers 403'd without it).
resource "google_project_iam_member" "agent_aiplatform_users" {
  for_each = toset([
    "sa-facilitator",
    "sa-business-reviewer",
    "sa-engineering-reviewer",
    "sa-synthesis",
  ])

  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime[each.key].email}"
}

resource "google_project_iam_member" "orchestration_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime["sa-orchestration"].email}"
}

# Signed URLs and MCP audience tokens: the SA signs as itself, which requires
# token creator on itself, not a project-wide role.
resource "google_service_account_iam_member" "orchestration_token_creator_self" {
  service_account_id = google_service_account.runtime["sa-orchestration"].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.runtime["sa-orchestration"].email}"
}
