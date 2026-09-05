output "service_name" {
  description = "Cloud Run service name of the disposable spike MCP."
  value       = google_cloud_run_v2_service.spike_mcp.name
}

output "service_url" {
  description = "Service URL; the ID-token audience for the Agent Engine caller."
  value       = google_cloud_run_v2_service.spike_mcp.uri
}
