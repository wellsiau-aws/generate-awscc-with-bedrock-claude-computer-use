"""
PR Agent Logging Utilities
Provides structured logging, progress indicators, and summary reporting for the PR agent
"""

import time
from datetime import datetime
from typing import Optional, Dict, List


class PRAgentLogger:
    """
    Structured logger for PR agent with progress tracking and timing.
    """
    
    def __init__(self, resource_name: Optional[str] = None):
        self.resource_name = resource_name
        self.start_time = None
        self.step_times = {}
        self.current_step = None
        self.total_steps = 8  # Total number of steps in PR workflow
        self.completed_steps = 0
        self.files_created = []
        self.validation_results = {}
        
    def start(self, resource_name: Optional[str] = None):
        """Log PR agent start with resource information"""
        if resource_name:
            self.resource_name = resource_name
        
        self.start_time = time.time()
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        print("\n" + "="*80)
        print(f"🔀 PR AGENT - STARTING [{timestamp}]")
        print("="*80)
        
        if self.resource_name:
            print(f"   Resource: {self.resource_name}")
        else:
            print(f"   Mode: Query next eligible resource")
        
        print(f"   Total steps: {self.total_steps}")
        print("="*80)
    
    def step_start(self, step_number: int, step_name: str, description: Optional[str] = None):
        """Log the start of a workflow step with progress indicator"""
        self.current_step = step_number
        self.step_times[step_number] = {'name': step_name, 'start': time.time()}
        
        # Calculate progress percentage
        progress_pct = (self.completed_steps / self.total_steps) * 100
        
        # Calculate estimated time remaining
        elapsed = time.time() - self.start_time
        if self.completed_steps > 0:
            avg_time_per_step = elapsed / self.completed_steps
            remaining_steps = self.total_steps - self.completed_steps
            estimated_remaining = avg_time_per_step * remaining_steps
            eta_str = f" | ETA: {estimated_remaining:.0f}s"
        else:
            eta_str = ""
        
        print("\n" + "="*80)
        print(f"STEP {step_number}/{self.total_steps}: {step_name}")
        print(f"Progress: [{self._progress_bar(progress_pct)}] {progress_pct:.0f}%{eta_str}")
        print("="*80)
        
        if description:
            print(f"   {description}")
    
    def step_complete(self, details: Optional[str] = None):
        """Log the completion of a workflow step"""
        if self.current_step is None:
            return
        
        step_data = self.step_times.get(self.current_step, {})
        step_start = step_data.get('start')
        step_name = step_data.get('name', 'Unknown')
        
        if step_start:
            duration = time.time() - step_start
            step_data['duration'] = duration
            step_data['end'] = time.time()
            
            print(f"\n   ✓ {step_name} completed ({duration:.2f}s)")
            
            if details:
                for line in details.split('\n'):
                    if line.strip():
                        print(f"      {line}")
        
        self.completed_steps += 1
        self.current_step = None
    
    def step_fail(self, error: str):
        """Log the failure of a workflow step"""
        if self.current_step is None:
            return
        
        step_data = self.step_times.get(self.current_step, {})
        step_start = step_data.get('start')
        step_name = step_data.get('name', 'Unknown')
        
        if step_start:
            duration = time.time() - step_start
            step_data['duration'] = duration
            step_data['end'] = time.time()
            step_data['error'] = error
            
            print(f"\n   ❌ {step_name} failed ({duration:.2f}s)")
            print(f"      Error: {error}")
        
        self.current_step = None
    
    def log_operation(self, operation: str, status: str = "info", details: Optional[str] = None):
        """Log a sub-operation within a step"""
        icon = {
            "info": "ℹ️",
            "success": "✓",
            "warning": "⚠️",
            "error": "❌",
            "progress": "⏳"
        }.get(status, "•")
        
        print(f"   {icon} {operation}")
        
        if details:
            for line in details.split('\n'):
                if line.strip():
                    print(f"      {line}")
    
    def add_file_created(self, file_path: str):
        """Track a file that was created"""
        self.files_created.append(file_path)
    
    def add_validation_result(self, command: str, success: bool, duration: Optional[float] = None):
        """Track a validation command result"""
        self.validation_results[command] = {
            'success': success,
            'duration': duration
        }
    
    def complete(self, pr_url: Optional[str] = None, pr_number: Optional[int] = None, 
                 branch_name: Optional[str] = None, commit_hash: Optional[str] = None):
        """Log PR agent completion with summary"""
        total_duration = time.time() - self.start_time if self.start_time else 0
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        print("\n" + "="*80)
        print(f"✅ PR AGENT - COMPLETED SUCCESSFULLY [{timestamp}]")
        print("="*80)
        
        # Summary section
        print("\n📊 SUMMARY")
        print("-" * 80)
        
        if self.resource_name:
            print(f"   Resource: {self.resource_name}")
        
        if pr_url:
            print(f"   PR URL: {pr_url}")
        
        if pr_number:
            print(f"   PR Number: #{pr_number}")
        
        if branch_name:
            print(f"   Branch: {branch_name}")
        
        if commit_hash:
            print(f"   Commit: {commit_hash}")
        
        # Files created
        if self.files_created:
            print(f"\n   Files Created ({len(self.files_created)}):")
            for file in self.files_created:
                print(f"      - {file}")
        
        # Validation results
        if self.validation_results:
            print(f"\n   Validation Results:")
            for command, result in self.validation_results.items():
                status_icon = "✓" if result['success'] else "❌"
                duration_str = f" ({result['duration']:.2f}s)" if result.get('duration') else ""
                print(f"      {status_icon} {command}{duration_str}")
        
        # Timing statistics
        print(f"\n⏱️  TIMING STATISTICS")
        print("-" * 80)
        print(f"   Total Duration: {total_duration:.2f}s ({total_duration/60:.1f}m)")
        print(f"   Steps Completed: {self.completed_steps}/{self.total_steps}")
        
        if self.step_times:
            print(f"\n   Step Breakdown:")
            for step_num in sorted(self.step_times.keys()):
                step_data = self.step_times[step_num]
                step_name = step_data.get('name', 'Unknown')
                duration = step_data.get('duration', 0)
                pct = (duration / total_duration * 100) if total_duration > 0 else 0
                print(f"      {step_num}. {step_name}: {duration:.2f}s ({pct:.1f}%)")
        
        print("\n" + "="*80 + "\n")
    
    def fail(self, error: str, error_type: Optional[str] = None):
        """Log PR agent failure with summary"""
        total_duration = time.time() - self.start_time if self.start_time else 0
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        print("\n" + "="*80)
        print(f"❌ PR AGENT - FAILED [{timestamp}]")
        print("="*80)
        
        print(f"\n   Error: {error}")
        
        if error_type:
            print(f"   Type: {error_type}")
        
        if self.resource_name:
            print(f"   Resource: {self.resource_name}")
        
        print(f"\n   Duration: {total_duration:.2f}s")
        print(f"   Steps Completed: {self.completed_steps}/{self.total_steps}")
        
        if self.current_step:
            current_step_data = self.step_times.get(self.current_step, {})
            current_step_name = current_step_data.get('name', 'Unknown')
            print(f"   Failed at: Step {self.current_step} - {current_step_name}")
        
        print("\n" + "="*80 + "\n")
    
    def _progress_bar(self, percentage: float, width: int = 40) -> str:
        """Generate a text-based progress bar"""
        filled = int(width * percentage / 100)
        empty = width - filled
        return "█" * filled + "░" * empty


class PRStepLogger:
    """
    Context manager for logging individual PR workflow steps.
    Automatically logs step start and completion/failure.
    """
    
    def __init__(self, logger: PRAgentLogger, step_number: int, step_name: str, 
                 description: Optional[str] = None):
        self.logger = logger
        self.step_number = step_number
        self.step_name = step_name
        self.description = description
        self.success = False
    
    def __enter__(self):
        self.logger.step_start(self.step_number, self.step_name, self.description)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # No exception - step completed successfully
            self.logger.step_complete()
        else:
            # Exception occurred - step failed
            self.logger.step_fail(str(exc_val))
        
        return False  # Don't suppress exceptions


# Convenience function to create a PR logger
def create_pr_logger(resource_name: Optional[str] = None) -> PRAgentLogger:
    """Create a new PR agent logger instance"""
    return PRAgentLogger(resource_name)
