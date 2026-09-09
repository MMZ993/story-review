variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Region for the Cloud Run service."
  type        = string
}

variable "service_name" {
  description = "Cloud Run service name (e.g. mcp-story)."
  type        = string
}

variable "image" {
  description = "Container image reference (Artifact Registry)."
  type        = string
}

variable "runtime_sa_email" {
  description = "Runtime service account the service runs as."
  type        = string
}

variable "invoker_sa_emails" {
  description = "Runtime SAs allowed to invoke the service (middleware allowlists still apply per principal)."
  type        = list(string)
}

variable "env" {
  description = "Plain env vars for the container (no secrets; config secrets live in Secret Manager)."
  type        = map(string)
  default     = {}
}

variable "max_instances" {
  description = "Cloud Run max instance count."
  type        = number
  default     = 2
}

variable "memory" {
  description = "Container memory limit."
  type        = string
  default     = "512Mi"
}
