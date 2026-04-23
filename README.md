# Chopper v2

Chopper is a Python CLI for trimming VLSI EDA tool-flow domains down to the files, Tcl procedures, and generated run scripts a project actually needs. Selection is driven by JSON, execution is deterministic, and every run writes an audit bundle under `.chopper/` for review.

Inspired by the works of SNORT by Mike McCurdy and FlowBuilder by Stelian Alupoaei.

## What It Does

Chopper supports three capability classes that can be used independently or together:

| Capability | Purpose |
| --- | --- |
| `F1` | Keep or drop whole files |
| `F2` | Keep or drop individual Tcl procedures inside a file |
| `F3` | Generate `<stage>.tcl` run files from JSON stage definitions |

The CLI surface is intentionally small:

- `chopper validate` runs the read-only analysis path.
- `chopper trim` runs the full pipeline.
- `chopper cleanup --confirm` removes the backup directory after the trim window closes.

Global flags such as `--plain`, `--strict`, `-v`, and `-q` always go before the subcommand.

## Quick Start

Chopper requires Python 3.11+ at runtime. The provided setup scripts create a local `.venv`, activate it, and install the development dependencies.

| Platform | Command |
| --- | --- |
| Windows PowerShell | `. .\setup.ps1` |
| Windows cmd.exe | `setup.bat` |
| Unix tcsh/csh | `source setup.csh` |
| Unix bash/zsh/sh | `source setup.sh` |

After setup, confirm the CLI is available:

```text
chopper --help
```

Typical first run:

```text
chopper validate --project configs/project_abc.json
chopper trim --dry-run --project configs/project_abc.json
chopper trim --project configs/project_abc.json
```

Use `--dry-run` before a live trim when you want the compiled manifest, trace graph, and trim report without rebuilding domain content.

## Repo Guide

Start with the docs that match your role:

| Path | Audience | Purpose |
| --- | --- | --- |
| [doc/README.md](doc/README.md) | Operators, JSON authors, integrators | Entry point to the user-facing docs |
| [doc/IMPLEMENTATION_GUIDE.md](doc/IMPLEMENTATION_GUIDE.md) | Engineers reading the code | Full implementation walkthrough with architecture, service flow, tests, and Mermaid diagrams |
| [.github/agents/chopper-domain-companion.agent.md](.github/agents/chopper-domain-companion.agent.md) | Copilot users analyzing customer domains | Chopper-aware custom agent for codebase scanning, JSON authoring, Chopper runs, log analysis, and trim guidance |
| [json_kit/README.md](json_kit/README.md) | JSON authors | Standalone authoring kit with schemas, examples, and validator |
| [technical_docs/chopper_description.md](technical_docs/chopper_description.md) | Engineers | Authoritative behavior and pipeline specification |
| [technical_docs/CLI_HELP_TEXT_REFERENCE.md](technical_docs/CLI_HELP_TEXT_REFERENCE.md) | Engineers, doc writers | Canonical CLI wording and option reference |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contributors | Development workflow, design constraints, and PR checklist |

## Use the Chopper Domain Companion Agent

The repo ships with a custom agent at [.github/agents/chopper-domain-companion.agent.md](.github/agents/chopper-domain-companion.agent.md).

It comes with embedded Chopper knowledge and a guided workflow for:

- understanding whether Chopper fits the user’s trimming goal
- scanning a target codebase and confirming the real domain boundary
- identifying entry points, proc libraries, utilities, configs, and optional flows
- building a call-tree understanding without confusing external tool commands with domain proc calls
- authoring and refining `base.json`, feature JSONs, and `project.json`
- running `chopper validate` and `chopper trim --dry-run`
- analyzing `.chopper/` artifacts like `compiled_manifest.json`, `dependency_graph.json`, `diagnostics.json`, and `trim_report.json`
- helping users understand why the output differs from intent
- suggesting JSON changes and codebase changes that make trimming more reliable

The agent is collaborative by design: it asks for the user’s goal, confirms the domain boundary, identifies mandatory versus optional flows, and only then recommends boundaries or JSON edits. It explicitly knows the critical Chopper rules like default-exclude, explicit-include-wins, and trace-is-reporting-only.

### Use it in VS Code GitHub Copilot

Open this repository in VS Code, then open GitHub Copilot Chat.

If your VS Code Copilot setup shows repository custom agents in the agent picker, select `Chopper Domain Companion` and ask for help directly.

Suggested prompts:

- "Analyze my customer codebase under `path/to/domain/` and tell me whether Chopper is a good fit."
- "Scan this repo, identify the real domain boundary and entry points, and help me author `base.json`, feature JSONs, and `project.json`."
- "Run `chopper validate` and `chopper trim --dry-run`, then explain the `.chopper/` outputs and tell me what JSON changes I should make."
- "Read `compiled_manifest.json`, `dependency_graph.json`, and `trim_report.json`, explain why the output differs from my intent, and propose the next JSON edits."

If your Copilot setup does not surface repo custom agents automatically, open [.github/agents/chopper-domain-companion.agent.md](.github/agents/chopper-domain-companion.agent.md) and use it as the instruction source for the same workflow.

## Repository Layout

| Path | Contents |
| --- | --- |
| `src/chopper/` | Application code: CLI, orchestrator, parser, compiler, trimmer, validator, generators, audit |
| `tests/` | Unit, integration, golden, and property test suites |
| `json_kit/` | Self-contained JSON authoring kit used by Chopper for runtime schemas |
| `doc/` | User manual, behavior guide, technical guide, and implementation guide |
| `technical_docs/` | Full engineering specification, architecture, diagnostics, and risks |
| `scripts/` | Repo validation helpers used in local checks and CI |

## Development Checks

The main local quality gates are:

```text
make check
make ci
make test
```

If `make` is not available on your platform, the underlying tooling is defined in [pyproject.toml](pyproject.toml) and the VS Code workspace exposes matching tasks.

## Notes for Contributors

- Keep changes aligned with the documented `validate`, `trim`, and `cleanup` command surface.
- Chopper reads its authoritative runtime schemas from `json_kit/schemas/`.
- Behavior changes should update the corresponding user docs and engineering docs in the same pull request.
- For a code-level onboarding path, start with [doc/IMPLEMENTATION_GUIDE.md](doc/IMPLEMENTATION_GUIDE.md).

For contribution details, see [CONTRIBUTING.md](CONTRIBUTING.md).
