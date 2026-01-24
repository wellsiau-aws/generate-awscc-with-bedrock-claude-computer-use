# Output value declarations for TANGO Pipeline Infrastructure
# This file will contain outputs for configuring the Python application

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for pipeline state tracking"
  value       = aws_dynamodb_table.pipeline_state.name
}
output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table for pipeline state tracking"
  value       = aws_dynamodb_table.pipeline_state.arn
}
output "s3_bucket_name" {
  description = "Name of the S3 bucket for storing Terraform configurations and reports"
  value       = aws_s3_bucket.project_docs.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for storing Terraform configurations and reports"
  value       = aws_s3_bucket.project_docs.arn
}
output "aws_region" {
  description = "AWS region where resources were created"
  value       = var.aws_region
}

output "generic_template_path" {
  description = "S3 path to the generic resource template"
  value       = "s3://${aws_s3_bucket.project_docs.id}/${aws_s3_object.generic_template.key}"
}
