# Artifact/report GCS bucket with uniform bucket-level access and scoped grants.
terraform {
  required_version = ">= 1.16.0, < 2.0.0"
}

resource "google_storage_bucket" "artifacts" {
  name                        = var.bucket_name
  project                     = var.project_id
  location                    = "EU"
  uniform_bucket_level_access = true
  force_destroy               = var.force_destroy

  versioning {
    enabled = false
  }

  lifecycle_rule {
    condition {
      age = var.report_retention_days
      matches_prefix = [
        "reports/",
      ]
    }

    action {
      type = "Delete"
    }
  }
}

# Orchestration reads artifacts (never writes; reports are written by report MCP).
resource "google_storage_bucket_iam_member" "orchestration_viewer" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.orchestration_sa_email}"
}

# Artifact MCP owns artifact objects.
resource "google_storage_bucket_iam_member" "artifact_admin" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.artifact_sa_email}"
}

# Report MCP owns only the reports/ prefix (IAM condition).
resource "google_storage_bucket_iam_member" "report_prefix_admin" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.report_sa_email}"

  condition {
    title       = "report-prefix-only"
    description = "Report MCP may only manage objects under reports/."
    expression  = "resource.name.startsWith(\"projects/_/buckets/${var.bucket_name}/objects/reports/\")"
  }
}
