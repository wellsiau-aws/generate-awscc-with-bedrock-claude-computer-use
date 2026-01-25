#!/usr/bin/env python3
"""
TANGO Multi-Agent Pipeline - PR Creation CLI
Command-line interface for creating GitHub pull requests for validated AWSCC resources
"""

import argparse
import json
import sys
from agents.pr_agent import pr_agent
from agents.pr_exceptions import (
    ConfigurationError,
    ResourceNotReadyError,
    GitOperationError,
    GitHubAPIError
)
import config


def validate_configuration():
    """
    Validate PR agent configuration before running.
    
    Returns:
        List of configuration errors (empty if valid)
    """
    errors = config.validate_pr_config()
    return errors


def display_result(result_json: str, dry_run: bool = False):
    """
    Display PR creation result to the user.
    
    Args:
        result_json: JSON string with PR creation result
        dry_run: Whether this was a dry-run execution
    
    Returns:
        Exit code for the process
    """
    try:
        result = json.loads(result_json)
        status = result.get('status')
        error_type = result.get('error_type')
        exit_code = result.get('exit_code', 0)
        
        print("\n" + "="*80)
        
        if status == 'success':
            print("✅ PR CREATION SUCCESSFUL")
            print("="*80)
            print(f"\n📦 Resource: {result.get('resource_name')}")
            print(f"🔀 PR Number: #{result.get('pr_number')}")
            print(f"🔗 PR URL: {result.get('pr_url')}")
            print(f"🌿 Branch: {result.get('branch_name')}")
            print(f"📝 Commit: {result.get('commit_hash')}")
            
            files_created = result.get('files_created', [])
            if files_created:
                print(f"\n📄 Files Created:")
                for file in files_created:
                    print(f"   - {file}")
            
            print(f"\n💬 Message: {result.get('message')}")
            return 0
            
        elif status == 'no_resources':
            print("ℹ️  NO ELIGIBLE RESOURCES")
            print("="*80)
            print(f"\n{result.get('message')}")
            print("\nNo resources are currently ready for PR creation.")
            print("Resources must have:")
            print("  - source='tango_pipeline'")
            print("  - status='success'")
            print("  - No existing pr_status field (or pr_status='failed' for retry)")
            return 0
            
        elif status == 'error':
            print(f"❌ PR CREATION FAILED - {error_type or 'Error'}")
            print("="*80)
            print(f"\n⚠️  Error: {result.get('error')}")
            
            # Display error-specific information
            if error_type == 'ConfigurationError':
                missing_config = result.get('missing_config', [])
                if missing_config:
                    print(f"\n📋 Missing configuration:")
                    for config_key in missing_config:
                        print(f"   - {config_key}")
                
                print("\n💡 How to fix:")
                print("   1. Create or update .env file in the project root:")
                print("      GITHUB_TOKEN=your_github_token_here")
                print("      GITHUB_FORK_URL=https://github.com/your-username/terraform-provider-awscc")
                print("      GIT_USER_NAME=Your Name")
                print("      GIT_USER_EMAIL=your.email@example.com")
                print()
                print("   2. Or set environment variables:")
                print("      export GITHUB_TOKEN='your_token'")
                print("      export GITHUB_FORK_URL='https://github.com/your-username/terraform-provider-awscc'")
                print("      export GIT_USER_NAME='Your Name'")
                print("      export GIT_USER_EMAIL='your.email@example.com'")
            
            elif error_type == 'ResourceNotReadyError':
                resource_name = result.get('resource_name')
                reason = result.get('reason')
                if resource_name:
                    print(f"\n📦 Resource: {resource_name}")
                if reason:
                    print(f"   Reason: {reason}")
                
                print("\n💡 Possible reasons:")
                print("   - Resource not found in DynamoDB")
                print("   - Resource status is not 'success'")
                print("   - Resource source is not 'tango_pipeline'")
                print("   - Required S3 files are missing")
                print("   - Resource already has a PR (pr_status='created')")
            
            elif error_type == 'GitOperationError':
                operation = result.get('operation')
                if operation:
                    print(f"\n🔧 Failed operation: {operation}")
                
                print("\n💡 Common causes:")
                print("   - Authentication failure: Check GITHUB_TOKEN")
                print("   - Network error: Check internet connection")
                print("   - Push conflict: Branch may already exist on remote")
                print("   - Merge conflict: Fork may be out of sync with upstream")
            
            elif error_type == 'GitHubAPIError':
                status_code = result.get('status_code')
                if status_code:
                    print(f"\n🌐 HTTP Status: {status_code}")
                
                print("\n💡 Common causes:")
                if status_code == 401:
                    print("   - Invalid GITHUB_TOKEN")
                    print("   - Token expired or revoked")
                elif status_code == 403:
                    print("   - Rate limit exceeded (wait and retry)")
                    print("   - Insufficient permissions")
                elif status_code == 404:
                    print("   - Repository not found")
                    print("   - Check GITHUB_FORK_URL and GITHUB_UPSTREAM_URL")
                elif status_code == 422:
                    print("   - PR already exists for this branch")
                    print("   - Invalid PR parameters")
                else:
                    print("   - Check GitHub API status")
                    print("   - Verify repository access")
            
            else:
                # Generic error suggestions
                error_msg = result.get('error', '').lower()
                
                if 'github_token' in error_msg or 'authentication' in error_msg:
                    print("\n💡 Suggestion:")
                    print("   Check that GITHUB_TOKEN is set in .env file")
                    print("   Verify the token has 'repo' scope permissions")
                
                elif 'github_fork_url' in error_msg:
                    print("\n💡 Suggestion:")
                    print("   Set GITHUB_FORK_URL environment variable")
                    print("   Example: export GITHUB_FORK_URL='https://github.com/your-username/terraform-provider-awscc'")
                
                elif 'git_user' in error_msg:
                    print("\n💡 Suggestion:")
                    print("   Set GIT_USER_NAME and GIT_USER_EMAIL environment variables")
                    print("   Example:")
                    print("     export GIT_USER_NAME='Your Name'")
                    print("     export GIT_USER_EMAIL='your.email@example.com'")
                
                elif 'already exists' in error_msg:
                    print("\n💡 Suggestion:")
                    print("   A PR already exists for this resource")
                    print("   Check GitHub for existing PRs")
                
                elif 'rate limit' in error_msg:
                    print("\n💡 Suggestion:")
                    print("   GitHub API rate limit exceeded")
                    print("   Wait a few minutes and try again")
                
                elif 'network' in error_msg or 'connection' in error_msg:
                    print("\n💡 Suggestion:")
                    print("   Check your internet connection")
                    print("   Verify GitHub is accessible")
            
            return exit_code
        
        else:
            print("⚠️  UNKNOWN STATUS")
            print("="*80)
            print(f"\nResult: {result_json}")
            return 99
        
        print("\n" + "="*80 + "\n")
        
    except json.JSONDecodeError:
        print("\n" + "="*80)
        print("❌ ERROR - Invalid result format")
        print("="*80)
        print(f"\nRaw result: {result_json}")
        print("\n" + "="*80 + "\n")
        return 99


def main():
    """
    Main entry point for the PR creation CLI.
    """
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Create GitHub pull requests for validated AWSCC Terraform resources',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process next eligible resource (atomic operation)
  python create_pr.py

  # Process specific resource
  python create_pr.py awscc_s3_bucket

  # Dry-run mode (validate without creating PR)
  python create_pr.py --dry-run

  # Dry-run for specific resource
  python create_pr.py --dry-run awscc_s3_bucket

Notes:
  - The agent processes exactly ONE resource per execution (atomic operation)
  - Resources must have source='tango_pipeline' and status='success'
  - Resources with existing pr_status='created' are skipped
  - Resources with pr_status='failed' can be retried

Configuration:
  Required environment variables (set in .env or export):
    - GITHUB_TOKEN: GitHub personal access token with 'repo' scope
    - GITHUB_FORK_URL: URL of your fork (e.g., https://github.com/user/terraform-provider-awscc)
    - GIT_USER_NAME: Git commit author name
    - GIT_USER_EMAIL: Git commit author email
    - AWS_REGION: AWS region for S3/DynamoDB access
    - S3_BUCKET: S3 bucket name for resource content
    - DYNAMODB_TABLE: DynamoDB table name for state tracking
        """
    )
    
    # Add arguments
    parser.add_argument(
        'resource_name',
        nargs='?',
        help='Specific AWSCC resource name to create PR for (e.g., awscc_s3_bucket). If not provided, processes next eligible resource.'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate configuration and show what would be done without creating PR'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Create PR even if one already exists (only valid with specific resource)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Display header
    print("\n" + "="*80)
    print("🔀 TANGO PR AGENT - GitHub Pull Request Creator")
    print("="*80)
    
    # Validate --force flag usage
    if args.force and not args.resource_name:
        print("\n❌ ERROR: --force flag requires a specific resource name")
        print("\nUsage: python create_pr.py --force <resource_name>")
        print("\n" + "="*80 + "\n")
        sys.exit(1)
    
    # Display mode
    if args.dry_run:
        print("\n🔍 Mode: DRY RUN (validation only, no PR will be created)")
    elif args.resource_name:
        print(f"\n📦 Mode: Specific resource")
        print(f"   Resource: {args.resource_name}")
        if args.force:
            print(f"   Force: Yes (will attempt even if PR exists)")
    else:
        print("\n🔄 Mode: Next eligible resource (atomic operation)")
    
    print("="*80)
    
    # Validate configuration
    print("\n🔧 Validating configuration...")
    
    config_errors = validate_configuration()
    
    if config_errors:
        print("\n❌ CONFIGURATION ERROR")
        print("="*80)
        print("\nMissing or invalid configuration:")
        for error in config_errors:
            print(f"   - {error}")
        
        print("\n💡 How to fix:")
        print("   1. Create or update .env file in the project root:")
        print("      GITHUB_TOKEN=your_github_token_here")
        print("      GITHUB_FORK_URL=https://github.com/your-username/terraform-provider-awscc")
        print("      GIT_USER_NAME=Your Name")
        print("      GIT_USER_EMAIL=your.email@example.com")
        print()
        print("   2. Or set environment variables:")
        print("      export GITHUB_TOKEN='your_token'")
        print("      export GITHUB_FORK_URL='https://github.com/your-username/terraform-provider-awscc'")
        print("      export GIT_USER_NAME='Your Name'")
        print("      export GIT_USER_EMAIL='your.email@example.com'")
        print()
        print("   3. Ensure AWS configuration is set (see config.py validation)")
        print("\n" + "="*80 + "\n")
        sys.exit(1)
    
    print("   ✓ Configuration valid")
    print(f"   GitHub Token: {'*' * 8}...{config.GITHUB_TOKEN[-4:] if len(config.GITHUB_TOKEN) > 4 else '****'}")
    print(f"   Fork URL: {config.GITHUB_FORK_URL}")
    print(f"   Git User: {config.GIT_USER_NAME} <{config.GIT_USER_EMAIL}>")
    print(f"   AWS Region: {config.AWS_REGION}")
    print(f"   S3 Bucket: {config.S3_BUCKET}")
    print(f"   DynamoDB Table: {config.DYNAMODB_TABLE}")
    
    # Dry-run mode
    if args.dry_run:
        print("\n" + "="*80)
        print("✅ DRY RUN VALIDATION COMPLETE")
        print("="*80)
        print("\nConfiguration is valid. Ready to create PRs.")
        
        if args.resource_name:
            print(f"\nWould process resource: {args.resource_name}")
        else:
            print("\nWould process next eligible resource from DynamoDB")
        
        print("\nTo create PR, run without --dry-run flag:")
        if args.resource_name:
            print(f"   python create_pr.py {args.resource_name}")
        else:
            print(f"   python create_pr.py")
        
        print("\n" + "="*80 + "\n")
        sys.exit(0)
    
    # Build PR request
    pr_request = {}
    if args.resource_name:
        pr_request['resource_name'] = args.resource_name
    if args.force:
        pr_request['force'] = True
    
    # Execute PR agent
    print("\n" + "="*80)
    print("🚀 STARTING PR CREATION")
    print("="*80 + "\n")
    
    try:
        result_json = pr_agent(json.dumps(pr_request))
        
        # Display result and get exit code
        exit_code = display_result(result_json, dry_run=False)
        
        # Exit with appropriate code
        sys.exit(exit_code)
    
    except KeyboardInterrupt:
        print("\n\n" + "="*80)
        print("⚠️  INTERRUPTED BY USER")
        print("="*80)
        print("\nPR creation was interrupted.")
        print("Cleanup should have been performed automatically.")
        print("\n" + "="*80 + "\n")
        sys.exit(130)  # Standard exit code for SIGINT
    
    except Exception as e:
        print("\n\n" + "="*80)
        print("❌ UNEXPECTED ERROR")
        print("="*80)
        print(f"\nError: {str(e)}")
        print(f"Type: {type(e).__name__}")
        print("\nPlease report this error with the full output.")
        print("\n" + "="*80 + "\n")
        sys.exit(99)


if __name__ == "__main__":
    main()
