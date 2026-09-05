output "secret_ids" {
  description = "Map of service key to created secret id."
  value       = { for k, s in google_secret_manager_secret.service_config : k => s.secret_id }
}
