variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Region for the disposable Cloud Run service."
  type        = string
  default     = "europe-west4"
}

variable "image" {
  description = "Image reference pushed by spikes/connectivity/deploy-mcp.sh. Empty until the first spike deploy plan (documented in Runbook 06 §3)."
  type        = string
  default     = ""
}

variable "runtime_sa_email" {
  description = "Runtime identity of the MCP service (sa-artifact-mcp)."
  type        = string
}

variable "invoker_sa_email" {
  description = "Only principal allowed to invoke the service (sa-facilitator)."
  type        = string
}

variable "instance_connection_name" {
  description = "Cloud SQL instance connection name for the /cloudsql socket."
  type        = string
}

variable "service_url" {
  description = "Service URL used as the ID-token audience; empty until the service exists (two-step apply)."
  type        = string
  default     = ""
}
