# AgentCore Memory Integration Spec

## Overview

This spec defines the integration of Amazon Bedrock AgentCore Memory into the TANGO Multi-Agent Pipeline to enable:

1. **Shared working memory** across all agents during a pipeline run
2. **Agent-specific learning memory** for each agent type to improve over time
3. **Semantic search and intelligent retrieval** of relevant context
4. **Graceful fallback** when memory is unavailable

## Problem Statement

Currently, the TANGO pipeline agents:
- Cannot share context during execution (must pass data explicitly)
- Cannot learn from past executions
- Cannot retrieve relevant historical information
- Have no memory of previous pipeline runs

This limits the pipeline's ability to:
- Build upon previous work within a run
- Improve success rates over time
- Handle similar resources more efficiently
- Provide context-aware decision making

## Solution

Implement a **dual-memory architecture** using Amazon Bedrock AgentCore Memory:

### 1. Shared Working Memory
- All agents in a pipeline run share the same actor ID (`tango_pipeline`)
- Each agent has a unique session ID (`{agent_name}_{pipeline_run_id}`)
- Agents write to and read from actor-level namespaces:
  - `/pipeline/facts/{actorId}` - Shared facts
  - `/pipeline/preferences/{actorId}` - Shared patterns

### 2. Agent-Specific Learning Memory
- Each agent type has its own isolated memory store
- Agents learn from past executions across pipeline runs
- Agent-specific namespaces:
  - `/agent/patterns/{actorId}` - General patterns
  - `/agent/code_patterns/{actorId}` - Code patterns (documentation agent)
  - `/agent/validation_fixes/{actorId}` - Validation fixes (terraform agent)

## Key Design Decisions

### Decision 1: Different Session IDs, Same Actor ID
**Rationale**: AgentCore Memory limitation of "one agent per session" requires unique session IDs. Using the same actor ID enables namespace sharing.

### Decision 2: Actor-Level Namespaces
**Rationale**: Session-level namespaces (with `{sessionId}`) are not shared across sessions. Actor-level namespaces enable cross-agent memory access.

### Decision 3: Sequential Workflow Pattern
**Rationale**: Strands multi-agent patterns (Graph, Swarm) don't allow individual agents to have session managers. Sequential workflow gives us full control.

### Decision 4: Optional Memory Integration
**Rationale**: Memory should be optional to ensure backward compatibility and allow operation when AgentCore Memory is unavailable.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Pipeline Run (run_123)                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Discovery Agent          Documentation Agent                │
│  session: discovery_123   session: documentation_123         │
│  actor: tango_pipeline    actor: tango_pipeline             │
│         │                          │                          │
│         └──────────┬───────────────┘                          │
│                    │                                          │
│            ┌───────▼────────┐                                │
│            │ Shared Memory  │                                │
│            │ /facts/{actor} │                                │
│            │ /prefs/{actor} │                                │
│            └────────────────┘                                │
│                                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Agent-Specific Learning Memory                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Discovery Memory    Documentation Memory    Terraform Memory│
│  (isolated)          (isolated)              (isolated)      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Foundation (Tasks 1-2)
- Install dependencies
- Create memory configuration module
- Create memory setup module
- Create agent factory module

### Phase 2: Agent Integration (Task 3)
- Update all agents to support memory
- Extract system prompts
- Add memory-aware prompts
- Test with memory enabled/disabled

### Phase 3: Pipeline Refactoring (Task 4)
- Create new pipeline with memory support
- Update main entry points
- Add feature flags
- Maintain backward compatibility

### Phase 4: Testing (Task 5)
- Unit tests for configuration and factory
- Integration tests for memory operations
- End-to-end tests for full pipeline
- Performance tests for latency

### Phase 5: Documentation (Task 6)
- Update README and USAGE
- Create memory guide
- Add code documentation
- Add troubleshooting guide

### Phase 6: Deployment (Tasks 7-8)
- Deploy with feature flag
- Setup memory stores
- Enable gradually
- Monitor and validate

## Success Criteria

1. ✅ All agents can share context via memory in 95% of pipeline runs
2. ✅ Memory retrieval returns relevant information in < 1 second
3. ✅ Agent learning improves success rate by 10% over 100 runs
4. ✅ Zero pipeline failures due to memory integration
5. ✅ Memory operations are logged and traceable

## Files in This Spec

- **requirements.md** - User stories and acceptance criteria
- **design.md** - Technical design and architecture
- **tasks.md** - Implementation task breakdown
- **README.md** - This file (overview and summary)

## Getting Started

1. Review the requirements document to understand user stories
2. Review the design document to understand the architecture
3. Follow the tasks document for implementation
4. Test thoroughly at each phase
5. Deploy with feature flag for gradual rollout

## Dependencies

- `bedrock-agentcore[strands-agents]` >= 0.1.0
- `strands-agents` >= 1.0.0
- AWS credentials with AgentCore Memory permissions
- Existing TANGO pipeline infrastructure

## References

- [Strands AgentCore Memory Documentation](https://strandsagents.com/latest/documentation/docs/community/session-managers/agentcore-memory/)
- [AWS AgentCore Memory Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/strands-sdk-memory.html)
- [Strands Session Management](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/session-management/)
- [AgentCore Memory Namespaces](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/specify-long-term-memory-organization.html)

## Questions or Issues?

- Review the design document for technical details
- Check the tasks document for implementation guidance
- Refer to AWS and Strands documentation for API details
- Test with memory disabled if issues arise
