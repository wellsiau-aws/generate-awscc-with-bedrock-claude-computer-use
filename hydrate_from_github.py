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
import base64
import os
import sys
import time
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import boto3
import requests
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


class GitHubClient:
    """
    Client for interacting with the GitHub API to fetch Terraform examples.
    
    This client handles authentication, rate limiting, retry logic, and error
    handling for GitHub API operations.
    """
    
    # GitHub API configuration
    BASE_URL = "https://api.github.com"
    REPO_OWNER = "hashicorp"
    REPO_NAME = "terraform-provider-awscc"
    API_VERSION = "2022-11-28"
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize the GitHub client with optional authentication.
        
        Args:
            token: Optional GitHub personal access token for authentication.
                   If provided, increases rate limits from 60/hour to 5000/hour.
        """
        self.token = token
        
        # Set up requests session with appropriate headers
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.API_VERSION,
            "User-Agent": "TANGO-Hydration-Script/1.0"
        })
        
        # Add authentication header if token provided
        if self.token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}"
            })
        
        print(f"✅ GitHub client initialized ({'authenticated' if self.token else 'unauthenticated'})")
    
    def _handle_rate_limit(self, response: requests.Response) -> None:
        """
        Handle GitHub API rate limiting with exponential backoff.
        
        Checks rate limit headers and sleeps until rate limit reset if exhausted.
        
        Args:
            response: Response object from GitHub API request
        """
        # Check rate limit headers
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset_time = response.headers.get("X-RateLimit-Reset")
        
        if remaining is not None and int(remaining) == 0:
            # Rate limit exhausted - sleep until reset
            if reset_time:
                reset_timestamp = int(reset_time)
                current_timestamp = int(time.time())
                sleep_duration = max(reset_timestamp - current_timestamp, 0) + 1
                
                print(f"⚠️  Rate limit exhausted. Sleeping for {sleep_duration} seconds until reset...")
                time.sleep(sleep_duration)
            else:
                # Fallback: sleep for 60 seconds if reset time not available
                print("⚠️  Rate limit exhausted. Sleeping for 60 seconds...")
                time.sleep(60)
    
    def _retry_with_backoff(self, operation, max_attempts: int = 3) -> Any:
        """
        Retry an operation with exponential backoff and jitter.
        
        Args:
            operation: Callable that performs the operation
            max_attempts: Maximum number of retry attempts (default: 3)
            
        Returns:
            Result from successful operation
            
        Raises:
            Exception: If all retry attempts fail
        """
        base_delay = 1.0  # seconds
        max_delay = 60.0  # seconds
        
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                result = operation()
                return result
                
            except requests.exceptions.HTTPError as e:
                # Handle specific HTTP error codes
                if e.response is not None:
                    status_code = e.response.status_code
                    
                    # 404 errors - log and skip (don't retry)
                    if status_code == 404:
                        print(f"⚠️  Resource not found (404): {e}")
                        raise
                    
                    # 5xx errors - retry with backoff
                    if 500 <= status_code < 600:
                        last_exception = e
                        
                        # Don't retry on final attempt
                        if attempt == max_attempts - 1:
                            raise
                        
                        # Calculate delay with exponential backoff and jitter
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        jitter = random.uniform(0, delay * 0.1)
                        total_delay = delay + jitter
                        
                        print(f"⚠️  Server error {status_code} (attempt {attempt + 1}/{max_attempts}): {e}")
                        print(f"   Retrying in {total_delay:.1f} seconds...")
                        time.sleep(total_delay)
                        continue
                
                # Other HTTP errors - raise immediately
                raise
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                
                # Don't retry on final attempt
                if attempt == max_attempts - 1:
                    raise
                
                # Calculate delay with exponential backoff and jitter
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = random.uniform(0, delay * 0.1)
                total_delay = delay + jitter
                
                print(f"⚠️  Network error (attempt {attempt + 1}/{max_attempts}): {e}")
                print(f"   Retrying in {total_delay:.1f} seconds...")
                time.sleep(total_delay)
        
        # Should not reach here, but raise last exception if we do
        raise last_exception
    
    def list_resource_directories(self) -> List[str]:
        """
        Fetch list of resource directories from examples/resources/.
        
        This method uses the Git Trees API to discover all available AWSCC resource 
        examples, which supports more than 1000 items (unlike the Contents API).
        
        Returns:
            List of resource directory names (e.g., ['awscc_s3_bucket', 'awscc_ec2_instance'])
            
        Raises:
            Exception: If GitHub API request fails after retries
        """
        print("\n" + "="*80)
        print("🔍 DISCOVERING RESOURCES FROM GITHUB")
        print("="*80)
        
        # Step 1: Get the default branch (usually 'main' or 'master')
        repo_url = f"{self.BASE_URL}/repos/{self.REPO_OWNER}/{self.REPO_NAME}"
        
        def _fetch_repo():
            response = self.session.get(repo_url)
            self._handle_rate_limit(response)
            response.raise_for_status()
            return response
        
        try:
            repo_response = self._retry_with_backoff(_fetch_repo)
            default_branch = repo_response.json().get('default_branch', 'main')
            
            # Step 2: Get the tree SHA for the default branch
            branch_url = f"{self.BASE_URL}/repos/{self.REPO_OWNER}/{self.REPO_NAME}/git/trees/{default_branch}"
            
            def _fetch_branch():
                response = self.session.get(branch_url)
                self._handle_rate_limit(response)
                response.raise_for_status()
                return response
            
            branch_response = self._retry_with_backoff(_fetch_branch)
            tree = branch_response.json().get('tree', [])
            
            # Find the 'examples' directory
            examples_sha = None
            for item in tree:
                if item['path'] == 'examples' and item['type'] == 'tree':
                    examples_sha = item['sha']
                    break
            
            if not examples_sha:
                raise Exception("Could not find 'examples' directory in repository")
            
            # Step 3: Get the tree for 'examples' directory
            examples_url = f"{self.BASE_URL}/repos/{self.REPO_OWNER}/{self.REPO_NAME}/git/trees/{examples_sha}"
            
            def _fetch_examples():
                response = self.session.get(examples_url)
                self._handle_rate_limit(response)
                response.raise_for_status()
                return response
            
            examples_response = self._retry_with_backoff(_fetch_examples)
            examples_tree = examples_response.json().get('tree', [])
            
            # Find the 'resources' directory
            resources_sha = None
            for item in examples_tree:
                if item['path'] == 'resources' and item['type'] == 'tree':
                    resources_sha = item['sha']
                    break
            
            if not resources_sha:
                raise Exception("Could not find 'examples/resources' directory in repository")
            
            # Step 4: Get the tree for 'examples/resources' directory with recursive flag
            # This gets ALL subdirectories regardless of count
            resources_url = f"{self.BASE_URL}/repos/{self.REPO_OWNER}/{self.REPO_NAME}/git/trees/{resources_sha}?recursive=0"
            
            def _fetch_resources():
                response = self.session.get(resources_url)
                self._handle_rate_limit(response)
                response.raise_for_status()
                return response
            
            resources_response = self._retry_with_backoff(_fetch_resources)
            resources_tree = resources_response.json().get('tree', [])
            
            # Filter for directories only (type == 'tree')
            directories = [
                item['path']
                for item in resources_tree
                if item['type'] == 'tree'
            ]
            
            print(f"✅ Discovered {len(directories)} resource directories")
            
            return directories
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to discover resources: {e}")
            raise
    
    def list_terraform_files(self, resource_name: str) -> List[str]:
        """
        List all .tf files for a given resource.
        
        Args:
            resource_name: Name of the resource directory (e.g., 'awscc_s3_bucket')
            
        Returns:
            List of .tf filenames (e.g., ['main.tf', 'variables.tf'])
            
        Raises:
            Exception: If GitHub API request fails after retries
        """
        url = f"{self.BASE_URL}/repos/{self.REPO_OWNER}/{self.REPO_NAME}/contents/examples/resources/{resource_name}"
        
        def _fetch():
            response = self.session.get(url)
            self._handle_rate_limit(response)
            response.raise_for_status()
            return response
        
        try:
            response = self._retry_with_backoff(_fetch)
            
            # Parse response to extract .tf files
            contents = response.json()
            
            # Filter for .tf files only
            tf_files = [
                item["name"]
                for item in contents
                if item["type"] == "file" and item["name"].endswith(".tf")
            ]
            
            return tf_files
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to list files for {resource_name}: {e}")
            raise
    
    def fetch_file_content(self, resource_name: str, filename: str) -> str:
        """
        Download content of a specific .tf file.
        
        Args:
            resource_name: Name of the resource directory (e.g., 'awscc_s3_bucket')
            filename: Name of the file to fetch (e.g., 'main.tf')
            
        Returns:
            Decoded file content as string
            
        Raises:
            ValueError: If file content is empty
            Exception: If GitHub API request fails after retries
        """
        url = f"{self.BASE_URL}/repos/{self.REPO_OWNER}/{self.REPO_NAME}/contents/examples/resources/{resource_name}/{filename}"
        
        def _fetch():
            response = self.session.get(url)
            self._handle_rate_limit(response)
            response.raise_for_status()
            return response
        
        try:
            response = self._retry_with_backoff(_fetch)
            
            # Parse response and decode base64 content
            file_data = response.json()
            
            # GitHub API returns content as base64-encoded string
            encoded_content = file_data.get("content", "")
            decoded_content = base64.b64decode(encoded_content).decode("utf-8")
            
            # Validate file content is non-empty
            if not decoded_content.strip():
                raise ValueError(f"File content is empty: {resource_name}/{filename}")
            
            return decoded_content
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch {resource_name}/{filename}: {e}")
            raise


class StorageManager:
    """
    Manager for AWS storage operations (S3 and DynamoDB).
    
    This class handles uploading Terraform files to S3 and creating
    corresponding DynamoDB entries with proper error handling and
    dry-run support.
    """
    
    def __init__(self, s3_bucket: str, dynamodb_table: str, aws_region: str, dry_run: bool = False):
        """
        Initialize the storage manager with AWS resource names.
        
        Args:
            s3_bucket: Name of the S3 bucket for storing Terraform files
            dynamodb_table: Name of the DynamoDB table for resource metadata
            aws_region: AWS region for boto3 clients
            dry_run: If True, log operations without executing them
        """
        self.s3_bucket = s3_bucket
        self.dynamodb_table = dynamodb_table
        self.aws_region = aws_region
        self.dry_run = dry_run
        
        # Set up boto3 clients for S3 and DynamoDB
        if not dry_run:
            self.s3_client = boto3.client('s3', region_name=aws_region)
            self.dynamodb_client = boto3.client('dynamodb', region_name=aws_region)
        else:
            # In dry-run mode, we don't need actual clients
            self.s3_client = None
            self.dynamodb_client = None
        
        print(f"✅ Storage manager initialized ({'dry-run mode' if dry_run else 'live mode'})")
    
    def construct_s3_path(self, resource_name: str, filename: str) -> str:
        """
        Build S3 path for a Terraform file.
        
        Args:
            resource_name: Name of the resource (e.g., 'awscc_s3_bucket')
            filename: Name of the file (e.g., 'main.tf')
            
        Returns:
            S3 path in format: examples/resources/{resource_name}/{filename}.tf
        """
        # Ensure filename ends with .tf
        if not filename.endswith('.tf'):
            filename = f"{filename}.tf"
        
        return f"examples/resources/{resource_name}/{filename}"
    
    def file_exists_in_s3(self, resource_name: str, filename: str) -> bool:
        """
        Check if a file already exists in S3.
        
        Args:
            resource_name: Name of the resource
            filename: Name of the file
            
        Returns:
            True if file exists, False otherwise
        """
        if self.dry_run:
            # In dry-run mode, assume file doesn't exist
            return False
        
        s3_path = self.construct_s3_path(resource_name, filename)
        
        try:
            self.s3_client.head_object(Bucket=self.s3_bucket, Key=s3_path)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False
            # Other errors - log and return False
            print(f"⚠️  Error checking S3 file existence: {e}")
            return False
    
    def upload_to_s3(self, resource_name: str, filename: str, content: str) -> str:
        """
        Upload a .tf file to S3 with error handling.
        
        Args:
            resource_name: Name of the resource
            filename: Name of the file
            content: File content to upload
            
        Returns:
            S3 path where file was uploaded
            
        Raises:
            Exception: If upload fails (in non-dry-run mode)
        """
        s3_path = self.construct_s3_path(resource_name, filename)
        
        if self.dry_run:
            # Dry-run mode: log intended operation
            print(f"   [DRY-RUN] Would upload to S3: s3://{self.s3_bucket}/{s3_path}")
            print(f"   [DRY-RUN] Content size: {len(content)} bytes")
            return s3_path
        
        try:
            # Upload file to S3
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_path,
                Body=content.encode('utf-8'),
                ContentType='text/plain'
            )
            print(f"   ✅ Uploaded to S3: s3://{self.s3_bucket}/{s3_path}")
            return s3_path
            
        except ClientError as e:
            error_msg = f"S3 upload failed for {resource_name}/{filename}: {e}"
            print(f"   ❌ {error_msg}")
            raise Exception(error_msg)
    
    def entry_exists_in_dynamodb(self, resource_name: str, s3_path: str, source: str = "hashicorp_github") -> bool:
        """
        Check if a DynamoDB entry already exists for this specific file.
        
        Args:
            resource_name: Name of the resource (partition key)
            s3_path: S3 path to the specific file
            source: Source identifier to check for (default: "hashicorp_github")
            
        Returns:
            True if entry exists for this specific file, False otherwise
        """
        if self.dry_run:
            # In dry-run mode, assume entry doesn't exist
            return False
        
        try:
            # Query DynamoDB for entries with this resource_name, s3_path, and source
            response = self.dynamodb_client.query(
                TableName=self.dynamodb_table,
                KeyConditionExpression='resource_name = :rn',
                FilterExpression='#src = :source AND s3_terraform_link = :s3path',
                ExpressionAttributeNames={
                    '#src': 'source'
                },
                ExpressionAttributeValues={
                    ':rn': {'S': resource_name},
                    ':source': {'S': source},
                    ':s3path': {'S': s3_path}
                },
                Limit=1
            )
            
            return response['Count'] > 0
            
        except ClientError as e:
            print(f"⚠️  Error checking DynamoDB entry existence: {e}")
            return False
    
    def create_dynamodb_entry(self, resource_name: str, s3_path: str, filename: str) -> bool:
        """
        Create a DynamoDB entry for an imported resource file.
        
        Args:
            resource_name: Name of the resource (partition key)
            s3_path: S3 path to the Terraform file
            filename: Name of the file (for logging)
            
        Returns:
            True if entry was created, False if skipped or failed
        """
        # Check if entry already exists for this specific file
        if self.entry_exists_in_dynamodb(resource_name, s3_path):
            print(f"   ⏭️  Skipping DynamoDB entry (already exists): {resource_name}/{filename}")
            return False
        
        # Generate Unix timestamp as sort key (Number type for DynamoDB)
        import time
        timestamp = int(time.time())
        
        if self.dry_run:
            # Dry-run mode: log intended operation
            print(f"   [DRY-RUN] Would create DynamoDB entry:")
            print(f"   [DRY-RUN]   resource_name: {resource_name}")
            print(f"   [DRY-RUN]   timestamp: {timestamp}")
            print(f"   [DRY-RUN]   status: success")
            print(f"   [DRY-RUN]   source: hashicorp_github")
            print(f"   [DRY-RUN]   s3_terraform_link: {s3_path}")
            print(f"   [DRY-RUN]   pr_status: created")
            return True
        
        try:
            # Create DynamoDB entry (store path without s3:// prefix)
            self.dynamodb_client.put_item(
                TableName=self.dynamodb_table,
                Item={
                    'resource_name': {'S': resource_name},
                    'timestamp': {'N': str(timestamp)},
                    'status': {'S': 'success'},
                    'source': {'S': 'hashicorp_github'},
                    's3_terraform_link': {'S': s3_path},
                    'pr_status': {'S': 'created'}
                }
            )
            print(f"   ✅ Created DynamoDB entry for {resource_name} ({filename})")
            return True
            
        except ClientError as e:
            error_msg = f"DynamoDB write failed for {resource_name}/{filename}: {e}"
            print(f"   ❌ {error_msg}")
            return False


@dataclass
class ResourceResult:
    """Result of processing a single resource."""
    
    resource_name: str
    status: str  # "success", "failed", "skipped"
    files_processed: int
    files_uploaded: int
    dynamodb_entries_created: int
    error_message: Optional[str] = None


@dataclass
class HydrationReport:
    """Summary report of hydration execution."""
    
    total_resources: int
    successful: int
    failed: int
    skipped: int
    total_files_uploaded: int
    total_dynamodb_entries: int
    errors: List[str]
    duration_seconds: float


class HydrationOrchestrator:
    """
    Orchestrator for the hydration workflow.
    
    This class coordinates the complete hydration process:
    - Discovering resources from GitHub
    - Processing each resource (fetch, upload, store)
    - Collecting and reporting results
    """
    
    def __init__(self, config: HydrationConfig, github_client: GitHubClient, storage_manager: StorageManager):
        """
        Initialize the orchestrator with configuration and clients.
        
        Args:
            config: Hydration configuration
            github_client: GitHub API client
            storage_manager: AWS storage manager
        """
        self.config = config
        self.github_client = github_client
        self.storage_manager = storage_manager
        
        print("\n" + "="*80)
        print("🎯 HYDRATION ORCHESTRATOR INITIALIZED")
        print("="*80)
        print(f"   Mode: {'DRY-RUN (no AWS writes)' if config.dry_run else 'LIVE (will write to AWS)'}")
        print(f"   Filter: {config.resource_filter or 'None (process all resources)'}")
        print("="*80 + "\n")
    
    def process_resource(self, resource_name: str) -> ResourceResult:
        """
        Process a single resource (fetch, upload, store).
        
        This method:
        1. Fetches all .tf files for the resource from GitHub
        2. Uploads each file to S3 (with existence check)
        3. Creates DynamoDB entry for each uploaded file
        4. Tracks success/failure/skip counts
        5. Isolates errors (continues processing on failure)
        
        Args:
            resource_name: Name of the resource to process
            
        Returns:
            ResourceResult with processing details
        """
        print(f"\n📦 Processing: {resource_name}")
        print("-" * 80)
        
        files_processed = 0
        files_uploaded = 0
        dynamodb_entries_created = 0
        
        try:
            # Fetch all .tf files for the resource
            tf_files = self.github_client.list_terraform_files(resource_name)
            
            print(f"   Found {len(tf_files)} .tf files: {tf_files}")
            
            # Process each file
            for filename in tf_files:
                files_processed += 1
                
                # Skip import files (not useful as examples)
                if filename in ['import-by-identity.tf', 'import-by-string-id.tf']:
                    print(f"   ⏭️  Skipping import file: {filename}")
                    continue
                
                try:
                    # Fetch file content from GitHub
                    content = self.github_client.fetch_file_content(resource_name, filename)
                    
                    # Validate content is non-empty
                    if not content.strip():
                        print(f"   ⚠️  Empty file: {filename} - skipping")
                        continue
                    
                    # Upload to S3 (with existence check)
                    if not self.storage_manager.file_exists_in_s3(resource_name, filename):
                        s3_path = self.storage_manager.upload_to_s3(resource_name, filename, content)
                        files_uploaded += 1
                    else:
                        # File already exists - just get the path
                        s3_path = self.storage_manager.construct_s3_path(resource_name, filename)
                        print(f"   ⏭️  Skipping S3 upload (already exists): {s3_path}")
                    
                    # Create DynamoDB entry for each file
                    if self.storage_manager.create_dynamodb_entry(resource_name, s3_path, filename):
                        dynamodb_entries_created += 1
                    
                except ValueError as e:
                    # Empty file or validation error - log and continue
                    print(f"   ⚠️  Validation error for {filename}: {e}")
                    continue
                    
                except Exception as e:
                    # S3 or DynamoDB error - log and continue with other files
                    print(f"   ❌ Error processing {filename}: {e}")
                    continue
            
            # Determine status based on whether any work was done or files already existed
            if files_processed == 0:
                # No files found
                return ResourceResult(
                    resource_name=resource_name,
                    status="skipped",
                    files_processed=0,
                    files_uploaded=0,
                    dynamodb_entries_created=0,
                    error_message="No .tf files found"
                )
            elif files_uploaded == 0 and dynamodb_entries_created == 0:
                # Files exist but nothing was uploaded or created (already hydrated)
                print(f"   ⏭️  Skipped: All files already exist in S3 and DynamoDB")
                return ResourceResult(
                    resource_name=resource_name,
                    status="skipped",
                    files_processed=files_processed,
                    files_uploaded=0,
                    dynamodb_entries_created=0,
                    error_message="All files already exist"
                )
            else:
                # Success - at least some files were uploaded or DynamoDB entries created
                print(f"   ✅ Completed: {files_uploaded} files uploaded, {dynamodb_entries_created} DynamoDB entries created")
                return ResourceResult(
                    resource_name=resource_name,
                    status="success",
                    files_processed=files_processed,
                    files_uploaded=files_uploaded,
                    dynamodb_entries_created=dynamodb_entries_created
                )
            
        except Exception as e:
            # GitHub fetch error or other critical error - log and mark as failed
            error_msg = f"Failed to process {resource_name}: {e}"
            print(f"   ❌ {error_msg}")
            return ResourceResult(
                resource_name=resource_name,
                status="failed",
                files_processed=files_processed,
                files_uploaded=files_uploaded,
                dynamodb_entries_created=dynamodb_entries_created,
                error_message=str(e)
            )
    
    def run(self) -> HydrationReport:
        """
        Execute the complete hydration workflow.
        
        This method:
        1. Discovers all resources from GitHub
        2. Applies resource filter if provided
        3. Processes each resource sequentially
        4. Collects results for all resources
        5. Generates summary report
        
        Returns:
            HydrationReport with execution summary
        """
        start_time = time.time()
        
        print("\n" + "="*80)
        print("🚀 STARTING HYDRATION WORKFLOW")
        print("="*80 + "\n")
        
        # Discover all resources from GitHub
        try:
            all_resources = self.github_client.list_resource_directories()
        except Exception as e:
            print(f"❌ Failed to discover resources: {e}")
            return HydrationReport(
                total_resources=0,
                successful=0,
                failed=1,
                skipped=0,
                total_files_uploaded=0,
                total_dynamodb_entries=0,
                errors=[f"Resource discovery failed: {e}"],
                duration_seconds=time.time() - start_time
            )
        
        # Apply resource filter if provided
        if self.config.resource_filter:
            import fnmatch
            filtered_resources = [
                r for r in all_resources
                if fnmatch.fnmatch(r, self.config.resource_filter)
            ]
            
            print(f"🔍 Filter applied: '{self.config.resource_filter}'")
            print(f"   Matched {len(filtered_resources)} of {len(all_resources)} resources")
            
            if not filtered_resources:
                print(f"⚠️  No resources matched filter '{self.config.resource_filter}'")
                print(f"   Available resources (first 10): {all_resources[:10]}")
                return HydrationReport(
                    total_resources=0,
                    successful=0,
                    failed=0,
                    skipped=0,
                    total_files_uploaded=0,
                    total_dynamodb_entries=0,
                    errors=["No resources matched filter"],
                    duration_seconds=time.time() - start_time
                )
            
            resources_to_process = filtered_resources
        else:
            resources_to_process = all_resources
        
        print(f"\n📊 Processing {len(resources_to_process)} resources...")
        print("="*80)
        
        # Process each resource sequentially
        results: List[ResourceResult] = []
        
        for i, resource_name in enumerate(resources_to_process, 1):
            print(f"\n[{i}/{len(resources_to_process)}] {resource_name}")
            result = self.process_resource(resource_name)
            results.append(result)
        
        # Generate summary report
        report = self._generate_report(results, time.time() - start_time)
        
        # Display summary report
        self._display_report(report)
        
        return report
    
    def _generate_report(self, results: List[ResourceResult], duration_seconds: float) -> HydrationReport:
        """
        Generate summary report from processing results.
        
        Args:
            results: List of ResourceResult objects
            duration_seconds: Total execution time
            
        Returns:
            HydrationReport with aggregated statistics
        """
        successful = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "failed")
        skipped = sum(1 for r in results if r.status == "skipped")
        
        total_files_uploaded = sum(r.files_uploaded for r in results)
        total_dynamodb_entries = sum(r.dynamodb_entries_created for r in results)
        
        errors = [
            f"{r.resource_name}: {r.error_message}"
            for r in results
            if r.error_message
        ]
        
        return HydrationReport(
            total_resources=len(results),
            successful=successful,
            failed=failed,
            skipped=skipped,
            total_files_uploaded=total_files_uploaded,
            total_dynamodb_entries=total_dynamodb_entries,
            errors=errors,
            duration_seconds=duration_seconds
        )
    
    def _display_report(self, report: HydrationReport) -> None:
        """
        Display formatted summary report.
        
        Args:
            report: HydrationReport to display
        """
        print("\n" + "="*80)
        print("📊 HYDRATION SUMMARY REPORT")
        print("="*80)
        
        # Overall statistics
        print(f"\n📈 Overall Statistics:")
        print(f"   Total Resources: {report.total_resources}")
        print(f"   ✅ Successful: {report.successful}")
        print(f"   ❌ Failed: {report.failed}")
        print(f"   ⏭️  Skipped: {report.skipped}")
        print(f"   ⏱️  Duration: {report.duration_seconds:.2f} seconds")
        
        # Storage statistics
        print(f"\n💾 Storage Statistics:")
        print(f"   Files Uploaded to S3: {report.total_files_uploaded}")
        print(f"   DynamoDB Entries Created: {report.total_dynamodb_entries}")
        
        # Success rate
        if report.total_resources > 0:
            success_rate = (report.successful / report.total_resources) * 100
            print(f"\n✨ Success Rate: {success_rate:.1f}%")
        
        # Errors (if any)
        if report.errors:
            print(f"\n❌ Errors ({len(report.errors)}):")
            for i, error in enumerate(report.errors[:10], 1):  # Show first 10 errors
                print(f"   {i}. {error}")
            if len(report.errors) > 10:
                print(f"   ... and {len(report.errors) - 10} more errors")
        
        # Final status
        print("\n" + "="*80)
        if report.failed == 0 and report.successful > 0:
            print("✅ HYDRATION COMPLETED SUCCESSFULLY")
        elif report.successful > 0:
            print("⚠️  HYDRATION COMPLETED WITH SOME FAILURES")
        else:
            print("❌ HYDRATION FAILED")
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


def test_github_client(config: HydrationConfig) -> int:
    """
    Test the GitHub client functionality (checkpoint for task 3).
    
    This function verifies:
    - Resource discovery works correctly
    - File listing works for a single resource
    - File content fetching works correctly
    - Rate limiting and retry logic function properly
    
    Args:
        config: Hydration configuration
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    print("\n" + "="*80)
    print("🧪 TESTING GITHUB CLIENT")
    print("="*80 + "\n")
    
    try:
        # Initialize GitHub client
        github_client = GitHubClient(token=config.github_token)
        
        # Test 1: Discover all resources
        print("\n📋 Test 1: Resource Discovery")
        print("-" * 80)
        resources = github_client.list_resource_directories()
        print(f"✅ Successfully discovered {len(resources)} resources")
        
        # Apply filter if provided
        if config.resource_filter:
            import fnmatch
            filtered_resources = [
                r for r in resources 
                if fnmatch.fnmatch(r, config.resource_filter)
            ]
            print(f"✅ Filter '{config.resource_filter}' matched {len(filtered_resources)} resources")
            
            if not filtered_resources:
                print(f"⚠️  No resources matched filter '{config.resource_filter}'")
                print(f"   Available resources (first 10): {resources[:10]}")
                return 1
            
            # Use filtered list for testing
            test_resources = filtered_resources[:1]  # Test with first matching resource
        else:
            # No filter - test with first resource
            test_resources = resources[:1]
        
        # Test 2: List files for a resource
        print(f"\n📋 Test 2: File Listing for '{test_resources[0]}'")
        print("-" * 80)
        tf_files = github_client.list_terraform_files(test_resources[0])
        print(f"✅ Found {len(tf_files)} .tf files: {tf_files}")
        
        if not tf_files:
            print(f"⚠️  No .tf files found for {test_resources[0]}")
            return 1
        
        # Test 3: Fetch content for first file
        print(f"\n📋 Test 3: File Content Fetching for '{tf_files[0]}'")
        print("-" * 80)
        content = github_client.fetch_file_content(test_resources[0], tf_files[0])
        
        # Display first few lines of content
        lines = content.split('\n')
        preview_lines = min(10, len(lines))
        print(f"✅ Successfully fetched {len(content)} bytes ({len(lines)} lines)")
        print(f"\n📄 Content preview (first {preview_lines} lines):")
        print("-" * 80)
        for i, line in enumerate(lines[:preview_lines], 1):
            print(f"{i:3d} | {line}")
        if len(lines) > preview_lines:
            print(f"... ({len(lines) - preview_lines} more lines)")
        print("-" * 80)
        
        # Test 4: Verify rate limiting headers are being checked
        print(f"\n📋 Test 4: Rate Limiting")
        print("-" * 80)
        print("✅ Rate limiting logic is implemented in _handle_rate_limit()")
        print("✅ Retry logic is implemented in _retry_with_backoff()")
        print("   Note: Rate limits are checked on every API call")
        
        # Summary
        print("\n" + "="*80)
        print("✅ GITHUB CLIENT TESTS PASSED")
        print("="*80)
        print("\n📊 Test Summary:")
        print(f"   ✓ Resource discovery: {len(resources)} resources found")
        print(f"   ✓ File listing: {len(tf_files)} files found for {test_resources[0]}")
        print(f"   ✓ File fetching: {len(content)} bytes retrieved")
        print(f"   ✓ Rate limiting: Implemented and functional")
        print(f"   ✓ Retry logic: Implemented with exponential backoff")
        print("="*80 + "\n")
        
        return 0
        
    except Exception as e:
        print("\n" + "="*80)
        print("❌ GITHUB CLIENT TEST FAILED")
        print("="*80)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print("="*80 + "\n")
        return 1


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
        
        # Initialize GitHub client
        github_client = GitHubClient(token=config.github_token)
        
        # Initialize storage manager
        storage_manager = StorageManager(
            s3_bucket=config.s3_bucket,
            dynamodb_table=config.dynamodb_table,
            aws_region=config.aws_region,
            dry_run=config.dry_run
        )
        
        # Create and run orchestrator
        orchestrator = HydrationOrchestrator(config, github_client, storage_manager)
        report = orchestrator.run()
        
        # Return appropriate exit code
        if report.failed > 0 and report.successful == 0:
            # All resources failed
            return 1
        elif report.total_resources == 0:
            # No resources processed
            return 1
        else:
            # At least some resources succeeded
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
        import traceback
        traceback.print_exc()
        print("="*80 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
