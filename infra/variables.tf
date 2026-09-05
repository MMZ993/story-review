variable "project_id" {
  description = "Google Cloud project ID for this environment."
  type        = string

  validation {
    condition     = length(trimspace(var.project_id)) > 0
    error_message = "project_id must not be empty."
  }
}

variable "region" {
  description = "Google Cloud region for regional bootstrap resources."
  type        = string
  default     = "europe-west4"

  validation {
    condition     = length(trimspace(var.region)) > 0
    error_message = "region must not be empty."
  }
}

variable "report_retention_days" {
  description = "Lifecycle deletion age for report objects in the artifact bucket (days)."
  type        = number
  default     = 90
}

variable "required_services" {
  description = "Google APIs enabled before provisioning bootstrap resources."
  type        = set(string)
  default = [
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
  ]
}
