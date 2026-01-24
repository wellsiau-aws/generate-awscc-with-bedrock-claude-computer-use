#!/usr/bin/env python3
"""
GitHub Examples Hydration Script

This script hydrates the TANGO pipeline's DynamoDB table and S3 bucket with
validated AWSCC Terraform examples from the HashiCorp GitHub repository.

Usage:
    python hydrate_from_github.py [--dry-run] [--filter PATTERN] [--github-token TOKEN]

Examples:
    # Dry-run mode (preview without making changes)
    python hydrate_from_github.py --dry-run

    # Process only S3-related resources
    python hydrate_from_github.py --filter awscc_s3_*

    # Use GitHub authentication for higher rate limits
    python hydrate_from_github.py --github-token ghp_xxxxxxxxxxxxx
"""

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


@dataclass
class HydrationConfig:
    """Configuration for the hydration script."""
    
    aws_region: str
    s3_bucket: str
    dynamodb_table: str
    github_token: Optional[str] = None
    dry_run: bool = False
    resource_filter: Optional[str] = None
    
    @classmethod
    def from_config(cls, args: argparse.Namespace) -> "HydrationConfig":
        """
        Load configuration from config.py and command-line arguments.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            HydrationConfig instance
            
        Raises:
            SystemExit: If required configuration is missing
        """
        # Import config.py to get AWS settings
        # Note: config.py validates on import and exits if invalid
        try:
            import config
        except SystemExit:
            # config.py already printed error messages
            raise
        
        # Load configuration from config.py
        aws_region = config.AWS_REGION
        s3_bucket = config.S3_BUCKET
        dynamodb_table = config.DYNAMODB_TABLE
        
        # Get GitHub token from args or environment
        github_token = args.github_token or os.environ.get("GITHUB_TOKEN")
        
        return cls(
            aws_region=aws_region,
            s3_bucket=s3_bucket,
            dynamodb_table=dynamodb_table,
            github_token=github_token,
            dry_run=args.dry_run,
            resource_filter=args.filter
        )
    
    def validate(self) -> None:
        """
        Validate that AWS resources are accessible.
        
        This performs additional validation beyond config.py to ensure
        the script can successfully interact with AWS services.
        
        Raises:
            SystemExit: If validation fails
        """
        print("\n" + "="*80)
        print("🔍 HYDRATION CONFIGURATION VALIDATION")
        print("="*80)
        
        errors = []
        
        # Validate AWS credentials
        try:
            sts = boto3.client('sts', region_name=self.aws_region)
            identity = sts.get_caller_identity()
            print(f"✅ AWS credentials valid (Account: {identity['Account']})")
        except NoCredentialsError:
            errors.append("AWS credentials not configured")
        except Exception as e:
            errors.append(f"Failed to validate AWS credentials: {e}")
        
        # Validate S3 bucket access
        try:
            s3 = boto3.client('s3', region_name=self.aws_region)
            s3.head_bucket(Bucket=self.s3_bucket)
            print(f"✅ S3 bucket '{self.s3_bucket}' is accessible")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                errors.append(f"S3 bucket '{self.s3_bucket}' does not exist")
            elif error_code == '403':
                errors.append(f"S3 bucket '{self.s3_bucket}' access denied")
            else:
                errors.append(f"S3 bucket '{self.s3_bucket}' error: {e}")
        except Exception as e:
            errors.append(f"Failed to check S3 bucket: {e}")
        
        # Validate DynamoDB table access
        try:
            dynamodb = boto3.client('dynamodb', region_name=self.aws_region)
            dynamodb.describe_table(TableName=self.dynamodb_table)
            print(f"✅ DynamoDB table '{self.dynamodb_table}' is accessible")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                errors.append(f"DynamoDB table '{self.dynamodb_table}' does not exist")
            else:
                errors.append(f"DynamoDB table '{self.dynamodb_table}' error: {e}")
        except Exception as e:
            errors.append(f"Failed to check DynamoDB table: {e}")
        
        # Display configuration
        print("\n📋 Configuration:")
        print(f"   AWS Region: {self.aws_region}")
        print(f"   S3 Bucket: {self.s3_bucket}")
        print(f"   DynamoDB Table: {self.dynamodb_table}")
        print(f"   GitHub Token: {'✓ Provided' if self.github_token else '✗ Not provided (rate limits apply)'}")
        print(f"   Dry Run: {'✓ Enabled (no AWS writes)' if self.dry_run else '✗ Disabled (will write to AWS)'}")
        print(f"   Resource Filter: {self.resource_filter or 'None (process all resources)'}")
        
        # Fail fast if errors found
        if errors:
            print("\n" + "="*80)
            print("❌ CONFIGURATION VALIDATION FAILED")
            print("="*80)
            for error in errors:
                print(f"   ✗ {error}")
            print("\n💡 Suggestions:")
            print("   1. Ensure AWS credentials are configured: aws sts get-caller-identity")
            print("   2. Verify S3 bucket and DynamoDB table exist")
            print("   3. Check IAM permissions for S3 and DynamoDB access")
            print("="*80 + "\n")
            sys.exit(1)
        
        print("\n" + "="*80)
        print("✅ CONFIGURATION VALIDATION PASSED")
        print("="*80 + "\n")


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Hydrate TANGO pipeline with GitHub examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run mode (preview without making changes)
  python hydrate_from_github.py --dry-run

  # Process only S3-related resources
  python hydrate_from_github.py --filter awscc_s3_*

  # Use GitHub authentication for higher rate limits
  python hydrate_from_github.py --github-token ghp_xxxxxxxxxxxxx

  # Combine options
  python hydrate_from_github.py --dry-run --filter awscc_s3_bucket
        """
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview operations without making AWS changes"
    )
    
    parser.add_argument(
        "--filter",
        type=str,
        metavar="PATTERN",
        help="Process only resources matching this pattern (e.g., awscc_s3_*)"
    )
    
    parser.add_argument(
        "--github-token",
        type=str,
        metavar="TOKEN",
        help="GitHub personal access token for authentication (increases rate limits)"
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the hydration script.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    print("\n" + "="*80)
    print("🚀 GITHUB EXAMPLES HYDRATION SCRIPT")
    print("="*80 + "\n")
    
    try:
        # Parse command-line arguments
        args = parse_arguments()
        
        # Load and validate configuration
        config = HydrationConfig.from_config(args)
        config.validate()
        
        # TODO: Initialize GitHub client
        # TODO: Initialize storage manager
        # TODO: Create and run orchestrator
        
        print("✅ Hydration script initialized successfully")
        print("⚠️  Implementation incomplete - remaining tasks to be implemented")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Hydration interrupted by user")
        return 130
    except SystemExit as e:
        # Re-raise SystemExit from config validation
        raise
    except Exception as e:
        print("\n" + "="*80)
        print("❌ HYDRATION FAILED")
        print("="*80)
        print(f"Error: {e}")
        print("="*80 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
