# Requirements Document

## Introduction

This document specifies the requirements for implementing Pydantic data models for all function interactions in `agents/pr_tools.py`. The TANGO Multi-Agent Pipeline currently has 8 PR agent tools that use manual JSON string parsing for inputs and outputs. This implementation will add Pydantic models (similar to those in `agents/models.py`) to improve type safety, validation, and maintainability.

## Glossary

- **PR_Tools**: The module `agents/pr_tools.py` containing 8 tools for GitHub pull request creation
- **Pydantic**: Python data validation library using type annotations
- **TANGOBaseModel**: Base Pydantic model class defined in `agents/models.py` with common configuration
- **Input_Model**: Pydantic model representing validated input parameters for a tool
- **Output_Model**: Pydantic model representing validated output results from a tool
- **Tool**: A function decorated with `@tool` that performs a specific operation
- **JSON_String**: String representation of JSON data (current approach)
- **Model_Instance**: Instance of a Pydantic model class (new approach)
- **Computed_Property**: A `@property` method on a model that derives a value from other fields
- **Field_Validation**: Automatic checking of data types, patterns, and constraints by Pydantic
- **Type_Safety**: Compile-time and runtime checking of data types
- **IDE_Autocomplete**: Editor feature that suggests available fields and methods

## Requirements

### Requirement 1: Create Pydantic Models Module

**User Story:** As a developer, I want a dedicated module for PR tool models, so that model definitions are organized and reusable.

#### Acceptance Criteria

1. THE System SHALL create a new file `agents/pr_models.py` for all PR tool models
2. THE System SHALL import TANGOBaseModel from `agents/models.py` as the base class
3. THE System SHALL include comprehensive module-level docstrings explaining the purpose
4. THE System SHALL organize models by tool with clear naming conventions
5. THE System SHALL include usage examples in docstrings for each model

### Requirement 2: Define Input Models for Tool Parameters

**User Story:** As a developer, I want validated input models for all tools, so that invalid parameters are caught before execution.

#### Acceptance Criteria

1. WHEN a tool accepts JSON string parameters, THE System SHALL create a corresponding Input_Model
2. THE Input_Model SHALL inherit from TANGOBaseModel
3. THE Input_Model SHALL use Field() with descriptions, patterns, and examples
4. THE Input_Model SHALL validate required fields are present
5. THE Input_Model SHALL validate field types match expected types
6. THE Input_Model SHALL validate string patterns using regex where applicable
7. THE Input_Model SHALL provide clear error messages when validation fails
8. THE Input_Model SHALL include field-level docstrings with examples

### Requirement 3: Define Output Models for Tool Results

**User Story:** As a developer, I want validated output models for all tools, so that tool results have consistent structure and type safety.

#### Acceptance Criteria

1. WHEN a tool returns JSON string results, THE System SHALL create a corresponding Output_Model
2. THE Output_Model SHALL inherit from TANGOBaseModel
3. THE Output_Model SHALL use Field() with descriptions and examples
4. THE Output_Model SHALL include all fields returned by the tool
5. THE Output_Model SHALL mark optional fields with Optional[] type hints
6. THE Output_Model SHALL provide default values for optional fields
7. THE Output_Model SHALL validate output structure before returning
8. THE Output_Model SHALL include model-level docstrings with usage examples

### Requirement 4: Add Computed Properties for Convenience

**User Story:** As a developer, I want computed properties on output models, so that I can easily check common conditions without manual field inspection.

#### Acceptance Criteria

1. WHEN an Output_Model has a status field, THE System SHALL provide an `is_success` Computed_Property
2. THE `is_success` property SHALL return True when status equals "success" and error is None
3. WHEN an Output_Model represents resource eligibility, THE System SHALL provide an `is_valid` Computed_Property
4. THE `is_valid` property SHALL return True when resource_name is not "NONE" or "ERROR"
5. WHEN an Output_Model has multiple required fields, THE System SHALL provide convenience properties for checking completeness
6. THE Computed_Property SHALL include docstrings with examples
7. THE Computed_Property SHALL not modify model state

### Requirement 5: Implement Models for S3 Content Fetching

**User Story:** As a developer, I want models for the `fetch_resource_content` tool, so that S3 content fetching has validated inputs and outputs.

#### Acceptance Criteria

1. THE System SHALL create S3LinksInput model with s3_terraform_link, s3_template_link, and optional s3_analysis_link fields
2. THE System SHALL validate S3 link fields are non-empty strings
3. THE System SHALL create ResourceContentResult model with all output fields from fetch_resource_content
4. THE ResourceContentResult SHALL include status, resource_name, service_name, terraform_code, template, analysis_report, S3 links, provider_version, and fetch_date fields
5. THE ResourceContentResult SHALL provide is_success Computed_Property
6. THE ResourceContentResult SHALL mark optional fields (analysis_report, error) as Optional
7. THE System SHALL validate resource_name matches pattern `^awscc_[a-z0-9_]+$`
8. THE System SHALL validate provider_version matches pattern `^\d+\.\d+\.\d+$`

### Requirement 6: Implement Models for Resource Discovery

**User Story:** As a developer, I want models for the `get_next_eligible_resource` tool, so that resource discovery has validated outputs.

#### Acceptance Criteria

1. THE System SHALL create EligibleResourceResult model with resource_name, timestamp, and S3 link fields
2. THE EligibleResourceResult SHALL include optional fields for s3_terraform_link, s3_template_link, s3_analysis_link, and error
3. THE EligibleResourceResult SHALL provide is_valid Computed_Property returning True when resource_name is not "NONE" or "ERROR"
4. THE EligibleResourceResult SHALL provide has_all_files Computed_Property checking all S3 links are present
5. THE System SHALL validate resource_name allows "NONE" and "ERROR" as special values
6. THE System SHALL validate timestamp is an integer when present

### Requirement 7: Implement Models for Repository Setup

**User Story:** As a developer, I want models for the `clone_and_setup_repo` tool, so that git repository operations have validated outputs.

#### Acceptance Criteria

1. THE System SHALL create RepoSetupResult model with status, repo_path, branch_name, work_dir_name, and optional error fields
2. THE RepoSetupResult SHALL validate status matches pattern `^(success|error)$`
3. THE RepoSetupResult SHALL provide is_success Computed_Property
4. THE RepoSetupResult SHALL mark repo_path, branch_name, and work_dir_name as optional (None on error)
5. THE System SHALL validate branch_name follows pattern `^d-awscc_[a-z0-9_]+$` when present

### Requirement 8: Implement Models for File Placement

**User Story:** As a developer, I want models for the `place_files_in_structure` tool, so that file operations have validated inputs and outputs.

#### Acceptance Criteria

1. THE System SHALL create FileContentInput model with terraform_code, template, and service_name fields
2. THE FileContentInput SHALL validate terraform_code and template have min_length=1
3. THE FileContentInput SHALL validate service_name matches pattern `^[a-z0-9_]+$`
4. THE System SHALL create FilePlacementResult model with status, files_created list, resource_name, service_name, validation, and optional error fields
5. THE FilePlacementResult SHALL provide is_success Computed_Property checking status="success" and validation="passed"
6. THE FilePlacementResult SHALL default files_created to empty list

### Requirement 9: Implement Models for HashiCorp Validation

**User Story:** As a developer, I want models for the `run_hashicorp_validation` tool, so that validation command results are structured and type-safe.

#### Acceptance Criteria

1. THE System SHALL create ValidationCommandResult model with command, returncode, success, stdout, stderr, and optional error fields
2. THE ValidationCommandResult SHALL validate success is a boolean
3. THE System SHALL create HashiCorpValidationResult model with status, resource_name, commands list, docs_generated, docs_file_path, docs_file_size, error, and error_details fields
4. THE HashiCorpValidationResult SHALL use List[ValidationCommandResult] for commands field
5. THE HashiCorpValidationResult SHALL provide is_success Computed_Property checking status="success" and docs_generated=True
6. THE HashiCorpValidationResult SHALL provide all_commands_succeeded Computed_Property checking all commands have success=True
7. THE HashiCorpValidationResult SHALL default commands to empty list

### Requirement 10: Implement Models for GitHub PR Creation

**User Story:** As a developer, I want models for the `create_github_pr` tool, so that PR creation has validated inputs and outputs.

#### Acceptance Criteria

1. THE System SHALL create PRContentInput model with service_name, provider_version, fetch_date, and optional s3_analysis_link and analysis_report fields
2. THE PRContentInput SHALL validate provider_version matches pattern `^\d+\.\d+\.\d+$`
3. THE System SHALL create GitHubPRResult model with status, pr_url, pr_number, pr_title, resource_name, branch_name, and optional error fields
4. THE GitHubPRResult SHALL provide is_success Computed_Property checking status="success" and pr_url is not None
5. THE GitHubPRResult SHALL validate status matches pattern `^(success|error)$`
6. THE GitHubPRResult SHALL mark pr_url, pr_number, and pr_title as optional (None on error)

### Requirement 11: Implement Models for PR Status Updates

**User Story:** As a developer, I want models for the `update_pr_status` tool, so that DynamoDB updates have validated inputs and outputs.

#### Acceptance Criteria

1. THE System SHALL create PRStatusInput model with resource_name, pr_url, and status fields
2. THE PRStatusInput SHALL validate resource_name matches pattern `^awscc_[a-z0-9_]+$`
3. THE PRStatusInput SHALL validate status matches pattern `^(created|failed)$`
4. THE PRStatusInput SHALL use field_validator to ensure status is only "created" or "failed"
5. THE PRStatusInput SHALL mark pr_url as optional
6. THE System SHALL create PRStatusUpdateResult model with status, resource_name, timestamp, pr_status, pr_created_at, github_pr_url, message, and optional error fields
7. THE PRStatusUpdateResult SHALL provide is_success Computed_Property
8. THE PRStatusUpdateResult SHALL mark optional fields appropriately

### Requirement 12: Implement Models for Git Operations

**User Story:** As a developer, I want models for the `git_commit_and_push` tool, so that git operations have validated outputs.

#### Acceptance Criteria

1. THE System SHALL create GitCommitPushResult model with status, commit_hash, commit_hash_short, branch_name, resource_name, files_changed, commit_message, and optional error fields
2. THE GitCommitPushResult SHALL validate status matches pattern `^(success|error)$`
3. THE GitCommitPushResult SHALL provide is_success Computed_Property checking status="success" and commit_hash is not None
4. THE GitCommitPushResult SHALL mark commit_hash, commit_hash_short, and other success fields as optional (None on error)
5. THE GitCommitPushResult SHALL validate files_changed is an integer when present

### Requirement 13: Update Tools to Use Models

**User Story:** As a developer, I want all tools updated to use Pydantic models, so that type safety and validation are enforced throughout the codebase.

#### Acceptance Criteria

1. WHEN a tool is updated, THE System SHALL change function signature to accept Model_Instance instead of JSON_String for complex inputs
2. WHEN a tool is updated, THE System SHALL change return type to Output_Model instead of JSON_String
3. WHEN a tool is updated, THE System SHALL remove manual json.loads() calls for inputs
4. WHEN a tool is updated, THE System SHALL remove manual json.dumps() calls for outputs
5. WHEN a tool is updated, THE System SHALL use model field access instead of dict.get()
6. WHEN a tool is updated, THE System SHALL construct Output_Model instances with validated data
7. WHEN a tool is updated, THE System SHALL let Pydantic handle validation errors
8. THE System SHALL update one tool at a time to minimize risk

### Requirement 14: Update Calling Code

**User Story:** As a developer, I want calling code updated to use models, so that the entire PR workflow benefits from type safety.

#### Acceptance Criteria

1. WHEN calling code is updated, THE System SHALL construct Input_Model instances instead of JSON strings
2. WHEN calling code is updated, THE System SHALL receive Output_Model instances instead of JSON strings
3. WHEN calling code is updated, THE System SHALL use Computed_Property methods for condition checking
4. WHEN calling code is updated, THE System SHALL use direct field access instead of dict.get()
5. WHEN calling code is updated, THE System SHALL remove manual JSON parsing
6. THE System SHALL update `agents/pr_agent.py` to use all new models
7. THE System SHALL ensure backward compatibility during transition if needed

### Requirement 15: Maintain Consistency with Existing Patterns

**User Story:** As a developer, I want PR models to follow existing patterns, so that the codebase remains consistent and maintainable.

#### Acceptance Criteria

1. THE System SHALL use the same TANGOBaseModel base class as `agents/models.py`
2. THE System SHALL follow the same Field() usage patterns as existing models
3. THE System SHALL use the same docstring format as existing models
4. THE System SHALL use the same Computed_Property patterns as existing models
5. THE System SHALL use the same validation patterns as existing models
6. THE System SHALL include examples in Field() definitions like existing models
7. THE System SHALL organize models with clear section comments like existing models

### Requirement 16: Provide Comprehensive Documentation

**User Story:** As a developer, I want comprehensive documentation for all models, so that I can understand how to use them correctly.

#### Acceptance Criteria

1. THE System SHALL include module-level docstrings explaining the purpose of pr_models.py
2. THE System SHALL include class-level docstrings for each model with usage examples
3. THE System SHALL include field-level descriptions using Field(description=...)
4. THE System SHALL include examples for each field using Field(examples=[...])
5. THE System SHALL include docstrings for all Computed_Property methods
6. THE System SHALL include usage examples showing model instantiation and access patterns
7. THE System SHALL document validation rules and error messages

### Requirement 17: Add Comprehensive Tests

**User Story:** As a developer, I want comprehensive tests for all models, so that I can be confident they work correctly.

#### Acceptance Criteria

1. THE System SHALL create test file `tests/test_pr_models.py` for model tests
2. THE System SHALL test valid model instantiation for each model
3. THE System SHALL test invalid model instantiation raises ValidationError
4. THE System SHALL test field validation rules (patterns, min_length, etc.)
5. THE System SHALL test Computed_Property methods return correct values
6. THE System SHALL test optional fields default to correct values
7. THE System SHALL test model serialization to JSON
8. THE System SHALL test model deserialization from JSON
9. THE System SHALL achieve 100% test coverage for all models

### Requirement 18: Handle Errors Gracefully

**User Story:** As a developer, I want clear error messages from model validation, so that I can quickly identify and fix issues.

#### Acceptance Criteria

1. WHEN model validation fails, THE System SHALL provide detailed error messages
2. THE error message SHALL indicate which field failed validation
3. THE error message SHALL indicate why validation failed
4. THE error message SHALL include the invalid value that was provided
5. THE System SHALL catch Pydantic ValidationError and provide context
6. THE System SHALL not expose internal implementation details in error messages
7. THE System SHALL log validation errors for debugging

### Requirement 19: Optimize Performance

**User Story:** As a developer, I want model validation to have minimal performance impact, so that the PR workflow remains fast.

#### Acceptance Criteria

1. THE System SHALL use Pydantic's optimized validation
2. THE System SHALL not perform unnecessary validation passes
3. THE System SHALL reuse model instances where appropriate
4. THE System SHALL not add significant overhead compared to manual JSON parsing
5. THE System SHALL validate only when necessary (on instantiation and assignment)
6. THE System SHALL use Pydantic's built-in caching where applicable
