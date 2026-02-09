"""
TANGO Multi-Agent Pipeline - PR Agent Custom Exceptions
Custom exception classes for the PR agent to provide clear error handling
"""


class PRAgentError(Exception):
    """Base exception class for all PR agent errors."""
    
    def __init__(self, message: str, details: dict = None):
        """
        Initialize the PR agent error.
        
        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self):
        """Return string representation of the error."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class ConfigurationError(PRAgentError):
    """
    Raised when required configuration is missing or invalid.
    
    Examples:
        - Missing GITHUB_TOKEN
        - Invalid GITHUB_FORK_URL
        - Missing GIT_USER_NAME or GIT_USER_EMAIL
        - AWS credentials not configured
    """
    
    def __init__(self, message: str, missing_config: list = None):
        """
        Initialize configuration error.
        
        Args:
            message: Error message
            missing_config: List of missing configuration keys
        """
        details = {}
        if missing_config:
            details['missing_config'] = missing_config
        
        super().__init__(message, details)
        self.missing_config = missing_config or []


class ResourceNotReadyError(PRAgentError):
    """
    Raised when a resource is not ready for PR creation.
    
    Examples:
        - Resource not found in DynamoDB
        - Resource status is not 'success'
        - Resource source is not 'tango_pipeline'
        - Required S3 files are missing
        - Resource already has a PR (pr_status='created')
    """
    
    def __init__(self, message: str, resource_name: str = None, reason: str = None):
        """
        Initialize resource not ready error.
        
        Args:
            message: Error message
            resource_name: The resource that is not ready
            reason: Specific reason why resource is not ready
        """
        details = {}
        if resource_name:
            details['resource_name'] = resource_name
        if reason:
            details['reason'] = reason
        
        super().__init__(message, details)
        self.resource_name = resource_name
        self.reason = reason


class GitOperationError(PRAgentError):
    """
    Raised when a git operation fails.
    
    Examples:
        - Clone failure
        - Authentication failure
        - Push conflicts
        - Merge conflicts
        - Branch creation failure
        - Commit failure
    """
    
    def __init__(self, message: str, operation: str = None, git_error: str = None):
        """
        Initialize git operation error.
        
        Args:
            message: Error message
            operation: The git operation that failed (e.g., 'clone', 'push', 'commit')
            git_error: The underlying git error message
        """
        details = {}
        if operation:
            details['operation'] = operation
        if git_error:
            details['git_error'] = git_error
        
        super().__init__(message, details)
        self.operation = operation
        self.git_error = git_error


class GitHubAPIError(PRAgentError):
    """
    Raised when a GitHub API operation fails.
    
    Examples:
        - Authentication failure (401)
        - PR already exists (422)
        - Rate limiting (403)
        - Repository not found (404)
        - Permission denied (403)
    """
    
    def __init__(self, message: str, status_code: int = None, api_response: dict = None):
        """
        Initialize GitHub API error.
        
        Args:
            message: Error message
            status_code: HTTP status code from GitHub API
            api_response: The API response data
        """
        details = {}
        if status_code:
            details['status_code'] = status_code
        if api_response:
            details['api_response'] = api_response
        
        super().__init__(message, details)
        self.status_code = status_code
        self.api_response = api_response or {}
    
    def is_rate_limit(self) -> bool:
        """Check if this is a rate limit error."""
        return self.status_code == 403 and 'rate limit' in self.message.lower()
    
    def is_authentication_error(self) -> bool:
        """Check if this is an authentication error."""
        return self.status_code == 401
    
    def is_not_found(self) -> bool:
        """Check if this is a not found error."""
        return self.status_code == 404
    
    def is_pr_exists(self) -> bool:
        """Check if this is a PR already exists error."""
        return self.status_code == 422 and 'already exists' in self.message.lower()


class S3OperationError(PRAgentError):
    """
    Raised when an S3 operation fails.
    
    Examples:
        - File not found in S3
        - Empty file content
        - Invalid UTF-8 content
        - S3 access denied
    """
    
    def __init__(self, message: str, s3_key: str = None, operation: str = None):
        """
        Initialize S3 operation error.
        
        Args:
            message: Error message
            s3_key: The S3 key that caused the error
            operation: The S3 operation that failed (e.g., 'get_object', 'head_object')
        """
        details = {}
        if s3_key:
            details['s3_key'] = s3_key
        if operation:
            details['operation'] = operation
        
        super().__init__(message, details)
        self.s3_key = s3_key
        self.operation = operation


class DynamoDBOperationError(PRAgentError):
    """
    Raised when a DynamoDB operation fails.
    
    Examples:
        - Resource not found
        - Update failure
        - Query failure
        - Table access denied
    """
    
    def __init__(self, message: str, resource_name: str = None, operation: str = None):
        """
        Initialize DynamoDB operation error.
        
        Args:
            message: Error message
            resource_name: The resource name involved in the operation
            operation: The DynamoDB operation that failed (e.g., 'query', 'update')
        """
        details = {}
        if resource_name:
            details['resource_name'] = resource_name
        if operation:
            details['operation'] = operation
        
        super().__init__(message, details)
        self.resource_name = resource_name
        self.operation = operation


class ValidationError(PRAgentError):
    """
    Raised when HashiCorp validation fails.
    
    Examples:
        - make fmt failure
        - make docs failure
        - Documentation not generated
        - Validation command failure
    """
    
    def __init__(self, message: str, command: str = None, returncode: int = None, stderr: str = None):
        """
        Initialize validation error.
        
        Args:
            message: Error message
            command: The command that failed
            returncode: The command return code
            stderr: The command stderr output
        """
        details = {}
        if command:
            details['command'] = command
        if returncode is not None:
            details['returncode'] = returncode
        if stderr:
            details['stderr'] = stderr[:500]  # Limit stderr length
        
        super().__init__(message, details)
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
