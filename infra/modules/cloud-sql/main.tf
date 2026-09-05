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
  }
}

# Project-level prerequisite for IAM database login; database-level grants are
# applied by migrations (deploy/cloud-sql/run-migrations.sh).
resource "google_project_iam_member" "instance_users" {
  for_each = toset(var.iam_login_sa_emails)

  project = var.project_id
  role    = "roles/cloudsql.instanceUser"
  member  = "serviceAccount:${each.value}"
}
