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

## Testing Guidelines

### Creating Test Files

**CRITICAL**: Always create actual `.py` test files instead of using inline Python with `-c` flag.

**Why:**
- The `cd` command is not allowed in bash execution
- Inline Python with `-c` flag is error-prone with multi-line code
- Test files are reusable and can be version controlled
- Test files provide better error messages and debugging

**Pattern to Follow:**

```python
# ✅ CORRECT: Create a test file
# 1. Create test_feature.py
# 2. Run: python3 test_feature.py
# 3. Clean up after successful test

# ❌ INCORRECT: Don't use inline Python
# cd /path && python3 -c "..."  # This will fail!
```

**Example:**

```python
# test_my_model.py
from agents.models import MyModel

def test_valid_model():
    result = MyModel(field1="value1", field2="value2")
    assert result.is_valid == True
    print("✅ Test passed")

if __name__ == '__main__':
    test_valid_model()
```

Then run:
```bash
python3 test_my_model.py
```

**Cleanup:**
- Delete test files after successful validation
- Keep test files if they will be reused or added to test suite

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
