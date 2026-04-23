# Chopper

Chopper is a Python CLI for trimming VLSI EDA tool-flow domains down to the files, Tcl procedures, and generated run scripts a project actually needs. Selection is driven by JSON, execution is deterministic, and every run writes an audit bundle under `.chopper/` for review.

Release details live in [VERSION.md](VERSION.md).

Inspired by the works of:
- `SNORT` by Mike McCurdy
- `FlowBuilder` by Stelian Alupoaei

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

## Guided Workflow: Use the Chopper Domain Companion Agent

The repo ships with a custom VS Code agent ([.github/agents/chopper-domain-companion.agent.md](.github/agents/chopper-domain-companion.agent.md)) that guides you through the entire workflow:

- **Analyze fit:** Determine whether Chopper is right for your domain and trimming goal.
- **Scan codebase:** Identify entry points, proc libraries, utilities, and optional flows without manual call-tree hunting.
- **Author JSON:** Build and refine `base.json`, feature JSONs, and `project.json` interactively.
- **Run and review:** Execute `chopper validate` and `chopper trim --dry-run`; analyze `.chopper/` artifacts with explanations.
- **Refine:** Understand why output differs from intent; propose JSON and codebase changes.

### Getting Started with the Agent

**In VS Code Copilot Chat:**

1. Open this repository in VS Code.
2. Open GitHub Copilot Chat.
3. If your Copilot setup surfaces custom agents, select **Chopper Domain Companion** and ask:

   - "Analyze my customer codebase under `path/to/domain/` and tell me whether Chopper is a good fit."
   - "Scan this repo, identify the real domain boundary and entry points, and help me author `base.json`, feature JSONs, and `project.json`."
   - "Run `chopper validate` and `chopper trim --dry-run`, then explain the `.chopper/` outputs and tell me what JSON changes I should make."
   - "Read `compiled_manifest.json`, `dependency_graph.json`, and `trim_report.json`, explain why the output differs from my intent, and propose the next JSON edits."

**If custom agents don't show up automatically:**
Open [.github/agents/chopper-domain-companion.agent.md](.github/agents/chopper-domain-companion.agent.md) and copy it into your Copilot instruction source.

---

## Direct CLI Workflow

If you prefer to run commands directly without agent guidance, use the standard procedure below.

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
