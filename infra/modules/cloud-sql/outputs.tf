output "instance_name" {
  description = "Cloud SQL instance name (instance connection name is derived as <project>:<region>:<instance_name>)."
  value       = google_sql_database_instance.sessions.name
}

output "instance_connection_name" {
  description = "Connection name for the Cloud Run /cloudsql connector."
  value       = google_sql_database_instance.sessions.connection_name
}
