# Technology Stack

## Core Framework

- **Python 3.8+**: Primary language
- **Strands Agent SDK**: Multi-agent orchestration framework
- **Terraform 1.0+**: Infrastructure as Code validation
- **AWS CLI 2.0+**: AWS resource management

## Key Dependencies

```
strands-agents>=0.1.0          # Agent framework
strands-agents-tools>=0.1.0    # Agent tooling
boto3>=1.26.0                  # AWS SDK
botocore[crt]                  # AWS core with CRT support
requests>=2.31.0               # HTTP client
```

## AWS Services

- **DynamoDB**: Pipeline state tracking
- **S3**: Result storage
- **CloudControl API**: Resource validation
- **IAM**: Permission management
- **Multiple AWS services**: For resource testing (EC2, Lambda, etc.)

## Common Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials
aws configure

# Load Terraform outputs as environment variables
cd infra
export AWS_REGION=$(terraform output -raw aws_region)
export S3_BUCKET=$(terraform output -raw s3_bucket_name)
export DYNAMODB_TABLE=$(terraform output -raw dynamodb_table_name)
cd ..
```

### Running the Pipeline
```bash
# Process next unprocessed resource
python main.py

# Target specific resource
python target_resource.py awscc_s3_bucket

# Target with specific provider version
python target_resource.py awscc_s3_bucket 1.48.0

# Evaluate code quality
python evaluation_agent.py awscc_s3_bucket
```

### Terraform Operations
```bash
# Initialize Terraform (in terraform_test directory)
cd terraform_test
terraform init
terraform validate
terraform plan
terraform apply -auto-approve
terraform destroy -auto-approve
cd ..
```

## Configuration

Configuration is managed via `config.py` with environment variables:

- `AWS_REGION`: Target AWS region (required)
- `AWS_PROFILE`: AWS profile (default: "default")
- `S3_BUCKET`: S3 bucket for results (required)
- `DYNAMODB_TABLE`: DynamoDB table for state (required)
- `DEFAULT_PROVIDER_VERSION`: AWSCC provider version (default: "1.53.0")
- `TERRAFORM_WORK_DIR`: Terraform working directory (default: "terraform_test")

Configuration validation runs on import and checks for:
1. Required environment variables
2. AWS resource accessibility
3. AWS credentials validity
