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

  project_id                = var.project_id
  bucket_name               = "${local.resource_prefix}artifacts"
  story_dataset_bucket_name = "${local.resource_prefix}story-dataset"
  orchestration_sa_email    = module.service_accounts.runtime_emails["sa-orchestration"]
  artifact_sa_email         = module.service_accounts.runtime_emails["sa-artifact-mcp"]
  report_sa_email           = module.service_accounts.runtime_emails["sa-report-mcp"]
  story_sa_email            = module.service_accounts.runtime_emails["sa-story-mcp"]
  report_retention_days     = var.report_retention_days
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

# ---- Phase 4 MCP Cloud Run services (increment 5) ----
# Enabled per service by supplying the built image (-var mcp_<name>_image=...);
# the audience service URL is a second -var after the first apply reveals it.

locals {
  mcp_runtime_sas = {
    story    = module.service_accounts.runtime_emails["sa-story-mcp"]
    artifact = module.service_accounts.runtime_emails["sa-artifact-mcp"]
    report   = module.service_accounts.runtime_emails["sa-report-mcp"]
  }
  mcp_invokers = {
    story    = [module.service_accounts.runtime_emails["sa-orchestration"], module.service_accounts.runtime_emails["sa-facilitator"]]
    artifact = [module.service_accounts.runtime_emails["sa-orchestration"], module.service_accounts.runtime_emails["sa-facilitator"]]
    report   = [module.service_accounts.runtime_emails["sa-orchestration"]]
  }
}

module "mcp_story" {
  count = var.mcp_story_image == "" ? 0 : 1

  source = "./modules/mcp-service"

  project_id        = var.project_id
  region            = var.region
  service_name      = "mcp-story"
  image             = var.mcp_story_image
  runtime_sa_email  = local.mcp_runtime_sas["story"]
  invoker_sa_emails = local.mcp_invokers["story"]
  env = {
    STORY_SOURCE           = var.mcp_story_source
    STORY_DATASET_LOCATION = "gs://${module.storage.story_dataset_bucket_name}/stories/"
    STORY_ALLOWED_CALLERS  = join(",", local.mcp_invokers["story"])
    STORY_SERVICE_URL      = var.mcp_story_service_url # empty on first apply -> fail closed
  }
}

module "mcp_artifact" {
  count = var.mcp_artifact_image == "" ? 0 : 1

  source = "./modules/mcp-service"

  project_id        = var.project_id
  region            = var.region
  service_name      = "mcp-artifact"
  image             = var.mcp_artifact_image
  runtime_sa_email  = local.mcp_runtime_sas["artifact"]
  invoker_sa_emails = local.mcp_invokers["artifact"]
  env = {
    ARTIFACT_BUCKET                = module.storage.bucket_name
    ARTIFACT_ORCHESTRATION_CALLERS = module.service_accounts.runtime_emails["sa-orchestration"]
    ARTIFACT_FACILITATOR_CALLERS   = module.service_accounts.runtime_emails["sa-facilitator"]
    ARTIFACT_SERVICE_URL           = var.mcp_artifact_service_url
  }
}

module "mcp_report" {
  count = var.mcp_report_image == "" ? 0 : 1

  source = "./modules/mcp-service"

  project_id        = var.project_id
  region            = var.region
  service_name      = "mcp-report"
  image             = var.mcp_report_image
  runtime_sa_email  = local.mcp_runtime_sas["report"]
  invoker_sa_emails = local.mcp_invokers["report"]
  memory            = "1Gi" # PDF render path
  env = {
    REPORT_BUCKET                = module.storage.bucket_name
    REPORT_ORCHESTRATION_CALLERS = module.service_accounts.runtime_emails["sa-orchestration"]
    REPORT_SERVICE_URL           = var.mcp_report_service_url
  }
}

# Smoke-test impersonation (owner-approved increment 5): the owner's user
# mints sa-orchestration ID tokens locally to drive the authenticated smoke
# targets; the middleware allowlists contain only that principal across all
# three services. Sandbox-only grant — remove on promotion.
resource "google_service_account_iam_member" "smoke_token_creator" {
  count = var.smoke_user_email == "" ? 0 : 1

  service_account_id = module.service_accounts.runtime_sa_ids["sa-orchestration"]
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "user:${var.smoke_user_email}"
}
