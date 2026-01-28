"""
TANGO Multi-Agent Pipeline - Terraform Cleanup Agent
Specialized agent for cleaning up Terraform code
"""

from strands import Agent, tool
from strands_tools import python_repl

from agents.models import CleanupResult, ValidationResult, get_model_schema_description

# Generate schema dynamically to avoid duplication
CLEANUP_RESULT_SCHEMA = get_model_schema_description(CleanupResult)

CLEANUP_SYSTEM_PROMPT = f"""
You are a specialized Terraform code cleanup agent.

CRITICAL: Check if the input indicates a FAILED execution first!
- If you see "validation_result" or similar failure indicators in the input
- Return the code AS-IS without any cleanup
- Do NOT attempt to clean up failed code - it masks the actual errors

Your objective is to clean up SUCCESSFUL Terraform code and make it ready for examples in the AWSCC repository.

CLEANUP RULES (ONLY FOR SUCCESSFUL CODE):
1. Remove the `terraform` block - not needed for examples
2. Remove the `provider "aws"` and `provider "awscc"` blocks - not needed for examples
3. Remove any `provider "random"` blocks - not needed for examples
4. Remove any `random_id` or `random_*` resources - not needed for examples
5. Replace dynamic names with simple, static names:
   - `"example-bucket-${{random_id.bucket_suffix.hex}}"` → `"example-bucket"`
   - `"test-function-${{random_string.suffix.result}}"` → `"example-function"`
   - Any random suffixes or dynamic references → simple static names
6. Remove comments that explain testing or validation purposes
7. Remove output sections
8. Make the code look clean and production-ready like official Terraform Registry examples
9. Keep all resource configurations intact
10. Ensure proper formatting and indentation

WHAT TO KEEP:
- All main AWSCC resource configurations
- Variable references (if any, but clean up random ones)
- Clean, descriptive resource names

FAILURE HANDLING:
- If input contains failure indicators, return it unchanged
- Do NOT clean up failed code - it needs to preserve error context

OUTPUT FORMAT:
You MUST return a valid JSON object matching this CleanupResult schema:

{CLEANUP_RESULT_SCHEMA}

IMPORTANT INSTRUCTIONS:
1. If validation FAILED (detected by failure indicators), set:
   - cleanup_applied: false
   - skipped_reason: "Failed validation detected - keeping original code for debugging"
   - cleaned_code: path to original unchanged code
   - cleanup_operations: [] (empty list)

2. If cleanup is SUCCESSFUL, set:
   - cleanup_applied: true
   - cleanup_operations: list of operations performed (e.g., ["Removed provider blocks", "Removed random resources"])
   - cleaned_code: path to cleaned code
   - skipped_reason: null

3. If an ERROR occurs during cleanup, set:
   - cleanup_applied: false
   - error: description of the error
   - cleaned_code: path to original code
   - cleanup_operations: [] (empty list)

Return ONLY valid JSON matching the CleanupResult schema.
"""

@tool
def terraform_cleanup_agent(validation_result: ValidationResult) -> str:
    """
    Clean up Terraform code by removing provider blocks, terraform blocks, 
    excessive comments, and test-specific names.
    
    IMPORTANT: If validation failed, cleanup is skipped to preserve error context.

    Args:
        validation_result: ValidationResult object from validation_agent containing
                          validated terraform code path, resource name, provider version,
                          and validation status

    Returns:
        JSON string containing CleanupResult with cleaned code path and metadata
    """
    print("\n" + "="*80)
    print("🧹 TERRAFORM CLEANUP AGENT - STARTING")
    print("="*80)
    
    # Handle both dict and object inputs (Strands may serialize to dict)
    if isinstance(validation_result, dict):
        resource_name = validation_result.get('resource_name')
        provider_version = validation_result.get('provider_version')
        validation_result_status = validation_result.get('validation_result')
        target_resource_confirmed = validation_result.get('target_resource_confirmed', False)
        workspace_reused = validation_result.get('workspace_reused', False)
        is_success = validation_result.get('is_success', False)
    else:
        resource_name = validation_result.resource_name
        provider_version = validation_result.provider_version
        validation_result_status = validation_result.validation_result
        target_resource_confirmed = validation_result.target_resource_confirmed
        workspace_reused = validation_result.workspace_reused
        is_success = validation_result.is_success
    
    print(f"   Resource: {resource_name}")
    print(f"   Provider Version: {provider_version}")
    print(f"   Validation Result: {validation_result_status}")
    print(f"   Target Resource Confirmed: {target_resource_confirmed}")
    print(f"   Workspace Reused: {workspace_reused}")
       
    # Check if validation failed
    validation_failed = not is_success
    
    # Get terraform code path
    terraform_code_path = f"{config.TERRAFORM_WORK_DIR}/main.tf"
    
    try:
        # If validation failed, skip cleanup and return original code
        if validation_failed:
            print("\n" + "-"*80)
            print("⚠️  TERRAFORM CLEANUP AGENT - SKIPPED")
            print("   Validation failed - keeping original code for debugging")
            print("="*80 + "\n")
            
            # Create CleanupResult for skipped cleanup
            result = CleanupResult(
                cleaned_code="n/a",
                resource_name=resource_name,
                cleanup_applied=False,
                cleanup_operations=[],
                original_code_path=terraform_code_path,
                skipped_reason="Failed validation detected - keeping original code for debugging"
            )
            
            return result.model_dump_json()
                
        # Create agent with structured output
        agent = Agent(
            system_prompt=CLEANUP_SYSTEM_PROMPT,
            tools=[python_repl],
            structured_output_model=CleanupResult
        )
        
        cleanup_query = f"""
        Clean up this Terraform code for resource {resource_name} (provider version {provider_version}).
        
        Terraform Code path: {config.TERRAFORM_WORK_DIR}
                
        Return a CleanupResult JSON object with:
        - cleaned_code: "the terraform code path
        - resource_name: "{resource_name}"
        - cleanup_applied: true
        - cleanup_operations: list of operations performed (e.g., ["Removed provider blocks", "Removed random resources"])
        - original_code_path: null (or backup path if you create one)
        """
        
        print (cleanup_query)
        
        response = agent(cleanup_query)
        
        # Access structured output
        if hasattr(response, 'structured_output') and response.structured_output:
            cleanup_result = response.structured_output
            
            # Validate the result
            if cleanup_result.is_success:
                print("\n" + "-"*80)
                print("✅ TERRAFORM CLEANUP AGENT - COMPLETED")
                print(f"   Cleanup Applied: {cleanup_result.cleanup_applied}")
                print(f"   Operations Performed:")
                for op in cleanup_result.cleanup_operations:
                    print(f"     - {op}")
                print("="*80 + "\n")
            else:
                print("\n" + "-"*80)
                print("⚠️  TERRAFORM CLEANUP AGENT - COMPLETED WITH ISSUES")
                print(f"   Error: {cleanup_result.error}")
                print("="*80 + "\n")
            
            # Return JSON for backward compatibility
            return cleanup_result.model_dump_json()
        else:
            # Fallback if structured output not available
            print("\n" + "-"*80)
            print("⚠️  TERRAFORM CLEANUP AGENT - NO STRUCTURED OUTPUT")
            print("   Creating fallback result")
            print("="*80 + "\n")
            
            result = CleanupResult(
                cleaned_code=terraform_code_path,
                resource_name=validation_result.resource_name,
                cleanup_applied=False,
                cleanup_operations=[],
                error="Agent did not return structured output"
            )
            return result.model_dump_json()
            
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ TERRAFORM CLEANUP AGENT - FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        
        # Return error result
        result = CleanupResult(
            cleaned_code=terraform_code_path,
            resource_name=validation_result.resource_name,
            cleanup_applied=False,
            cleanup_operations=[],
            error=f"Cleanup agent exception: {str(e)}"
        )
        return result.model_dump_json()
