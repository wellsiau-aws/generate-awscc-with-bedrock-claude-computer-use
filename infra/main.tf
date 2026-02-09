# Main Terraform configuration for TANGO Pipeline Infrastructure
# This file will contain resource definitions for DynamoDB and S3

# Data source to retrieve AWS account ID for creating globally unique S3 bucket name
data "aws_caller_identity" "current" {}

# DynamoDB Table for Pipeline State Tracking
resource "aws_dynamodb_table" "pipeline_state" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "resource_name"
  range_key    = "timestamp"

  attribute {
    name = "resource_name"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  tags = merge(
    var.tags,
    {
      Name      = var.dynamodb_table_name
      ManagedBy = "Terraform"
    }
  )
}
# S3 Bucket for Project Documentation and Pipeline Artifacts
resource "aws_s3_bucket" "project_docs" {
  bucket = "${var.s3_bucket_prefix}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.tags,
    {
      Name      = "${var.s3_bucket_prefix}-${data.aws_caller_identity.current.account_id}"
      ManagedBy = "Terraform"
    }
  )
}

# Enable versioning on S3 bucket for data protection and rollback capability
resource "aws_s3_bucket_versioning" "project_docs" {
  bucket = aws_s3_bucket.project_docs.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Configure server-side encryption for S3 bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "project_docs" {
  bucket = aws_s3_bucket.project_docs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.encryption_type
      kms_master_key_id = var.encryption_type == "aws:kms" ? var.kms_key_id : null
    }
  }
}
# Block all public access to S3 bucket for security
resource "aws_s3_bucket_public_access_block" "project_docs" {
  bucket = aws_s3_bucket.project_docs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Create S3 folder structure for organizing pipeline artifacts
resource "aws_s3_object" "folders" {
  for_each = toset([
    "templates/resources/",
    "examples/resources/",
    "failed/resources/",
    "analysis/resource/"
  ])

  bucket       = aws_s3_bucket.project_docs.id
  key          = each.value
  content_type = "application/x-directory"

  tags = var.tags
}

# Upload generic resource template file (critical for storage agent)
resource "aws_s3_object" "generic_template" {
  bucket       = aws_s3_bucket.project_docs.id
  key          = "templates/resources/generic_resource.md.tmpl"
  source       = "${path.module}/../templates/resources/generic_resource.md.tmpl"
  etag         = filemd5("${path.module}/../templates/resources/generic_resource.md.tmpl")
  content_type = "text/plain"

  tags = merge(
    var.tags,
    {
      Name     = "generic_resource_template"
      Critical = "true"
    }
  )
}
