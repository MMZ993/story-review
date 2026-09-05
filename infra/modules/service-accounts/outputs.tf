output "deployer_email" {
  description = "Email of the deployment service account."
  value       = google_service_account.deployer.email
}

output "runtime_emails" {
  description = "Map of runtime account_id to service account email."
  value       = { for id, sa in google_service_account.runtime : id => sa.email }
}
