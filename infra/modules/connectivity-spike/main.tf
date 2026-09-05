# Connectivity-spike Cloud Run service (Phase 1, disposable).
#
# Owns the disposable MCP service per docs-local/plans/phase-1-connectivity-spike.md:
# internal-and-LB ingress, ID-token-only (no public invoker), runtime identity
# sa-artifact-mcp with the Cloud SQL unix-socket attachment. Removed at spike
# teardown (increment 5); deletion_protection is off for that reason.
#
# Note the deliberate two-step apply: `service_url` (the ID-token audience,
# env SPIKE_SERVICE_URL) is only known after the first apply creates the
# service; the first apply deploys with an empty audience and the service
# fails closed (503 on MCP traffic) until the second apply sets it.

terraform {
  required_version = ">= 1.16.0, < 2.0.0"
}

resource "google_project_iam_member" "runtime_sql_client" {
  # roles/cloudsql.instanceUser (cloud-sql module) grants IAM *login*, but
  # connecting over the Cloud Run unix socket additionally requires
  # cloudsql.instances.connect (roles/cloudsql.client).
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${var.runtime_sa_email}"
}

resource "google_cloud_run_v2_service" "spike_mcp" {
  project  = var.project_id
  location = var.region
  name     = "spike-connectivity-mcp"

  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = var.runtime_sa_email

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [var.instance_connection_name]
      }
    }

    # Single-request spike: bounded, min-scale 0.
    timeout                          = "60s"
    max_instance_request_concurrency = 4

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = var.image

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "SPIKE_INSTANCE_CONNECTION_NAME"
        value = var.instance_connection_name
      }
      env {
        # IAM db username = SA email without ".gserviceaccount.com" (Cloud SQL
        # convention; the service strips the suffix itself).
        name  = "SPIKE_SA_EMAIL"
        value = var.runtime_sa_email
      }
      env {
        name  = "SPIKE_SERVICE_URL"
        value = var.service_url # empty on first apply -> fail closed (503)
      }
    }
  }

  depends_on = [google_project_iam_member.runtime_sql_client]
}

# No public invoker member exists: anonymous invocation is denied by default.
resource "google_cloud_run_v2_service_iam_member" "facilitator_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.spike_mcp.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.invoker_sa_email}"
}
