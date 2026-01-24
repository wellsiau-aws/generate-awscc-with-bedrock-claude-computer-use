"""
Workspace Guard Utility
Detects and warns about files created in wrong locations
"""

import os
import config
from typing import List, Tuple

# Files that should NEVER be in the root directory during pipeline execution
PROTECTED_FILES = [
    'main.tf',
    'variables.tf',
    'outputs.tf',
    'terraform.tfstate',
    'terraform.tfstate.backup',
    '.terraform.lock.hcl'
]

def check_root_directory() -> Tuple[bool, List[str]]:
    """
    Check if any Terraform files were created in the root directory.
    
    Returns:
        Tuple of (has_violations, list_of_violating_files)
    """
    violations = []
    
    for filename in PROTECTED_FILES:
        if os.path.exists(filename) and os.path.isfile(filename):
            violations.append(filename)
    
    return len(violations) > 0, violations


def check_terraform_work_dir() -> Tuple[bool, str]:
    """
    Check if terraform_test directory exists and has expected structure.
    
    Returns:
        Tuple of (is_valid, message)
    """
    work_dir = config.TERRAFORM_WORK_DIR
    
    if not os.path.exists(work_dir):
        return False, f"❌ {work_dir} directory does not exist"
    
    if not os.path.isdir(work_dir):
        return False, f"❌ {work_dir} exists but is not a directory"
    
    main_tf = os.path.join(work_dir, 'main.tf')
    if not os.path.exists(main_tf):
        return False, f"⚠️  {work_dir} exists but main.tf is missing"
    
    return True, f"✅ {work_dir} is properly configured"


def print_workspace_status():
    """Print current workspace status for debugging"""
    print("\n" + "="*80)
    print("🔍 WORKSPACE STATUS CHECK")
    print("="*80)
    
    # Check root directory
    has_violations, violations = check_root_directory()
    if has_violations:
        print("\n⚠️  WARNING: Terraform files found in ROOT directory:")
        for file in violations:
            print(f"   ❌ {file} (should be in {config.TERRAFORM_WORK_DIR}/)")
    else:
        print(f"\n✅ Root directory is clean (no Terraform files)")
    
    # Check work directory
    is_valid, message = check_terraform_work_dir()
    print(f"\n{message}")
    
    # List work directory contents if it exists
    if os.path.exists(config.TERRAFORM_WORK_DIR):
        print(f"\n📁 Contents of {config.TERRAFORM_WORK_DIR}:")
        try:
            contents = os.listdir(config.TERRAFORM_WORK_DIR)
            if contents:
                for item in sorted(contents):
                    item_path = os.path.join(config.TERRAFORM_WORK_DIR, item)
                    if os.path.isdir(item_path):
                        print(f"   📁 {item}/")
                    else:
                        size = os.path.getsize(item_path)
                        print(f"   📄 {item} ({size} bytes)")
            else:
                print(f"   (empty)")
        except Exception as e:
            print(f"   Error reading directory: {e}")
    
    print("="*80 + "\n")


def cleanup_root_violations():
    """Remove Terraform files from root directory"""
    has_violations, violations = check_root_directory()
    
    if not has_violations:
        return
    
    print("\n🧹 Cleaning up root directory violations...")
    for file in violations:
        try:
            os.remove(file)
            print(f"   ✅ Removed {file}")
        except Exception as e:
            print(f"   ❌ Failed to remove {file}: {e}")


if __name__ == "__main__":
    # Run as standalone script for debugging
    print_workspace_status()
