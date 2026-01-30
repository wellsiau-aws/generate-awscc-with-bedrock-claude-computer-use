"""
TANGO Pipeline - PR Tools Data Models

This module provides Pydantic models for type-safe data validation in PR tool
interactions. All PR tools use these models to ensure validated, structured data
exchange with automatic validation and clear error messages.

The PR tools handle GitHub pull request creation workflow for AWS CloudControl
resources, including:
- Fetching resource content from S3
- Discovering eligible resources for PR creation
- Setting up git repositories
- Placing files in repository structure
- Running HashiCorp validation commands
- Creating GitHub pull requests
- Updating PR status in DynamoDB
- Git commit and push operations

Models are organized into two categories:
1. Input Models: Validate tool input parameters before execution
2. Output Models: Validate tool output structure and provide convenience properties

All models inherit from TANGOBaseModel (defined in agents/models.py) to ensure
consistent configuration and behavior across the TANGO pipeline.

Input Models:
    S3LinksInput: Input for fetch_resource_content tool
    FileContentInput: Input for place_files_in_structure tool
    PRContentInput: Input for create_github_pr tool
    PRStatusInput: Input for update_pr_status tool

Output Models:
    ResourceContentResult: Output from fetch_resource_content tool
    EligibleResourceResult: Output from get_next_eligible_resource tool
    RepoSetupResult: Output from clone_and_setup_repo tool
    FilePlacementResult: Output from place_files_in_structure tool
    ValidationCommandResult: Individual validation command result (nested in HashiCorpValidationResult)
    HashiCorpValidationResult: Output from run_hashicorp_validation tool
    GitHubPRResult: Output from create_github_pr tool
    PRStatusUpdateResult: Output from update_pr_status tool
    GitCommitPushResult: Output from git_commit_and_push tool

Usage:
    from agents.pr_models import S3LinksInput, ResourceContentResult
    
    # Create validated input model
    s3_links = S3LinksInput(
        s3_terraform_link="examples/resources/awscc_s3_bucket/s3_bucket.tf",
        s3_template_link="templates/resources/s3_bucket.md.tmpl"
    )
    
    # Call tool with model
    result = fetch_resource_content(resource_name="awscc_s3_bucket", s3_links=s3_links)
    
    # Access fields with type safety
    if result.is_success:
        terraform_code = result.terraform_code
        print(f"Fetched code: {terraform_code}")
    
    # Serialize back to JSON
    json_output = result.model_dump_json()

Author: TANGO Team
Version: 1.0.0
"""

from typing import Dict, List, Optional

from pydantic import Field, field_validator

from agents.models import TANGOBaseModel


# =============================================================================
# Input Models - Tool Parameters
# =============================================================================


# =============================================================================
# Output Models - Tool Results
# =============================================================================
