terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "unused" {
  type = string
}

resource "aws_s3_bucket" "data" {
  bucket = "swe-metrics-fixture"
}
