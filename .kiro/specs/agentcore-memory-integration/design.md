# AgentCore Memory Integration - Design

## Architecture Overview

The memory integration uses a **dual-memory architecture**:

1. **Shared Working Memory**: Actor-level namespaces for cross-agent communication within a pipeline run
2. **Agent-Specific Memory**: Separate memory stores for each agent type to learn from past executions

```
┌─────────────────────────────────────────────────────────────┐
│         TANGO Pipeline Run (awscc_s3_bucket)                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Discovery   │  │Documentation │  │  Terraform   │      │
│  │    Agent     │  │    Agent     │  │    Agent     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            │                                 │
│                    ┌───────▼────────┐                        │
│                    │ Shared Memory  │                        │
│                    │ Actor: awscc_  │                        │
│                    │   s3_bucket    │                        │
│                    │ Namespaces:    │                        │
│                    │ /facts/{actor} │                        │
│                    │ /prefs/{actor} │                        │
│                    └────────────────┘                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Agent-Specific Learning Memory                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Discovery   │  │Documentation │  │  Terraform   │      │
│  │   Memory     │  │   Memory     │  │   Memory     │      │
│  │  (isolated)  │  │  (isolated)  │  │  (isolated)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Memory Configuration Module

**File**: `memory_config.py`

```python
"""
Memory configuration for TANGO pipeline agents.
Manages AgentCore Memory setup and configuration.
"""

import os
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class MemoryConfig:
    """Configuration for AgentCore Memory integration"""
    
    # Shared memory for pipeline runs
    shared_memory_id: str
    
    # Agent-specific memory IDs
    discovery_memory_id: str
    documentation_memory_id: str
    terraform_memory_id: str
    validation_memory_id: str
    cleanup_memory_id: str
    storage_memory_id: str
    
    # Common configuration
    aws_region: str
    actor_id: Optional[str] = None  # Set dynamically per resource
    
    @classmethod
    def from_env(cls, actor_id: Optional[str] = None) -> 'MemoryConfig':
        """
        Load configuration from environment variables.
        
        Args:
            actor_id: Resource name (e.g., 'awscc_s3_bucket'). 
                     If None, must be set before creating agents.
        """
        """Load configuration from environment variables"""
        return cls(
            shared_memory_id=os.environ.get(
                "TANGO_SHARED_MEMORY_ID",
                "tango-shared-memory"
            ),
            discovery_memory_id=os.environ.get(
                "TANGO_DISCOVERY_MEMORY_ID",
                "tango-discovery-memory"
            ),
            documentation_memory_id=os.environ.get(
                "TANGO_DOCUMENTATION_MEMORY_ID",
                "tango-documentation-memory"
            ),
            terraform_memory_id=os.environ.get(
                "TANGO_TERRAFORM_MEMORY_ID",
                "tango-terraform-memory"
            ),
            validation_memory_id=os.environ.get(
                "TANGO_VALIDATION_MEMORY_ID",
                "tango-validation-memory"
            ),
            cleanup_memory_id=os.environ.get(
                "TANGO_CLEANUP_MEMORY_ID",
                "tango-cleanup-memory"
            ),
            storage_memory_id=os.environ.get(
                "TANGO_STORAGE_MEMORY_ID",
                "tango-storage-memory"
            ),
            aws_region=os.environ.get("AWS_REGION", "us-west-2"),
            actor_id=actor_id  # Set dynamically per resource
        )

# Shared retrieval configuration for all agents
SHARED_RETRIEVAL_CONFIG = {
    "/pipeline/facts/{actorId}": {
        "top_k": 10,
        "relevance_score": 0.3
    },
    "/pipeline/preferences/{actorId}": {
        "top_k": 5,
        "relevance_score": 0.7
    }
}

# Agent-specific retrieval configurations
AGENT_RETRIEVAL_CONFIGS = {
    "discovery": {
        "/agent/patterns/{actorId}": {
            "top_k": 5,
            "relevance_score": 0.5
        }
    },
    "documentation": {
        "/agent/code_patterns/{actorId}": {
            "top_k": 8,
            "relevance_score": 0.6
        }
    },
    "terraform": {
        "/agent/validation_fixes/{actorId}": {
            "top_k": 10,
            "relevance_score": 0.4
        }
    }
}
```

### 2. Memory Setup Module

**File**: `memory_setup.py`

```python
"""
Setup and initialization for AgentCore Memory stores.
Creates memory stores with appropriate strategies if they don't exist.
"""

from bedrock_agentcore.memory import MemoryClient
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

def create_shared_memory(
    client: MemoryClient,
    memory_name: str,
    region: str
) -> str:
    """
    Create shared memory store with actor-level strategies.
    
    Returns:
        Memory ID
    """
    try:
        memory = client.create_memory_and_wait(
            name=memory_name,
            description="Shared memory for TANGO pipeline agents",
            strategies=[
                {
                    "semanticMemoryStrategy": {
                        "name": "PipelineFacts",
                        "namespaces": ["/pipeline/facts/{actorId}"]
                    }
                },
                {
                    "userPreferenceMemoryStrategy": {
                        "name": "PipelinePreferences",
                        "namespaces": ["/pipeline/preferences/{actorId}"]
                    }
                }
            ]
        )
        memory_id = memory.get('id')
        logger.info(f"Created shared memory: {memory_id}")
        return memory_id
    except Exception as e:
        logger.error(f"Failed to create shared memory: {e}")
        raise

def create_agent_memory(
    client: MemoryClient,
    memory_name: str,
    agent_type: str,
    region: str
) -> str:
    """
    Create agent-specific memory store with learning strategies.
    
    Args:
        memory_name: Name for the memory store
        agent_type: Type of agent (discovery, documentation, etc.)
        region: AWS region
        
    Returns:
        Memory ID
    """
    try:
        # Define strategies based on agent type
        strategies = get_agent_strategies(agent_type)
        
        memory = client.create_memory_and_wait(
            name=memory_name,
            description=f"Learning memory for {agent_type} agent",
            strategies=strategies
        )
        memory_id = memory.get('id')
        logger.info(f"Created {agent_type} memory: {memory_id}")
        return memory_id
    except Exception as e:
        logger.error(f"Failed to create {agent_type} memory: {e}")
        raise

def get_agent_strategies(agent_type: str) -> List[Dict]:
    """Get memory strategies for specific agent type"""
    
    base_strategies = [
        {
            "semanticMemoryStrategy": {
                "name": f"{agent_type.title()}Patterns",
                "namespaces": [f"/agent/patterns/{{actorId}}"]
            }
        }
    ]
    
    # Agent-specific strategies
    if agent_type == "documentation":
        base_strategies.append({
            "semanticMemoryStrategy": {
                "name": "CodePatterns",
                "namespaces": ["/agent/code_patterns/{actorId}"]
            }
        })
    elif agent_type == "terraform":
        base_strategies.append({
            "semanticMemoryStrategy": {
                "name": "ValidationFixes",
                "namespaces": ["/agent/validation_fixes/{actorId}"]
            }
        })
    
    return base_strategies

def setup_all_memories(region: str) -> Dict[str, str]:
    """
    Setup all required memory stores for TANGO pipeline.
    
    Returns:
        Dictionary mapping memory names to memory IDs
    """
    client = MemoryClient(region_name=region)
    memory_ids = {}
    
    try:
        # Create shared memory
        memory_ids['shared'] = create_shared_memory(
            client,
            "TangoPipelineSharedMemory",
            region
        )
        
        # Create agent-specific memories
        agent_types = [
            'discovery',
            'documentation',
            'terraform',
            'validation',
            'cleanup',
            'storage'
        ]
        
        for agent_type in agent_types:
            memory_ids[agent_type] = create_agent_memory(
                client,
                f"Tango{agent_type.title()}Memory",
                agent_type,
                region
            )
        
        logger.info("All memory stores created successfully")
        return memory_ids
        
    except Exception as e:
        logger.error(f"Memory setup failed: {e}")
        raise
```

### 3. Agent Factory Module

**File**: `agents/agent_factory.py`

```python
"""
Factory for creating agents with memory integration.
Handles session manager setup and agent initialization.
"""

from datetime import datetime
from strands import Agent
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager
)
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class AgentFactory:
    """Factory for creating agents with memory integration"""
    
    def __init__(
        self,
        shared_memory_id: str,
        agent_memory_ids: Dict[str, str],
        actor_id: str,
        pipeline_run_id: str,
        region: str,
        enable_memory: bool = True
    ):
        self.shared_memory_id = shared_memory_id
        self.agent_memory_ids = agent_memory_ids
        self.actor_id = actor_id
        self.pipeline_run_id = pipeline_run_id
        self.region = region
        self.enable_memory = enable_memory
    
    def create_session_manager(
        self,
        agent_name: str,
        memory_id: str,
        retrieval_config: Dict
    ) -> Optional[AgentCoreMemorySessionManager]:
        """Create session manager for an agent"""
        
        if not self.enable_memory:
            return None
        
        try:
            # Convert retrieval config to RetrievalConfig objects
            retrieval_configs = {
                namespace: RetrievalConfig(
                    top_k=config['top_k'],
                    relevance_score=config['relevance_score']
                )
                for namespace, config in retrieval_config.items()
            }
            
            config = AgentCoreMemoryConfig(
                memory_id=memory_id,
                session_id=f"{agent_name}_{self.pipeline_run_id}",
                actor_id=self.actor_id,
                retrieval_config=retrieval_configs
            )
            
            return AgentCoreMemorySessionManager(
                agentcore_memory_config=config,
                region_name=self.region
            )
        except Exception as e:
            logger.warning(
                f"Failed to create session manager for {agent_name}: {e}"
            )
            return None
    
    def create_agent(
        self,
        agent_name: str,
        system_prompt: str,
        tools: list = None,
        use_shared_memory: bool = True,
        use_agent_memory: bool = True
    ) -> Agent:
        """
        Create an agent with memory integration.
        
        Args:
            agent_name: Name of the agent (discovery, documentation, etc.)
            system_prompt: System prompt for the agent
            tools: List of tools for the agent
            use_shared_memory: Whether to use shared memory
            use_agent_memory: Whether to use agent-specific memory
            
        Returns:
            Configured Agent instance
        """
        
        # Determine which memory to use
        memory_id = None
        retrieval_config = {}
        
        if use_shared_memory and use_agent_memory:
            # Use shared memory (primary) with agent memory retrieval
            memory_id = self.shared_memory_id
            retrieval_config = {
                **SHARED_RETRIEVAL_CONFIG,
                **AGENT_RETRIEVAL_CONFIGS.get(agent_name, {})
            }
        elif use_shared_memory:
            # Use only shared memory
            memory_id = self.shared_memory_id
            retrieval_config = SHARED_RETRIEVAL_CONFIG
        elif use_agent_memory:
            # Use only agent-specific memory
            memory_id = self.agent_memory_ids.get(agent_name)
            retrieval_config = AGENT_RETRIEVAL_CONFIGS.get(agent_name, {})
        
        # Create session manager
        session_manager = None
        if memory_id:
            session_manager = self.create_session_manager(
                agent_name,
                memory_id,
                retrieval_config
            )
        
        # Create agent
        agent = Agent(
            system_prompt=system_prompt,
            session_manager=session_manager,
            tools=tools or []
        )
        
        logger.info(
            f"Created {agent_name} agent with memory: "
            f"{'enabled' if session_manager else 'disabled'}"
        )
        
        return agent

# Import shared configs
from memory_config import SHARED_RETRIEVAL_CONFIG, AGENT_RETRIEVAL_CONFIGS
```

### 4. Pipeline Integration

**File**: `agents/pipeline_with_memory.py`

```python
"""
TANGO pipeline with memory integration.
Sequential workflow with shared and agent-specific memory.
"""

from datetime import datetime
from agents.agent_factory import AgentFactory
from memory_config import MemoryConfig
import json
import logging

logger = logging.getLogger(__name__)

def run_pipeline_with_memory():
    """Execute TANGO pipeline with memory integration"""
    
    # Generate pipeline run ID
    pipeline_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info(f"Starting pipeline run: {pipeline_run_id}")
    
    # Load memory configuration (without actor_id yet)
    try:
        memory_config = MemoryConfig.from_env()
        enable_memory = True
    except Exception as e:
        logger.warning(f"Memory configuration failed: {e}. Running without memory.")
        enable_memory = False
    
    # Execute discovery to get resource name
    logger.info("Step 1: Discovery")
    discovery_agent = create_discovery_agent(None)  # No memory for discovery
    discovery_result = discovery_agent("Find next unprocessed resource")
    resource_info = json.loads(str(discovery_result))
    
    if resource_info["resource_name"] == "NONE":
        logger.info("No resources to process")
        return
    
    # Set actor_id to the resource name
    actor_id = resource_info["resource_name"]
    logger.info(f"Processing resource: {actor_id}")
    
    # Create agent factory with resource-specific actor_id
    if enable_memory:
        memory_config.actor_id = actor_id  # Set dynamically
        factory = AgentFactory(
            shared_memory_id=memory_config.shared_memory_id,
            agent_memory_ids={
                'discovery': memory_config.discovery_memory_id,
                'documentation': memory_config.documentation_memory_id,
                'terraform': memory_config.terraform_memory_id,
                'validation': memory_config.validation_memory_id,
                'cleanup': memory_config.cleanup_memory_id,
                'storage': memory_config.storage_memory_id
            },
            actor_id=actor_id,  # Resource-specific actor ID
            pipeline_run_id=pipeline_run_id,
            region=memory_config.aws_region,
            enable_memory=True
        )
    else:
        factory = None
    
    # Create agents with memory (now that we have actor_id)
    documentation_agent = create_documentation_agent(factory)
    terraform_agent = create_terraform_agent(factory)
    validation_agent = create_validation_agent(factory)
    cleanup_agent = create_cleanup_agent(factory)
    storage_agent = create_storage_agent(factory)
    
    # Execute pipeline
    try:
        # Step 2: Documentation (with memory)
        logger.info("Step 2: Documentation")
        doc_input = json.dumps(resource_info)
        terraform_code = documentation_agent(doc_input)
        
        # Step 3: Terraform validation
        logger.info("Step 3: Terraform Validation")
        terraform_input = {
            "terraform_code": str(terraform_code),
            "provider_version": resource_info["provider_version"]
        }
        corrected_code = terraform_agent(json.dumps(terraform_input))
        
        # Step 4: Independent validation
        logger.info("Step 4: Validation")
        validation_input = {
            "terraform_code": str(corrected_code),
            "resource_name": resource_info["resource_name"]
        }
        validation_result = validation_agent(json.dumps(validation_input))
        validation_data = json.loads(str(validation_result))
        
        # Step 5: Cleanup
        logger.info("Step 5: Cleanup")
        cleaned_code = cleanup_agent(str(corrected_code))
        
        # Step 6: Storage
        logger.info("Step 6: Storage")
        storage_input = {
            "resource_name": resource_info["resource_name"],
            "provider_version": resource_info["provider_version"],
            "cleaned_code": str(cleaned_code),
            "validation_result": validation_data["validation_result"],
            "s3_analysis_link": validation_data["s3_path"]
        }
        storage_result = storage_agent(json.dumps(storage_input))
        
        logger.info("Pipeline completed successfully")
        return storage_result
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        raise

def create_discovery_agent(factory):
    """Create discovery agent with memory"""
    # Import from existing module
    from agents.discovery_agent import discovery_agent as base_agent
    
    if factory:
        return factory.create_agent(
            agent_name="discovery",
            system_prompt=base_agent.system_prompt,
            tools=base_agent.tools,
            use_shared_memory=True,
            use_agent_memory=True
        )
    return base_agent

# Similar functions for other agents...
```

## Data Flow

### Shared Memory Flow

```
Discovery Agent
    ↓ (discovers: awscc_s3_bucket)
    ↓ (writes to /pipeline/facts/awscc_s3_bucket)
/pipeline/facts/awscc_s3_bucket
    ↓ (reads)
Documentation Agent
    ↓ (writes code patterns to /pipeline/facts/awscc_s3_bucket)
/pipeline/facts/awscc_s3_bucket
    ↓ (reads)
Terraform Agent
```

**Key Point**: Each resource type (awscc_s3_bucket, awscc_lambda_function, etc.) has its own isolated memory namespace.

### Agent Learning Flow

```
Terraform Agent (Run 1: awscc_s3_bucket)
    ↓ (learns from failure)
/agent/validation_fixes/awscc_s3_bucket
    ↓ (retrieves on Run 2)
Terraform Agent (Run 2: awscc_s3_bucket)
    ↓ (applies learned fix)
Success!
```

**Key Point**: Agent learning is also scoped per resource type, so fixes for S3 buckets don't interfere with Lambda functions.

## Configuration

### Environment Variables

```bash
# Shared memory
export TANGO_SHARED_MEMORY_ID="mem-abc123"

# Agent-specific memories
export TANGO_DISCOVERY_MEMORY_ID="mem-def456"
export TANGO_DOCUMENTATION_MEMORY_ID="mem-ghi789"
export TANGO_TERRAFORM_MEMORY_ID="mem-jkl012"
export TANGO_VALIDATION_MEMORY_ID="mem-mno345"
export TANGO_CLEANUP_MEMORY_ID="mem-pqr678"
export TANGO_STORAGE_MEMORY_ID="mem-stu901"

# AWS configuration
export AWS_REGION="us-west-2"
```

**Note**: Actor ID is set dynamically to the resource name (e.g., `awscc_s3_bucket`) during pipeline execution, not via environment variable.

## Error Handling

1. **Memory Creation Failure**: Log error, continue without memory
2. **Session Manager Creation Failure**: Log warning, create agent without memory
3. **Memory Retrieval Failure**: Log warning, continue with empty context
4. **Memory Write Failure**: Log warning, continue pipeline execution

## Testing Strategy

1. **Unit Tests**: Test memory configuration, session manager creation
2. **Integration Tests**: Test agent creation with memory, memory retrieval
3. **End-to-End Tests**: Test full pipeline with memory enabled
4. **Fallback Tests**: Test pipeline execution with memory disabled

## Migration Path

1. **Phase 1**: Add memory configuration and setup scripts
2. **Phase 2**: Create agent factory with memory support
3. **Phase 3**: Update pipeline to use agent factory
4. **Phase 4**: Test with memory enabled
5. **Phase 5**: Deploy to production with feature flag

## Performance Considerations

- Memory retrieval adds ~500ms per agent invocation
- Shared memory reduces need for explicit data passing
- Agent learning improves success rate over time
- Memory operations are logged for observability

## Security Considerations

- Memory stores use AWS IAM for access control
- Actor ID scopes memory access to pipeline
- Session IDs prevent cross-session data leakage
- Memory data is encrypted at rest by AgentCore
