# Artifact Registry Docker repository for service images.
terraform {
  required_version = ">= 1.16.0, < 2.0.0"
}

resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = var.repository_id
  description   = "Docker images for MCP services and orchestration (home phase)."
  format        = "DOCKER"

  docker_config {
    immutable_tags = false
  }
}
