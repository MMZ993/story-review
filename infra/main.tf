terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

module "project_services" {
  source = "./modules/project-services"

  project_id = var.project_id
  services   = var.required_services
}

module "service_accounts" {
  source = "./modules/service-accounts"

  project_id = var.project_id
}

locals {
  resource_prefix = "${var.project_id}-"
}

module "artifact_registry" {
  source = "./modules/artifact-registry"

  project_id    = var.project_id
  region        = var.region
  repository_id = "service-images"
}

module "storage" {
  source = "./modules/storage"

  project_id             = var.project_id
  bucket_name            = "${local.resource_prefix}artifacts"
  orchestration_sa_email = module.service_accounts.runtime_emails["sa-orchestration"]
  artifact_sa_email      = module.service_accounts.runtime_emails["sa-artifact-mcp"]
  report_sa_email        = module.service_accounts.runtime_emails["sa-report-mcp"]
  report_retention_days  = var.report_retention_days
}

module "cloud_sql" {
  source = "./modules/cloud-sql"

  project_id    = var.project_id
  region        = var.region
  instance_name = "${local.resource_prefix}sessions"
  iam_login_sa_emails = [
    module.service_accounts.runtime_emails["sa-orchestration"],
    module.service_accounts.runtime_emails["sa-facilitator"],
    module.service_accounts.runtime_emails["sa-artifact-mcp"],
    module.service_accounts.runtime_emails["sa-report-mcp"],
  ]
}

locals {
  service_secret_names = {
    orchestration        = "${local.resource_prefix}orchestration-config"
    facilitator          = "${local.resource_prefix}facilitator-config"
    business-reviewer    = "${local.resource_prefix}business-reviewer-config"
    engineering-reviewer = "${local.resource_prefix}engineering-reviewer-config"
    synthesis            = "${local.resource_prefix}synthesis-config"
    story                = "${local.resource_prefix}story-config"
    artifact             = "${local.resource_prefix}artifact-config"
    report               = "${local.resource_prefix}report-config"
  }
  service_secret_sa_keys = {
    orchestration        = "sa-orchestration"
    facilitator          = "sa-facilitator"
    business-reviewer    = "sa-business-reviewer"
    engineering-reviewer = "sa-engineering-reviewer"
    synthesis            = "sa-synthesis"
    story                = "sa-story-mcp"
    artifact             = "sa-artifact-mcp"
    report               = "sa-report-mcp"
  }
}

module "connectivity_spike" {
  # Disposable Phase 1 spike service; created only when spike_mcp_image is
  # supplied (Runbook 06 increment 3), so routine plans stay unaffected.
  count  = var.spike_mcp_image == "" ? 0 : 1
  source = "./modules/connectivity-spike"

  project_id               = var.project_id
  region                   = var.region
  image                    = var.spike_mcp_image
  runtime_sa_email         = module.service_accounts.runtime_emails["sa-artifact-mcp"]
  invoker_sa_email         = module.service_accounts.runtime_emails["sa-facilitator"]
  instance_connection_name = module.cloud_sql.instance_connection_name
  service_url              = var.spike_service_url
}

module "secrets" {
  source = "./modules/secrets"

  project_id        = var.project_id
  secret_names      = local.service_secret_names
  sa_emails         = { for k, id in local.service_secret_sa_keys : k => module.service_accounts.runtime_emails[id] }
  deployer_sa_email = module.service_accounts.deployer_email
}

