terraform {
  required_version = ">= 1.5"
}

resource "terraform_data" "example" {
  input = var.missing
}
