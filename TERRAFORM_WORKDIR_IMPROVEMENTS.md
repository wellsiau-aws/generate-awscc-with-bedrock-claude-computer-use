# Terraform Working Directory Consistency Improvements

## Problem Analysis

Your agents were inconsistently handling the `terraform_test` working directory:

### Issues Found:
1. **Documentation Agent**: Explicitly created `terraform_test` ✅
2. **Terraform Agent**: Created vague "test directory" (name not specified) ❌
3. **Validation Agent**: Created vague "test directory" (name not specified) ❌
4. **No shared constant**: Each agent independently decided directory names
5. **Cleanup conflicts**: Agents didn't know if they should reuse or recreate directories

## Solutions Implemented

### 1. Centralized Configuration (config.py)
Added a shared constant that all agents reference:
```python
TERRAFORM_WORK_DIR = os.environ.get("TERRAFORM_WORK_DIR", "terraform_test")
```

### 2. Updated Agent Prompts
All three agents now have explicit instructions:

**Documentation Agent:**
- Creates `{config.TERRAFORM_WORK_DIR}` if it doesn't exist
- Uses it for all Terraform operations
- Leaves it for next agent to use

**Terraform Agent:**
- Uses existing `{config.TERRAFORM_WORK_DIR}` or creates if missing
- Performs all operations in this directory
- Cleans up completely after destroy

**Validation Agent:**
- Removes `{config.TERRAFORM_WORK_DIR}` if exists (fresh start for independent validation)
- Creates fresh directory
- Performs all operations in this directory
- Cleans up completely after validation

## Additional Recommendations

### 1. Add Directory State Validation
Consider adding a helper function to check directory state:

```python
# In config.py or a new utils.py
import os
import shutil

def ensure_clean_workdir(work_dir: str = None):
    """Ensure working directory is clean and ready"""
    work_dir = work_dir or TERRAFORM_WORK_DIR
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    os.makedirs(work_dir)
    return work_dir

def cleanup_workdir(work_dir: str = None):
    """Clean up working directory"""
    work_dir = work_dir or TERRAFORM_WORK_DIR
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
```

### 2. Add Explicit Cleanup Instructions
Update orchestrator to emphasize cleanup:

```python
ORCHESTRATOR_SYSTEM_PROMPT = """
...
WORKING DIRECTORY MANAGEMENT:
- All agents use {config.TERRAFORM_WORK_DIR} as the working directory
- Documentation agent: Creates and initializes
- Terraform agent: Uses existing, cleans up after destroy
- Validation agent: Removes and recreates for independent testing
- Each agent MUST clean up after itself on completion
...
"""
```

### 3. Add Pre-flight Checks
Add validation before pipeline starts:

```python
def pre_flight_check():
    """Verify environment before starting pipeline"""
    # Check if terraform_test exists from previous failed run
    if os.path.exists(config.TERRAFORM_WORK_DIR):
        print(f"⚠️  Warning: {config.TERRAFORM_WORK_DIR} exists from previous run")
        response = input("Clean it up? (y/n): ")
        if response.lower() == 'y':
            shutil.rmtree(config.TERRAFORM_WORK_DIR)
            print(f"✅ Cleaned up {config.TERRAFORM_WORK_DIR}")
```

### 4. Add Post-execution Cleanup Hook
Ensure cleanup even on failures:

```python
def run_pipeline():
    """Execute the TANGO multi-agent pipeline"""
    try:
        # ... existing code ...
    finally:
        # Always cleanup on exit
        if os.path.exists(config.TERRAFORM_WORK_DIR):
            print(f"🧹 Cleaning up {config.TERRAFORM_WORK_DIR}")
            shutil.rmtree(config.TERRAFORM_WORK_DIR)
```

### 5. Environment Variable Override
You can now override the working directory via environment variable:
```bash
export TERRAFORM_WORK_DIR="my_custom_test_dir"
python main.py
```

## Testing the Changes

1. **Test normal flow:**
   ```bash
   python main.py
   # Verify terraform_test is created and cleaned up
   ```

2. **Test with existing directory:**
   ```bash
   mkdir terraform_test
   python main.py
   # Verify agents handle existing directory correctly
   ```

3. **Test cleanup on failure:**
   ```bash
   # Simulate failure and verify cleanup
   ```

## Benefits

✅ **Consistency**: All agents use the same directory name
✅ **Predictability**: Clear ownership and lifecycle management
✅ **Debuggability**: Easy to find and inspect working directory
✅ **Flexibility**: Can override via environment variable
✅ **Maintainability**: Single source of truth in config.py

## Migration Notes

- No breaking changes - default behavior unchanged
- Existing code will work with new constant
- Can gradually add helper functions for better error handling
