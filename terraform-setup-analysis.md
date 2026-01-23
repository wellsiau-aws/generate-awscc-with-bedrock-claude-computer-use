# Terraform Setup Analysis for TANGO Multi-Agent Pipeline

## Overview
This document analyzes the requirements for automating the AWS infrastructure setup (DynamoDB and S3) using Terraform for the TANGO Multi-Agent Pipeline.

## Current Manual Setup Requirements

### 1. DynamoDB Table
**Table Name:** `tango-pipeline-state` (configurable via `DYNAMODB_TABLE` env var)

**Configuration:**
- **Partition Key:** `resource_name` (String)
- **Sort Key:** `timestamp` (Number)
- **Billing Mode:** PAY_PER_REQUEST (on-demand)
- **Region:** `us-west-2` (configurable via `AWS_REGION` env var)

**Access Patterns:**
- **Scan operations:** Discovery agent scans for all processed resources (ProjectionExpression: 'resource_name')
- **Write operations:** Storage agent creates new entries with full schema
- **Delete operations:** Storage agent deletes old entries for the same resource_name before creating new ones

**Item Schema:**
```json
{
  "resource_name": "awscc_s3_bucket",
  "timestamp": 1753897013,
  "status": "success" | "failed",
  "s3_terraform_link": "examples/resources/awscc_s3_bucket/s3_bucket.tf",
  "s3_template_link": "templates/resources/awscc_s3_bucket.md.tmpl",
  "s3_analysis_link": "analysis/resource/awscc_s3_bucket/2025-07-30.txt"
}
```

### 2. S3 Bucket
**Bucket Name:** `tango-project-docs` (configurable via `S3_BUCKET` env var)

**Required Folder Structure:**
```
s3://tango-project-docs/
├── templates/
│   └── resources/
│       ├── generic_resource.md.tmpl  (MUST exist - read by storage agent)
│       └── {resource_name}.md.tmpl   (created by pipeline)
├── examples/
│   └── resources/
│       └── {resource_name}/
│           └── {service_name}.tf     (successful terraform configs)
├── failed/
│   └── resources/
│       └── {resource_name}/
│           └── {service_name}.tf     (failed terraform configs)
└── analysis/
    └── resource/
        └── {resource_name}/
            └── {date}.txt            (validation analysis reports)
```

**Access Patterns:**
- **Read:** Storage agent reads `templates/resources/generic_resource.md.tmpl`
- **Write:** Storage agent writes terraform files, templates, and analysis reports
- **No Delete:** No delete operations detected in code

**Critical Requirement:**
- The file `templates/resources/generic_resource.md.tmpl` MUST exist in the bucket before the pipeline runs
- This file is read by the storage agent's `template_replacer` tool

### 3. IAM Permissions Required

**For the Pipeline Execution Role/User:**

**DynamoDB Permissions:**
- `dynamodb:Scan` - Discovery agent reads processed resources
- `dynamodb:PutItem` - Storage agent creates new entries
- `dynamodb:DeleteItem` - Storage agent removes old entries
- `dynamodb:Query` - Storage agent queries for existing entries

**S3 Permissions:**
- `s3:GetObject` - Read generic template and other files
- `s3:PutObject` - Write terraform configs, templates, and analysis
- `s3:ListBucket` - List bucket contents (implicit requirement)

**AWS CloudControl Permissions:**
- `cloudformation:CreateResource`
- `cloudformation:DeleteResource`
- `cloudformation:GetResource`
- `cloudformation:ListResources`
- `cloudformation:UpdateResource`

**Additional Service Permissions:**
- Wildcard permissions for testing various AWS resources (EC2, Lambda, IAM, etc.)
- This is resource-dependent based on what AWSCC resources are being validated

## Terraform Implementation Requirements

### 1. Resources to Create

#### DynamoDB Table
```hcl
resource "aws_dynamodb_table" "tango_pipeline_state" {
  name           = var.dynamodb_table_name
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "resource_name"
  range_key      = "timestamp"

  attribute {
    name = "resource_name"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  tags = {
    Name        = "TANGO Pipeline State"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
```

#### S3 Bucket
```hcl
resource "aws_s3_bucket" "tango_docs" {
  bucket = var.s3_bucket_name

  tags = {
    Name        = "TANGO Project Documentation"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Enable versioning for safety
resource "aws_s3_bucket_versioning" "tango_docs" {
  bucket = aws_s3_bucket.tango_docs.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "tango_docs" {
  bucket = aws_s3_bucket.tango_docs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "tango_docs" {
  bucket = aws_s3_bucket.tango_docs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
```

#### S3 Folder Structure (via objects)
```hcl
# Create folder structure using empty objects with trailing slashes
resource "aws_s3_object" "folders" {
  for_each = toset([
    "templates/resources/",
    "examples/resources/",
    "failed/resources/",
    "analysis/resource/"
  ])

  bucket  = aws_s3_bucket.tango_docs.id
  key     = each.value
  content = ""
}
```

#### Upload Generic Template
```hcl
resource "aws_s3_object" "generic_template" {
  bucket = aws_s3_bucket.tango_docs.id
  key    = "templates/resources/generic_resource.md.tmpl"
  source = "${path.module}/templates/resources/generic_resource.md.tmpl"
  etag   = filemd5("${path.module}/templates/resources/generic_resource.md.tmpl")

  depends_on = [aws_s3_object.folders]
}
```

#### IAM Policy for Pipeline Execution
```hcl
resource "aws_iam_policy" "tango_pipeline_policy" {
  name        = "tango-pipeline-execution-policy"
  description = "Policy for TANGO pipeline to access DynamoDB and S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query"
        ]
        Resource = aws_dynamodb_table.tango_pipeline_state.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.tango_docs.arn,
          "${aws_s3_bucket.tango_docs.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudformation:CreateResource",
          "cloudformation:DeleteResource",
          "cloudformation:GetResource",
          "cloudformation:ListResources",
          "cloudformation:UpdateResource"
        ]
        Resource = "*"
      }
    ]
  })
}
```

### 2. Variables to Define

```hcl
variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-west-2"
}

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table for pipeline state"
  type        = string
  default     = "tango-pipeline-state"
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for storing documentation"
  type        = string
  default     = "tango-project-docs"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "enable_versioning" {
  description = "Enable S3 bucket versioning"
  type        = bool
  default     = true
}

variable "enable_encryption" {
  description = "Enable S3 bucket encryption"
  type        = bool
  default     = true
}
```

### 3. Outputs to Provide

```hcl
output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.tango_pipeline_state.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.tango_pipeline_state.arn
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.tango_docs.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.tango_docs.arn
}

output "s3_bucket_region" {
  description = "Region of the S3 bucket"
  value       = aws_s3_bucket.tango_docs.region
}

output "iam_policy_arn" {
  description = "ARN of the IAM policy for pipeline execution"
  value       = aws_iam_policy.tango_pipeline_policy.arn
}

output "setup_complete" {
  description = "Confirmation message"
  value       = "TANGO infrastructure setup complete. Update config.py with these values."
}
```

## File Structure for Terraform Module

```
terraform/
├── main.tf                          # Main resource definitions
├── variables.tf                     # Input variables
├── outputs.tf                       # Output values
├── versions.tf                      # Provider version constraints
├── terraform.tfvars.example         # Example variable values
├── README.md                        # Terraform module documentation
└── templates/
    └── resources/
        └── generic_resource.md.tmpl # Template file to upload to S3
```

## Additional Considerations

### 1. S3 Bucket Naming
- S3 bucket names must be globally unique
- Consider adding a random suffix or account ID to the default bucket name
- Example: `tango-project-docs-${data.aws_caller_identity.current.account_id}`

### 2. State Management
- Terraform state should be stored remotely (S3 backend) for team collaboration
- Consider creating a separate S3 bucket for Terraform state
- Enable state locking with DynamoDB

### 3. Cost Optimization
- DynamoDB PAY_PER_REQUEST is good for variable workloads
- Consider lifecycle policies for S3 to archive old analysis reports
- Add tags for cost allocation

### 4. Security Enhancements
- Enable CloudTrail logging for audit trail
- Add bucket policies to restrict access
- Consider using KMS for encryption instead of AES256
- Implement least-privilege IAM policies

### 5. Disaster Recovery
- Enable S3 versioning (already included)
- Consider cross-region replication for critical data
- Enable point-in-time recovery for DynamoDB

### 6. Monitoring & Alerts
- CloudWatch alarms for DynamoDB throttling
- S3 bucket metrics and notifications
- Cost anomaly detection

## Integration with Python Application

After Terraform creates the infrastructure, the Python application needs:

1. **Environment Variables:**
   ```bash
   export AWS_REGION="<terraform_output_s3_bucket_region>"
   export S3_BUCKET="<terraform_output_s3_bucket_name>"
   export DYNAMODB_TABLE="<terraform_output_dynamodb_table_name>"
   ```

2. **IAM Permissions:**
   - Attach the created IAM policy to the execution role/user
   - Or use the policy ARN from Terraform outputs

3. **Verification Script:**
   - Create a Python script to verify connectivity to DynamoDB and S3
   - Check that the generic template exists in S3

## Next Steps for Spec Creation

1. **Define Terraform module structure**
2. **Create variable definitions with validation**
3. **Implement resource configurations**
4. **Add data sources for account ID and region**
5. **Create outputs for integration**
6. **Write module documentation**
7. **Add examples and usage instructions**
8. **Create verification/validation scripts**
9. **Update USAGE.md with Terraform setup instructions**
10. **Add cleanup/destroy instructions**
