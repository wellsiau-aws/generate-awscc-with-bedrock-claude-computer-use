"""
TANGO Multi-Agent Pipeline - Discovery Agent
Direct API-based discovery for finding unprocessed AWS CloudControl resources
"""

import json
import os
import re
import boto3
import requests
from strands import Agent, tool
from typing import Dict, List, Set
import config
from .models import DiscoveryResult

def get_processed_resources() -> Set[str]:
    """
    Get list of processed resources from DynamoDB.
    
    A resource is considered processed if it has at least one entry with 
    status='success' or status='failed'. This prevents infinite retries of 
    failed resources while allowing new resources to be processed.
    
    Returns:
        Set of resource names that have been processed (success or failed)
    """
    try:
        dynamodb = boto3.client('dynamodb', region_name=config.AWS_REGION)
        
        # Scan the table to get all items
        response = dynamodb.scan(
            TableName=config.DYNAMODB_TABLE,
            ProjectionExpression='resource_name, #status',
            ExpressionAttributeNames={
                '#status': 'status'
            }
        )
        
        # Track resources with successful or failed entries
        processed = set()
        
        for item in response.get('Items', []):
            resource_name = item.get('resource_name', {}).get('S')
            status = item.get('status', {}).get('S')
            
            # Consider resources with success or failed status as "processed"
            if resource_name and status in ('success', 'failed'):
                processed.add(resource_name)
        
        # Handle pagination if there are more items
        while 'LastEvaluatedKey' in response:
            response = dynamodb.scan(
                TableName=config.DYNAMODB_TABLE,
                ProjectionExpression='resource_name, #status',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            
            for item in response.get('Items', []):
                resource_name = item.get('resource_name', {}).get('S')
                status = item.get('status', {}).get('S')
                
                if resource_name and status in ('success', 'failed'):
                    processed.add(resource_name)
        
        return processed
        
    except Exception as e:
        print(f"⚠️  Warning: Could not access DynamoDB: {e}")
        return set()

def get_github_releases() -> List[Dict]:
    """Get recent releases from terraform-provider-awscc GitHub repository."""
    try:
        url = "https://api.github.com/repos/hashicorp/terraform-provider-awscc/releases"
        response = requests.get(url, timeout=30, params={'per_page': 10})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching GitHub releases: {e}")
        return []

def extract_resources_from_release(release: Dict) -> tuple[List[str], str]:
    """Extract new resources and provider version from a release."""
    body = release.get('body', '')
    tag = release.get('tag_name', '')
    
    # Extract provider version (e.g., "v1.49.0" -> "1.49.0")
    version = tag.lstrip('v') if tag else "unknown"
    
    # Find new resources using regex pattern
    pattern = r'\*\*New Resource:\*\*\s*`(awscc_[^`]+)`'
    resources = re.findall(pattern, body, re.IGNORECASE)
    
    return resources, version

def find_unprocessed_resource() -> Dict[str, str]:
    """Find the next unprocessed AWS CloudControl resource."""
    print("🔍 Checking processed resources...")
    processed_resources = get_processed_resources()
    print(f"Found {len(processed_resources)} processed resources")
    
    print("📡 Fetching GitHub releases...")
    releases = get_github_releases()
    
    if not releases:
        return {"resource_name": "NONE", "provider_version": "NONE"}
    
    # Get latest version from the most recent release
    latest_version = releases[0].get('tag_name', '').lstrip('v') if releases else "unknown"
    print(f"🔄 Using latest provider version: {latest_version}")
    
    # Check releases from newest to oldest for unprocessed resources
    for release in releases:
        resources, _ = extract_resources_from_release(release)  # Ignore original version
        print(f"Release {release.get('tag_name', 'unknown')}: {len(resources)} resources")
        
        # Find first unprocessed resource
        for resource in resources:
            if resource not in processed_resources:
                print(f"✅ Found unprocessed resource: {resource} (using latest version {latest_version})")
                return {"resource_name": resource, "provider_version": latest_version}
    
    print("ℹ️ All resources are processed")
    return {"resource_name": "NONE", "provider_version": "NONE"}

@tool
def discovery_agent(query: str) -> str:
    """
    Find the next unprocessed AWS CloudControl resource using direct API calls.
    
    This agent uses the Strands structured output feature to return a validated
    DiscoveryResult model, ensuring type-safe data exchange with the orchestrator.
    
    Args:
        query: Request to find next resource to process
        
    Returns:
        JSON string containing DiscoveryResult model with validated fields
    """
    print("\n" + "="*80)
    print("🔍 DISCOVERY AGENT - STARTING")
    print("="*80)
    
    try:
        # Find unprocessed resource using direct API calls
        result_dict = find_unprocessed_resource()
        
        # Create DiscoveryResult model with validation
        # This will automatically validate the resource_name and provider_version patterns
        discovery_result = DiscoveryResult(
            resource_name=result_dict.get("resource_name", "ERROR"),
            provider_version=result_dict.get("provider_version", "0.0.0"),
            error=result_dict.get("error")
        )
        
        # Use is_valid property for validation logic
        if discovery_result.is_valid:
            print(f"✅ Found valid resource: {discovery_result.resource_name}")
        else:
            print(f"⚠️  No valid resource found: {discovery_result.resource_name}")
        
        print("\n" + "-"*80)
        print("✅ DISCOVERY AGENT - COMPLETED")
        print(f"   Resource: {discovery_result.resource_name}")
        print(f"   Provider Version: {discovery_result.provider_version}")
        print(f"   Valid: {discovery_result.is_valid}")
        print("="*80 + "\n")
        
        # Return JSON for backward compatibility with orchestrator
        return discovery_result.model_dump_json()
        
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ DISCOVERY AGENT - FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        
        # Create error result with validated model
        error_result = DiscoveryResult(
            resource_name="ERROR",
            provider_version="0.0.0",
            error=str(e)
        )
        return error_result.model_dump_json()
