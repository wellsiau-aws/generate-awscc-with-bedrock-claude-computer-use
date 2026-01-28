"""
TANGO Multi-Agent Pipeline - Storage Agent
Specialized agent for storing pipeline results in DynamoDB and S3 (both success and failure)
"""

import json
import os
import boto3
from datetime import datetime
from strands import Agent, tool
from strands_tools import python_repl, use_aws
import config
from agents.models import StorageRequest, StorageResult, get_model_schema_description

# Generate schemas dynamically for both input and output models
STORAGE_REQUEST_SCHEMA = get_model_schema_description(StorageRequest)
STORAGE_RESULT_SCHEMA = get_model_schema_description(StorageResult)

@tool
def template_replacer(resource_name: str, service_name: str, description: str, heading: str) -> str:
    """
    Programmatically replace template variables in the generic template.
    
    Args:
        resource_name: Full resource name (e.g., "awscc_b2bi_capability")
        service_name: Service name without prefix (e.g., "b2bi_capability") 
        description: Brief description for the resource
        heading: Descriptive heading for the example
        
    Returns:
        The processed template content
    """
    try:
        s3_client = boto3.client('s3')
        response = s3_client.get_object(
            Bucket=config.S3_BUCKET,
            Key='templates/resources/generic_resource.md.tmpl'
        )
        template_content = response['Body'].read().decode('utf-8')
        
        replacements = {
            "Description about the first example": description,
            "First example": heading,
            "SERVICE_NAME": service_name
        }
        
        processed_content = template_content
        for old_text, new_text in replacements.items():
            processed_content = processed_content.replace(old_text, new_text)
        
        if "{{ tffile" not in processed_content:
            return "Error: Template processing failed - missing {{ tffile }} pattern"
            
        if "resource \"" in processed_content and "{{ tffile" in processed_content:
            lines = processed_content.split('\n')
            terraform_lines = [i for i, line in enumerate(lines) if "resource \"" in line]
            tffile_lines = [i for i, line in enumerate(lines) if "{{ tffile" in line]
            
            if terraform_lines and tffile_lines:
                return "Error: Template contains both embedded Terraform code and {{ tffile }} - this is incorrect"
        
        return processed_content
        
    except Exception as e:
        return f"Error in template replacement: {str(e)}"

STORAGE_SYSTEM_PROMPT = f"""
You are a specialized storage agent for pipeline results and template generation.

YOUR TASKS:
1. Store pipeline execution results in DynamoDB and S3
2. Generate resource-specific templates from generic template using the template_replacer tool
3. Receive validation results and S3 analysis link from validation agent
4. Create simplified DynamoDB entries with S3 links
5. Return clean, structured execution summary

REGION CONFIGURATION:
- DynamoDB: {config.AWS_REGION} region ({config.DYNAMODB_TABLE} table)
- S3: {config.AWS_REGION} region ({config.S3_BUCKET} bucket)

CRITICAL: Always specify region="{config.AWS_REGION}" in ALL use_aws tool calls.

DYNAMODB SCHEMA ({config.DYNAMODB_TABLE} table):
- resource_name (Partition Key): AWS CloudControl resource name
- timestamp (Sort Key): Unix timestamp
- status: "success" or "failed"
- source: "tango_pipeline" (identifies entries created by the pipeline)
- s3_terraform_link: S3 path to terraform file 
  * SUCCESS: examples/resources/{{resource_name}}/{{service_name}}.tf
  * FAILED: failed/resources/{{resource_name}}/{{service_name}}.tf
- s3_template_link: S3 path to template file (ONLY for success, omit for failures)
  * SUCCESS: templates/resources/{{resource_name}}.md.tmpl
  * FAILED: (not created)
- s3_analysis_link: S3 path to detailed validation results (analysis/resource/{{resource_name}}/{{date}}.txt)

WORKFLOW:
1. Extract service name from resource_name (remove "awscc_" prefix)
2. Extract validation results and S3 analysis link from input
3. Determine if execution was SUCCESS or FAILED
4. Clean up old entries: Query DynamoDB for existing entries with same resource_name AND source=tango_pipeline, if found, delete them
5. Store .tf file directly to S3:
   - SUCCESS: examples/resources/{{resource_name}}/{{service_name}}.tf
   - FAILED: failed/resources/{{resource_name}}/{{service_name}}.tf
6. ONLY FOR SUCCESS: Generate and store template:
   - Use the template_replacer tool to create the resource-specific template
   - Reads generic template from S3: s3://{config.S3_BUCKET}/templates/resources/generic_resource.md.tmpl
   - Pass the resource_name, service_name, a brief description, and a descriptive heading
   - Store template to S3 at templates/resources/{{service_name}}.md.tmpl
7. Create simplified DynamoDB entry with:
   - resource_name (partition key)
   - timestamp (sort key)
   - status (success/failed)
   - source (always set to "tango_pipeline")
   - s3_terraform_link
   - s3_template_link (ONLY for success, omit for failures)
   - s3_analysis_link (from validation agent)
8. Return structured summary

CRITICAL: 
- DO NOT create templates for failed executions. Templates are only for successful examples that can be used in pull requests.
- DO NOT delete entries with source=hashicorp_github, these are original examples created by contributors

TEMPLATE REPLACEMENT EXAMPLES:
- For awscc_s3_bucket: description="Create an S3 bucket with versioning and encryption", heading="Create an S3 bucket"

IMPORTANT: Always use the template_replacer tool - do NOT try to do template replacements manually.

INPUT FORMAT:
You will receive a JSON string containing a StorageRequest object with this structure:

{STORAGE_REQUEST_SCHEMA}

OUTPUT FORMAT:
You must return a JSON string containing a StorageResult object with this structure:

{STORAGE_RESULT_SCHEMA}

EXAMPLE OUTPUT:
{{{{
  "status": "success",
  "resource_name": "awscc_s3_bucket",
  "provider_version": "1.53.0",
  "dynamodb_stored": true,
  "s3_terraform_link": "examples/resources/awscc_s3_bucket.tf",
  "s3_template_link": "templates/resources/awscc_s3_bucket.md.tmpl",
  "s3_analysis_link": "analysis/resource/awscc_s3_bucket.txt",
  "template_generated": true,
  "old_entries_deleted": 2,
  "execution_time": 125.5
}}}}

Note: Templates are only created for successful executions to avoid triggering artifacts for pull requests.
"""

@tool
def storage_agent(storage_request: str) -> str:
    """
    Store pipeline results in DynamoDB and S3, generate resource-specific templates.

    Args:
        storage_request: JSON string with execution results (StorageRequest model)

    Returns:
        JSON string with storage confirmation (StorageResult model)
    """
    print("\n" + "="*80)
    print("💾 STORAGE AGENT - STARTING")
    print("="*80)
    
    try:
        # Parse input to StorageRequest model for validation
        try:
            request = StorageRequest.model_validate_json(storage_request)
            print(f"   Parsed StorageRequest for: {request.resource_name}")
            print(f"   Status: {request.status}")
            print(f"   Validation result: {request.validation_result.validation_result}")
        except Exception as e:
            print(f"   Warning: Failed to parse StorageRequest: {e}")
            print(f"   Continuing with raw JSON input...")
        
        agent = Agent(
            system_prompt=STORAGE_SYSTEM_PROMPT,
            tools=[use_aws, python_repl, template_replacer],
            structured_output_model=StorageResult
        )

        print(storage_request)
        
        response = agent(storage_request)
        
        # Access structured output
        if hasattr(response, 'structured_output') and response.structured_output:
            result = response.structured_output
            print(f"\n   ✅ Structured output validated: {result.status}")
            print(f"   DynamoDB stored: {result.dynamodb_stored}")
            print(f"   S3 Terraform link: {result.s3_terraform_link}")
            if result.s3_template_link:
                print(f"   S3 Template link: {result.s3_template_link}")
            print(f"   S3 Analysis link: {result.s3_analysis_link}")
            print(f"   Template generated: {result.template_generated}")
            print(f"   Old entries deleted: {result.old_entries_deleted}")
            
            # Return JSON for backward compatibility
            json_output = result.model_dump_json()
        else:
            print(f"   ⚠️  No structured output, using raw response")
            json_output = str(response)
        
        print("\n" + "-"*80)
        print("✅ STORAGE AGENT - COMPLETED")
        print(f"   Stored results in DynamoDB and S3")
        print("="*80 + "\n")
        
        return json_output
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ STORAGE AGENT - FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        
        # Return error as StorageResult JSON
        error_result = StorageResult(
            status="failed",
            resource_name="unknown",
            provider_version="0.0.0",
            dynamodb_stored=False,
            s3_terraform_link="failed/resources/unknown.tf",
            s3_analysis_link="analysis/resource/unknown.txt",
            template_generated=False,
            old_entries_deleted=0,
            error=f"Storage agent error: {str(e)}"
        )
        return error_result.model_dump_json()
