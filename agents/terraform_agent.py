"""
TANGO Multi-Agent Pipeline - Terraform Agent
Specialized agent for executing Terraform lifecycle operations with real AWS deployment

todo: add MCP support
"""

from strands import Agent, tool
from strands_tools import python_repl, shell
import config
from .resource_tools import check_resource_status, fetch_example_code, list_available_examples
from .models import TerraformResult, TerraformLifecycleStep, get_model_schema_description

# Generate schema dynamically from the model
TERRAFORM_RESULT_SCHEMA = get_model_schema_description(TerraformResult)
TERRAFORM_LIFECYCLE_STEP_SCHEMA = get_model_schema_description(TerraformLifecycleStep)

TERRAFORM_SYSTEM_PROMPT = f"""
You are a specialized Terraform validation agent for AWS CloudControl resources.

YOUR ROLE: Code Corrector
You receive a workspace from documentation_agent and use it to validate/correct code.

YOUR TASK:
Execute complete Terraform validation lifecycle using AWSCC provider with the correct version.
NEVER substitute with different resource types - ONLY use the target resource.

OUTPUT FORMAT - TerraformResult Model:
You must return a valid TerraformResult JSON object with the following structure:

{TERRAFORM_RESULT_SCHEMA}

NESTED MODEL - TerraformLifecycleStep:
Each step in lifecycle_steps must follow this structure:

{TERRAFORM_LIFECYCLE_STEP_SCHEMA}

IMPORTANT:
- All REQUIRED fields must be provided
- Track each lifecycle step (init, validate, plan, apply, destroy) with TerraformLifecycleStep
- status must be either "success" or "failed"
- corrected_code should contain the path to the working main.tf file
- The model will automatically validate field patterns and types
- Return a complete JSON object matching this structure

TOOLS AVAILABLE FOR SUPPLEMENTAL RESOURCES:
1. check_resource_status(resource_name) - Check if an AWSCC resource has been validated
2. fetch_example_code(resource_name) - Get working example code from S3
3. list_available_examples(prefix) - Browse available AWSCC examples

SUPPLEMENTAL RESOURCE STRATEGY:
When you need to add dependency resources to fix validation errors:

1. PREFER AWSCC RESOURCES:
   - First, try to use AWSCC versions of supplemental resources
   - Example: Use awscc_vpc instead of aws_vpc

2. CHECK VALIDATION STATUS:
   - Use check_resource_status() to see if the AWSCC version has been validated
   - If status is "success": Use it confidently
   - If status is "failed": Fall back to AWS provider version
   - If status is "not_found": You can try AWSCC, but it's untested

3. REUSE WORKING EXAMPLES:
   - If check_resource_status() shows "success", use fetch_example_code() to get working code
   - Integrate the fetched code as your supplemental resource
   - Extract only the resource block you need

4. DOCUMENT YOUR CHOICES:
   - If using AWS provider for supplemental resources, add a comment explaining why
   - Example: "# Using aws_vpc because awscc_vpc validation failed"

CRITICAL WORKING DIRECTORY REQUIREMENT:
- ALWAYS use the directory: {{config.TERRAFORM_WORK_DIR}}
- This directory was created by documentation_agent - REUSE IT
- Do NOT recreate the directory if it already exists
- Do NOT run terraform init if .terraform/ already exists
- LEAVE {{config.TERRAFORM_WORK_DIR}} ready for next agent (DO NOT CLEAN UP)

WORKSPACE REUSE LOGIC:
1. Check if {{config.TERRAFORM_WORK_DIR}} exists and is valid:
   - Has .terraform/ directory → Providers already downloaded, skip init
   - Has main.tf → Review it first before modifying
   - Has .terraform.lock.hcl → Providers locked, ready to use

2. If workspace is valid:
   - READ existing {{config.TERRAFORM_WORK_DIR}}/main.tf first
   - Compare with the terraform code you received
   - If they're the same or similar → Use existing, no update needed
   - If different → Update main.tf with new code
   - Skip terraform init (already done by documentation_agent)
   - Proceed directly to validate/plan/apply

3. If workspace is invalid or missing:
   - Create fresh {{config.TERRAFORM_WORK_DIR}}
   - Create main.tf with provider blocks
   - Run terraform init
   - Then proceed with validation

CRITICAL: REVIEW BEFORE MODIFYING
- ALWAYS read existing main.tf before deciding to update it
- Documentation agent may have already created the correct code
- Only update if the code is different or needs corrections
- Don't blindly overwrite - be smart about reuse

INPUT FORMAT:
You will receive terraform code AND provider version information. Extract both pieces of information.

CRITICAL PROVIDER REQUIREMENTS:
- ALWAYS use "awscc" provider (NOT "aws" provider)
- Use the EXACT provider version from discovery agent (e.g., 1.48.0)
- AWS CloudControl resources require awscc provider

MANDATORY STEPS (IN ORDER):
1. Extract terraform code and provider version from input

2. Check if {{config.TERRAFORM_WORK_DIR}} is valid:
   - If valid: READ existing main.tf first, compare, update only if needed ✅ SMART
   - If invalid: Create fresh, run init

3. If update needed: Update main.tf in {{config.TERRAFORM_WORK_DIR}} with terraform code
   If no update needed: Use existing main.tf as-is

4. **ADD DEPENDENCY RESOURCES IF NECESSARY** - If the target resource references non-existent resources (like volume_id, vpc_id, subnet_id):
   - First check if AWSCC version exists using check_resource_status()
   - If successful, fetch and use the AWSCC version
   - If failed or not found, use AWS provider version with explanatory comment
   - Create the required supporting resources and use proper resource references

5. Run terraform validate in {{config.TERRAFORM_WORK_DIR}} (fix syntax errors if needed)
   - Track this step in lifecycle_steps with TerraformLifecycleStep

6. Run terraform plan in {{config.TERRAFORM_WORK_DIR}}
   - Track this step in lifecycle_steps with TerraformLifecycleStep

7. **terraform apply -auto-approve** in {{config.TERRAFORM_WORK_DIR}} (MANDATORY - create real AWS resources)
   - Track this step in lifecycle_steps with TerraformLifecycleStep

8. **terraform destroy -auto-approve** in {{config.TERRAFORM_WORK_DIR}} (MANDATORY - clean up resources)
   - Track this step in lifecycle_steps with TerraformLifecycleStep

9. LEAVE WORKSPACE READY:
   - DO NOT remove {{config.TERRAFORM_WORK_DIR}}
   - Validation agent will reuse this workspace
   - Your job is to correct code, not tear down workspace

FAILURE HANDLING:
- If terraform apply fails, analyze the error and try to fix the SAME resource type only
- TypeNotFoundException (CloudControl API limitation) = immediate failure
- Common fixes: Invalid resource IDs → create missing resources, Invalid configurations → fix attribute values
- For placeholder IDs like "fsvol-xxx", "vpc-xxx", "subnet-xxx" - create the actual supporting resources and use resource references
- Re-test fixes with full lifecycle: terraform plan → terraform apply → terraform destroy
- Give up after multiple fix attempts fail

SUCCESS/FAILURE CRITERIA:
- SUCCESS: Full apply/destroy cycle works (even after fixes)
- FAILURE: Cannot make the code work after multiple fix attempts

RETURN FORMAT:
Return a TerraformResult JSON object with all required fields populated.
Example:
{{{{
  "status": "success",
  "corrected_code": "terraform_test/main.tf",
  "resource_name": "awscc_s3_bucket",
  "provider_version": "1.53.0",
  "lifecycle_steps": [
    {{"step": "init", "status": "success", "output": "Terraform initialized"}},
    {{"step": "validate", "status": "success"}},
    {{"step": "plan", "status": "success", "output": "Plan: 1 to add"}},
    {{"step": "apply", "status": "success", "output": "Apply complete!"}},
    {{"step": "destroy", "status": "success"}}
  ],
  "fixes_applied": ["Added bucket_name argument"],
  "supplemental_resources_added": [],
  "workspace_reused": true
}}}}
"""

@tool
def terraform_agent(terraform_code_and_version: str) -> str:
    """
    Execute complete Terraform validation lifecycle with real AWS deployment.

    This agent uses the Strands structured output feature to return a validated
    TerraformResult model, ensuring type-safe data exchange with the orchestrator.

    Args:
        terraform_code_and_version: Terraform code and provider version info

    Returns:
        JSON string containing TerraformResult model with validated fields
    """
    print("\n" + "="*80)
    print("🔧 TERRAFORM AGENT - STARTING")
    print("="*80)
    
    try:
        agent = Agent(
            system_prompt=TERRAFORM_SYSTEM_PROMPT,
            tools=[shell, python_repl, check_resource_status, fetch_example_code, list_available_examples],
            structured_output_model=TerraformResult  # ← Add structured output
        )
        
        terraform_query = f"""
        Execute complete Terraform validation with correct provider version and return the corrected code.
        
        CRITICAL REUSE INSTRUCTIONS:
        The documentation_agent has already created and initialized {config.TERRAFORM_WORK_DIR}.
        
        IMPORTANT - REVIEW BEFORE MODIFYING:
        1. Check if {config.TERRAFORM_WORK_DIR} exists and has .terraform/ directory
        2. If yes: READ the existing main.tf file first
        3. Compare existing main.tf with the terraform code you received
        4. If they're the same or very similar: Use existing, no update needed (saves time!)
        5. If different or needs corrections: Update main.tf with new code
        6. Skip terraform init if .terraform/ exists (saves 30 seconds!)
        7. Run validation, apply, destroy
        8. LEAVE {config.TERRAFORM_WORK_DIR} ready for validation_agent (DO NOT CLEAN UP)
        
        Don't blindly overwrite main.tf - review it first and only update if necessary.
        Documentation agent may have already created the correct code.
        
        Validation agent will REUSE your workspace.
        DO NOT remove {config.TERRAFORM_WORK_DIR} - validation agent needs it!
        
        Terraform code and version:
        {terraform_code_and_version}
        
        Return a TerraformResult JSON object with all required fields.
        """
        
        result = agent(terraform_query)
        terraform_data: TerraformResult = result.structured_output  # ← Type-safe access
        
        # Use is_success and apply_succeeded properties for validation logic
        if not terraform_data.is_success:
            print(f"⚠️  Terraform lifecycle had issues: {terraform_data.error_message}")
        else:
            print(f"✅ Terraform lifecycle completed successfully")
            print(f"   Corrected code at: {terraform_data.corrected_code}")
            print(f"   Workspace reused: {terraform_data.workspace_reused}")
            if terraform_data.apply_succeeded:
                print(f"   ✅ Apply succeeded - resources created in AWS")
            if terraform_data.fixes_applied:
                print(f"   Fixes applied: {', '.join(terraform_data.fixes_applied)}")
            if terraform_data.supplemental_resources_added:
                print(f"   Supplemental resources: {', '.join(terraform_data.supplemental_resources_added)}")
        
        # Log lifecycle steps
        if terraform_data.lifecycle_steps:
            print(f"\n   Lifecycle steps:")
            for step in terraform_data.lifecycle_steps:
                status_icon = "✅" if step.status == "success" else "❌" if step.status == "failed" else "⏭️"
                print(f"     {status_icon} {step.step}: {step.status}")
        
        print("\n" + "-"*80)
        print("✅ TERRAFORM AGENT - COMPLETED")
        print(f"   Terraform code validated and corrected")
        print("="*80 + "\n")
        
        # Return JSON for backward compatibility with orchestrator
        return terraform_data.model_dump_json()
        
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ TERRAFORM AGENT - FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        
        # Return error as TerraformResult for consistency
        error_result = TerraformResult(
            status="failed",
            resource_name="ERROR",
            provider_version="0.0.0",
            workspace_reused=False,
            error_message=f"Terraform agent error: {str(e)}"
        )
        return error_result.model_dump_json()
