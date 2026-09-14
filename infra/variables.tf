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

variable "spike_mcp_image" {
  description = "Image reference for the disposable connectivity-spike Cloud Run service (empty = module disabled)."
  type        = string
  default     = ""
}

variable "spike_service_url" {
  description = "Spike Cloud Run service URL used as ID-token audience; set in the second apply after the first reveals it."
  type        = string
  default     = ""
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
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
  ]
}

variable "mcp_story_image" {
  description = "Image reference for the story MCP Cloud Run service (empty = not deployed)."
  type        = string
  default     = ""
}

variable "mcp_artifact_image" {
  description = "Image reference for the artifact MCP Cloud Run service (empty = not deployed)."
  type        = string
  default     = ""
}

variable "mcp_report_image" {
  description = "Image reference for the report MCP Cloud Run service (empty = not deployed)."
  type        = string
  default     = ""
}

variable "mcp_story_service_url" {
  description = "Story MCP service URL (ID-token audience); set in the second apply after the first reveals it."
  type        = string
  default     = ""
}

variable "mcp_artifact_service_url" {
  description = "Artifact MCP service URL (ID-token audience); set in the second apply."
  type        = string
  default     = ""
}

variable "mcp_report_service_url" {
  description = "Report MCP service URL (ID-token audience); set in the second apply."
  type        = string
  default     = ""
}

variable "mcp_story_source" {
  description = "STORY_SOURCE deployment default for the story MCP (mock | azure)."
  type        = string
  default     = "mock"
}

variable "smoke_user_email" {
  description = "Owner user email granted tokenCreator on sa-orchestration for local smoke tests (empty = no grant)."
  type        = string
  default     = ""
}
