# Agent Structured Output Spec - Update Summary

## Changes Made

Added **terraform_cleanup_agent** to the structured output model specification.

## Problem Identified

The original spec was missing a critical agent in the pipeline flow:
- Discovery → Documentation → Terraform → Validation → **[MISSING: Cleanup]** → Storage

The terraform_cleanup_agent runs between validation_agent and storage_agent to remove provider blocks and test infrastructure from the Terraform code before storage.

## Solution Implemented

### 1. Added User Story 5 (requirements.md)

**User Story:** Terraform Cleanup Agent Output

**Purpose:** Provide cleaned terraform code with provider blocks removed for production-ready examples

**Acceptance Criteria:**
- Returns `CleanupResult` Pydantic model
- Tracks cleanup operations performed
- Handles failure detection (skips cleanup if validation failed)
- Maintains reference to original code
- Includes success/failure status

### 2. Added CleanupResult Model (requirements.md)

```python
class CleanupResult(BaseModel):
    """Result from cleaning up Terraform code"""
    cleaned_code: str  # Path to cleaned main.tf
    resource_name: str  # Target resource
    cleanup_applied: bool  # Whether cleanup was performed
    cleanup_operations: List[str]  # Operations performed
    original_code_path: Optional[str]  # Reference to original
    skipped_reason: Optional[str]  # Why skipped (if applicable)
    error: Optional[str]  # Error message
    
    @property
    def is_success(self) -> bool:
        """Check if cleanup succeeded"""
        return self.error is None
```

**Key Features:**
- Tracks whether cleanup was applied or skipped
- Documents specific cleanup operations performed
- Handles failure cases gracefully (passes through unchanged code)
- Maintains reference to original code for audit trail

### 3. Updated StorageRequest Model (requirements.md)

Added `cleanup_result` field to StorageRequest:

```python
class StorageRequest(BaseModel):
    # ... existing fields ...
    cleanup_result: Optional[CleanupResult] = Field(
        default=None,
        description="Cleanup agent results"
    )
```

This ensures storage_agent receives cleaned code and cleanup metadata.

### 4. Updated Architecture Diagrams (design.md)

**Added Cleanup Agent to Pipeline Flow:**

```
Discovery → Documentation → Terraform → Validation → Cleanup → Storage
```

**Updated Model Relationships:**

```
DiscoveryResult
    ↓
DocumentationResult
    ↓
TerraformResult
    ↓
ValidationResult
    ↓
CleanupResult  ← NEW
    ↓
StorageRequest (now includes CleanupResult)
    ↓
StorageResult
```

### 5. Added Cleanup Agent Implementation Guide (design.md)

**System Prompt Updates:**
- Dynamic schema injection using `get_model_schema_description(CleanupResult)`
- Structured output with `structured_output_model=CleanupResult`
- Failure detection logic (skip cleanup if validation failed)
- Cleanup operations tracking

**Cleanup Operations:**
- Remove terraform blocks
- Remove provider blocks (aws, awscc, random)
- Remove random_* resources
- Replace dynamic names with static names
- Remove test-specific comments
- Remove output blocks

### 6. Updated Orchestrator Integration (design.md)

**Added Cleanup Phase:**

```python
# 5. Cleanup - Parse to CleanupResult
cleanup_input = tf_data.model_dump_json()
cleanup_str = terraform_cleanup_agent(cleanup_input)
cleanup_data = CleanupResult.model_validate_json(cleanup_str)

# 6. Storage - Include cleanup results
storage_req = StorageRequest(
    # ... existing fields ...
    terraform_code=cleanup_data.cleaned_code,  # Use cleaned code
    cleanup_result=cleanup_data  # Include cleanup results
)
```

### 7. Added Task 6.6 (tasks.md)

**New Task:** Update terraform_cleanup_agent with structured output

**Implementation Steps:**
- Import CleanupResult and schema helper
- Generate schema dynamically
- Inject schema into system prompt
- Add structured_output_model parameter
- Track cleanup operations
- Handle failure detection
- Add integration test

## Pipeline Flow (Updated)

**Complete Pipeline with Cleanup:**

1. **Discovery Agent** → DiscoveryResult
2. **Documentation Agent** → DocumentationResult
3. **Terraform Agent** → TerraformResult
4. **Validation Agent** → ValidationResult
5. **Terraform Cleanup Agent** → CleanupResult ← **NEW**
6. **Storage Agent** → StorageResult (with CleanupResult)

## Benefits

### Type Safety
- CleanupResult provides type-safe access to cleaned code
- Validation ensures cleanup operations are documented
- IDE autocomplete for all cleanup fields

### Failure Handling
- Graceful handling of failed validations (skip cleanup)
- Clear indication of why cleanup was skipped
- Preserves error context by passing through unchanged code

### Audit Trail
- Complete record of cleanup operations performed
- Reference to original code maintained
- Tracks whether cleanup was applied or skipped

### Data Integrity
- Ensures storage_agent receives cleaned code
- Validates cleanup result structure
- Maintains consistency across pipeline

## Next Steps

### Implementation Order

1. ✅ **Spec Updated** - All three spec files updated with CleanupResult
2. **Model Implementation** - Add CleanupResult to `agents/models.py`
3. **Agent Update** - Update terraform_cleanup_agent with structured output
4. **Orchestrator Update** - Update orchestrator to parse CleanupResult
5. **Testing** - Add integration tests for cleanup phase
6. **Documentation** - Update README and usage guides

### Testing Requirements

- Unit tests for CleanupResult model validation
- Integration test for cleanup agent with structured output
- Test cleanup skip logic (failed validation detection)
- Test cleanup operations tracking
- Test orchestrator parsing of CleanupResult
- End-to-end pipeline test with cleanup phase

## Files Modified

1. `.kiro/specs/agent-structured-output/requirements.md`
   - Added User Story 5 (Terraform Cleanup Agent Output)
   - Added CleanupResult model specification
   - Updated StorageRequest to include cleanup_result field
   - Renumbered User Story 6 (Storage Agent)

2. `.kiro/specs/agent-structured-output/design.md`
   - Updated architecture diagrams to include Cleanup Agent
   - Updated model relationships to include CleanupResult
   - Added Cleanup Agent implementation guide
   - Updated orchestrator integration with cleanup phase
   - Updated Example Pipeline Flow with cleanup step

3. `.kiro/specs/agent-structured-output/tasks.md`
   - Updated task 6.5 (storage_agent) to validate CleanupResult
   - Added task 6.6 (terraform_cleanup_agent) with structured output

## Validation

### Model Validation Rules

**CleanupResult:**
- ✅ Cleaned code must not be empty
- ✅ Resource name must match AWSCC pattern `^awscc_[a-z0-9_]+$`
- ✅ Cleanup operations list can be empty (if skipped)
- ✅ Either cleanup_applied is True OR skipped_reason is provided
- ✅ Error field is optional

### Computed Properties

**CleanupResult.is_success:**
- Returns True if error is None
- Allows checking success status without inspecting error field
- Consistent with other model properties (is_valid, all_steps_passed)

## Summary

The spec now includes complete coverage of all agents in the TANGO pipeline:

1. ✅ Discovery Agent → DiscoveryResult
2. ✅ Documentation Agent → DocumentationResult
3. ✅ Terraform Agent → TerraformResult
4. ✅ Validation Agent → ValidationResult
5. ✅ **Terraform Cleanup Agent → CleanupResult** ← **ADDED**
6. ✅ Storage Agent → StorageRequest/StorageResult (updated)

The terraform_cleanup_agent is now fully integrated into the structured output specification with:
- Complete model definition with validation rules
- System prompt guidance for structured output
- Orchestrator integration pattern
- Implementation tasks and testing requirements
- Failure handling and audit trail support

**Status:** Spec is now complete and ready for implementation.

---

**Document Version:** 1.0  
**Created:** 2026-01-27  
**Author:** Kiro AI Assistant
