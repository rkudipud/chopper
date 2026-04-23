# Agent Local Memory Files

Agents in this repository use workspace-local memory files so their working context stays repository-native and tool-agnostic.

## Directory

Store agent memory files in `.github/agent_memory/`.

Recommended filenames:

- `chopper-buildout.md`
- `chopper-stage-builder.md`
- `principal-software-engineer.md`
- `chopper-domain-companion.md`

## Lifecycle

1. On first invocation, if the agent's memory file does not exist, create it.
2. On later invocations, read the file before planning or implementation.
3. Update the file after milestones, validations, or decisions that the next invocation should inherit.

## Minimum Template

```markdown
# <Agent Name> Memory

## Current Focus
- 

## Last Completed Work
- 

## Next Actions
- 

## Open Questions
- 

## Validation Notes
- 
```

## Rules

- Keep entries short and factual.
- Record decisions, active work, and the next concrete action.
- Do not depend on external or proprietary memory systems.
