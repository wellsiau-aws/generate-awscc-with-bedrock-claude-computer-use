# Implementation Plan: PR Tools Pydantic Models

## Overview

This plan implements Pydantic data models for all function interactions in `agents/pr_tools.py`. The implementation follows a phased approach: create models first, then update tools one at a time, then update calling code, and finally add comprehensive tests. This minimizes risk and ensures each step can be validated before proceeding.

## Tasks

- [x] 1. Create pr_models.py module with base structure
  - Create `agents/pr_models.py` file
  - Add module-level docstring explaining purpose
  - Import TANGOBaseModel from agents/models.py
  - Import required types (Optional, List, Dict, Field, field_validator)
  - Add section comments for organizing models
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 15.1, 15.7_

- [ ]* 1.1 Write property test for TANGOBaseModel inheritance
  - **Property: All PR models inherit from TANGOBaseModel**
  - **Validates: Requirements 1.2, 15.1**

- [x] 2. Implement input models for tool parameters
  - [x] 2.1 Create S3LinksInput model
    - Define S3LinksInput class inheriting from TANGOBaseModel
    - Add s3_terraform_link field with min_length=1 validation
    - Add s3_template_link field with min_length=1 validation
    - Add optional s3_analysis_link field
    - Add comprehensive docstring with usage examples
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2_
  
  - [ ]* 2.2 Write property test for S3LinksInput validation
    - **Property 4: Non-Empty String Validation**
    - **Validates: Requirements 5.2**
  
  - [x] 2.3 Create FileContentInput model
    - Define FileContentInput class inheriting from TANGOBaseModel
    - Add terraform_code field with min_length=1 validation
    - Add template field with min_length=1 validation
    - Add service_name field with pattern validation `^[a-z0-9_]+$`
    - Add comprehensive docstring with usage examples
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 8.1, 8.2, 8.3_
  
  - [ ]* 2.4 Write property test for FileContentInput pattern validation
    - **Property 3: Pattern Validation**
    - **Validates: Requirements 2.6, 8.3**
  
  - [x] 2.5 Create PRContentInput model
    - Define PRContentInput class inheriting from TANGOBaseModel
    - Add service_name field
    - Add provider_version field with pattern validation `^\d+\.\d+\.\d+$`
    - Add fetch_date field
    - Add optional s3_analysis_link field
    - Add optional analysis_report field
    - Add comprehensive docstring with usage examples
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 10.1, 10.2_
  
  - [ ]* 2.6 Write property test for provider_version pattern validation
    - **Property 3: Pattern Validation (provider_version)**
    - **Validates: Requirements 5.8, 10.2**
  
  - [x] 2.7 Create PRStatusInput model
    - Define PRStatusInput class inheriting from TANGOBaseModel
    - Add resource_name field with pattern validation `^awscc_[a-z0-9_]+$`
    - Add optional pr_url field
    - Add status field with pattern validation `^(created|failed)$`
    - Add field_validator for status to ensure only "created" or "failed"
    - Add comprehensive docstring with usage examples
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [ ]* 2.8 Write property test for resource_name pattern validation
    - **Property 3: Pattern Validation (resource_name)**
    - **Validates: Requirements 5.7, 11.2**

- [x] 3. Implement output models for tool results
  - [x] 3.1 Create ResourceContentResult model
    - Define ResourceContentResult class inheriting from TANGOBaseModel
    - Add status field with pattern validation `^(success|error)$`
    - Add resource_name, service_name, provider_version, fetch_date fields
    - Add optional terraform_code, template, analysis_report fields
    - Add optional s3_terraform_link, s3_template_link, s3_analysis_link fields
    - Add optional error field
    - Add is_success computed property
    - Add comprehensive docstring with usage examples
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 5.3, 5.4, 5.5, 5.6_
  
  - [ ]* 3.2 Write property test for is_success computed property
    - **Property 7: Success Property Correctness**
    - **Validates: Requirements 4.1, 4.2, 5.5**
  
  - [x] 3.3 Create EligibleResourceResult model
    - Define EligibleResourceResult class inheriting from TANGOBaseModel
    - Add resource_name field (allows "NONE" and "ERROR" special values)
    - Add optional timestamp field (integer type)
    - Add optional s3_terraform_link, s3_template_link, s3_analysis_link fields
    - Add optional error field
    - Add is_valid computed property
    - Add has_all_files computed property
    - Add comprehensive docstring with usage examples
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.3, 4.4, 4.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  
  - [ ]* 3.4 Write unit tests for EligibleResourceResult special values
    - Test resource_name="NONE" is accepted
    - Test resource_name="ERROR" is accepted
    - Test is_valid returns False for "NONE" and "ERROR"
    - _Requirements: 6.5_
  
  - [ ]* 3.5 Write property test for integer type validation
    - **Property 10: Integer Type Validation**
    - **Validates: Requirements 6.6**
  
  - [x] 3.6 Create RepoSetupResult model
    - Define RepoSetupResult class inheriting from TANGOBaseModel
    - Add status field with pattern validation `^(success|error)$`
    - Add optional repo_path, branch_name, work_dir_name fields
    - Add optional error field
    - Add is_success computed property
    - Add comprehensive docstring with usage examples
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 7.1, 7.2, 7.3, 7.4_
  
  - [x] 3.7 Create FilePlacementResult model
    - Define FilePlacementResult class inheriting from TANGOBaseModel
    - Add status field with pattern validation `^(success|error)$`
    - Add files_created field (List[str] with default_factory=list)
    - Add optional resource_name, service_name, validation fields
    - Add optional error field
    - Add is_success computed property (checks status="success" and validation="passed")
    - Add comprehensive docstring with usage examples
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 8.4, 8.5_
  
  - [x] 3.8 Create ValidationCommandResult model
    - Define ValidationCommandResult class inheriting from TANGOBaseModel
    - Add command field (string)
    - Add optional returncode field (integer)
    - Add success field (boolean)
    - Add optional stdout, stderr, error fields
    - Add comprehensive docstring with usage examples
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 9.1, 9.2_
  
  - [x] 3.9 Create HashiCorpValidationResult model
    - Define HashiCorpValidationResult class inheriting from TANGOBaseModel
    - Add status field with pattern validation `^(success|error)$`
    - Add resource_name field
    - Add commands field (List[ValidationCommandResult] with default_factory=list)
    - Add optional docs_generated (bool), docs_file_path, docs_file_size fields
    - Add optional error, error_details fields
    - Add is_success computed property (checks status="success" and docs_generated=True)
    - Add all_commands_succeeded computed property
    - Add comprehensive docstring with usage examples
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 9.3, 9.4, 9.5, 9.6, 9.7_
  
  - [ ]* 3.10 Write property test for computed property idempotence
    - **Property 8: Computed Property Idempotence**
    - **Validates: Requirements 4.7**
  
  - [x] 3.11 Create GitHubPRResult model
    - Define GitHubPRResult class inheriting from TANGOBaseModel
    - Add status field with pattern validation `^(success|error)$`
    - Add optional pr_url, pr_number, pr_title fields
    - Add optional resource_name, branch_name fields
    - Add optional error field
    - Add is_success computed property (checks status="success" and pr_url is not None)
    - Add comprehensive docstring with usage examples
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 10.3, 10.4, 10.5, 10.6_
  
  - [x] 3.12 Create PRStatusUpdateResult model
    - Define PRStatusUpdateResult class inheriting from TANGOBaseModel
    - Add status field with pattern validation `^(success|error)$`
    - Add resource_name field
    - Add optional timestamp (int), pr_status, pr_created_at fields
    - Add optional github_pr_url, message, error fields
    - Add is_success computed property
    - Add comprehensive docstring with usage examples
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 11.6, 11.7, 11.8_
  
  - [x] 3.13 Create GitCommitPushResult model
    - Define GitCommitPushResult class inheriting from TANGOBaseModel
    - Add status field with pattern validation `^(success|error)$`
    - Add optional commit_hash, commit_hash_short, branch_name fields
    - Add optional resource_name, files_changed (int), commit_message fields
    - Add optional error field
    - Add is_success computed property (checks status="success" and commit_hash is not None)
    - Add comprehensive docstring with usage examples
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 4. Checkpoint - Verify all models are created
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update fetch_resource_content tool
  - [x] 5.1 Update function signature to accept Optional[S3LinksInput]
    - Change s3_links_json parameter to s3_links: Optional[S3LinksInput]
    - Update return type to ResourceContentResult
    - _Requirements: 13.1, 13.2_
  
  - [x] 5.2 Remove manual JSON parsing for s3_links
    - Remove json.loads(s3_links_json) call
    - Access fields directly from s3_links model (e.g., s3_links.s3_terraform_link)
    - _Requirements: 13.3, 13.5_
  
  - [x] 5.3 Update result construction to use ResourceContentResult
    - Replace json.dumps(result) with ResourceContentResult instantiation
    - Let Pydantic validate all fields automatically
    - _Requirements: 13.4, 13.6, 13.7_
  
  - [x] 5.4 Update error handling to return ResourceContentResult
    - Catch exceptions and return ResourceContentResult with status="error"
    - Include error message in error field
    - _Requirements: 13.6, 13.7_
  
  - [ ]* 5.5 Write integration test for fetch_resource_content with models
    - Test valid S3LinksInput produces ResourceContentResult
    - Test invalid input raises ValidationError
    - Test error cases return ResourceContentResult with error
    - _Requirements: 13.1, 13.2, 13.6_

- [x] 6. Update get_next_eligible_resource tool
  - [x] 6.1 Update function signature to return EligibleResourceResult
    - Change return type from str to EligibleResourceResult
    - _Requirements: 13.2_
  
  - [x] 6.2 Update result construction to use EligibleResourceResult
    - Replace json.dumps(result) with EligibleResourceResult instantiation
    - Handle "NONE" and "ERROR" special cases
    - _Requirements: 13.4, 13.6_
  
  - [x] 6.3 Update error handling to return EligibleResourceResult
    - Return EligibleResourceResult with resource_name="ERROR" and error message
    - _Requirements: 13.6, 13.7_
  
  - [ ]* 6.4 Write integration test for get_next_eligible_resource with models
    - Test successful case returns EligibleResourceResult with is_valid=True
    - Test no resources case returns resource_name="NONE"
    - Test error case returns resource_name="ERROR"
    - _Requirements: 13.2, 13.6_

- [x] 7. Update clone_and_setup_repo tool
  - [x] 7.1 Update function signature to return RepoSetupResult
    - Change return type from str to RepoSetupResult
    - _Requirements: 13.2_
  
  - [x] 7.2 Update result construction to use RepoSetupResult
    - Replace json.dumps(result) with RepoSetupResult instantiation
    - _Requirements: 13.4, 13.6_
  
  - [x] 7.3 Update error handling to return RepoSetupResult
    - Return RepoSetupResult with status="error" and error message
    - _Requirements: 13.6, 13.7_
  
  - [ ]* 7.4 Write integration test for clone_and_setup_repo with models
    - Test successful case returns RepoSetupResult with is_success=True
    - Test error cases return RepoSetupResult with error
    - _Requirements: 13.2, 13.6_

- [x] 8. Update place_files_in_structure tool
  - [x] 8.1 Update function signature to accept FileContentInput
    - Change content_json parameter to content: FileContentInput
    - Change return type to FilePlacementResult
    - _Requirements: 13.1, 13.2_
  
  - [x] 8.2 Remove manual JSON parsing for content
    - Remove json.loads(content_json) call
    - Access fields directly from content model
    - _Requirements: 13.3, 13.5_
  
  - [x] 8.3 Update result construction to use FilePlacementResult
    - Replace json.dumps(result) with FilePlacementResult instantiation
    - _Requirements: 13.4, 13.6_
  
  - [x] 8.4 Update error handling to return FilePlacementResult
    - Return FilePlacementResult with status="error" and error message
    - _Requirements: 13.6, 13.7_
  
  - [ ]* 8.5 Write integration test for place_files_in_structure with models
    - Test valid FileContentInput produces FilePlacementResult
    - Test invalid input raises ValidationError
    - Test error cases return FilePlacementResult with error
    - _Requirements: 13.1, 13.2, 13.6_

- [x] 9. Update run_hashicorp_validation tool
  - [x] 9.1 Update function signature to return HashiCorpValidationResult
    - Change return type from str to HashiCorpValidationResult
    - _Requirements: 13.2_
  
  - [x] 9.2 Update command result construction to use ValidationCommandResult
    - Replace dict construction with ValidationCommandResult instantiation
    - Build list of ValidationCommandResult objects
    - _Requirements: 13.6_
  
  - [x] 9.3 Update result construction to use HashiCorpValidationResult
    - Replace json.dumps(result) with HashiCorpValidationResult instantiation
    - Include commands list with ValidationCommandResult objects
    - _Requirements: 13.4, 13.6_
  
  - [x] 9.4 Update error handling to return HashiCorpValidationResult
    - Return HashiCorpValidationResult with status="error" and error message
    - _Requirements: 13.6, 13.7_
  
  - [ ]* 9.5 Write integration test for run_hashicorp_validation with models
    - Test successful case returns HashiCorpValidationResult with is_success=True
    - Test all_commands_succeeded property works correctly
    - Test error cases return HashiCorpValidationResult with error
    - _Requirements: 13.2, 13.6_

- [x] 10. Update create_github_pr tool
  - [x] 10.1 Update function signature to accept PRContentInput
    - Change content_json parameter to content: PRContentInput
    - Change return type to GitHubPRResult
    - _Requirements: 13.1, 13.2_
  
  - [x] 10.2 Remove manual JSON parsing for content
    - Remove json.loads(content_json) call
    - Access fields directly from content model
    - Update _generate_pr_description to accept PRContentInput
    - _Requirements: 13.3, 13.5_
  
  - [x] 10.3 Update result construction to use GitHubPRResult
    - Replace json.dumps(result) with GitHubPRResult instantiation
    - _Requirements: 13.4, 13.6_
  
  - [x] 10.4 Update error handling to return GitHubPRResult
    - Return GitHubPRResult with status="error" and error message
    - _Requirements: 13.6, 13.7_
  
  - [ ]* 10.5 Write integration test for create_github_pr with models
    - Test valid PRContentInput produces GitHubPRResult
    - Test invalid input raises ValidationError
    - Test error cases return GitHubPRResult with error
    - _Requirements: 13.1, 13.2, 13.6_

- [x] 11. Update update_pr_status tool
  - [x] 11.1 Update function signature to accept PRStatusInput
    - Change individual parameters to input: PRStatusInput
    - Change return type to PRStatusUpdateResult
    - _Requirements: 13.1, 13.2_
  
  - [x] 11.2 Remove manual validation for status
    - Remove manual status validation (Pydantic handles it)
    - Access fields directly from input model
    - _Requirements: 13.5, 13.6_
  
  - [x] 11.3 Update result construction to use PRStatusUpdateResult
    - Replace json.dumps(result) with PRStatusUpdateResult instantiation
    - _Requirements: 13.4, 13.6_
  
  - [x] 11.4 Update error handling to return PRStatusUpdateResult
    - Return PRStatusUpdateResult with status="error" and error message
    - _Requirements: 13.6, 13.7_
  
  - [ ]* 11.5 Write integration test for update_pr_status with models
    - Test valid PRStatusInput produces PRStatusUpdateResult
    - Test invalid status raises ValidationError
    - Test error cases return PRStatusUpdateResult with error
    - _Requirements: 13.1, 13.2, 13.6_

- [x] 12. Update git_commit_and_push tool
  - [x] 12.1 Update function signature to return GitCommitPushResult
    - Change return type from str to GitCommitPushResult
    - _Requirements: 13.2_
  
  - [x] 12.2 Update result construction to use GitCommitPushResult
    - Replace json.dumps(result) with GitCommitPushResult instantiation
    - _Requirements: 13.4, 13.6_
  
  - [x] 12.3 Update error handling to return GitCommitPushResult
    - Return GitCommitPushResult with status="error" and error message
    - _Requirements: 13.6, 13.7_
  
  - [ ]* 12.4 Write integration test for git_commit_and_push with models
    - Test successful case returns GitCommitPushResult with is_success=True
    - Test error cases return GitCommitPushResult with error
    - _Requirements: 13.2, 13.6_

- [ ]* 13. Checkpoint - Verify all tools are updated
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Update pr_agent.py to use models
  - [x] 14.1 Update imports to include all PR models
    - Import all input and output models from agents.pr_models
    - _Requirements: 14.1_
  
  - [x] 14.2 Update tool calls to construct input models
    - Replace JSON string construction with model instantiation
    - Pass model instances to tools instead of JSON strings
    - _Requirements: 14.1, 14.2_
  
  - [x] 14.3 Update result handling to use model properties
    - Replace json.loads() calls with direct model access
    - Use computed properties (is_success, is_valid) for condition checking
    - Use direct field access instead of dict.get()
    - _Requirements: 14.2, 14.3, 14.4, 14.5_
  
  - [x] 14.4 Update error handling to use model error fields
    - Access error field directly from result models
    - Use is_success property for success checking
    - _Requirements: 14.3, 14.4_
  
  - [ ]* 14.5 Write integration test for full PR workflow with models
    - Test end-to-end PR creation workflow
    - Verify all tools work together with models
    - Test error propagation through workflow
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

- [ ] 15. Add comprehensive unit tests for models
  - [ ] 15.1 Create tests/test_pr_models.py file
    - Set up test file structure
    - Import all models and pytest
    - _Requirements: 17.1_
  
  - [ ] 15.2 Add unit tests for S3LinksInput
    - Test valid instantiation
    - Test empty string validation
    - Test optional field defaults
    - _Requirements: 17.2, 17.3, 17.4, 17.6_
  
  - [ ] 15.3 Add unit tests for FileContentInput
    - Test valid instantiation
    - Test pattern validation for service_name
    - Test min_length validation
    - _Requirements: 17.2, 17.3, 17.4_
  
  - [ ] 15.4 Add unit tests for PRContentInput
    - Test valid instantiation
    - Test provider_version pattern validation
    - Test optional field defaults
    - _Requirements: 17.2, 17.3, 17.4, 17.6_
  
  - [ ] 15.5 Add unit tests for PRStatusInput
    - Test valid instantiation
    - Test resource_name pattern validation
    - Test status field_validator
    - Test invalid status values
    - _Requirements: 17.2, 17.3, 17.4_
  
  - [ ] 15.6 Add unit tests for ResourceContentResult
    - Test valid instantiation
    - Test is_success property for success case
    - Test is_success property for error case
    - Test optional field defaults
    - _Requirements: 17.2, 17.5, 17.6_
  
  - [ ] 15.7 Add unit tests for EligibleResourceResult
    - Test valid instantiation
    - Test is_valid property for valid resource
    - Test is_valid property for "NONE" and "ERROR"
    - Test has_all_files property
    - Test special value acceptance
    - _Requirements: 17.2, 17.5, 17.6_
  
  - [ ] 15.8 Add unit tests for RepoSetupResult
    - Test valid instantiation
    - Test is_success property
    - Test optional field defaults
    - _Requirements: 17.2, 17.5, 17.6_
  
  - [ ] 15.9 Add unit tests for FilePlacementResult
    - Test valid instantiation
    - Test is_success property (checks validation="passed")
    - Test files_created default to empty list
    - _Requirements: 17.2, 17.5, 17.6_
  
  - [ ] 15.10 Add unit tests for ValidationCommandResult
    - Test valid instantiation
    - Test optional field defaults
    - _Requirements: 17.2, 17.6_
  
  - [ ] 15.11 Add unit tests for HashiCorpValidationResult
    - Test valid instantiation
    - Test is_success property
    - Test all_commands_succeeded property
    - Test commands default to empty list
    - _Requirements: 17.2, 17.5, 17.6_
  
  - [ ] 15.12 Add unit tests for GitHubPRResult
    - Test valid instantiation
    - Test is_success property (checks pr_url is not None)
    - Test optional field defaults
    - _Requirements: 17.2, 17.5, 17.6_
  
  - [ ] 15.13 Add unit tests for PRStatusUpdateResult
    - Test valid instantiation
    - Test is_success property
    - Test optional field defaults
    - _Requirements: 17.2, 17.5, 17.6_
  
  - [ ] 15.14 Add unit tests for GitCommitPushResult
    - Test valid instantiation
    - Test is_success property (checks commit_hash is not None)
    - Test optional field defaults
    - _Requirements: 17.2, 17.5, 17.6_

- [ ] 16. Add property-based tests for universal properties
  - [ ] 16.1 Set up hypothesis testing framework
    - Install hypothesis library if not present
    - Create test strategies for generating test data
    - _Requirements: 17.1_
  
  - [ ]* 16.2 Write property test for required field validation (Property 1)
    - Test all models reject missing required fields
    - Run with 100+ iterations
    - Tag with feature name and property number
    - _Requirements: 2.4, 17.4_
  
  - [ ]* 16.3 Write property test for type validation (Property 2)
    - Test all models reject wrong types
    - Run with 100+ iterations
    - Tag with feature name and property number
    - _Requirements: 2.5, 17.4_
  
  - [ ]* 16.4 Write property test for pattern validation (Property 3)
    - Test all pattern-validated fields reject invalid patterns
    - Run with 100+ iterations
    - Tag with feature name and property number
    - _Requirements: 2.6, 5.7, 5.8, 17.4_
  
  - [ ]* 16.5 Write property test for non-empty string validation (Property 4)
    - Test all min_length=1 fields reject empty strings
    - Run with 100+ iterations
    - Tag with feature name and property number
    - _Requirements: 5.2, 17.4_
  
  - [ ]* 16.6 Write property test for optional field defaults (Property 5)
    - Test all optional fields get correct defaults
    - Run with 100+ iterations
    - Tag with feature name and property number
    - _Requirements: 3.6, 17.6_
  
  - [ ]* 16.7 Write property test for output structure validation (Property 6)
    - Test all output models validate structure
    - Run with 100+ iterations
    - Tag with feature name and property number
    - _Requirements: 3.7_
  
  - [ ]* 16.8 Write property test for success property correctness (Property 7)
    - Test is_success property logic across all models
    - Run with 100+ iterations
    - Tag with feature name and property number
    - _Requirements: 4.1, 4.2, 5.5_
  
  - [ ]* 16.9 Write property test for computed property idempotence (Property 8)
    - Test all computed properties are idempotent
    - Run with 100+ iterations
    - Tag with feature name and property number
    - _Requirements: 4.7_
  
  - [ ]* 16.10 Write property test for JSON serialization round-trip (Property 9)
    - Test all models support JSON round-trip
    - Run with 100+ iterations
    - Tag with feature name and property number
    - _Requirements: 17.7, 17.8_
  
  - [ ]* 16.11 Write property test for integer type validation (Property 10)
    - Test all integer fields reject non-integers
    - Run with 100+ iterations
    - Tag with feature name and property number
    - _Requirements: 6.6_

- [ ] 17. Final checkpoint - Run all tests and verify coverage
  - Run all unit tests and property tests
  - Verify test coverage meets requirements
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test tasks that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests are tagged with feature name and property number for documentation
- Tools are updated one at a time to minimize risk
- Checkpoints ensure incremental validation
- All models follow existing patterns from agents/models.py
