# Agent Structured Output - Design Document

## Executive Summary

This document details the technical design for implementing Strands Structured Output across all TANGO pipeline agents. The implementation will replace unstructured string/JSON passing with type-safe Pydantic models, providing validation, type safety, and improved error handling.

**Key Design Decisions:**
- Single `agents/models.py` file for all Pydantic models
- Gradual migration with backward compatibility
- Agents return JSON strings initially, orchestrator parses to models
- Workspace reuse pattern preserved (critical for performance)
- Pydantic v2 for better performance and features

---

## Architecture Overview

### Current Architecture (Unstructured)

```
┌─────────────────┐
│ Discovery Agent │ → JSON string → ┌──────────────┐
└─────────────────┘                 │              │
                                    │ Orchestrator │
┌──────────────────┐                │   (manual    │
│ Documentation    │ ← raw text ──  │    JSON      │
│ Agent            │ → raw text →   │   parsing)   │
└──────────────────┘                │              │
                                    └──────────────┘
┌─────────────────┐
│ Terraform Agent │ ← raw text ──
│                 │ → raw text →
└─────────────────┘

Problems: No validation, runtime errors, no type safety
```

### Target Architecture (Structured)

```
┌─────────────────┐
│ Discovery Agent │ → DiscoveryResult → ┌──────────────┐
│ (Pydantic)      │                     │              │
└─────────────────┘                     │ Orchestrator │
                                        │  (type-safe  │
┌──────────────────┐                    │   Pydantic   │
│ Documentation    │ ← DiscoveryResult  │   models)    │
│ Agent (Pydantic) │ → DocumentationResult              │
└──────────────────┘                    └──────────────┘
                                        
┌─────────────────┐
│ Terraform Agent │ ← DocumentationResult
│ (Pydantic)      │ → TerraformResult
└─────────────────┘

┌─────────────────┐
│ Validation Agent│ ← TerraformResult
│ (Pydantic)      │ → ValidationResult
└─────────────────┘

┌─────────────────┐
│ Cleanup Agent   │ ← TerraformResult
│ (Pydantic)      │ → CleanupResult
└─────────────────┘

┌─────────────────┐
│ Storage Agent   │ ← StorageRequest (with CleanupResult)
│ (Pydantic)      │ → StorageResult
└─────────────────┘

Benefits: Validation, type safety, clear contracts
```

---

## Component Design

### 1. Pydantic Models (`agents/models.py`)

**Location:** `agents/models.py` (new file)

**Purpose:** Central location for all data exchange models

**Design Rationale:**
- Single file keeps models discoverable and maintainable
- Shared imports and base configurations
- Easy to version and document
- Clear dependency graph


**File Structure:**

```python
# agents/models.py
"""
TANGO Pipeline - Structured Output Models
Pydantic models for type-safe agent communication
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
from datetime import datetime

# Base configuration for all models
class TANGOBaseModel(BaseModel):
    """Base model with common configuration"""
    class Config:
        # Allow extra fields for forward compatibility
        extra = "allow"
        # Use enum values instead of enum objects
        use_enum_values = True
        # Validate on assignment
        validate_assignment = True

# 1. Discovery Agent Models
class DiscoveryResult(TANGOBaseModel):
    """Result from discovering next unprocessed resource"""
    # ... (full model from requirements.md)

# 2. Documentation Agent Models  
class DocumentationResult(TANGOBaseModel):
    """Result from generating Terraform documentation"""
    # ... (full model from requirements.md)

# 3. Terraform Agent Models
class TerraformLifecycleStep(TANGOBaseModel):
    """Individual Terraform lifecycle step result"""
    # ... (full model from requirements.md)

class TerraformResult(TANGOBaseModel):
    """Result from Terraform validation lifecycle"""
    # ... (full model from requirements.md)

# 4. Validation Agent Models
class ValidationResult(TANGOBaseModel):
    """Result from independent validation"""
    # ... (full model from requirements.md)

# 5. Storage Agent Models
class StorageRequest(TANGOBaseModel):
    """Request to store pipeline results"""
    # ... (full model from requirements.md)

class StorageResult(TANGOBaseModel):
    """Result from storing pipeline data"""
    # ... (full model from requirements.md)
```

**Model Relationships:**

```
DiscoveryResult
    ↓
DocumentationResult
    ↓
TerraformResult (contains List[TerraformLifecycleStep])
    ↓
ValidationResult
    ↓
CleanupResult
    ↓
StorageRequest (contains ValidationResult, TerraformResult, CleanupResult)
    ↓
StorageResult
```


---

## 2. Agent Updates

### Pattern for All Agents

Each agent will follow this pattern:

**Before (Current):**
```python
@tool
def discovery_agent(query: str) -> str:
    # ... agent logic ...
    result = {"resource_name": "awscc_s3_bucket", "provider_version": "1.53.0"}
    return json.dumps(result)  # Unstructured string
```

**After (Structured):**
```python
from .models import DiscoveryResult

@tool
def discovery_agent(query: str) -> str:
    """
    Find the next unprocessed AWS CloudControl resource.
    
    Returns:
        JSON string containing DiscoveryResult model
    """
    agent = Agent(
        system_prompt=DISCOVERY_SYSTEM_PROMPT,
        structured_output_model=DiscoveryResult  # ← Add structured output
    )
    
    result = agent(query)
    discovery_data: DiscoveryResult = result.structured_output  # ← Type-safe access
    
    # Validate before returning
    if not discovery_data.is_valid:
        print(f"⚠️  No valid resource found: {discovery_data.resource_name}")
    
    # Return JSON for backward compatibility with orchestrator
    return discovery_data.model_dump_json()
```

**Key Changes:**
1. Import model from `agents.models`
2. Add `structured_output_model` parameter to Agent
3. Access via `result.structured_output` (type-safe)
4. Return `model_dump_json()` for backward compatibility
5. Use model properties for validation (e.g., `is_valid`)


### Agent-Specific Implementations

#### Discovery Agent

**Changes:**
- Add `structured_output_model=DiscoveryResult`
- Access via `result.structured_output`
- Use `is_valid` property for validation
- Return `model_dump_json()` for orchestrator

**System Prompt Updates:**
```python
DISCOVERY_SYSTEM_PROMPT = """
...existing prompt...

OUTPUT FORMAT:
Return a DiscoveryResult with:
- resource_name: AWS CloudControl resource (e.g., "awscc_s3_bucket")
- provider_version: Semantic version (e.g., "1.53.0")
- error: Optional error message if discovery failed

The model will automatically validate:
- Resource name matches pattern ^awscc_[a-z0-9_]+$
- Provider version matches pattern ^\d+\.\d+\.\d+$
"""
```

#### Documentation Agent

**Changes:**
- Add `structured_output_model=DocumentationResult`
- Parse input as `DiscoveryResult` (from orchestrator)
- Return `DocumentationResult.model_dump_json()`
- Track workspace initialization status

**System Prompt Updates:**
```python
DOCUMENTATION_SYSTEM_PROMPT = """
...existing prompt...

OUTPUT FORMAT:
Return a DocumentationResult with:
- terraform_code: Generated Terraform configuration
- resource_name: Target resource name
- provider_version: AWSCC provider version used
- workspace_initialized: Whether terraform_test was initialized
- supplemental_resources: List of supplemental resources created
- supplemental_strategy: Explanation of choices
- error: Optional error message

The model will automatically validate:
- Terraform code is not empty
- Resource name matches AWSCC pattern
- Provider version is semantic version
"""
```


#### Terraform Agent

**Changes:**
- Add `structured_output_model=TerraformResult`
- Parse input as `DocumentationResult` (from orchestrator)
- Return `TerraformResult.model_dump_json()`
- Track each lifecycle step with `TerraformLifecycleStep`

**System Prompt Updates:**
```python
TERRAFORM_SYSTEM_PROMPT = """
...existing prompt...

OUTPUT FORMAT:
Return a TerraformResult with:
- status: "success" or "failed"
- corrected_code: Terraform code that passed validation
- resource_name: Target resource name
- lifecycle_steps: List of TerraformLifecycleStep objects
- fixes_applied: List of fixes made
- supplemental_resources_added: List of resources added
- workspace_reused: Whether workspace was reused
- error_message: Optional error if failed

Each TerraformLifecycleStep includes:
- step: "init", "validate", "plan", "apply", or "destroy"
- status: "success", "failed", or "skipped"
- output: Command output
- error: Error message if failed
"""
```

#### Validation Agent

**Changes:**
- Add `structured_output_model=ValidationResult`
- Parse input as `TerraformResult` (from orchestrator)
- Return `ValidationResult.model_dump_json()`
- Track terraform steps as dict

**System Prompt Updates:**
```python
VALIDATION_SYSTEM_PROMPT = """
...existing prompt...

OUTPUT FORMAT:
Return a ValidationResult with:
- validation_result: "success" or "failed"
- resource_name: Target resource validated
- target_resource_confirmed: Whether target resource found
- s3_analysis_path: S3 path to detailed report
- terraform_steps: Dict of step statuses
- workspace_reused: Whether workspace was reused
- validation_timestamp: When validation performed
- error: Optional error message
"""
```

#### Terraform Cleanup Agent

**Changes:**
- Add `structured_output_model=CleanupResult`
- Parse input as `TerraformResult` (from orchestrator)
- Return `CleanupResult.model_dump_json()`
- Track cleanup operations performed
- Handle failure detection (skip cleanup if validation failed)

**System Prompt Updates:**
```python
CLEANUP_SYSTEM_PROMPT = """
...existing prompt...

OUTPUT FORMAT:
Return a CleanupResult with:
- cleaned_code: Path to cleaned Terraform code (or unchanged if skipped)
- resource_name: Target resource name
- cleanup_applied: Whether cleanup was performed
- cleanup_operations: List of operations performed
- original_code_path: Reference to original code
- skipped_reason: Why cleanup was skipped (if applicable)
- error: Optional error message

Cleanup operations include:
- Remove terraform blocks
- Remove provider blocks (aws, awscc, random)
- Remove random_* resources
- Replace dynamic names with static names
- Remove test-specific comments
- Remove output blocks

FAILURE DETECTION:
- If input contains "TERRAFORM_LIFECYCLE_FAILED" or error indicators
- Set cleanup_applied=false
- Set skipped_reason="Failed validation detected"
- Return code unchanged to preserve error context
"""
```


#### Storage Agent

**Changes:**
- Add `structured_output_model=StorageResult`
- Accept `StorageRequest` as input (from orchestrator)
- Return `StorageResult.model_dump_json()`
- Validate nested models (ValidationResult, TerraformResult)

**System Prompt Updates:**
```python
STORAGE_SYSTEM_PROMPT = """
...existing prompt...

INPUT FORMAT:
You will receive a StorageRequest with:
- resource_name: Resource name
- status: "success" or "failed"
- terraform_code: Final Terraform code
- provider_version: Provider version used
- validation_result: ValidationResult object
- terraform_result: Optional TerraformResult object
- execution_time_seconds: Total execution time
- failed_agent: Which agent failed (if any)

OUTPUT FORMAT:
Return a StorageResult with:
- status: "success" or "failed"
- resource_name: Resource name stored
- dynamodb_stored: Whether DynamoDB entry created
- s3_terraform_link: S3 path to Terraform file
- s3_template_link: S3 path to template (success only)
- s3_analysis_link: S3 path to validation analysis
- template_generated: Whether template was generated
- old_entries_deleted: Number of old entries deleted
- error: Optional error message
"""
```

---

## 3. Orchestrator Integration

### Current Orchestrator Pattern

```python
# Current: Manual JSON parsing
discovery_result_str = discovery_agent("Find next resource")
discovery_data = json.loads(discovery_result_str)  # ← Manual parsing
resource_name = discovery_data["resource_name"]  # ← No type safety
```

### Target Orchestrator Pattern

```python
# Target: Type-safe model parsing
from agents.models import DiscoveryResult, DocumentationResult, TerraformResult

discovery_result_str = discovery_agent("Find next resource")
discovery_data = DiscoveryResult.model_validate_json(discovery_result_str)  # ← Validated parsing

# Type-safe access with IDE autocomplete
resource_name = discovery_data.resource_name  # ← Type-safe
provider_version = discovery_data.provider_version  # ← Type-safe

if discovery_data.is_valid:  # ← Use model properties
    # Continue pipeline
    pass
```


### Dynamic Schema Injection

Instead of hardcoding model schemas in the prompt, we'll dynamically inject them from the Pydantic models themselves:

**Add to `agents/models.py`:**

```python
def get_model_schema_description(model_class) -> str:
    """
    Generate a human-readable schema description from a Pydantic model.
    
    This extracts the JSON schema and formats it for inclusion in agent prompts,
    ensuring the prompt always matches the actual model structure.
    """
    schema = model_class.model_json_schema()
    
    lines = [f"{model_class.__name__}:"]
    
    # Add properties
    properties = schema.get('properties', {})
    required_fields = schema.get('required', [])
    
    for prop_name, prop_info in properties.items():
        # Get type information
        prop_type = prop_info.get('type', 'any')
        if 'anyOf' in prop_info:
            # Handle Optional types
            types = [t.get('type', 'any') for t in prop_info['anyOf'] if 'type' in t]
            prop_type = ' | '.join(types) if types else 'any'
        
        # Get description
        description = prop_info.get('description', '')
        
        # Check if required
        required = prop_name in required_fields
        optional_marker = "" if required else " (optional)"
        
        # Format line
        desc_text = f" - {description}" if description else ""
        lines.append(f"  - {prop_name}: {prop_type}{optional_marker}{desc_text}")
    
    # Add computed properties (methods decorated with @property)
    if hasattr(model_class, '__dict__'):
        for attr_name in dir(model_class):
            attr = getattr(model_class, attr_name)
            if isinstance(attr, property) and not attr_name.startswith('_'):
                lines.append(f"  - {attr_name}: computed property")
    
    return "\n".join(lines)


def get_all_agent_schemas() -> str:
    """
    Get formatted schema descriptions for all agent output models.
    
    This is used to dynamically inject model schemas into the orchestrator
    system prompt, ensuring documentation always matches implementation.
    """
    models = [
        DiscoveryResult,
        DocumentationResult,
        TerraformResult,
        ValidationResult,
        StorageRequest,
        StorageResult
    ]
    
    descriptions = []
    for i, model in enumerate(models, 1):
        descriptions.append(f"{i}. {get_model_schema_description(model)}")
    
    return "\n\n".join(descriptions)
```

**Update Orchestrator System Prompt:**

```python
# In agents/orchestrator_agent.py
from .models import get_all_agent_schemas

# Build prompt dynamically with current model schemas
ORCHESTRATOR_SYSTEM_PROMPT = f"""
You are the TANGO Pipeline Orchestrator...

DATA MODELS:
All agents return structured Pydantic models as JSON strings.
Parse these using the appropriate model classes:

{get_all_agent_schemas()}

WORKFLOW:
1. Call discovery_agent → parse DiscoveryResult
2. If valid, call documentation_agent → parse DocumentationResult
3. If successful, call terraform_agent → parse TerraformResult
4. If successful, call validation_agent → parse ValidationResult
5. If passed, call terraform_cleanup_agent → parse CleanupResult
6. Always call storage_agent → parse StorageResult
7. Clean up workspace

ERROR HANDLING:
- If any agent returns error field populated, log it and proceed to storage
- Always ensure workspace cleanup happens
- Validate all JSON responses against their models

Use these models to parse agent responses and access data in a type-safe manner.
"""
```

**Benefits:**
- ✅ No duplication - schema comes from model definition
- ✅ Always in sync - prompt updates automatically when models change
- ✅ Single source of truth - models.py defines everything
- ✅ Easier maintenance - change model, prompt updates automatically
- ✅ Type-safe - uses actual Pydantic schema generation


### Orchestrator Code Changes

**Phase 1: Add Model Imports**

```python
# At top of orchestrator_agent.py
from .models import (
    DiscoveryResult,
    DocumentationResult,
    TerraformResult,
    ValidationResult,
    StorageRequest,
    StorageResult
)
```

**Phase 2: Update run_pipeline() Function**

```python
def run_pipeline():
    """Execute the TANGO multi-agent pipeline with structured outputs"""
    print("🚀 TANGO Multi-Agent Pipeline Starting")
    print("=" * 60)
    
    cleanup_root_violations()
    
    try:
        # 1. Discovery - Parse to DiscoveryResult
        discovery_str = discovery_agent("Find next resource")
        discovery_data = DiscoveryResult.model_validate_json(discovery_str)
        
        if not discovery_data.is_valid:
            print(f"No valid resource found: {discovery_data.resource_name}")
            return None
        
        print(f"Processing: {discovery_data.resource_name} v{discovery_data.provider_version}")
        
        # 2. Documentation - Parse to DocumentationResult
        doc_input = discovery_data.model_dump_json()
        doc_str = documentation_agent(doc_input)
        doc_data = DocumentationResult.model_validate_json(doc_str)
        
        if not doc_data.is_success:
            print(f"Documentation failed: {doc_data.error}")
            # Store failure...
            return None
        
        # 3. Terraform - Parse to TerraformResult
        tf_input = doc_data.model_dump_json()
        tf_str = terraform_agent(tf_input)
        tf_data = TerraformResult.model_validate_json(tf_str)
        
        if not tf_data.is_success:
            print(f"Terraform failed: {tf_data.error_message}")
            # Store failure...
            return None
        
        # 4. Validation - Parse to ValidationResult
        val_input = tf_data.model_dump_json()
        val_str = validation_agent(val_input)
        val_data = ValidationResult.model_validate_json(val_str)
        
        # 5. Cleanup - Parse to CleanupResult
        cleanup_input = tf_data.model_dump_json()  # Pass terraform result
        cleanup_str = terraform_cleanup_agent(cleanup_input)
        cleanup_data = CleanupResult.model_validate_json(cleanup_str)
        
        if not cleanup_data.is_success:
            print(f"Cleanup failed: {cleanup_data.error}")
            # Continue to storage with cleanup failure
        
        # 6. Storage - Create StorageRequest, parse StorageResult
        storage_req = StorageRequest(
            resource_name=discovery_data.resource_name,
            status="success" if val_data.is_success else "failed",
            terraform_code=cleanup_data.cleaned_code,  # Use cleaned code
            provider_version=discovery_data.provider_version,
            validation_result=val_data,
            terraform_result=tf_data,
            cleanup_result=cleanup_data,  # Include cleanup results
            execution_time_seconds=None,  # Calculate if needed
            failed_agent=None
        )
        
        storage_str = storage_agent(storage_req.model_dump_json())
        storage_data = StorageResult.model_validate_json(storage_str)
        
        print(f"✅ Pipeline completed: {storage_data.status}")
        return storage_data
        
    except Exception as e:
        print(f"\n❌ Pipeline error: {e}")
        return None
        
    finally:
        # Cleanup terraform_test
        if os.path.exists(config.TERRAFORM_WORK_DIR):
            shutil.rmtree(config.TERRAFORM_WORK_DIR)
        print_workspace_status()
```


---

## 4. Error Handling Strategy

### Validation Errors

**Pydantic Validation Errors:**

```python
from pydantic import ValidationError

try:
    discovery_data = DiscoveryResult.model_validate_json(discovery_str)
except ValidationError as e:
    print(f"❌ Invalid discovery result: {e}")
    # Log validation errors
    for error in e.errors():
        print(f"  Field: {error['loc']}")
        print(f"  Error: {error['msg']}")
        print(f"  Input: {error['input']}")
    return None
```

**Benefits:**
- Clear error messages with field names
- Exact location of validation failure
- Input value that caused the error
- Type information

### Agent Errors

**Graceful Degradation:**

```python
# If agent returns invalid JSON or model
try:
    result = DiscoveryResult.model_validate_json(agent_output)
except (ValidationError, json.JSONDecodeError) as e:
    # Fall back to error result
    result = DiscoveryResult(
        resource_name="ERROR",
        provider_version="0.0.0",
        error=f"Agent output validation failed: {str(e)}"
    )
```

### Nested Model Errors

**StorageRequest with nested ValidationResult:**

```python
try:
    storage_req = StorageRequest(
        resource_name="awscc_s3_bucket",
        status="success",
        terraform_code="...",
        provider_version="1.53.0",
        validation_result=val_data,  # ← Nested model
        terraform_result=tf_data      # ← Nested model
    )
except ValidationError as e:
    # Pydantic validates nested models automatically
    print(f"Invalid storage request: {e}")
```

---

## 13. References

### External Documentation

- [Strands Structured Output](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/structured-output/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
- [Pydantic Performance](https://docs.pydantic.dev/latest/concepts/performance/)
- [Type Hints (PEP 484)](https://peps.python.org/pep-0484/)

### Internal Documentation

- [Requirements Document](.kiro/specs/agent-structured-output/requirements.md)
- [Analysis Document](../../../docs/STRUCTURED_OUTPUT_ANALYSIS.md)
- [TANGO Architecture](../../../docs/structure.md)

### Code Examples

- [Strands Examples](https://github.com/strandsagents/strands-examples)
- [Pydantic Examples](https://docs.pydantic.dev/latest/examples/)

---

## Appendix A: Complete Model Definitions

See `requirements.md` for complete Pydantic model definitions with all fields, validators, and properties.

## Appendix B: Migration Checklist

- [ ] Create `agents/models.py` with all models
- [ ] Add unit tests for all models
- [ ] Update discovery_agent with structured output
- [ ] Update documentation_agent with structured output
- [ ] Update terraform_agent with structured output
- [ ] Update validation_agent with structured output
- [ ] Update storage_agent with structured output
- [ ] Update orchestrator to parse models
- [ ] Remove manual JSON parsing
- [ ] Enable mypy strict mode
- [ ] Update documentation
- [ ] Performance benchmarking
- [ ] Deploy to production

## Appendix C: Example Pipeline Flow

```
1. Discovery Agent
   Input: "Find next resource"
   Output: DiscoveryResult(resource_name="awscc_s3_bucket", provider_version="1.53.0")

2. Documentation Agent
   Input: DiscoveryResult
   Output: DocumentationResult(terraform_code="...", workspace_initialized=True)

3. Terraform Agent
   Input: DocumentationResult
   Output: TerraformResult(status="success", corrected_code="...", lifecycle_steps=[...])

4. Validation Agent
   Input: TerraformResult
   Output: ValidationResult(validation_result="success", target_resource_confirmed=True)

5. Terraform Cleanup Agent
   Input: TerraformResult
   Output: CleanupResult(cleaned_code="...", cleanup_applied=True, cleanup_operations=["Removed provider blocks", "Removed random resources"])

6. Storage Agent
   Input: StorageRequest(validation_result=..., terraform_result=..., cleanup_result=...)
   Output: StorageResult(status="success", dynamodb_stored=True, s3_terraform_link="...")
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-27  
**Status:** Draft - Ready for Review
