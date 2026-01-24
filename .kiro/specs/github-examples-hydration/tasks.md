# Implementation Plan: GitHub Examples Hydration

## Overview

This implementation creates a standalone Python script that hydrates the TANGO pipeline's DynamoDB table and S3 bucket with validated AWSCC Terraform examples from the HashiCorp GitHub repository. The script will be implemented as a single-file utility with clear separation of concerns through classes, following the sequential processing model defined in the design.

## Tasks

- [x] 1. Create script structure and configuration management
  - Create `hydrate_from_github.py` in project root
  - Implement `HydrationConfig` class to load settings from config.py
  - Add command-line argument parsing (--dry-run, --filter, --github-token)
  - Implement configuration validation (check AWS credentials, S3 bucket, DynamoDB table)
  - Add early failure for missing or invalid configuration
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 5.2, 5.3, 5.5_

- [x] 2. Implement GitHub API client
  - [x] 2.1 Create `GitHubClient` class with authentication support
    - Initialize with optional GitHub token
    - Set up requests session with appropriate headers
    - Implement base URL and API version configuration
    - _Requirements: 1.3, 1.4_
  
  - [x] 2.2 Implement resource discovery methods
    - Add `list_resource_directories()` to fetch examples/resources/ listing
    - Parse GitHub API response to extract directory names
    - Filter for directories only (exclude files)
    - _Requirements: 1.1_
  
  - [x] 2.3 Implement file listing and content fetching
    - Add `list_terraform_files()` to get .tf files for a resource
    - Add `fetch_file_content()` to download file content
    - Decode base64 content from GitHub API response
    - _Requirements: 2.1, 2.4_
  
  - [x] 2.4 Add rate limiting and retry logic
    - Implement exponential backoff with jitter
    - Check X-RateLimit-Remaining and X-RateLimit-Reset headers
    - Sleep until rate limit reset when exhausted
    - Retry network errors up to 3 times
    - _Requirements: 1.2, 1.5, 5.4_
  
  - [x] 2.5 Add error handling for GitHub operations
    - Handle 404 errors gracefully (log and skip)
    - Handle 5xx errors with retry logic
    - Validate file content is non-empty
    - _Requirements: 2.3, 2.5_

- [ ] 3. Checkpoint - Verify GitHub client works
  - Test with --dry-run and --filter flags on a single resource
  - Verify resource discovery and file fetching work correctly
  - Ensure rate limiting and retry logic function properly

- [ ] 4. Implement AWS storage management
  - [ ] 4.1 Create `StorageManager` class
    - Initialize with S3 bucket name, DynamoDB table name, and dry-run flag
    - Set up boto3 clients for S3 and DynamoDB
    - _Requirements: 7.1_
  
  - [ ] 4.2 Implement S3 operations
    - Add `construct_s3_path()` to build path: examples/resources/{resource_name}/{filename}.tf
    - Add `file_exists_in_s3()` to check for existing files
    - Add `upload_to_s3()` to upload file content with error handling
    - Skip upload if file already exists
    - Log all operations (actual or simulated for dry-run)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 8.3_
  
  - [ ] 4.3 Implement DynamoDB operations
    - Add `entry_exists_in_dynamodb()` to check for existing entries with source="hashicorp_github"
    - Add `create_dynamodb_entry()` to write resource metadata
    - Use resource_name as partition key
    - Generate ISO 8601 UTC timestamp as sort key
    - Set status="success" and source="hashicorp_github"
    - Include s3_terraform_link field
    - Skip write if entry already exists
    - Log all operations (actual or simulated for dry-run)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.1, 8.2, 8.4, 8.5_

- [ ] 5. Implement orchestration and workflow
  - [ ] 5.1 Create `HydrationOrchestrator` class
    - Initialize with HydrationConfig, GitHubClient, and StorageManager
    - Set up logging with visual separators
    - _Requirements: 6.1, 6.5_
  
  - [ ] 5.2 Implement resource processing logic
    - Add `process_resource()` method for single resource handling
    - Fetch all .tf files for the resource
    - Upload each file to S3 (with existence check)
    - Create DynamoDB entry for each uploaded file
    - Track success/failure/skip counts per resource
    - Isolate errors (continue processing on failure)
    - Log progress for each resource
    - _Requirements: 2.1, 2.2, 3.5, 5.1, 6.2, 8.4_
  
  - [ ] 5.3 Implement main workflow
    - Add `run()` method to execute complete hydration
    - Discover all resources from GitHub
    - Apply resource filter if provided
    - Process each resource sequentially
    - Collect results for all resources
    - Generate summary report
    - _Requirements: 1.1, 7.3, 6.3_
  
  - [ ] 5.4 Implement reporting
    - Create `HydrationReport` dataclass
    - Track total resources, successful, failed, skipped counts
    - Track total files uploaded and DynamoDB entries created
    - Collect error messages
    - Calculate execution duration
    - Format and display summary report
    - _Requirements: 6.3, 6.4_

- [ ] 6. Add main entry point and CLI
  - Create `main()` function with argument parsing
  - Add argparse configuration for --dry-run, --filter, --github-token
  - Initialize configuration and validate AWS resources
  - Create and run orchestrator
  - Handle top-level exceptions with clear error messages
  - Exit with appropriate status code (0 for success, non-zero for failure)
  - Add `if __name__ == "__main__"` block
  - _Requirements: 5.5, 7.2, 7.3, 7.4, 7.5_

- [ ] 7. Final checkpoint - Manual verification
  - Run with --dry-run flag to verify logic without AWS writes
  - Run with --filter awscc_s3_bucket to test single resource
  - Verify S3 upload and DynamoDB entry in AWS Console
  - Review logs for completeness and error handling
  - Run full hydration and verify summary report

## Notes

- Script is designed as a one-time hydration utility (no automated tests)
- Manual verification through dry-run mode and small batch testing
- Each task builds incrementally with checkpoints for validation
- Error isolation ensures partial failures don't stop the entire process
- Idempotent design allows safe re-runs
