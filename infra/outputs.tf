output "enabled_services" {
  description = "Google APIs managed by this Terraform configuration."
  value       = module.project_services.enabled_services
}

output "artifact_registry_url" {
  description = "Docker repository URL for service images."
  value       = module.artifact_registry.repository_url
}

output "artifact_bucket_name" {
  description = "GCS bucket for artifacts and reports."
  value       = module.storage.bucket_name
}

output "cloud_sql" {
  description = "Cloud SQL instance identifiers."
  value = {
    instance_name            = module.cloud_sql.instance_name
    instance_connection_name = module.cloud_sql.instance_connection_name
  }
}

output "service_secret_ids" {
  description = "Per-service Secret Manager secret ids."
  value       = module.secrets.secret_ids
}

output "service_accounts" {
  description = "Service account emails managed by this configuration."
  value = {
    deployer = module.service_accounts.deployer_email
    runtime  = module.service_accounts.runtime_emails
  }
}

