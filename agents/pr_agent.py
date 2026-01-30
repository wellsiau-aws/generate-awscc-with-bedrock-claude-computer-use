"""
TANGO Multi-Agent Pipeline - PR Agent
Standalone function act as "agent" that creates GitHub pull requests for validated AWSCC resources
"""

import json
import os
import time
from strands import Agent, tool
from strands_tools import python_repl, use_aws
import config
from agents.pr_tools import (
    get_next_eligible_resource,
    fetch_resource_content,
    clone_and_setup_repo,
    place_files_in_structure,
    run_hashicorp_validation,
    create_github_pr,
    update_pr_status,
    git_commit_and_push,
    PRWorkspaceCleanup
)
from agents.pr_exceptions import (
    PRAgentError,
    ConfigurationError,
    ResourceNotReadyError,
    GitOperationError,
    GitHubAPIError,
    S3OperationError,
    DynamoDBOperationError,
    ValidationError
)
from agents.pr_error_recovery import (
    retry_with_backoff,
    is_transient_error,
    get_actionable_error_message
)
from agents.pr_logging import create_pr_logger, PRStepLogger

def pr_agent(pr_request: str = "{}") -> str:
    """
    Create GitHub pull request for validated AWSCC resource.
    
    This is the main entry point for the PR agent. It coordinates all the steps
    required to create a pull request for a validated AWSCC resource.
    
    Args:
        pr_request: JSON with optional resource_name. If not provided, processes next eligible resource.
                   Example: {"resource_name": "awscc_s3_bucket"} or {}
    
    Returns:
        JSON with PR creation status, PR URL, and details
    """
    # Create logger
    logger = create_pr_logger()
    logger.start()
    
    resource_name = None  # Track resource name for error handling
    
    try:
        # Parse request
        try:
            request = json.loads(pr_request) if pr_request else {}
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in pr_request: {str(e)}")
        
        specific_resource = request.get('resource_name')
        
        if specific_resource:
            logger.log_operation(f"Mode: Specific resource - {specific_resource}", "info")
        else:
            logger.log_operation("Mode: Next eligible resource (atomic)", "info")
        
        # Step 1: Get resource to process
        s3_links_json = None  # Will hold S3 links from get_next_eligible_resource
        
        with PRStepLogger(logger, 1, "Query for eligible resource", 
                         "Finding next resource ready for PR creation"):
            
            if specific_resource:
                # Use the specified resource
                resource_name = specific_resource
                logger.log_operation(f"Using specified resource: {resource_name}", "success")
                # Note: When using specific resource, S3 links will be constructed from conventions
            else:
                # Query for next eligible resource
                logger.log_operation("Querying DynamoDB for next eligible resource...", "progress")
                
                eligible_result = get_next_eligible_resource()
                eligible_data = json.loads(eligible_result)
                
                resource_name = eligible_data.get('resource_name')
                
                if resource_name == "NONE":
                    logger.log_operation("No eligible resources found", "info")
                    
                    print("\n" + "="*80)
                    print("ℹ️  PR AGENT - NO ELIGIBLE RESOURCES")
                    print("   No resources ready for PR creation")
                    print("="*80 + "\n")
                    
                    return json.dumps({
                        "status": "no_resources",
                        "message": "No eligible resources found for PR creation"
                    })
                
                if resource_name == "ERROR":
                    error_msg = eligible_data.get('error', 'Unknown error')
                    raise Exception(f"Failed to query eligible resources: {error_msg}")
                
                # Extract S3 links from eligible_data
                s3_links = {
                    's3_terraform_link': eligible_data.get('s3_terraform_link'),
                    's3_template_link': eligible_data.get('s3_template_link'),
                    's3_analysis_link': eligible_data.get('s3_analysis_link')
                }
                s3_links_json = json.dumps(s3_links)
                
                logger.log_operation(f"Found eligible resource: {resource_name}", "success")
                logger.log_operation(f"S3 links retrieved from DynamoDB", "info")
            
            # Update logger with resource name
            logger.resource_name = resource_name
        
        # Step 2: Fetch S3 content
        with PRStepLogger(logger, 2, "Fetch S3 content", 
                         "Retrieving Terraform code, templates, and analysis"):
            
            # Retry S3 operations as they can be transient
            def fetch_content():
                # Pass S3 links if available (from get_next_eligible_resource)
                result = fetch_resource_content(resource_name, s3_links_json)
                data = json.loads(result)
                if data.get('status') == 'error':
                    raise S3OperationError(data.get('error', 'Unknown S3 error'))
                return result
            
            content_result, fetch_error = retry_with_backoff(
                fetch_content,
                max_attempts=3,
                base_delay=2.0,
                transient_only=True
            )
            
            if fetch_error:
                raise fetch_error
            
            content_data = json.loads(content_result)
            logger.log_operation("Content fetched successfully", "success")
        
        # Step 3: Clone and setup repository
        with PRStepLogger(logger, 3, "Clone and setup repository", 
                         "Cloning fork, syncing with upstream, creating branch"):
            
            repo_result = clone_and_setup_repo(resource_name)
            repo_data = json.loads(repo_result)
            
            if repo_data.get('status') == 'error':
                raise Exception(f"Failed to setup repository: {repo_data.get('error')}")
            
            repo_path = repo_data.get('repo_path')
            branch_name = repo_data.get('branch_name')
            work_dir_name = repo_data.get('work_dir_name')
            
            logger.log_operation(f"Repository setup complete", "success", 
                               f"Path: {repo_path}\nBranch: {branch_name}")
        
        # Use cleanup context manager for remaining steps
        work_dir = os.path.join(config.PR_WORK_DIR, work_dir_name)
        
        try:
            with PRWorkspaceCleanup(work_dir):
                # Step 4: Place files in structure
                with PRStepLogger(logger, 4, "Place files in HashiCorp structure", 
                                 "Creating directories and placing Terraform files"):
                    
                    placement_result = place_files_in_structure(
                        repo_path,
                        resource_name,
                        json.dumps(content_data)
                    )
                    placement_data = json.loads(placement_result)
                    
                    if placement_data.get('status') == 'error':
                        raise Exception(f"Failed to place files: {placement_data.get('error')}")
                    
                    # Track files created
                    files_created = placement_data.get('files_created', [])
                    for file in files_created:
                        logger.add_file_created(file)
                    
                    logger.log_operation("Files placed successfully", "success")
                
                # Step 5: Run HashiCorp validation
                with PRStepLogger(logger, 5, "Run HashiCorp validation", 
                                 "Running make fmt and make docs"):
                    
                    validation_start = time.time()
                    validation_result = run_hashicorp_validation(repo_path, resource_name)
                    validation_duration = time.time() - validation_start
                    validation_data = json.loads(validation_result)
                    
                    if validation_data.get('status') == 'error':
                        raise Exception(f"HashiCorp validation failed: {validation_data.get('error')}")
                    
                    # Track validation results
                    for cmd_result in validation_data.get('commands', []):
                        cmd_name = cmd_result.get('command')
                        cmd_success = cmd_result.get('success', False)
                        logger.add_validation_result(cmd_name, cmd_success)
                    
                    logger.log_operation("Validation passed", "success", 
                                       f"Duration: {validation_duration:.2f}s")
                
                # Step 6: Commit and push changes
                with PRStepLogger(logger, 6, "Commit and push changes", 
                                 "Staging files, creating commit, pushing to fork"):
                    
                    commit_result = git_commit_and_push(repo_path, resource_name, branch_name)
                    commit_data = json.loads(commit_result)
                    
                    if commit_data.get('status') == 'error':
                        raise Exception(f"Failed to commit and push: {commit_data.get('error')}")
                    
                    commit_hash = commit_data.get('commit_hash')
                    logger.log_operation("Changes committed and pushed", "success", 
                                       f"Commit: {commit_hash[:8] if commit_hash else 'N/A'}")
                
                # Step 7: Create GitHub PR
                with PRStepLogger(logger, 7, "Create GitHub pull request", 
                                 "Creating PR via GitHub API"):
                    
                    pr_result = create_github_pr(
                        resource_name,
                        branch_name,
                        json.dumps(content_data)
                    )
                    pr_data = json.loads(pr_result)
                    
                    if pr_data.get('status') == 'error':
                        raise Exception(f"Failed to create PR: {pr_data.get('error')}")
                    
                    pr_url = pr_data.get('pr_url')
                    pr_number = pr_data.get('pr_number')
                    
                    logger.log_operation("Pull request created", "success", 
                                       f"PR #{pr_number}: {pr_url}")
                
                # Step 8: Update DynamoDB status
                with PRStepLogger(logger, 8, "Update DynamoDB status", 
                                 "Recording PR creation in database"):
                    
                    status_result = update_pr_status(resource_name, pr_url, 'created')
                    status_data = json.loads(status_result)
                    
                    if status_data.get('status') == 'error':
                        logger.log_operation(
                            f"Warning: Failed to update DynamoDB: {status_data.get('error')}", 
                            "warning"
                        )
                        logger.log_operation("PR was created successfully, but status update failed", "warning")
                    else:
                        logger.log_operation("DynamoDB updated with PR status", "success")
                
                # Success! Log completion with summary
                logger.complete(
                    pr_url=pr_url,
                    pr_number=pr_number,
                    branch_name=branch_name,
                    commit_hash=commit_data.get('commit_hash_short')
                )
                
                result = {
                    "status": "success",
                    "resource_name": resource_name,
                    "pr_url": pr_url,
                    "pr_number": pr_number,
                    "branch_name": branch_name,
                    "commit_hash": commit_data.get('commit_hash_short'),
                    "files_created": placement_data.get('files_created', []),
                    "message": f"Successfully created PR for {resource_name}"
                }
                
                return json.dumps(result)
        
        except Exception as e:
            # Error occurred - update DynamoDB with failed status
            logger.log_operation(f"Error occurred: {str(e)}", "error")
            logger.log_operation("Updating DynamoDB with failed status...", "progress")
            
            try:
                status_result = update_pr_status(resource_name, None, 'failed')
                status_data = json.loads(status_result)
                
                if status_data.get('status') == 'error':
                    logger.log_operation(f"Failed to update DynamoDB: {status_data.get('error')}", "warning")
                else:
                    logger.log_operation("DynamoDB updated with failed status", "success")
            except Exception as status_error:
                logger.log_operation(f"Failed to update DynamoDB: {str(status_error)}", "warning")
            
            # Re-raise the original exception with proper type
            if isinstance(e, PRAgentError):
                raise
            else:
                # Wrap unexpected errors
                raise PRAgentError(f"Unexpected error: {str(e)}", {"original_type": type(e).__name__})
    
    except ConfigurationError as e:
        # Configuration error - missing or invalid config
        logger.fail(str(e), "ConfigurationError")
        
        # Provide actionable error message
        print("\n" + get_actionable_error_message(e))
        print("\n")
        
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": "ConfigurationError",
            "exit_code": 1,
            "missing_config": e.missing_config,
            "actionable_message": get_actionable_error_message(e)
        })
    
    except ResourceNotReadyError as e:
        # Resource not ready for PR
        logger.fail(str(e), "ResourceNotReadyError")
        
        # Provide actionable error message
        print("\n" + get_actionable_error_message(e))
        print("\n")
        
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": "ResourceNotReadyError",
            "exit_code": 2,
            "resource_name": e.resource_name,
            "reason": e.reason,
            "actionable_message": get_actionable_error_message(e)
        })
    
    except GitOperationError as e:
        # Git operation failed
        logger.fail(str(e), "GitOperationError")
        
        # Provide actionable error message
        print("\n" + get_actionable_error_message(e))
        print("\n")
        
        # Update DynamoDB with failed status if we have a resource name
        if resource_name:
            try:
                update_pr_status(resource_name, None, 'failed')
            except Exception:
                pass  # Ignore DynamoDB update errors here
        
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": "GitOperationError",
            "exit_code": 3,
            "operation": e.operation,
            "resource_name": resource_name,
            "actionable_message": get_actionable_error_message(e)
        })
    
    except GitHubAPIError as e:
        # GitHub API error
        logger.fail(str(e), "GitHubAPIError")
        
        # Provide actionable error message
        print("\n" + get_actionable_error_message(e))
        print("\n")
        
        # Update DynamoDB with failed status if we have a resource name
        if resource_name:
            try:
                update_pr_status(resource_name, None, 'failed')
            except Exception:
                pass  # Ignore DynamoDB update errors here
        
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": "GitHubAPIError",
            "exit_code": 4,
            "status_code": e.status_code,
            "resource_name": resource_name,
            "actionable_message": get_actionable_error_message(e)
        })
    
    except (S3OperationError, DynamoDBOperationError, ValidationError) as e:
        # Other specific PR agent errors
        logger.fail(str(e), type(e).__name__)
        
        # Update DynamoDB with failed status if we have a resource name
        if resource_name:
            try:
                update_pr_status(resource_name, None, 'failed')
            except Exception:
                pass  # Ignore DynamoDB update errors here
        
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "exit_code": 5,
            "resource_name": resource_name
        })
    
    except PRAgentError as e:
        # Generic PR agent error
        logger.fail(str(e), "PRAgentError")
        
        # Update DynamoDB with failed status if we have a resource name
        if resource_name:
            try:
                update_pr_status(resource_name, None, 'failed')
            except Exception:
                pass  # Ignore DynamoDB update errors here
        
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": "PRAgentError",
            "exit_code": 5,
            "resource_name": resource_name
        })
    
    except Exception as e:
        # Unexpected error - should not happen if all errors are properly caught
        logger.fail(str(e), type(e).__name__)
        
        # Update DynamoDB with failed status if we have a resource name
        if resource_name:
            try:
                update_pr_status(resource_name, None, 'failed')
            except Exception:
                pass  # Ignore DynamoDB update errors here
        
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "exit_code": 99,
            "resource_name": resource_name
        })