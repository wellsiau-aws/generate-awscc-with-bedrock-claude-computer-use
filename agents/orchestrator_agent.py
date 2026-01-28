"""
TANGO Multi-Agent Pipeline - Orchestrator Agent
Main entry point that coordinates specialized agents using Strands Agent pattern
"""

import os
import shutil
import config
from strands import Agent, tool
from .discovery_agent import discovery_agent
from .documentation_agent import documentation_agent
from .terraform_agent import terraform_agent
from .validation_agent import validation_agent
from .terraform_cleanup_agent import terraform_cleanup_agent
from .storage_agent import storage_agent
from .cleanup_agent import cleanup_agent
from .workspace_guard import print_workspace_status, cleanup_root_violations
from .models import (
    DiscoveryResult,
    DocumentationResult,
    TerraformResult,
    ValidationResult,
    StorageRequest,
    StorageResult,
    get_model_schema_description
)

# Configuration
os.environ['AWS_PROFILE'] = config.AWS_PROFILE
os.environ['AWS_REGION'] = config.AWS_REGION
os.environ['BYPASS_TOOL_CONSENT'] = 'true'

# Create schema inspection tool for the orchestrator
@tool
def get_data_model_schema(model_name: str) -> str:
    """
    Get the JSON schema description for a TANGO pipeline data model.
    
    Use this tool to understand the exact structure of data models used by agents.
    This is especially useful when constructing JSON to pass to agents like storage_agent.
    
    Args:
        model_name: Name of the model class. Valid options:
                   - "DiscoveryResult" (from discovery_agent)
                   - "DocumentationResult" (from documentation_agent)
                   - "TerraformResult" (from terraform_agent)
                   - "ValidationResult" (from validation_agent)
                   - "StorageRequest" (input to storage_agent)
                   - "StorageResult" (output from storage_agent)
                   - "CleanupResult" (output from terraform_cleanup_agent)
    
    Returns:
        Human-readable schema description with field names, types, and descriptions.
    
    Example:
        To understand what structure storage_agent expects:
        >>> schema = get_data_model_schema("StorageRequest")
        >>> print(schema)
        StorageRequest:
          - resource_name: string - AWS CloudControl resource name
          - status: string - Overall pipeline status
          - validation_result: ValidationResult - Complete validation results (nested model)
          ...
    """
    model_map = {
        "DiscoveryResult": DiscoveryResult,
        "DocumentationResult": DocumentationResult,
        "TerraformResult": TerraformResult,
        "ValidationResult": ValidationResult,
        "StorageRequest": StorageRequest,
        "StorageResult": StorageResult,
    }
    
    if model_name not in model_map:
        available = ", ".join(model_map.keys())
        return f"Error: Unknown model '{model_name}'. Available models: {available}"
    
    model_class = model_map[model_name]
    return get_model_schema_description(model_class)

# Define the orchestrator system prompt with clear agent coordination guidance
ORCHESTRATOR_SYSTEM_PROMPT = """
You are the TANGO Pipeline Orchestrator that coordinates specialized agents to process AWS CloudControl resources:

CRITICAL WORKING DIRECTORY RULE:
⚠️  ALL agents MUST work inside the directory: terraform_test
⚠️  NEVER allow agents to create files in the root directory
⚠️  If you see agents creating main.tf or other Terraform files in root, STOP and correct them
⚠️  All terraform commands must run from inside terraform_test directory

WORKSPACE REUSE MODEL (IMPORTANT):
The agents follow a Sequential Reuse pattern for efficiency:
1. Documentation Agent: Creates and initializes terraform_test (SETUP OWNER)
2. Terraform Agent: Reuses terraform_test, updates code only (CODE CORRECTOR)
3. Validation Agent: Reuses terraform_test, verifies independently (VERIFIER)
4. Pipeline Wrapper: Cleans up terraform_test at the end (CLEANUP OWNER)

This saves ~60 seconds per resource by avoiding redundant terraform init operations!

WORKFLOW:
1. For finding unprocessed resources → Use the discovery_agent tool
2. For generating Terraform code → Use the documentation_agent tool 
   - Documentation agent creates terraform_test and initializes it
   - Leaves terraform_test ready for next agent
3. For terraform validation (init/validate/plan/apply/destroy) → Use the terraform_agent tool
   - Terraform agent reuses existing terraform_test
   - Updates code and validates
   - Leaves terraform_test ready for next agent
4. For independent validation review → Use the validation_agent tool
   - Validation agent reuses existing terraform_test
   - Verifies independently
   - Leaves terraform_test for your cleanup
5. For cleaning up Terraform code (removing provider blocks) → Use the terraform_cleanup_agent tool
   - Agent automatically skips cleanup if validation failed (preserves error context)
   - Agent removes provider blocks only from successful validations
6. For storing results in DynamoDB and S3 → Use the storage_agent tool
7. For cleaning up orphaned AWS resources → Use the cleanup_agent tool (when needed)
8. To inspect data model structure for each agent, use the get_data_model_schema

EXECUTION ORDER:
1. Call discovery_agent to get the next resource to process AND provider version
   - Discovery agent returns a DiscoveryResult object with validated fields
2. Call documentation_agent with the DiscoveryResult object from discovery_agent
   - Documentation agent creates terraform_test directory and initializes it
   - Documentation agent returns a DocumentationResult object with validated fields
   - Ensure all files are created INSIDE terraform_test
3. Call terraform_agent with the DocumentationResult object from documentation_agent
   - Terraform agent reuses terraform_test (no recreation!)
   - Terraform agent returns a TerraformResult object with validated fields
4. Call validation_agent with the TerraformResult object from terraform_agent
   - Validation agent reuses terraform_test (no recreation!)
   - Validation agent returns a ValidationResult object with validated fields
5. Call terraform_cleanup_agent with the ValidationResult object from validation_agent
   - For successful validations: removes provider blocks and terraform blocks
   - For failed validations: skips cleanup and preserves original code for debugging
   - Returns a CleanupResult object with cleanup status and metadata
6. Call storage_agent to store results with StorageRequest object
   - Storage agent runs regardless if the previous steps are success and failure cases
   - Storage agent retuns a StorageResult 
7. Report completion and instruct user to run again for next resource

CLEANUP RESPONSIBILITY:
- Agents do NOT clean up terraform_test directory between themselves
- The pipeline wrapper function handles terraform_test cleanup automatically
- Cleanup happens even on failure (via try/finally in wrapper)
- Your job is to coordinate agents, not manage filesystem cleanup
- This ensures agents can reuse the workspace efficiently

CLEANUP: Use cleanup_agent only when explicitly requested or when terraform validation fails and leaves orphaned resources.

CRITICAL REQUIREMENTS:
- Always follow the workflow in order
- Each agent has a specific purpose - use the right tool for each phase
- Pass provider version information from discovery_agent to documentation_agent
- Pass BOTH terraform_code AND provider_version from documentation_agent to terraform_agent
- Ensure terraform_agent actually runs apply/destroy for real AWS validation
- Pass corrected_code AND resource_name to validation_agent for independent review
- Validation_agent stores its own results in S3 and returns validation status
- ALWAYS call storage_agent regardless of success or failure
- For failures: pass error details, failed agent name, and partial results to storage_agent
- For success: pass cleaned terraform code, execution results, validation results, and timing to storage_agent

DATA MODEL INSPECTION:
When you need to understand the exact structure of data models (especially for constructing JSON to pass to agents):
- Use the get_data_model_schema tool to inspect model structures
- Example: get_data_model_schema("StorageRequest") shows you exactly what storage_agent expects
- Example: get_data_model_schema("ValidationResult") shows you what validation_agent returns
- This is CRITICAL for passing task to the next agent

DATA FLOW:
discovery_agent → DiscoveryResult object
documentation_agent(DiscoveryResult) → DocumentationResult object [creates terraform_test]
terraform_agent(DocumentationResult) → TerraformResult object [reuses terraform_test]
validation_agent(TerraformResult) → ValidationResult object [reuses terraform_test]
terraform_cleanup_agent(ValidationResult) → CleanupResult object
storage_agent(all_results + cleaned_code + validation_results) → storage_confirmation
pipeline_wrapper → cleanup terraform_test

IMPORTANT UPDATES:
- The terraform_agent returns corrected code
- The validation_agent acts as independent reviewer and stores evaluation results in S3
- The storage_agent receives cleaned code from terraform_cleanup_agent and validation results
- This ensures that only working, validated, and cleaned code is stored in the examples
- Agents reuse terraform_test workspace for efficiency (saves 60 seconds per resource!)

FAILURE HANDLING:
- If any agent fails (including validation_agent), still call terraform_cleanup_agent
- Always call storage_agent with failure details after cleanup agent
- Include which agent failed, error messages, and any partial results
- If validation_agent fails, include validation failure details in storage
- This maintains complete audit trail for learning and debugging
- The pipeline wrapper will clean up terraform_test automatically (even on failure)

Execute the complete pipeline workflow using the specialized agents and handle both success and failure cases.
"""

# Create the orchestrator agent with specialized agents as tools
orchestrator = Agent(
    system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    tools=[
        discovery_agent,
        documentation_agent,
        terraform_agent,
        validation_agent,
        terraform_cleanup_agent,
        storage_agent,
        cleanup_agent,
        get_data_model_schema  # Schema inspection tool
    ],
    name="TANGO Pipeline Orchestrator"
)

def run_pipeline():
    """Execute the TANGO multi-agent pipeline"""
    print("🚀 TANGO Multi-Agent Pipeline Starting")
    print("=" * 60)
    
    # Clean up any files in root directory from previous failed runs
    cleanup_root_violations()
    
    try:
        pipeline_prompt = "Execute the complete pipeline workflow for the next AWS CloudControl resource."
        
        result = orchestrator(pipeline_prompt)
        
        return result
        
    except Exception as e:
        print(f"\n❌ Pipeline error: {e}")
        return None
        
    finally:
        # ALWAYS clean up terraform_test, even on failure
        import shutil
        if os.path.exists(config.TERRAFORM_WORK_DIR):
            print(f"\n🧹 Orchestrator cleaning up {config.TERRAFORM_WORK_DIR}...")
            try:
                shutil.rmtree(config.TERRAFORM_WORK_DIR)
                print(f"✅ Cleaned up {config.TERRAFORM_WORK_DIR}")
            except Exception as e:
                print(f"⚠️  Failed to clean up {config.TERRAFORM_WORK_DIR}: {e}")
        
        # Check workspace status after execution
        print_workspace_status()
        
        print("\n🎉 Multi-agent pipeline execution completed!")
        print("🔄 Run again to process the next resource")

if __name__ == "__main__":
    run_pipeline()
