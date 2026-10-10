terraform {
  required_version = ">= 1.5"
}

variable "name" {
  type = string
}

resource "terraform_data" "example" {
  input = var.name
}
