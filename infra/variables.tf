# Input variable declarations for TANGO Pipeline Infrastructure
# This file will contain all configurable parameters

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table for pipeline state tracking"
  type        = string
  default     = "tango-pipeline-state"
}
variable "s3_bucket_prefix" {
  description = "Prefix for the S3 bucket name (account ID will be appended)"
  type        = string
  default     = "tango-project-docs"
}
variable "aws_region" {
  description = "AWS region where resources will be created"
  type        = string
  default     = "us-west-2"
}
variable "encryption_type" {
  description = "Type of encryption for S3 bucket (AES256 or aws:kms)"
  type        = string
  default     = "AES256"

  validation {
    condition     = contains(["AES256", "aws:kms"], var.encryption_type)
    error_message = "Encryption type must be either AES256 or aws:kms"
  }
}
variable "kms_key_id" {
  description = "KMS key ID for S3 encryption (required if encryption_type is aws:kms)"
  type        = string
  default     = null
}
variable "enable_point_in_time_recovery" {
  description = "Enable point-in-time recovery for DynamoDB table"
  type        = bool
  default     = true
}
variable "force_destroy_bucket" {
  description = "Allow destruction of S3 bucket even if it contains objects"
  type        = bool
  default     = false
}
variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
