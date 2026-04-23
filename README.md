# Chopper

Chopper is a Python CLI for trimming VLSI EDA tool-flow domains down to the files, Tcl procedures, and generated run scripts a project actually needs. Selection is driven by JSON, execution is deterministic, and every run writes an audit bundle under `.chopper/` for review.

Release details live in [VERSION.md](VERSION.md).

Inspired by the works of SNORT by Mike McCurdy and FlowBuilder by Stelian Alupoaei.

## Product Summary

| Capability | Purpose |
| --- | --- |
| `F1` | Keep or drop whole files |
| `F2` | Keep or drop individual Tcl procedures inside a file |
| `F3` | Generate `<stage>.tcl` run files from JSON stage definitions |

Supported operator commands:

- `chopper validate`
- `chopper trim`
- `chopper cleanup --confirm`

Global flags such as `--plain`, `--strict`, `-v`, and `-q` always go before the subcommand.

## Standard Procedure

### Inputs

- A domain root
- A base JSON or project JSON
- Optional feature JSONs
- Optional stage definitions when generated run scripts are required

### Procedure

1. Bootstrap the environment.
2. Run `chopper validate`.
3. Run `chopper trim --dry-run`.
4. Review `.chopper/compiled_manifest.json`, `.chopper/dependency_graph.json`, and `.chopper/trim_report.txt`.
5. Run live `chopper trim` only after the dry-run result matches intent.

Example:

```text
chopper validate --project configs/project_abc.json
chopper trim --dry-run --project configs/project_abc.json
chopper trim --project configs/project_abc.json
```

### Environment Setup

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

## Outputs You Review

| Artifact | Purpose |
| --- | --- |
| `.chopper/chopper_run.json` | Run metadata and outcome |
| `.chopper/compiled_manifest.json` | Final file/proc/stage decisions |
| `.chopper/dependency_graph.json` | Trace graph and reporting-only dependencies |
| `.chopper/trim_report.txt` | Human-readable trim summary |
| `.chopper/diagnostics.json` | All diagnostics for the run |

## Documentation Set

| Path | Audience | Purpose |
| --- | --- | --- |
| [doc/README.md](doc/README.md) | Operators, JSON authors, integrators | Entry point to the user-facing docs |
| [doc/USER_MANUAL.md](doc/USER_MANUAL.md) | Operators | Task-oriented operating guide |
| [doc/BEHAVIOR_GUIDE.md](doc/BEHAVIOR_GUIDE.md) | JSON authors | Merge logic, tracing behavior, and authoring patterns |
| [doc/TECHNICAL_GUIDE.md](doc/TECHNICAL_GUIDE.md) | Integrators and contributors | Short architecture and pipeline map |
| [doc/IMPLEMENTATION_GUIDE.md](doc/IMPLEMENTATION_GUIDE.md) | Engineers reading the code | Code-level implementation walkthrough |
| [json_kit/README.md](json_kit/README.md) | JSON authors | Standalone authoring kit with schemas, examples, and validator |
| [technical_docs/chopper_description.md](technical_docs/chopper_description.md) | Engineers | Authoritative behavior and pipeline specification |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contributors | Development workflow and quality gates |

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

## Contributing

The README is intentionally product-facing. Contributor workflow, local quality gates, implementation rules, and the pull-request checklist live in [CONTRIBUTING.md](CONTRIBUTING.md).
