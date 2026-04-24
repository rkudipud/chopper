# Chopper Domain Companion Memory

## Current Focus

- No active customer-domain task recorded.

## Last Completed Work

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
  - **Prompt library** at `.github/prompts/` — `bootstrap-domain`, `explain-last-run`, `why-was-dropped`, `validate-my-jsons`, `bisect-feature-breakage`, `report-chopper-bug`.
  - **USER_MANUAL.md** now cross-refs the companion at the top of the Operating Tasks section.

## Next Actions

- Read this file at the start of each invocation and replace placeholders with the active domain-analysis state.
- When a user enables `options.generate_stack: true`, guide them through the standard trim workflow — this is a fully tested feature.

## Open Questions

- None.

## Supported Features

- **`options.generate_stack` (F3 stack-file auto-generation).** When set to `true` in the base JSON, Chopper emits one `<stage>.stack` file per resolved stage alongside `<stage>.tcl` using the N/J/L/D/I/O/R format defined in the bible §3.6. Dependency-line derivation: `dependencies` > `load_from` > bare `D`. Fully tested in the integration suite (`tests/fixtures/stages_domain/`). No experimental caveats.

## Validation Notes

- Created from the repository local-memory convention in `.github/agent_memory/README.md`.
- 0.3.2 consolidation: card and memory now aligned on analyzer-absorbed scope, Operating Modes, and tier-2 menu.
- 0.3.3: `generate_stack` promoted from "known untested" to "supported feature"; pilot-user framing removed.

