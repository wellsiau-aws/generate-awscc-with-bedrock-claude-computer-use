"""
Configuration module for tango-multi-agent-pipeline.
Requires configuration via environment variables with mandatory validation.
"""
import os
import sys

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()  # Loads from .env file in root directory
except ImportError:
    # python-dotenv not installed, skip loading .env file
    pass

# Required configuration from environment variables
# These MUST be set before running the pipeline
AWS_REGION = os.environ.get("AWS_REGION")
AWS_PROFILE = os.environ.get("AWS_PROFILE", "default")
S3_BUCKET = os.environ.get("S3_BUCKET")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE")

# Optional configuration with defaults
DEFAULT_PROVIDER_VERSION = os.environ.get("DEFAULT_PROVIDER_VERSION", "1.68.0")
TERRAFORM_WORK_DIR = os.environ.get("TERRAFORM_WORK_DIR", "terraform_test")

# GitHub Configuration (for PR agent)
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
GITHUB_FORK_URL = os.getenv('GITHUB_FORK_URL', '')
GITHUB_UPSTREAM_URL = "https://github.com/hashicorp/terraform-provider-awscc"

# Git Configuration (for PR agent)
GIT_USER_NAME = os.getenv('GIT_USER_NAME', 'TANGO Pipeline')
GIT_USER_EMAIL = os.getenv('GIT_USER_EMAIL', 'tango@example.com')

# PR Configuration (for PR agent)
PR_WORK_DIR = os.getenv('PR_WORK_DIR', 'pr_workspace')

def validate_required_config():
    """
    Validate that all required configuration values are set.
    
    Returns:
        List of missing configuration keys
    """
    missing = []
    
    if not AWS_REGION:
        missing.append("AWS_REGION")
    if not S3_BUCKET:
        missing.append("S3_BUCKET")
    if not DYNAMODB_TABLE:
        missing.append("DYNAMODB_TABLE")
    
    return missing

def validate_aws_resources():
    """
    Validate that configured AWS resources exist and are accessible.
    
    Returns:
        List of error messages (empty if all valid)
    """
    errors = []
    
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        
        # Check S3 bucket
        try:
            s3 = boto3.client('s3', region_name=AWS_REGION)
            s3.head_bucket(Bucket=S3_BUCKET)
        except NoCredentialsError:
            errors.append("AWS credentials not configured")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                errors.append(f"S3 bucket '{S3_BUCKET}' does not exist")
            elif error_code == '403':
                errors.append(f"S3 bucket '{S3_BUCKET}' exists but access denied")
            else:
                errors.append(f"S3 bucket '{S3_BUCKET}' not accessible: {e}")
        except Exception as e:
            errors.append(f"Error checking S3 bucket: {e}")
        
        # Check DynamoDB table
        try:
            dynamodb = boto3.client('dynamodb', region_name=AWS_REGION)
            dynamodb.describe_table(TableName=DYNAMODB_TABLE)
        except NoCredentialsError:
            if "AWS credentials not configured" not in errors:
                errors.append("AWS credentials not configured")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                errors.append(f"DynamoDB table '{DYNAMODB_TABLE}' does not exist")
            else:
                errors.append(f"DynamoDB table '{DYNAMODB_TABLE}' not accessible: {e}")
        except Exception as e:
            errors.append(f"Error checking DynamoDB table: {e}")
            
    except ImportError:
        errors.append("boto3 not installed - cannot validate AWS resources")
    
    return errors

def validate_pr_config():
    """
    Validate PR agent configuration.
    
    Returns:
        List of missing/invalid configuration keys
    """
    errors = []
    
    if not GITHUB_TOKEN:
        errors.append("GITHUB_TOKEN not found in .env file or environment")
    
    if not GITHUB_FORK_URL:
        errors.append("GITHUB_FORK_URL environment variable required")
    
    if not GIT_USER_NAME:
        errors.append("GIT_USER_NAME environment variable required")
    
    if not GIT_USER_EMAIL:
        errors.append("GIT_USER_EMAIL environment variable required")
    
    return errors

# Validate required configuration on import
print("🔧 Validating configuration...")

missing_config = validate_required_config()
if missing_config:
    print("❌ CONFIGURATION ERROR: Required environment variables not set")
    print("\nMissing configuration:")
    for key in missing_config:
        print(f"   - {key}")
    
    print("\n💡 How to fix:")
    print("   Set the required environment variables before running:")
    print()
    print("   export AWS_REGION='us-west-2'")
    print("   export S3_BUCKET='tango-project-docs-204034886740'")
    print("   export DYNAMODB_TABLE='tango-pipeline-state'")
    print()
    print("   Or load from Terraform outputs:")
    print("   cd infra")
    print("   export AWS_REGION=$(terraform output -raw aws_region)")
    print("   export S3_BUCKET=$(terraform output -raw s3_bucket_name)")
    print("   export DYNAMODB_TABLE=$(terraform output -raw dynamodb_table_name)")
    print("   cd ..")
    print()
    
    sys.exit(1)

# Show loaded configuration
print("✅ Required configuration loaded:")
print(f"   AWS_REGION: {AWS_REGION}")
print(f"   AWS_PROFILE: {AWS_PROFILE}")
print(f"   S3_BUCKET: {S3_BUCKET}")
print(f"   DYNAMODB_TABLE: {DYNAMODB_TABLE}")

# Validate AWS resources
print("\n🔍 Validating AWS resources...")
validation_errors = validate_aws_resources()

if validation_errors:
    print("❌ AWS resource validation failed:")
    for error in validation_errors:
        print(f"   - {error}")
    
    print("\n� Suggestions:")
    print("   1. Run 'terraform apply' in the infra/ directory to create resources")
    print("   2. Check AWS credentials: aws sts get-caller-identity")
    print("   3. Verify region and resource names are correct")
    print()
    
    sys.exit(1)

print("✅ AWS resources validated:")
print(f"   ✓ S3 bucket '{S3_BUCKET}' is accessible")
print(f"   ✓ DynamoDB table '{DYNAMODB_TABLE}' is accessible")
print("=" * 60)
