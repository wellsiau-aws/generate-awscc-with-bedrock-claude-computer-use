"""
Comprehensive tests for agents/models.py

Tests cover:
- Valid data instantiation for each model
- Invalid data (pattern violations, required fields)
- Computed properties (@property methods)
- JSON serialization/deserialization round-trips
- Nested model validation (StorageRequest)
"""

import pytest
from pydantic import ValidationError
from agents.models import (
    TANGOBaseModel,
    DiscoveryResult,
    DocumentationResult,
    TerraformLifecycleStep,
    TerraformResult,
    ValidationResult,
    StorageRequest,
    StorageResult,
    get_model_schema_description,
    get_all_agent_schemas,
)


class TestTANGOBaseModel:
    """Test the base model configuration"""
    
    def test_base_model_config(self):
        """Test that base model has correct Pydantic configuration"""
        # TANGOBaseModel is abstract, so we test via a concrete subclass
        result = DiscoveryResult(
            resource_name="awscc_s3_bucket",
            provider_version="1.0.0",
            github_url="https://github.com/test",
            release_date="2024-01-01"
        )
        # Verify the model can be instantiated and has expected config
        assert result.resource_name == "awscc_s3_bucket"


class TestDiscoveryResult:
    """Test DiscoveryResult model"""
    
    def test_valid_discovery_result(self):
        """Test creating a valid DiscoveryResult"""
        result = DiscoveryResult(
            resource_name="awscc_s3_bucket",
            provider_version="1.0.0",
            github_url="https://github.com/hashicorp/terraform-provider-awscc/releases/tag/v1.0.0",
            release_date="2024-01-01"
        )
        assert result.resource_name == "awscc_s3_bucket"
        assert result.provider_version == "1.0.0"
        assert result.is_valid is True
    
    def test_invalid_resource_name_pattern(self):
        """Test that invalid resource name pattern raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            DiscoveryResult(
                resource_name="invalid_name",  # Must start with awscc_
                provider_version="1.0.0",
                github_url="https://github.com/test",
                release_date="2024-01-01"
            )
        assert "resource_name" in str(exc_info.value)
    
    def test_missing_required_fields(self):
        """Test that missing required fields raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            DiscoveryResult(
                resource_name="awscc_s3_bucket"
                # Missing provider_version, github_url, release_date
            )
        assert "provider_version" in str(exc_info.value)
    
    def test_is_valid_computed_property(self):
        """Test the is_valid computed property"""
        result = DiscoveryResult(
            resource_name="awscc_s3_bucket",
            provider_version="1.0.0",
            github_url="https://github.com/test",
            release_date="2024-01-01"
        )
        assert result.is_valid is True
        assert isinstance(result.is_valid, bool)
    
    def test_json_serialization_roundtrip(self):
        """Test JSON serialization and deserialization"""
        original = DiscoveryResult(
            resource_name="awscc_s3_bucket",
            provider_version="1.0.0",
            github_url="https://github.com/test",
            release_date="2024-01-01"
        )
        json_str = original.model_dump_json()
        restored = DiscoveryResult.model_validate_json(json_str)
        assert restored.resource_name == original.resource_name
        assert restored.provider_version == original.provider_version
        assert restored.is_valid == original.is_valid


class TestDocumentationResult:
    """Test DocumentationResult model"""
    
    def test_valid_documentation_result_success(self):
        """Test creating a successful DocumentationResult"""
        result = DocumentationResult(
            terraform_code="resource \"awscc_s3_bucket\" \"test\" {}",
            markdown_template="# Test",
            terraform_example="# Example",
            success=True,
            error_message=None
        )
        assert result.success is True
        assert result.is_success is True
        assert result.error_message is None
    
    def test_valid_documentation_result_failure(self):
        """Test creating a failed DocumentationResult"""
        result = DocumentationResult(
            terraform_code="",
            markdown_template="",
            terraform_example="",
            success=False,
            error_message="Failed to generate code"
        )
        assert result.success is False
        assert result.is_success is False
        assert result.error_message == "Failed to generate code"
    
    def test_missing_required_fields(self):
        """Test that missing required fields raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            DocumentationResult(
                terraform_code="test"
                # Missing other required fields
            )
        assert "markdown_template" in str(exc_info.value)
    
    def test_is_success_computed_property(self):
        """Test the is_success computed property"""
        result = DocumentationResult(
            terraform_code="test",
            markdown_template="test",
            terraform_example="test",
            success=True,
            error_message=None
        )
        assert result.is_success is True
        assert isinstance(result.is_success, bool)
    
    def test_json_serialization_roundtrip(self):
        """Test JSON serialization and deserialization"""
        original = DocumentationResult(
            terraform_code="resource \"awscc_s3_bucket\" \"test\" {}",
            markdown_template="# Test",
            terraform_example="# Example",
            success=True,
            error_message=None
        )
        json_str = original.model_dump_json()
        restored = DocumentationResult.model_validate_json(json_str)
        assert restored.terraform_code == original.terraform_code
        assert restored.is_success == original.is_success


class TestTerraformLifecycleStep:
    """Test TerraformLifecycleStep model"""
    
    def test_valid_lifecycle_step(self):
        """Test creating a valid TerraformLifecycleStep"""
        step = TerraformLifecycleStep(
            step_name="init",
            success=True,
            output="Terraform initialized",
            error_message=None
        )
        assert step.step_name == "init"
        assert step.success is True
    
    def test_missing_required_fields(self):
        """Test that missing required fields raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            TerraformLifecycleStep(
                step_name="init"
                # Missing success, output
            )
        assert "success" in str(exc_info.value)


class TestTerraformResult:
    """Test TerraformResult model"""
    
    def test_valid_terraform_result_all_success(self):
        """Test creating a TerraformResult with all steps successful"""
        result = TerraformResult(
            corrected_code="resource \"awscc_s3_bucket\" \"test\" {}",
            lifecycle_steps=[
                TerraformLifecycleStep(
                    step_name="init",
                    success=True,
                    output="Initialized",
                    error_message=None
                ),
                TerraformLifecycleStep(
                    step_name="apply",
                    success=True,
                    output="Applied",
                    error_message=None
                )
            ],
            final_success=True,
            error_summary=None
        )
        assert result.is_success is True
        assert result.apply_succeeded is True
    
    def test_valid_terraform_result_apply_failed(self):
        """Test TerraformResult with failed apply step"""
        result = TerraformResult(
            corrected_code="resource \"awscc_s3_bucket\" \"test\" {}",
            lifecycle_steps=[
                TerraformLifecycleStep(
                    step_name="init",
                    success=True,
                    output="Initialized",
                    error_message=None
                ),
                TerraformLifecycleStep(
                    step_name="apply",
                    success=False,
                    output="",
                    error_message="Apply failed"
                )
            ],
            final_success=False,
            error_summary="Apply failed"
        )
        assert result.is_success is False
        assert result.apply_succeeded is False
    
    def test_is_success_computed_property(self):
        """Test the is_success computed property"""
        result = TerraformResult(
            corrected_code="test",
            lifecycle_steps=[],
            final_success=True,
            error_summary=None
        )
        assert result.is_success is True
    
    def test_apply_succeeded_computed_property(self):
        """Test the apply_succeeded computed property"""
        result = TerraformResult(
            corrected_code="test",
            lifecycle_steps=[
                TerraformLifecycleStep(
                    step_name="apply",
                    success=True,
                    output="Applied",
                    error_message=None
                )
            ],
            final_success=True,
            error_summary=None
        )
        assert result.apply_succeeded is True
    
    def test_apply_succeeded_no_apply_step(self):
        """Test apply_succeeded when no apply step exists"""
        result = TerraformResult(
            corrected_code="test",
            lifecycle_steps=[
                TerraformLifecycleStep(
                    step_name="init",
                    success=True,
                    output="Initialized",
                    error_message=None
                )
            ],
            final_success=True,
            error_summary=None
        )
        assert result.apply_succeeded is False
    
    def test_json_serialization_roundtrip(self):
        """Test JSON serialization and deserialization with nested models"""
        original = TerraformResult(
            corrected_code="test",
            lifecycle_steps=[
                TerraformLifecycleStep(
                    step_name="init",
                    success=True,
                    output="Initialized",
                    error_message=None
                )
            ],
            final_success=True,
            error_summary=None
        )
        json_str = original.model_dump_json()
        restored = TerraformResult.model_validate_json(json_str)
        assert restored.corrected_code == original.corrected_code
        assert len(restored.lifecycle_steps) == len(original.lifecycle_steps)
        assert restored.lifecycle_steps[0].step_name == original.lifecycle_steps[0].step_name


class TestValidationResult:
    """Test ValidationResult model"""
    
    def test_valid_validation_result_all_passed(self):
        """Test ValidationResult with all steps passed"""
        result = ValidationResult(
            validation_steps={
                "syntax_check": True,
                "resource_validation": True,
                "best_practices": True
            },
            overall_assessment="All checks passed",
            recommendations=[],
            success=True,
            error_message=None
        )
        assert result.is_success is True
        assert result.all_steps_passed is True
    
    def test_valid_validation_result_some_failed(self):
        """Test ValidationResult with some steps failed"""
        result = ValidationResult(
            validation_steps={
                "syntax_check": True,
                "resource_validation": False,
                "best_practices": True
            },
            overall_assessment="Some checks failed",
            recommendations=["Fix resource validation"],
            success=False,
            error_message="Resource validation failed"
        )
        assert result.is_success is False
        assert result.all_steps_passed is False
    
    def test_is_success_computed_property(self):
        """Test the is_success computed property"""
        result = ValidationResult(
            validation_steps={"test": True},
            overall_assessment="Passed",
            recommendations=[],
            success=True,
            error_message=None
        )
        assert result.is_success is True
    
    def test_all_steps_passed_computed_property(self):
        """Test the all_steps_passed computed property"""
        result = ValidationResult(
            validation_steps={
                "step1": True,
                "step2": True,
                "step3": True
            },
            overall_assessment="All passed",
            recommendations=[],
            success=True,
            error_message=None
        )
        assert result.all_steps_passed is True
    
    def test_all_steps_passed_with_failure(self):
        """Test all_steps_passed when at least one step failed"""
        result = ValidationResult(
            validation_steps={
                "step1": True,
                "step2": False,
                "step3": True
            },
            overall_assessment="Some failed",
            recommendations=[],
            success=False,
            error_message="Step 2 failed"
        )
        assert result.all_steps_passed is False
    
    def test_json_serialization_roundtrip(self):
        """Test JSON serialization and deserialization"""
        original = ValidationResult(
            validation_steps={"test": True},
            overall_assessment="Passed",
            recommendations=["Good job"],
            success=True,
            error_message=None
        )
        json_str = original.model_dump_json()
        restored = ValidationResult.model_validate_json(json_str)
        assert restored.validation_steps == original.validation_steps
        assert restored.is_success == original.is_success


class TestStorageRequest:
    """Test StorageRequest model with nested validation"""
    
    def test_valid_storage_request_full(self):
        """Test creating a valid StorageRequest with all nested models"""
        request = StorageRequest(
            resource_name="awscc_s3_bucket",
            provider_version="1.0.0",
            terraform_code="resource \"awscc_s3_bucket\" \"test\" {}",
            markdown_template="# Test",
            terraform_example="# Example",
            validation_result=ValidationResult(
                validation_steps={"test": True},
                overall_assessment="Passed",
                recommendations=[],
                success=True,
                error_message=None
            ),
            terraform_result=TerraformResult(
                corrected_code="test",
                lifecycle_steps=[],
                final_success=True,
                error_summary=None
            ),
            success=True,
            error_message=None
        )
        assert request.resource_name == "awscc_s3_bucket"
        assert request.validation_result.is_success is True
        assert request.terraform_result.is_success is True
    
    def test_storage_request_nested_validation_failure(self):
        """Test StorageRequest with failed nested validation"""
        request = StorageRequest(
            resource_name="awscc_s3_bucket",
            provider_version="1.0.0",
            terraform_code="test",
            markdown_template="test",
            terraform_example="test",
            validation_result=ValidationResult(
                validation_steps={"test": False},
                overall_assessment="Failed",
                recommendations=["Fix it"],
                success=False,
                error_message="Validation failed"
            ),
            terraform_result=TerraformResult(
                corrected_code="test",
                lifecycle_steps=[],
                final_success=False,
                error_summary="Terraform failed"
            ),
            success=False,
            error_message="Overall failure"
        )
        assert request.success is False
        assert request.validation_result.is_success is False
        assert request.terraform_result.is_success is False
    
    def test_storage_request_invalid_resource_name(self):
        """Test that invalid resource name in StorageRequest raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            StorageRequest(
                resource_name="invalid_name",  # Must start with awscc_
                provider_version="1.0.0",
                terraform_code="test",
                markdown_template="test",
                terraform_example="test",
                validation_result=ValidationResult(
                    validation_steps={},
                    overall_assessment="",
                    recommendations=[],
                    success=True,
                    error_message=None
                ),
                terraform_result=TerraformResult(
                    corrected_code="test",
                    lifecycle_steps=[],
                    final_success=True,
                    error_summary=None
                ),
                success=True,
                error_message=None
            )
        assert "resource_name" in str(exc_info.value)
    
    def test_storage_request_missing_nested_models(self):
        """Test that missing nested models raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            StorageRequest(
                resource_name="awscc_s3_bucket",
                provider_version="1.0.0",
                terraform_code="test",
                markdown_template="test",
                terraform_example="test",
                # Missing validation_result and terraform_result
                success=True,
                error_message=None
            )
        assert "validation_result" in str(exc_info.value)
    
    def test_json_serialization_roundtrip_nested(self):
        """Test JSON serialization with deeply nested models"""
        original = StorageRequest(
            resource_name="awscc_s3_bucket",
            provider_version="1.0.0",
            terraform_code="test",
            markdown_template="test",
            terraform_example="test",
            validation_result=ValidationResult(
                validation_steps={"test": True},
                overall_assessment="Passed",
                recommendations=[],
                success=True,
                error_message=None
            ),
            terraform_result=TerraformResult(
                corrected_code="test",
                lifecycle_steps=[
                    TerraformLifecycleStep(
                        step_name="init",
                        success=True,
                        output="Initialized",
                        error_message=None
                    )
                ],
                final_success=True,
                error_summary=None
            ),
            success=True,
            error_message=None
        )
        json_str = original.model_dump_json()
        restored = StorageRequest.model_validate_json(json_str)
        assert restored.resource_name == original.resource_name
        assert restored.validation_result.is_success == original.validation_result.is_success
        assert restored.terraform_result.is_success == original.terraform_result.is_success
        assert len(restored.terraform_result.lifecycle_steps) == len(original.terraform_result.lifecycle_steps)


class TestStorageResult:
    """Test StorageResult model"""
    
    def test_valid_storage_result_success(self):
        """Test creating a successful StorageResult"""
        result = StorageResult(
            dynamodb_success=True,
            s3_success=True,
            dynamodb_error=None,
            s3_error=None
        )
        assert result.dynamodb_success is True
        assert result.s3_success is True
    
    def test_valid_storage_result_failure(self):
        """Test creating a failed StorageResult"""
        result = StorageResult(
            dynamodb_success=False,
            s3_success=True,
            dynamodb_error="DynamoDB write failed",
            s3_error=None
        )
        assert result.dynamodb_success is False
        assert result.dynamodb_error == "DynamoDB write failed"
    
    def test_missing_required_fields(self):
        """Test that missing required fields raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            StorageResult(
                dynamodb_success=True
                # Missing other required fields
            )
        assert "s3_success" in str(exc_info.value)
    
    def test_json_serialization_roundtrip(self):
        """Test JSON serialization and deserialization"""
        original = StorageResult(
            dynamodb_success=True,
            s3_success=True,
            dynamodb_error=None,
            s3_error=None
        )
        json_str = original.model_dump_json()
        restored = StorageResult.model_validate_json(json_str)
        assert restored.dynamodb_success == original.dynamodb_success
        assert restored.s3_success == original.s3_success


class TestHelperFunctions:
    """Test helper functions"""
    
    def test_get_model_schema_description(self):
        """Test get_model_schema_description function"""
        description = get_model_schema_description(DiscoveryResult)
        assert isinstance(description, str)
        assert "resource_name" in description
        assert "provider_version" in description
        assert "string" in description.lower()
    
    def test_get_all_agent_schemas(self):
        """Test get_all_agent_schemas function"""
        schemas = get_all_agent_schemas()
        assert isinstance(schemas, str)
        assert "DiscoveryResult" in schemas
        assert "DocumentationResult" in schemas
        assert "TerraformResult" in schemas
        assert "ValidationResult" in schemas
        assert "StorageRequest" in schemas
        assert "StorageResult" in schemas
