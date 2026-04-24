# Chopper Domain Companion Memory

## Current Focus

- No active customer-domain task recorded.

## Last Completed Work

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
- When a user enables `options.generate_stack: true`, follow the pilot-user callout below.

## Open Questions

- None.

## Known Untested Features (feedback solicited)

- **`options.generate_stack` (F3 stack-file auto-generation).** Newly implemented in release 0.3.0. When set to `true` in the base JSON, Chopper emits one `<stage>.stack` file per resolved stage alongside `<stage>.tcl` using the N/J/L/D/I/O/R format defined in the bible §3.6. This feature has **not** yet been exercised against real customer domains. When guiding users who enable `generate_stack`, actively solicit:
  - **Feedback** on whether the emitted stack-file layout matches what their scheduler expects.
  - **Bug reports** for any unexpected output, missing fields, or format deviations.
  - **Expected-behaviour descriptions** from domain owners — concrete examples of what the `.stack` file *should* contain for their flow. These descriptions are high-value and should be captured verbatim when received.

  Until this feature has real-world coverage, treat any domain using `generate_stack: true` as a pilot user and call out the experimental status in your guidance.

## Validation Notes

- Created from the repository local-memory convention in `.github/agent_memory/README.md`.
- 0.3.2 consolidation: card and memory now aligned on analyzer-absorbed scope, Operating Modes, and tier-2 menu.
