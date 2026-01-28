"""
TANGO Pipeline - Structured Output Models

This module provides Pydantic models for type-safe agent communication across
the TANGO multi-agent pipeline. All agents use these models to ensure validated,
structured data exchange with automatic validation and clear error messages.

Models:
    TANGOBaseModel: Base class with common Pydantic configuration
    DiscoveryResult: Output from discovery_agent
    DocumentationResult: Output from documentation_agent
    TerraformLifecycleStep: Individual Terraform lifecycle step result
    TerraformResult: Output from terraform_agent
    ValidationResult: Output from validation_agent
    StorageRequest: Input to storage_agent
    StorageResult: Output from storage_agent

Usage:
    from agents.models import DiscoveryResult
    
    # Parse JSON string to validated model
    result = DiscoveryResult.model_validate_json(json_string)
    
    # Access fields with type safety
    resource_name = result.resource_name
    
    # Use computed properties
    if result.is_valid:
        print(f"Found valid resource: {resource_name}")
    
    # Serialize back to JSON
    json_output = result.model_dump_json()

Author: TANGO Team
Version: 1.0.0
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class TANGOBaseModel(BaseModel):
    """
    Base model with common Pydantic configuration for all TANGO models.
    
    This base class provides consistent configuration across all agent models:
    - Allows extra fields for forward compatibility
    - Uses enum values instead of enum objects for JSON serialization
    - Validates fields on assignment to catch errors early
    - Provides JSON schema generation for documentation
    
    All TANGO agent models should inherit from this base class to ensure
    consistent behavior and configuration.
    
    Example:
        class MyAgentResult(TANGOBaseModel):
            status: str = Field(description="Operation status")
            data: Optional[str] = None
    """
    
    class Config:
        """Pydantic model configuration"""
        # Allow extra fields for forward compatibility
        # This prevents errors when new fields are added to models
        extra = "allow"
        
        # Use enum values instead of enum objects in JSON
        # Makes serialization more straightforward
        use_enum_values = True
        
        # Validate on assignment to catch errors early
        # Ensures data integrity throughout model lifecycle
        validate_assignment = True
        
        # Generate JSON schema for documentation
        # Enables automatic API documentation generation
        json_schema_extra = {
            "examples": []
        }


# =============================================================================
# Discovery Agent Models
# =============================================================================

class DiscoveryResult(TANGOBaseModel):
    """
    Result from discovering the next unprocessed AWS CloudControl resource.
    
    The discovery agent searches GitHub releases for new AWSCC provider resources
    and identifies which ones haven't been processed yet. This model captures
    the discovered resource information with validation to ensure data quality.
    
    Attributes:
        resource_name: AWS CloudControl resource name (e.g., "awscc_s3_bucket").
                      Must start with "awscc_" and contain only lowercase letters,
                      numbers, and underscores.
        provider_version: Terraform AWSCC provider semantic version (e.g., "1.53.0").
                         Must follow X.Y.Z format.
        error: Optional error message if discovery failed. When populated, indicates
               that the discovery process encountered an issue.
    
    Computed Properties:
        is_valid: Returns True if a valid resource was discovered (not "NONE" or "ERROR").
    
    Validation:
        - resource_name must match pattern: ^(awscc_[a-z0-9_]+|NONE|ERROR)$
        - provider_version must match pattern: ^\\d+\\.\\d+\\.\\d+$
        - error field is optional
    
    Usage Examples:
        # Parse from JSON string
        >>> json_str = '{"resource_name": "awscc_s3_bucket", "provider_version": "1.53.0"}'
        >>> result = DiscoveryResult.model_validate_json(json_str)
        >>> print(result.resource_name)
        awscc_s3_bucket
        
        # Check if discovery was successful
        >>> if result.is_valid:
        ...     print(f"Processing {result.resource_name}")
        Processing awscc_s3_bucket
        
        # Handle discovery failure
        >>> error_result = DiscoveryResult(
        ...     resource_name="ERROR",
        ...     provider_version="0.0.0",
        ...     error="No unprocessed resources found"
        ... )
        >>> print(error_result.is_valid)
        False
        
        # Serialize back to JSON
        >>> json_output = result.model_dump_json()
        >>> print(json_output)
        {"resource_name":"awscc_s3_bucket","provider_version":"1.53.0","error":null}
    
    Notes:
        - Special resource names "NONE" and "ERROR" indicate no valid resource found
        - The is_valid property provides a convenient way to check discovery success
        - All validation happens automatically on model instantiation
        - Invalid data raises pydantic.ValidationError with detailed error messages
    """
    
    resource_name: str = Field(
        description="AWS CloudControl resource name (e.g., awscc_s3_bucket) or special values NONE/ERROR",
        pattern=r"^(awscc_[a-z0-9_]+|NONE|ERROR)$",
        examples=["awscc_s3_bucket", "awscc_lambda_function", "awscc_dynamodb_table", "NONE", "ERROR"]
    )
    
    provider_version: str = Field(
        description="Terraform AWSCC provider version (e.g., 1.53.0)",
        pattern=r"^\d+\.\d+\.\d+$",
        examples=["1.53.0", "1.48.0", "2.0.0"]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if discovery failed",
        examples=[None, "No unprocessed resources found", "GitHub API rate limit exceeded"]
    )
    
    @property
    def is_valid(self) -> bool:
        """
        Check if discovery found a valid resource.
        
        Returns True if the resource_name is not one of the special error values
        ("NONE" or "ERROR"), indicating that a valid, processable resource was found.
        
        Returns:
            bool: True if a valid resource was discovered, False otherwise.
        
        Examples:
            >>> result = DiscoveryResult(resource_name="awscc_s3_bucket", provider_version="1.53.0")
            >>> result.is_valid
            True
            
            >>> error_result = DiscoveryResult(resource_name="NONE", provider_version="0.0.0")
            >>> error_result.is_valid
            False
            
            >>> error_result = DiscoveryResult(resource_name="ERROR", provider_version="0.0.0")
            >>> error_result.is_valid
            False
        """
        return self.resource_name not in ("NONE", "ERROR")


# =============================================================================
# Documentation Agent Models
# =============================================================================

class DocumentationResult(TANGOBaseModel):
    """
    Result from generating Terraform documentation and configuration code.
    
    The documentation agent generates Terraform configuration files for AWS CloudControl
    resources by analyzing AWS documentation and creating working examples. This model
    captures the generated code, metadata about the generation process, and any
    supplemental resources that were created to support the main resource.
    
    Attributes:
        terraform_code: Path to the main.tf file containing the generated Terraform code.
                       Must not be empty. This is the primary output of the documentation
                       agent and contains the complete Terraform configuration.
        resource_name: Target AWS CloudControl resource name (e.g., "awscc_s3_bucket").
                      Must match the AWSCC naming pattern.
        provider_version: AWSCC provider version used for code generation (e.g., "1.53.0").
                         Must follow semantic versioning format.
        workspace_initialized: Whether the terraform_test workspace was initialized.
                              True indicates the workspace is ready for terraform operations.
        supplemental_resources: List of supplemental resource names that were created
                               to support the main resource (e.g., ["awscc_iam_role"]).
                               Can be empty if no supplemental resources were needed.
        supplemental_strategy: Explanation of why supplemental resources were chosen
                              and how they support the main resource. Optional field
                              that provides context for the supplemental resources.
        error: Optional error message if generation failed. When populated, indicates
              that the documentation generation process encountered an issue.
        log: Optional path to the log file containing Terraform execution output.
            Useful for debugging and understanding what happened during generation.
    
    Computed Properties:
        is_success: Returns True if documentation generation succeeded (no error and
                   terraform_code is not empty).
    
    Validation:
        - terraform_code must not be empty (min_length=1)
        - resource_name must match pattern: ^awscc_[a-z0-9_]+$
        - provider_version must match pattern: ^\\d+\\.\\d+\\.\\d+$
        - supplemental_resources defaults to empty list if not provided
        - supplemental_strategy is optional
        - error field is optional
        - log field is optional
    
    Usage Examples:
        # Parse from JSON string
        >>> json_str = '''
        ... {
        ...     "terraform_code": "terraform_test/main.tf",
        ...     "resource_name": "awscc_s3_bucket",
        ...     "provider_version": "1.53.0",
        ...     "workspace_initialized": true,
        ...     "supplemental_resources": ["awscc_iam_role"],
        ...     "supplemental_strategy": "IAM role needed for bucket notifications"
        ... }
        ... '''
        >>> result = DocumentationResult.model_validate_json(json_str)
        >>> print(result.resource_name)
        awscc_s3_bucket
        
        # Check if generation was successful
        >>> if result.is_success:
        ...     print(f"Generated code at: {result.terraform_code}")
        Generated code at: terraform_test/main.tf
        
        # Access supplemental resources
        >>> print(result.supplemental_resources)
        ['awscc_iam_role']
        >>> print(result.supplemental_strategy)
        IAM role needed for bucket notifications
        
        # Handle generation failure
        >>> error_result = DocumentationResult(
        ...     terraform_code="",
        ...     resource_name="awscc_s3_bucket",
        ...     provider_version="1.53.0",
        ...     workspace_initialized=False,
        ...     error="Failed to generate valid Terraform code"
        ... )
        >>> print(error_result.is_success)
        False
        
        # Create with minimal fields
        >>> minimal_result = DocumentationResult(
        ...     terraform_code="terraform_test/main.tf",
        ...     resource_name="awscc_lambda_function",
        ...     provider_version="1.53.0",
        ...     workspace_initialized=True
        ... )
        >>> print(minimal_result.supplemental_resources)
        []
        
        # Serialize back to JSON
        >>> json_output = result.model_dump_json()
    
    Notes:
        - The terraform_code field contains the path to the generated file, not the code itself
        - workspace_initialized=True means terraform init has been run successfully
        - Supplemental resources are additional AWS resources needed to make the main resource work
        - The is_success property checks both error field and terraform_code non-emptiness
        - All validation happens automatically on model instantiation
        - Invalid data raises pydantic.ValidationError with detailed error messages
        - The workspace is typically created in terraform_test/ directory
    """
    
    terraform_code: str = Field(
        description="Path to the main.tf file containing the generated Terraform code",
        min_length=1,
        examples=["terraform_test/main.tf", "terraform_test/main.tf"]
    )
    
    resource_name: str = Field(
        description="Target AWS CloudControl resource name",
        pattern=r"^awscc_[a-z0-9_]+$",
        examples=["awscc_s3_bucket", "awscc_lambda_function", "awscc_dynamodb_table"]
    )
    
    provider_version: str = Field(
        description="AWSCC provider version used for code generation",
        pattern=r"^\d+\.\d+\.\d+$",
        examples=["1.53.0", "1.48.0", "2.0.0"]
    )
    
    workspace_initialized: bool = Field(
        description="Whether the terraform_test workspace was initialized with terraform init"
    )
    
    supplemental_resources: List[str] = Field(
        default_factory=list,
        description="List of supplemental resource names created to support the main resource",
        examples=[
            [],
            ["awscc_iam_role"],
            ["awscc_iam_role", "awscc_kms_key"],
            ["awscc_vpc", "awscc_subnet", "awscc_security_group"]
        ]
    )
    
    supplemental_strategy: Optional[str] = Field(
        default=None,
        description="Explanation of why supplemental resources were chosen and how they support the main resource",
        examples=[
            None,
            "IAM role needed for Lambda execution permissions",
            "VPC and subnet required for RDS instance deployment",
            "KMS key needed for S3 bucket encryption"
        ]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if generation failed",
        examples=[
            None,
            "Failed to generate valid Terraform code",
            "AWS documentation not found for resource",
            "Terraform init failed in workspace"
        ]
    )
    
    log: Optional[str] = Field(
        default=None,
        description="Path to the log file containing Terraform execution output",
        examples=[None, "terraform_test/terraform.log", "logs/documentation_agent.log"]
    )
    
    @property
    def is_success(self) -> bool:
        """
        Check if documentation generation succeeded.
        
        Returns True if both conditions are met:
        1. No error message is present (error is None)
        2. Terraform code was generated (terraform_code is not empty)
        
        This property provides a convenient way to check if the documentation
        agent completed successfully and produced usable output.
        
        Returns:
            bool: True if generation succeeded, False otherwise.
        
        Examples:
            >>> result = DocumentationResult(
            ...     terraform_code="terraform_test/main.tf",
            ...     resource_name="awscc_s3_bucket",
            ...     provider_version="1.53.0",
            ...     workspace_initialized=True
            ... )
            >>> result.is_success
            True
            
            >>> error_result = DocumentationResult(
            ...     terraform_code="terraform_test/main.tf",
            ...     resource_name="awscc_s3_bucket",
            ...     provider_version="1.53.0",
            ...     workspace_initialized=False,
            ...     error="Generation failed"
            ... )
            >>> error_result.is_success
            False
            
            >>> empty_code_result = DocumentationResult(
            ...     terraform_code="",
            ...     resource_name="awscc_s3_bucket",
            ...     provider_version="1.53.0",
            ...     workspace_initialized=False
            ... )
            >>> empty_code_result.is_success
            False
        """
        return self.error is None and len(self.terraform_code) > 0


# =============================================================================
# Terraform Agent Models
# =============================================================================

class TerraformLifecycleStep(TANGOBaseModel):
    """
    Individual Terraform lifecycle step result.
    
    Represents the outcome of a single step in the Terraform lifecycle (init, validate,
    plan, apply, or destroy). Each step tracks its execution status, output, and any
    errors that occurred during execution.
    
    Attributes:
        step: Name of the Terraform lifecycle step. Must be one of: "init", "validate",
              "plan", "apply", or "destroy".
        status: Execution status of the step. Must be one of: "success", "failed", or
               "skipped". "skipped" indicates the step was not executed (e.g., apply
               skipped if plan failed).
        output: Optional command output from the Terraform execution. Contains the
               stdout/stderr from running the terraform command. Useful for debugging
               and understanding what happened during execution.
        error: Optional error message if the step failed. Provides details about what
              went wrong during execution.
    
    Validation:
        - step must match pattern: ^(init|validate|plan|apply|destroy)$
        - status must match pattern: ^(success|failed|skipped)$
        - output is optional
        - error is optional
    
    Usage Examples:
        # Create a successful init step
        >>> init_step = TerraformLifecycleStep(
        ...     step="init",
        ...     status="success",
        ...     output="Terraform has been successfully initialized!"
        ... )
        >>> print(init_step.step)
        init
        >>> print(init_step.status)
        success
        
        # Create a failed validate step
        >>> validate_step = TerraformLifecycleStep(
        ...     step="validate",
        ...     status="failed",
        ...     output="Error: Invalid configuration",
        ...     error="Missing required argument: bucket_name"
        ... )
        >>> print(validate_step.error)
        Missing required argument: bucket_name
        
        # Create a skipped apply step
        >>> apply_step = TerraformLifecycleStep(
        ...     step="apply",
        ...     status="skipped",
        ...     error="Skipped due to plan failure"
        ... )
        >>> print(apply_step.status)
        skipped
        
        # Parse from JSON
        >>> json_str = '''
        ... {
        ...     "step": "plan",
        ...     "status": "success",
        ...     "output": "Plan: 1 to add, 0 to change, 0 to destroy."
        ... }
        ... '''
        >>> step = TerraformLifecycleStep.model_validate_json(json_str)
        >>> print(step.step)
        plan
    
    Notes:
        - Steps are typically executed in order: init → validate → plan → apply → destroy
        - A failed step usually causes subsequent steps to be skipped
        - The output field can be quite large for complex Terraform operations
        - Error messages should be concise and actionable
        - All validation happens automatically on model instantiation
    """
    
    step: str = Field(
        description="Terraform lifecycle step name",
        pattern=r"^(init|validate|plan|apply|destroy)$",
        examples=["init", "validate", "plan", "apply", "destroy"]
    )
    
    status: str = Field(
        description="Execution status of the step",
        pattern=r"^(success|failed|skipped)$",
        examples=["success", "failed", "skipped"]
    )
    
    output: Optional[str] = Field(
        default=None,
        description="Command output from Terraform execution (stdout/stderr)",
        examples=[
            None,
            "Terraform has been successfully initialized!",
            "Plan: 1 to add, 0 to change, 0 to destroy.",
            "Error: Invalid configuration"
        ]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if the step failed",
        examples=[
            None,
            "Missing required argument: bucket_name",
            "Provider configuration not found",
            "Resource already exists"
        ]
    )


class TerraformResult(TANGOBaseModel):
    """
    Result from Terraform validation lifecycle execution.
    
    The terraform agent executes the complete Terraform lifecycle (init, validate,
    plan, apply, destroy) to validate that generated Terraform code works correctly
    with real AWS infrastructure. This model captures the overall result, detailed
    step-by-step execution information, any fixes applied, and metadata about the
    validation process.
    
    Attributes:
        status: Overall status of the Terraform lifecycle. Must be either "success"
               (all steps completed successfully) or "failed" (one or more steps failed).
        corrected_code: Optional path to the main.tf file containing corrected Terraform
                       code that passed validation. Required on success, optional on failure.
                       This is the final, working version of the code after any fixes.
        resource_name: Target AWS CloudControl resource name being validated (e.g.,
                      "awscc_s3_bucket"). Must match the AWSCC naming pattern.
        provider_version: AWSCC provider version used for validation (e.g., "1.53.0").
                         Must follow semantic versioning format.
        lifecycle_steps: List of TerraformLifecycleStep objects tracking each step
                        (init, validate, plan, apply, destroy) with detailed results.
                        Can be empty if no steps were executed.
        fixes_applied: List of descriptions of fixes that were applied to make the
                      code work. Each entry describes a specific change made during
                      validation. Can be empty if no fixes were needed.
        supplemental_resources_added: List of supplemental resource names that were
                                     added during validation to make the main resource
                                     work. Can be empty if no additional resources needed.
        workspace_reused: Whether an existing terraform_test workspace was reused
                         (True) or a new one was created (False). Reusing workspaces
                         saves significant time (~60 seconds per resource).
        error_message: Optional error message if the lifecycle failed. Provides a
                      high-level summary of what went wrong.
    
    Computed Properties:
        is_success: Returns True if the overall status is "success".
        apply_succeeded: Returns True if any apply step in lifecycle_steps has
                        status "success", indicating resources were successfully
                        created in AWS.
    
    Validation:
        - status must match pattern: ^(success|failed)$
        - corrected_code is optional (but typically required on success)
        - resource_name must match pattern: ^awscc_[a-z0-9_]+$
        - provider_version must match pattern: ^\\d+\\.\\d+\\.\\d+$
        - lifecycle_steps defaults to empty list if not provided
        - fixes_applied defaults to empty list if not provided
        - supplemental_resources_added defaults to empty list if not provided
        - workspace_reused is required
        - error_message is optional
    
    Usage Examples:
        # Parse successful result from JSON
        >>> json_str = '''
        ... {
        ...     "status": "success",
        ...     "corrected_code": "terraform_test/main.tf",
        ...     "resource_name": "awscc_s3_bucket",
        ...     "provider_version": "1.53.0",
        ...     "lifecycle_steps": [
        ...         {"step": "init", "status": "success", "output": "Initialized!"},
        ...         {"step": "validate", "status": "success"},
        ...         {"step": "plan", "status": "success", "output": "Plan: 1 to add"},
        ...         {"step": "apply", "status": "success", "output": "Apply complete!"},
        ...         {"step": "destroy", "status": "success"}
        ...     ],
        ...     "fixes_applied": ["Added bucket_name argument"],
        ...     "supplemental_resources_added": [],
        ...     "workspace_reused": true
        ... }
        ... '''
        >>> result = TerraformResult.model_validate_json(json_str)
        >>> print(result.status)
        success
        
        # Check if validation succeeded
        >>> if result.is_success:
        ...     print(f"Validation passed for {result.resource_name}")
        Validation passed for awscc_s3_bucket
        
        # Check if apply succeeded
        >>> if result.apply_succeeded:
        ...     print("Resources were successfully created in AWS")
        Resources were successfully created in AWS
        
        # Access lifecycle steps
        >>> for step in result.lifecycle_steps:
        ...     print(f"{step.step}: {step.status}")
        init: success
        validate: success
        plan: success
        apply: success
        destroy: success
        
        # Check fixes applied
        >>> print(result.fixes_applied)
        ['Added bucket_name argument']
        
        # Create failed result
        >>> failed_result = TerraformResult(
        ...     status="failed",
        ...     resource_name="awscc_lambda_function",
        ...     provider_version="1.53.0",
        ...     lifecycle_steps=[
        ...         TerraformLifecycleStep(step="init", status="success"),
        ...         TerraformLifecycleStep(
        ...             step="validate",
        ...             status="failed",
        ...             error="Missing required argument"
        ...         )
        ...     ],
        ...     workspace_reused=False,
        ...     error_message="Validation failed: Missing required argument"
        ... )
        >>> print(failed_result.is_success)
        False
        >>> print(failed_result.apply_succeeded)
        False
        
        # Create minimal result
        >>> minimal_result = TerraformResult(
        ...     status="success",
        ...     corrected_code="terraform_test/main.tf",
        ...     resource_name="awscc_dynamodb_table",
        ...     provider_version="1.53.0",
        ...     workspace_reused=True
        ... )
        >>> print(minimal_result.lifecycle_steps)
        []
        
        # Serialize back to JSON
        >>> json_output = result.model_dump_json()
    
    Notes:
        - The status field provides a high-level success/failure indicator
        - lifecycle_steps provides detailed step-by-step execution information
        - corrected_code contains the final working version after any fixes
        - fixes_applied documents what changes were made during validation
        - supplemental_resources_added tracks additional resources created
        - workspace_reused=True indicates significant time savings (~60 seconds)
        - The is_success property is a convenient way to check overall status
        - The apply_succeeded property specifically checks if AWS resources were created
        - All validation happens automatically on model instantiation
        - Invalid data raises pydantic.ValidationError with detailed error messages
    """
    
    status: str = Field(
        description="Overall status of the Terraform lifecycle",
        pattern=r"^(success|failed)$",
        examples=["success", "failed"]
    )
    
    corrected_code: Optional[str] = Field(
        default=None,
        description="Path to main.tf containing corrected Terraform code that passed validation",
        examples=[None, "terraform_test/main.tf", "terraform_test/main.tf"]
    )
    
    resource_name: str = Field(
        description="Target AWS CloudControl resource name being validated",
        pattern=r"^awscc_[a-z0-9_]+$",
        examples=["awscc_s3_bucket", "awscc_lambda_function", "awscc_dynamodb_table"]
    )
    
    provider_version: str = Field(
        description="AWSCC provider version used for validation",
        pattern=r"^\d+\.\d+\.\d+$",
        examples=["1.53.0", "1.48.0", "2.0.0"]
    )
    
    lifecycle_steps: List[TerraformLifecycleStep] = Field(
        default_factory=list,
        description="Detailed results from each Terraform lifecycle step (init, validate, plan, apply, destroy)",
        examples=[
            [],
            [
                {"step": "init", "status": "success"},
                {"step": "validate", "status": "success"},
                {"step": "plan", "status": "success"},
                {"step": "apply", "status": "success"},
                {"step": "destroy", "status": "success"}
            ]
        ]
    )
    
    fixes_applied: List[str] = Field(
        default_factory=list,
        description="List of fixes applied to make the code work during validation",
        examples=[
            [],
            ["Added bucket_name argument"],
            ["Fixed IAM role ARN format", "Added required tags"],
            ["Corrected subnet configuration", "Added security group rules"]
        ]
    )
    
    supplemental_resources_added: List[str] = Field(
        default_factory=list,
        description="Supplemental resource names added during validation to support the main resource",
        examples=[
            [],
            ["awscc_iam_role"],
            ["awscc_vpc", "awscc_subnet"],
            ["awscc_kms_key", "awscc_iam_role"]
        ]
    )
    
    workspace_reused: bool = Field(
        description="Whether existing terraform_test workspace was reused (saves ~60 seconds)"
    )
    
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if the Terraform lifecycle failed",
        examples=[
            None,
            "Terraform validate failed: Missing required argument",
            "Terraform apply failed: Resource already exists",
            "Terraform destroy failed: Resource not found"
        ]
    )
    
    @property
    def is_success(self) -> bool:
        """
        Check if Terraform lifecycle succeeded.
        
        Returns True if the overall status is "success", indicating that all
        Terraform lifecycle steps completed successfully and the code is valid.
        
        Returns:
            bool: True if lifecycle succeeded, False otherwise.
        
        Examples:
            >>> result = TerraformResult(
            ...     status="success",
            ...     corrected_code="terraform_test/main.tf",
            ...     resource_name="awscc_s3_bucket",
            ...     provider_version="1.53.0",
            ...     workspace_reused=True
            ... )
            >>> result.is_success
            True
            
            >>> failed_result = TerraformResult(
            ...     status="failed",
            ...     resource_name="awscc_s3_bucket",
            ...     provider_version="1.53.0",
            ...     workspace_reused=False,
            ...     error_message="Validation failed"
            ... )
            >>> failed_result.is_success
            False
        """
        return self.status == "success"
    
    @property
    def apply_succeeded(self) -> bool:
        """
        Check if terraform apply succeeded.
        
        Returns True if any apply step in the lifecycle_steps list has a status
        of "success", indicating that AWS resources were successfully created.
        This is a more specific check than is_success, as it confirms that the
        code not only validated but also successfully deployed to AWS.
        
        Returns:
            bool: True if apply step succeeded, False otherwise.
        
        Examples:
            >>> result = TerraformResult(
            ...     status="success",
            ...     corrected_code="terraform_test/main.tf",
            ...     resource_name="awscc_s3_bucket",
            ...     provider_version="1.53.0",
            ...     lifecycle_steps=[
            ...         TerraformLifecycleStep(step="init", status="success"),
            ...         TerraformLifecycleStep(step="validate", status="success"),
            ...         TerraformLifecycleStep(step="plan", status="success"),
            ...         TerraformLifecycleStep(step="apply", status="success"),
            ...         TerraformLifecycleStep(step="destroy", status="success")
            ...     ],
            ...     workspace_reused=True
            ... )
            >>> result.apply_succeeded
            True
            
            >>> failed_apply_result = TerraformResult(
            ...     status="failed",
            ...     resource_name="awscc_s3_bucket",
            ...     provider_version="1.53.0",
            ...     lifecycle_steps=[
            ...         TerraformLifecycleStep(step="init", status="success"),
            ...         TerraformLifecycleStep(step="validate", status="success"),
            ...         TerraformLifecycleStep(step="plan", status="success"),
            ...         TerraformLifecycleStep(step="apply", status="failed", error="Resource exists")
            ...     ],
            ...     workspace_reused=False
            ... )
            >>> failed_apply_result.apply_succeeded
            False
            
            >>> no_apply_result = TerraformResult(
            ...     status="failed",
            ...     resource_name="awscc_s3_bucket",
            ...     provider_version="1.53.0",
            ...     lifecycle_steps=[
            ...         TerraformLifecycleStep(step="init", status="success"),
            ...         TerraformLifecycleStep(step="validate", status="failed")
            ...     ],
            ...     workspace_reused=False
            ... )
            >>> no_apply_result.apply_succeeded
            False
        """
        apply_steps = [s for s in self.lifecycle_steps if s.step == "apply"]
        return any(s.status == "success" for s in apply_steps)


# =============================================================================
# Validation Agent Models
# =============================================================================

class ValidationResult(TANGOBaseModel):
    """
    Result from independent validation of Terraform code and AWS resource deployment.
    
    The validation agent performs an independent review of the Terraform code generated
    and validated by previous agents. It re-runs the Terraform lifecycle in a fresh
    context to confirm that the code works correctly, verifies that the target resource
    was actually created, and generates a detailed analysis report stored in S3.
    
    This independent validation provides an additional quality check and ensures that
    the generated examples are truly production-ready.
    
    Attributes:
        validation_result: Overall validation outcome. Must be either "success" (all
                          validation checks passed) or "failed" (one or more checks failed).
        resource_name: Target AWS CloudControl resource name that was validated (e.g.,
                      "awscc_s3_bucket"). Must match the AWSCC naming pattern.
        provider_version: AWSCC provider version used for validation (e.g., "1.53.0").
                         Must follow semantic versioning format.
        target_resource_confirmed: Whether the target resource was found in the Terraform
                                  code and successfully created in AWS. True indicates the
                                  main resource (not just supplemental resources) was deployed.
        s3_analysis_path: S3 path to the detailed validation analysis report. Must follow
                         the pattern "analysis/resource/{resource_name}.txt". This report
                         contains comprehensive validation results, Terraform output, and
                         quality assessment.
        terraform_steps: Dictionary mapping Terraform step names to their status. Keys are
                        step names ("init", "validate", "plan", "apply", "destroy") and
                        values are status strings ("success", "failed", "skipped"). Can be
                        empty if no steps were executed.
        workspace_reused: Whether an existing terraform_test workspace was reused (True)
                         or a new one was created (False). Reusing workspaces saves
                         significant time (~60 seconds per resource).
        validation_timestamp: When the validation was performed. Automatically set to
                             current UTC time if not provided. Useful for tracking when
                             validation occurred and for audit trails.
        error: Optional error message if validation failed. Provides details about what
              went wrong during the validation process.
    
    Computed Properties:
        is_success: Returns True if validation_result is "success".
        all_steps_passed: Returns True if all Terraform steps in terraform_steps dict
                         have status "success", indicating complete lifecycle success.
    
    Validation:
        - validation_result must match pattern: ^(success|failed)$
        - resource_name must match pattern: ^awscc_[a-z0-9_]+$
        - provider_version must match pattern: ^\\d+\\.\\d+\\.\\d+$
        - target_resource_confirmed is required
        - s3_analysis_path must match pattern: ^analysis/resource/.+\\.txt$
        - terraform_steps defaults to empty dict if not provided
        - workspace_reused is required
        - validation_timestamp defaults to current UTC time if not provided
        - error is optional
    
    Usage Examples:
        # Parse successful validation from JSON
        >>> json_str = '''
        ... {
        ...     "validation_result": "success",
        ...     "resource_name": "awscc_s3_bucket",
        ...     "provider_version": "1.53.0",
        ...     "target_resource_confirmed": true,
        ...     "s3_analysis_path": "analysis/resource/awscc_s3_bucket.txt",
        ...     "terraform_steps": {
        ...         "init": "success",
        ...         "validate": "success",
        ...         "plan": "success",
        ...         "apply": "success",
        ...         "destroy": "success"
        ...     },
        ...     "workspace_reused": true
        ... }
        ... '''
        >>> result = ValidationResult.model_validate_json(json_str)
        >>> print(result.validation_result)
        success
        
        # Check if validation succeeded
        >>> if result.is_success:
        ...     print(f"Validation passed for {result.resource_name}")
        Validation passed for awscc_s3_bucket
        
        # Check if all steps passed
        >>> if result.all_steps_passed:
        ...     print("All Terraform steps completed successfully")
        All Terraform steps completed successfully
        
        # Check target resource confirmation
        >>> if result.target_resource_confirmed:
        ...     print("Target resource was successfully created in AWS")
        Target resource was successfully created in AWS
        
        # Access S3 analysis path
        >>> print(result.s3_analysis_path)
        analysis/resource/awscc_s3_bucket.txt
        
        # Access terraform steps
        >>> for step, status in result.terraform_steps.items():
        ...     print(f"{step}: {status}")
        init: success
        validate: success
        plan: success
        apply: success
        destroy: success
        
        # Create failed validation result
        >>> failed_result = ValidationResult(
        ...     validation_result="failed",
        ...     resource_name="awscc_lambda_function",
        ...     provider_version="1.53.0",
        ...     target_resource_confirmed=False,
        ...     s3_analysis_path="analysis/resource/awscc_lambda_function.txt",
        ...     terraform_steps={
        ...         "init": "success",
        ...         "validate": "success",
        ...         "plan": "failed"
        ...     },
        ...     workspace_reused=False,
        ...     error="Terraform plan failed: Missing required argument"
        ... )
        >>> print(failed_result.is_success)
        False
        >>> print(failed_result.all_steps_passed)
        False
        
        # Create with automatic timestamp
        >>> result_with_timestamp = ValidationResult(
        ...     validation_result="success",
        ...     resource_name="awscc_dynamodb_table",
        ...     provider_version="1.53.0",
        ...     target_resource_confirmed=True,
        ...     s3_analysis_path="analysis/resource/awscc_dynamodb_table.txt",
        ...     workspace_reused=True
        ... )
        >>> print(type(result_with_timestamp.validation_timestamp))
        <class 'datetime.datetime'>
        
        # Create minimal result
        >>> minimal_result = ValidationResult(
        ...     validation_result="success",
        ...     resource_name="awscc_ec2_instance",
        ...     provider_version="1.53.0",
        ...     target_resource_confirmed=True,
        ...     s3_analysis_path="analysis/resource/awscc_ec2_instance.txt",
        ...     workspace_reused=True
        ... )
        >>> print(minimal_result.terraform_steps)
        {}
        
        # Serialize back to JSON
        >>> json_output = result.model_dump_json()
    
    Notes:
        - This is an independent validation separate from the terraform_agent
        - The validation agent re-runs Terraform lifecycle to confirm code works
        - target_resource_confirmed ensures the main resource (not just supplemental) was created
        - s3_analysis_path points to a detailed validation report in S3
        - terraform_steps provides step-by-step status information
        - workspace_reused=True indicates significant time savings (~60 seconds)
        - validation_timestamp is automatically set to current UTC time if not provided
        - The is_success property provides a convenient way to check overall status
        - The all_steps_passed property checks if every Terraform step succeeded
        - All validation happens automatically on model instantiation
        - Invalid data raises pydantic.ValidationError with detailed error messages
        - The validation report in S3 contains comprehensive analysis and recommendations
    """
    
    validation_result: str = Field(
        description="Overall validation outcome",
        pattern=r"^(success|failed)$",
        examples=["success", "failed"]
    )
    
    resource_name: str = Field(
        description="Target AWS CloudControl resource name that was validated",
        pattern=r"^awscc_[a-z0-9_]+$",
        examples=["awscc_s3_bucket", "awscc_lambda_function", "awscc_dynamodb_table"]
    )
    
    provider_version: str = Field(
        description="AWSCC provider version used for validation",
        pattern=r"^\d+\.\d+\.\d+$",
        examples=["1.53.0", "1.48.0", "2.0.0"]
    )
    
    target_resource_confirmed: bool = Field(
        description="Whether the target resource was found in Terraform code and successfully created in AWS"
    )
    
    s3_analysis_path: str = Field(
        description="S3 path to detailed validation analysis report",
        pattern=r"^analysis/resource/.+\.txt$",
        examples=[
            "analysis/resource/awscc_s3_bucket.txt",
            "analysis/resource/awscc_lambda_function.txt",
            "analysis/resource/awscc_dynamodb_table.txt"
        ]
    )
    
    terraform_steps: Dict[str, str] = Field(
        default_factory=dict,
        description="Dictionary mapping Terraform step names to their status (e.g., {'init': 'success', 'validate': 'success'})",
        examples=[
            {},
            {"init": "success", "validate": "success", "plan": "success", "apply": "success", "destroy": "success"},
            {"init": "success", "validate": "failed"},
            {"init": "success", "validate": "success", "plan": "success", "apply": "failed"}
        ]
    )
    
    workspace_reused: bool = Field(
        description="Whether existing terraform_test workspace was reused (saves ~60 seconds)"
    )
    
    validation_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the validation was performed (UTC)"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if validation failed",
        examples=[
            None,
            "Terraform plan failed: Missing required argument",
            "Target resource not found in Terraform code",
            "Terraform apply failed: Resource already exists",
            "Validation timeout exceeded"
        ]
    )
    
    @property
    def is_success(self) -> bool:
        """
        Check if validation passed.
        
        Returns True if the validation_result is "success", indicating that all
        validation checks passed and the Terraform code is confirmed to work correctly.
        
        Returns:
            bool: True if validation passed, False otherwise.
        
        Examples:
            >>> result = ValidationResult(
            ...     validation_result="success",
            ...     resource_name="awscc_s3_bucket",
            ...     provider_version="1.53.0",
            ...     target_resource_confirmed=True,
            ...     s3_analysis_path="analysis/resource/awscc_s3_bucket.txt",
            ...     workspace_reused=True
            ... )
            >>> result.is_success
            True
            
            >>> failed_result = ValidationResult(
            ...     validation_result="failed",
            ...     resource_name="awscc_s3_bucket",
            ...     provider_version="1.53.0",
            ...     target_resource_confirmed=False,
            ...     s3_analysis_path="analysis/resource/awscc_s3_bucket.txt",
            ...     workspace_reused=False,
            ...     error="Validation failed"
            ... )
            >>> failed_result.is_success
            False
        """
        return self.validation_result == "success"
    
    @property
    def all_steps_passed(self) -> bool:
        """
        Check if all Terraform steps succeeded.
        
        Returns True if all steps in the terraform_steps dictionary have a status
        of "success". This provides a more granular check than is_success, as it
        confirms that every individual Terraform lifecycle step completed successfully.
        
        If terraform_steps is empty, returns True (no steps means no failures).
        
        Returns:
            bool: True if all steps succeeded, False if any step failed or was skipped.
        
        Examples:
            >>> result = ValidationResult(
            ...     validation_result="success",
            ...     resource_name="awscc_s3_bucket",
            ...     provider_version="1.53.0",
            ...     target_resource_confirmed=True,
            ...     s3_analysis_path="analysis/resource/awscc_s3_bucket.txt",
            ...     terraform_steps={
            ...         "init": "success",
            ...         "validate": "success",
            ...         "plan": "success",
            ...         "apply": "success",
            ...         "destroy": "success"
            ...     },
            ...     workspace_reused=True
            ... )
            >>> result.all_steps_passed
            True
            
            >>> partial_success_result = ValidationResult(
            ...     validation_result="failed",
            ...     resource_name="awscc_lambda_function",
            ...     provider_version="1.53.0",
            ...     target_resource_confirmed=False,
            ...     s3_analysis_path="analysis/resource/awscc_lambda_function.txt",
            ...     terraform_steps={
            ...         "init": "success",
            ...         "validate": "success",
            ...         "plan": "failed"
            ...     },
            ...     workspace_reused=False
            ... )
            >>> partial_success_result.all_steps_passed
            False
            
            >>> empty_steps_result = ValidationResult(
            ...     validation_result="success",
            ...     resource_name="awscc_dynamodb_table",
            ...     provider_version="1.53.0",
            ...     target_resource_confirmed=True,
            ...     s3_analysis_path="analysis/resource/awscc_dynamodb_table.txt",
            ...     workspace_reused=True
            ... )
            >>> empty_steps_result.all_steps_passed
            True
        """
        return all(status == "success" for status in self.terraform_steps.values())


# =============================================================================
# Terraform Cleanup Agent Models
# =============================================================================

class CleanupResult(TANGOBaseModel):
    """
    Result from cleaning up Terraform code by removing provider blocks and test infrastructure.
    
    The terraform cleanup agent processes validated Terraform code to remove provider
    configuration blocks and any test-specific infrastructure (like random resources),
    producing production-ready examples suitable for documentation. This model captures
    the cleaned code, tracks what operations were performed, and handles cases where
    cleanup should be skipped (e.g., when validation failed).
    
    The cleanup agent runs after validation and before storage, ensuring that only
    clean, production-ready code is stored in the examples directory.
    
    Attributes:
        cleaned_code: Path to the main.tf file containing the cleaned Terraform code.
                     Must not be empty. If cleanup was skipped, this points to the
                     original unchanged code. This is the code that will be stored.
        resource_name: Target AWS CloudControl resource name (e.g., "awscc_s3_bucket").
                      Must match the AWSCC naming pattern.
        cleanup_applied: Whether cleanup operations were actually performed. False
                        indicates cleanup was skipped (e.g., due to failed validation).
                        True indicates provider blocks and test infrastructure were removed.
        cleanup_operations: List of cleanup operations that were performed. Each entry
                           describes a specific change made (e.g., "Removed provider blocks",
                           "Removed random_string resources"). Empty list if cleanup was
                           skipped. Useful for audit trail and understanding what changed.
        original_code_path: Optional reference to the original code before cleanup.
                           Useful for comparison and debugging. May be None if cleanup
                           was skipped or if original code wasn't preserved.
        skipped_reason: Optional explanation of why cleanup was skipped. Typically set
                       when validation failed (e.g., "Failed validation detected - keeping
                       original code"). None if cleanup was performed normally.
        error: Optional error message if cleanup failed unexpectedly. When populated,
              indicates that the cleanup process encountered an issue. None if cleanup
              succeeded or was intentionally skipped.
    
    Computed Properties:
        is_success: Returns True if no error occurred (cleanup succeeded or was
                   intentionally skipped). False only if an unexpected error occurred.
    
    Validation:
        - cleaned_code must not be empty (min_length=1)
        - resource_name must match pattern: ^awscc_[a-z0-9_]+$
        - cleanup_applied is required
        - cleanup_operations defaults to empty list if not provided
        - original_code_path is optional
        - skipped_reason is optional
        - error is optional
        - Either cleanup_applied is True OR skipped_reason should be provided
    
    Usage Examples:
        # Parse successful cleanup from JSON
        >>> json_str = '''
        ... {
        ...     "cleaned_code": "terraform_test/main.tf",
        ...     "resource_name": "awscc_s3_bucket",
        ...     "cleanup_applied": true,
        ...     "cleanup_operations": [
        ...         "Removed provider blocks",
        ...         "Removed random_string resources"
        ...     ],
        ...     "original_code_path": "terraform_test/main.tf.backup"
        ... }
        ... '''
        >>> result = CleanupResult.model_validate_json(json_str)
        >>> print(result.resource_name)
        awscc_s3_bucket
        
        # Check if cleanup was applied
        >>> if result.cleanup_applied:
        ...     print("Cleanup operations performed:")
        ...     for op in result.cleanup_operations:
        ...         print(f"  - {op}")
        Cleanup operations performed:
          - Removed provider blocks
          - Removed random_string resources
        
        # Check if cleanup succeeded
        >>> if result.is_success:
        ...     print(f"Cleaned code available at: {result.cleaned_code}")
        Cleaned code available at: terraform_test/main.tf
        
        # Create skipped cleanup result (validation failed)
        >>> skipped_result = CleanupResult(
        ...     cleaned_code="terraform_test/main.tf",
        ...     resource_name="awscc_lambda_function",
        ...     cleanup_applied=False,
        ...     cleanup_operations=[],
        ...     skipped_reason="Failed validation detected - keeping original code for debugging"
        ... )
        >>> print(skipped_result.cleanup_applied)
        False
        >>> print(skipped_result.skipped_reason)
        Failed validation detected - keeping original code for debugging
        >>> print(skipped_result.is_success)
        True
        
        # Create cleanup with error
        >>> error_result = CleanupResult(
        ...     cleaned_code="terraform_test/main.tf",
        ...     resource_name="awscc_dynamodb_table",
        ...     cleanup_applied=False,
        ...     cleanup_operations=[],
        ...     error="Failed to parse Terraform code: Invalid HCL syntax"
        ... )
        >>> print(error_result.is_success)
        False
        >>> print(error_result.error)
        Failed to parse Terraform code: Invalid HCL syntax
        
        # Create minimal successful cleanup
        >>> minimal_result = CleanupResult(
        ...     cleaned_code="terraform_test/main.tf",
        ...     resource_name="awscc_ec2_instance",
        ...     cleanup_applied=True,
        ...     cleanup_operations=["Removed provider blocks"]
        ... )
        >>> print(minimal_result.cleanup_operations)
        ['Removed provider blocks']
        
        # Create cleanup with original code reference
        >>> with_backup_result = CleanupResult(
        ...     cleaned_code="terraform_test/main.tf",
        ...     resource_name="awscc_rds_db_instance",
        ...     cleanup_applied=True,
        ...     cleanup_operations=[
        ...         "Removed provider blocks",
        ...         "Removed random_password resources",
        ...         "Removed random_id resources"
        ...     ],
        ...     original_code_path="terraform_test/main.tf.original"
        ... )
        >>> print(with_backup_result.original_code_path)
        terraform_test/main.tf.original
        
        # Serialize back to JSON
        >>> json_output = result.model_dump_json()
    
    Notes:
        - cleanup_applied=False with skipped_reason indicates intentional skip (not an error)
        - cleanup_applied=False with error indicates unexpected failure
        - cleanup_operations provides audit trail of what was changed
        - original_code_path allows comparison between original and cleaned code
        - The is_success property returns True for both successful cleanup and intentional skips
        - Only returns False if an unexpected error occurred
        - Cleanup is typically skipped when validation fails to preserve debugging information
        - Provider blocks are removed to make code suitable for documentation
        - Random resources are removed as they're test infrastructure, not production code
        - All validation happens automatically on model instantiation
        - Invalid data raises pydantic.ValidationError with detailed error messages
        - This model is used between validation_agent and storage_agent in the pipeline
    """
    
    cleaned_code: str = Field(
        description="Path to main.tf containing the cleaned Terraform code (or unchanged if skipped)",
        min_length=1,
        examples=[
            "terraform_test/main.tf",
            "terraform_test/main.tf",
            "terraform_test/main_cleaned.tf"
        ]
    )
    
    resource_name: str = Field(
        description="Target AWS CloudControl resource name",
        pattern=r"^awscc_[a-z0-9_]+$",
        examples=["awscc_s3_bucket", "awscc_lambda_function", "awscc_dynamodb_table"]
    )
    
    cleanup_applied: bool = Field(
        description="Whether cleanup operations were performed (false if skipped due to failure)"
    )
    
    cleanup_operations: List[str] = Field(
        default_factory=list,
        description="List of cleanup operations performed (e.g., 'Removed provider blocks', 'Removed random resources')",
        examples=[
            [],
            ["Removed provider blocks"],
            ["Removed provider blocks", "Removed random_string resources"],
            ["Removed provider blocks", "Removed random_password resources", "Removed random_id resources"]
        ]
    )
    
    original_code_path: Optional[str] = Field(
        default=None,
        description="Reference to original code before cleanup (for comparison/debugging)",
        examples=[
            None,
            "terraform_test/main.tf.backup",
            "terraform_test/main.tf.original",
            "terraform_test/main_before_cleanup.tf"
        ]
    )
    
    skipped_reason: Optional[str] = Field(
        default=None,
        description="Reason cleanup was skipped (e.g., 'Failed validation detected')",
        examples=[
            None,
            "Failed validation detected - keeping original code for debugging",
            "Validation failed - skipping cleanup to preserve error context",
            "Terraform apply failed - keeping original code"
        ]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if cleanup failed unexpectedly",
        examples=[
            None,
            "Failed to parse Terraform code: Invalid HCL syntax",
            "Failed to write cleaned code: Permission denied",
            "Failed to backup original code: Disk full"
        ]
    )
    
    @property
    def is_success(self) -> bool:
        """
        Check if cleanup succeeded (or was intentionally skipped).
        
        Returns True if no error occurred, indicating that either:
        1. Cleanup was performed successfully (cleanup_applied=True, error=None)
        2. Cleanup was intentionally skipped (cleanup_applied=False, skipped_reason set, error=None)
        
        Returns False only if an unexpected error occurred during cleanup.
        
        This property distinguishes between intentional skips (which are success cases)
        and unexpected failures (which are error cases).
        
        Returns:
            bool: True if cleanup succeeded or was intentionally skipped, False if error occurred.
        
        Examples:
            >>> result = CleanupResult(
            ...     cleaned_code="terraform_test/main.tf",
            ...     resource_name="awscc_s3_bucket",
            ...     cleanup_applied=True,
            ...     cleanup_operations=["Removed provider blocks"]
            ... )
            >>> result.is_success
            True
            
            >>> skipped_result = CleanupResult(
            ...     cleaned_code="terraform_test/main.tf",
            ...     resource_name="awscc_lambda_function",
            ...     cleanup_applied=False,
            ...     skipped_reason="Failed validation detected"
            ... )
            >>> skipped_result.is_success
            True
            
            >>> error_result = CleanupResult(
            ...     cleaned_code="terraform_test/main.tf",
            ...     resource_name="awscc_dynamodb_table",
            ...     cleanup_applied=False,
            ...     error="Failed to parse Terraform code"
            ... )
            >>> error_result.is_success
            False
        """
        return self.error is None


# =============================================================================
# Storage Agent Models
# =============================================================================

class StorageRequest(TANGOBaseModel):
    """
    Request to store pipeline results in DynamoDB and S3.
    
    The storage agent receives this request containing all pipeline execution data
    and stores it in DynamoDB (for tracking) and S3 (for code, templates, and analysis).
    This model captures the complete pipeline state including nested results from
    validation and terraform agents.
    
    This is the final step in the TANGO pipeline, ensuring all results are persisted
    for future reference, analysis, and documentation generation.
    
    Attributes:
        resource_name: AWS CloudControl resource name (e.g., "awscc_s3_bucket").
                      Must match the AWSCC naming pattern.
        status: Overall pipeline status. Must be either "success" (pipeline completed
               successfully) or "failed" (one or more agents failed).
        terraform_code: Path to the main.tf file containing the final Terraform code.
                       Must not be empty. This is the code that will be stored in S3.
        provider_version: AWSCC provider version used throughout the pipeline (e.g.,
                         "1.53.0"). Must follow semantic versioning format.
        validation_result: ValidationResult object containing complete validation data
                          from the validation agent. This is a nested model that includes
                          all validation details, terraform steps, and analysis path.
        terraform_result: Optional TerraformResult object containing terraform agent
                         execution data. May be None if terraform agent was not executed
                         (e.g., if documentation agent failed). This is a nested model
                         that includes lifecycle steps, fixes applied, and corrected code.
        execution_time_seconds: Optional total pipeline execution time in seconds.
                               Must be non-negative if provided. Useful for performance
                               tracking and optimization analysis.
        failed_agent: Optional name of the agent that failed (if any). Examples:
                     "discovery_agent", "documentation_agent", "terraform_agent",
                     "validation_agent". Helps identify where in the pipeline the
                     failure occurred.
    
    Validation:
        - resource_name must match pattern: ^awscc_[a-z0-9_]+$
        - status must match pattern: ^(success|failed)$
        - terraform_code must not be empty (min_length=1)
        - provider_version must match pattern: ^\\d+\\.\\d+\\.\\d+$
        - validation_result is required (nested ValidationResult model)
        - terraform_result is optional (nested TerraformResult model)
        - execution_time_seconds must be >= 0 if provided
        - failed_agent is optional
    
    Usage Examples:
        # Create successful storage request with all data
        >>> from datetime import datetime
        >>> validation_result = ValidationResult(
        ...     validation_result="success",
        ...     resource_name="awscc_s3_bucket",
        ...     provider_version="1.53.0",
        ...     target_resource_confirmed=True,
        ...     s3_analysis_path="analysis/resource/awscc_s3_bucket.txt",
        ...     workspace_reused=True
        ... )
        >>> terraform_result = TerraformResult(
        ...     status="success",
        ...     corrected_code="terraform_test/main.tf",
        ...     resource_name="awscc_s3_bucket",
        ...     provider_version="1.53.0",
        ...     workspace_reused=True
        ... )
        >>> storage_req = StorageRequest(
        ...     resource_name="awscc_s3_bucket",
        ...     status="success",
        ...     terraform_code="terraform_test/main.tf",
        ...     provider_version="1.53.0",
        ...     validation_result=validation_result,
        ...     terraform_result=terraform_result,
        ...     execution_time_seconds=125.5
        ... )
        >>> print(storage_req.resource_name)
        awscc_s3_bucket
        
        # Create failed storage request
        >>> failed_validation = ValidationResult(
        ...     validation_result="failed",
        ...     resource_name="awscc_lambda_function",
        ...     provider_version="1.53.0",
        ...     target_resource_confirmed=False,
        ...     s3_analysis_path="analysis/resource/awscc_lambda_function.txt",
        ...     workspace_reused=False,
        ...     error="Validation failed"
        ... )
        >>> failed_storage_req = StorageRequest(
        ...     resource_name="awscc_lambda_function",
        ...     status="failed",
        ...     terraform_code="terraform_test/main.tf",
        ...     provider_version="1.53.0",
        ...     validation_result=failed_validation,
        ...     execution_time_seconds=45.2,
        ...     failed_agent="validation_agent"
        ... )
        >>> print(failed_storage_req.status)
        failed
        >>> print(failed_storage_req.failed_agent)
        validation_agent
        
        # Create minimal storage request (no terraform_result)
        >>> minimal_validation = ValidationResult(
        ...     validation_result="failed",
        ...     resource_name="awscc_dynamodb_table",
        ...     provider_version="1.53.0",
        ...     target_resource_confirmed=False,
        ...     s3_analysis_path="analysis/resource/awscc_dynamodb_table.txt",
        ...     workspace_reused=False,
        ...     error="Documentation agent failed"
        ... )
        >>> minimal_req = StorageRequest(
        ...     resource_name="awscc_dynamodb_table",
        ...     status="failed",
        ...     terraform_code="",
        ...     provider_version="1.53.0",
        ...     validation_result=minimal_validation,
        ...     failed_agent="documentation_agent"
        ... )
        >>> print(minimal_req.terraform_result)
        None
        
        # Parse from JSON (with nested models)
        >>> json_str = '''
        ... {
        ...     "resource_name": "awscc_s3_bucket",
        ...     "status": "success",
        ...     "terraform_code": "terraform_test/main.tf",
        ...     "provider_version": "1.53.0",
        ...     "validation_result": {
        ...         "validation_result": "success",
        ...         "resource_name": "awscc_s3_bucket",
        ...         "provider_version": "1.53.0",
        ...         "target_resource_confirmed": true,
        ...         "s3_analysis_path": "analysis/resource/awscc_s3_bucket.txt",
        ...         "workspace_reused": true
        ...     },
        ...     "execution_time_seconds": 120.5
        ... }
        ... '''
        >>> req = StorageRequest.model_validate_json(json_str)
        >>> print(req.validation_result.validation_result)
        success
        
        # Serialize back to JSON (includes nested models)
        >>> json_output = storage_req.model_dump_json()
    
    Notes:
        - This model contains nested ValidationResult and TerraformResult models
        - Pydantic automatically validates nested models
        - The validation_result field is always required (even for failures)
        - The terraform_result field may be None if terraform agent didn't run
        - execution_time_seconds helps track pipeline performance
        - failed_agent helps identify where failures occurred
        - All validation happens automatically on model instantiation
        - Invalid data raises pydantic.ValidationError with detailed error messages
        - Nested model validation errors will indicate which nested field failed
        - This is the input to the storage_agent, which persists all data
    """
    
    resource_name: str = Field(
        description="AWS CloudControl resource name",
        pattern=r"^awscc_[a-z0-9_]+$",
        examples=["awscc_s3_bucket", "awscc_lambda_function", "awscc_dynamodb_table"]
    )
    
    status: str = Field(
        description="Overall pipeline status",
        pattern=r"^(success|failed)$",
        examples=["success", "failed"]
    )
    
    terraform_code: str = Field(
        description="Path to main.tf containing the final Terraform code",
        min_length=1,
        examples=["terraform_test/main.tf", "terraform_test/main.tf"]
    )
    
    provider_version: str = Field(
        description="AWSCC provider version used throughout the pipeline",
        pattern=r"^\d+\.\d+\.\d+$",
        examples=["1.53.0", "1.48.0", "2.0.0"]
    )
    
    validation_result: ValidationResult = Field(
        description="Complete validation results from validation agent (nested model)"
    )
    
    terraform_result: Optional[TerraformResult] = Field(
        default=None,
        description="Terraform agent execution results (nested model, may be None if terraform agent didn't run)"
    )
    
    cleanup_result: Optional[CleanupResult] = Field(
        default=None,
        description="Cleanup agent results (nested model, may be None if cleanup agent didn't run)"
    )
    
    execution_time_seconds: Optional[float] = Field(
        default=None,
        description="Total pipeline execution time in seconds",
        ge=0,
        examples=[None, 45.2, 120.5, 300.0]
    )
    
    failed_agent: Optional[str] = Field(
        default=None,
        description="Name of the agent that failed (if any)",
        examples=[
            None,
            "discovery_agent",
            "documentation_agent",
            "terraform_agent",
            "validation_agent"
        ]
    )


class StorageResult(TANGOBaseModel):
    """
    Result from storing pipeline data in DynamoDB and S3.
    
    The storage agent returns this result after persisting all pipeline data to
    DynamoDB (for tracking and querying) and S3 (for code, templates, and analysis).
    This model confirms what was stored, where it was stored, and whether the
    storage operations succeeded.
    
    This is the final output of the TANGO pipeline, confirming that all results
    have been successfully persisted for future reference.
    
    Attributes:
        status: Storage operation status. Must be either "success" (all storage
               operations completed successfully) or "failed" (one or more storage
               operations failed).
        resource_name: AWS CloudControl resource name that was stored (e.g.,
                      "awscc_s3_bucket"). Must match the AWSCC naming pattern.
        provider_version: AWSCC provider version used (e.g., "1.53.0"). Must follow
                         semantic versioning format.
        dynamodb_stored: Whether the DynamoDB entry was successfully created. True
                        indicates the pipeline result is tracked in DynamoDB for
                        querying and analysis.
        s3_terraform_link: S3 path to the stored Terraform file. Must match pattern
                          for either successful examples or failed attempts:
                          - Success: "examples/resources/{resource_name}.tf"
                          - Failed: "failed/resources/{resource_name}.tf"
        s3_template_link: Optional S3 path to the generated documentation template.
                         Only populated for successful pipeline runs. Must match
                         pattern: "templates/resources/{resource_name}.md.tmpl"
                         This template is used to generate Terraform provider docs.
        s3_analysis_link: S3 path to the validation analysis report. Must match
                         pattern: "analysis/resource/{resource_name}.txt"
                         Contains detailed validation results and quality assessment.
        template_generated: Whether a documentation template was generated. True only
                           for successful pipeline runs. Templates are used to create
                           official Terraform provider documentation.
        old_entries_deleted: Number of old DynamoDB entries that were deleted for this
                            resource. Must be non-negative. Helps track cleanup of
                            previous attempts and keeps the database clean.
        execution_time: Optional total execution time in seconds. Must be non-negative
                       if provided. Useful for performance tracking and optimization.
        error: Optional error message if storage failed. Provides details about what
              went wrong during the storage process.
    
    Validation:
        - status must match pattern: ^(success|failed)$
        - resource_name must match pattern: ^awscc_[a-z0-9_]+$
        - provider_version must match pattern: ^\\d+\\.\\d+\\.\\d+$
        - dynamodb_stored is required
        - s3_terraform_link must match pattern: ^(examples|failed)/resources/.+\\.tf$
        - s3_template_link must match pattern: ^templates/resources/.+\\.md\\.tmpl$ (if provided)
        - s3_analysis_link must match pattern: ^analysis/resource/.+\\.txt$
        - template_generated is required
        - old_entries_deleted must be >= 0
        - execution_time must be >= 0 if provided
        - error is optional
    
    Usage Examples:
        # Parse successful storage result from JSON
        >>> json_str = '''
        ... {
        ...     "status": "success",
        ...     "resource_name": "awscc_s3_bucket",
        ...     "provider_version": "1.53.0",
        ...     "dynamodb_stored": true,
        ...     "s3_terraform_link": "examples/resources/awscc_s3_bucket.tf",
        ...     "s3_template_link": "templates/resources/awscc_s3_bucket.md.tmpl",
        ...     "s3_analysis_link": "analysis/resource/awscc_s3_bucket.txt",
        ...     "template_generated": true,
        ...     "old_entries_deleted": 2,
        ...     "execution_time": 125.5
        ... }
        ... '''
        >>> result = StorageResult.model_validate_json(json_str)
        >>> print(result.status)
        success
        
        # Check storage success
        >>> if result.status == "success":
        ...     print(f"Stored {result.resource_name} successfully")
        Stored awscc_s3_bucket successfully
        
        # Access S3 links
        >>> print(result.s3_terraform_link)
        examples/resources/awscc_s3_bucket.tf
        >>> print(result.s3_template_link)
        templates/resources/awscc_s3_bucket.md.tmpl
        >>> print(result.s3_analysis_link)
        analysis/resource/awscc_s3_bucket.txt
        
        # Check template generation
        >>> if result.template_generated:
        ...     print("Documentation template was generated")
        Documentation template was generated
        
        # Check old entries cleanup
        >>> print(f"Deleted {result.old_entries_deleted} old entries")
        Deleted 2 old entries
        
        # Create failed storage result
        >>> failed_result = StorageResult(
        ...     status="failed",
        ...     resource_name="awscc_lambda_function",
        ...     provider_version="1.53.0",
        ...     dynamodb_stored=False,
        ...     s3_terraform_link="failed/resources/awscc_lambda_function.tf",
        ...     s3_analysis_link="analysis/resource/awscc_lambda_function.txt",
        ...     template_generated=False,
        ...     old_entries_deleted=0,
        ...     error="Failed to store in DynamoDB: Access denied"
        ... )
        >>> print(failed_result.status)
        failed
        >>> print(failed_result.error)
        Failed to store in DynamoDB: Access denied
        
        # Create minimal successful result
        >>> minimal_result = StorageResult(
        ...     status="success",
        ...     resource_name="awscc_dynamodb_table",
        ...     provider_version="1.53.0",
        ...     dynamodb_stored=True,
        ...     s3_terraform_link="examples/resources/awscc_dynamodb_table.tf",
        ...     s3_template_link="templates/resources/awscc_dynamodb_table.md.tmpl",
        ...     s3_analysis_link="analysis/resource/awscc_dynamodb_table.txt",
        ...     template_generated=True,
        ...     old_entries_deleted=0
        ... )
        >>> print(minimal_result.old_entries_deleted)
        0
        
        # Create result without template (failed pipeline)
        >>> no_template_result = StorageResult(
        ...     status="success",
        ...     resource_name="awscc_ec2_instance",
        ...     provider_version="1.53.0",
        ...     dynamodb_stored=True,
        ...     s3_terraform_link="failed/resources/awscc_ec2_instance.tf",
        ...     s3_analysis_link="analysis/resource/awscc_ec2_instance.txt",
        ...     template_generated=False,
        ...     old_entries_deleted=1
        ... )
        >>> print(no_template_result.s3_template_link)
        None
        
        # Serialize back to JSON
        >>> json_output = result.model_dump_json()
    
    Notes:
        - status="success" means storage operations completed, not that pipeline succeeded
        - dynamodb_stored=True confirms the result is tracked in DynamoDB
        - s3_terraform_link points to either examples/ (success) or failed/ (failure)
        - s3_template_link is only populated for successful pipeline runs
        - s3_analysis_link always points to the validation analysis report
        - template_generated=True only for successful pipelines
        - old_entries_deleted tracks cleanup of previous attempts
        - execution_time helps track storage operation performance
        - All S3 paths are validated against expected patterns
        - All validation happens automatically on model instantiation
        - Invalid data raises pydantic.ValidationError with detailed error messages
        - This is the final output of the TANGO pipeline
    """
    
    status: str = Field(
        description="Storage operation status",
        pattern=r"^(success|failed)$",
        examples=["success", "failed"]
    )
    
    resource_name: str = Field(
        description="AWS CloudControl resource name that was stored",
        pattern=r"^awscc_[a-z0-9_]+$",
        examples=["awscc_s3_bucket", "awscc_lambda_function", "awscc_dynamodb_table"]
    )
    
    provider_version: str = Field(
        description="AWSCC provider version used",
        pattern=r"^\d+\.\d+\.\d+$",
        examples=["1.53.0", "1.48.0", "2.0.0"]
    )
    
    dynamodb_stored: bool = Field(
        description="Whether the DynamoDB entry was successfully created"
    )
    
    s3_terraform_link: str = Field(
        description="S3 path to stored Terraform file (examples/ for success, failed/ for failure)",
        pattern=r"^(examples|failed)/resources/.+\.tf$",
        examples=[
            "examples/resources/awscc_s3_bucket.tf",
            "failed/resources/awscc_lambda_function.tf",
            "examples/resources/awscc_dynamodb_table.tf"
        ]
    )
    
    s3_template_link: Optional[str] = Field(
        default=None,
        description="S3 path to generated documentation template (only for successful pipeline runs)",
        pattern=r"^templates/resources/.+\.md\.tmpl$",
        examples=[
            None,
            "templates/resources/awscc_s3_bucket.md.tmpl",
            "templates/resources/awscc_lambda_function.md.tmpl"
        ]
    )
    
    s3_analysis_link: str = Field(
        description="S3 path to validation analysis report",
        pattern=r"^analysis/resource/.+\.txt$",
        examples=[
            "analysis/resource/awscc_s3_bucket.txt",
            "analysis/resource/awscc_lambda_function.txt",
            "analysis/resource/awscc_dynamodb_table.txt"
        ]
    )
    
    template_generated: bool = Field(
        description="Whether documentation template was generated (only for successful pipeline runs)"
    )
    
    old_entries_deleted: int = Field(
        default=0,
        description="Number of old DynamoDB entries deleted for this resource",
        ge=0,
        examples=[0, 1, 2, 5]
    )
    
    execution_time: Optional[float] = Field(
        default=None,
        description="Total execution time in seconds",
        ge=0,
        examples=[None, 45.2, 120.5, 300.0]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if storage failed",
        examples=[
            None,
            "Failed to store in DynamoDB: Access denied",
            "Failed to upload to S3: Bucket not found",
            "Template generation failed: Invalid Terraform code"
        ]
    )


# =============================================================================
# Dynamic Schema Injection Helpers
# =============================================================================

def get_model_schema_description(model_class) -> str:
    """
    Generate a human-readable schema description from a Pydantic model.
    
    This function extracts the JSON schema from a Pydantic model and formats it
    as human-readable text suitable for inclusion in agent prompts. The output
    includes field names, types, descriptions, and whether fields are optional.
    It also includes computed properties (methods decorated with @property) to
    provide a complete picture of the model's interface.
    
    This ensures that agent prompts always match the actual model structure,
    eliminating the need to manually maintain schema documentation in prompts.
    
    Args:
        model_class: A Pydantic model class (subclass of BaseModel) to generate
                    schema description for.
    
    Returns:
        str: A formatted, human-readable schema description with:
            - Model class name as header
            - Each field with its type, description, and optional marker
            - Computed properties listed separately
            - Proper indentation for readability
    
    Example Output:
        DiscoveryResult:
          - resource_name: string - AWS CloudControl resource name (e.g., awscc_s3_bucket)
          - provider_version: string - Terraform AWSCC provider version (e.g., 1.53.0)
          - error: string (optional) - Error message if discovery failed
          - is_valid: computed property
    
    Usage Examples:
        # Get schema for a single model
        >>> schema = get_model_schema_description(DiscoveryResult)
        >>> print(schema)
        DiscoveryResult:
          - resource_name: string - AWS CloudControl resource name...
          - provider_version: string - Terraform AWSCC provider version...
          - error: string (optional) - Error message if discovery failed
          - is_valid: computed property
        
        # Use in agent prompt
        >>> prompt = f'''
        ... You are an agent that returns structured data.
        ... 
        ... OUTPUT FORMAT:
        ... {get_model_schema_description(DiscoveryResult)}
        ... '''
        
        # Get schema for nested model
        >>> schema = get_model_schema_description(TerraformResult)
        >>> print(schema)
        TerraformResult:
          - status: string - Overall status of the Terraform lifecycle
          - corrected_code: string (optional) - Path to main.tf...
          - lifecycle_steps: array - Detailed results from each step
          - is_success: computed property
          - apply_succeeded: computed property
    
    Notes:
        - Automatically handles Optional types and marks them as "(optional)"
        - Extracts descriptions from Field() definitions
        - Includes pattern validation info where applicable
        - Lists computed properties (@property methods) separately
        - Works with nested models (shows "object" type for nested models)
        - Handles arrays/lists by showing "array" type
        - Output is designed to be readable by both humans and LLMs
        - Schema is generated from actual Pydantic model, ensuring accuracy
        - Changes to model automatically reflect in schema output
    """
    schema = model_class.model_json_schema()
    
    lines = [f"{model_class.__name__}:"]
    
    # Add properties (fields)
    properties = schema.get('properties', {})
    required_fields = schema.get('required', [])
    
    for prop_name, prop_info in properties.items():
        # Get type information
        prop_type = prop_info.get('type', 'any')
        
        # Handle anyOf (used for Optional types)
        if 'anyOf' in prop_info:
            types = []
            for type_option in prop_info['anyOf']:
                if 'type' in type_option:
                    types.append(type_option['type'])
                elif '$ref' in type_option:
                    # Handle nested model references
                    ref_name = type_option['$ref'].split('/')[-1]
                    types.append(ref_name)
            prop_type = ' | '.join(types) if types else 'any'
        
        # Handle $ref (nested models)
        elif '$ref' in prop_info:
            ref_name = prop_info['$ref'].split('/')[-1]
            prop_type = ref_name
        
        # Handle arrays
        elif prop_type == 'array':
            items = prop_info.get('items', {})
            if 'type' in items:
                prop_type = f"array of {items['type']}"
            elif '$ref' in items:
                ref_name = items['$ref'].split('/')[-1]
                prop_type = f"array of {ref_name}"
            else:
                prop_type = "array"
        
        # Handle objects (dicts)
        elif prop_type == 'object':
            prop_type = "object (dictionary)"
        
        # Get description
        description = prop_info.get('description', '')
        
        # Check if required
        required = prop_name in required_fields
        optional_marker = "" if required else " (optional)"
        
        # Get pattern if exists
        pattern = prop_info.get('pattern', '')
        pattern_text = f" [pattern: {pattern}]" if pattern else ""
        
        # Format line
        desc_text = f" - {description}" if description else ""
        lines.append(f"  - {prop_name}: {prop_type}{optional_marker}{pattern_text}{desc_text}")
    
    # Add computed properties (methods decorated with @property)
    computed_props = []
    for attr_name in dir(model_class):
        # Skip private attributes and built-in methods
        if attr_name.startswith('_'):
            continue
        
        try:
            attr = getattr(model_class, attr_name)
            # Check if it's a property (computed property)
            if isinstance(attr, property):
                computed_props.append(attr_name)
        except AttributeError:
            # Some attributes might not be accessible on the class
            continue
    
    if computed_props:
        lines.append("  Computed properties:")
        for prop_name in computed_props:
            lines.append(f"    - {prop_name}: computed property (read-only)")
    
    return "\n".join(lines)


def get_all_agent_schemas() -> str:
    """
    Get formatted schema descriptions for all agent output models.
    
    This function generates a comprehensive schema reference for all Pydantic
    models used in the TANGO pipeline. It's designed to be injected into the
    orchestrator system prompt to provide complete documentation of all data
    structures that agents produce and consume.
    
    The output includes schemas for all agent models in the order they appear
    in the pipeline workflow, making it easy for the orchestrator to understand
    the data flow and structure at each stage.
    
    Returns:
        str: A formatted string containing schema descriptions for all models:
            - DiscoveryResult (discovery_agent output)
            - DocumentationResult (documentation_agent output)
            - TerraformLifecycleStep (nested in TerraformResult)
            - TerraformResult (terraform_agent output)
            - ValidationResult (validation_agent output)
            - StorageRequest (storage_agent input)
            - StorageResult (storage_agent output)
            
            Each schema is numbered and separated for readability.
    
    Usage Examples:
        # Get all schemas for orchestrator prompt
        >>> schemas = get_all_agent_schemas()
        >>> print(schemas)
        1. DiscoveryResult:
          - resource_name: string - AWS CloudControl resource name...
          - provider_version: string - Terraform AWSCC provider version...
        
        2. DocumentationResult:
          - terraform_code: string - Path to the main.tf file...
        ...
        
        # Inject into orchestrator system prompt
        >>> ORCHESTRATOR_SYSTEM_PROMPT = f'''
        ... You are the TANGO Pipeline Orchestrator...
        ... 
        ... DATA MODELS:
        ... All agents return structured Pydantic models as JSON strings.
        ... Parse these using the appropriate model classes:
        ... 
        ... {get_all_agent_schemas()}
        ... 
        ... WORKFLOW:
        ... 1. Call discovery_agent → parse DiscoveryResult
        ... 2. If valid, call documentation_agent → parse DocumentationResult
        ... ...
        ... '''
        
        # Use in documentation generation
        >>> with open('docs/models.md', 'w') as f:
        ...     f.write("# TANGO Pipeline Data Models\n\n")
        ...     f.write(get_all_agent_schemas())
        
        # Verify all models are included
        >>> schemas = get_all_agent_schemas()
        >>> assert "DiscoveryResult" in schemas
        >>> assert "DocumentationResult" in schemas
        >>> assert "TerraformResult" in schemas
        >>> assert "ValidationResult" in schemas
        >>> assert "StorageRequest" in schemas
        >>> assert "StorageResult" in schemas
    
    Notes:
        - Models are listed in pipeline execution order for clarity
        - Each model is numbered for easy reference
        - Includes nested models (e.g., TerraformLifecycleStep)
        - Output is designed to be readable by both humans and LLMs
        - Automatically stays in sync with model definitions
        - Changes to any model automatically reflect in output
        - Can be used in prompts, documentation, or API references
        - Provides complete data contract documentation for the pipeline
        - Eliminates need to manually maintain schema docs in multiple places
    
    Example Output:
        1. DiscoveryResult:
          - resource_name: string - AWS CloudControl resource name...
          - provider_version: string - Terraform AWSCC provider version...
          - error: string (optional) - Error message if discovery failed
          - is_valid: computed property
        
        2. DocumentationResult:
          - terraform_code: string - Path to the main.tf file...
          - resource_name: string - Target AWS CloudControl resource name
          ...
        
        3. TerraformLifecycleStep:
          - step: string [pattern: ^(init|validate|plan|apply|destroy)$] - Step name
          - status: string [pattern: ^(success|failed|skipped)$] - Status
          ...
        
        4. TerraformResult:
          - status: string - Overall status
          - lifecycle_steps: array of TerraformLifecycleStep - Detailed results
          ...
        
        5. ValidationResult:
          - validation_result: string - Validation outcome
          ...
        
        6. StorageRequest:
          - resource_name: string - AWS CloudControl resource name
          - validation_result: ValidationResult - Complete validation data
          ...
        
        7. StorageResult:
          - status: string - Storage operation status
          ...
    """
    models = [
        DiscoveryResult,
        DocumentationResult,
        TerraformLifecycleStep,
        TerraformResult,
        ValidationResult,
        CleanupResult,
        StorageRequest,
        StorageResult
    ]
    
    descriptions = []
    for i, model in enumerate(models, 1):
        descriptions.append(f"{i}. {get_model_schema_description(model)}")
    
    return "\n\n".join(descriptions)
