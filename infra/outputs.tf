output "enabled_services" {
  description = "Google APIs managed by this Terraform configuration."
  value       = module.project_services.enabled_services
}
