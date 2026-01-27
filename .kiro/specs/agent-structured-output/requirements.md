# Agent Structured Output - Requirements

## Feature Overview

Implement Strands Structured Output using Pydantic models for all data exchanges between agents in the TANGO pipeline. This will replace unstructured string/JSON passing with type-safe, validated data structures.

## Problem Statement

Currently, agents communicate through unstructured strings and manual JSON parsing, leading to:
- Runtime errors from malformed data
- No type safety or IDE support
- Difficult debugging of data flow issues
- Inconsistent data formats between agents
- Manual validation logic scattered across agents

## Goals

1. **Type Safety**: All agent outputs are strongly typed with Pydantic models
2. **Validation**: Automatic validation of data structures at agent boundaries
3. **Documentation**: Self-documenting data contracts between agents
4. **Error Handling**: Clear, structured error messages with validation details
5. **Maintainability**: Easier refactoring with compile-time type checking

## Non-Goals

- Changing agent business logic or responsibilities
- Modifying the overall pipeline workflow
- Altering DynamoDB or S3 storage schemas
- Performance optimization (though may improve as side effect)

---

## User Stories

### 1. Discovery Agent Output

**As a** pipeline orchestrator  
**I want** discovery results in a validated structure  
**So that** I can safely access resource names and versions without parsing errors

**Acceptance Criteria:**
1.1. Discovery agent returns `DiscoveryResult` Pydantic model
1.2. Resource name is validated against pattern `^awscc_[a-z0-9_]+$`
1.3. Provider version is validated against semantic version pattern `^\d+\.\d+\.\d+$`
1.4. Model includes `is_valid` property to check if resource was found
1.5. Error field is populated when discovery fails
1.6. Model can be serialized to/from JSON for backward compatibility

### 2. Documentation Agent Output

**As a** terraform agent  
**I want** documentation results with separated code and metadata  
**So that** I can understand what was generated and what workspace state exists

**Acceptance Criteria:**
2.1. Documentation agent returns `DocumentationResult` Pydantic model
2.2. Terraform code is separated from metadata
2.3. Model tracks workspace initialization status
2.4. Supplemental resources are listed with explanations
2.5. Model includes `is_success` property for quick status check
2.6. Provider version is included for validation
2.7. Error field captures generation failures

### 3. Terraform Agent Output

**As a** validation agent  
**I want** detailed terraform lifecycle results  
**So that** I can understand what steps passed/failed and what fixes were applied

**Acceptance Criteria:**
3.1. Terraform agent returns `TerraformResult` Pydantic model
3.2. Overall status is clearly indicated (success/failed)
3.3. Each lifecycle step (init, validate, plan, apply, destroy) is tracked
3.4. Fixes applied during validation are documented
3.5. Supplemental resources added are listed
3.6. Workspace reuse status is tracked
3.7. Model includes `is_success` and `apply_succeeded` properties
3.8. Corrected code is included on success
3.9. Error message is included on failure

### 4. Validation Agent Output

**As a** storage agent  
**I want** structured validation results with all test outcomes  
**So that** I can store comprehensive validation reports and determine success/failure

**Acceptance Criteria:**
4.1. Validation agent returns `ValidationResult` Pydantic model
4.2. Validation result is clearly indicated (success/failed)
4.3. Target resource confirmation is tracked
4.4. S3 analysis path is included
4.5. Each terraform step status is recorded
4.6. Workspace reuse status is tracked
4.7. Validation timestamp is included
4.8. Model includes `is_success` and `all_steps_passed` properties
4.9. Error field captures validation failures

### 5. Storage Agent Input/Output

**As a** pipeline orchestrator  
**I want** structured storage requests and confirmations  
**So that** I can track what was stored and where

**Acceptance Criteria:**
5.1. Storage agent accepts `StorageRequest` Pydantic model
5.2. Storage agent returns `StorageResult` Pydantic model
5.3. Request includes all pipeline results (terraform, validation, timing)
5.4. Request validates status field (success/failed)
5.5. Result confirms DynamoDB and S3 storage
5.6. Result includes all S3 paths (terraform, template, analysis)
5.7. Result tracks template generation status
5.8. Result tracks old entries deleted count
5.9. Error field captures storage failures

---

## Data Models Specification

### 1. DiscoveryResult

```python
class DiscoveryResult(BaseModel):
    """Result from discovering next unprocessed resource"""
    resource_name: str = Field(
        description="AWS CloudControl resource name (e.g., awscc_s3_bucket)",
        pattern="^awscc_[a-z0-9_]+$"
    )
    provider_version: str = Field(
        description="Terraform AWSCC provider version (e.g., 1.53.0)",
        pattern="^\d+\.\d+\.\d+$"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if discovery failed"
    )
    
    @property
    def is_valid(self) -> bool:
        """Check if discovery found a valid resource"""
        return self.resource_name not in ("NONE", "ERROR")
```

**Validation Rules:**
- Resource name must start with "awscc_"
- Resource name can only contain lowercase letters, numbers, and underscores
- Provider version must be semantic version (X.Y.Z)
- Error field is optional

### 2. DocumentationResult

```python
class DocumentationResult(BaseModel):
    """Result from generating Terraform documentation"""
    terraform_code: str = Field(
        description="path to the main.tf containing the generated code",
        min_length=1
    )
    resource_name: str = Field(
        description="Target resource name",
        pattern="^awscc_[a-z0-9_]+$"
    )
    provider_version: str = Field(
        description="AWSCC provider version used",
        pattern="^\d+\.\d+\.\d+$"
    )
    workspace_initialized: bool = Field(
        description="Whether terraform_test workspace was initialized"
    )
    supplemental_resources: List[str] = Field(
        default_factory=list,
        description="List of supplemental resources created"
    )
    supplemental_strategy: Optional[str] = Field(
        default=None,
        description="Explanation of supplemental resource choices"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if generation failed"
    )
    log: Optional[str] = Field(
        default=None,
        description="path to the log containing Terraform execution"
    )
    
    @property
    def is_success(self) -> bool:
        """Check if documentation generation succeeded"""
        return self.error is None and len(self.terraform_code) > 0
```

**Validation Rules:**
- Terraform code must not be empty
- Resource name must match AWSCC pattern
- Provider version must be semantic version
- Supplemental resources list can be empty
- Error field is optional

### 3. TerraformLifecycleStep

```python
class TerraformLifecycleStep(BaseModel):
    """Individual Terraform lifecycle step result"""
    step: str = Field(
        description="Step name",
        pattern="^(init|validate|plan|apply|destroy)$"
    )
    status: str = Field(
        description="Status",
        pattern="^(success|failed|skipped)$"
    )
    output: Optional[str] = Field(
        default=None,
        description="Command output"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
```

### 4. TerraformResult

```python
class TerraformResult(BaseModel):
    """Result from Terraform validation lifecycle"""
    status: str = Field(
        description="Overall status",
        pattern="^(success|failed)$"
    )
    corrected_code: Optional[str] = Field(
        default=None,
        description="Path to main.tf containing the corrected Terraform code that passed validation"
    )
    resource_name: str = Field(
        description="Target resource name",
        pattern="^awscc_[a-z0-9_]+$"
    )
    lifecycle_steps: List[TerraformLifecycleStep] = Field(
        default_factory=list,
        description="Detailed results from each lifecycle step"
    )
    fixes_applied: List[str] = Field(
        default_factory=list,
        description="List of fixes applied to make code work"
    )
    supplemental_resources_added: List[str] = Field(
        default_factory=list,
        description="Supplemental resources added during validation"
    )
    workspace_reused: bool = Field(
        description="Whether existing workspace was reused"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if lifecycle failed"
    )
    
    @property
    def is_success(self) -> bool:
        """Check if Terraform lifecycle succeeded"""
        return self.status == "success"
    
    @property
    def apply_succeeded(self) -> bool:
        """Check if terraform apply succeeded"""
        apply_steps = [s for s in self.lifecycle_steps if s.step == "apply"]
        return any(s.status == "success" for s in apply_steps)
```

**Validation Rules:**
- Status must be "success" or "failed"
- Corrected code required on success, optional on failure
- Resource name must match AWSCC pattern
- Lifecycle steps can be empty list
- Step names must be one of: init, validate, plan, apply, destroy
- Step status must be: success, failed, or skipped

### 5. ValidationResult

```python
class ValidationResult(BaseModel):
    """Result from independent validation"""
    validation_result: str = Field(
        description="Validation outcome",
        pattern="^(success|failed)$"
    )
    resource_name: str = Field(
        description="Target resource name validated",
        pattern="^awscc_[a-z0-9_]+$"
    )
    target_resource_confirmed: bool = Field(
        description="Whether target resource was found in Terraform code"
    )
    s3_analysis_path: str = Field(
        description="S3 path to detailed validation report",
        pattern="^analysis/resource/.+\\.txt$"
    )
    terraform_steps: Dict[str, str] = Field(
        default_factory=dict,
        description="Status of each Terraform step"
    )
    workspace_reused: bool = Field(
        description="Whether existing workspace was reused"
    )
    validation_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When validation was performed"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if validation failed"
    )
    
    @property
    def is_success(self) -> bool:
        """Check if validation passed"""
        return self.validation_result == "success"
    
    @property
    def all_steps_passed(self) -> bool:
        """Check if all Terraform steps succeeded"""
        return all(status == "success" for status in self.terraform_steps.values())
```

**Validation Rules:**
- Validation result must be "success" or "failed"
- Resource name must match AWSCC pattern
- S3 analysis path must match expected format
- Terraform steps dict can be empty
- Timestamp is auto-generated if not provided
- Error field is optional

### 6. StorageRequest

```python
class StorageRequest(BaseModel):
    """Request to store pipeline results"""
    resource_name: str = Field(
        description="Resource name",
        pattern="^awscc_[a-z0-9_]+$"
    )
    status: str = Field(
        description="Pipeline status",
        pattern="^(success|failed)$"
    )
    terraform_code: str = Field(
        description="Path to main.tf containing the final Terraform code",
        min_length=1
    )
    provider_version: str = Field(
        description="Provider version used",
        pattern="^\d+\.\d+\.\d+$"
    )
    validation_result: ValidationResult = Field(
        description="Validation results from validation agent"
    )
    terraform_result: Optional[TerraformResult] = Field(
        default=None,
        description="Terraform agent results"
    )
    execution_time_seconds: Optional[float] = Field(
        default=None,
        description="Total execution time",
        ge=0
    )
    failed_agent: Optional[str] = Field(
        default=None,
        description="Which agent failed (if any)"
    )
```

### 7. StorageResult

```python
class StorageResult(BaseModel):
    """Result from storing pipeline data"""
    status: str = Field(
        description="Storage status",
        pattern="^(success|failed)$"
    )
    resource_name: str = Field(
        description="Resource name stored",
        pattern="^awscc_[a-z0-9_]+$"
    )
    dynamodb_stored: bool = Field(
        description="Whether DynamoDB entry created"
    )
    s3_terraform_link: str = Field(
        description="S3 path to Terraform file",
        pattern="^(examples|failed)/resources/.+\\.tf$"
    )
    s3_template_link: Optional[str] = Field(
        default=None,
        description="S3 path to template (only for success)",
        pattern="^templates/resources/.+\\.md\\.tmpl$"
    )
    s3_analysis_link: str = Field(
        description="S3 path to validation analysis",
        pattern="^analysis/resource/.+\\.txt$"
    )
    template_generated: bool = Field(
        description="Whether template was generated (success only)"
    )
    old_entries_deleted: int = Field(
        default=0,
        description="Number of old DynamoDB entries deleted",
        ge=0
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if storage failed"
    )
```

**Validation Rules:**
- Status must be "success" or "failed"
- Resource name must match AWSCC pattern
- Terraform code must not be empty
- Provider version must be semantic version
- Validation result is required (nested model)
- Execution time must be non-negative if provided
- S3 paths must match expected patterns
- Old entries deleted must be non-negative

---

## Technical Constraints

1. **Backward Compatibility**: Agents must continue to return JSON strings for gradual migration
2. **Strands Version**: Requires Strands Agents SDK with structured output support
3. **Python Version**: Python 3.8+ for Pydantic v2 features
4. **No Breaking Changes**: Orchestrator must handle both old and new formats during transition

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- Create `agents/models.py` with all Pydantic models
- Add comprehensive unit tests for models
- Document models in system prompts

### Phase 2: Agent Updates (Week 2-3)
- Update each agent to use `structured_output_model` parameter
- Maintain JSON string returns for backward compatibility
- Add integration tests for each agent

### Phase 3: Orchestrator Integration (Week 4)
- Update orchestrator to parse structured outputs
- Remove manual JSON parsing
- Full end-to-end testing

### Phase 4: Cleanup (Week 5)
- Remove backward compatibility code
- Enable strict type checking
- Performance benchmarking

---

## Success Metrics

1. **Type Safety**: 100% of agent outputs use Pydantic models
2. **Validation**: Zero runtime JSON parsing errors
3. **Test Coverage**: 90%+ coverage for model validation
4. **Error Reduction**: 50% reduction in data-related errors
5. **Developer Experience**: IDE autocomplete for all agent outputs

---

## Dependencies

- Strands Agents SDK (with structured output support)
- Pydantic v2.0+
- Python 3.8+
- Existing agent infrastructure

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking changes to agent interfaces | High | Maintain backward compatibility during transition |
| Pydantic validation performance | Medium | Benchmark and optimize if needed |
| Complex nested model validation | Medium | Comprehensive unit tests for all models |
| Orchestrator parsing complexity | High | Phased rollout with fallback to old format |

---

## Open Questions

1. Should we use Pydantic v1 or v2? (Recommend v2 for better performance)
2. How to handle partial failures in nested models?
3. Should models be in separate files or single `models.py`?
4. Do we need custom validators beyond pattern matching?
5. How to version models if schema changes in future?

---

## References

- [Strands Structured Output Documentation](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/structured-output/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [TANGO Pipeline Analysis](../../../docs/STRUCTURED_OUTPUT_ANALYSIS.md)
