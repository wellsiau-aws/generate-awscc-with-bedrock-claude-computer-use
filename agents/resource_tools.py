"""
TANGO Multi-Agent Pipeline - Resource Tools
Tools for querying resource validation status and fetching examples
"""

import json
import boto3
from datetime import datetime
from strands import tool
from typing import Dict, Any
import config


@tool
def check_resource_status(resource_name: str) -> str:
    """
    Check if an AWSCC resource has been successfully validated in the pipeline.
    
    Args:
        resource_name: AWSCC resource name (e.g., "awscc_connect_instance")
        
    Returns:
        JSON string with status information:
        {
            "resource_name": "awscc_connect_instance",
            "status": "success" | "failed" | "not_found",
            "s3_terraform_link": "examples/resources/..." (if success),
            "last_attempt": "2024-01-23T10:30:00" (if exists)
        }
    """
    print(f"🔍 Checking status for: {resource_name}")
    
    try:
        dynamodb = boto3.client('dynamodb', region_name=config.AWS_REGION)
        
        # Query for the resource (get most recent attempt)
        response = dynamodb.query(
            TableName=config.DYNAMODB_TABLE,
            KeyConditionExpression='resource_name = :rname',
            ExpressionAttributeValues={
                ':rname': {'S': resource_name}
            },
            ScanIndexForward=False,  # Latest first
            Limit=1
        )
        
        # No records found
        if not response.get('Items'):
            result = {
                "resource_name": resource_name,
                "status": "not_found"
            }
            print(f"   Status: not_found")
            return json.dumps(result)
        
        # Parse the item
        item = response['Items'][0]
        status = item.get('status', {}).get('S', 'unknown')
        timestamp = int(item.get('timestamp', {}).get('N', 0))
        s3_link = item.get('s3_terraform_link', {}).get('S')
        
        result = {
            "resource_name": resource_name,
            "status": status,
            "last_attempt": datetime.fromtimestamp(timestamp).isoformat()
        }
        
        # Include S3 link if successful
        if status == "success" and s3_link:
            result["s3_terraform_link"] = s3_link
        
        print(f"   Status: {status}")
        if s3_link:
            print(f"   S3 Link: {s3_link}")
        
        return json.dumps(result)
        
    except Exception as e:
        error_result = {
            "resource_name": resource_name,
            "error": str(e)
        }
        print(f"   Error: {str(e)}")
        return json.dumps(error_result)


@tool
def fetch_example_code(resource_name: str) -> str:
    """
    Fetch example Terraform code for a successfully validated AWSCC resource.
    
    Args:
        resource_name: AWSCC resource name (e.g., "awscc_connect_instance")
        
    Returns:
        Terraform code as string, or error message if not found.
    """
    print(f"📥 Fetching example code for: {resource_name}")
    
    try:
        # First check status to get S3 link
        status_json = check_resource_status(resource_name)
        status = json.loads(status_json)
        
        # Check if resource was successful
        if status.get('status') != 'success':
            message = f"No successful example found for {resource_name}. Status: {status.get('status', 'unknown')}"
            print(f"   {message}")
            return message
        
        # Get S3 link
        s3_link = status.get('s3_terraform_link')
        if not s3_link:
            message = f"No S3 link found for {resource_name}"
            print(f"   {message}")
            return message
        
        # Fetch from S3
        s3_client = boto3.client('s3', region_name=config.AWS_REGION)
        response = s3_client.get_object(
            Bucket=config.S3_BUCKET,
            Key=s3_link
        )
        
        code = response['Body'].read().decode('utf-8')
        print(f"   ✅ Fetched {len(code)} characters from S3")
        
        return code
        
    except Exception as e:
        error_message = f"Error fetching example for {resource_name}: {str(e)}"
        print(f"   ❌ {error_message}")
        return error_message


@tool
def list_available_examples(prefix: str = "") -> str:
    """
    List available AWSCC resource examples in S3.
    
    Args:
        prefix: Optional filter (e.g., "awscc_connect" to see all Connect resources)
        
    Returns:
        JSON string with available resources:
        {
            "available_resources": [
                "awscc_connect_instance",
                "awscc_connect_workspace"
            ],
            "count": 2
        }
    """
    print(f"📋 Listing available examples with prefix: '{prefix}'")
    
    try:
        s3_client = boto3.client('s3', region_name=config.AWS_REGION)
        
        # List objects in examples/resources/ directory
        list_prefix = f'examples/resources/{prefix}' if prefix else 'examples/resources/'
        
        response = s3_client.list_objects_v2(
            Bucket=config.S3_BUCKET,
            Prefix=list_prefix,
            Delimiter='/'
        )
        
        # Extract resource names from common prefixes
        resources = []
        for prefix_obj in response.get('CommonPrefixes', []):
            # Extract resource name from path like 'examples/resources/awscc_s3_bucket/'
            resource_name = prefix_obj['Prefix'].rstrip('/').split('/')[-1]
            resources.append(resource_name)
        
        result = {
            "available_resources": sorted(resources),
            "count": len(resources)
        }
        
        print(f"   Found {len(resources)} resources")
        
        return json.dumps(result)
        
    except Exception as e:
        error_result = {
            "error": str(e),
            "available_resources": [],
            "count": 0
        }
        print(f"   Error: {str(e)}")
        return json.dumps(error_result)
