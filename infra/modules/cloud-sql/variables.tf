variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "instance_name" {
  type = string
}

variable "tier" {
  description = "Machine tier; db-f1-micro is the smallest practical choice."
  type        = string
  default     = "db-f1-micro"
}

variable "iam_login_sa_emails" {
  description = "Runtime SA emails that need Cloud SQL IAM database login."
  type        = set(string)
}
