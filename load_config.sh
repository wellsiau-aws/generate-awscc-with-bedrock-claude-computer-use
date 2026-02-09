#!/bin/bash
# Load configuration from Terraform outputs
# Usage: source load_config.sh

echo "🔧 Loading configuration from Terraform outputs..."

cd infra

# Check if Terraform state exists
if [ ! -f "terraform.tfstate" ]; then
    echo "❌ Error: terraform.tfstate not found"
    echo "   Run 'terraform apply' first to create infrastructure"
    cd ..
    return 1
fi

# Load configuration from Terraform outputs
export AWS_REGION=$(terraform output -raw aws_region 2>/dev/null)
export S3_BUCKET=$(terraform output -raw s3_bucket_name 2>/dev/null)
export DYNAMODB_TABLE=$(terraform output -raw dynamodb_table_name 2>/dev/null)

cd ..

# Verify all values were loaded
if [ -z "$AWS_REGION" ] || [ -z "$S3_BUCKET" ] || [ -z "$DYNAMODB_TABLE" ]; then
    echo "❌ Error: Failed to load configuration from Terraform"
    echo "   Make sure Terraform outputs are defined in infra/outputs.tf"
    return 1
fi

echo "✅ Configuration loaded successfully:"
echo "   AWS_REGION=$AWS_REGION"
echo "   S3_BUCKET=$S3_BUCKET"
echo "   DYNAMODB_TABLE=$DYNAMODB_TABLE"
echo ""
echo "You can now run: python main.py"
