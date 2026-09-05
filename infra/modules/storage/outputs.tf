output "bucket_name" {
  description = "Name of the artifact/report bucket."
  value       = google_storage_bucket.artifacts.name
}
