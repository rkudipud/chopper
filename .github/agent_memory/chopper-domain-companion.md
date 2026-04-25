# Chopper Domain Companion Memory

## Current Focus

- No active customer-domain task recorded.

## Last Completed Work

- **0.3.6 automatic GitHub issue filing for bug reports (2026-04-25).** Added `scripts/file_bug_report.py`, which takes a JSON payload, packages local evidence via `scripts/package_bug_report.py`, renders a GitHub issue body matching `.github/ISSUE_TEMPLATE/bug_report.yml`, and creates the issue automatically through `gh issue create` when host GitHub auth exists. The create step is now best-effort by default: if `gh` is missing or issue creation fails, the same run falls back to the simple local output path and returns the generated issue-body file plus bundle paths without requiring a rerun. Binary attachment upload remains manual by design per architecture doc §5.11.7 / FD-13.

- **0.3.5 VS Code Unix bug-attachment helper (2026-04-24).** Added `scripts/package_bug_report.py` to package one or more Unix paths (`.chopper/`, logs, markdown reports, screenshots) into a single upload-ready zip. Added `.github/prompts/package-bug-artifacts.prompt.md` and updated the companion/reporting docs so VS Code users can package evidence locally, open the bug form, and upload the generated zip without hand-zipping paths outside the workspace.

- **0.3.4 bug-report intake hardening (2026-04-24).** Tightened `.github/ISSUE_TEMPLATE/bug_report.yml` so terminal output, audit evidence, and JSON reproduction cannot be left blank without an explicit explanation. Fixed `.github/ISSUE_TEMPLATE/config.yml` placeholder links. Updated `.github/prompts/report-chopper-bug.prompt.md` and the companion card so bug-report help now returns field-by-field issue-form answers and forbids empty sections or external markdown-path placeholders.

- **0.4.0 MCP stdio surface (2026-04-24).** `chopper mcp-serve` ships — a stdio-only Model Context Protocol server that exposes three read-only tools (`chopper.validate`, `chopper.explain_diagnostic`, `chopper.read_audit`). Destructive tools (`trim`, `cleanup`) remain CLI-only and are guarded by an in-process assertion plus an integration test. New diagnostic `PE-04 mcp-protocol-error` (exit 4). `mcp>=1.0,<2` is now a hard runtime dependency. Scope-lock §1.1 in `project.instructions.md` documents the narrowed exception. Architecture Doc §3.9 is the authoritative contract.

- **0.3.3 generate_stack end-to-end tests (2026-04-24).** `options.generate_stack` is now fully tested and production-ready (D1 + D2):
  - New `tests/fixtures/stages_domain/` fixture (three-stage domain with `generate_stack: true`).
  - Four integration tests in `tests/integration/test_runner_localfs_e2e.py` covering dry-run manifest shape, live-trim file emission, stack-file content, and audit-bundle recording.
  - Eight unit tests in `tests/unit/orchestrator/test_runner.py` covering the same paths via `InMemoryFS`.
  - `(new, untested)` label and pilot-user guidance removed from `JSON_AUTHORING_GUIDE.md`, `README.md`, and this memory file.

- **0.3.2 consolidation (2026-04-24).** Absorbed the former `domain-analyzer.agent.md` into this companion card. Now the single user-facing agent for anything Chopper-related. Added:
  - **Operating Modes** — `analyze-only` (JSON authoring only, no CLI calls) vs `full-loop` (validate + dry-run + audit walk + live trim on explicit direction).
  - **Q1–Q5 Discovery Protocol** — explicit discovery sequence for unfamiliar codebases (root, stack files, scripts, configs, utility dirs).
  - **JSON Templates & Checklists** — base / feature / project skeletons with per-type validation checklists.
  - **Schema Error → Fix Mapping** — one-glance remediation table for `validate_jsons.py` output.
  - **Bootstrapping a New Domain** playbook — 7-step flow from Q1–Q5 through first dry-run.
  - **Common CLI Workflows** — Bisect, Compare-two-runs, Prove-JSON-safe, Explain-a-diagnostic.
  - **Tier-2 greeting menu** — Tier 1 "where are you starting from?" table, Tier 2 full capability list.
  - **Prompt library** at `.github/prompts/` — `bootstrap-domain`, `explain-last-run`, `why-was-dropped`, `validate-my-jsons`, `bisect-feature-breakage`, `report-chopper-bug`, `package-bug-artifacts`.
  - **USER_MANUAL.md** now cross-refs the companion at the top of the Operating Tasks section.

## Next Actions

- Read this file at the start of each invocation and replace placeholders with the active domain-analysis state.
- When a user enables `options.generate_stack: true`, guide them through the standard trim workflow — this is a fully tested feature.

## Open Questions

- None.

## Supported Features

- **`options.generate_stack` (F3 stack-file auto-generation).** When set to `true` in the base JSON, Chopper emits one `<stage>.stack` file per resolved stage alongside `<stage>.tcl` using the N/J/L/D/I/O/R format defined in the architecture doc §3.6. Dependency-line derivation: `dependencies` > `load_from` > bare `D`. Fully tested in the integration suite (`tests/fixtures/stages_domain/`). No experimental caveats.

## Validation Notes

- Created from the repository local-memory convention in `.github/agent_memory/README.md`.
- 0.3.2 consolidation: card and memory now aligned on analyzer-absorbed scope, Operating Modes, and tier-2 menu.
- 0.3.3: `generate_stack` promoted from "known untested" to "supported feature"; pilot-user framing removed.

