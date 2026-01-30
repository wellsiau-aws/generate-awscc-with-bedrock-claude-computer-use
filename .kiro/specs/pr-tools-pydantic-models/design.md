# Design Document: PR Tools Pydantic Models

## Overview

This design document describes the implementation of Pydantic data models for all function interactions in `agents/pr_tools.py`. The current implementation uses manual JSON string parsing for inputs and outputs across 8 tools. This design introduces structured Pydantic models that provide type safety, automatic validation, and improved maintainability while following existing patterns from `agents/models.py`.

### Goals

1. **Type Safety**: Replace manual JSON parsing with type-safe Pydantic models
2. **Automatic Validation**: Validate all inputs and outputs automatically using Pydantic
3. **Consistency**: Follow existing patterns from `agents/models.py` for uniformity
4. **Maintainability**: Improve code readability and reduce validation boilerplate
5. **Developer Experience**: Provide IDE autocomplete and clear error messages

### Non-Goals

1. Changing the functionality of existing tools
2. Modifying the PR workflow or agent orchestration
3. Adding new tools or capabilities
4. Backward compatibility with JSON string approach (clean migration)

## Architecture

### Module Structure

```
agents/
├── models.py              # Existing: Main pipeline models
├── pr_models.py           # NEW: PR tool models
├── pr_tools.py            # MODIFIED: Tools updated to use models
└── pr_agent.py            # MODIFIED: Agent updated to use models
```

### Model Hierarchy

All PR models inherit from `TANGOBaseModel` (defined in `agents/models.py`):

```
TANGOBaseModel (from agents/models.py)
├── Input Models (8 models for tool inputs)
│   ├── S3LinksInput
│   ├── FileContentInput
│   ├── PRContentInput
│   └── PRStatusInput
└── Output Models (8 models for tool outputs)
    ├── ResourceContentResult
    ├── EligibleResourceResult
    ├── RepoSetupResult
    ├── FilePlacementResult
    ├── ValidationCommandResult
    ├── HashiCorpValidationResult
    ├── GitHubPRResult
    ├── PRStatusUpdateResult
    └── GitCommitPushResult
```

### Design Principles

1. **One Model Per Tool**: Each tool gets dedicated input/output models
2. **Computed Properties**: Add convenience properties like `is_success` for common checks
3. **Optional Fields**: Use `Optional[]` for fields that may be None
4. **Field Validation**: Use `Field()` with patterns, min_length, and examples
5. **Clear Naming**: Model names clearly indicate their purpose (e.g., `ResourceContentResult`)
6. **Comprehensive Docs**: Every model, field, and property has detailed docstrings

## Components and Interfaces

### Component 1: TANGOBaseModel (Existing)

**Location**: `agents/models.py`

**Purpose**: Base class for all TANGO models with common Pydantic configuration

**Configuration**:
- `extra = "allow"`: Allow extra fields for forward compatibility
- `use_enum_values = True`: Use enum values in JSON
- `validate_assignment = True`: Validate on field assignment
- `json_schema_extra`: Enable JSON schema generation

**Usage**: All PR models inherit from this base class

### Component 2: Input Models

**Location**: `agents/pr_models.py`

**Purpose**: Validate tool input parameters before execution

#### S3LinksInput

Used by: `fetch_resource_content`

```python
class S3LinksInput(TANGOBaseModel):
    """S3 links for resource content."""
    s3_terraform_link: str = Field(
        description="S3 key for Terraform file",
        min_length=1
    )
    s3_template_link: str = Field(
        description="S3 key for template file",
        min_length=1
    )
    s3_analysis_link: Optional[str] = Field(
        default=None,
        description="S3 key for analysis file"
    )
```

#### FileContentInput

Used by: `place_files_in_structure`

```python
class FileContentInput(TANGOBaseModel):
    """Content to place in repository structure."""
    terraform_code: str = Field(
        min_length=1,
        description="Terraform code content"
    )
    template: str = Field(
        min_length=1,
        description="Template content"
    )
    service_name: str = Field(
        pattern=r"^[a-z0-9_]+$",
        description="Service name (lowercase, numbers, underscores)"
    )
```

#### PRContentInput

Used by: `create_github_pr`

```python
class PRContentInput(TANGOBaseModel):
    """Content metadata for PR creation."""
    service_name: str = Field(description="Service name")
    provider_version: str = Field(
        pattern=r"^\d+\.\d+\.\d+$",
        description="Provider version (semantic versioning)"
    )
    fetch_date: str = Field(description="Fetch date (YYYY-MM-DD)")
    s3_analysis_link: Optional[str] = Field(
        default=None,
        description="S3 analysis link"
    )
    analysis_report: Optional[str] = Field(
        default=None,
        description="Analysis report content"
    )
```

#### PRStatusInput

Used by: `update_pr_status`

```python
class PRStatusInput(TANGOBaseModel):
    """Input for updating PR status."""
    resource_name: str = Field(
        pattern=r"^awscc_[a-z0-9_]+$",
        description="Resource name (must start with awscc_)"
    )
    pr_url: Optional[str] = Field(
        default=None,
        description="GitHub PR URL"
    )
    status: str = Field(
        pattern=r"^(created|failed)$",
        description="PR status (created or failed)"
    )
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Validate status is only 'created' or 'failed'."""
        if v not in ['created', 'failed']:
            raise ValueError("Status must be 'created' or 'failed'")
        return v
```

### Component 3: Output Models

**Location**: `agents/pr_models.py`

**Purpose**: Validate tool output structure and provide convenience properties

#### ResourceContentResult

Used by: `fetch_resource_content`

```python
class ResourceContentResult(TANGOBaseModel):
    """Result from fetching resource content from S3."""
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status"
    )
    resource_name: str = Field(description="Resource name")
    service_name: str = Field(description="Service name")
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
        description="S3 terraform link"
    )
    s3_template_link: Optional[str] = Field(
        default=None,
        description="S3 template link"
    )
    s3_analysis_link: Optional[str] = Field(
        default=None,
        description="S3 analysis link"
    )
    provider_version: str = Field(description="Provider version")
    fetch_date: str = Field(description="Fetch date")
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    
    @property
    def is_success(self) -> bool:
        """Check if fetch succeeded."""
        return self.status == "success" and self.error is None
```

#### EligibleResourceResult

Used by: `get_next_eligible_resource`

```python
class EligibleResourceResult(TANGOBaseModel):
    """Result from getting next eligible resource."""
    resource_name: str = Field(
        description="Resource name or NONE/ERROR"
    )
    timestamp: Optional[int] = Field(
        default=None,
        description="Resource timestamp"
    )
    s3_terraform_link: Optional[str] = Field(
        default=None,
        description="S3 terraform link"
    )
    s3_template_link: Optional[str] = Field(
        default=None,
        description="S3 template link"
    )
    s3_analysis_link: Optional[str] = Field(
        default=None,
        description="S3 analysis link"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    
    @property
    def is_valid(self) -> bool:
        """Check if a valid resource was found."""
        return self.resource_name not in ("NONE", "ERROR")
    
    @property
    def has_all_files(self) -> bool:
        """Check if all required S3 files are present."""
        return all([
            self.s3_terraform_link,
            self.s3_template_link,
            self.s3_analysis_link
        ])
```

#### RepoSetupResult

Used by: `clone_and_setup_repo`

```python
class RepoSetupResult(TANGOBaseModel):
    """Result from cloning and setting up repository."""
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status"
    )
    repo_path: Optional[str] = Field(
        default=None,
        description="Repository path"
    )
    branch_name: Optional[str] = Field(
        default=None,
        description="Branch name"
    )
    work_dir_name: Optional[str] = Field(
        default=None,
        description="Working directory name"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    
    @property
    def is_success(self) -> bool:
        """Check if setup succeeded."""
        return self.status == "success" and self.error is None
```

#### FilePlacementResult

Used by: `place_files_in_structure`

```python
class FilePlacementResult(TANGOBaseModel):
    """Result from placing files in repository structure."""
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status"
    )
    files_created: List[str] = Field(
        default_factory=list,
        description="List of created files"
    )
    resource_name: Optional[str] = Field(
        default=None,
        description="Resource name"
    )
    service_name: Optional[str] = Field(
        default=None,
        description="Service name"
    )
    validation: Optional[str] = Field(
        default=None,
        description="Validation status"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    
    @property
    def is_success(self) -> bool:
        """Check if placement succeeded."""
        return self.status == "success" and self.validation == "passed"
```

#### ValidationCommandResult

Used by: `HashiCorpValidationResult` (nested model)

```python
class ValidationCommandResult(TANGOBaseModel):
    """Result from a single validation command."""
    command: str = Field(description="Command that was run")
    returncode: Optional[int] = Field(
        default=None,
        description="Command return code"
    )
    success: bool = Field(description="Whether command succeeded")
    stdout: Optional[str] = Field(
        default=None,
        description="Command stdout"
    )
    stderr: Optional[str] = Field(
        default=None,
        description="Command stderr"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
```

#### HashiCorpValidationResult

Used by: `run_hashicorp_validation`

```python
class HashiCorpValidationResult(TANGOBaseModel):
    """Result from running HashiCorp validation commands."""
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Overall status"
    )
    resource_name: str = Field(description="Resource name")
    commands: List[ValidationCommandResult] = Field(
        default_factory=list,
        description="Command results"
    )
    docs_generated: Optional[bool] = Field(
        default=None,
        description="Whether docs were generated"
    )
    docs_file_path: Optional[str] = Field(
        default=None,
        description="Path to generated docs"
    )
    docs_file_size: Optional[int] = Field(
        default=None,
        description="Size of generated docs"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    error_details: Optional[Dict] = Field(
        default=None,
        description="Detailed error information"
    )
    
    @property
    def is_success(self) -> bool:
        """Check if validation succeeded."""
        return self.status == "success" and self.docs_generated == True
    
    @property
    def all_commands_succeeded(self) -> bool:
        """Check if all commands succeeded."""
        return all(cmd.success for cmd in self.commands)
```

#### GitHubPRResult

Used by: `create_github_pr`

```python
class GitHubPRResult(TANGOBaseModel):
    """Result from creating GitHub pull request."""
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status"
    )
    pr_url: Optional[str] = Field(
        default=None,
        description="GitHub PR URL"
    )
    pr_number: Optional[int] = Field(
        default=None,
        description="GitHub PR number"
    )
    pr_title: Optional[str] = Field(
        default=None,
        description="PR title"
    )
    resource_name: Optional[str] = Field(
        default=None,
        description="Resource name"
    )
    branch_name: Optional[str] = Field(
        default=None,
        description="Branch name"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    
    @property
    def is_success(self) -> bool:
        """Check if PR creation succeeded."""
        return self.status == "success" and self.pr_url is not None
```

#### PRStatusUpdateResult

Used by: `update_pr_status`

```python
class PRStatusUpdateResult(TANGOBaseModel):
    """Result from updating PR status in DynamoDB."""
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status"
    )
    resource_name: str = Field(description="Resource name")
    timestamp: Optional[int] = Field(
        default=None,
        description="DynamoDB timestamp"
    )
    pr_status: Optional[str] = Field(
        default=None,
        description="Updated PR status"
    )
    pr_created_at: Optional[str] = Field(
        default=None,
        description="PR creation timestamp"
    )
    github_pr_url: Optional[str] = Field(
        default=None,
        description="GitHub PR URL"
    )
    message: Optional[str] = Field(
        default=None,
        description="Success message"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    
    @property
    def is_success(self) -> bool:
        """Check if update succeeded."""
        return self.status == "success" and self.error is None
```

#### GitCommitPushResult

Used by: `git_commit_and_push`

```python
class GitCommitPushResult(TANGOBaseModel):
    """Result from git commit and push operation."""
    status: str = Field(
        pattern=r"^(success|error)$",
        description="Operation status"
    )
    commit_hash: Optional[str] = Field(
        default=None,
        description="Full commit hash"
    )
    commit_hash_short: Optional[str] = Field(
        default=None,
        description="Short commit hash"
    )
    branch_name: Optional[str] = Field(
        default=None,
        description="Branch name"
    )
    resource_name: Optional[str] = Field(
        default=None,
        description="Resource name"
    )
    files_changed: Optional[int] = Field(
        default=None,
        description="Number of files changed"
    )
    commit_message: Optional[str] = Field(
        default=None,
        description="Commit message"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    
    @property
    def is_success(self) -> bool:
        """Check if commit and push succeeded."""
        return self.status == "success" and self.commit_hash is not None
```

### Component 4: Tool Updates

**Location**: `agents/pr_tools.py`

**Purpose**: Update tools to use Pydantic models instead of JSON strings

#### Migration Pattern

**Before** (current implementation):
```python
@tool
def fetch_resource_content(resource_name: str, s3_links_json: str = None) -> str:
    # Manual JSON parsing
    s3_links = json.loads(s3_links_json)
    terraform_key = s3_links.get('s3_terraform_link')
    
    # ... tool logic ...
    
    # Manual JSON construction
    result = {
        "status": "success",
        "resource_name": resource_name,
        # ... many fields ...
    }
    return json.dumps(result)
```

**After** (with models):
```python
@tool
def fetch_resource_content(
    resource_name: str,
    s3_links: Optional[S3LinksInput] = None
) -> ResourceContentResult:
    """Fetch resource content from S3 with validated inputs/outputs."""
    # Type-safe access
    if s3_links:
        terraform_key = s3_links.s3_terraform_link
    
    # ... tool logic ...
    
    # Validated construction
    return ResourceContentResult(
        status="success",
        resource_name=resource_name,
        # ... Pydantic validates all fields automatically ...
    )
```

#### Tool-by-Tool Migration

1. **fetch_resource_content**: Add S3LinksInput and ResourceContentResult
2. **get_next_eligible_resource**: Add EligibleResourceResult
3. **clone_and_setup_repo**: Add RepoSetupResult
4. **place_files_in_structure**: Add FileContentInput and FilePlacementResult
5. **run_hashicorp_validation**: Add ValidationCommandResult and HashiCorpValidationResult
6. **create_github_pr**: Add PRContentInput and GitHubPRResult
7. **update_pr_status**: Add PRStatusInput and PRStatusUpdateResult
8. **git_commit_and_push**: Add GitCommitPushResult

### Component 5: Agent Updates

**Location**: `agents/pr_agent.py`

**Purpose**: Update calling code to use models

#### Migration Pattern

**Before**:
```python
# Call tool with JSON string
result_json = fetch_resource_content(resource_name, s3_links_json)

# Manual parsing
result = json.loads(result_json)

# Manual checking
if result.get('status') == 'success':
    terraform_code = result.get('terraform_code')
```

**After**:
```python
# Call tool with model
result = fetch_resource_content(resource_name, s3_links)

# Type-safe access with computed property
if result.is_success:
    terraform_code = result.terraform_code
```

## Data Models

### Model Field Types

All models use standard Python types with Pydantic validation:

- `str`: String fields with optional pattern validation
- `int`: Integer fields
- `bool`: Boolean fields
- `Optional[T]`: Fields that can be None
- `List[T]`: List fields with typed elements
- `Dict`: Dictionary fields (used sparingly)

### Validation Rules

#### Pattern Validation

- **resource_name**: `^awscc_[a-z0-9_]+$` (must start with "awscc_")
- **service_name**: `^[a-z0-9_]+$` (lowercase, numbers, underscores)
- **provider_version**: `^\d+\.\d+\.\d+$` (semantic versioning)
- **status**: `^(success|error)$` (only "success" or "error")
- **pr_status**: `^(created|failed)$` (only "created" or "failed")

#### Length Validation

- **terraform_code**: `min_length=1` (must not be empty)
- **template**: `min_length=1` (must not be empty)
- **s3_terraform_link**: `min_length=1` (must not be empty)
- **s3_template_link**: `min_length=1` (must not be empty)

#### Custom Validation

- **PRStatusInput.status**: Field validator ensures only "created" or "failed"

### Default Values

- **Optional fields**: Default to `None`
- **List fields**: Default to empty list using `default_factory=list`
- **Dict fields**: Default to `None` (not empty dict to avoid mutable defaults)

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Required Field Validation

*For any* input or output model and any required field, attempting to instantiate the model without providing that field should raise a Pydantic ValidationError.

**Validates: Requirements 2.4**

### Property 2: Type Validation

*For any* model and any field, providing a value of the wrong type should raise a Pydantic ValidationError with a message indicating the type mismatch.

**Validates: Requirements 2.5**

### Property 3: Pattern Validation

*For any* field with a regex pattern constraint, providing a string that does not match the pattern should raise a Pydantic ValidationError.

**Validates: Requirements 2.6, 5.7, 5.8**

### Property 4: Non-Empty String Validation

*For any* field with min_length=1 constraint, providing an empty string should raise a Pydantic ValidationError.

**Validates: Requirements 5.2**

### Property 5: Optional Field Defaults

*For any* output model with optional fields, instantiating the model without providing those fields should result in the fields having their default values (None or empty list).

**Validates: Requirements 3.6**

### Property 6: Output Structure Validation

*For any* output model, attempting to create an instance with invalid field values should raise a Pydantic ValidationError before the instance is created.

**Validates: Requirements 3.7**

### Property 7: Success Property Correctness

*For any* output model with an is_success computed property, the property should return True if and only if status equals "success" and error is None.

**Validates: Requirements 4.1, 4.2, 5.5**

### Property 8: Computed Property Idempotence

*For any* computed property on any model, calling the property multiple times on the same instance should always return the same value and should not modify any model fields.

**Validates: Requirements 4.7**

### Property 9: JSON Serialization Round-Trip

*For any* valid model instance, serializing it to JSON using model_dump_json() and then deserializing it using model_validate_json() should produce a model instance with equivalent field values.

**Validates: Requirements 17.7, 17.8**

### Property 10: Integer Type Validation

*For any* field with type int (such as timestamp or files_changed), providing a non-integer value should raise a Pydantic ValidationError.

**Validates: Requirements 6.6**

## Error Handling

### Validation Errors

All models use Pydantic's automatic validation, which raises `pydantic.ValidationError` when:

1. **Missing Required Fields**: A required field is not provided during instantiation
2. **Type Mismatch**: A field value doesn't match the expected type
3. **Pattern Mismatch**: A string field doesn't match its regex pattern
4. **Length Violation**: A string field violates min_length constraint
5. **Custom Validation**: A field_validator rejects the value

### Error Message Format

Pydantic ValidationError provides structured error information:

```python
try:
    model = PRStatusInput(
        resource_name="invalid_name",  # Missing "awscc_" prefix
        status="pending"  # Invalid status value
    )
except ValidationError as e:
    print(e.json())
    # Output:
    # [
    #   {
    #     "loc": ["resource_name"],
    #     "msg": "String should match pattern '^awscc_[a-z0-9_]+$'",
    #     "type": "string_pattern_mismatch"
    #   },
    #   {
    #     "loc": ["status"],
    #     "msg": "String should match pattern '^(created|failed)$'",
    #     "type": "string_pattern_mismatch"
    #   }
    # ]
```

### Tool Error Handling

Tools should catch ValidationError and convert to appropriate error responses:

```python
@tool
def update_pr_status(input: PRStatusInput) -> PRStatusUpdateResult:
    try:
        # Tool logic here
        return PRStatusUpdateResult(status="success", ...)
    except ValidationError as e:
        # Pydantic validation failed
        return PRStatusUpdateResult(
            status="error",
            resource_name=input.resource_name,
            error=f"Validation failed: {str(e)}"
        )
    except Exception as e:
        # Other errors
        return PRStatusUpdateResult(
            status="error",
            resource_name=input.resource_name,
            error=str(e)
        )
```

### Error Propagation

- **Input Validation**: Fails fast at tool entry point
- **Output Validation**: Fails before returning to caller
- **Computed Properties**: Never raise exceptions, return boolean values
- **Field Access**: Type-safe, no KeyError or AttributeError

## Testing Strategy

### Dual Testing Approach

This implementation requires both unit tests and property-based tests:

- **Unit Tests**: Verify specific model instantiation, field access, and edge cases
- **Property Tests**: Verify universal properties across all models and inputs

### Unit Testing

**Focus Areas**:
- Specific model instantiation with valid data
- Specific model instantiation with invalid data (should raise ValidationError)
- Computed property behavior for specific cases
- Edge cases (empty strings, None values, special values like "NONE" and "ERROR")
- Error message content and structure

**Example Unit Tests**:

```python
def test_s3_links_input_valid():
    """Test S3LinksInput with valid data."""
    input = S3LinksInput(
        s3_terraform_link="examples/resources/awscc_s3_bucket/s3_bucket.tf",
        s3_template_link="templates/resources/s3_bucket.md.tmpl",
        s3_analysis_link="analysis/resource/awscc_s3_bucket/report.md"
    )
    assert input.s3_terraform_link == "examples/resources/awscc_s3_bucket/s3_bucket.tf"
    assert input.s3_analysis_link == "analysis/resource/awscc_s3_bucket/report.md"

def test_s3_links_input_empty_string():
    """Test S3LinksInput rejects empty strings."""
    with pytest.raises(ValidationError) as exc_info:
        S3LinksInput(
            s3_terraform_link="",  # Empty string should fail
            s3_template_link="templates/resources/s3_bucket.md.tmpl"
        )
    errors = exc_info.value.errors()
    assert any(e['loc'] == ('s3_terraform_link',) for e in errors)

def test_resource_content_result_is_success():
    """Test is_success property."""
    # Success case
    result = ResourceContentResult(
        status="success",
        resource_name="awscc_s3_bucket",
        service_name="s3_bucket",
        provider_version="1.53.0",
        fetch_date="2024-01-15"
    )
    assert result.is_success == True
    
    # Error case
    result_error = ResourceContentResult(
        status="error",
        resource_name="awscc_s3_bucket",
        service_name="s3_bucket",
        provider_version="1.53.0",
        fetch_date="2024-01-15",
        error="S3 file not found"
    )
    assert result_error.is_success == False
```

### Property-Based Testing

**Configuration**:
- Use `hypothesis` library for Python property-based testing
- Minimum 100 iterations per property test
- Tag each test with feature name and property number

**Property Test Examples**:

```python
from hypothesis import given, strategies as st
import pytest
from pydantic import ValidationError

# Strategy for generating valid resource names
resource_name_strategy = st.from_regex(r"^awscc_[a-z0-9_]+$", fullmatch=True)

# Strategy for generating invalid resource names
invalid_resource_name_strategy = st.text().filter(
    lambda x: not x.startswith("awscc_") or not x.replace("awscc_", "").replace("_", "").isalnum()
)

@given(resource_name=resource_name_strategy)
def test_property_1_required_field_validation(resource_name):
    """
    Feature: pr-tools-pydantic-models, Property 1: Required Field Validation
    
    For any input or output model and any required field, attempting to 
    instantiate the model without providing that field should raise ValidationError.
    """
    # Test PRStatusInput missing required status field
    with pytest.raises(ValidationError) as exc_info:
        PRStatusInput(resource_name=resource_name)  # Missing status
    
    errors = exc_info.value.errors()
    assert any(e['loc'] == ('status',) and e['type'] == 'missing' for e in errors)

@given(
    field_value=st.one_of(
        st.integers(),
        st.floats(),
        st.lists(st.text()),
        st.dictionaries(st.text(), st.text())
    )
)
def test_property_2_type_validation(field_value):
    """
    Feature: pr-tools-pydantic-models, Property 2: Type Validation
    
    For any model and any field, providing a value of the wrong type should 
    raise ValidationError with a message indicating the type mismatch.
    """
    # Assume field_value is not a string
    if isinstance(field_value, str):
        return
    
    # Try to create S3LinksInput with non-string value
    with pytest.raises(ValidationError) as exc_info:
        S3LinksInput(
            s3_terraform_link=field_value,  # Wrong type
            s3_template_link="valid/path.tf"
        )
    
    errors = exc_info.value.errors()
    assert any(
        e['loc'] == ('s3_terraform_link',) and 'type' in e['type'].lower()
        for e in errors
    )

@given(invalid_pattern=st.text().filter(lambda x: not x.startswith("awscc_")))
def test_property_3_pattern_validation(invalid_pattern):
    """
    Feature: pr-tools-pydantic-models, Property 3: Pattern Validation
    
    For any field with a regex pattern constraint, providing a string that 
    does not match the pattern should raise ValidationError.
    """
    # Test resource_name pattern validation
    with pytest.raises(ValidationError) as exc_info:
        PRStatusInput(
            resource_name=invalid_pattern,  # Doesn't match pattern
            status="created"
        )
    
    errors = exc_info.value.errors()
    assert any(
        e['loc'] == ('resource_name',) and 'pattern' in e['type'].lower()
        for e in errors
    )

@given(
    status=st.sampled_from(["success", "error"]),
    has_error=st.booleans()
)
def test_property_7_success_property_correctness(status, has_error):
    """
    Feature: pr-tools-pydantic-models, Property 7: Success Property Correctness
    
    For any output model with an is_success computed property, the property 
    should return True if and only if status equals "success" and error is None.
    """
    error_value = "Some error" if has_error else None
    
    result = ResourceContentResult(
        status=status,
        resource_name="awscc_s3_bucket",
        service_name="s3_bucket",
        provider_version="1.53.0",
        fetch_date="2024-01-15",
        error=error_value
    )
    
    expected_success = (status == "success" and error_value is None)
    assert result.is_success == expected_success

@given(
    resource_name=resource_name_strategy,
    status=st.sampled_from(["success", "error"]),
    terraform_code=st.text(),
    template=st.text(),
    provider_version=st.from_regex(r"^\d+\.\d+\.\d+$", fullmatch=True),
    fetch_date=st.text()
)
def test_property_9_json_serialization_round_trip(
    resource_name, status, terraform_code, template, provider_version, fetch_date
):
    """
    Feature: pr-tools-pydantic-models, Property 9: JSON Serialization Round-Trip
    
    For any valid model instance, serializing it to JSON and then deserializing 
    it should produce a model instance with equivalent field values.
    """
    # Create original model
    original = ResourceContentResult(
        status=status,
        resource_name=resource_name,
        service_name=resource_name.replace("awscc_", ""),
        terraform_code=terraform_code,
        template=template,
        provider_version=provider_version,
        fetch_date=fetch_date
    )
    
    # Serialize to JSON
    json_str = original.model_dump_json()
    
    # Deserialize from JSON
    deserialized = ResourceContentResult.model_validate_json(json_str)
    
    # Check equivalence
    assert deserialized.status == original.status
    assert deserialized.resource_name == original.resource_name
    assert deserialized.service_name == original.service_name
    assert deserialized.terraform_code == original.terraform_code
    assert deserialized.template == original.template
    assert deserialized.provider_version == original.provider_version
    assert deserialized.fetch_date == original.fetch_date
```

### Test Organization

```
tests/
├── test_pr_models.py           # Model validation tests
│   ├── Unit tests for each model
│   ├── Property tests for universal properties
│   └── Edge case tests
└── test_pr_tools_integration.py  # Integration tests for tools with models
    ├── Test tool input validation
    ├── Test tool output validation
    └── Test end-to-end workflows
```

### Test Coverage Goals

- **Model Validation**: 100% coverage of all validation rules
- **Computed Properties**: 100% coverage of all property methods
- **Error Cases**: All ValidationError paths tested
- **Round-Trip**: All models tested for JSON serialization/deserialization
- **Integration**: All 8 tools tested with models

## Implementation Notes

### Migration Strategy

1. **Phase 1: Create Models** (Low Risk)
   - Create `agents/pr_models.py` with all model definitions
   - Add comprehensive docstrings and examples
   - Add unit tests for model validation
   - **No changes to existing tools yet**

2. **Phase 2: Update Tools** (Medium Risk)
   - Update tools one at a time
   - Change function signatures to use models
   - Remove manual JSON parsing
   - Update error handling
   - Test each tool after update

3. **Phase 3: Update Agent** (Low Risk)
   - Update `agents/pr_agent.py` to use models
   - Remove manual JSON parsing in agent code
   - Use computed properties for cleaner logic
   - Test full PR workflow

4. **Phase 4: Add Property Tests** (Low Risk)
   - Add property-based tests for all models
   - Run tests with 100+ iterations
   - Verify all properties hold

### Tool Update Order

Recommended order (simplest to most complex):

1. `get_next_eligible_resource` - No input model, simple output
2. `clone_and_setup_repo` - No input model, simple output
3. `git_commit_and_push` - No input model, simple output
4. `fetch_resource_content` - Simple input model, complex output
5. `place_files_in_structure` - Simple input model, simple output
6. `update_pr_status` - Simple input model with validation, simple output
7. `create_github_pr` - Complex input model, simple output
8. `run_hashicorp_validation` - No input model, complex nested output

### Performance Considerations

- **Pydantic V2**: Use Pydantic V2 for optimal performance (10-50x faster than V1)
- **Validation Overhead**: Minimal (<1ms per model instantiation)
- **Memory**: Models use slightly more memory than dicts, but negligible for this use case
- **Serialization**: Pydantic's JSON serialization is highly optimized

### Compatibility

- **Python Version**: Requires Python 3.8+ (same as existing codebase)
- **Pydantic Version**: Requires Pydantic 2.0+ (check current version in requirements.txt)
- **Dependencies**: No new dependencies (Pydantic already used in agents/models.py)

### Code Style

Follow existing patterns from `agents/models.py`:

- Use `Field()` for all field definitions
- Include `description` for every field
- Include `examples` for fields where helpful
- Use `Optional[]` for fields that can be None
- Use `default=None` or `default_factory=list` for optional fields
- Add comprehensive docstrings with usage examples
- Use `@property` decorator for computed properties
- Include type hints for all methods

### Documentation

Each model should include:

1. **Module Docstring**: Explain purpose of pr_models.py
2. **Class Docstring**: Explain what the model represents, with usage examples
3. **Field Descriptions**: Use Field(description=...) for every field
4. **Field Examples**: Use Field(examples=[...]) where helpful
5. **Property Docstrings**: Explain what each computed property does
6. **Usage Examples**: Show how to instantiate and use the model

### Example Complete Model

```python
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
        terraform_code: Terraform configuration code content
        template: Template file content
        analysis_report: Optional analysis report content
        s3_terraform_link: S3 key for Terraform file
        s3_template_link: S3 key for template file
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
        ...     terraform_code="resource \"awscc_s3_bucket\" \"example\" {...}",
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
        
        # Serialize to JSON
        >>> json_str = result.model_dump_json()
        
        # Deserialize from JSON
        >>> result2 = ResourceContentResult.model_validate_json(json_str)
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
        
        Examples:
            >>> result = ResourceContentResult(
            ...     status="success",
            ...     resource_name="awscc_s3_bucket",
            ...     service_name="s3_bucket",
            ...     provider_version="1.53.0",
            ...     fetch_date="2024-01-15"
            ... )
            >>> result.is_success
            True
            
            >>> error_result = ResourceContentResult(
            ...     status="error",
            ...     resource_name="awscc_s3_bucket",
            ...     service_name="s3_bucket",
            ...     provider_version="1.53.0",
            ...     fetch_date="2024-01-15",
            ...     error="S3 file not found"
            ... )
            >>> error_result.is_success
            False
        """
        return self.status == "success" and self.error is None
```
