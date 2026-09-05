output "enabled_services" {
  description = "Google APIs managed by this Terraform configuration."
  value       = module.project_services.enabled_services
}

output "service_accounts" {
  description = "Service account emails managed by this configuration."
  value = {
    deployer = module.service_accounts.deployer_email
    runtime  = module.service_accounts.runtime_emails
  }
}

