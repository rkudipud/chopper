---
name: gitnexus-refactoring
description: "Use when the user wants to rename, extract, split, move, or restructure code safely. Examples: \"Rename this function\", \"Extract this into a module\", \"Refactor this class\", \"Move this to a separate file\""
---

# Refactoring with GitNexus

> Availability protocol: use this workflow when GitNexus MCP tools or `gitnexus://...` resources are exposed in the current session. If MCP is unavailable, read the relevant `.github/agent_memory/*.md` file first, map references with local usages/text search, apply targeted patches, and verify scope with local changes plus tests.

## When to Use

- "Rename this function safely"
- "Extract this into a module"
- "Split this service"
- "Move this to a new file"
- Any task involving renaming, extracting, splitting, or restructuring code

## Workflow

```
1. GitNexus impact on target "X"                          → Map all dependents
2. GitNexus query for "X"                                  → Find execution flows involving X
3. GitNexus context for "X"                                → See all incoming/outgoing refs
4. Plan update order: interfaces → implementations → callers → tests
```

> If "Index is stale" -> run `npx gitnexus analyze --skip-agents-md` in terminal.

## Checklists

### Rename Symbol

```
- [ ] GitNexus rename dry run (`rename` or namespaced equivalent) — preview all edits
- [ ] Review graph edits (high confidence) and ast_search edits (review carefully)
- [ ] If satisfied: apply the GitNexus rename or targeted patches
- [ ] GitNexus detect_changes, or local changes fallback — verify only expected files changed
- [ ] Run tests for affected processes
```

### Extract Module

```
- [ ] GitNexus context — see all incoming/outgoing refs
- [ ] GitNexus impact — find all external callers
- [ ] Define new module interface
- [ ] Extract code, update imports
- [ ] GitNexus detect_changes, or local changes fallback — verify affected scope
- [ ] Run tests for affected processes
```

### Split Function/Service

```
- [ ] GitNexus context — understand all callees
- [ ] Group callees by responsibility
- [ ] GitNexus impact — map callers to update
- [ ] Create new functions/services
- [ ] Update callers
- [ ] GitNexus detect_changes, or local changes fallback — verify affected scope
- [ ] Run tests for affected processes
```

## Tools

**GitNexus rename** — automated multi-file rename:

```
rename({symbol_name: "validateUser", new_name: "authenticateUser", dry_run: true})
→ 12 edits across 8 files
→ 10 graph edits (high confidence), 2 ast_search edits (review)
→ Changes: [{file_path, edits: [{line, old_text, new_text, confidence}]}]
```

**GitNexus impact** — map all dependents first:

```
impact({target: "validateUser", direction: "upstream"})
→ d=1: loginHandler, apiMiddleware, testUtils
→ Affected Processes: LoginFlow, TokenRefresh
```

**GitNexus detect_changes** — verify your changes after refactoring:

```
detect_changes({scope: "all"})
→ Changed: 8 files, 12 symbols
→ Affected processes: LoginFlow, TokenRefresh
→ Risk: MEDIUM
```

**GitNexus cypher** — custom reference queries:

```cypher
MATCH (caller)-[:CodeRelation {type: 'CALLS'}]->(f:Function {name: "validateUser"})
RETURN caller.name, caller.filePath ORDER BY caller.filePath
```

## Risk Rules

| Risk Factor         | Mitigation                                |
| ------------------- | ----------------------------------------- |
| Many callers (>5)   | Use GitNexus rename for automated updates |
| Cross-area refs     | Use detect_changes after to verify scope  |
| String/dynamic refs | Use GitNexus query to find them           |
| External/public API | Version and deprecate properly            |

## Example: Rename `validateUser` to `authenticateUser`

```
1. rename({symbol_name: "validateUser", new_name: "authenticateUser", dry_run: true})
   → 12 edits: 10 graph (safe), 2 ast_search (review)
   → Files: validator.ts, login.ts, middleware.ts, config.json...

2. Review ast_search edits (config.json: dynamic reference!)

3. rename({symbol_name: "validateUser", new_name: "authenticateUser", dry_run: false})
   → Applied 12 edits across 8 files

4. detect_changes({scope: "all"})
   → Affected: LoginFlow, TokenRefresh
   → Risk: MEDIUM — run tests for these flows
```
