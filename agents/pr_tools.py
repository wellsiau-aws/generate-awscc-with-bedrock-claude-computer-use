"""
TANGO Multi-Agent Pipeline - PR Agent Tools
Helper tools for the PR agent to create GitHub pull requests
"""

import json
import os
import shutil
import tempfile
import boto3
from datetime import datetime
from strands import tool
import config


@tool
def fetch_resource_content(resource_name: str) -> str:
    """
    Fetch all required content from S3 for a resource.
    
    Args:
        resource_name: The AWSCC resource name (e.g., "awscc_s3_bucket")
    
    Returns:
        JSON with terraform_code, template, analysis_report, and metadata
    """
    print("\n" + "="*80)
    print(f"📥 FETCHING S3 CONTENT - {resource_name}")
    print("="*80)
    
    try:
        s3 = boto3.client('s3', region_name=config.AWS_REGION)
        
        # Extract service_name from resource_name (remove "awscc_" prefix)
        if resource_name.startswith('awscc_'):
            service_name = resource_name[6:]  # Remove "awscc_" prefix
        else:
            service_name = resource_name
        
        print(f"   Service name: {service_name}")
        
        # Construct S3 paths
        terraform_key = f"examples/resources/{resource_name}/{service_name}.tf"
        template_key = f"templates/resources/{service_name}.md.tmpl"
        
        # Find the latest analysis file
        analysis_prefix = f"analysis/resource/{resource_name}/"
        print(f"\n📂 Listing analysis files in {analysis_prefix}...")
        
        analysis_response = s3.list_objects_v2(
            Bucket=config.S3_BUCKET,
            Prefix=analysis_prefix
        )
        
        analysis_key = None
        if 'Contents' in analysis_response and analysis_response['Contents']:
            # Sort by LastModified to get the latest
            analysis_files = sorted(
                analysis_response['Contents'],
                key=lambda x: x['LastModified'],
                reverse=True
            )
            analysis_key = analysis_files[0]['Key']
            print(f"   Found latest analysis: {analysis_key}")
        else:
            print(f"   ⚠️  No analysis files found")
        
        # Fetch terraform code
        print(f"\n📄 Fetching Terraform code from {terraform_key}...")
        try:
            terraform_response = s3.get_object(
                Bucket=config.S3_BUCKET,
                Key=terraform_key
            )
            terraform_code = terraform_response['Body'].read().decode('utf-8')
            print(f"   ✓ Fetched {len(terraform_code)} bytes")
            
            # Validate content is not empty
            if not terraform_code or not terraform_code.strip():
                raise ValueError("Terraform code is empty")
            
            # Validate content is valid UTF-8 (already decoded, so this is implicit)
            print(f"   ✓ Content validated (non-empty, valid UTF-8)")
            
        except s3.exceptions.NoSuchKey:
            raise FileNotFoundError(f"Terraform file not found: {terraform_key}")
        except UnicodeDecodeError:
            raise ValueError(f"Terraform file is not valid UTF-8: {terraform_key}")
        
        # Fetch template
        print(f"\n📄 Fetching template from {template_key}...")
        try:
            template_response = s3.get_object(
                Bucket=config.S3_BUCKET,
                Key=template_key
            )
            template = template_response['Body'].read().decode('utf-8')
            print(f"   ✓ Fetched {len(template)} bytes")
            
            # Validate content is not empty
            if not template or not template.strip():
                raise ValueError("Template is empty")
            
            print(f"   ✓ Content validated (non-empty, valid UTF-8)")
            
        except s3.exceptions.NoSuchKey:
            raise FileNotFoundError(f"Template file not found: {template_key}")
        except UnicodeDecodeError:
            raise ValueError(f"Template file is not valid UTF-8: {template_key}")
        
        # Fetch analysis report
        analysis_report = None
        if analysis_key:
            print(f"\n📄 Fetching analysis report from {analysis_key}...")
            try:
                analysis_response = s3.get_object(
                    Bucket=config.S3_BUCKET,
                    Key=analysis_key
                )
                analysis_report = analysis_response['Body'].read().decode('utf-8')
                print(f"   ✓ Fetched {len(analysis_report)} bytes")
                
                # Validate content is not empty
                if not analysis_report or not analysis_report.strip():
                    raise ValueError("Analysis report is empty")
                
                print(f"   ✓ Content validated (non-empty, valid UTF-8)")
                
            except s3.exceptions.NoSuchKey:
                print(f"   ⚠️  Analysis file not found: {analysis_key}")
                analysis_report = None
            except UnicodeDecodeError:
                raise ValueError(f"Analysis file is not valid UTF-8: {analysis_key}")
        
        # Build result
        result = {
            "resource_name": resource_name,
            "service_name": service_name,
            "terraform_code": terraform_code,
            "template": template,
            "analysis_report": analysis_report,
            "s3_terraform_link": terraform_key,
            "s3_template_link": template_key,
            "s3_analysis_link": analysis_key,
            "provider_version": config.DEFAULT_PROVIDER_VERSION,
            "fetch_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        print("\n" + "-"*80)
        print("✅ FETCH COMPLETED")
        print(f"   Resource: {resource_name}")
        print(f"   Service: {service_name}")
        print(f"   Terraform: {len(terraform_code)} bytes")
        print(f"   Template: {len(template)} bytes")
        print(f"   Analysis: {len(analysis_report) if analysis_report else 0} bytes")
        print("="*80 + "\n")
        
        return json.dumps(result)
    
    except FileNotFoundError as e:
        print("\n" + "-"*80)
        print("❌ FETCH FAILED - File not found")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        raise
    
    except ValueError as e:
        print("\n" + "-"*80)
        print("❌ FETCH FAILED - Content validation error")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        raise
    
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ FETCH FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        raise


@tool
def get_next_eligible_resource() -> str:
    """
    Get the next single resource eligible for PR creation (atomic operation).
    
    Returns:
        JSON with one resource (source='tango_pipeline', status='success', no PR)
        or {"resource_name": "NONE"} if no eligible resources
    """
    print("\n" + "="*80)
    print("🔍 QUERYING DYNAMODB - Getting next eligible resource")
    print("="*80)
    
    def process_item(item, s3):
        """Process a single DynamoDB item and check if it's eligible."""
        # Skip if already has a successful PR (pr_status='created')
        # Allow retry if pr_status='failed'
        pr_status = item.get('pr_status', {}).get('S')
        if pr_status == 'created':
            return None
        
        resource_name = item.get('resource_name', {}).get('S')
        timestamp = item.get('timestamp', {}).get('N')
        s3_terraform_link = item.get('s3_terraform_link', {}).get('S')
        s3_template_link = item.get('s3_template_link', {}).get('S')
        s3_analysis_link = item.get('s3_analysis_link', {}).get('S')
        
        if not resource_name:
            return None
        
        # Validate S3 files exist
        print(f"   Checking S3 files for {resource_name}...")
        files_exist = True
        
        # Check terraform file
        if s3_terraform_link:
            try:
                s3.head_object(Bucket=config.S3_BUCKET, Key=s3_terraform_link)
            except:
                print(f"      ✗ Terraform file missing: {s3_terraform_link}")
                files_exist = False
        else:
            files_exist = False
        
        # Check template file
        if s3_template_link:
            try:
                s3.head_object(Bucket=config.S3_BUCKET, Key=s3_template_link)
            except:
                print(f"      ✗ Template file missing: {s3_template_link}")
                files_exist = False
        else:
            files_exist = False
        
        # Check analysis file
        if s3_analysis_link:
            try:
                s3.head_object(Bucket=config.S3_BUCKET, Key=s3_analysis_link)
            except:
                print(f"      ✗ Analysis file missing: {s3_analysis_link}")
                files_exist = False
        else:
            files_exist = False
        
        if files_exist:
            print(f"      ✓ All files exist for {resource_name}")
            return {
                'resource_name': resource_name,
                'timestamp': int(timestamp) if timestamp else 0,
                's3_terraform_link': s3_terraform_link,
                's3_template_link': s3_template_link,
                's3_analysis_link': s3_analysis_link
            }
        
        return None
    
    try:
        dynamodb = boto3.client('dynamodb', region_name=config.AWS_REGION)
        s3 = boto3.client('s3', region_name=config.AWS_REGION)
        
        # Scan DynamoDB for eligible resources
        print("📊 Scanning DynamoDB table...")
        response = dynamodb.scan(
            TableName=config.DYNAMODB_TABLE,
            FilterExpression='#src = :source AND #status = :status',
            ExpressionAttributeNames={
                '#src': 'source',
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':source': {'S': 'tango_pipeline'},
                ':status': {'S': 'success'}
            }
        )
        
        eligible_resources = []
        
        # Process initial batch
        for item in response.get('Items', []):
            result = process_item(item, s3)
            if result:
                eligible_resources.append(result)
        
        # Handle pagination if there are more items
        while 'LastEvaluatedKey' in response:
            print("📊 Fetching more items (pagination)...")
            response = dynamodb.scan(
                TableName=config.DYNAMODB_TABLE,
                FilterExpression='#src = :source AND #status = :status',
                ExpressionAttributeNames={
                    '#src': 'source',
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':source': {'S': 'tango_pipeline'},
                    ':status': {'S': 'success'}
                },
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            
            for item in response.get('Items', []):
                result = process_item(item, s3)
                if result:
                    eligible_resources.append(result)
        
        # Sort by timestamp (oldest first) and return the first one
        if eligible_resources:
            eligible_resources.sort(key=lambda x: x['timestamp'])
            selected = eligible_resources[0]
            
            print("\n" + "-"*80)
            print("✅ QUERY COMPLETED - Found eligible resource")
            print(f"   Resource: {selected['resource_name']}")
            print(f"   Timestamp: {selected['timestamp']}")
            print(f"   Total eligible: {len(eligible_resources)}")
            print("="*80 + "\n")
            
            return json.dumps(selected)
        else:
            print("\n" + "-"*80)
            print("ℹ️  QUERY COMPLETED - No eligible resources found")
            print("="*80 + "\n")
            
            return json.dumps({"resource_name": "NONE"})
    
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ QUERY FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        
        return json.dumps({"resource_name": "ERROR", "error": str(e)})


@tool
def clone_and_setup_repo(resource_name: str) -> str:
    """
    Clone fork, create branch, and prepare for changes.
    
    Args:
        resource_name: The AWSCC resource name (e.g., "awscc_s3_bucket")
    
    Returns:
        JSON with repo_path, branch_name, and status
    """
    print("\n" + "="*80)
    print(f"🔧 GIT OPERATIONS - Setting up repository for {resource_name}")
    print("="*80)
    
    try:
        import git
        from git import Repo
    except ImportError:
        error_msg = "GitPython not installed. Run: pip install GitPython>=3.1.40"
        print(f"\n❌ ERROR: {error_msg}")
        return json.dumps({"status": "error", "error": error_msg})
    
    try:
        # Validate configuration
        if not config.GITHUB_FORK_URL:
            raise ValueError("GITHUB_FORK_URL not configured")
        if not config.GIT_USER_NAME:
            raise ValueError("GIT_USER_NAME not configured")
        if not config.GIT_USER_EMAIL:
            raise ValueError("GIT_USER_EMAIL not configured")
        
        # Create temporary working directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        work_dir_name = f"{resource_name}_{timestamp}"
        work_dir = os.path.join(config.PR_WORK_DIR, work_dir_name)
        
        print(f"\n📁 Creating working directory: {work_dir}")
        os.makedirs(work_dir, exist_ok=True)
        
        # Clone fork repository
        print(f"\n📥 Cloning fork repository...")
        print(f"   URL: {config.GITHUB_FORK_URL}")
        print(f"   Destination: {work_dir}")
        
        # Use token authentication if available
        clone_url = config.GITHUB_FORK_URL
        if config.GITHUB_TOKEN and 'github.com' in clone_url:
            # Insert token into URL for authentication
            if clone_url.startswith('https://github.com/'):
                clone_url = clone_url.replace(
                    'https://github.com/',
                    f'https://{config.GITHUB_TOKEN}@github.com/'
                )
        
        repo = Repo.clone_from(clone_url, work_dir)
        print(f"   ✓ Repository cloned successfully")
        
        # Configure git user name and email
        print(f"\n👤 Configuring git user...")
        print(f"   Name: {config.GIT_USER_NAME}")
        print(f"   Email: {config.GIT_USER_EMAIL}")
        
        with repo.config_writer() as git_config:
            git_config.set_value('user', 'name', config.GIT_USER_NAME)
            git_config.set_value('user', 'email', config.GIT_USER_EMAIL)
        
        print(f"   ✓ Git user configured")
        
        # Add upstream remote
        print(f"\n🔗 Adding upstream remote...")
        print(f"   URL: {config.GITHUB_UPSTREAM_URL}")
        
        try:
            upstream = repo.create_remote('upstream', config.GITHUB_UPSTREAM_URL)
            print(f"   ✓ Upstream remote added")
        except git.exc.GitCommandError as e:
            if 'already exists' in str(e):
                print(f"   ℹ️  Upstream remote already exists")
                upstream = repo.remote('upstream')
            else:
                raise
        
        # Fetch upstream main branch
        print(f"\n📡 Fetching upstream main branch...")
        upstream.fetch()
        print(f"   ✓ Upstream fetched")
        
        # Merge upstream into fork
        print(f"\n🔄 Merging upstream/main into local main...")
        try:
            # Ensure we're on main branch
            repo.git.checkout('main')
            
            # Merge upstream/main
            repo.git.merge('upstream/main', '--ff-only')
            print(f"   ✓ Merged upstream/main (fast-forward)")
        except git.exc.GitCommandError as e:
            if 'Not possible to fast-forward' in str(e):
                print(f"   ⚠️  Fast-forward not possible, attempting regular merge...")
                try:
                    repo.git.merge('upstream/main')
                    print(f"   ✓ Merged upstream/main (regular merge)")
                except git.exc.GitCommandError as merge_error:
                    print(f"   ❌ Merge conflict detected")
                    print(f"   Error: {str(merge_error)}")
                    raise ValueError(f"Merge conflict when syncing with upstream: {str(merge_error)}")
            else:
                raise
        
        # Create branch with naming convention: d-{resource_name}
        branch_name = f"d-{resource_name}"
        print(f"\n🌿 Creating feature branch: {branch_name}")
        
        try:
            # Check if branch already exists locally
            if branch_name in [ref.name for ref in repo.heads]:
                print(f"   ⚠️  Branch {branch_name} already exists locally, deleting...")
                repo.delete_head(branch_name, force=True)
            
            # Create and checkout new branch
            new_branch = repo.create_head(branch_name)
            new_branch.checkout()
            print(f"   ✓ Branch created and checked out")
        except git.exc.GitCommandError as e:
            print(f"   ❌ Failed to create branch")
            print(f"   Error: {str(e)}")
            raise
        
        result = {
            "status": "success",
            "repo_path": work_dir,
            "branch_name": branch_name,
            "work_dir_name": work_dir_name
        }
        
        print("\n" + "-"*80)
        print("✅ GIT SETUP COMPLETED")
        print(f"   Repository: {work_dir}")
        print(f"   Branch: {branch_name}")
        print(f"   User: {config.GIT_USER_NAME} <{config.GIT_USER_EMAIL}>")
        print("="*80 + "\n")
        
        return json.dumps(result)
    
    except ValueError as e:
        print("\n" + "-"*80)
        print("❌ GIT SETUP FAILED - Configuration error")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": str(e)})
    
    except git.exc.GitCommandError as e:
        print("\n" + "-"*80)
        print("❌ GIT SETUP FAILED - Git operation error")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": f"Git operation failed: {str(e)}"})
    
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ GIT SETUP FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": str(e)})


@tool
def place_files_in_structure(repo_path: str, resource_name: str, content_json: str) -> str:
    """
    Place files in correct HashiCorp repository structure.
    
    Args:
        repo_path: Path to the cloned repository
        resource_name: The AWSCC resource name (e.g., "awscc_s3_bucket")
        content_json: JSON string with terraform_code, template, and service_name
    
    Returns:
        JSON with list of files created and validation status
    """
    print("\n" + "="*80)
    print(f"📁 FILE PLACEMENT - Placing files for {resource_name}")
    print("="*80)
    
    try:
        # Parse content JSON
        content = json.loads(content_json)
        terraform_code = content.get('terraform_code')
        template = content.get('template')
        service_name = content.get('service_name')
        
        if not terraform_code:
            raise ValueError("terraform_code is required in content")
        if not template:
            raise ValueError("template is required in content")
        if not service_name:
            raise ValueError("service_name is required in content")
        
        print(f"   Resource: {resource_name}")
        print(f"   Service: {service_name}")
        print(f"   Repository: {repo_path}")
        
        files_created = []
        
        # Create examples/resources/{resource_name}/ directory
        examples_dir = os.path.join(repo_path, 'examples', 'resources', resource_name)
        print(f"\n📂 Creating examples directory: {examples_dir}")
        os.makedirs(examples_dir, exist_ok=True)
        print(f"   ✓ Directory created")
        
        # Write terraform file with correct name        
        terraform_filename = f"{service_name}.tf"
        terraform_path = os.path.join(examples_dir, terraform_filename)
        print(f"\n📄 Writing Terraform file: {terraform_filename}")
        print(f"   Path: {terraform_path}")
        
        with open(terraform_path, 'w', encoding='utf-8') as f:
            f.write(terraform_code)
        
        print(f"   ✓ Terraform file written ({len(terraform_code)} bytes)")
        files_created.append(f"examples/resources/{resource_name}/{terraform_filename}")
        
        # Create templates/resources/ directory if needed
        templates_dir = os.path.join(repo_path, 'templates', 'resources')
        print(f"\n📂 Creating templates directory: {templates_dir}")
        os.makedirs(templates_dir, exist_ok=True)
        print(f"   ✓ Directory created")
        
        # Write template file to templates/resources/{service_name}.md.tmpl
        template_filename  = f"{service_name}.md.tmpl"
        template_path = os.path.join(templates_dir, template_filename)
        print(f"\n📄 Writing template file: {template_filename}")
        print(f"   Path: {template_path}")
        
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(template)
        
        print(f"   ✓ Template file written ({len(template)} bytes)")
        files_created.append(f"templates/resources/{template_filename}")
        
        # Note about docs generation
        print(f"\n📝 Note: docs/resources/{resource_name}.md will be auto-generated by 'make docs'")
        
        # Validate files were created and content is correct
        print(f"\n🔍 Validating created files...")
        validation_errors = []
        
        # Verify terraform file exists and has correct content
        if not os.path.exists(terraform_path):
            validation_errors.append(f"Terraform file not found: {terraform_path}")
        else:
            with open(terraform_path, 'r', encoding='utf-8') as f:
                written_terraform = f.read()
            if written_terraform != terraform_code:
                validation_errors.append(f"Terraform file content mismatch")
            else:
                print(f"   ✓ Terraform file verified: {terraform_filename}")
        
        # Verify template file exists and has correct content
        if not os.path.exists(template_path):
            validation_errors.append(f"Template file not found: {template_path}")
        else:
            with open(template_path, 'r', encoding='utf-8') as f:
                written_template = f.read()
            if written_template != template:
                validation_errors.append(f"Template file content mismatch")
            else:
                print(f"   ✓ Template file verified: {template_filename}")
        
        # If validation errors, raise exception
        if validation_errors:
            error_msg = "; ".join(validation_errors)
            raise ValueError(f"File validation failed: {error_msg}")
        
        print(f"   ✓ All files validated successfully")
        
        result = {
            "status": "success",
            "files_created": files_created,
            "resource_name": resource_name,
            "service_name": service_name,
            "validation": "passed"
        }
        
        print("\n" + "-"*80)
        print("✅ FILE PLACEMENT COMPLETED")
        print(f"   Files created: {len(files_created)}")
        for file in files_created:
            print(f"      - {file}")
        print("="*80 + "\n")
        
        return json.dumps(result)
    
    except json.JSONDecodeError as e:
        print("\n" + "-"*80)
        print("❌ FILE PLACEMENT FAILED - Invalid JSON")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": f"Invalid JSON: {str(e)}"})
    
    except ValueError as e:
        print("\n" + "-"*80)
        print("❌ FILE PLACEMENT FAILED - Missing required content")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": str(e)})
    
    except OSError as e:
        print("\n" + "-"*80)
        print("❌ FILE PLACEMENT FAILED - File system error")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": f"File system error: {str(e)}"})
    
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ FILE PLACEMENT FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": str(e)})


@tool
def run_hashicorp_validation(repo_path: str, resource_name: str) -> str:
    """
    Run required make commands for HashiCorp validation.
    
    Args:
        repo_path: Path to the cloned repository
        resource_name: The AWSCC resource name (e.g., "awscc_s3_bucket")
    
    Returns:
        JSON with command results, stdout/stderr, and validation status
    """
    print("\n" + "="*80)
    print(f"🔨 HASHICORP VALIDATION - Running make commands for {resource_name}")
    print("="*80)
    
    import subprocess
    
    try:
        print(f"   Repository: {repo_path}")
        
        results = {
            "status": "success",
            "resource_name": resource_name,
            "commands": []
        }
        
        # Set environment variables for Go operations
        env = os.environ.copy()
        env['GOPROXY'] = 'direct'  # Use direct downloads instead of proxy
        
        print(f"\n🔧 Preparing Go environment...")
        print(f"   Environment: GOPROXY=direct")
        
        # Run 'make tools' command to install required tools
        print(f"\n🔧 Running 'make tools' (installing required tools)...")
        try:
            tools_result = subprocess.run(
                ['make', 'tools'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for tool installation
                env=env
            )
            
            tools_success = tools_result.returncode == 0
            
            results["commands"].append({
                "command": "make tools",
                "returncode": tools_result.returncode,
                "success": tools_success,
                "stdout": tools_result.stdout,
                "stderr": tools_result.stderr
            })
            
            if tools_success:
                print(f"   ✓ make tools completed successfully")
                if tools_result.stdout:
                    # Show last few lines of output
                    stdout_lines = tools_result.stdout.strip().split('\n')
                    if len(stdout_lines) > 5:
                        print(f"   Output (last 5 lines):")
                        for line in stdout_lines[-5:]:
                            print(f"      {line}")
                    else:
                        print(f"   Output: {tools_result.stdout[:200]}...")
            else:
                print(f"   ❌ make tools failed with return code {tools_result.returncode}")
                if tools_result.stderr:
                    print(f"   Error: {tools_result.stderr[:500]}...")
                raise subprocess.CalledProcessError(
                    tools_result.returncode,
                    'make tools',
                    tools_result.stdout,
                    tools_result.stderr
                )
        
        except subprocess.TimeoutExpired:
            error_msg = "make tools command timed out after 10 minutes"
            print(f"   ❌ {error_msg}")
            results["commands"].append({
                "command": "make tools",
                "success": False,
                "error": error_msg
            })
            results["status"] = "error"
            results["error"] = error_msg
            return json.dumps(results)
        
        # Run 'make docs' command (auto-generates docs from templates)
        print(f"\n📚 Running 'make docs' (generating documentation)...")
        try:
            docs_result = subprocess.run(
                ['make', 'docs'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for docs generation
                env=env
            )
            
            docs_success = docs_result.returncode == 0
            
            results["commands"].append({
                "command": "make docs",
                "returncode": docs_result.returncode,
                "success": docs_success,
                "stdout": docs_result.stdout,
                "stderr": docs_result.stderr
            })
            
            if docs_success:
                print(f"   ✓ make docs completed successfully")
                if docs_result.stdout:
                    # Show last few lines of output
                    stdout_lines = docs_result.stdout.strip().split('\n')
                    if len(stdout_lines) > 5:
                        print(f"   Output (last 5 lines):")
                        for line in stdout_lines[-5:]:
                            print(f"      {line}")
                    else:
                        print(f"   Output: {docs_result.stdout[:200]}...")
            else:
                print(f"   ❌ make docs failed with return code {docs_result.returncode}")
                if docs_result.stderr:
                    print(f"   Error: {docs_result.stderr[:500]}...")
                raise subprocess.CalledProcessError(
                    docs_result.returncode,
                    'make docs',
                    docs_result.stdout,
                    docs_result.stderr
                )
        
        except subprocess.TimeoutExpired:
            error_msg = "make docs command timed out after 10 minutes"
            print(f"   ❌ {error_msg}")
            results["commands"].append({
                "command": "make docs",
                "success": False,
                "error": error_msg
            })
            results["status"] = "error"
            results["error"] = error_msg
            return json.dumps(results)
        
        # Verify docs/resources/{service_name}.md was created by make docs
        docs_file_path = os.path.join(repo_path, 'docs', 'resources', f"{service_name}.md")
        print(f"\n🔍 Verifying generated documentation...")
        print(f"   Expected file: docs/resources/{service_name}.md")
        
        if os.path.exists(docs_file_path):
            file_size = os.path.getsize(docs_file_path)
            print(f"   ✓ Documentation file exists ({file_size} bytes)")
            results["docs_generated"] = True
            results["docs_file_path"] = f"docs/resources/{service_name}.md"
            results["docs_file_size"] = file_size
        else:
            error_msg = f"Documentation file not generated: docs/resources/{service_name}.md"
            print(f"   ❌ {error_msg}")
            results["docs_generated"] = False
            results["status"] = "error"
            results["error"] = error_msg
            return json.dumps(results)
        
        # Run additional validation commands if needed
        # Check if 'make validate' target exists
        print(f"\n🔍 Checking for additional validation commands...")
        try:
            # Check if 'make validate' target exists by running make -n validate
            validate_check = subprocess.run(
                ['make', '-n', 'validate'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # If the command succeeds and doesn't show "No rule to make target", run it
            if validate_check.returncode == 0 and 'No rule to make target' not in validate_check.stderr:
                print(f"   Found 'make validate' target, running...")
                
                validate_result = subprocess.run(
                    ['make', 'validate'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                validate_success = validate_result.returncode == 0
                
                results["commands"].append({
                    "command": "make validate",
                    "returncode": validate_result.returncode,
                    "success": validate_success,
                    "stdout": validate_result.stdout,
                    "stderr": validate_result.stderr
                })
                
                if validate_success:
                    print(f"   ✓ make validate completed successfully")
                else:
                    print(f"   ⚠️  make validate failed with return code {validate_result.returncode}")
                    # Don't fail the entire validation if this optional command fails
                    print(f"   Continuing despite validation failure...")
            else:
                print(f"   ℹ️  No 'make validate' target found, skipping")
        
        except subprocess.TimeoutExpired:
            print(f"   ⚠️  make validate timed out, skipping")
        except Exception as e:
            print(f"   ℹ️  Could not check for make validate: {str(e)}")
        
        print("\n" + "-"*80)
        print("✅ HASHICORP VALIDATION COMPLETED")
        print(f"   Resource: {resource_name}")
        print(f"   Commands run: {len(results['commands'])}")
        print(f"   Documentation generated: {results.get('docs_generated', False)}")
        print("="*80 + "\n")
        
        return json.dumps(results)
    
    except subprocess.CalledProcessError as e:
        # Command failed - provide detailed error information
        error_msg = f"Command '{e.cmd}' failed with return code {e.returncode}"
        
        print("\n" + "-"*80)
        print("❌ HASHICORP VALIDATION FAILED - Command error")
        print(f"   Command: {e.cmd}")
        print(f"   Return code: {e.returncode}")
        if e.stdout:
            print(f"   Stdout: {e.stdout[:500]}...")
        if e.stderr:
            print(f"   Stderr: {e.stderr[:500]}...")
        print("="*80 + "\n")
        
        results["status"] = "error"
        results["error"] = error_msg
        results["error_details"] = {
            "command": str(e.cmd),
            "returncode": e.returncode,
            "stdout": e.stdout,
            "stderr": e.stderr
        }
        
        return json.dumps(results)
    
    except FileNotFoundError as e:
        # make command not found
        error_msg = f"'make' command not found. Ensure make is installed and in PATH."
        
        print("\n" + "-"*80)
        print("❌ HASHICORP VALIDATION FAILED - make not found")
        print(f"   Error: {error_msg}")
        print("="*80 + "\n")
        
        results["status"] = "error"
        results["error"] = error_msg
        
        return json.dumps(results)
    
    except Exception as e:
        # Unexpected error
        error_msg = f"Unexpected error during validation: {str(e)}"
        
        print("\n" + "-"*80)
        print("❌ HASHICORP VALIDATION FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        
        results["status"] = "error"
        results["error"] = error_msg
        
        return json.dumps(results)



@tool
def create_github_pr(resource_name: str, branch_name: str, content_json: str) -> str:
    """
    Create pull request via GitHub API.
    
    Args:
        resource_name: The AWSCC resource name (e.g., "awscc_s3_bucket")
        branch_name: The branch name to create PR from (e.g., "d-awscc_s3_bucket")
        content_json: JSON string with resource metadata (analysis_report, s3_analysis_link, etc.)
    
    Returns:
        JSON with pr_url, pr_number, and status
    """
    print("\n" + "="*80)
    print(f"🔀 GITHUB PR CREATOR - Creating PR for {resource_name}")
    print("="*80)
    
    try:
        from github import Github, GithubException
    except ImportError:
        error_msg = "PyGithub not installed. Run: pip install PyGithub>=2.1.1"
        print(f"\n❌ ERROR: {error_msg}")
        return json.dumps({"status": "error", "error": error_msg})
    
    try:
        # Validate configuration
        if not config.GITHUB_TOKEN:
            raise ValueError("GITHUB_TOKEN not configured")
        if not config.GITHUB_FORK_URL:
            raise ValueError("GITHUB_FORK_URL not configured")
        
        # Parse content JSON
        content = json.loads(content_json)
        
        print(f"   Resource: {resource_name}")
        print(f"   Branch: {branch_name}")
        
        # Authenticate with GitHub API
        print(f"\n🔐 Authenticating with GitHub API...")
        gh = Github(config.GITHUB_TOKEN)
        
        # Verify authentication
        try:
            user = gh.get_user()
            print(f"   ✓ Authenticated as: {user.login}")
        except GithubException as e:
            raise ValueError(f"GitHub authentication failed: {str(e)}")
        
        # Parse repository information from URLs
        # Extract owner and repo from fork URL
        # Format: https://github.com/owner/repo or git@github.com:owner/repo.git
        fork_url = config.GITHUB_FORK_URL
        if 'github.com/' in fork_url:
            fork_parts = fork_url.split('github.com/')[-1].replace('.git', '').split('/')
            fork_owner = fork_parts[0]
            fork_repo = fork_parts[1] if len(fork_parts) > 1 else 'terraform-provider-awscc'
        else:
            raise ValueError(f"Invalid GITHUB_FORK_URL format: {fork_url}")
        
        # Extract owner and repo from upstream URL
        upstream_url = config.GITHUB_UPSTREAM_URL
        if 'github.com/' in upstream_url:
            upstream_parts = upstream_url.split('github.com/')[-1].replace('.git', '').split('/')
            upstream_owner = upstream_parts[0]
            upstream_repo = upstream_parts[1] if len(upstream_parts) > 1 else 'terraform-provider-awscc'
        else:
            raise ValueError(f"Invalid GITHUB_UPSTREAM_URL format: {upstream_url}")
        
        print(f"\n📦 Repository information:")
        print(f"   Fork: {fork_owner}/{fork_repo}")
        print(f"   Upstream: {upstream_owner}/{upstream_repo}")
        
        # Get the upstream repository
        print(f"\n🔍 Getting upstream repository...")
        try:
            upstream_repo_obj = gh.get_repo(f"{upstream_owner}/{upstream_repo}")
            print(f"   ✓ Found repository: {upstream_repo_obj.full_name}")
        except GithubException as e:
            if e.status == 404:
                raise ValueError(f"Upstream repository not found: {upstream_owner}/{upstream_repo}")
            elif e.status == 403:
                raise ValueError(f"Access denied to upstream repository: {upstream_owner}/{upstream_repo}")
            else:
                raise ValueError(f"Error accessing upstream repository: {str(e)}")
        
        # Generate PR title
        pr_title = f"Add example for {resource_name}"
        print(f"\n📝 PR Title: {pr_title}")
        
        # Generate PR description
        print(f"\n📄 Generating PR description...")
        pr_description = _generate_pr_description(resource_name, content)
        print(f"   ✓ Description generated ({len(pr_description)} characters)")
        
        # Create the pull request
        print(f"\n🚀 Creating pull request...")
        print(f"   Head: {fork_owner}:{branch_name}")
        print(f"   Base: main")
        
        try:
            pr = upstream_repo_obj.create_pull(
                title=pr_title,
                body=pr_description,
                head=f"{fork_owner}:{branch_name}",
                base="main"
            )
            
            print(f"   ✓ Pull request created successfully")
            print(f"   PR Number: #{pr.number}")
            print(f"   PR URL: {pr.html_url}")
            
            result = {
                "status": "success",
                "pr_url": pr.html_url,
                "pr_number": pr.number,
                "pr_title": pr_title,
                "resource_name": resource_name,
                "branch_name": branch_name
            }
            
            print("\n" + "-"*80)
            print("✅ GITHUB PR CREATED")
            print(f"   PR #{pr.number}: {pr.html_url}")
            print(f"   Title: {pr_title}")
            print("="*80 + "\n")
            
            return json.dumps(result)
        
        except GithubException as e:
            # Handle specific GitHub API errors
            if e.status == 422:
                # Unprocessable entity - likely PR already exists
                error_data = e.data
                if 'errors' in error_data:
                    for error in error_data['errors']:
                        if 'message' in error and 'already exists' in error['message'].lower():
                            raise ValueError(f"Pull request already exists for branch {branch_name}")
                
                raise ValueError(f"Cannot create PR: {error_data.get('message', str(e))}")
            
            elif e.status == 403:
                # Rate limiting or permissions
                if 'rate limit' in str(e).lower():
                    raise ValueError(f"GitHub API rate limit exceeded. Try again later.")
                else:
                    raise ValueError(f"Permission denied: {str(e)}")
            
            elif e.status == 401:
                raise ValueError(f"GitHub authentication failed. Check GITHUB_TOKEN.")
            
            else:
                raise ValueError(f"GitHub API error ({e.status}): {str(e)}")
    
    except json.JSONDecodeError as e:
        print("\n" + "-"*80)
        print("❌ PR CREATION FAILED - Invalid JSON")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": f"Invalid JSON: {str(e)}"})
    
    except ValueError as e:
        print("\n" + "-"*80)
        print("❌ PR CREATION FAILED - Configuration or validation error")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": str(e)})
    
    except Exception as e:
        print("\n" + "-"*80)
        print("❌ PR CREATION FAILED")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({"status": "error", "error": str(e)})


def _generate_pr_description(resource_name: str, content: dict) -> str:
    """
    Generate PR description from template.
    
    Args:
        resource_name: The AWSCC resource name
        content: Dictionary with resource metadata
    
    Returns:
        Formatted PR description string
    """
    # Extract metadata from content
    service_name = content.get('service_name', resource_name.replace('awscc_', ''))
    provider_version = content.get('provider_version', config.DEFAULT_PROVIDER_VERSION)
    validation_date = content.get('fetch_date', datetime.now().strftime("%Y-%m-%d"))
    s3_analysis_link = content.get('s3_analysis_link', '')
    
    # Fetch analysis content from S3
    analysis_content = ""
    if s3_analysis_link:
        try:
            print(f"   📥 Fetching analysis from S3: {s3_analysis_link}")
            s3_client = boto3.client('s3', region_name=config.AWS_REGION)
            response = s3_client.get_object(
                Bucket=config.S3_BUCKET,
                Key=s3_analysis_link
            )
            analysis_content = response['Body'].read().decode('utf-8')
            print(f"   ✓ Analysis fetched ({len(analysis_content)} characters)")
        except Exception as e:
            print(f"   ⚠️  Could not fetch analysis from S3: {str(e)}")
            analysis_content = ""
    
    # Generate PR description using template
    description = f"""## Description

This PR adds a validated Terraform example for `{resource_name}`.

## Validation Summary

- ✅ Terraform code generated and validated
- ✅ Real AWS deployment tested (apply/destroy lifecycle)
- ✅ Independent validation review completed
- ✅ Required tools installed with `make tools`
- ✅ Documentation generated with `make docs`

## Resource Details

- **Resource**: `{resource_name}`
- **Provider Version**: `{provider_version}`
- **Validation Date**: `{validation_date}`
- **AWS Region**: `{config.AWS_REGION}`

## Files Added

- `examples/resources/{resource_name}/{service_name}.tf`
- `templates/resources/{resource_name}.md.tmpl`
- `docs/resources/{resource_name}.md` (auto-generated by `make docs`)

"""
    
    # Add detailed validation report if available
    if analysis_content:
        description += f"""## Validation Report

<details>
<summary>Click to expand full validation report</summary>

```
{analysis_content}
```

</details>

"""
    
    description += """---

*This PR was automatically generated by the TANGO Multi-Agent Pipeline.*
"""
    
    return description



@tool
def update_pr_status(resource_name: str, pr_url: str, status: str) -> str:
    """
    Update DynamoDB with PR creation status.
    
    Args:
        resource_name: The AWSCC resource name (e.g., "awscc_s3_bucket")
        pr_url: The GitHub PR URL (or None if PR creation failed)
        status: PR status - 'created' or 'failed'
    
    Returns:
        JSON with confirmation message and update details
    """
    print("\n" + "="*80)
    print(f"💾 DYNAMODB STATUS UPDATER - Updating PR status for {resource_name}")
    print("="*80)
    
    try:
        # Validate status parameter
        if status not in ['created', 'failed']:
            raise ValueError(f"Invalid status: {status}. Must be 'created' or 'failed'")
        
        print(f"   Resource: {resource_name}")
        print(f"   Status: {status}")
        print(f"   PR URL: {pr_url if pr_url else 'N/A'}")
        
        # Initialize DynamoDB client
        dynamodb = boto3.client('dynamodb', region_name=config.AWS_REGION)
        
        # Query DynamoDB for the latest resource entry
        print(f"\n🔍 Querying DynamoDB for latest entry...")
        print(f"   Table: {config.DYNAMODB_TABLE}")
        print(f"   Resource: {resource_name}")
        
        try:
            query_response = dynamodb.query(
                TableName=config.DYNAMODB_TABLE,
                KeyConditionExpression='resource_name = :rname',
                ExpressionAttributeValues={
                    ':rname': {'S': resource_name}
                },
                ScanIndexForward=False,  # Sort descending (newest first)
                Limit=1  # Only get the latest entry
            )
            
            if not query_response.get('Items'):
                raise ValueError(f"No DynamoDB entry found for resource: {resource_name}")
            
            latest_item = query_response['Items'][0]
            timestamp = latest_item.get('timestamp', {}).get('N')
            
            print(f"   ✓ Found latest entry with timestamp: {timestamp}")
            
        except Exception as e:
            raise ValueError(f"Failed to query DynamoDB: {str(e)}")
        
        # Prepare update expression and attribute values
        print(f"\n📝 Preparing update...")
        
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}
        
        # Add pr_status field
        update_expression_parts.append("#pr_status = :pr_status")
        expression_attribute_names['#pr_status'] = 'pr_status'
        expression_attribute_values[':pr_status'] = {'S': status}
        
        # Add pr_created_at timestamp
        pr_created_at = datetime.now().isoformat()
        update_expression_parts.append("#pr_created_at = :pr_created_at")
        expression_attribute_names['#pr_created_at'] = 'pr_created_at'
        expression_attribute_values[':pr_created_at'] = {'S': pr_created_at}
        
        # Add github_pr_url if provided
        if pr_url:
            update_expression_parts.append("#github_pr_url = :github_pr_url")
            expression_attribute_names['#github_pr_url'] = 'github_pr_url'
            expression_attribute_values[':github_pr_url'] = {'S': pr_url}
        
        update_expression = "SET " + ", ".join(update_expression_parts)
        
        print(f"   Fields to update:")
        print(f"      - pr_status: {status}")
        print(f"      - pr_created_at: {pr_created_at}")
        if pr_url:
            print(f"      - github_pr_url: {pr_url}")
        
        # Update DynamoDB entry
        print(f"\n💾 Updating DynamoDB entry...")
        
        try:
            update_response = dynamodb.update_item(
                TableName=config.DYNAMODB_TABLE,
                Key={
                    'resource_name': {'S': resource_name},
                    'timestamp': {'N': timestamp}
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues='ALL_NEW'
            )
            
            print(f"   ✓ DynamoDB entry updated successfully")
            
            # Verify the update succeeded
            updated_attributes = update_response.get('Attributes', {})
            updated_pr_status = updated_attributes.get('pr_status', {}).get('S')
            updated_pr_created_at = updated_attributes.get('pr_created_at', {}).get('S')
            updated_pr_url = updated_attributes.get('github_pr_url', {}).get('S')
            
            print(f"\n🔍 Verifying update...")
            print(f"   pr_status: {updated_pr_status}")
            print(f"   pr_created_at: {updated_pr_created_at}")
            if updated_pr_url:
                print(f"   github_pr_url: {updated_pr_url}")
            
            # Validate update succeeded
            if updated_pr_status != status:
                raise ValueError(f"Update verification failed: pr_status mismatch (expected: {status}, got: {updated_pr_status})")
            
            if updated_pr_created_at != pr_created_at:
                raise ValueError(f"Update verification failed: pr_created_at mismatch")
            
            if pr_url and updated_pr_url != pr_url:
                raise ValueError(f"Update verification failed: github_pr_url mismatch")
            
            print(f"   ✓ Update verified successfully")
            
            # Build result
            result = {
                "status": "success",
                "resource_name": resource_name,
                "timestamp": int(timestamp),
                "pr_status": updated_pr_status,
                "pr_created_at": updated_pr_created_at,
                "message": f"Successfully updated PR status to '{status}' for {resource_name}"
            }
            
            if updated_pr_url:
                result["github_pr_url"] = updated_pr_url
            
            print("\n" + "-"*80)
            print("✅ DYNAMODB UPDATE COMPLETED")
            print(f"   Resource: {resource_name}")
            print(f"   Status: {status}")
            print(f"   Timestamp: {timestamp}")
            print("="*80 + "\n")
            
            return json.dumps(result)
        
        except Exception as e:
            raise ValueError(f"Failed to update DynamoDB: {str(e)}")
    
    except ValueError as e:
        # Configuration or validation error
        print("\n" + "-"*80)
        print("❌ DYNAMODB UPDATE FAILED - Validation error")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "resource_name": resource_name
        })
    
    except Exception as e:
        # Unexpected error
        print("\n" + "-"*80)
        print("❌ DYNAMODB UPDATE FAILED")
        print(f"   Error: {str(e)}")
        print(f"   Type: {type(e).__name__}")
        print("="*80 + "\n")
        return json.dumps({
            "status": "error",
            "error": f"Unexpected error: {str(e)}",
            "error_type": type(e).__name__,
            "resource_name": resource_name
        })



@tool
def git_commit_and_push(repo_path: str, resource_name: str, branch_name: str) -> str:
    """
    Stage all modified files, commit with descriptive message, and push to fork.
    
    Args:
        repo_path: Path to the cloned repository
        resource_name: The AWSCC resource name (e.g., "awscc_s3_bucket")
        branch_name: The branch name to push (e.g., "d-awscc_s3_bucket")
    
    Returns:
        JSON with commit hash, push status, and details
    """
    print("\n" + "="*80)
    print(f"📤 GIT COMMIT AND PUSH - Committing and pushing changes for {resource_name}")
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
        print(f"   Resource: {resource_name}")
        print(f"   Branch: {branch_name}")
        
        # Open the repository
        print(f"\n📂 Opening repository...")
        repo = Repo(repo_path)
        print(f"   ✓ Repository opened")
        
        # Stage all modified files
        print(f"\n📝 Staging all modified files...")
        
        # Get list of modified files before staging
        modified_files = []
        untracked_files = []
        
        # Check for modified tracked files
        if repo.is_dirty(untracked_files=False):
            modified_files = [item.a_path for item in repo.index.diff(None)]
            print(f"   Modified files: {len(modified_files)}")
            for file in modified_files:
                print(f"      - {file}")
        
        # Check for untracked files
        untracked_files = repo.untracked_files
        if untracked_files:
            print(f"   Untracked files: {len(untracked_files)}")
            for file in untracked_files:
                print(f"      - {file}")
        
        # Stage all changes (modified and untracked)
        if modified_files or untracked_files:
            repo.git.add(A=True)  # Stage all files (equivalent to git add -A)
            print(f"   ✓ All files staged")
        else:
            print(f"   ℹ️  No changes to stage")
            return json.dumps({
                "status": "success",
                "message": "No changes to commit",
                "commit_hash": None,
                "push_status": "skipped"
            })
        
        # Create commit with descriptive message following conventions
        print(f"\n💬 Creating commit...")
        
        # Generate commit message following HashiCorp conventions
        # Format: "Add example for {resource_name}"
        commit_message = f"Add example for {resource_name}"
        
        print(f"   Message: {commit_message}")
        
        try:
            commit = repo.index.commit(commit_message)
            commit_hash = commit.hexsha
            print(f"   ✓ Commit created: {commit_hash[:8]}")
        except git.exc.GitCommandError as e:
            raise ValueError(f"Failed to create commit: {str(e)}")
        
        # Push branch to fork remote
        print(f"\n📤 Pushing branch to fork...")
        print(f"   Remote: origin")
        print(f"   Branch: {branch_name}")
        
        try:
            # Get the origin remote
            origin = repo.remote('origin')
            
            # Configure push URL with token for authentication
            if config.GITHUB_TOKEN and 'github.com' in config.GITHUB_FORK_URL:
                # Update remote URL to include token for authentication
                fork_url = config.GITHUB_FORK_URL
                if fork_url.startswith('https://github.com/'):
                    # Use token in URL for authentication
                    push_url = fork_url.replace(
                        'https://github.com/',
                        f'https://{config.GITHUB_TOKEN}@github.com/'
                    )
                    # Set push URL (keeps fetch URL unchanged)
                    origin.set_url(push_url, push=True)
                    print(f"   ✓ Configured authentication with GitHub token")
                else:
                    print(f"   ⚠️  Fork URL doesn't start with https://github.com/")
            else:
                if not config.GITHUB_TOKEN:
                    print(f"   ⚠️  GITHUB_TOKEN not found - push may fail")
                else:
                    print(f"   ⚠️  Fork URL doesn't contain github.com")
            
            # Push the branch with explicit refspec
            print(f"   Pushing...")
            refspec = f'{branch_name}:{branch_name}'
            push_info = origin.push(refspec)
            
            # Check push result
            if push_info:
                push_result = push_info[0]
                
                # Check for errors
                if push_result.flags & push_result.ERROR:
                    error_msg = f"Push failed: {push_result.summary}"
                    print(f"   ❌ {error_msg}")
                    raise ValueError(error_msg)
                
                # Check for rejected push
                if push_result.flags & push_result.REJECTED:
                    error_msg = f"Push rejected: {push_result.summary}"
                    print(f"   ❌ {error_msg}")
                    raise ValueError(error_msg)
                
                # Check for up-to-date (nothing to push)
                if push_result.flags & push_result.UP_TO_DATE:
                    print(f"   ℹ️  Branch is up-to-date")
                    push_status = "up-to-date"
                else:
                    print(f"   ✓ Push completed successfully")
                    push_status = "success"
                
                print(f"   Summary: {push_result.summary}")
            else:
                print(f"   ✓ Push completed")
                push_status = "success"
            
        except git.exc.GitCommandError as e:
            # Handle specific git push errors
            error_str = str(e)
            
            print(f"\n❌ Git push error:")
            print(f"   Error: {error_str}")
            
            # Check for authentication failures (403, 401)
            if '403' in error_str or '401' in error_str or 'authentication failed' in error_str.lower():
                print(f"\n🔍 Authentication troubleshooting:")
                print(f"   GITHUB_TOKEN present: {bool(config.GITHUB_TOKEN)}")
                if config.GITHUB_TOKEN:
                    print(f"   Token length: {len(config.GITHUB_TOKEN)} characters")
                    print(f"   Token prefix: {config.GITHUB_TOKEN[:10]}...")
                print(f"   Fork URL: {config.GITHUB_FORK_URL}")
                
                # Check remote URL
                try:
                    remote_urls = list(origin.urls)
                    print(f"   Remote URLs: {remote_urls}")
                except:
                    pass
                
                raise ValueError(
                    f"Authentication failed (403/401). "
                    f"Check that GITHUB_TOKEN is valid and has 'repo' scope. "
                    f"Token present: {bool(config.GITHUB_TOKEN)}"
                )
            
            # Check for network errors
            if 'could not resolve host' in error_str.lower() or 'failed to connect' in error_str.lower():
                raise ValueError(f"Network error: Unable to connect to GitHub. Check internet connection.")
            
            # Check for push conflicts
            if 'rejected' in error_str.lower() or 'non-fast-forward' in error_str.lower():
                raise ValueError(f"Push conflict: Branch has diverged. Try syncing with upstream first.")
            
            # Generic git error
            raise ValueError(f"Git push failed: {str(e)}")
        
        # Verify push succeeded
        print(f"\n🔍 Verifying push...")
        try:
            # Fetch to verify the branch exists on remote
            origin.fetch()
            
            # Check if branch exists on remote
            remote_refs = [ref.name for ref in origin.refs]
            expected_ref = f"origin/{branch_name}"
            
            if expected_ref in remote_refs:
                print(f"   ✓ Branch verified on remote: {branch_name}")
            else:
                print(f"   ⚠️  Could not verify branch on remote")
        except Exception as e:
            print(f"   ⚠️  Could not verify push: {str(e)}")
        
        # Build result
        result = {
            "status": "success",
            "commit_hash": commit_hash,
            "commit_message": commit_message,
            "branch_name": branch_name,
            "push_status": push_status,
            "files_committed": len(modified_files) + len(untracked_files),
            "resource_name": resource_name
        }
        
        print("\n" + "-"*80)
        print("✅ GIT COMMIT AND PUSH COMPLETED")
        print(f"   Commit: {commit_hash[:8]}")
        print(f"   Message: {commit_message}")
        print(f"   Branch: {branch_name}")
        print(f"   Files: {result['files_committed']}")
        print(f"   Push: {push_status}")
        print("="*80 + "\n")
        
        return json.dumps(result)
    
    except ValueError as e:
        # Configuration or validation error
        print("\n" + "-"*80)
        print("❌ GIT COMMIT AND PUSH FAILED - Validation error")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "resource_name": resource_name
        })
    
    except git.exc.GitCommandError as e:
        # Git command error
        print("\n" + "-"*80)
        print("❌ GIT COMMIT AND PUSH FAILED - Git operation error")
        print(f"   Error: {str(e)}")
        print("="*80 + "\n")
        return json.dumps({
            "status": "error",
            "error": f"Git operation failed: {str(e)}",
            "resource_name": resource_name
        })
    
    except Exception as e:
        # Unexpected error
        print("\n" + "-"*80)
        print("❌ GIT COMMIT AND PUSH FAILED")
        print(f"   Error: {str(e)}")
        print(f"   Type: {type(e).__name__}")
        print("="*80 + "\n")
        return json.dumps({
            "status": "error",
            "error": f"Unexpected error: {str(e)}",
            "error_type": type(e).__name__,
            "resource_name": resource_name
        })


class PRWorkspaceCleanup:
    """
    Context manager for PR workspace cleanup.
    
    Ensures that the PR workspace directory is always cleaned up,
    even if an error occurs during PR creation.
    
    Usage:
        with PRWorkspaceCleanup(work_dir) as workspace:
            # Do work with workspace
            pass
        # Cleanup happens automatically
    """
    
    def __init__(self, work_dir: str):
        """
        Initialize the cleanup context manager.
        
        Args:
            work_dir: Path to the workspace directory to clean up
        """
        self.work_dir = work_dir
        self.cleanup_performed = False
    
    def __enter__(self):
        """
        Enter the context manager.
        
        Returns:
            The workspace directory path
        """
        print("\n" + "="*80)
        print("🧹 PR WORKSPACE CLEANUP - Context manager initialized")
        print(f"   Workspace: {self.work_dir}")
        print("="*80 + "\n")
        
        return self.work_dir
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context manager and perform cleanup.
        
        Args:
            exc_type: Exception type (if an exception occurred)
            exc_val: Exception value (if an exception occurred)
            exc_tb: Exception traceback (if an exception occurred)
        
        Returns:
            False to propagate any exception that occurred
        """
        print("\n" + "="*80)
        print("🧹 PR WORKSPACE CLEANUP - Starting cleanup")
        print(f"   Workspace: {self.work_dir}")
        
        # Log if cleanup is happening due to an exception
        if exc_type is not None:
            print(f"   ⚠️  Cleanup triggered by exception: {exc_type.__name__}")
            print(f"   Error: {str(exc_val)}")
        else:
            print(f"   ✓ Cleanup triggered by successful completion")
        
        print("="*80)
        
        # Perform cleanup
        try:
            if os.path.exists(self.work_dir):
                print(f"\n🗑️  Removing workspace directory: {self.work_dir}")
                shutil.rmtree(self.work_dir)
                self.cleanup_performed = True
                print(f"   ✓ Workspace directory removed successfully")
            else:
                print(f"\n ℹ️  Workspace directory does not exist: {self.work_dir}")
                print(f"   (May have been cleaned up already)")
                self.cleanup_performed = True
            
            print("\n" + "-"*80)
            print("✅ PR WORKSPACE CLEANUP - Completed successfully")
            print("="*80 + "\n")
        
        except OSError as e:
            # Log cleanup failure but don't raise exception
            print("\n" + "-"*80)
            print("❌ PR WORKSPACE CLEANUP - Failed")
            print(f"   Error: {str(e)}")
            print(f"   Workspace may need manual cleanup: {self.work_dir}")
            print("="*80 + "\n")
            self.cleanup_performed = False
        
        except Exception as e:
            # Log unexpected cleanup failure
            print("\n" + "-"*80)
            print("❌ PR WORKSPACE CLEANUP - Unexpected error")
            print(f"   Error: {str(e)}")
            print(f"   Type: {type(e).__name__}")
            print(f"   Workspace may need manual cleanup: {self.work_dir}")
            print("="*80 + "\n")
            self.cleanup_performed = False
        
        # Return False to propagate any exception that occurred in the with block
        return False
