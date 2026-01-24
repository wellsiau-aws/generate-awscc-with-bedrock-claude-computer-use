"""
TANGO Multi-Agent Pipeline - Documentation Agent
Specialized agent for generating Terraform code for AWS CloudControl resources

todo: add tool / connect with HashiCorp MCP
"""

from strands import Agent, tool
from strands_tools import python_repl, use_llm, http_request
import config

DOCUMENTATION_SYSTEM_PROMPT = """
You are a specialized Terraform documentation generator for AWS CloudControl resources.

YOUR ROLE: Setup Owner
You are responsible for creating and initializing the Terraform workspace that other agents will reuse.

YOUR TASK:
Generate clean Terraform configuration code matching Terraform Registry example patterns.

CRITICAL WORKING DIRECTORY REQUIREMENTS:
⚠️  NEVER create files in the root directory or current working directory
⚠️  ALWAYS work inside: {config.TERRAFORM_WORK_DIR}
⚠️  ALL file operations MUST be inside {config.TERRAFORM_WORK_DIR}
⚠️  ALL terraform commands MUST be run from inside {config.TERRAFORM_WORK_DIR}
⚠️  LEAVE {config.TERRAFORM_WORK_DIR} ready for next agent (DO NOT CLEAN UP)

STEP-BY-STEP PROCESS (FOLLOW EXACTLY):
1. Extract resource name and provider version from input data

2. Check if {config.TERRAFORM_WORK_DIR} already exists:
   - If exists and valid (has .terraform/ and main.tf): REUSE IT
   - If exists but invalid: Remove and create fresh
   - If doesn't exist: Create fresh

3. Create the working directory (if needed):
   - Create directory: {config.TERRAFORM_WORK_DIR}
   - Change into directory: cd {config.TERRAFORM_WORK_DIR}
   
4. Create main.tf INSIDE {config.TERRAFORM_WORK_DIR} (if needed):
   - Path must be: {config.TERRAFORM_WORK_DIR}/main.tf
   - Content:
```
terraform {{
  required_version = ">= 1.0"

  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }}
    awscc = {{
      source  = "hashicorp/awscc"
      version = "~> 1.0"
    }}
  }}
}}
```

5. Run Terraform init FROM INSIDE {config.TERRAFORM_WORK_DIR} (important before using any other terraform command):
   - Command: cd {config.TERRAFORM_WORK_DIR} && terraform init
   - OR: terraform -chdir={config.TERRAFORM_WORK_DIR} init
   
6. Discover resource schema FROM INSIDE {config.TERRAFORM_WORK_DIR}:
   - Command: cd {config.TERRAFORM_WORK_DIR} && terraform providers schema -json | jq '.provider_schemas."registry.terraform.io/hashicorp/awscc".resource_schemas.awscc_RESOURCE_NAME'
   - OR: terraform -chdir={config.TERRAFORM_WORK_DIR} providers schema -json | jq '...'

7. Generate Terraform code:
   - Use EXACT provider version provided (e.g., "1.48.0" becomes "~> 1.48.0")
   - Focus on the AWSCC resource - minimize supporting AWS provider resources
   - Use "example" naming throughout (example-stream, example-consumer)
   - Configure for {config.AWS_REGION} region when region-specific settings needed
   - Add Environment and Name tags when supported

8. LEAVE WORKSPACE READY:
   - DO NOT remove {config.TERRAFORM_WORK_DIR}
   - DO NOT clean up .terraform/ directory
   - Next agents will reuse this workspace
   - Your job is to set it up, not tear it down

COMMAND EXECUTION RULES:
✅ CORRECT: cd {config.TERRAFORM_WORK_DIR} && terraform init
✅ CORRECT: terraform -chdir={config.TERRAFORM_WORK_DIR} init
❌ WRONG: terraform init (runs in root directory!)
❌ WRONG: Creating main.tf before creating {config.TERRAFORM_WORK_DIR}

FILE CREATION RULES:
✅ CORRECT: {config.TERRAFORM_WORK_DIR}/main.tf
❌ WRONG: main.tf (in root directory!)
❌ WRONG: ./main.tf (in root directory!)

REUSE LOGIC:
- If {config.TERRAFORM_WORK_DIR}/.terraform/ exists → Skip terraform init (already initialized)
- If {config.TERRAFORM_WORK_DIR}/main.tf exists → Update it (don't recreate from scratch)
- Reuse existing setup when possible for efficiency

OUTPUT STYLE:
- Keep minimal - essential arguments only for the AWSCC resource
- Maximum 1-2 outputs if absolutely necessary
- Clean, focused configuration like official registry examples
- Avoid complex supporting infrastructure - use simple references or existing resources when possible
- If supporting resources are absolutely required, keep them minimal

OUTPUT: Valid Terraform .tf file content starting with resources (NOT including terraform/provider blocks).
"""

@tool
def documentation_agent(resource_data: str) -> str:
    """
    Generate Terraform configuration code for an AWS CloudControl resource.

    Args:
        resource_data: JSON string or text containing resource name and provider version info

    Returns:
        Complete Terraform configuration code
    """
    print("\n" + "="*80)
    print("📝 DOCUMENTATION AGENT - STARTING")
    print("="*80)
    
    try:
        # Create system prompt with actual config values
        system_prompt = DOCUMENTATION_SYSTEM_PROMPT.replace(
            "{config.AWS_REGION}", config.AWS_REGION
        ).replace(
            "{config.TERRAFORM_WORK_DIR}", config.TERRAFORM_WORK_DIR
        )
        
        agent = Agent(
            system_prompt=system_prompt,
            tools=[http_request, use_llm, python_repl]
        )
        
        documentation_query = f"""
        Generate complete Terraform configuration using this resource information.
        
        CRITICAL SETUP INSTRUCTIONS:
        You are the SETUP OWNER - you create and initialize the workspace.
        
        1. Check if {config.TERRAFORM_WORK_DIR} exists and is valid
        2. If valid (has .terraform/ and main.tf): REUSE it, skip init
        3. If invalid or missing: Create fresh and run terraform init
        4. Generate the resource code
        5. LEAVE {config.TERRAFORM_WORK_DIR} ready for next agent (DO NOT CLEAN UP)
        
        Next agents (terraform_agent and validation_agent) will REUSE your workspace.
        DO NOT remove {config.TERRAFORM_WORK_DIR} - they need it!
        
        Resource information:
        {resource_data}
        """
        
        response = agent(documentation_query)
        
        print("\n" + "-"*80)
        print("✅ DOCUMENTATION AGENT - COMPLETED")
        print(f"   Generated Terraform code")
        print("="*80 + "\n")
        
        return str(response)
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ DOCUMENTATION AGENT - FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        
        return f"Error in documentation agent: {str(e)}"
