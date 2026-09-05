variable "project_id" {
  description = "Google Cloud project whose APIs are enabled."
  type        = string
}

variable "services" {
  description = "Set of Service Usage API names to enable."
  type        = set(string)
}
