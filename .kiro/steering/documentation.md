# Documentation Standards

## Purpose

The `./docs` folder contains design decisions, architectural analysis, and implementation documentation that captures the reasoning behind code changes and system improvements.

## When to Document

Create documentation in `./docs` when:

- Making significant architectural changes
- Analyzing system behavior or performance issues
- Identifying problems and proposing solutions
- Implementing major refactors or optimizations
- Documenting design decisions that affect multiple components
- Creating analysis reports for future reference

## Documentation Types

### Analysis Documents
Investigate and document system behavior, issues, or patterns.

**Naming:** `*_ANALYSIS.md`

**Structure:**
- Executive Summary: High-level overview of findings
- Current State: What exists now
- Issues Found: Specific problems identified
- Root Causes: Why problems exist
- Recommendations: Proposed solutions (not yet implemented)
- Next Steps: Action items

**Example:** `AGENT_HANDOFF_ANALYSIS.md`

### Implementation Summaries
Document changes made, solutions implemented, and their impact.

**Naming:** `*_SUMMARY.md` or `*_IMPLEMENTATION.md`

**Structure:**
- Problem: What was broken or needed improvement
- Solution Implemented: What was changed
- Changes Made: Specific code/config modifications
- Benefits: Improvements gained
- Testing: How to verify the changes
- Impact: Effects on other components

**Example:** `CONFIG_FIX_SUMMARY.md`

### Improvement Proposals
Document proposed enhancements with rationale and implementation guidance.

**Naming:** `*_IMPROVEMENTS.md` or `*_RECOMMENDATIONS.md`

**Structure:**
- Problem Analysis: Current issues
- Solutions Implemented: What was done
- Additional Recommendations: Future improvements
- Benefits: Expected gains
- Migration Notes: How to adopt changes

**Example:** `TERRAFORM_WORKDIR_IMPROVEMENTS.md`

### Visual Documentation
Diagrams and flowcharts explaining system architecture or workflows.

**Naming:** `*_VISUAL.md` or `*_FLOW.md`

**Structure:**
- Overview: What the diagram shows
- Visual representation (ASCII art, mermaid diagrams, or references to images)
- Component descriptions
- Data flow explanations

**Example:** `AGENT_HANDOFF_VISUAL.md`

## Writing Style

### Be Specific
- Use concrete examples with code snippets
- Reference actual file names and line numbers
- Show before/after comparisons
- Include actual error messages

### Be Actionable
- Provide clear next steps
- Include commands to run
- Suggest specific code changes
- Offer troubleshooting guidance

### Be Structured
- Use clear headings and sections
- Include table of contents for long documents
- Use tables for comparisons
- Use code blocks with language tags
- Use visual separators (horizontal rules)

### Be Concise
- Focus on the essential information
- Avoid redundant explanations
- Use bullet points for lists
- Keep paragraphs short

## Code Examples

Always include:
- Language identifier in code blocks
- Context about where code lives
- Comments explaining key parts

```python
# In agents/orchestrator_agent.py
ORCHESTRATOR_SYSTEM_PROMPT = """
You are the TANGO Pipeline Orchestrator...
"""
```

## Cross-References

Link to related files and documentation:
- Use relative paths: `See config.py for details`
- Reference other docs: `See AGENT_HANDOFF_ANALYSIS.md`
- Link to code: `agents/orchestrator_agent.py`

## Status Indicators

Use emoji or markers to show status:
- ✅ Implemented/Working
- ❌ Broken/Not working
- ⚠️ Warning/Caution
- 🔄 In progress
- 💡 Suggestion/Idea

## Maintenance

### Keep Documentation Current
- Update docs when implementing changes
- Mark outdated sections clearly
- Archive obsolete documents (move to `docs/archive/`)
- Review docs periodically for accuracy

### Document Decisions, Not Just Code
Focus on:
- Why decisions were made
- What alternatives were considered
- What trade-offs were accepted
- What assumptions were made

### Don't Document Everything
Avoid documenting:
- Obvious code behavior
- Temporary debugging notes
- Personal preferences
- Implementation details better suited for code comments

## File Organization

```
docs/
├── *_ANALYSIS.md          # Problem investigation
├── *_SUMMARY.md           # Implementation documentation
├── *_IMPROVEMENTS.md      # Enhancement proposals
├── *_VISUAL.md            # Diagrams and flows
├── *_RECOMMENDATIONS.md   # Future work suggestions
└── archive/               # Outdated documentation
```

## Review Before Modifying

Always read `docs/REVIEW_BEFORE_MODIFY.md` (if it exists) before making changes to understand:
- Current system state
- Known issues
- Planned improvements
- Areas requiring caution
