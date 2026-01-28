"""
TANGO Multi-Agent Pipeline - Documentation Agent
Specialized agent for generating Terraform code for AWS CloudControl resources

todo: add tool / connect with HashiCorp MCP
"""

from strands import Agent, tool
from strands_tools import python_repl, use_llm, http_request
import config
from .resource_tools import check_resource_status, fetch_example_code, list_available_examples
from .models import DocumentationResult, DiscoveryResult, get_model_schema_description

# Generate schema dynamically from the model
DOCUMENTATION_RESULT_SCHEMA = get_model_schema_description(DocumentationResult)

DOCUMENTATION_SYSTEM_PROMPT = f"""
You are a specialized Terraform documentation generator for AWS CloudControl resources.

YOUR ROLE: Setup Owner
You are responsible for creating and initializing the Terraform workspace that other agents will reuse.

YOUR TASK:
Generate clean Terraform configuration code matching Terraform Registry example patterns.

OUTPUT FORMAT - DocumentationResult Model:
You must return a valid DocumentationResult JSON object with the following structure:

{DOCUMENTATION_RESULT_SCHEMA}

IMPORTANT:
- All REQUIRED fields must be provided
- terraform_code must not be empty (use a comment like "# Error: ..." if generation fails)
- The model will automatically validate field patterns and types
- Return a complete JSON object matching this structure

TOOLS AVAILABLE FOR SUPPLEMENTAL RESOURCES:
1. check_resource_status(resource_name) - Check if an AWSCC resource has been validated
2. fetch_example_code(resource_name) - Get working example code from S3
3. list_available_examples(prefix) - Browse available AWSCC examples

SUPPLEMENTAL RESOURCE STRATEGY:
When your target resource needs supplemental resources (dependencies), follow this approach:

1. PREFER AWSCC RESOURCES:
   - First, try to use AWSCC versions of supplemental resources
   - Example: Use awscc_connect_instance instead of aws_connect_instance

2. CHECK VALIDATION STATUS:
   - Use check_resource_status() to see if the AWSCC version has been validated
   - If status is "success": Great! You can use it confidently
   - If status is "failed": Fall back to AWS provider version
   - If status is "not_found": You can try AWSCC, but it's untested

3. REUSE WORKING EXAMPLES:
   - If check_resource_status() shows "success", use fetch_example_code() to get the working code
   - Integrate the fetched code as your supplemental resource
   - This ensures you're using proven, working configurations
   - Extract only the resource block you need (don't include nested dependencies)

4. DOCUMENT YOUR CHOICES:
   - If using AWS provider for supplemental resources, add a comment explaining why
   - Example: "# Using aws_connect_instance because awscc_connect_instance validation failed"
   - Example: "# Using aws_iam_role (awscc_iam_role not yet validated)"

5. KEEP IT SIMPLE:
   - Don't create deep dependency chains
   - Prefer simple, standalone supplemental resources
   - If fetched example has its own dependencies, extract just the resource block you need

EXAMPLE WORKFLOW:
Target: awscc_connect_workspace (needs a Connect instance)

Step 1: Check if awscc_connect_instance is validated
>>> check_resource_status("awscc_connect_instance")
{{"status": "success", "s3_terraform_link": "examples/resources/awscc_connect_instance/connect_instance.tf"}}

Step 2: Fetch the working example
>>> fetch_example_code("awscc_connect_instance")
[Returns working Terraform code]

Step 3: Integrate into your code
Use the fetched code as your supplemental resource, adjust naming as needed.

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
   - Set workspace_initialized=true after successful init
   
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

RETURN FORMAT:
Return a DocumentationResult JSON object with all required fields populated.
Example:
{{
  "terraform_code": "terraform_test/main.tf",
  "resource_name": "awscc_s3_bucket",
  "provider_version": "1.53.0",
  "workspace_initialized": true,
  "supplemental_resources": ["awscc_iam_role"],
  "supplemental_strategy": "IAM role needed for bucket notifications"
}}
"""

@tool
def documentation_agent(discovery_result: DiscoveryResult) -> str:
    """
    Generate Terraform configuration code for an AWS CloudControl resource.

    Args:
        discovery_result: DiscoveryResult object from discovery_agent containing validated
                         resource name and provider version

    Returns:
        JSON string containing DocumentationResult model
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
            tools=[http_request, use_llm, python_repl, check_resource_status, fetch_example_code, list_available_examples],
            structured_output_model=DocumentationResult  # ← Add structured output
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
        - Resource Name: {discovery_result.resource_name}
        - Provider Version: {discovery_result.provider_version}
        
        Return a DocumentationResult JSON object with all required fields.
        """
        
        print (documentation_query)
        
        result = agent(documentation_query)
        documentation_data: DocumentationResult = result.structured_output  # ← Type-safe access
        
        # Validate before returning
        if not documentation_data.is_success:
            print(f"⚠️  Documentation generation had issues: {documentation_data.error}")
        else:
            print(f"✅ Generated code at: {documentation_data.terraform_code}")
            print(f"   Workspace initialized: {documentation_data.workspace_initialized}")
            if documentation_data.supplemental_resources:
                print(f"   Supplemental resources: {', '.join(documentation_data.supplemental_resources)}")
        
        print("\n" + "-"*80)
        print("✅ DOCUMENTATION AGENT - COMPLETED")
        print(f"   Generated Terraform code")
        print("="*80 + "\n")
        
        # Return JSON for backward compatibility with orchestrator
        return documentation_data.model_dump_json()
        
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ DOCUMENTATION AGENT - FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        
        # Return error as DocumentationResult for consistency
        error_result = DocumentationResult(
            terraform_code="",
            resource_name="ERROR",
            provider_version="0.0.0",
            workspace_initialized=False,
            error=f"Documentation agent error: {str(e)}"
        )
        return error_result.model_dump_json()
