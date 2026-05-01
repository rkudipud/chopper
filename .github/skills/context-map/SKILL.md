---
name: context-map
description: 'Generate a map of all files relevant to a task before making changes'
---

# Context Map

Before implementing any changes, analyze the codebase and create a context map.

Use GitNexus `query`/`context`/`impact` first when MCP tools or `gitnexus://...` resources are exposed. If GitNexus MCP is unavailable, read the relevant `.github/agent_memory/*.md` file and build the map with local `search/*`, `read/*`, and `search/usages` tools.

## Task

{{task_description}}

## Instructions

1. Search the codebase for files related to this task
2. Identify direct dependencies (imports/exports)
3. Find related tests
4. Look for similar patterns in existing code

## Output Format

```markdown
## Context Map

### Files to Modify
| File | Purpose | Changes Needed |
|------|---------|----------------|
| path/to/file | description | what changes |

### Dependencies (may need updates)
| File | Relationship |
|------|--------------|
| path/to/dep | imports X from modified file |

### Test Files
| Test | Coverage |
|------|----------|
| path/to/test | tests affected functionality |

### Reference Patterns
| File | Pattern |
|------|---------|
| path/to/similar | example to follow |

### Risk Assessment
- [ ] Breaking changes to public API
- [ ] Database migrations needed
- [ ] Configuration changes required
```

Do not proceed with implementation until this map is reviewed.
