# Cloud SQL PostgreSQL instance: ADK session store and audit records.
# IAM database authentication only — no password secrets.
terraform {
  required_version = ">= 1.16.0, < 2.0.0"
}

resource "google_sql_database_instance" "sessions" {
  project             = var.project_id
  name                = var.instance_name
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = false

  settings {
    edition           = "ENTERPRISE" # shared-core tier db-f1-micro requires it (ENTERPRISE_PLUS rejects the tier)
    tier              = var.tier
    availability_type = "ZONAL" # smallest cost; trial sandbox per local-decisions D5
    disk_size         = 10
    disk_autoresize   = true

    backup_configuration {
      enabled = false # trial budget: sessions are reproducible
    }

    ip_configuration {
      # Cloud SQL requires at least one connectivity path; private IP needs VPC
      # peering (servicenetworking), which is a Phase 1 spike decision. Until then:
      # public IP with IAM database authentication only (design fallback),
      # authorized networks left empty (nothing whitelisted beyond IAM-auth logins).
      ipv4_enabled = true
    }

    database_flags {
      # PostgreSQL flag name is "cloudsql.iam_authentication" (with dot); the
      # MySQL-style "cloudsql_iam_authentication" is rejected: Error 404
      # invalidFlagName (gotcha learned 2026-09-05).
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
  }
}

# IAM database users for the runtime SAs (passwordless; login = IAM database
# authentication). Requires the cloudsql.iam_authentication flag above plus
# project-level roles/cloudsql.instanceUser (granted further down). Database
# privileges (schema ownership/grants) are applied by migrations, not here.
# Gotcha: for service accounts the database username drops the
# ".gserviceaccount.com" suffix (Error 400 otherwise); the Cloud Run connector
# with auto-iam-authn maps the SA email to this form automatically.
resource "google_sql_user" "iam_runtime_users" {
  for_each = toset(var.iam_login_sa_emails)

  project  = var.project_id
  name     = trimsuffix(each.value, ".gserviceaccount.com")
  instance = google_sql_database_instance.sessions.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}

# Project-level prerequisite for IAM database login; database-level grants are
# applied by migrations (deploy/cloud-sql/run-migrations.sh).
resource "google_project_iam_member" "instance_users" {
  for_each = toset(var.iam_login_sa_emails)

  project = var.project_id
  role    = "roles/cloudsql.instanceUser"
  member  = "serviceAccount:${each.value}"
}
