---
name: gitnexus-cli
description: "Use when the user needs to run GitNexus CLI commands like analyze/index a repo, check status, clean the index, generate a wiki, or list indexed repos. Examples: \"Index this repo\", \"Reanalyze the codebase\", \"Generate a wiki\""
---

# GitNexus CLI Commands

> Availability protocol: this skill covers the `npx gitnexus ...` CLI. CLI availability does not imply GitNexus MCP tools are exposed in the current VS Code session. If MCP is unavailable, read the relevant `.github/agent_memory/*.md` file and use local search/read/usages tools for code intelligence.

Official docs checked 2026-05-01: MCP starts over stdio with `npx -y gitnexus@latest mcp`; `npx gitnexus setup` configures supported editors; Chopper's workspace MCP config is `.vscode/mcp.json`.

All commands work via `npx` — no global install required.

## Commands

### analyze — Build or refresh the index

```bash
npx gitnexus analyze
```

Run from the project root. This parses all source files, builds the knowledge graph, writes it to `.gitnexus/`, and regenerates `AGENTS.md` / `CLAUDE.md` context files unless `--skip-agents-md` is used.

| Flag | Effect |
| ---- | ------ |
| `--force` | Force full re-index even if up to date |
| `--embeddings` | Generate vectors for new/changed nodes (off by default) |
| `--drop-embeddings` | Wipe existing embeddings and rebuild. Use only when changing embedding models. |
| `--skip-embeddings` | Skip embedding generation entirely (faster) |
| `--skills` | **Generate per-module skill files** from Leiden community detection into `.github/skills/generated/`. Each skill covers a functional area's key files, entry points, and execution flows. Re-run to keep current. |
| `--skip-agents-md` | Preserve your custom edits inside the `<!-- gitnexus:start -->` block of `AGENTS.md`/`CLAUDE.md` — GitNexus will not overwrite them. |
| `--skip-git` | Index directories that are not git repositories |
| `--verbose` | Log skipped files when language parsers are unavailable |

> **For this repo, prefer `npx gitnexus analyze --skip-agents-md`** so GitNexus refreshes the index without overwriting curated Chopper agent guidance. Embeddings are preserved by default. Pass `--drop-embeddings` only when you intentionally want to wipe them.

**When to run:** First time in a project, after major code changes, or when `gitnexus://repo/{name}/context` reports the index is stale.

#### Generate per-module skills for Chopper

Run this once (and after major module changes) to get targeted skill files for each Chopper module:

```bash
npx gitnexus analyze --skills
```

This creates `.github/skills/generated/<module>/SKILL.md` for each detected functional community (parser, compiler, trimmer, validator, etc.) — giving agents pinpoint context for whatever module they're working in.

### setup — Configure MCP for your editors (one-time)

```bash
npx gitnexus setup
```

Auto-detects installed editors (Claude Code, Cursor, Codex, Windsurf, OpenCode) and writes the correct global MCP config. Only needs to run once. Manual/workspace MCP config should use `npx -y gitnexus@latest mcp`.

### status — Check index freshness

```bash
npx gitnexus status
```

Shows whether the current repo has a GitNexus index, when it was last updated, and symbol/relationship counts. Use this to check if re-indexing is needed.

### clean — Delete the index

```bash
npx gitnexus clean
```

Deletes the `.gitnexus/` directory and unregisters the repo from the global registry.

| Flag | Effect |
| ---- | ------ |
| `--force` | Skip confirmation prompt |
| `--all` | Clean all indexed repos, not just the current one |

### wiki — Generate documentation from the graph

```bash
npx gitnexus wiki
```

Generates LLM-powered documentation from the knowledge graph. Requires an API key (saved to `~/.gitnexus/config.json` on first use).

| Flag | Effect |
| ---- | ------ |
| `--force` | Force full regeneration |
| `--model <model>` | LLM model (default: gpt-4o-mini) |
| `--base-url <url>` | LLM API base URL |
| `--api-key <key>` | LLM API key |
| `--concurrency <n>` | Parallel LLM calls (default: 3) |
| `--gist` | Publish wiki as a public GitHub Gist |

### list — Show all indexed repos

```bash
npx gitnexus list
```

Lists all repositories registered in `~/.gitnexus/registry.json`.

### serve — Start HTTP server for web UI

```bash
npx gitnexus serve
```

Starts a local HTTP API on port 4747. The web UI at `gitnexus.vercel.app` auto-detects it and shows all your indexed repos without re-uploading.

## After Indexing

1. **Read `gitnexus://repo/{name}/context`** to verify the index loaded
2. If you ran `--skills`, load the relevant generated skill from `.github/skills/generated/`
3. Use the other GitNexus skills (`exploring`, `debugging`, `impact-analysis`, `refactoring`) for your task

## Troubleshooting

- **"Not inside a git repository"**: Run from a directory inside a git repo, or use `--skip-git`
- **Index is stale after re-analyzing**: Restart the MCP server to reload the index
- **`stats.embeddings` is 0 after analyze**: Re-run `npx gitnexus analyze --embeddings`. If the log shows `Warning: could not load cached embeddings`, the cache was corrupt — rebuild is clean.
- **MCP lists no repos**: Run `npx gitnexus analyze --skip-agents-md` in the target repo; verify with `npx gitnexus list`
- **LadybugDB lock / "database busy"**: Stop overlapping processes — only one writer at a time
