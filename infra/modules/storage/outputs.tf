output "bucket_name" {
  description = "Name of the artifact/report bucket."
  value       = google_storage_bucket.artifacts.name
}

output "story_dataset_bucket_name" {
  description = "Name of the story dataset bucket."
  value       = google_storage_bucket.story_dataset.name
}
