variable "project_id" {
  type = string
}

variable "bucket_name" {
  description = "Globally unique bucket name for artifacts and reports."
  type        = string
}

variable "orchestration_sa_email" {
  type = string
}

variable "artifact_sa_email" {
  type = string
}

variable "report_sa_email" {
  type = string
}

variable "force_destroy" {
  description = "Allow bucket deletion with objects inside (home phase convenience)."
  type        = bool
  default     = true
}

variable "report_retention_days" {
  description = "Lifecycle deletion age for report objects (days)."
  type        = number
  default     = 90
}
