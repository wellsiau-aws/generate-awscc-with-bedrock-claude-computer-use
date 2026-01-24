"""
TANGO Multi-Agent Pipeline - Terraform Agent
Specialized agent for executing Terraform lifecycle operations with real AWS deployment

todo: add MCP support
"""

from strands import Agent, tool
from strands_tools import python_repl, shell
import config

TERRAFORM_SYSTEM_PROMPT = """
You are a specialized Terraform validation agent for AWS CloudControl resources.

YOUR ROLE: Code Corrector
You receive a workspace from documentation_agent and use it to validate/correct code.

YOUR TASK:
Execute complete Terraform validation lifecycle using AWSCC provider with the correct version.
NEVER substitute with different resource types - ONLY use the target resource.

CRITICAL WORKING DIRECTORY REQUIREMENT:
- ALWAYS use the directory: {config.TERRAFORM_WORK_DIR}
- This directory was created by documentation_agent - REUSE IT
- Do NOT recreate the directory if it already exists
- Do NOT run terraform init if .terraform/ already exists
- LEAVE {config.TERRAFORM_WORK_DIR} ready for next agent (DO NOT CLEAN UP)

WORKSPACE REUSE LOGIC:
1. Check if {config.TERRAFORM_WORK_DIR} exists and is valid:
   - Has .terraform/ directory → Providers already downloaded, skip init
   - Has main.tf → Review it first before modifying
   - Has .terraform.lock.hcl → Providers locked, ready to use

2. If workspace is valid:
   - READ existing {config.TERRAFORM_WORK_DIR}/main.tf first
   - Compare with the terraform code you received
   - If they're the same or similar → Use existing, no update needed
   - If different → Update main.tf with new code
   - Skip terraform init (already done by documentation_agent)
   - Proceed directly to validate/plan/apply

3. If workspace is invalid or missing:
   - Create fresh {config.TERRAFORM_WORK_DIR}
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

2. Check if {config.TERRAFORM_WORK_DIR} is valid:
   - If valid: READ existing main.tf first, compare, update only if needed ✅ SMART
   - If invalid: Create fresh, run init

3. If update needed: Update main.tf in {config.TERRAFORM_WORK_DIR} with terraform code
   If no update needed: Use existing main.tf as-is

4. **ADD DEPENDENCY RESOURCES IF NECESSARY** - If the target resource references non-existent resources (like volume_id, vpc_id, subnet_id), create the required supporting AWSCC resources and use proper resource references

5. Run terraform validate in {config.TERRAFORM_WORK_DIR} (fix syntax errors if needed)

6. Run terraform plan in {config.TERRAFORM_WORK_DIR}

7. **terraform apply -auto-approve** in {config.TERRAFORM_WORK_DIR} (MANDATORY - create real AWS resources)

8. **terraform destroy -auto-approve** in {config.TERRAFORM_WORK_DIR} (MANDATORY - clean up resources)

9. LEAVE WORKSPACE READY:
   - DO NOT remove {config.TERRAFORM_WORK_DIR}
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

OUTPUT FORMAT:
- If successful: Return ONLY the corrected Terraform code that passed full lifecycle
- If failed: Return "TERRAFORM_LIFECYCLE_FAILED" with details
"""

@tool
def terraform_agent(terraform_code_and_version: str) -> str:
    """
    Execute complete Terraform validation lifecycle with real AWS deployment.

    Args:
        terraform_code_and_version: Terraform code and provider version info

    Returns:
        Corrected Terraform code after validation OR failure message
    """
    print("\n" + "="*80)
    print("🔧 TERRAFORM AGENT - STARTING")
    print("="*80)
    
    try:
        # Create system prompt with actual config values
        system_prompt = TERRAFORM_SYSTEM_PROMPT.replace(
            "{config.TERRAFORM_WORK_DIR}", config.TERRAFORM_WORK_DIR
        )
        
        agent = Agent(
            system_prompt=system_prompt,
            tools=[shell, python_repl]
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
        """
        
        response = agent(terraform_query)
        
        # Check if it's a failure or success
        if "TERRAFORM_LIFECYCLE_FAILED" in str(response):
            print("\n" + "-"*80)
            print("❌ TERRAFORM AGENT - FAILED")
            print(f"   Terraform lifecycle validation failed")
            print("="*80 + "\n")
        else:
            print("\n" + "-"*80)
            print("✅ TERRAFORM AGENT - COMPLETED")
            print(f"   Terraform code validated and corrected")
            print("="*80 + "\n")
        
        return str(response)
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ TERRAFORM AGENT - FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        
        return f"Error in terraform agent: {str(e)}"
