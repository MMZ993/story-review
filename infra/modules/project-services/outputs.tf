output "enabled_services" {
  description = "Managed Google API service names."
  value       = sort(keys(google_project_service.this))
}
