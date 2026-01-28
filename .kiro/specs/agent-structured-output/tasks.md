# Implementation Plan: Agent Structured Output

## Overview

This implementation adds Pydantic structured output to all TANGO agents, replacing manual JSON parsing with type-safe models. The system uses dynamic schema injection to avoid duplicating model definitions in prompts, maintains backward compatibility during migration, and provides comprehensive validation with computed properties.

## Tasks

- [x] 1. Create base model infrastructure
  - Create `agents/models.py` in agents directory
  - Implement `TANGOBaseModel` base class with common Pydantic configuration
  - Add proper module docstring and imports
  - Verify imports work without errors
  - _Requirements: All model requirements depend on this foundation_

- [ ] 2. Implement agent data models
  - [x] 2.1 Create DiscoveryResult model
    - Define class with resource_name, provider_version, error, fields
    - Add pattern validation for resource_name (^awscc_[a-z0-9_]+$)
    - Add pattern validation for provider_version (^\d+\.\d+\.\d+$)
    - Implement `is_valid` computed property
    - Add comprehensive docstring with usage examples
    - _Requirements: Discovery agent output structure_
  
  - [x] 2.2 Create DocumentationResult model
    - Define class with terraform_code, resource_name, provider_version, workspace_initialized, supplemental_resources, supplemental_strategy, error fields
    - Add validation for non-empty terraform_code
    - Implement `is_success` computed property
    - Add comprehensive docstring
    - _Requirements: Documentation agent output structure_
  
  - [x] 2.3 Create TerraformResult models
    - Define TerraformLifecycleStep nested model (step, status, output, error)
    - Define TerraformResult with lifecycle_steps, corrected_code, resource_name, provider_version, error fields
    - Add pattern validation for step names and statuses
    - Implement `is_success` and `apply_succeeded` computed properties
    - Add comprehensive docstrings
    - _Requirements: Terraform agent output structure_
  
  - [x] 2.4 Create ValidationResult model
    - Define class with terraform_steps, s3_analysis_path, resource_name, provider_version, error fields
    - Add pattern validation for s3_analysis_path
    - Implement `is_success` and `all_steps_passed` computed properties
    - Add comprehensive docstring
    - _Requirements: Validation agent output structure_
  
  - [x] 2.5 Create Storage models
    - Define StorageRequest with nested ValidationResult and TerraformResult
    - Define StorageResult with dynamodb_status, s3_status, execution_time, old_entries_deleted fields
    - Add pattern validation for S3 paths
    - Add validation for non-negative values
    - Add comprehensive docstrings
    - _Requirements: Storage agent input/output structure_

- [x] 3. Add dynamic schema injection helpers
  - Implement `get_model_schema_description(model_class)` function
  - Extract JSON schema from Pydantic model
  - Format schema as human-readable text with field types, descriptions, optional markers
  - Include computed properties (@property methods) in output
  - Implement `get_all_agent_schemas()` to combine all model schemas
  - Test schema generation with all model classes
  - Verify output is readable and matches model definitions
  - _Requirements: Avoid schema duplication in prompts_

- [x] 4. Create comprehensive model tests
  - Create `tests/test_models.py` file
  - Add tests for valid data for each model
  - Add tests for invalid data (pattern violations, required fields)
  - Add tests for computed properties (is_valid, is_success, etc.)
  - Add tests for nested model validation (StorageRequest)
  - Add tests for JSON serialization/deserialization round-trips
  - Verify 90%+ code coverage for models.py
  - _Requirements: Ensure model reliability_

- [x] 5. Checkpoint - Verify models work independently
  - Run model tests and verify all pass
  - Test schema generation functions manually
  - Verify model validation catches expected errors
  - Review model docstrings for completeness

- [ ] 6. Update agents with structured output
  - [x] 6.1 Update discovery_agent
    - Import DiscoveryResult and get_model_schema_description from agents.models
    - Generate schema dynamically: `DISCOVERY_RESULT_SCHEMA = get_model_schema_description(DiscoveryResult)`
    - Inject schema into system prompt using f-string
    - Add `structured_output_model=DiscoveryResult` to Agent initialization
    - Access structured output via `result.structured_output`
    - Return `model_dump_json()` for backward compatibility
    - Use `is_valid` property for validation logic
    - Add integration test
    - _Requirements: Discovery agent structured output with dynamic schema_
  
  - [x] 6.2 Update documentation_agent
    - Import DocumentationResult and get_model_schema_description from agents.models
    - Generate schema dynamically: `DOCUMENTATION_RESULT_SCHEMA = get_model_schema_description(DocumentationResult)`
    - Inject schema into system prompt using f-string
    - Add `structured_output_model=DocumentationResult` to Agent
    - Access via `result.structured_output`
    - Return `model_dump_json()` for backward compatibility
    - Use `is_success` property for validation
    - Track workspace_initialized status correctly
    - Add integration test
    - _Requirements: Documentation agent structured output with dynamic schema_
  
  - [x] 6.3 Update terraform_agent
    - Import TerraformResult, TerraformLifecycleStep, and get_model_schema_description from agents.models
    - Generate schema dynamically: `TERRAFORM_RESULT_SCHEMA = get_model_schema_description(TerraformResult)`
    - Inject schema into system prompt using f-string
    - Add `structured_output_model=TerraformResult` to Agent
    - Access via `result.structured_output`
    - Return `model_dump_json()` for backward compatibility
    - Track each lifecycle step with TerraformLifecycleStep
    - Use `is_success` and `apply_succeeded` properties
    - Add integration test
    - _Requirements: Terraform agent structured output with dynamic schema_
  
  - [x] 6.4 Update validation_agent
    - Import ValidationResult and get_model_schema_description from agents.models
    - Generate schema dynamically: `VALIDATION_RESULT_SCHEMA = get_model_schema_description(ValidationResult)`
    - Inject schema into system prompt using f-string
    - Add `structured_output_model=ValidationResult` to Agent
    - Access via `result.structured_output`
    - Return `model_dump_json()` for backward compatibility
    - Track terraform_steps as dict
    - Use `is_success` and `all_steps_passed` properties
    - Add integration test
    - _Requirements: Validation agent structured output with dynamic schema_
  
  - [x] 6.5 Update storage_agent
    - Import StorageRequest, StorageResult, and get_model_schema_description from agents.models
    - Generate schemas dynamically for both input and output models
    - Inject schemas into system prompt using f-string
    - Add `structured_output_model=StorageResult` to Agent
    - Accept StorageRequest as input (parse from JSON)
    - Access via `result.structured_output`
    - Return `model_dump_json()` for backward compatibility
    - Validate nested models (ValidationResult, TerraformResult)
    - Add integration test
    - _Requirements: Storage agent structured output with dynamic schema_

- [ ] 7. Create agent integration tests
  - Create `tests/test_agent_integration.py`
  - Test discovery → documentation data flow
  - Test documentation → terraform data flow
  - Test terraform → validation data flow
  - Test validation → storage data flow
  - Test error handling at each agent boundary
  - Test JSON serialization round-trips work correctly
  - Verify all integration tests pass
  - _Requirements: Ensure agents work together_

- [ ] 8. Checkpoint - Verify agents work with structured output
  - Run all agent integration tests
  - Test with real pipeline run (single resource)
  - Verify backward compatibility maintained
  - Check logs for proper model usage

- [ ] 9. Update orchestrator with model parsing
  - [ ] 9.1 Add model imports and type hints
    - Import all models from agents.models
    - Add type hints to orchestrator functions
    - Verify no import errors
    - _Requirements: Type safety in orchestrator_
  
  - [ ] 9.2 Update system prompt with dynamic schemas
    - Import `get_all_agent_schemas` from agents.models
    - Use f-string to inject schemas into ORCHESTRATOR_SYSTEM_PROMPT
    - Add DATA MODELS section with: `{get_all_agent_schemas()}`
    - Provide usage examples in prompt showing how to parse each model
    - Verify prompt includes all model schemas automatically
    - Test prompt updates when models change
    - Document that schemas are generated dynamically (no manual updates needed)
    - _Requirements: Orchestrator understands model structure via dynamic injection_
  
  - [ ] 9.3 Update discovery phase parsing
    - Parse discovery_agent output to DiscoveryResult using `model_validate_json()`
    - Use type-safe field access (result.resource_name instead of dict access)
    - Use `is_valid` property for validation
    - Handle ValidationError gracefully with logging
    - Test discovery phase works
    - _Requirements: Type-safe discovery phase_
  
  - [ ] 9.4 Update documentation phase parsing
    - Parse documentation_agent output to DocumentationResult
    - Use type-safe field access
    - Use `is_success` property for validation
    - Handle ValidationError gracefully
    - Pass DiscoveryResult data to documentation_agent
    - Test documentation phase works
    - _Requirements: Type-safe documentation phase_
  
  - [ ] 9.5 Update terraform phase parsing
    - Parse terraform_agent output to TerraformResult
    - Use type-safe field access
    - Use `is_success` and `apply_succeeded` properties
    - Handle ValidationError gracefully
    - Pass DocumentationResult data to terraform_agent
    - Test terraform phase works
    - _Requirements: Type-safe terraform phase_
  
  - [ ] 9.6 Update validation phase parsing
    - Parse validation_agent output to ValidationResult
    - Use type-safe field access
    - Use `is_success` and `all_steps_passed` properties
    - Handle ValidationError gracefully
    - Pass TerraformResult data to validation_agent
    - Test validation phase works
    - _Requirements: Type-safe validation phase_
  
  - [ ] 9.7 Update storage phase with StorageRequest
    - Create StorageRequest with all pipeline data
    - Include nested ValidationResult and TerraformResult
    - Parse storage_agent output to StorageResult
    - Use type-safe field access
    - Handle ValidationError gracefully
    - Test storage phase works
    - Test nested model validation
    - _Requirements: Type-safe storage phase_
  
  - [ ] 9.8 Remove manual JSON parsing
    - Remove all `json.loads()` calls from orchestrator
    - Replace with `model_validate_json()` calls
    - Ensure all field access is type-safe (no dict access)
    - Verify code is cleaner and more readable
    - Verify all tests still pass
    - _Requirements: Eliminate manual JSON parsing_
  
  - [ ] 9.9 Add comprehensive error handling
    - Catch ValidationError at each agent boundary
    - Log detailed validation errors with field names
    - Create error models for failed validations
    - Continue pipeline with error models (don't crash)
    - Store validation failures in DynamoDB
    - Test all error handling paths
    - _Requirements: Graceful error handling_

- [ ] 10. Create end-to-end pipeline tests
  - Create `tests/test_pipeline_structured.py`
  - Test successful pipeline run with all phases
  - Test pipeline with discovery failure
  - Test pipeline with documentation failure
  - Test pipeline with terraform failure
  - Test pipeline with validation failure
  - Test pipeline with storage failure
  - Test error recovery and logging
  - Verify all pipeline tests pass
  - _Requirements: Complete pipeline validation_

- [ ] 11. Checkpoint - Verify complete pipeline works
  - Run full pipeline with structured output
  - Test with multiple resources
  - Verify DynamoDB and S3 storage works
  - Check logs for proper model usage
  - Verify error handling works correctly

- [ ] 12. Add type checking and code quality
  - [ ] 12.1 Enable mypy type checking
    - Create `mypy.ini` configuration file
    - Enable strict mode
    - Fix all type errors in agents/
    - Fix all type errors in orchestrator_agent.py
    - Add type hints to all functions
    - Verify mypy passes with zero errors
    - _Requirements: Type safety enforcement_
  
  - [ ] 12.2 Add pre-commit hooks
    - Create `.pre-commit-config.yaml`
    - Add mypy hook for type checking
    - Add black formatter hook
    - Add isort import sorter hook
    - Test hooks work locally
    - Document hook setup in README
    - _Requirements: Automated code quality_
  
  - [ ] 12.3 Performance benchmarking
    - Create benchmark script
    - Measure baseline performance (before structured output)
    - Measure performance with structured output
    - Compare validation overhead
    - Compare memory usage
    - Document results in docs/
    - Verify overhead is <5ms per pipeline run
    - _Requirements: Acceptable performance impact_

- [ ] 13. Complete documentation
  - Update README with structured output section
  - Add migration guide for developers
  - Add troubleshooting section for common issues
  - Add API reference for all models
  - Add usage examples for each model
  - Update architecture diagrams
  - Review and polish all documentation
  - _Requirements: Complete developer documentation_

- [ ] 14. Final checkpoint - Production readiness
  - Run full test suite and verify all pass
  - Run mypy and verify zero errors
  - Test with real AWS resources
  - Review all documentation
  - Verify backward compatibility maintained

- [ ] 15. (Optional) Remove backward compatibility
  - Agents return models directly instead of JSON strings
  - Orchestrator accepts models directly
  - Remove all `model_dump_json()` calls
  - Remove all `model_validate_json()` calls
  - Update all tests for direct model usage
  - Verify all tests pass
  - Verify performance improves (no JSON serialization overhead)
  - _Note: Only do this after Phase 1-14 stable in production_

## Notes

- Backward compatibility maintained throughout implementation (agents return JSON strings)
- Dynamic schema injection eliminates prompt/model duplication
- Comprehensive testing at each phase with checkpoints
- Type safety enforced with mypy in strict mode
- Optional final phase removes JSON serialization for performance
- Error isolation ensures partial failures don't crash pipeline

