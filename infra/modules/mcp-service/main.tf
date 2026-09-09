# One MCP Cloud Run service (story / artifact / report), Phase 4 increment 5.
#
# Pattern proven by the connectivity spike (Runbook 06, D8 fallback): default
# ingress + mandatory ID-token audience auth (fail-closed until the service
# URL is set) + invoker-only IAM. Identity, not network position, is the
# boundary. min instances 0 — cost near-zero when idle.
#
# Two-step apply: `<name>_service_url` (the ID-token audience, env
# <PREFIX>_SERVICE_URL) is only known after the first apply creates the
# service; the first apply deploys with an empty audience and the middleware
# rejects all MCP traffic until the second apply sets it (fail-closed, tested
# per server suite).

terraform {
  required_version = ">= 1.16.0, < 2.0.0"
}

resource "google_cloud_run_v2_service" "service" {
  project  = var.project_id
  location = var.region
  name     = var.service_name

  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL" # D8 fallback; ID-token auth is the boundary

  template {
    service_account = var.runtime_sa_email

    timeout = "60s"
    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = "1"
          memory = var.memory
        }
      }

      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }
}

# No public invoker: anonymous invocation is denied by default; only the
# listed runtime SAs may reach the service at all (allowlist middleware then
# decides per principal and tool).
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  for_each = toset(var.invoker_sa_emails)

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${each.value}"
}
