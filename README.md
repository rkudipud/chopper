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
| [json_kit/README.md](json_kit/README.md) | JSON authors | Standalone authoring kit with schemas, examples, and validator |
| [technical_docs/chopper_description.md](technical_docs/chopper_description.md) | Engineers | Authoritative behavior and pipeline specification |
| [technical_docs/CLI_HELP_TEXT_REFERENCE.md](technical_docs/CLI_HELP_TEXT_REFERENCE.md) | Engineers, doc writers | Canonical CLI wording and option reference |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contributors | Development workflow, design constraints, and PR checklist |

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
