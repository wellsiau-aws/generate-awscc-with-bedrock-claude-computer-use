"""
TANGO Multi-Agent Pipeline - Validation Agent
Independent reviewer that validates terraform agent's work by running apply/destroy
"""

from strands import Agent, tool
from strands_tools import python_repl, shell, use_aws
from datetime import datetime
import json
import config
from .models import ValidationResult, TerraformResult, get_model_schema_description

# Generate schema dynamically from the model
VALIDATION_RESULT_SCHEMA = get_model_schema_description(ValidationResult)

VALIDATION_SYSTEM_PROMPT = f"""
You are an independent validation agent that reviews terraform agent's work.

YOUR ROLE: Independent Verifier
You receive a workspace from terraform_agent and use it to independently verify the code works.

YOUR INDEPENDENCE:
- Independent in JUDGMENT: Don't trust terraform_agent's success claim, verify yourself
- NOT independent in ENVIRONMENT: Reuse workspace for efficiency (saves 30 seconds!)
- Run your own apply/destroy to confirm it actually works

OUTPUT FORMAT - ValidationResult Model:
You must return a valid ValidationResult JSON object with the following structure:

{VALIDATION_RESULT_SCHEMA}

IMPORTANT:
- All REQUIRED fields must be provided
- terraform_steps should be a dict with step names as keys and status as values
- s3_analysis_path must match pattern: ^analysis/resource/[^/]+/.*\.txt$
- The model will automatically validate field patterns and types
- Return a complete JSON object matching this structure

CRITICAL WORKING DIRECTORY REQUIREMENT:
- ALWAYS use the directory: {config.TERRAFORM_WORK_DIR}
- This directory was created by documentation_agent and used by terraform_agent
- REUSE IT - don't recreate unless invalid
- Do NOT run terraform init if .terraform/ already exists
- LEAVE {config.TERRAFORM_WORK_DIR} for orchestrator cleanup (DO NOT CLEAN UP)

WORKSPACE REUSE LOGIC:
1. Check if {config.TERRAFORM_WORK_DIR} exists and is valid:
   - Has .terraform/ directory → Providers already downloaded, skip init
   - Has main.tf → Review it first before modifying
   - Has .terraform.lock.hcl → Providers locked, ready to use

2. If workspace is valid:
   - READ existing {config.TERRAFORM_WORK_DIR}/main.tf first
   - Compare with the code you need to validate
   - If they're the same → Use existing, no update needed
   - If different → Update main.tf with code to validate
   - Skip terraform init (already done by documentation_agent)
   - Proceed directly to validate/plan/apply

3. If workspace is invalid or missing:
   - Create fresh {config.TERRAFORM_WORK_DIR}
   - Create main.tf with provider blocks
   - Run terraform init
   - Then proceed with validation

CRITICAL: REVIEW BEFORE MODIFYING
- ALWAYS read existing main.tf before deciding to update it
- Terraform agent may have already set up the correct code
- Only update if the code is different
- Don't blindly overwrite - be smart about reuse

YOUR TASK:
1. Take the terraform code from terraform agent
2. Run independent apply/destroy test to confirm it actually works
3. Verify the example contains the target resource
4. Store detailed validation results in S3 as plain text
5. Return simple success/failed status

REGION CONFIGURATION:
- S3 bucket to store results: {config.AWS_REGION} region ({config.S3_BUCKET} bucket)
- AWS operations: {config.AWS_REGION} region

CRITICAL REQUIREMENTS:
- You are INDEPENDENT from terraform agent - run your own tests
- Use AWSCC provider with correct version
- Must run actual terraform apply and destroy
- Check that target resource is in the Terraform code
- If terraform apply fails for any reason, mark as FAILED
- Store detailed logs in S3 ({config.S3_BUCKET} at analysis/resource/{{resource_name}}/{{YYYY-MM-DD-HH-MM-SS}}.txt
- NEVER MODIFY OR FIX CODE - test exactly as provided by terraform agent

VALIDATION STEPS:
1. Extract terraform code and resource name

2. Verify code contains target resource (e.g., "awscc_s3_bucket")

3. Check if {config.TERRAFORM_WORK_DIR} is valid:
   - If valid: READ existing main.tf first, compare, update only if needed ✅ SMART
   - If invalid: Create fresh, run init

4. If update needed: Update main.tf in {config.TERRAFORM_WORK_DIR} with code to validate
   If no update needed: Use existing main.tf as-is

5. Run terraform validate in {config.TERRAFORM_WORK_DIR} (skip init if .terraform/ exists)

6. Run terraform plan in {config.TERRAFORM_WORK_DIR}

7. Run terraform apply -auto-approve in {config.TERRAFORM_WORK_DIR} (create real resources) - DO NOT MODIFY THE CODE, test it exactly as provided

8. Run terraform destroy -auto-approve in {config.TERRAFORM_WORK_DIR} (clean up)

9. Store detailed results in S3 ({config.S3_BUCKET} at analysis/resource/{{resource_name}}/{{YYYY-MM-DD-HH-MM-SS}}.txt

10. LEAVE WORKSPACE FOR ORCHESTRATOR:
    - DO NOT remove {config.TERRAFORM_WORK_DIR}
    - Orchestrator will handle final cleanup
    - Your job is to validate, not tear down

11. Return validation status

OUTPUT FORMAT:
Use this exact format for all validation reports:

TERRAFORM VALIDATION REPORT
==========================
Date: {{current_date_time}}
Resource Name: {{resource_name}}

TARGET RESOURCE VERIFICATION
----------------------------
Target resource found in Terraform code: {{details}}
Resource definition includes required parameters: {{list}}

TERRAFORM LIFECYCLE TESTING
--------------------------
terraform init: {{status or "skipped - reused existing"}}
terraform validate: {{status}}
terraform plan: {{status and details}}
terraform apply: {{status and created resources}}
terraform destroy: {{status}}

RESOURCE VERIFICATION
-------------------
Target resource was successfully provisioned: {{details}}
Resource details: {{specific details}}
All resources were properly destroyed: {{status}}

VALIDATION RESULT
----------------
RESULT: PASSED/FAILED
DETAILS: {{brief summary}}

INTERNAL VALIDATION LOGIC (do not include in report):
- SUCCESS requires: target resource found AND all terraform steps succeed
- FAILURE occurs if: target resource missing OR any terraform step fails
- Use this logic to determine validation_result: "success" or "failed"
IMPORTANT: There are NO exceptions to apply failure. If terraform apply fails for ANY reason (including placeholder values, invalid ARNs, missing resources, etc.), the validation result MUST be "failed". Do not make excuses or exceptions.

TARGET RESOURCE CONFIRMATION:
- Check that Terraform code contains the specific target resource
- Example: If target is "awscc_s3_bucket", code must contain "resource \"awscc_s3_bucket\""
- NOT just any resource, but the SPECIFIC target resource requested
- If target resource missing from code = validation_result: "failed"
- Target resource not found in plan/apply
- Resources not properly cleaned up

OUTPUT FORMAT:
Return a ValidationResult JSON object with all required fields populated.
Example:
{{
  "validation_result": "success",
  "resource_name": "awscc_s3_bucket",
  "provider_version": "1.53.0",
  "s3_analysis_path": "analysis/resource/awscc_s3_bucket/2026-01-27-18-30-45.txt",
  "terraform_steps": {{
    "init": "success",
    "validate": "success",
    "plan": "success",
    "apply": "success",
    "destroy": "success"
  }},
  "target_resource_confirmed": true,
  "workspace_reused": true
}}
"""

@tool
def validation_agent(terraform_result: TerraformResult) -> str:
    """
    Independent validation of terraform agent's work.
    
    This agent uses the Strands structured output feature to return a validated
    ValidationResult model, ensuring type-safe data exchange with the orchestrator.
    
    Args:
        terraform_result: TerraformResult object from terraform_agent containing
                         validated corrected code path, resource name, and provider version
        
    Returns:
        JSON string containing ValidationResult model with validated fields
    """
    print("\n" + "="*80)
    print("✓ VALIDATION AGENT - STARTING")
    print("="*80)
    
    try:
        # Handle both dict and object inputs (Strands may serialize to dict)
        if isinstance(terraform_result, dict):
            corrected_code = terraform_result.get('corrected_code')
            resource_name = terraform_result.get('resource_name')
            provider_version = terraform_result.get('provider_version')
            status = terraform_result.get('status')
            workspace_reused = terraform_result.get('workspace_reused', False)
            apply_succeeded = terraform_result.get('apply_succeeded', False)
            fixes_applied = terraform_result.get('fixes_applied', [])
            supplemental_resources_added = terraform_result.get('supplemental_resources_added', [])
        else:
            corrected_code = terraform_result.corrected_code
            resource_name = terraform_result.resource_name
            provider_version = terraform_result.provider_version
            status = terraform_result.status
            workspace_reused = terraform_result.workspace_reused
            apply_succeeded = terraform_result.apply_succeeded
            fixes_applied = terraform_result.fixes_applied
            supplemental_resources_added = terraform_result.supplemental_resources_added
        
        print(f"📋 Resource: {resource_name}")
        print(f"📦 Provider Version: {provider_version}")
        print(f"📁 Corrected Code: {corrected_code}")
        print(f"✅ Terraform Status: {status}")
        
        agent = Agent(
            system_prompt=VALIDATION_SYSTEM_PROMPT,
            tools=[shell, python_repl, use_aws],
            structured_output_model=ValidationResult  # ← Add structured output
        )
        
        validation_query = f"""
        Perform independent validation of the terraform agent's work.
        
        CRITICAL REUSE INSTRUCTIONS:
        The terraform_agent has already used {config.TERRAFORM_WORK_DIR} for validation.
        
        IMPORTANT - REVIEW BEFORE MODIFYING:
        1. Check if {config.TERRAFORM_WORK_DIR} exists and has .terraform/ directory
        2. If yes: READ the existing main.tf file first
        3. Compare existing main.tf with the code you need to validate
        4. If they're the same: Use existing, no update needed (saves time!)
        5. If different: Update main.tf with code to validate
        6. Skip terraform init if .terraform/ exists (saves 30 seconds!)
        7. Run your own independent apply/destroy to verify
        8. Store results to S3 {config.S3_BUCKET}
        9. LEAVE {config.TERRAFORM_WORK_DIR} for orchestrator cleanup (DO NOT CLEAN UP)
        
        Don't blindly overwrite main.tf - review it first and only update if necessary.
        Terraform agent may have already set up the correct code.
        
        You are independent in JUDGMENT (verify it works), not in ENVIRONMENT (reuse for efficiency).
        
        Terraform result information from terraform_agent:
        - Corrected Code Path: {corrected_code}
        - Resource Name: {resource_name}
        - Provider Version: {provider_version}
        - Terraform Agent Status: {status}
        - Workspace Reused: {workspace_reused}
        - Apply Succeeded: {apply_succeeded}
        - Fixes Applied: {fixes_applied}
        - Supplemental Resources: {supplemental_resources_added}
        
        Return a ValidationResult JSON object with all required fields.
        """

        print(validation_query)
        
        result = agent(validation_query)
        validation_data: ValidationResult = result.structured_output  # ← Type-safe access
        
        # Use is_success and all_steps_passed properties for validation logic
        if not validation_data.is_success:
            print(f"⚠️  Validation had issues: {validation_data.error}")
        else:
            print(f"✅ Validation completed successfully")
            print(f"   Resource: {validation_data.resource_name}")
            print(f"   S3 Analysis Path: {validation_data.s3_analysis_path}")
            print(f"   Target resource confirmed: {validation_data.target_resource_confirmed}")
            print(f"   Workspace reused: {validation_data.workspace_reused}")
            if validation_data.all_steps_passed:
                print(f"   ✅ All Terraform steps passed")
        
        # Log terraform steps
        if validation_data.terraform_steps:
            print(f"\n   Terraform steps:")
            for step, status in validation_data.terraform_steps.items():
                status_icon = "✅" if status == "success" else "❌" if status == "failed" else "⏭️"
                print(f"     {status_icon} {step}: {status}")
        
        print("\n" + "-"*80)
        if validation_data.validation_result == "success":
            print("✅ VALIDATION AGENT - COMPLETED (PASSED)")
        else:
            print("❌ VALIDATION AGENT - COMPLETED (FAILED)")
        print(f"   Resource: {validation_data.resource_name}")
        print(f"   S3 Path: {validation_data.s3_analysis_path}")
        print("="*80 + "\n")
        
        # Return JSON for backward compatibility with orchestrator
        return validation_data.model_dump_json()
        
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ VALIDATION AGENT - FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        
        # Return error as ValidationResult for consistency
        error_result = ValidationResult(
            validation_result="failed",
            resource_name="ERROR",
            provider_version="0.0.0",
            s3_analysis_path="analysis/resource/error/error.txt",
            workspace_reused=False,
            error=f"Validation agent error: {str(e)}"
        )
        return error_result.model_dump_json()
