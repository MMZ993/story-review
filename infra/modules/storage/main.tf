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

  # Retention (owner-approved increment 5): the report server writes under
  # runs/<run>/reports/, which a plain "reports/" prefix can never match
  # (GCS lifecycle prefixes are literal). The 90-day rule therefore covers
  # the whole runs/ tree — artifacts are per-run data too in this design.
  lifecycle_rule {
    condition {
      age = var.report_retention_days
      matches_prefix = [
        "runs/",
      ]
    }

    action {
      type = "Delete"
    }
  }
}

# Story dataset bucket (Phase 4 increment 5): frozen mock stories under
# stories/ (make dataset-push; expected files never upload). Read by the
# story server's `mock` source; pushes run from the owner's workstation
# with the project owner's own credentials (D2: app data is not IaC).
resource "google_storage_bucket" "story_dataset" {
  name                        = var.story_dataset_bucket_name
  project                     = var.project_id
  location                    = "EU"
  uniform_bucket_level_access = true
  force_destroy               = var.force_destroy

  versioning {
    enabled = false
  }
}

resource "google_storage_bucket_iam_member" "story_dataset_viewer" {
  bucket = google_storage_bucket.story_dataset.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.story_sa_email}"
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

# Report MCP: read-only access to the whole bucket (it reads the
# finalized-review under runs/<run>/artifacts/) plus objectAdmin scoped to
# its own runs/.../reports/ and runs/.../report-idem/ prefixes (CEL; GCS
# lifecycle-style literal prefixes cannot express mid-path wildcards).
resource "google_storage_bucket_iam_member" "report_viewer" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.report_sa_email}"
}

resource "google_storage_bucket_iam_member" "report_prefix_admin" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.report_sa_email}"

  condition {
    title       = "report-runs-tree-only"
    description = "Report MCP may manage objects under runs/. GCS condition prefixes cannot express mid-path wildcards (runs/*/reports/); an extract()-based CEL condition compiled but did not evaluate on object create. Recorded in local-decisions."
    expression  = "resource.name.startsWith('projects/_/buckets/${var.bucket_name}/objects/runs/')"
  }
}
