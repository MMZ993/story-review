variable "project_id" {
  type = string
}

variable "secret_names" {
  description = "Map of service key to Secret Manager secret id."
  type        = map(string)
}

variable "sa_emails" {
  description = "Map of service key to the runtime SA email that may read that secret."
  type        = map(string)
}

variable "deployer_sa_email" {
  type = string
}
