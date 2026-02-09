"""
TANGO Multi-Agent Pipeline - PR Agent Error Recovery
Helper functions for error recovery, retry logic, and actionable error messages
"""

import time
import json
from typing import Callable, Any, Optional, Tuple
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


def is_transient_error(error: Exception) -> bool:
    """
    Determine if an error is transient and can be retried.
    
    Args:
        error: The exception to check
    
    Returns:
        True if the error is transient and can be retried
    """
    # Network-related errors are usually transient
    error_str = str(error).lower()
    
    if 'network' in error_str or 'connection' in error_str:
        return True
    
    if 'timeout' in error_str or 'timed out' in error_str:
        return True
    
    if 'temporarily unavailable' in error_str:
        return True
    
    # GitHub API rate limiting is transient
    if isinstance(error, GitHubAPIError):
        if error.is_rate_limit():
            return True
        # 502, 503, 504 are transient server errors
        if error.status_code in [502, 503, 504]:
            return True
    
    # Some git operations can be transient
    if isinstance(error, GitOperationError):
        if 'network' in error_str or 'connection' in error_str:
            return True
        if 'timeout' in error_str:
            return True
    
    # S3 and DynamoDB throttling errors are transient
    if isinstance(error, (S3OperationError, DynamoDBOperationError)):
        if 'throttl' in error_str or 'rate' in error_str:
            return True
        if 'service unavailable' in error_str:
            return True
    
    return False


def get_retry_delay(attempt: int, base_delay: float = 2.0, max_delay: float = 60.0) -> float:
    """
    Calculate exponential backoff delay for retry attempts.
    
    Args:
        attempt: The current attempt number (1-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
    
    Returns:
        Delay in seconds before next retry
    """
    # Exponential backoff: base_delay * 2^(attempt-1)
    delay = base_delay * (2 ** (attempt - 1))
    
    # Cap at max_delay
    return min(delay, max_delay)


def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    transient_only: bool = True
) -> Tuple[Any, Optional[Exception]]:
    """
    Retry a function with exponential backoff.
    
    Args:
        func: The function to retry (should take no arguments)
        max_attempts: Maximum number of attempts
        base_delay: Base delay in seconds between retries
        max_delay: Maximum delay in seconds
        transient_only: Only retry transient errors
    
    Returns:
        Tuple of (result, error) where:
        - result is the function result if successful
        - error is the last exception if all attempts failed
    """
    last_error = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            result = func()
            
            # Success!
            if attempt > 1:
                print(f"   ✓ Retry succeeded on attempt {attempt}")
            
            return result, None
        
        except Exception as e:
            last_error = e
            
            # Check if we should retry
            should_retry = False
            
            if transient_only:
                should_retry = is_transient_error(e)
            else:
                should_retry = True
            
            # Don't retry on last attempt
            if attempt >= max_attempts:
                should_retry = False
            
            if should_retry:
                delay = get_retry_delay(attempt, base_delay, max_delay)
                
                print(f"   ⚠️  Attempt {attempt} failed: {str(e)[:100]}")
                print(f"   ⏳ Retrying in {delay:.1f} seconds...")
                
                time.sleep(delay)
            else:
                # Don't retry, return the error
                if attempt < max_attempts:
                    print(f"   ❌ Non-transient error, not retrying: {str(e)[:100]}")
                
                break
    
    return None, last_error


def get_actionable_error_message(error: Exception) -> str:
    """
    Generate an actionable error message with suggestions for fixing the error.
    
    Args:
        error: The exception to generate a message for
    
    Returns:
        Actionable error message with suggestions
    """
    error_str = str(error).lower()
    
    # Configuration errors
    if isinstance(error, ConfigurationError):
        message = "Configuration Error:\n"
        message += f"  {str(error)}\n\n"
        message += "How to fix:\n"
        
        if error.missing_config:
            message += "  Missing configuration:\n"
            for config_key in error.missing_config:
                message += f"    - {config_key}\n"
            message += "\n"
        
        message += "  1. Create or update .env file in project root:\n"
        message += "     GITHUB_TOKEN=your_github_token_here\n"
        message += "     GITHUB_FORK_URL=https://github.com/your-username/terraform-provider-awscc\n"
        message += "     GIT_USER_NAME=Your Name\n"
        message += "     GIT_USER_EMAIL=your.email@example.com\n\n"
        message += "  2. Or set environment variables:\n"
        message += "     export GITHUB_TOKEN='your_token'\n"
        message += "     export GITHUB_FORK_URL='https://github.com/your-username/terraform-provider-awscc'\n"
        
        return message
    
    # Resource not ready errors
    if isinstance(error, ResourceNotReadyError):
        message = "Resource Not Ready:\n"
        message += f"  {str(error)}\n\n"
        
        if error.resource_name:
            message += f"  Resource: {error.resource_name}\n"
        if error.reason:
            message += f"  Reason: {error.reason}\n"
        
        message += "\nPossible causes:\n"
        message += "  - Resource not found in DynamoDB\n"
        message += "  - Resource status is not 'success'\n"
        message += "  - Resource source is not 'tango_pipeline'\n"
        message += "  - Required S3 files are missing\n"
        message += "  - Resource already has a PR (pr_status='created')\n\n"
        message += "What to do:\n"
        message += "  - Check DynamoDB for resource status\n"
        message += "  - Verify S3 files exist\n"
        message += "  - Run the TANGO pipeline to validate the resource\n"
        
        return message
    
    # Git operation errors
    if isinstance(error, GitOperationError):
        message = "Git Operation Failed:\n"
        message += f"  {str(error)}\n\n"
        
        if error.operation:
            message += f"  Operation: {error.operation}\n"
        
        message += "\nCommon causes and fixes:\n"
        
        if 'authentication' in error_str or 'permission' in error_str:
            message += "  Authentication failure:\n"
            message += "    - Check GITHUB_TOKEN is valid and not expired\n"
            message += "    - Verify token has 'repo' scope permissions\n"
            message += "    - Ensure token has access to the fork repository\n"
        
        elif 'network' in error_str or 'connection' in error_str:
            message += "  Network error:\n"
            message += "    - Check internet connection\n"
            message += "    - Verify GitHub is accessible (https://www.githubstatus.com/)\n"
            message += "    - Try again in a few minutes\n"
        
        elif 'conflict' in error_str or 'merge' in error_str:
            message += "  Merge conflict:\n"
            message += "    - Fork may be out of sync with upstream\n"
            message += "    - Manually sync fork with upstream main branch\n"
            message += "    - Delete conflicting branch and try again\n"
        
        elif 'rejected' in error_str or 'non-fast-forward' in error_str:
            message += "  Push rejected:\n"
            message += "    - Branch may already exist on remote\n"
            message += "    - Delete remote branch and try again\n"
            message += "    - Or use a different branch name\n"
        
        else:
            message += "  General git error:\n"
            message += "    - Check git configuration\n"
            message += "    - Verify repository access\n"
            message += "    - Check error message for specific details\n"
        
        return message
    
    # GitHub API errors
    if isinstance(error, GitHubAPIError):
        message = "GitHub API Error:\n"
        message += f"  {str(error)}\n\n"
        
        if error.status_code:
            message += f"  HTTP Status: {error.status_code}\n\n"
        
        message += "What to do:\n"
        
        if error.is_authentication_error():
            message += "  Authentication failed:\n"
            message += "    - Check GITHUB_TOKEN is valid\n"
            message += "    - Verify token has not expired\n"
            message += "    - Ensure token has 'repo' scope\n"
        
        elif error.is_rate_limit():
            message += "  Rate limit exceeded:\n"
            message += "    - Wait 60 minutes for rate limit to reset\n"
            message += "    - Check rate limit status: https://api.github.com/rate_limit\n"
            message += "    - Consider using a different token\n"
        
        elif error.is_not_found():
            message += "  Repository not found:\n"
            message += "    - Verify GITHUB_FORK_URL is correct\n"
            message += "    - Check GITHUB_UPSTREAM_URL is correct\n"
            message += "    - Ensure token has access to the repository\n"
        
        elif error.is_pr_exists():
            message += "  Pull request already exists:\n"
            message += "    - Check GitHub for existing PRs\n"
            message += "    - Close or merge existing PR first\n"
            message += "    - Or use a different branch name\n"
        
        else:
            message += "  General GitHub API error:\n"
            message += "    - Check GitHub status: https://www.githubstatus.com/\n"
            message += "    - Verify API access and permissions\n"
            message += "    - Try again in a few minutes\n"
        
        return message
    
    # Validation errors
    if isinstance(error, ValidationError):
        message = "Validation Failed:\n"
        message += f"  {str(error)}\n\n"
        
        if error.command:
            message += f"  Command: {error.command}\n"
        if error.returncode is not None:
            message += f"  Return code: {error.returncode}\n"
        
        message += "\nWhat to do:\n"
        message += "  - Check the command output for specific errors\n"
        message += "  - Verify make is installed and in PATH\n"
        message += "  - Ensure repository structure is correct\n"
        message += "  - Check that all required files are present\n"
        
        if error.stderr:
            message += f"\nError output:\n{error.stderr[:500]}\n"
        
        return message
    
    # S3 operation errors
    if isinstance(error, S3OperationError):
        message = "S3 Operation Failed:\n"
        message += f"  {str(error)}\n\n"
        
        if error.s3_key:
            message += f"  S3 Key: {error.s3_key}\n"
        if error.operation:
            message += f"  Operation: {error.operation}\n"
        
        message += "\nWhat to do:\n"
        message += "  - Verify S3 bucket exists and is accessible\n"
        message += "  - Check AWS credentials are valid\n"
        message += "  - Ensure file exists in S3\n"
        message += "  - Verify IAM permissions for S3 access\n"
        
        return message
    
    # DynamoDB operation errors
    if isinstance(error, DynamoDBOperationError):
        message = "DynamoDB Operation Failed:\n"
        message += f"  {str(error)}\n\n"
        
        if error.resource_name:
            message += f"  Resource: {error.resource_name}\n"
        if error.operation:
            message += f"  Operation: {error.operation}\n"
        
        message += "\nWhat to do:\n"
        message += "  - Verify DynamoDB table exists\n"
        message += "  - Check AWS credentials are valid\n"
        message += "  - Ensure resource exists in table\n"
        message += "  - Verify IAM permissions for DynamoDB access\n"
        
        return message
    
    # Generic error
    message = f"Error: {str(error)}\n\n"
    message += "What to do:\n"
    message += "  - Check the error message for specific details\n"
    message += "  - Review logs for more information\n"
    message += "  - Verify all configuration is correct\n"
    message += "  - Try running with --dry-run to validate setup\n"
    
    return message


def suggest_fixes_for_common_errors(error_message: str) -> list:
    """
    Suggest fixes for common error patterns.
    
    Args:
        error_message: The error message to analyze
    
    Returns:
        List of suggested fixes
    """
    suggestions = []
    error_lower = error_message.lower()
    
    # GitHub token issues
    if 'github_token' in error_lower or 'authentication' in error_lower:
        suggestions.append("Check GITHUB_TOKEN in .env file")
        suggestions.append("Verify token has 'repo' scope permissions")
        suggestions.append("Ensure token has not expired")
    
    # Fork URL issues
    if 'github_fork_url' in error_lower or 'fork' in error_lower:
        suggestions.append("Set GITHUB_FORK_URL environment variable")
        suggestions.append("Verify fork URL format: https://github.com/username/repo")
    
    # Git user issues
    if 'git_user' in error_lower or 'user.name' in error_lower or 'user.email' in error_lower:
        suggestions.append("Set GIT_USER_NAME environment variable")
        suggestions.append("Set GIT_USER_EMAIL environment variable")
    
    # Network issues
    if 'network' in error_lower or 'connection' in error_lower or 'timeout' in error_lower:
        suggestions.append("Check internet connection")
        suggestions.append("Verify GitHub is accessible")
        suggestions.append("Try again in a few minutes")
    
    # Rate limiting
    if 'rate limit' in error_lower:
        suggestions.append("Wait 60 minutes for rate limit to reset")
        suggestions.append("Check rate limit status at https://api.github.com/rate_limit")
    
    # PR already exists
    if 'already exists' in error_lower:
        suggestions.append("Check GitHub for existing PRs")
        suggestions.append("Close or merge existing PR first")
    
    # AWS credentials
    if 'credentials' in error_lower or 'access denied' in error_lower:
        suggestions.append("Check AWS credentials: aws sts get-caller-identity")
        suggestions.append("Verify IAM permissions")
    
    # S3 issues
    if 's3' in error_lower or 'bucket' in error_lower:
        suggestions.append("Verify S3 bucket exists and is accessible")
        suggestions.append("Check S3_BUCKET environment variable")
    
    # DynamoDB issues
    if 'dynamodb' in error_lower or 'table' in error_lower:
        suggestions.append("Verify DynamoDB table exists")
        suggestions.append("Check DYNAMODB_TABLE environment variable")
    
    # Make command issues
    if 'make' in error_lower:
        suggestions.append("Ensure make is installed and in PATH")
        suggestions.append("Verify repository structure is correct")
    
    return suggestions
