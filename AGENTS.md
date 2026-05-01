<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project was indexed by GitNexus as **chopper** (4877 symbols, 8740 relationships, 90 execution flows), but GitNexus MCP tools are not assumed to be available in every VS Code session. Use local search/read/usages tools as the default; use GitNexus CLI or MCP only when the current session explicitly exposes it.

> If GitNexus CLI is available and reports a stale index, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, use `search/usages` and `search/textSearch` to report the blast radius. If GitNexus MCP is available, `gitnexus_impact` may supplement this.
- **MUST review changes before committing.** Use `search/changes`, targeted reference searches, and tests to verify changes only affect expected symbols and flows. If GitNexus MCP is available, `gitnexus_detect_changes` may supplement this.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `search/codebase`, `search/textSearch`, and `read/readFile`; use GitNexus queries only if MCP is available.

## Never Do

- NEVER edit a function, class, or method without first mapping usages and text references.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with blind find-and-replace; map references first and use language-aware rename tooling when available.
- NEVER commit changes without reviewing the changed-file scope.

## Optional Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/chopper/context` | Codebase overview, check index freshness when MCP is available |
| `gitnexus://repo/chopper/clusters` | All functional areas |
| `gitnexus://repo/chopper/processes` | All execution flows |
| `gitnexus://repo/chopper/process/{name}` | Step-by-step execution trace |

## CLI / Local Fallbacks

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `search/codebase` + `read/readFile` |
| Blast radius / "What breaks if I change X?" | `search/usages` + `search/textSearch` |
| Trace bugs / "Why is X failing?" | `search/textSearch` + `read/readFile` |
| Rename / extract / split / refactor | language-aware rename when available, otherwise usage-mapped patches |
| Index, status, clean, wiki CLI commands | `npx gitnexus ...` only when CLI is available |

<!-- gitnexus:end -->
