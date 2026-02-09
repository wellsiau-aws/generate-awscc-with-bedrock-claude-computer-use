# Project Structure

## Directory Layout

```
tango-multi-agent-pipeline/
├── agents/                    # Multi-agent system components
│   ├── orchestrator_agent.py  # Main coordinator
│   ├── discovery_agent.py     # GitHub API and resource discovery
│   ├── documentation_agent.py # Terraform code generation
│   ├── terraform_agent.py     # Terraform lifecycle operations
│   ├── validation_agent.py    # Independent validation and review
│   ├── terraform_cleanup_agent.py  # Code cleanup (remove provider blocks)
│   ├── storage_agent.py       # DynamoDB and S3 operations
│   ├── cleanup_agent.py       # AWS resource cleanup
│   ├── workspace_guard.py     # Workspace integrity checks
│   └── agent_logger.py        # Logging utilities
├── infra/                     # Terraform infrastructure setup
│   ├── main.tf                # Main infrastructure definition
│   ├── variables.tf           # Input variables
│   ├── outputs.tf             # Output values
│   └── versions.tf            # Provider versions
├── terraform_test/            # Terraform working directory (created at runtime)
├── templates/resources/       # Markdown templates for documentation
├── examples/resources/        # Successfully validated Terraform configs
├── failed/resources/          # Failed attempts with error analysis
├── analysis/resource/         # Detailed validation reports
├── docs/                      # Project documentation
├── config.py                  # Configuration with validation
├── main.py                    # Main entry point
├── target_resource.py         # Target specific resources
├── evaluation_agent.py        # Standalone evaluation agent
└── requirements.txt           # Python dependencies
```

## Key Architectural Patterns

### Multi-Agent Coordination

Agents follow a **Sequential Reuse** pattern for efficiency:

1. **Discovery Agent**: Finds unprocessed resources from GitHub releases
2. **Documentation Agent**: Generates Terraform code, creates `terraform_test/` workspace
3. **Terraform Agent**: Reuses workspace, validates with real AWS deployment
4. **Validation Agent**: Reuses workspace, performs independent review
5. **Terraform Cleanup Agent**: Removes provider blocks from code
6. **Storage Agent**: Stores results in DynamoDB and S3
7. **Cleanup Agent**: Handles orphaned AWS resources (when needed)
8. **Orchestrator**: Coordinates all agents, cleans up workspace at end

### Workspace Management

**CRITICAL**: All Terraform operations occur in `terraform_test/` directory:
- Documentation agent creates and initializes it
- Terraform and validation agents reuse it (saves ~60 seconds per resource)
- Orchestrator cleans it up at the end
- **NEVER** create Terraform files in root directory

### Data Flow

```
discovery_agent → {resource_name, provider_version}
documentation_agent → terraform_code [creates terraform_test/]
terraform_agent → corrected_code [reuses terraform_test/]
validation_agent → validation_results [reuses terraform_test/]
terraform_cleanup_agent → cleaned_code
storage_agent → storage_confirmation
orchestrator → cleanup terraform_test/
```

## Code Conventions

### Agent Structure

Each agent follows the Strands Agent pattern:
- Decorated with `@tool` for orchestrator integration
- Clear system prompts defining role and responsibilities
- Structured input/output with JSON where appropriate
- Comprehensive logging with visual separators

### Error Handling

- All agents handle failures gracefully
- Storage agent called regardless of success/failure
- Complete audit trail maintained in DynamoDB
- Workspace cleanup happens even on failure (try/finally)

### Configuration

- Environment variables validated on import
- AWS resources checked for accessibility
- Fails fast with helpful error messages
- Terraform outputs can be loaded as env vars

### Logging Format

```python
print("\n" + "="*80)
print("🔍 AGENT NAME - STARTING")
print("="*80)
# ... agent work ...
print("\n" + "-"*80)
print("✅ AGENT NAME - COMPLETED")
print("="*80 + "\n")
```

## Important Files

- `config.py`: Central configuration with validation logic
- `orchestrator_agent.py`: Main workflow coordination
- `workspace_guard.py`: Ensures workspace integrity
- `dynamodb-schema.md`: DynamoDB table schema documentation
- `USAGE.md`: Setup and usage instructions
