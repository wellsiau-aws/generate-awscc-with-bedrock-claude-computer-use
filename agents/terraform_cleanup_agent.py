"""
TANGO Multi-Agent Pipeline - Terraform Cleanup Agent
Specialized agent for cleaning up Terraform code
"""

from strands import Agent, tool
from strands_tools import python_repl

CLEANUP_SYSTEM_PROMPT = """
You are a specialized Terraform code cleanup agent.

CRITICAL: Check if the input indicates a FAILED execution first!
- If you see "TERRAFORM_LIFECYCLE_FAILED" or similar failure indicators in the input
- Return the code AS-IS without any cleanup
- Do NOT attempt to clean up failed code - it masks the actual errors

Your objective is to clean up SUCCESSFUL Terraform code and make it ready for examples in the AWSCC repository.

CLEANUP RULES (ONLY FOR SUCCESSFUL CODE):
1. Remove the `terraform` block - not needed for examples
2. Remove the `provider "aws"` and `provider "awscc"` blocks - not needed for examples
3. Remove any `provider "random"` blocks - not needed for examples
4. Remove any `random_id` or `random_*` resources - not needed for examples
5. Replace dynamic names with simple, static names:
   - `"example-bucket-${random_id.bucket_suffix.hex}"` → `"example-bucket"`
   - `"test-function-${random_string.suffix.result}"` → `"example-function"`
   - Any random suffixes or dynamic references → simple static names
6. Remove excessive comments that explain testing or validation purposes
7. Remove comments like "# Bucket name must be globally unique" unless essential
8. Keep only essential comments that explain configuration choices
9. Make the code look clean and production-ready like official Terraform Registry examples
10. Keep all resource configurations and outputs intact
11. Ensure proper formatting and indentation

WHAT TO KEEP:
- All main AWSCC resource configurations
- Essential configuration comments
- Output blocks (but clean up any random references)
- Variable references (if any, but clean up random ones)
- Clean, descriptive resource names

FAILURE HANDLING:
- If input contains failure indicators, return it unchanged
- Do NOT clean up failed code - it needs to preserve error context

Return ONLY the cleaned Terraform code (or unchanged code if failed) with no additional commentary.
"""

@tool
def terraform_cleanup_agent(terraform_code: str) -> str:
    """
    Clean up Terraform code by removing provider blocks, terraform blocks, 
    excessive comments, and test-specific names.
    
    IMPORTANT: If the code represents a failed execution, it will be returned unchanged
    to preserve error context.

    Args:
        terraform_code: The Terraform code to clean (or failure message)

    Returns:
        Cleaned Terraform code ready for examples (or unchanged if failed)
    """
    print("\n" + "="*80)
    print("🧹 TERRAFORM CLEANUP AGENT - STARTING")
    print("="*80)
    
    try:
        # Check if this is a failed execution
        if "TERRAFORM_LIFECYCLE_FAILED" in terraform_code or "Error" in terraform_code[:200]:
            print("\n" + "-"*80)
            print("⚠️  TERRAFORM CLEANUP AGENT - SKIPPED")
            print(f"   Detected failed execution - passing through unchanged")
            print("="*80 + "\n")
            return terraform_code
        
        agent = Agent(
            system_prompt=CLEANUP_SYSTEM_PROMPT,
            tools=[python_repl]
        )
        
        cleanup_query = f"""
        Clean up this Terraform code to make it look like a clean, production-ready example:
        
        {terraform_code}
        """
        
        response = agent(cleanup_query)
        
        print("\n" + "-"*80)
        print("✅ TERRAFORM CLEANUP AGENT - COMPLETED")
        print(f"   Removed provider blocks and cleaned up code")
        print("="*80 + "\n")
        
        return str(response)
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ TERRAFORM CLEANUP AGENT - FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        
        return f"Error in terraform cleanup agent: {str(e)}"
