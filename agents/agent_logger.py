"""
Agent Logger Utility
Provides consistent logging for all agents with timing information
"""

import time
from datetime import datetime
from typing import Optional

class AgentLogger:
    """Helper class for consistent agent logging"""
    
    def __init__(self, agent_name: str, icon: str):
        self.agent_name = agent_name
        self.icon = icon
        self.start_time = None
        
    def start(self):
        """Log agent start"""
        self.start_time = time.time()
        timestamp = datetime.now().strftime('%H:%M:%S')
        print("\n" + "="*80)
        print(f"{self.icon} {self.agent_name} - STARTING [{timestamp}]")
        print("="*80)
        
    def complete(self, details: Optional[str] = None):
        """Log agent completion"""
        duration = time.time() - self.start_time if self.start_time else 0
        timestamp = datetime.now().strftime('%H:%M:%S')
        print("\n" + "-"*80)
        print(f"✅ {self.agent_name} - COMPLETED [{timestamp}] ({duration:.2f}s)")
        if details:
            for line in details.split('\n'):
                print(f"   {line}")
        print("="*80 + "\n")
        
    def fail(self, error: str):
        """Log agent failure"""
        duration = time.time() - self.start_time if self.start_time else 0
        timestamp = datetime.now().strftime('%H:%M:%S')
        print("\n" + "-"*80)
        print(f"❌ {self.agent_name} - FAILED [{timestamp}] ({duration:.2f}s)")
        print(f"   Error: {error}")
        print("="*80 + "\n")


# Pre-configured loggers for each agent
def get_discovery_logger():
    return AgentLogger("DISCOVERY AGENT", "🔍")

def get_documentation_logger():
    return AgentLogger("DOCUMENTATION AGENT", "📝")

def get_terraform_logger():
    return AgentLogger("TERRAFORM AGENT", "🔧")

def get_validation_logger():
    return AgentLogger("VALIDATION AGENT", "✓")

def get_terraform_cleanup_logger():
    return AgentLogger("TERRAFORM CLEANUP AGENT", "🧹")

def get_storage_logger():
    return AgentLogger("STORAGE AGENT", "💾")

def get_cleanup_logger():
    return AgentLogger("CLEANUP AGENT", "🗑️")

def get_pr_logger():
    return AgentLogger("PR AGENT", "🔀")
