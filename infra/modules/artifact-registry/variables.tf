variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "repository_id" {
  description = "Repository id (final name is <repository_id> in <region>)."
  type        = string
}
