<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **chopper** (5161 nodes, 9006 edges, 86 flows as of 2026-05-01). GitNexus MCP is configured for stdio through `.vscode/mcp.json` and `npx gitnexus setup`, but graph tools/resources are available only when the current client exposes them.

> Official setup: MCP starts with `npx -y gitnexus@latest mcp`. If `gitnexus://repo/chopper/context` or `npx gitnexus status` reports a stale index, run `npx gitnexus analyze --skip-agents-md` from the repo root so custom AGENTS/CLAUDE guidance is preserved.

## Always Do

- **MUST run impact analysis before editing any symbol.** If GitNexus MCP tools/resources are exposed, use GitNexus `impact`/`context` plus `gitnexus://repo/chopper/processes`; otherwise read the relevant `.github/agent_memory/*.md` file, then use `search/usages` and `search/textSearch` to report the blast radius.
- **MUST review changes before committing.** If GitNexus MCP is exposed, use `detect_changes`; otherwise use `search/changes`, targeted reference searches, memory notes, and tests to verify changes only affect expected symbols and flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, prefer GitNexus `query`/`context` when MCP is available. If it is not available, start from memory files and use `search/codebase`, `search/textSearch`, and `read/readFile`.

## Never Do

- NEVER edit a function, class, or method without first mapping usages and text references.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with blind find-and-replace; map references first and use language-aware rename tooling when available.
- NEVER treat a successful `npx gitnexus status` as proof that MCP tools are exposed in the current editor session.
- NEVER commit changes without reviewing the changed-file scope.

## Optional Resources

| Resource | Use for |
| -------- | ------- |
| `gitnexus://repos` | Discover indexed repos when MCP resources are exposed |
| `gitnexus://repo/chopper/context` | Codebase overview, check index freshness when MCP is available |
| `gitnexus://repo/chopper/clusters` | All functional areas |
| `gitnexus://repo/chopper/processes` | All execution flows |
| `gitnexus://repo/chopper/process/{name}` | Step-by-step execution trace |

## CLI / Local Fallbacks

| Task | GitNexus available | Fallback when MCP is unavailable |
| ---- | ------------------ | -------------------------------- |
| Understand architecture / "How does X work?" | `query` + `context` + process resources | memory file + `search/codebase` + `read/readFile` |
| Blast radius / "What breaks if I change X?" | `impact` + `context` | memory file + `search/usages` + `search/textSearch` |
| Trace bugs / "Why is X failing?" | `query` + `context` + process trace | memory file + `search/textSearch` + `read/readFile` |
| Rename / extract / split / refactor | `rename` dry run where exposed, then `detect_changes` | memory file + usage-mapped patches + `search/changes` |
| Index, status, clean, wiki CLI commands | `npx gitnexus ...` | local memory and repo docs |

<!-- gitnexus:end -->
