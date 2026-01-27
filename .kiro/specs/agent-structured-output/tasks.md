# Agent Structured Output - Implementation Tasks

## Phase 1: Foundation

- [ ] 1.1 Create `agents/models.py` with base model infrastructure
  - [ ] 1.1.1 Create file with proper docstring and imports
  - [ ] 1.1.2 Implement `TANGOBaseModel` base class with common configuration
  - [ ] 1.1.3 Verify imports work without errors

- [ ] 1.2 Implement DiscoveryResult model
  - [ ] 1.2.1 Define class with all fields from requirements.md
  - [ ] 1.2.2 Add pattern validation for resource_name (^awscc_[a-z0-9_]+$)
  - [ ] 1.2.3 Add pattern validation for provider_version (^\d+\.\d+\.\d+$)
  - [ ] 1.2.4 Implement `is_valid` property
  - [ ] 1.2.5 Add comprehensive docstring with examples

- [ ] 1.3 Implement DocumentationResult model
  - [ ] 1.3.1 Define class with all fields from requirements.md
  - [ ] 1.3.2 Add validation for non-empty terraform_code
  - [ ] 1.3.3 Implement `is_success` property
  - [ ] 1.3.4 Add comprehensive docstring

- [ ] 1.4 Implement TerraformResult models
  - [ ] 1.4.1 Define TerraformLifecycleStep class
  - [ ] 1.4.2 Define TerraformResult class with all fields
  - [ ] 1.4.3 Add pattern validation for step names and statuses
  - [ ] 1.4.4 Implement `is_success` property
  - [ ] 1.4.5 Implement `apply_succeeded` property
  - [ ] 1.4.6 Add comprehensive docstrings

- [ ] 1.5 Implement ValidationResult model
  - [ ] 1.5.1 Define class with all fields from requirements.md
  - [ ] 1.5.2 Add pattern validation for s3_analysis_path
  - [ ] 1.5.3 Implement `is_success` property
  - [ ] 1.5.4 Implement `all_steps_passed` property
  - [ ] 1.5.5 Add comprehensive docstring

- [ ] 1.6 Implement Storage models
  - [ ] 1.6.1 Define StorageRequest class with nested models
  - [ ] 1.6.2 Define StorageResult class
  - [ ] 1.6.3 Add pattern validation for S3 paths
  - [ ] 1.6.4 Add validation for non-negative values
  - [ ] 1.6.5 Add comprehensive docstrings

- [ ] 1.7 Add dynamic schema injection helpers
  - [ ] 1.7.1 Implement `get_model_schema_description()` function
  - [ ] 1.7.2 Implement `get_all_agent_schemas()` function
  - [ ] 1.7.3 Test schema generation with all models
  - [ ] 1.7.4 Verify output is readable and accurate

- [ ] 1.8 Create model unit tests
  - [ ] 1.8.1 Create `tests/test_models.py` file
  - [ ] 1.8.2 Add tests for valid data for each model
  - [ ] 1.8.3 Add tests for invalid data (pattern violations)
  - [ ] 1.8.4 Add tests for model properties
  - [ ] 1.8.5 Add tests for nested model validation
  - [ ] 1.8.6 Add tests for JSON serialization/deserialization
  - [ ] 1.8.7 Verify 90%+ code coverage for models.py

- [ ] 1.9 Document models
  - [ ] 1.9.1 Add README section on structured output
  - [ ] 1.9.2 Add usage examples for each model
  - [ ] 1.9.3 Add validation error examples
  - [ ] 1.9.4 Create migration guide

## Phase 2: Agent Updates

- [ ] 2.1 Update discovery_agent
  - [ ] 2.1.1 Import DiscoveryResult from models
  - [ ] 2.1.2 Add structured_output_model=DiscoveryResult to Agent
  - [ ] 2.1.3 Access via result.structured_output
  - [ ] 2.1.4 Return model_dump_json() for backward compatibility
  - [ ] 2.1.5 Update system prompt with model documentation
  - [ ] 2.1.6 Use is_valid property for validation
  - [ ] 2.1.7 Add integration test
  - [ ] 2.1.8 Verify JSON can be parsed to DiscoveryResult

- [ ] 2.2 Update documentation_agent
  - [ ] 2.2.1 Import DocumentationResult from models
  - [ ] 2.2.2 Add structured_output_model=DocumentationResult to Agent
  - [ ] 2.2.3 Access via result.structured_output
  - [ ] 2.2.4 Return model_dump_json() for backward compatibility
  - [ ] 2.2.5 Update system prompt with model documentation
  - [ ] 2.2.6 Use is_success property for validation
  - [ ] 2.2.7 Track workspace_initialized status
  - [ ] 2.2.8 Add integration test

- [ ] 2.3 Update terraform_agent
  - [ ] 2.3.1 Import TerraformResult and TerraformLifecycleStep from models
  - [ ] 2.3.2 Add structured_output_model=TerraformResult to Agent
  - [ ] 2.3.3 Access via result.structured_output
  - [ ] 2.3.4 Return model_dump_json() for backward compatibility
  - [ ] 2.3.5 Update system prompt with model documentation
  - [ ] 2.3.6 Track each lifecycle step with TerraformLifecycleStep
  - [ ] 2.3.7 Use is_success and apply_succeeded properties
  - [ ] 2.3.8 Add integration test

- [ ] 2.4 Update validation_agent
  - [ ] 2.4.1 Import ValidationResult from models
  - [ ] 2.4.2 Add structured_output_model=ValidationResult to Agent
  - [ ] 2.4.3 Access via result.structured_output
  - [ ] 2.4.4 Return model_dump_json() for backward compatibility
  - [ ] 2.4.5 Update system prompt with model documentation
  - [ ] 2.4.6 Track terraform_steps as dict
  - [ ] 2.4.7 Use is_success and all_steps_passed properties
  - [ ] 2.4.8 Add integration test

- [ ] 2.5 Update storage_agent
  - [ ] 2.5.1 Import StorageRequest and StorageResult from models
  - [ ] 2.5.2 Add structured_output_model=StorageResult to Agent
  - [ ] 2.5.3 Accept StorageRequest as input (parse from JSON)
  - [ ] 2.5.4 Access via result.structured_output
  - [ ] 2.5.5 Return model_dump_json() for backward compatibility
  - [ ] 2.5.6 Update system prompt with model documentation
  - [ ] 2.5.7 Validate nested models (ValidationResult, TerraformResult)
  - [ ] 2.5.8 Add integration test

- [ ] 2.6 End-to-end agent testing
  - [ ] 2.6.1 Create tests/test_agent_integration.py
  - [ ] 2.6.2 Test discovery → documentation flow
  - [ ] 2.6.3 Test documentation → terraform flow
  - [ ] 2.6.4 Test terraform → validation flow
  - [ ] 2.6.5 Test validation → storage flow
  - [ ] 2.6.6 Test error handling at each boundary
  - [ ] 2.6.7 Test JSON serialization round-trips
  - [ ] 2.6.8 Verify all integration tests pass

## Phase 3: Orchestrator Integration

- [ ] 3.1 Add model imports to orchestrator
  - [ ] 3.1.1 Import all models from agents.models
  - [ ] 3.1.2 Add type hints to orchestrator functions
  - [ ] 3.1.3 Verify no import errors
  - [ ] 3.1.4 Verify models available for use

- [ ] 3.2 Update orchestrator system prompt with dynamic schemas
  - [ ] 3.2.1 Import get_all_agent_schemas from models
  - [ ] 3.2.2 Use f-string to inject schemas into ORCHESTRATOR_SYSTEM_PROMPT
  - [ ] 3.2.3 Verify prompt includes all model schemas
  - [ ] 3.2.4 Verify schemas match actual model definitions
  - [ ] 3.2.5 Test prompt updates when models change
  - [ ] 3.2.6 Add DATA MODELS section to system prompt
  - [ ] 3.2.7 Provide usage examples
  - [ ] 3.2.8 Update workflow documentation

- [ ] 3.3 Update run_pipeline() - Discovery phase
  - [ ] 3.3.1 Parse discovery_agent output to DiscoveryResult
  - [ ] 3.3.2 Use type-safe field access
  - [ ] 3.3.3 Use is_valid property for validation
  - [ ] 3.3.4 Handle ValidationError gracefully
  - [ ] 3.3.5 Add logging for parsed data
  - [ ] 3.3.6 Test discovery phase works

- [ ] 3.4 Update run_pipeline() - Documentation phase
  - [ ] 3.4.1 Parse documentation_agent output to DocumentationResult
  - [ ] 3.4.2 Use type-safe field access
  - [ ] 3.4.3 Use is_success property for validation
  - [ ] 3.4.4 Handle ValidationError gracefully
  - [ ] 3.4.5 Pass DiscoveryResult data to documentation_agent
  - [ ] 3.4.6 Test documentation phase works

- [ ] 3.5 Update run_pipeline() - Terraform phase
  - [ ] 3.5.1 Parse terraform_agent output to TerraformResult
  - [ ] 3.5.2 Use type-safe field access
  - [ ] 3.5.3 Use is_success and apply_succeeded properties
  - [ ] 3.5.4 Handle ValidationError gracefully
  - [ ] 3.5.5 Pass DocumentationResult data to terraform_agent
  - [ ] 3.5.6 Test terraform phase works

- [ ] 3.6 Update run_pipeline() - Validation phase
  - [ ] 3.6.1 Parse validation_agent output to ValidationResult
  - [ ] 3.6.2 Use type-safe field access
  - [ ] 3.6.3 Use is_success and all_steps_passed properties
  - [ ] 3.6.4 Handle ValidationError gracefully
  - [ ] 3.6.5 Pass TerraformResult data to validation_agent
  - [ ] 3.6.6 Test validation phase works

- [ ] 3.7 Update run_pipeline() - Storage phase
  - [ ] 3.7.1 Create StorageRequest with all pipeline data
  - [ ] 3.7.2 Include nested ValidationResult and TerraformResult
  - [ ] 3.7.3 Parse storage_agent output to StorageResult
  - [ ] 3.7.4 Use type-safe field access
  - [ ] 3.7.5 Handle ValidationError gracefully
  - [ ] 3.7.6 Test storage phase works
  - [ ] 3.7.7 Test nested model validation

- [ ] 3.8 Remove manual JSON parsing
  - [ ] 3.8.1 Remove all json.loads() calls
  - [ ] 3.8.2 Use model_validate_json() for all parsing
  - [ ] 3.8.3 Ensure all field access is type-safe
  - [ ] 3.8.4 Verify code is cleaner and more readable
  - [ ] 3.8.5 Verify all tests still pass

- [ ] 3.9 Add error handling
  - [ ] 3.9.1 Catch ValidationError at each agent boundary
  - [ ] 3.9.2 Log detailed validation errors
  - [ ] 3.9.3 Create error models for failed validations
  - [ ] 3.9.4 Continue pipeline with error models
  - [ ] 3.9.5 Store validation failures in DynamoDB
  - [ ] 3.9.6 Test error handling paths

- [ ] 3.10 End-to-end pipeline testing
  - [ ] 3.10.1 Create tests/test_pipeline_structured.py
  - [ ] 3.10.2 Test successful pipeline run
  - [ ] 3.10.3 Test pipeline with discovery failure
  - [ ] 3.10.4 Test pipeline with documentation failure
  - [ ] 3.10.5 Test pipeline with terraform failure
  - [ ] 3.10.6 Test pipeline with validation failure
  - [ ] 3.10.7 Test pipeline with storage failure
  - [ ] 3.10.8 Test error recovery and logging
  - [ ] 3.10.9 Verify all pipeline tests pass

## Phase 4: Cleanup

- [ ] 4.1 Enable mypy type checking
  - [ ] 4.1.1 Create mypy.ini configuration file
  - [ ] 4.1.2 Enable strict mode
  - [ ] 4.1.3 Fix all type errors in agents/
  - [ ] 4.1.4 Fix all type errors in orchestrator
  - [ ] 4.1.5 Add type hints to all functions
  - [ ] 4.1.6 Verify mypy passes with zero errors

- [ ] 4.2 Add pre-commit hooks
  - [ ] 4.2.1 Create .pre-commit-config.yaml
  - [ ] 4.2.2 Add mypy hook
  - [ ] 4.2.3 Add black formatter hook
  - [ ] 4.2.4 Add isort import sorter hook
  - [ ] 4.2.5 Test hooks work locally
  - [ ] 4.2.6 Document hook setup in README

- [ ] 4.3 Performance benchmarking
  - [ ] 4.3.1 Create benchmark script
  - [ ] 4.3.2 Measure baseline (before structured output)
  - [ ] 4.3.3 Measure with structured output
  - [ ] 4.3.4 Compare validation overhead
  - [ ] 4.3.5 Compare memory usage
  - [ ] 4.3.6 Document results
  - [ ] 4.3.7 Verify overhead is <5ms per pipeline

- [ ] 4.4 Update documentation
  - [ ] 4.4.1 Update README with structured output section
  - [ ] 4.4.2 Add migration guide
  - [ ] 4.4.3 Add troubleshooting section
  - [ ] 4.4.4 Add API reference
  - [ ] 4.4.5 Add examples for each model
  - [ ] 4.4.6 Update architecture diagrams
  - [ ] 4.4.7 Review and polish all docs

- [ ]* 4.5 Remove backward compatibility (optional)
  - [ ]* 4.5.1 Agents return models directly (not JSON strings)
  - [ ]* 4.5.2 Orchestrator accepts models directly
  - [ ]* 4.5.3 Remove all model_dump_json() calls
  - [ ]* 4.5.4 Remove all model_validate_json() calls
  - [ ]* 4.5.5 Update all tests
  - [ ]* 4.5.6 Verify all tests pass
  - [ ]* 4.5.7 Verify performance improves (no JSON serialization)

