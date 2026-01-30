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

class ResourceContentResult(TANGOBaseModel):
    """
    Result from fetching resource content from S3.
    
    This model represents the output of the fetch_resource_content tool,
    which retrieves Terraform code, templates, and analysis reports from S3
    for a specific AWS CloudControl resource.
    
    Attributes:
        status: Operation status ("success" or "error")
        resource_name: AWS CloudControl resource name (e.g., "awscc_s3_bucket")
        service_name: Service name without "awscc_" prefix (e.g., "s3_bucket")
        terraform_code: Optional Terraform configuration code content
        template: Optional template file content
        analysis_report: Optional analysis report content
        s3_terraform_link: Optional S3 key for Terraform file
        s3_template_link: Optional S3 key for template file
        s3_analysis_link: Optional S3 key for analysis file
        provider_version: AWSCC provider version (e.g., "1.53.0")
        fetch_date: Date content was fetched (YYYY-MM-DD format)
        error: Optional error message if fetch failed
    
    Computed Properties:
        is_success: Returns True if fetch succeeded (status="success" and no error)
    
    Usage Examples:
        # Create successful result
        >>> result = ResourceContentResult(
        ...     status="success",
        ...     resource_name="awscc_s3_bucket",
        ...     service_name="s3_bucket",
        ...     terraform_code='resource "awscc_s3_bucket" "example" {...}',
        ...     template="# S3 Bucket Template...",
        ...     provider_version="1.53.0",
        ...     fetch_date="2024-01-15"
        ... )
        >>> print(result.is_success)
        True
        
        # Create error result
        >>> error_result = ResourceContentResult(
        ...     status="error",
        ...     resource_name="awscc_s3_bucket",
        ...     service_name="s3_bucket",
        ...     provider_version="1.53.0",
        ...     fetch_date="2024-01-15",
        ...     error="S3 file not found"
        ... )
        >>> print(error_result.is_success)
        False
    """
    
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status",
        examples=["success", "error"]
    )
    
    resource_name: str = Field(
        description="AWS CloudControl resource name",
        examples=["awscc_s3_bucket", "awscc_lambda_function"]
    )
    
    service_name: str = Field(
        description="Service name without awscc_ prefix",
        examples=["s3_bucket", "lambda_function"]
    )
    
    terraform_code: Optional[str] = Field(
        default=None,
        description="Terraform code content"
    )
    
    template: Optional[str] = Field(
        default=None,
        description="Template content"
    )
    
    analysis_report: Optional[str] = Field(
        default=None,
        description="Analysis report content"
    )
    
    s3_terraform_link: Optional[str] = Field(
        default=None,
        description="S3 key for Terraform file",
        examples=["examples/resources/awscc_s3_bucket/s3_bucket.tf"]
    )
    
    s3_template_link: Optional[str] = Field(
        default=None,
        description="S3 key for template file",
        examples=["templates/resources/s3_bucket.md.tmpl"]
    )
    
    s3_analysis_link: Optional[str] = Field(
        default=None,
        description="S3 key for analysis file",
        examples=["analysis/resource/awscc_s3_bucket/report.md"]
    )
    
    provider_version: str = Field(
        description="AWSCC provider version",
        examples=["1.53.0", "1.48.0"]
    )
    
    fetch_date: str = Field(
        description="Date content was fetched (YYYY-MM-DD)",
        examples=["2024-01-15", "2024-02-20"]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if fetch failed",
        examples=[None, "S3 file not found", "Invalid S3 key"]
    )
    
    @property
    def is_success(self) -> bool:
        """
        Check if fetch succeeded.
        
        Returns True if the operation status is "success" and no error
        message is present, indicating that all content was successfully
        fetched from S3.
        
        Returns:
            bool: True if fetch succeeded, False otherwise
        """
        return self.status == "success" and self.error is None



class EligibleResourceResult(TANGOBaseModel):
    """
    Result from getting next eligible resource for PR creation.
    
    This model represents the output of the get_next_eligible_resource tool,
    which identifies AWS CloudControl resources that are ready for pull request
    creation. The model supports special values "NONE" and "ERROR" to indicate
    when no eligible resources are found or when an error occurs.
    
    Attributes:
        resource_name: Resource name, or special values "NONE" (no resources found)
                      or "ERROR" (error occurred during discovery)
        timestamp: Optional resource timestamp (integer)
        s3_terraform_link: Optional S3 key for Terraform file
        s3_template_link: Optional S3 key for template file
        s3_analysis_link: Optional S3 key for analysis file
        error: Optional error message if discovery failed
    
    Computed Properties:
        is_valid: Returns True if a valid resource was found (not "NONE" or "ERROR")
        has_all_files: Returns True if all three S3 file links are present
    
    Usage Examples:
        # Create successful result with all files
        >>> result = EligibleResourceResult(
        ...     resource_name="awscc_s3_bucket",
        ...     timestamp=1705334400,
        ...     s3_terraform_link="examples/resources/awscc_s3_bucket/s3_bucket.tf",
        ...     s3_template_link="templates/resources/s3_bucket.md.tmpl",
        ...     s3_analysis_link="analysis/resource/awscc_s3_bucket/report.md"
        ... )
        >>> print(result.is_valid)
        True
        >>> print(result.has_all_files)
        True
        
        # Create result with no resources found
        >>> no_result = EligibleResourceResult(
        ...     resource_name="NONE"
        ... )
        >>> print(no_result.is_valid)
        False
        
        # Create error result
        >>> error_result = EligibleResourceResult(
        ...     resource_name="ERROR",
        ...     error="DynamoDB query failed"
        ... )
        >>> print(error_result.is_valid)
        False
    """
    
    resource_name: str = Field(
        description="Resource name or special values NONE/ERROR",
        examples=["awscc_s3_bucket", "awscc_lambda_function", "NONE", "ERROR"]
    )
    
    timestamp: Optional[int] = Field(
        default=None,
        description="Resource timestamp",
        examples=[None, 1705334400, 1706544000]
    )
    
    s3_terraform_link: Optional[str] = Field(
        default=None,
        description="S3 key for Terraform file",
        examples=[None, "examples/resources/awscc_s3_bucket/s3_bucket.tf"]
    )
    
    s3_template_link: Optional[str] = Field(
        default=None,
        description="S3 key for template file",
        examples=[None, "templates/resources/s3_bucket.md.tmpl"]
    )
    
    s3_analysis_link: Optional[str] = Field(
        default=None,
        description="S3 key for analysis file",
        examples=[None, "analysis/resource/awscc_s3_bucket/report.md"]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if discovery failed",
        examples=[None, "DynamoDB query failed", "No eligible resources found"]
    )
    
    @property
    def is_valid(self) -> bool:
        """
        Check if a valid resource was found.
        
        Returns True if the resource_name is not one of the special error values
        ("NONE" or "ERROR"), indicating that a valid, processable resource was found.
        
        Returns:
            bool: True if a valid resource was discovered, False otherwise
        """
        return self.resource_name not in ("NONE", "ERROR")
    
    @property
    def has_all_files(self) -> bool:
        """
        Check if all required S3 files are present.
        
        Returns True if all three S3 file links (terraform, template, and analysis)
        are present and not None.
        
        Returns:
            bool: True if all files are present, False otherwise
        """
        return all([
            self.s3_terraform_link,
            self.s3_template_link,
            self.s3_analysis_link
        ])



class RepoSetupResult(TANGOBaseModel):
    """
    Result from cloning and setting up git repository.
    
    This model represents the output of the clone_and_setup_repo tool,
    which clones a git repository, creates a new branch, and sets up the
    working directory for PR creation.
    
    Attributes:
        status: Operation status ("success" or "error")
        repo_path: Optional path to the cloned repository
        branch_name: Optional name of the created branch
        work_dir_name: Optional name of the working directory
        error: Optional error message if setup failed
    
    Computed Properties:
        is_success: Returns True if setup succeeded (status="success" and no error)
    
    Usage Examples:
        # Create successful result
        >>> result = RepoSetupResult(
        ...     status="success",
        ...     repo_path="/tmp/pr_workspace/terraform-provider-awscc",
        ...     branch_name="d-awscc_s3_bucket",
        ...     work_dir_name="pr_workspace"
        ... )
        >>> print(result.is_success)
        True
        
        # Create error result
        >>> error_result = RepoSetupResult(
        ...     status="error",
        ...     error="Failed to clone repository"
        ... )
        >>> print(error_result.is_success)
        False
    """
    
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status",
        examples=["success", "error"]
    )
    
    repo_path: Optional[str] = Field(
        default=None,
        description="Path to the cloned repository",
        examples=[None, "/tmp/pr_workspace/terraform-provider-awscc"]
    )
    
    branch_name: Optional[str] = Field(
        default=None,
        description="Name of the created branch",
        examples=[None, "d-awscc_s3_bucket", "d-awscc_lambda_function"]
    )
    
    work_dir_name: Optional[str] = Field(
        default=None,
        description="Name of the working directory",
        examples=[None, "pr_workspace"]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if setup failed",
        examples=[None, "Failed to clone repository", "Branch already exists"]
    )
    
    @property
    def is_success(self) -> bool:
        """
        Check if setup succeeded.
        
        Returns True if the operation status is "success" and no error
        message is present.
        
        Returns:
            bool: True if setup succeeded, False otherwise
        """
        return self.status == "success" and self.error is None



class FilePlacementResult(TANGOBaseModel):
    """
    Result from placing files in repository structure.
    
    This model represents the output of the place_files_in_structure tool,
    which creates Terraform and template files in the appropriate repository
    directories and validates the file structure.
    
    Attributes:
        status: Operation status ("success" or "error")
        files_created: List of file paths that were created
        resource_name: Optional resource name
        service_name: Optional service name
        validation: Optional validation status ("passed" or "failed")
        error: Optional error message if placement failed
    
    Computed Properties:
        is_success: Returns True if placement succeeded (status="success" and
                   validation="passed")
    
    Usage Examples:
        # Create successful result
        >>> result = FilePlacementResult(
        ...     status="success",
        ...     files_created=["examples/resources/awscc_s3_bucket/s3_bucket.tf",
        ...                    "templates/resources/s3_bucket.md.tmpl"],
        ...     resource_name="awscc_s3_bucket",
        ...     service_name="s3_bucket",
        ...     validation="passed"
        ... )
        >>> print(result.is_success)
        True
        
        # Create error result
        >>> error_result = FilePlacementResult(
        ...     status="error",
        ...     files_created=[],
        ...     error="Failed to write file"
        ... )
        >>> print(error_result.is_success)
        False
    """
    
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status",
        examples=["success", "error"]
    )
    
    files_created: List[str] = Field(
        default_factory=list,
        description="List of file paths that were created",
        examples=[
            [],
            ["examples/resources/awscc_s3_bucket/s3_bucket.tf"],
            ["examples/resources/awscc_s3_bucket/s3_bucket.tf",
             "templates/resources/s3_bucket.md.tmpl"]
        ]
    )
    
    resource_name: Optional[str] = Field(
        default=None,
        description="Resource name",
        examples=[None, "awscc_s3_bucket", "awscc_lambda_function"]
    )
    
    service_name: Optional[str] = Field(
        default=None,
        description="Service name",
        examples=[None, "s3_bucket", "lambda_function"]
    )
    
    validation: Optional[str] = Field(
        default=None,
        description="Validation status",
        examples=[None, "passed", "failed"]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if placement failed",
        examples=[None, "Failed to write file", "Invalid file path"]
    )
    
    @property
    def is_success(self) -> bool:
        """
        Check if placement succeeded.
        
        Returns True if the operation status is "success" and validation
        status is "passed".
        
        Returns:
            bool: True if placement succeeded, False otherwise
        """
        return self.status == "success" and self.validation == "passed"



class ValidationCommandResult(TANGOBaseModel):
    """
    Result from a single validation command execution.
    
    This model represents the outcome of running a single validation command
    (e.g., terraform fmt, terraform validate, go fmt). It is used as a nested
    model within HashiCorpValidationResult to track individual command results.
    
    Attributes:
        command: The command that was executed
        returncode: Optional command return code (0 for success)
        success: Whether the command succeeded
        stdout: Optional command standard output
        stderr: Optional command standard error
        error: Optional error message if command failed
    
    Usage Examples:
        # Create successful command result
        >>> result = ValidationCommandResult(
        ...     command="terraform fmt -check",
        ...     returncode=0,
        ...     success=True,
        ...     stdout="No formatting changes needed"
        ... )
        >>> print(result.success)
        True
        
        # Create failed command result
        >>> error_result = ValidationCommandResult(
        ...     command="terraform validate",
        ...     returncode=1,
        ...     success=False,
        ...     stderr="Error: Invalid configuration",
        ...     error="Validation failed"
        ... )
        >>> print(error_result.success)
        False
    """
    
    command: str = Field(
        description="Command that was executed",
        examples=["terraform fmt -check", "terraform validate", "go fmt"]
    )
    
    returncode: Optional[int] = Field(
        default=None,
        description="Command return code",
        examples=[None, 0, 1]
    )
    
    success: bool = Field(
        description="Whether command succeeded",
        examples=[True, False]
    )
    
    stdout: Optional[str] = Field(
        default=None,
        description="Command standard output",
        examples=[None, "No formatting changes needed", "Validation successful"]
    )
    
    stderr: Optional[str] = Field(
        default=None,
        description="Command standard error",
        examples=[None, "Error: Invalid configuration", "Warning: Deprecated syntax"]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if command failed",
        examples=[None, "Validation failed", "Command not found"]
    )



class HashiCorpValidationResult(TANGOBaseModel):
    """
    Result from running HashiCorp validation commands.
    
    This model represents the output of the run_hashicorp_validation tool,
    which executes multiple validation commands (terraform fmt, validate, etc.)
    and generates documentation. It tracks the overall status, individual command
    results, and documentation generation status.
    
    Attributes:
        status: Overall validation status ("success" or "error")
        resource_name: Resource name being validated
        commands: List of ValidationCommandResult objects for each command executed
        docs_generated: Optional boolean indicating if docs were generated
        docs_file_path: Optional path to the generated documentation file
        docs_file_size: Optional size of the generated documentation file in bytes
        error: Optional error message if validation failed
        error_details: Optional dictionary with detailed error information
    
    Computed Properties:
        is_success: Returns True if validation succeeded (status="success" and
                   docs_generated=True)
        all_commands_succeeded: Returns True if all commands in the commands list
                               have success=True
    
    Usage Examples:
        # Create successful result
        >>> result = HashiCorpValidationResult(
        ...     status="success",
        ...     resource_name="awscc_s3_bucket",
        ...     commands=[
        ...         ValidationCommandResult(command="terraform fmt -check",
        ...                                returncode=0, success=True),
        ...         ValidationCommandResult(command="terraform validate",
        ...                                returncode=0, success=True)
        ...     ],
        ...     docs_generated=True,
        ...     docs_file_path="docs/resources/s3_bucket.md",
        ...     docs_file_size=1024
        ... )
        >>> print(result.is_success)
        True
        >>> print(result.all_commands_succeeded)
        True
    """
    
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Overall validation status",
        examples=["success", "error"]
    )
    
    resource_name: str = Field(
        description="Resource name being validated",
        examples=["awscc_s3_bucket", "awscc_lambda_function"]
    )
    
    commands: List[ValidationCommandResult] = Field(
        default_factory=list,
        description="List of validation command results",
        examples=[
            [],
            [{"command": "terraform fmt -check", "returncode": 0, "success": True}]
        ]
    )
    
    docs_generated: Optional[bool] = Field(
        default=None,
        description="Whether documentation was generated",
        examples=[None, True, False]
    )
    
    docs_file_path: Optional[str] = Field(
        default=None,
        description="Path to generated documentation file",
        examples=[None, "docs/resources/s3_bucket.md"]
    )
    
    docs_file_size: Optional[int] = Field(
        default=None,
        description="Size of generated documentation file in bytes",
        examples=[None, 1024, 2048]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if validation failed",
        examples=[None, "Validation failed", "Documentation generation failed"]
    )
    
    error_details: Optional[Dict] = Field(
        default=None,
        description="Detailed error information",
        examples=[None, {"command": "terraform validate", "error": "Invalid config"}]
    )
    
    @property
    def is_success(self) -> bool:
        """
        Check if validation succeeded.
        
        Returns True if the overall status is "success" and documentation
        was successfully generated.
        
        Returns:
            bool: True if validation succeeded, False otherwise
        """
        return self.status == "success" and self.docs_generated == True
    
    @property
    def all_commands_succeeded(self) -> bool:
        """
        Check if all validation commands succeeded.
        
        Returns True if all commands in the commands list have success=True.
        Returns True if commands list is empty.
        
        Returns:
            bool: True if all commands succeeded, False otherwise
        """
        return all(cmd.success for cmd in self.commands)



class GitHubPRResult(TANGOBaseModel):
    """
    Result from creating a GitHub pull request.
    
    This model represents the output of the create_github_pr tool,
    which creates a pull request in the HashiCorp terraform-provider-awscc
    repository with the validated resource code.
    
    Attributes:
        status: Operation status ("success" or "error")
        pr_url: Optional GitHub pull request URL
        pr_number: Optional GitHub pull request number
        pr_title: Optional pull request title
        resource_name: Optional resource name
        branch_name: Optional branch name used for the PR
        error: Optional error message if PR creation failed
    
    Computed Properties:
        is_success: Returns True if PR creation succeeded (status="success" and
                   pr_url is not None)
    
    Usage Examples:
        # Create successful result
        >>> result = GitHubPRResult(
        ...     status="success",
        ...     pr_url="https://github.com/hashicorp/terraform-provider-awscc/pull/1234",
        ...     pr_number=1234,
        ...     pr_title="Add awscc_s3_bucket resource",
        ...     resource_name="awscc_s3_bucket",
        ...     branch_name="d-awscc_s3_bucket"
        ... )
        >>> print(result.is_success)
        True
        
        # Create error result
        >>> error_result = GitHubPRResult(
        ...     status="error",
        ...     resource_name="awscc_s3_bucket",
        ...     error="Failed to create PR: Authentication failed"
        ... )
        >>> print(error_result.is_success)
        False
    """
    
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status",
        examples=["success", "error"]
    )
    
    pr_url: Optional[str] = Field(
        default=None,
        description="GitHub pull request URL",
        examples=[None, "https://github.com/hashicorp/terraform-provider-awscc/pull/1234"]
    )
    
    pr_number: Optional[int] = Field(
        default=None,
        description="GitHub pull request number",
        examples=[None, 1234, 5678]
    )
    
    pr_title: Optional[str] = Field(
        default=None,
        description="Pull request title",
        examples=[None, "Add awscc_s3_bucket resource", "Add awscc_lambda_function resource"]
    )
    
    resource_name: Optional[str] = Field(
        default=None,
        description="Resource name",
        examples=[None, "awscc_s3_bucket", "awscc_lambda_function"]
    )
    
    branch_name: Optional[str] = Field(
        default=None,
        description="Branch name used for the PR",
        examples=[None, "d-awscc_s3_bucket", "d-awscc_lambda_function"]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if PR creation failed",
        examples=[None, "Authentication failed", "PR already exists"]
    )
    
    @property
    def is_success(self) -> bool:
        """
        Check if PR creation succeeded.
        
        Returns True if the operation status is "success" and a PR URL
        was returned, indicating the PR was successfully created.
        
        Returns:
            bool: True if PR creation succeeded, False otherwise
        """
        return self.status == "success" and self.pr_url is not None



class PRStatusUpdateResult(TANGOBaseModel):
    """
    Result from updating PR status in DynamoDB.
    
    This model represents the output of the update_pr_status tool,
    which updates the PR creation status for a resource in the DynamoDB
    tracking table.
    
    Attributes:
        status: Operation status ("success" or "error")
        resource_name: Resource name that was updated
        timestamp: Optional DynamoDB timestamp (integer)
        pr_status: Optional updated PR status value
        pr_created_at: Optional PR creation timestamp
        github_pr_url: Optional GitHub PR URL
        message: Optional success message
        error: Optional error message if update failed
    
    Computed Properties:
        is_success: Returns True if update succeeded (status="success" and no error)
    
    Usage Examples:
        # Create successful result
        >>> result = PRStatusUpdateResult(
        ...     status="success",
        ...     resource_name="awscc_s3_bucket",
        ...     timestamp=1705334400,
        ...     pr_status="created",
        ...     pr_created_at="2024-01-15T10:00:00Z",
        ...     github_pr_url="https://github.com/hashicorp/terraform-provider-awscc/pull/1234",
        ...     message="PR status updated successfully"
        ... )
        >>> print(result.is_success)
        True
        
        # Create error result
        >>> error_result = PRStatusUpdateResult(
        ...     status="error",
        ...     resource_name="awscc_s3_bucket",
        ...     error="DynamoDB update failed"
        ... )
        >>> print(error_result.is_success)
        False
    """
    
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status",
        examples=["success", "error"]
    )
    
    resource_name: str = Field(
        description="Resource name that was updated",
        examples=["awscc_s3_bucket", "awscc_lambda_function"]
    )
    
    timestamp: Optional[int] = Field(
        default=None,
        description="DynamoDB timestamp",
        examples=[None, 1705334400, 1706544000]
    )
    
    pr_status: Optional[str] = Field(
        default=None,
        description="Updated PR status value",
        examples=[None, "created", "failed"]
    )
    
    pr_created_at: Optional[str] = Field(
        default=None,
        description="PR creation timestamp",
        examples=[None, "2024-01-15T10:00:00Z", "2024-02-01T14:30:00Z"]
    )
    
    github_pr_url: Optional[str] = Field(
        default=None,
        description="GitHub PR URL",
        examples=[None, "https://github.com/hashicorp/terraform-provider-awscc/pull/1234"]
    )
    
    message: Optional[str] = Field(
        default=None,
        description="Success message",
        examples=[None, "PR status updated successfully", "Status set to created"]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if update failed",
        examples=[None, "DynamoDB update failed", "Resource not found"]
    )
    
    @property
    def is_success(self) -> bool:
        """
        Check if update succeeded.
        
        Returns True if the operation status is "success" and no error
        message is present.
        
        Returns:
            bool: True if update succeeded, False otherwise
        """
        return self.status == "success" and self.error is None



class GitCommitPushResult(TANGOBaseModel):
    """
    Result from git commit and push operation.
    
    This model represents the output of the git_commit_and_push tool,
    which commits changes to a git branch and pushes them to the remote
    repository.
    
    Attributes:
        status: Operation status ("success" or "error")
        commit_hash: Optional full commit hash (SHA-1)
        commit_hash_short: Optional short commit hash (first 7 characters)
        branch_name: Optional branch name that was pushed
        resource_name: Optional resource name
        files_changed: Optional number of files changed in the commit
        commit_message: Optional commit message
        error: Optional error message if commit/push failed
    
    Computed Properties:
        is_success: Returns True if commit/push succeeded (status="success" and
                   commit_hash is not None)
    
    Usage Examples:
        # Create successful result
        >>> result = GitCommitPushResult(
        ...     status="success",
        ...     commit_hash="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
        ...     commit_hash_short="a1b2c3d",
        ...     branch_name="d-awscc_s3_bucket",
        ...     resource_name="awscc_s3_bucket",
        ...     files_changed=2,
        ...     commit_message="Add awscc_s3_bucket resource"
        ... )
        >>> print(result.is_success)
        True
        
        # Create error result
        >>> error_result = GitCommitPushResult(
        ...     status="error",
        ...     resource_name="awscc_s3_bucket",
        ...     error="Failed to push: Authentication failed"
        ... )
        >>> print(error_result.is_success)
        False
    """
    
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status",
        examples=["success", "error"]
    )
    
    commit_hash: Optional[str] = Field(
        default=None,
        description="Full commit hash (SHA-1)",
        examples=[None, "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"]
    )
    
    commit_hash_short: Optional[str] = Field(
        default=None,
        description="Short commit hash (first 7 characters)",
        examples=[None, "a1b2c3d", "f9e8d7c"]
    )
    
    branch_name: Optional[str] = Field(
        default=None,
        description="Branch name that was pushed",
        examples=[None, "d-awscc_s3_bucket", "d-awscc_lambda_function"]
    )
    
    resource_name: Optional[str] = Field(
        default=None,
        description="Resource name",
        examples=[None, "awscc_s3_bucket", "awscc_lambda_function"]
    )
    
    files_changed: Optional[int] = Field(
        default=None,
        description="Number of files changed in the commit",
        examples=[None, 1, 2, 5]
    )
    
    commit_message: Optional[str] = Field(
        default=None,
        description="Commit message",
        examples=[None, "Add awscc_s3_bucket resource", "Update documentation"]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if commit/push failed",
        examples=[None, "Authentication failed", "Nothing to commit"]
    )
    
    @property
    def is_success(self) -> bool:
        """
        Check if commit and push succeeded.
        
        Returns True if the operation status is "success" and a commit hash
        was returned, indicating the commit was successfully created and pushed.
        
        Returns:
            bool: True if commit/push succeeded, False otherwise
        """
        return self.status == "success" and self.commit_hash is not None
