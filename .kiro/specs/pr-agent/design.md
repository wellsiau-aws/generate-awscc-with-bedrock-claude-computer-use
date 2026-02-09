# Pull Request Agent - Design Document

## Architecture Overview

The PR agent is a standalone Python script that operates independently from the main TANGO pipeline. It follows the existing Strands Agent pattern but is invoked directly via CLI rather than through the orchestrator.

### High-Level Flow

```
CLI Invocation
    ↓
Configuration Validation
    ↓
Query DynamoDB (find eligible resources)
    ↓
Fetch S3 Content (terraform, template, analysis)
    ↓
Clone Fork Repository
    ↓
Create Feature Branch
    ↓
Place Files in Correct Structure
    ↓
Run Make Commands (fmt, docs, validate)
    ↓
Git Commit & Push
    ↓
Create GitHub PR
    ↓
Update DynamoDB (PR status)
    ↓
Cleanup & Report
```

## Component Design

### 1. CLI Interface (`create_pr.py`)

**Purpose**: Entry point for PR creation

**Interface**:
```python
# Process next eligible resource (atomic)
python create_pr.py

# Process specific resource
python create_pr.py awscc_s3_bucket

# Dry run (validate without creating PR)
python create_pr.py --dry-run

# Dry run for specific resource
python create_pr.py --dry-run awscc_s3_bucket
```

**Arguments**:
- No args: Process next eligible resource from DynamoDB
- `resource_name`: Specific resource to create PR for
- `--dry-run`: Validate without creating PR
- `--force`: Create PR even if one exists (for specific resource only)

### 2. PR Agent (`agents/pr_agent.py`)

**Purpose**: Core agent logic following Strands pattern

**Structure**:
```python
from strands import Agent, tool
from strands_tools import python_repl, use_aws
import config

PR_SYSTEM_PROMPT = """
You are a specialized GitHub Pull Request agent for AWSCC Terraform examples.

YOUR ROLE: PR Creator
You create pull requests to HashiCorp's terraform-provider-awscc repository.

YOUR TASKS:
1. Query DynamoDB for successfully validated resources (source='tango_pipeline')
2. Fetch validated content from S3
3. Clone fork repository and create branch
4. Place files in correct HashiCorp structure
5. Run required make commands
6. Commit, push, and create PR
7. Update DynamoDB with PR status

TOOLS AVAILABLE:
1. get_next_eligible_resource() - Find next TANGO-generated resource ready for PR (atomic)
2. fetch_resource_content(resource_name) - Get S3 content
3. clone_and_setup_repo(resource_name) - Git operations
4. run_hashicorp_validation() - Run make commands
5. create_github_pr(resource_name, branch_name) - Create PR
6. update_pr_status(resource_name, pr_url) - Update DynamoDB

IMPORTANT: 
- Only process resources with source='tango_pipeline' to distinguish from pre-existing examples
- Process exactly ONE resource per execution (atomic operation)
- Return after completing one resource
"""

@tool
def pr_agent(pr_request: str) -> str:
    """
    Create GitHub pull request for validated AWSCC resource.
    
    Args:
        pr_request: JSON with resource_name and options
        
    Returns:
        PR creation status with GitHub URL
    """
```

### 3. Helper Tools

#### 3.1 DynamoDB Query Tool

```python
@tool
def get_next_eligible_resource() -> str:
    """
    Get the next single resource eligible for PR creation (atomic operation).
    
    Returns:
        JSON with one resource (source='tango_pipeline', status='success', no PR)
        or {"resource_name": "NONE"} if no eligible resources
    """
```

**Logic**:
- Scan DynamoDB for `source='tango_pipeline'` AND `status='success'`
- Filter out entries with `pr_status` field (already have PR)
- Sort by timestamp (oldest first)
- Return exactly ONE resource
- Validate S3 files exist for that resource
- Return "NONE" if no eligible resources found
- Ignore any entries without `source='tango_pipeline'` (pre-existing examples)

#### 3.2 S3 Content Fetcher

```python
@tool
def fetch_resource_content(resource_name: str) -> str:
    """
    Fetch all required content from S3 for a resource.
    
    Returns:
        JSON with terraform_code, template, analysis_report
    """
```

**Logic**:
- Fetch from `examples/resources/{resource_name}/{service_name}.tf`
- Fetch from `templates/resources/{resource_name}.md.tmpl`
- Fetch from `analysis/resource/{resource_name}/{latest}.txt`
- Validate content is not empty
- Return structured data

#### 3.3 Git Operations Tool

```python
@tool
def clone_and_setup_repo(resource_name: str, work_dir: str) -> str:
    """
    Clone fork, create branch, and prepare for changes.
    
    Returns:
        JSON with repo_path, branch_name
    """
```

**Logic**:
- Create temporary directory: `{PR_WORK_DIR}/{resource_name}_{timestamp}`
- Clone fork: `git clone {GITHUB_FORK_URL} {work_dir}`
- Configure git: `git config user.name/email`
- Fetch upstream: `git remote add upstream {GITHUB_UPSTREAM_URL}`
- Update fork: `git fetch upstream && git merge upstream/main`
- Create branch: `git checkout -b d-{resource_name}`

#### 3.4 File Placement Tool

```python
@tool
def place_files_in_structure(repo_path: str, resource_name: str, content: dict) -> str:
    """
    Place files in correct HashiCorp repository structure.
    
    Returns:
        JSON with list of files created
    """
```

**Logic**:
- Create directory: `{repo_path}/examples/resources/{resource_name}/`
- Write Terraform file: `{resource_name}.tf`
- Create directory: `{repo_path}/templates/resources/` (if needed)
- Write template file: `{repo_path}/templates/resources/{resource_name}.md.tmpl`
- Return list of created files
- Note: `docs/resources/{resource_name}.md` will be auto-generated by `make docs`

#### 3.5 HashiCorp Validation Tool

```python
@tool
def run_hashicorp_validation(repo_path: str) -> str:
    """
    Run required make commands for HashiCorp validation.
    
    Returns:
        JSON with command results
    """
```

**Logic**:
- Set environment: `GOPROXY=direct`
- Run: `make tools` (install required tools: tfplugindocs, goimports, etc.)
- Run: `make docs` (auto-generate documentation from templates)
- Verify: `docs/resources/{resource_name}.md` was created by `make docs`
- Capture stdout/stderr
- Return success/failure status

**Note**: The terraform-provider-awscc repository uses `make tools` and `make docs`, not `make fmt`. The `make docs` command uses tfplugindocs to generate documentation from the template files.

#### 3.6 GitHub PR Creator

```python
@tool
def create_github_pr(resource_name: str, branch_name: str, content: dict) -> str:
    """
    Create pull request via GitHub API.
    
    Returns:
        JSON with pr_url, pr_number
    """
```

**Logic**:
- Generate PR title: `Add example for {resource_name}`
- Generate PR description (see template below)
- Create PR: `POST /repos/{owner}/{repo}/pulls`
- Return PR URL

**PR Description Template**:
```markdown
## Description

This PR adds a validated Terraform example for `{resource_name}`.

## Validation Summary

- ✅ Terraform code generated and validated
- ✅ Real AWS deployment tested (apply/destroy lifecycle)
- ✅ Independent validation review completed
- ✅ Required tools installed with `make tools`
- ✅ Documentation generated with `make docs`

## Testing Evidence

Full validation analysis available at: {s3_analysis_link}

## Resource Details

- **Resource**: `{resource_name}`
- **Provider Version**: `{provider_version}`
- **Validation Date**: `{validation_date}`
- **AWS Region**: `{aws_region}`

## Files Added

- `examples/resources/{resource_name}/{service_name}.tf`
- `templates/resources/{resource_name}.md.tmpl`
- `docs/resources/{resource_name}.md` (auto-generated by `make docs`)

---

*This PR was automatically generated by the TANGO Multi-Agent Pipeline.*
```

#### 3.7 DynamoDB Status Updater

```python
@tool
def update_pr_status(resource_name: str, pr_url: str, status: str) -> str:
    """
    Update DynamoDB with PR creation status.
    
    Returns:
        Confirmation message
    """
```

**Logic**:
- Query DynamoDB for latest entry with resource_name
- Update with:
  - `pr_status`: 'created' | 'failed'
  - `github_pr_url`: PR URL
  - `pr_created_at`: timestamp
- Preserve all existing fields

### 4. Cleanup Manager

```python
class PRWorkspaceCleanup:
    """Context manager for PR workspace cleanup"""
    
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
    
    def __enter__(self):
        return self.work_dir
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Always cleanup, even on failure
        if os.path.exists(self.work_dir):
            shutil.rmtree(self.work_dir)
```

## Data Structures

### Resource Content
```python
{
    "resource_name": "awscc_s3_bucket",
    "service_name": "s3_bucket",
    "terraform_code": "resource \"awscc_s3_bucket\" ...",
    "template": "---\nsubcategory: ...",
    "analysis_report": "Validation Analysis...",
    "s3_terraform_link": "examples/resources/...",
    "s3_template_link": "templates/resources/...",
    "s3_analysis_link": "analysis/resource/...",
    "provider_version": "1.53.0",
    "validation_date": "2026-01-23"
}
```

### PR Request
```python
{
    "resource_name": "awscc_s3_bucket",
    "dry_run": false,
    "force": false
}
```

### PR Response
```python
{
    "status": "success" | "failed",
    "pr_url": "https://github.com/hashicorp/terraform-provider-awscc/pull/1234",
    "pr_number": 1234,
    "branch_name": "d-awscc_s3_bucket",
    "files_created": [
        "examples/resources/awscc_s3_bucket/s3_bucket.tf",
        "templates/resources/awscc_s3_bucket.md.tmpl",
        "docs/resources/awscc_s3_bucket.md"  # auto-generated by make docs
    ],
    "error": null
}
```

## Error Handling

### Error Categories

1. **Configuration Errors**
   - Missing GITHUB_TOKEN
   - Invalid GITHUB_FORK_URL
   - Missing git credentials

2. **DynamoDB Errors**
   - Resource not found
   - Resource not validated (status != 'success')
   - DynamoDB access denied

3. **S3 Errors**
   - Files not found
   - Empty content
   - S3 access denied

4. **Git Errors**
   - Clone failure
   - Authentication failure
   - Push conflicts

5. **Make Command Errors**
   - Format failures
   - Documentation generation failures
   - Validation failures

6. **GitHub API Errors**
   - PR already exists
   - Authentication failure
   - Rate limiting

### Error Handling Strategy

```python
try:
    # Main PR creation logic
    with PRWorkspaceCleanup(work_dir) as workspace:
        # Clone, modify, commit, push, create PR
        pass
except ConfigurationError as e:
    log_error("Configuration error", e)
    sys.exit(1)
except ResourceNotReadyError as e:
    log_error("Resource not ready for PR", e)
    sys.exit(2)
except GitOperationError as e:
    log_error("Git operation failed", e)
    update_pr_status(resource_name, None, 'failed')
    sys.exit(3)
except GitHubAPIError as e:
    log_error("GitHub API error", e)
    update_pr_status(resource_name, None, 'failed')
    sys.exit(4)
finally:
    # Cleanup always happens via context manager
    pass
```

## Configuration

### New Config Parameters

Add to `config.py`:

```python
# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv()  # Loads from .env file in root directory

# GitHub Configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
GITHUB_FORK_URL = os.getenv('GITHUB_FORK_URL', '')
GITHUB_UPSTREAM_URL = "https://github.com/hashicorp/terraform-provider-awscc"

# Git Configuration
GIT_USER_NAME = os.getenv('GIT_USER_NAME', 'TANGO Pipeline')
GIT_USER_EMAIL = os.getenv('GIT_USER_EMAIL', 'tango@example.com')

# PR Configuration
PR_WORK_DIR = os.getenv('PR_WORK_DIR', 'pr_workspace')

def validate_pr_config():
    """Validate PR-specific configuration"""
    if not GITHUB_TOKEN:
        raise ConfigurationError("GITHUB_TOKEN not found in .env file or environment")
    if not GITHUB_FORK_URL:
        raise ConfigurationError("GITHUB_FORK_URL environment variable required")
    if not GIT_USER_NAME or not GIT_USER_EMAIL:
        raise ConfigurationError("GIT_USER_NAME and GIT_USER_EMAIL required")
```

**Note**: The `.env` file in the root directory already contains `GITHUB_TOKEN`. Additional variables can be added to `.env` or set as environment variables.

## Logging Format

Follow existing agent pattern:

```python
print("\n" + "="*80)
print("🔀 PR AGENT - STARTING")
print(f"   Resource: {resource_name}")
print("="*80)

# ... work ...

print("\n" + "-"*80)
print("✅ PR AGENT - COMPLETED")
print(f"   PR URL: {pr_url}")
print(f"   Branch: {branch_name}")
print("="*80 + "\n")
```

## Testing Strategy

### Unit Tests
- Test DynamoDB query logic
- Test S3 content fetching
- Test file placement logic
- Test PR description generation

### Integration Tests
- Test with mock GitHub API
- Test with temporary git repository
- Test cleanup on failure

### Manual Testing
- Dry-run mode for validation
- Test with actual fork (non-production)
- Verify HashiCorp make commands work

## Performance Considerations

- **Clone Time**: ~30 seconds for terraform-provider-awscc repo
- **Make Commands**: ~1-2 minutes for fmt + docs
- **GitHub API**: ~1-2 seconds per request
- **Total Time**: ~3-5 minutes per resource

### Atomic Operation Benefits
- Simpler error handling (one resource at a time)
- Easier to retry on failure
- Clear progress tracking
- No partial batch failures
- Can run multiple times to process multiple resources

## Security Considerations

1. **Token Security**
   - Never log GITHUB_TOKEN
   - Use environment variable only
   - Validate token has minimal required permissions

2. **Temporary Files**
   - Use secure temporary directories
   - Clean up on success and failure
   - Don't leave sensitive data in temp files

3. **Git Credentials**
   - Use token-based authentication
   - Don't store credentials in git config
   - Use HTTPS URLs with token

## Future Enhancements

1. **PR Status Monitoring**
   - Check if PR was merged
   - Update DynamoDB with merge status

2. **Batch Optimization**
   - Reuse cloned repo for multiple PRs
   - Parallel PR creation

3. **PR Updates**
   - Update existing PR if validation improves
   - Handle review comments

4. **Automated Testing**
   - Run terraform validate in CI
   - Run example code in test environment

## Dependencies

```python
# requirements.txt additions
PyGithub>=2.1.1        # GitHub API client
GitPython>=3.1.40      # Git operations
python-dotenv>=1.0.0   # Load .env file
```

## Correctness Properties

### Property 1: Idempotency
**Description**: Running the PR agent multiple times for the same resource should not create duplicate PRs.

**Test Strategy**: 
- Run agent twice for same resource
- Verify only one PR exists
- Verify DynamoDB shows correct status

### Property 2: Cleanup Guarantee
**Description**: Temporary directories are always cleaned up, even on failure.

**Test Strategy**:
- Simulate failures at various stages
- Verify no temp directories remain
- Use context manager for guaranteed cleanup

### Property 3: Status Consistency
**Description**: DynamoDB status always reflects actual PR state.

**Test Strategy**:
- Verify status='created' only when PR exists
- Verify status='failed' when PR creation fails
- Verify pr_url matches actual GitHub PR

### Property 4: File Structure Correctness
**Description**: Files are placed in exact HashiCorp structure.

**Test Strategy**:
- Verify examples/resources/{resource_name}/ exists
- Verify docs/resources/{resource_name}.md exists
- Verify file names match conventions

### Property 5: Make Command Success
**Description**: All required make commands pass before PR creation.

**Test Strategy**:
- Run make fmt and verify no errors
- Run make docs and verify docs generated
- Fail PR creation if any make command fails
