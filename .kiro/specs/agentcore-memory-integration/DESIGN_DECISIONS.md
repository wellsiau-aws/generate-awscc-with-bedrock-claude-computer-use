# Key Design Decisions

## 1. Resource-Specific Actor ID

### Decision
The `actorId` is set dynamically to the **resource name being processed** (e.g., `awscc_s3_bucket`, `awscc_lambda_function`), not a static pipeline identifier.

### Rationale

#### Benefits
1. **Resource-Specific Memory Isolation**
   - Each resource type gets its own memory namespace
   - `awscc_s3_bucket` memories don't mix with `awscc_lambda_function` memories
   - Cleaner semantic search results

2. **Better Learning**
   - Agents learn patterns specific to each resource type
   - S3 bucket validation fixes don't interfere with Lambda function fixes
   - More relevant historical context

3. **Improved Retrieval**
   - Semantic search finds information relevant to the specific resource
   - Higher quality context for agent decision-making
   - Reduced noise from unrelated resources

4. **Natural Scoping**
   - Memory naturally scopes to what the pipeline is working on
   - Aligns with how the pipeline processes one resource at a time
   - Intuitive for debugging and observability

#### Example

```python
# Pipeline processing awscc_s3_bucket
actor_id = "awscc_s3_bucket"

# All agents share this namespace:
# /pipeline/facts/awscc_s3_bucket
# /pipeline/preferences/awscc_s3_bucket

# Discovery agent writes:
"S3 bucket requires globally unique name"

# Documentation agent reads and uses this context
# Terraform agent reads and learns from S3-specific patterns
```

```python
# Later, pipeline processing awscc_lambda_function
actor_id = "awscc_lambda_function"

# Different namespace:
# /pipeline/facts/awscc_lambda_function
# /pipeline/preferences/awscc_lambda_function

# No interference with S3 bucket memories
```

### Implementation

1. **Discovery Phase**: Run discovery agent **without memory** to get resource name
2. **Set Actor ID**: Extract resource name from discovery result
3. **Create Factory**: Initialize agent factory with resource-specific actor ID
4. **Create Agents**: All subsequent agents use the same resource-specific actor ID

```python
# Step 1: Discovery (no memory needed)
discovery_result = discovery_agent("Find next resource")
resource_info = json.loads(str(discovery_result))

# Step 2: Set actor_id dynamically
actor_id = resource_info["resource_name"]  # e.g., "awscc_s3_bucket"

# Step 3: Create factory with resource-specific actor_id
factory = AgentFactory(
    shared_memory_id=shared_memory_id,
    actor_id=actor_id,  # Resource-specific!
    pipeline_run_id=pipeline_run_id,
    region=region
)

# Step 4: All agents now share memory for this specific resource
documentation_agent = factory.create_agent("documentation", ...)
terraform_agent = factory.create_agent("terraform", ...)
```

### Trade-offs

#### Advantages ✅
- Resource-specific context and learning
- Better semantic search relevance
- Natural memory isolation
- Easier debugging (memory scoped to resource)

#### Considerations ⚠️
- Discovery agent cannot use shared memory (runs before actor_id is known)
- Need to handle discovery phase separately
- Actor ID must be extracted from discovery results

### Alternative Considered

**Static Pipeline Actor ID** (e.g., `tango_pipeline`)
- ❌ All resources share the same memory namespace
- ❌ Semantic search returns mixed results across resource types
- ❌ Agent learning less effective (patterns from different resources mixed)
- ✅ Simpler implementation (actor_id known upfront)

**Decision**: Resource-specific actor ID provides significantly better memory quality and relevance, worth the minor implementation complexity.

---

## 2. Discovery Agent Without Memory

### Decision
The discovery agent runs **without memory** (no session manager) because it executes before the actor ID is known.

### Rationale
- Discovery agent determines which resource to process
- Actor ID is set based on discovery result
- Cannot create session manager without actor ID
- Discovery is simple enough to not require memory

### Implementation
```python
# Discovery agent created without factory
discovery_agent = create_discovery_agent(factory=None)

# All other agents created with factory (after actor_id is known)
documentation_agent = create_documentation_agent(factory)
```

---

## 3. Session ID Pattern

### Decision
Session IDs follow the pattern: `{agent_name}_{pipeline_run_id}`

### Example
```
discovery_20250123_143022
documentation_20250123_143022
terraform_20250123_143022
```

### Rationale
- Unique session ID per agent (avoids "one agent per session" limitation)
- Pipeline run ID groups agents from the same execution
- Agent name makes debugging easier
- Timestamp provides chronological ordering

---

## 4. Namespace Design

### Decision
Use **actor-level namespaces** for shared memory, not session-level.

### Namespaces
```
/pipeline/facts/{actorId}        # Shared facts
/pipeline/preferences/{actorId}  # Shared patterns
/agent/patterns/{actorId}        # Agent-specific learning
```

### Rationale
- Session-level namespaces (with `{sessionId}`) are not shared across sessions
- Actor-level namespaces enable cross-agent memory access
- All agents with same actor ID can read/write to shared namespaces

### Example
```python
# All agents for awscc_s3_bucket share:
"/pipeline/facts/awscc_s3_bucket"

# Becomes:
"/pipeline/facts/awscc_s3_bucket"  # Shared across all agents

# NOT:
"/pipeline/facts/awscc_s3_bucket/discovery_123"  # Would be isolated
```

---

## Summary

The key insight is that **actor ID = resource name** provides:
1. Natural memory scoping per resource type
2. Better semantic search and learning
3. Cleaner memory isolation
4. More intuitive debugging

This design decision significantly improves memory quality and relevance at the cost of minor implementation complexity (discovery runs without memory).
