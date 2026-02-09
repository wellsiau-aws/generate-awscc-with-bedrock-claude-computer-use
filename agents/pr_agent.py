"""
TANGO Multi-Agent Pipeline - PR Agent
Standalone agent that creates GitHub pull requests for validated AWSCC resources
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


PR_SYSTEM_PROMPT = """
You are a specialized GitHub Pull Request agent for AWSCC Terraform examples.

YOUR ROLE: PR Creator
You create pull requests to HashiCorp's terraform-provider-awscc repository with validated Terraform examples.

YOUR TASKS:
1. Query DynamoDB for successfully validated resources (source='tango_pipeline')
2. Fetch validated content from S3 (terraform code, templates, analysis)
3. Clone fork repository and create feature branch
4. Place files in correct HashiCorp structure
5. Run required make commands (fmt, docs)
6. Commit changes and push to fork
7. Create GitHub pull request
8. Update DynamoDB with PR status

TOOLS AVAILABLE:
1. get_next_eligible_resource() - Find next TANGO-generated resource ready for PR (atomic)
2. fetch_resource_content(resource_name) - Get S3 content for a resource
3. clone_and_setup_repo(resource_name) - Clone fork, sync with upstream, create branch
4. place_files_in_structure(repo_path, resource_name, content_json) - Place files in HashiCorp structure
5. run_hashicorp_validation(repo_path, resource_name) - Run make fmt and make docs
6. git_commit_and_push(repo_path, resource_name, branch_name) - Commit and push changes
7. create_github_pr(resource_name, branch_name, content_json) - Create GitHub PR
8. update_pr_status(resource_name, pr_url, status) - Update DynamoDB with PR status

WORKFLOW:
1. Query for next eligible resource (source='tango_pipeline', status='success', no pr_status)
2. If resource_name is "NONE", report no eligible resources and exit
3. Fetch S3 content for the resource
4. Clone fork and setup repository
5. Place files in correct structure
6. Run HashiCorp validation (make fmt, make docs)
7. Commit and push changes to fork
8. Create GitHub pull request
9. Update DynamoDB with PR status ('created' or 'failed')
10. Report success with PR URL

IMPORTANT RULES:
- Only process resources with source='tango_pipeline' (distinguishes from pre-existing examples)
- Process exactly ONE resource per execution (atomic operation)
- Always update DynamoDB status, even on failure
- Provide clear error messages for all failure modes
- Clean up workspace on success or failure

ERROR HANDLING:
- If any step fails, update DynamoDB with pr_status='failed'
- Provide detailed error information
- Ensure workspace cleanup happens even on failure
- Report actionable error messages to user

SUCCESS CRITERIA:
- PR created successfully on GitHub
- DynamoDB updated with pr_status='created' and github_pr_url
- All files placed correctly in HashiCorp structure
- make fmt and make docs pass successfully
- Workspace cleaned up
"""


@tool
def git_commit_and_push(repo_path: str, resource_name: str, branch_name: str) -> str:
    """
    Commit changes and push to fork remote.
    
    Args:
        repo_path: Path to the cloned repository
        resource_name: The AWSCC resource name (e.g., "awscc_s3_bucket")
        branch_name: The branch name to push (e.g., "d-awscc_s3_bucket")
    
    Returns:
        JSON with commit hash, push status, and details
    """
    print("\n" + "="*80)
    print(f"📤 GIT COMMIT AND PUSH - Committing changes for {resource_name}")
    print("="*80)
    
    try:
        import git
        from git import Repo
    except ImportError:
        error_msg = "GitPython not installed. Run: pip install GitPython>=3.1.40"
        print(f"\n❌ ERROR: {error_msg}")
        return json.dumps({"status": "error", "error": error_msg})
    
    try:
        print(f"   Repository: {repo_path}")
        print(f"   Branch: {branch_name}")
        
        # Open the repository
        print(f"\n📂 Opening repository...")
        repo = Repo(repo_path)
        
        # Verify we're on the correct branch
        current_branch = repo.active_branch.name
        if current_branch != branch_name:
            raise ValueError(f"Not on expected branch. Current: {current_branch}, Expected: {branch_name}")
        
        print(f"   ✓ On branch: {current_branch}")
        
        # Stage all modified files
        print(f"\n📝 Staging modified files...")
        
        # Get list of modified files
        modified_files = [item.a_path for item in repo.index.diff(None)]
        untracked_files = repo.untracked_files
        
        if not modified_files and not untracked_files:
            raise ValueError("No changes to commit")
        
        print(f"   Modified files: {len(modified_files)}")
        for file in modified_files:
            print(f"      - {file}")
        
        print(f"   Untracked files: {len(untracked_files)}")
        for file in untracked_files:
            print(f"      - {file}")
        
        # Stage all changes
        repo.git.add(A=True)
        print(f"   ✓ All changes staged")
        
        # Create commit with descriptive message
        print(f"\n💬 Creating commit...")
        
        # Extract service name from resource name
        service_name = resource_name.replace('awscc_', '')
        
        # Follow commit message conventions
        commit_message = f"Add example for {resource_name}\n\n"
        commit_message += f"This commit adds a validated Terraform example for the {resource_name} resource.\n\n"
        commit_message += "Files added:\n"
        commit_message += f"- examples/resources/{resource_name}/{service_name}.tf\n"
        commit_message += f"- templates/resources/{resource_name}.md.tmpl\n"
        commit_message += f"- docs/resources/{resource_name}.md (generated by make docs)\n\n"
        commit_message += "The example has been validated through real AWS deployment testing\n"
        commit_message += "and passes all HashiCorp validation requirements.\n\n"
        commit_message += "Generated by TANGO Multi-Agent Pipeline"
        
        print(f"   Message: {commit_message.split(chr(10))[0]}...")
        
        commit = repo.index.commit(commit_message)
        commit_hash = commit.hexsha[:8]
        
        print(f"   ✓ Commit created: {commit_hash}")
        
        # Push branch to fork remote
        print(f"\n🚀 Pushing to fork remote...")
        print(f"   Remote: origin")
        print(f"   Branch: {branch_name}")
        
        # Configure push with authentication if token is available
        push_url = None
        if config.GITHUB_TOKEN and config.GITHUB_FORK_URL:
            fork_url = config.GITHUB_FORK_URL
            if 'github.com/' in fork_url and not fork_url.startswith('git@'):
                # Insert token into URL for authentication
                if fork_url.startswith('https://github.com/'):
                    push_url = fork_url.replace(
                        'https://github.com/',
                        f'https://{config.GITHUB_TOKEN}@github.com/'
                    )
        
        try:
            # Push to origin
            origin = repo.remote('origin')
            
            # If we have a push URL with token, update the remote temporarily
            original_url = None
            if push_url:
                original_url = list(origin.urls)[0]
                origin.set_url(push_url)
            
            # Push the branch
            push_info = origin.push(branch_name)
            
            # Restore original URL if we changed it
            if original_url:
                origin.set_url(original_url)
            
            # Check push result
            if push_info and len(push_info) > 0:
                push_result = push_info[0]
                
                # Check for errors
                if push_result.flags & push_result.ERROR:
                    raise git.exc.GitCommandError(
                        'git push',
                        f"Push failed: {push_result.summary}"
                    )
                
                print(f"   ✓ Push completed successfully")
                print(f"   Summary: {push_result.summary}")
            else:
                print(f"   ✓ Push completed")
        
        except git.exc.GitCommandError as e:
            # Handle push-specific errors
            error_str = str(e)
            
            if 'authentication failed' in error_str.lower() or 'could not read' in error_str.lower():
                raise ValueError(f"Authentication failed. Check GITHUB_TOKEN and permissions.")
            elif 'rejected' in error_str.lower():
                raise ValueError(f"Push rejected. Branch may already exist on remote or conflicts exist.")
            elif 'network' in error_str.lower() or 'connection' in error_str.lower():
                raise ValueError(f"Network error during push: {error_str}")
            else:
                raise ValueError(f"Push failed: {error_str}")
        
        # Verify push succeeded
        print(f"\n🔍 Verifying push...")
        
        try:
            # Fetch to verify the branch exists on remote
            origin.fetch()
            
            # Check if our branch exists on remote
            remote_branches = [ref.name for ref in origin.refs]
            expected_remote_branch = f"origin/{branch_name}"
            
            if expected_remote_branch in remote_branches:
                print(f"   ✓ Branch verified on remote: {branch_name}")
            else:
                print(f"   ⚠️  Could not verify branch on remote (may still be successful)")
        
        except Exception as e:
            print(f"   ⚠️  Could not verify push: {str(e)}")
            print(f"   (Push may still be successful)")
        
        result = {
            "status": "success",
            "commit_hash": commit.hexsha,
            "commit_hash_short": commit_hash,
            "branch_name": branch_name,
            "resource_name": resource_name,
            "files_changed": len(modified_files) + len(untracked_files),
            "commit_message": commit_message
        }
        
        print("\n" + "-"*80)
        print("✅ GIT COMMIT AND PUSH COMPLETED")
        print(f"   Commit: {commit_hash}")
        print(f"   Branch: {branch_name}")
        print(f"   Files changed: {result['files_changed']}")
        print("="*80 + "\n")
        
        return json.dumps(result)
    
    except ValueError as e:
        print("\n" + "-"*80)
        print("❌ GIT COMMIT AND PUSH FAILED - Validation error")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": str(e)})
    
    except git.exc.GitCommandError as e:
        print("\n" + "-"*80)
        print("❌ GIT COMMIT AND PUSH FAILED - Git operation error")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": f"Git operation failed: {str(e)}"})
    
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ GIT COMMIT AND PUSH FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": str(e)})


@tool
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
        with PRStepLogger(logger, 1, "Query for eligible resource", 
                         "Finding next resource ready for PR creation"):
            
            if specific_resource:
                # Use the specified resource
                resource_name = specific_resource
                logger.log_operation(f"Using specified resource: {resource_name}", "success")
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
                
                logger.log_operation(f"Found eligible resource: {resource_name}", "success")
            
            # Update logger with resource name
            logger.resource_name = resource_name
        
        # Step 2: Fetch S3 content
        with PRStepLogger(logger, 2, "Fetch S3 content", 
                         "Retrieving Terraform code, templates, and analysis"):
            
            # Retry S3 operations as they can be transient
            def fetch_content():
                result = fetch_resource_content(resource_name)
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


# Create the agent instance with all tools
pr_agent_instance = Agent(
    name="PR Agent",
    system_prompt=PR_SYSTEM_PROMPT,
    tools=[
        get_next_eligible_resource,
        fetch_resource_content,
        clone_and_setup_repo,
        place_files_in_structure,
        run_hashicorp_validation,
        git_commit_and_push,
        create_github_pr,
        update_pr_status,
        python_repl,
        use_aws
    ]
)


if __name__ == "__main__":
    # Test the agent
    print("Testing PR Agent...")
    result = pr_agent()
    print(f"\nResult: {result}")
