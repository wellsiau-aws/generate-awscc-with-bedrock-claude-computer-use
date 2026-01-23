# AgentCore Memory Integration - Requirements

## Feature Overview

Integrate Amazon Bedrock AgentCore Memory into the TANGO Multi-Agent Pipeline to provide:
1. **Shared working memory** across all agents in a pipeline run using actor-level namespaces
2. **Isolated agent memory** for each agent to learn from past executions
3. **Long-term memory (LTM)** with semantic search and intelligent retrieval
4. **Short-term memory (STM)** for conversation history within each agent's session

This enables agents to share context during pipeline execution while maintaining their own learning and conversation history.

## User Stories

### 1. Shared Working Memory Across Agents

**As a** pipeline orchestrator  
**I want** all agents to access shared working memory during a pipeline run  
**So that** agents can build upon each other's work without manual data passing

**Acceptance Criteria:**
- 1.1 All agents in a pipeline run can write facts to shared memory namespace
- 1.2 All agents in a pipeline run can retrieve facts from shared memory namespace
- 1.3 Discovery agent stores resource information that documentation agent can retrieve
- 1.4 Documentation agent stores Terraform code metadata that validation agent can retrieve
- 1.5 Shared memory uses actor-level namespaces (e.g., `/facts/{actorId}`)
- 1.6 Each agent uses a unique session ID to avoid "one agent per session" limitation
- 1.7 All agents use the same actor ID to access shared namespaces

### 2. Isolated Agent Learning Memory

**As an** individual agent  
**I want** my own isolated memory to learn from past executions  
**So that** I can improve my performance over time without interference from other agents

**Acceptance Criteria:**
- 2.1 Each agent type has its own dedicated memory store (discovery_memory, documentation_memory, etc.)
- 2.2 Discovery agent learns from past resource discovery patterns
- 2.3 Documentation agent learns from successful Terraform code patterns
- 2.4 Terraform agent learns from validation failures and fixes
- 2.5 Agent-specific memories persist across pipeline runs
- 2.6 Agent memories are scoped by agent type, not by pipeline run

### 3. Memory Configuration and Setup

**As a** system administrator  
**I want** to configure memory stores with appropriate strategies  
**So that** the system extracts and stores relevant information automatically

**Acceptance Criteria:**
- 3.1 Shared memory store is created with semantic memory strategy for facts
- 3.2 Shared memory store is created with user preference strategy for patterns
- 3.3 Each agent-specific memory store is created with appropriate strategies
- 3.4 Memory configuration is externalized to config.py
- 3.5 Memory IDs can be provided via environment variables
- 3.6 Setup script creates all required memory stores if they don't exist
- 3.7 Memory stores are created in the configured AWS region

### 4. Pipeline Integration

**As a** pipeline developer  
**I want** memory integration to be transparent to existing pipeline logic  
**So that** I can add memory without major refactoring

**Acceptance Criteria:**
- 4.1 Agents are created with session managers in a factory function
- 4.2 Pipeline run ID is generated at the start of each execution
- 4.3 Session IDs follow pattern: `{agent_name}_{pipeline_run_id}`
- 4.4 Actor ID is consistent across all agents: `tango_pipeline`
- 4.5 Existing agent system prompts are preserved
- 4.6 Memory integration doesn't break existing DynamoDB/S3 storage
- 4.7 Pipeline can run without memory if memory stores are not configured

### 5. Memory Retrieval and Context

**As an** agent  
**I want** to retrieve relevant memories based on my current task  
**So that** I can make informed decisions using past knowledge

**Acceptance Criteria:**
- 5.1 Agents retrieve top-k relevant facts from shared memory
- 5.2 Retrieval uses semantic search with configurable relevance threshold
- 5.3 Retrieved memories are automatically included in agent context
- 5.4 Retrieval configuration is customizable per agent
- 5.5 Agents can access memories from multiple namespaces
- 5.6 Memory retrieval doesn't significantly slow down pipeline execution

### 6. Error Handling and Fallback

**As a** system operator  
**I want** the pipeline to handle memory failures gracefully  
**So that** memory issues don't break the entire pipeline

**Acceptance Criteria:**
- 6.1 Pipeline continues if memory stores are not available
- 6.2 Agents log warnings when memory operations fail
- 6.3 Memory creation failures are caught and reported
- 6.4 Invalid memory configurations are detected at startup
- 6.5 Pipeline falls back to non-memory mode if AgentCore Memory is unavailable
- 6.6 Error messages clearly indicate memory-related issues

## Technical Constraints

1. **AgentCore Memory Limitation**: Only one agent per session ID
   - **Solution**: Use unique session IDs per agent, same actor ID for sharing

2. **Strands Multi-Agent Limitation**: Agents in multi-agent patterns cannot have session managers
   - **Solution**: Use sequential workflow pattern instead of orchestrator pattern

3. **Namespace Scoping**: Session-level namespaces are not shared across sessions
   - **Solution**: Use actor-level namespaces for shared memory

4. **AWS Region**: All memory operations must use the same AWS region as the pipeline

5. **Dependencies**: Requires `bedrock-agentcore[strands-agents]` package

## Non-Functional Requirements

1. **Performance**: Memory operations should add < 2 seconds to pipeline execution
2. **Reliability**: Memory failures should not cause pipeline failures
3. **Scalability**: Support up to 10 concurrent pipeline runs
4. **Maintainability**: Memory configuration should be centralized and easy to modify
5. **Observability**: Log all memory operations for debugging

## Out of Scope

1. Memory cleanup and retention policies (future enhancement)
2. Memory analytics and visualization (future enhancement)
3. Cross-region memory replication (future enhancement)
4. Memory access control and permissions (future enhancement)
5. Memory versioning and rollback (future enhancement)

## Dependencies

- Amazon Bedrock AgentCore Memory service
- `bedrock-agentcore[strands-agents]` Python package (version >= 0.1.0)
- `strands-agents` Python package (version >= 1.0.0)
- AWS credentials with AgentCore Memory permissions
- Existing TANGO pipeline infrastructure (DynamoDB, S3)

## Success Metrics

1. All agents successfully share context via memory in 95% of pipeline runs
2. Memory retrieval returns relevant information in < 1 second
3. Agent learning improves success rate by 10% over 100 pipeline runs
4. Zero pipeline failures due to memory integration
5. Memory operations are logged and traceable for all executions
