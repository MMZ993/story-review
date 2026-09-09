output "service_name" {
  description = "Cloud Run service name."
  value       = google_cloud_run_v2_service.service.name
}

output "service_url" {
  description = "Cloud Run service URL (use as the ID-token audience in the second apply)."
  value       = google_cloud_run_v2_service.service.uri
}
