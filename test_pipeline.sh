#!/bin/bash

# TANGO Pipeline Test Script
# This script configures and tests the TANGO Multi-Agent Pipeline with Terraform-provisioned infrastructure

set -e  # Exit on error

echo "🎯 TANGO Pipeline Test Script"
echo "================================"
echo ""

# Set environment variables from Terraform outputs
export AWS_REGION="us-west-2"
export DYNAMODB_TABLE="tango-pipeline-state"
export S3_BUCKET="tango-project-docs-204034886740"
export GENERIC_TEMPLATE_PATH="s3://tango-project-docs-204034886740/templates/resources/generic_resource.md.tmpl"

# Optional: Set AWS profile if needed
# export AWS_PROFILE="your-profile-name"

echo "📋 Configuration:"
echo "  AWS Region: $AWS_REGION"
echo "  DynamoDB Table: $DYNAMODB_TABLE"
echo "  S3 Bucket: $S3_BUCKET"
echo "  Template Path: $GENERIC_TEMPLATE_PATH"
echo ""

# Verify AWS credentials
echo "🔐 Verifying AWS credentials..."
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ Error: AWS credentials not configured or invalid"
    echo "   Please configure AWS credentials using 'aws configure' or set AWS_PROFILE"
    exit 1
fi
echo "✅ AWS credentials verified"
echo ""

# Verify DynamoDB table exists
echo "🗄️  Verifying DynamoDB table..."
if aws dynamodb describe-table --table-name "$DYNAMODB_TABLE" --region "$AWS_REGION" > /dev/null 2>&1; then
    echo "✅ DynamoDB table '$DYNAMODB_TABLE' exists"
else
    echo "❌ Error: DynamoDB table '$DYNAMODB_TABLE' not found"
    echo "   Please run 'terraform apply' in the terraform/ directory first"
    exit 1
fi
echo ""

# Verify S3 bucket exists
echo "🪣 Verifying S3 bucket..."
if aws s3 ls "s3://$S3_BUCKET" --region "$AWS_REGION" > /dev/null 2>&1; then
    echo "✅ S3 bucket '$S3_BUCKET' exists"
else
    echo "❌ Error: S3 bucket '$S3_BUCKET' not found"
    echo "   Please run 'terraform apply' in the terraform/ directory first"
    exit 1
fi
echo ""

# Verify generic template exists in S3
echo "📄 Verifying generic template..."
if aws s3 ls "$GENERIC_TEMPLATE_PATH" --region "$AWS_REGION" > /dev/null 2>&1; then
    echo "✅ Generic template exists in S3"
else
    echo "⚠️  Warning: Generic template not found in S3"
    echo "   The template will be uploaded when you run 'terraform apply'"
fi
echo ""

# Check Python dependencies
echo "🐍 Checking Python dependencies..."
if ! python3 -c "import boto3" 2>/dev/null; then
    echo "❌ Error: boto3 not installed"
    echo "   Please run: pip install -r requirements.txt"
    exit 1
fi
echo "✅ Python dependencies available"
echo ""

# Run a quick test - check if we can query DynamoDB
echo "🧪 Running connectivity test..."
echo "   Querying DynamoDB table for existing records..."
RECORD_COUNT=$(aws dynamodb scan --table-name "$DYNAMODB_TABLE" --select "COUNT" --region "$AWS_REGION" --output json | python3 -c "import sys, json; print(json.load(sys.stdin)['Count'])")
echo "✅ Found $RECORD_COUNT record(s) in DynamoDB table"
echo ""

# List S3 bucket contents
echo "📂 S3 Bucket structure:"
aws s3 ls "s3://$S3_BUCKET/" --recursive --region "$AWS_REGION" | head -20
echo ""

echo "✅ All infrastructure checks passed!"
echo ""
echo "🚀 Ready to run the pipeline!"
echo ""
echo "To run the pipeline, execute:"
echo "  python3 main.py"
echo ""
echo "Or to run a specific agent test:"
echo "  python3 -c 'from agents.discovery_agent import DiscoveryAgent; agent = DiscoveryAgent(); print(agent.discover_resources())'"
echo ""
