---
name: gitnexus-guide
description: "Use when the user asks about GitNexus itself — available tools, how to query the knowledge graph, MCP resources, graph schema, or workflow reference. Examples: \"What GitNexus tools are available?\", \"How do I use GitNexus?\""
---

# GitNexus Guide

Quick reference for all GitNexus MCP tools, resources, prompts, and the knowledge graph schema.

## Always Start Here

For any task involving code understanding, debugging, impact analysis, or refactoring:

1. **Read `gitnexus://repo/{name}/context`** — codebase overview + check index freshness
2. **Match your task to a skill below** and **read that skill file**
3. **Follow the skill's workflow and checklist**

> If step 1 warns the index is stale, run `npx gitnexus analyze` in the terminal first.

## Skills

| Task                                         | Skill to read                |
| -------------------------------------------- | ---------------------------- |
| Understand architecture / "How does X work?" | `gitnexus-exploring`         |
| Blast radius / "What breaks if I change X?"  | `gitnexus-impact-analysis`   |
| Trace bugs / "Why is X failing?"             | `gitnexus-debugging`         |
| Rename / extract / split / refactor          | `gitnexus-refactoring`       |
| Tools, resources, schema reference           | `gitnexus-guide` (this file) |
| Index, status, clean, wiki CLI commands      | `gitnexus-cli`               |
| Module-specific context (Chopper modules)    | `.github/skills/generated/<module>/SKILL.md` (run `npx gitnexus analyze --skills` to generate) |

## Tools Reference

**16 tools** exposed via MCP (per-repo and group):

| Tool | What it gives you | `repo` param |
| ---- | ----------------- | ------------ |
| `list_repos` | Discover all indexed repositories | — |
| `query` | Process-grouped hybrid search (BM25 + semantic + RRF) | Optional |
| `context` | 360-degree symbol view — categorized refs, process participation | Optional |
| `impact` | Symbol blast radius — what breaks at depth 1/2/3 with confidence | Optional |
| `detect_changes` | Git-diff impact — maps changed lines to affected processes | Optional |
| `rename` | Multi-file coordinated rename with graph + text search | Optional |
| `cypher` | Raw Cypher graph queries (read schema resource first) | Optional |
| `api_impact` | Blast radius for an HTTP route — what handlers and consumers break | Optional |
| `route_map` | Route → handler → consumer dependency map | Optional |
| `tool_map` | MCP/RPC tool definitions across the codebase | Optional |
| `shape_check` | Response shape vs consumer field access (drift detection) | Optional |
| `group_list` | List configured repository groups | — |
| `group_sync` | Rebuild Contract Registry across group repos | — |
| `query` (group mode) | Cross-repo search: `repo: "@groupName"` | — |
| `context` (group mode) | 360° view across all member repos: `repo: "@groupName"` | — |
| `impact` (group mode) | Cross-repo blast radius via Contract Bridge: `repo: "@groupName"` | — |

> When only one repo is indexed, the `repo` parameter is optional. With multiple repos, specify which one: `query({query: "auth", repo: "my-app"})`.

## MCP Prompts

Two guided workflow prompts:

| Prompt | What It Does |
| ------ | ------------ |
| `detect_impact` | Pre-commit change analysis — scope, affected processes, risk level |
| `generate_map` | Architecture documentation from the knowledge graph with Mermaid diagrams |

## Resources Reference

Lightweight reads (~100-500 tokens) for navigation:

| Resource | Content |
| -------- | ------- |
| `gitnexus://repos` | List all indexed repositories (read this first) |
| `gitnexus://repo/{name}/context` | Stats, staleness check, available tools |
| `gitnexus://repo/{name}/clusters` | All functional areas with cohesion scores |
| `gitnexus://repo/{name}/cluster/{clusterName}` | Area members |
| `gitnexus://repo/{name}/processes` | All execution flows |
| `gitnexus://repo/{name}/process/{processName}` | Step-by-step trace |
| `gitnexus://repo/{name}/schema` | Graph schema for Cypher |
| `gitnexus://group/{name}/contracts` | Group Contract Registry — provider/consumer rows + cross-links |
| `gitnexus://group/{name}/status` | Per-member index + Contract Registry staleness report |

## Graph Schema

**Nodes:** File, Function, Class, Interface, Method, Community, Process
**Edges (via CodeRelation.type):** CALLS, IMPORTS, EXTENDS, IMPLEMENTS, DEFINES, MEMBER_OF, STEP_IN_PROCESS

```cypher
MATCH (caller)-[:CodeRelation {type: 'CALLS'}]->(f:Function {name: "myFunc"})
RETURN caller.name, caller.filePath
```

## Self-Check Before Finishing

After completing any code task, verify all four:

```
1. gitnexus_impact was run for ALL modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. gitnexus_detect_changes() confirms only expected symbols/flows changed
4. All d=1 dependents (WILL BREAK) were updated
```
