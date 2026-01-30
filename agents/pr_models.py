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


class S3LinksInput(TANGOBaseModel):
    """
    Input model for S3 links to resource content files.
    
    Used by the fetch_resource_content tool to specify S3 locations of Terraform
    code, template files, and optional analysis reports. All S3 links are validated
    to ensure they are non-empty strings.
    
    Attributes:
        s3_terraform_link: S3 key for the Terraform configuration file. Must be a
                          non-empty string pointing to the .tf file location.
        s3_template_link: S3 key for the markdown template file. Must be a non-empty
                         string pointing to the .md.tmpl file location.
        s3_analysis_link: Optional S3 key for the analysis report file. When provided,
                         points to the analysis markdown file location.
    
    Validation:
        - s3_terraform_link must not be empty (min_length=1)
        - s3_template_link must not be empty (min_length=1)
        - s3_analysis_link is optional
    
    Usage Examples:
        # Create with all fields
        >>> s3_links = S3LinksInput(
        ...     s3_terraform_link="examples/resources/awscc_s3_bucket/s3_bucket.tf",
        ...     s3_template_link="templates/resources/s3_bucket.md.tmpl",
        ...     s3_analysis_link="analysis/resource/awscc_s3_bucket/report.md"
        ... )
        >>> print(s3_links.s3_terraform_link)
        examples/resources/awscc_s3_bucket/s3_bucket.tf
        
        # Create without optional analysis link
        >>> s3_links = S3LinksInput(
        ...     s3_terraform_link="examples/resources/awscc_lambda_function/lambda.tf",
        ...     s3_template_link="templates/resources/lambda_function.md.tmpl"
        ... )
        >>> print(s3_links.s3_analysis_link)
        None
        
        # Parse from JSON
        >>> json_str = '''
        ... {
        ...     "s3_terraform_link": "examples/resources/awscc_dynamodb_table/table.tf",
        ...     "s3_template_link": "templates/resources/dynamodb_table.md.tmpl"
        ... }
        ... '''
        >>> s3_links = S3LinksInput.model_validate_json(json_str)
        >>> print(s3_links.s3_terraform_link)
        examples/resources/awscc_dynamodb_table/table.tf
        
        # Validation error on empty string
        >>> try:
        ...     invalid = S3LinksInput(
        ...         s3_terraform_link="",  # Empty string not allowed
        ...         s3_template_link="templates/resources/test.md.tmpl"
        ...     )
        ... except ValidationError as e:
        ...     print("Validation failed: empty s3_terraform_link")
        Validation failed: empty s3_terraform_link
        
        # Serialize back to JSON
        >>> json_output = s3_links.model_dump_json()
    
    Notes:
        - All S3 links are keys (paths) within the S3 bucket, not full URLs
        - The fetch_resource_content tool uses these links to retrieve file content
        - Empty strings are rejected to prevent fetching errors
        - The analysis link is optional because not all resources have analysis reports
        - All validation happens automatically on model instantiation
        - Invalid data raises pydantic.ValidationError with detailed error messages
    """
    
    s3_terraform_link: str = Field(
        description="S3 key for Terraform configuration file",
        min_length=1,
        examples=[
            "examples/resources/awscc_s3_bucket/s3_bucket.tf",
            "examples/resources/awscc_lambda_function/lambda.tf",
            "examples/resources/awscc_dynamodb_table/table.tf"
        ]
    )
    
    s3_template_link: str = Field(
        description="S3 key for markdown template file",
        min_length=1,
        examples=[
            "templates/resources/s3_bucket.md.tmpl",
            "templates/resources/lambda_function.md.tmpl",
            "templates/resources/dynamodb_table.md.tmpl"
        ]
    )
    
    s3_analysis_link: Optional[str] = Field(
        default=None,
        description="S3 key for analysis report file (optional)",
        examples=[
            None,
            "analysis/resource/awscc_s3_bucket/report.md",
            "analysis/resource/awscc_lambda_function/report.md"
        ]
    )


class FileContentInput(TANGOBaseModel):
    """
    Input model for file content to place in repository structure.
    
    Used by the place_files_in_structure tool to specify the Terraform code,
    template content, and service name for creating files in the repository.
    All fields are validated to ensure they contain valid, non-empty content.
    
    Attributes:
        terraform_code: The Terraform configuration code content. Must be a non-empty
                       string containing the complete .tf file content.
        template: The markdown template content. Must be a non-empty string containing
                 the complete .md.tmpl file content.
        service_name: The AWS service name in lowercase with underscores. Must match
                     the pattern of lowercase letters, numbers, and underscores only.
                     Used for organizing files in the repository structure.
    
    Validation:
        - terraform_code must not be empty (min_length=1)
        - template must not be empty (min_length=1)
        - service_name must match pattern: ^[a-z0-9_]+$
    
    Usage Examples:
        # Create with valid content
        >>> content = FileContentInput(
        ...     terraform_code='resource "awscc_s3_bucket" "example" { bucket_name = "my-bucket" }',
        ...     template="# S3 Bucket\\n\\nThis resource creates an S3 bucket.",
        ...     service_name="s3_bucket"
        ... )
        >>> print(content.service_name)
        s3_bucket
        
        # Create with multi-line Terraform code
        >>> tf_code = '''
        ... resource "awscc_lambda_function" "example" {
        ...   function_name = "my-function"
        ...   runtime       = "python3.9"
        ...   handler       = "index.handler"
        ... }
        ... '''
        >>> content = FileContentInput(
        ...     terraform_code=tf_code,
        ...     template="# Lambda Function\\n\\nCreates a Lambda function.",
        ...     service_name="lambda_function"
        ... )
        >>> print(content.service_name)
        lambda_function
        
        # Parse from JSON
        >>> json_str = '''
        ... {
        ...     "terraform_code": "resource \\"awscc_dynamodb_table\\" \\"example\\" {}",
        ...     "template": "# DynamoDB Table",
        ...     "service_name": "dynamodb_table"
        ... }
        ... '''
        >>> content = FileContentInput.model_validate_json(json_str)
        >>> print(content.service_name)
        dynamodb_table
        
        # Validation error on empty terraform_code
        >>> try:
        ...     invalid = FileContentInput(
        ...         terraform_code="",  # Empty string not allowed
        ...         template="# Test",
        ...         service_name="test"
        ...     )
        ... except ValidationError as e:
        ...     print("Validation failed: empty terraform_code")
        Validation failed: empty terraform_code
        
        # Validation error on invalid service_name pattern
        >>> try:
        ...     invalid = FileContentInput(
        ...         terraform_code="resource {}",
        ...         template="# Test",
        ...         service_name="Invalid-Name"  # Uppercase and dash not allowed
        ...     )
        ... except ValidationError as e:
        ...     print("Validation failed: invalid service_name pattern")
        Validation failed: invalid service_name pattern
        
        # Serialize back to JSON
        >>> json_output = content.model_dump_json()
    
    Notes:
        - terraform_code contains the actual Terraform configuration, not a file path
        - template contains the actual markdown template content, not a file path
        - service_name must be lowercase with underscores (e.g., "s3_bucket", not "S3Bucket")
        - The place_files_in_structure tool uses these to create files in the repo
        - Empty strings are rejected to prevent creating empty files
        - All validation happens automatically on model instantiation
        - Invalid data raises pydantic.ValidationError with detailed error messages
    """
    
    terraform_code: str = Field(
        description="Terraform configuration code content",
        min_length=1,
        examples=[
            'resource "awscc_s3_bucket" "example" { bucket_name = "my-bucket" }',
            'resource "awscc_lambda_function" "example" { function_name = "my-function" }',
            'resource "awscc_dynamodb_table" "example" { table_name = "my-table" }'
        ]
    )
    
    template: str = Field(
        description="Markdown template content",
        min_length=1,
        examples=[
            "# S3 Bucket\n\nThis resource creates an S3 bucket.",
            "# Lambda Function\n\nCreates a Lambda function.",
            "# DynamoDB Table\n\nCreates a DynamoDB table."
        ]
    )
    
    service_name: str = Field(
        description="AWS service name (lowercase, numbers, underscores only)",
        pattern=r"^[a-z0-9_]+$",
        examples=[
            "s3_bucket",
            "lambda_function",
            "dynamodb_table",
            "ec2_instance",
            "iam_role"
        ]
    )


class PRContentInput(TANGOBaseModel):
    """
    Input model for PR content metadata.
    
    Used by the create_github_pr tool to specify metadata about the resource
    being submitted in a pull request. This includes service information,
    provider version, fetch date, and optional analysis content.
    
    Attributes:
        service_name: The AWS service name. Used in the PR title and description
                     to identify what resource is being added.
        provider_version: The Terraform AWSCC provider version in semantic versioning
                         format (X.Y.Z). Must match the pattern for valid semver.
        fetch_date: The date when the resource was fetched/processed. Typically in
                   YYYY-MM-DD format for consistency.
        s3_analysis_link: Optional S3 key for the analysis report. When provided,
                         the PR description will include a link to the analysis.
        analysis_report: Optional analysis report content. When provided, can be
                        included in the PR description for additional context.
    
    Validation:
        - service_name is required (any non-empty string)
        - provider_version must match pattern: ^\\d+\\.\\d+\\.\\d+$
        - fetch_date is required (any non-empty string)
        - s3_analysis_link is optional
        - analysis_report is optional
    
    Usage Examples:
        # Create with required fields only
        >>> pr_content = PRContentInput(
        ...     service_name="s3_bucket",
        ...     provider_version="1.53.0",
        ...     fetch_date="2024-01-15"
        ... )
        >>> print(pr_content.provider_version)
        1.53.0
        
        # Create with all fields
        >>> pr_content = PRContentInput(
        ...     service_name="lambda_function",
        ...     provider_version="1.48.0",
        ...     fetch_date="2024-01-10",
        ...     s3_analysis_link="analysis/resource/awscc_lambda_function/report.md",
        ...     analysis_report="## Analysis\\n\\nResource validated successfully."
        ... )
        >>> print(pr_content.s3_analysis_link)
        analysis/resource/awscc_lambda_function/report.md
        
        # Parse from JSON
        >>> json_str = '''
        ... {
        ...     "service_name": "dynamodb_table",
        ...     "provider_version": "2.0.0",
        ...     "fetch_date": "2024-02-01"
        ... }
        ... '''
        >>> pr_content = PRContentInput.model_validate_json(json_str)
        >>> print(pr_content.service_name)
        dynamodb_table
        
        # Validation error on invalid provider_version
        >>> try:
        ...     invalid = PRContentInput(
        ...         service_name="test",
        ...         provider_version="1.53",  # Missing patch version
        ...         fetch_date="2024-01-15"
        ...     )
        ... except ValidationError as e:
        ...     print("Validation failed: invalid provider_version format")
        Validation failed: invalid provider_version format
        
        # Validation error on invalid semver format
        >>> try:
        ...     invalid = PRContentInput(
        ...         service_name="test",
        ...         provider_version="v1.53.0",  # 'v' prefix not allowed
        ...         fetch_date="2024-01-15"
        ...     )
        ... except ValidationError as e:
        ...     print("Validation failed: provider_version must be X.Y.Z")
        Validation failed: provider_version must be X.Y.Z
        
        # Serialize back to JSON
        >>> json_output = pr_content.model_dump_json()
    
    Notes:
        - provider_version must be exactly X.Y.Z format (e.g., "1.53.0", not "v1.53.0")
        - fetch_date format is not strictly validated, but YYYY-MM-DD is recommended
        - s3_analysis_link is the S3 key, not a full URL
        - analysis_report can contain markdown formatting
        - The create_github_pr tool uses this to generate PR title and description
        - All validation happens automatically on model instantiation
        - Invalid data raises pydantic.ValidationError with detailed error messages
    """
    
    service_name: str = Field(
        description="AWS service name",
        examples=[
            "s3_bucket",
            "lambda_function",
            "dynamodb_table",
            "ec2_instance",
            "iam_role"
        ]
    )
    
    provider_version: str = Field(
        description="Terraform AWSCC provider version (semantic versioning: X.Y.Z)",
        pattern=r"^\d+\.\d+\.\d+$",
        examples=[
            "1.53.0",
            "1.48.0",
            "2.0.0",
            "1.0.1"
        ]
    )
    
    fetch_date: str = Field(
        description="Date when resource was fetched/processed",
        examples=[
            "2024-01-15",
            "2024-02-01",
            "2023-12-20"
        ]
    )
    
    s3_analysis_link: Optional[str] = Field(
        default=None,
        description="S3 key for analysis report (optional)",
        examples=[
            None,
            "analysis/resource/awscc_s3_bucket/report.md",
            "analysis/resource/awscc_lambda_function/report.md"
        ]
    )
    
    analysis_report: Optional[str] = Field(
        default=None,
        description="Analysis report content (optional)",
        examples=[
            None,
            "## Analysis\n\nResource validated successfully.",
            "## Validation Results\n\n- Terraform apply: SUCCESS\n- Terraform destroy: SUCCESS"
        ]
    )


class PRStatusInput(TANGOBaseModel):
    """
    Input model for updating PR status in DynamoDB.
    
    Used by the update_pr_status tool to specify which resource's PR status
    should be updated and what the new status should be. Validates that the
    resource name follows AWSCC naming conventions and that the status is
    one of the allowed values.
    
    Attributes:
        resource_name: The AWS CloudControl resource name. Must start with "awscc_"
                      and contain only lowercase letters, numbers, and underscores.
        pr_url: Optional GitHub pull request URL. When provided, stores the URL
               of the created PR for reference.
        status: The PR status to set. Must be either "created" (PR was successfully
               created) or "failed" (PR creation failed). Validated by both pattern
               matching and a field validator.
    
    Validation:
        - resource_name must match pattern: ^awscc_[a-z0-9_]+$
        - pr_url is optional
        - status must match pattern: ^(created|failed)$
        - status field_validator ensures only "created" or "failed" values
    
    Usage Examples:
        # Create with successful PR status
        >>> pr_status = PRStatusInput(
        ...     resource_name="awscc_s3_bucket",
        ...     pr_url="https://github.com/hashicorp/terraform-provider-awscc/pull/1234",
        ...     status="created"
        ... )
        >>> print(pr_status.status)
        created
        
        # Create with failed PR status (no URL)
        >>> pr_status = PRStatusInput(
        ...     resource_name="awscc_lambda_function",
        ...     status="failed"
        ... )
        >>> print(pr_status.pr_url)
        None
        
        # Parse from JSON
        >>> json_str = '''
        ... {
        ...     "resource_name": "awscc_dynamodb_table",
        ...     "pr_url": "https://github.com/hashicorp/terraform-provider-awscc/pull/5678",
        ...     "status": "created"
        ... }
        ... '''
        >>> pr_status = PRStatusInput.model_validate_json(json_str)
        >>> print(pr_status.resource_name)
        awscc_dynamodb_table
        
        # Validation error on invalid resource_name
        >>> try:
        ...     invalid = PRStatusInput(
        ...         resource_name="s3_bucket",  # Missing "awscc_" prefix
        ...         status="created"
        ...     )
        ... except ValidationError as e:
        ...     print("Validation failed: resource_name must start with awscc_")
        Validation failed: resource_name must start with awscc_
        
        # Validation error on invalid status
        >>> try:
        ...     invalid = PRStatusInput(
        ...         resource_name="awscc_s3_bucket",
        ...         status="pending"  # Only "created" or "failed" allowed
        ...     )
        ... except ValidationError as e:
        ...     print("Validation failed: status must be created or failed")
        Validation failed: status must be created or failed
        
        # Validation error on uppercase in resource_name
        >>> try:
        ...     invalid = PRStatusInput(
        ...         resource_name="awscc_S3_Bucket",  # Uppercase not allowed
        ...         status="created"
        ...     )
        ... except ValidationError as e:
        ...     print("Validation failed: resource_name must be lowercase")
        Validation failed: resource_name must be lowercase
        
        # Serialize back to JSON
        >>> json_output = pr_status.model_dump_json()
    
    Notes:
        - resource_name must always start with "awscc_" prefix
        - resource_name must be lowercase with underscores (no hyphens or uppercase)
        - status is restricted to exactly two values: "created" or "failed"
        - pr_url is typically provided when status is "created"
        - pr_url is typically None when status is "failed"
        - The field_validator provides an additional layer of validation beyond pattern matching
        - The update_pr_status tool uses this to update DynamoDB records
        - All validation happens automatically on model instantiation
        - Invalid data raises pydantic.ValidationError with detailed error messages
    """
    
    resource_name: str = Field(
        description="AWS CloudControl resource name (must start with awscc_)",
        pattern=r"^awscc_[a-z0-9_]+$",
        examples=[
            "awscc_s3_bucket",
            "awscc_lambda_function",
            "awscc_dynamodb_table",
            "awscc_ec2_instance",
            "awscc_iam_role"
        ]
    )
    
    pr_url: Optional[str] = Field(
        default=None,
        description="GitHub pull request URL (optional)",
        examples=[
            None,
            "https://github.com/hashicorp/terraform-provider-awscc/pull/1234",
            "https://github.com/hashicorp/terraform-provider-awscc/pull/5678"
        ]
    )
    
    status: str = Field(
        description="PR status (created or failed)",
        pattern=r"^(created|failed)$",
        examples=[
            "created",
            "failed"
        ]
    )
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """
        Validate that status is only 'created' or 'failed'.
        
        This field validator provides an additional layer of validation beyond
        the pattern matching to ensure only the two allowed status values are used.
        
        Args:
            v: The status value to validate
        
        Returns:
            str: The validated status value
        
        Raises:
            ValueError: If status is not 'created' or 'failed'
        
        Examples:
            >>> # Valid status values pass through
            >>> PRStatusInput(resource_name="awscc_s3_bucket", status="created")
            PRStatusInput(resource_name='awscc_s3_bucket', pr_url=None, status='created')
            
            >>> # Invalid status values raise ValueError
            >>> try:
            ...     PRStatusInput(resource_name="awscc_s3_bucket", status="pending")
            ... except ValidationError:
            ...     print("Status must be 'created' or 'failed'")
            Status must be 'created' or 'failed'
        """
        if v not in ['created', 'failed']:
            raise ValueError("Status must be 'created' or 'failed'")
        return v


# =============================================================================
# Output Models - Tool Results
# =============================================================================
