# Chopper -- User Documentation

Welcome. This folder is the **single end-user entry point** for Chopper. It is written to take you from the onboarding presentation to a working trim with as little reading fatigue as possible.

> **What is Chopper?** A Python CLI that derives a project-specific subset of a VLSI EDA tool-flow domain from JSON. You declare what to keep; Chopper produces a minimal, reproducible, audited domain.
>
> **Why is it easy?** Three reasons: (1) the workflow is iterative -- `validate` and `--dry-run` are free and safe, so you never commit to a trim blind; (2) the original domain is always preserved as a backup until you explicitly delete it; (3) every decision is recorded in `.chopper/` so you can always explain why something was kept or dropped.
>
> **Why the name?** Slightly misleading. Conceptually Chopper is closest to **Flow Builder**: both let domain owners derive specialised flows from a fully feature-rich domain. The distinction is scope -- Flow Builder targets *file-based* flows; Chopper supports both *file-based* **and** *proc-based* flows, which makes it suitable for procedure-heavy domains.

---

## Reading order (60-90 minutes total)

| # | Document | Read when | Time |
|---|---|---|---|
| 1 | [01_OVERVIEW.md](01_OVERVIEW.md) | Right after the onboarding deck -- explains the problem, the solution, F1/F2/F3, the full stage-field and flow-action reference, JSON structure, the overlay rules, options, and BKMs | ~25 min |
| 2 | [02_CLI_GUIDE.md](02_CLI_GUIDE.md) | When you are about to run Chopper for the first time -- every subcommand, every flag, deep examples | ~20 min |
| 3 | [03_HOW_CHOPPER_WORKS.md](03_HOW_CHOPPER_WORKS.md) | When you want to understand the pipeline, decide where it fits, or troubleshoot a result | ~25 min |

If you only have 10 minutes, read the **TL;DR** at the top of [01_OVERVIEW.md](01_OVERVIEW.md) and the **Quick Start** section of [02_CLI_GUIDE.md](02_CLI_GUIDE.md).

---

## Companion agent

Open VS Code Copilot Chat and pick the **Chopper Agent** ([.github/agents/chopper-agent.agent.md](../.github/agents/chopper-agent.agent.md)). It can:

- Bootstrap starter JSON for an unfamiliar domain
- Explain any diagnostic code or last run
- Bisect a feature that broke trim
- File a bug report with bundled evidence

Ready-made prompts live under [.github/prompts/](../.github/prompts/).

---

## Related material

| Resource | Use for |
|---|---|
| [../examples/](../examples/) | 14 progressive worked JSON examples (file-only -> full pipeline with stacks -> cross-feature `skip_if_no_stage`) |
| [../schemas/](../schemas/) | Authoritative JSON schemas |
| [../technical_docs/JSON_AUTHORING_GUIDE.md](../technical_docs/JSON_AUTHORING_GUIDE.md) | Complete JSON field reference |
| [../technical_docs/DIAGNOSTIC_CODES.md](../technical_docs/DIAGNOSTIC_CODES.md) | Every diagnostic code |
| [../technical_docs/ARCHITECTURE.md](../technical_docs/ARCHITECTURE.md) | Authoritative specification (for contributors) |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Contributor workflow |

---

## Ownership and support

- **Tool maintainer:** see [../README.md](../README.md) repository owners.
- **Bug reports:** [open a GitHub issue](https://github.com/rkudipud/chopper/issues/new?template=bug_report.yml) or run the `report-chopper-bug` Copilot prompt.
- **Inspirations:** SNORT (Mike McCurdy) -- domain-state and trim lifecycle; FlowBuilder (Stelian Alupoaei) -- stage-driven flow modelling.
