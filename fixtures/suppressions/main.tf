resource "aws_s3_bucket" "logs" {
  #checkov:skip=CKV_AWS_18: the log bucket does not log itself
}
