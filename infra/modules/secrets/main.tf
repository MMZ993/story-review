# Per-service Secret Manager skeletons: empty secrets created by bootstrap,
# values filled at deploy time through env-template indirection.
terraform {
  required_version = ">= 1.16.0, < 2.0.0"
}

resource "google_secret_manager_secret" "service_config" {
  for_each = var.secret_names

  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }
}

# Each runtime SA reads only its own secret.
resource "google_secret_manager_secret_iam_member" "runtime_accessor" {
  for_each = var.secret_names

  project   = var.project_id
  secret_id = google_secret_manager_secret.service_config[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.sa_emails[each.key]}"
}

# The deployment SA reads deploy-time values for every secret.
resource "google_secret_manager_secret_iam_member" "deployer_accessor" {
  for_each = var.secret_names

  project   = var.project_id
  secret_id = google_secret_manager_secret.service_config[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.deployer_sa_email}"
}
