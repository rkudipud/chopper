# Chopper

![Status](https://img.shields.io/badge/status-ready-0a7a3d)
![Python](https://img.shields.io/badge/python-3.11%2B-3776ab)
![License](https://img.shields.io/badge/license-Intel%20Proprietary-555555)
![Pipeline](https://img.shields.io/badge/pipeline-P0--P7-8a3ffc)

[![Chopper Domain Companion](https://img.shields.io/badge/🤖_Agent-Chopper_Domain_Companion-0f62fe)](https://github.com/github/copilot)
[![JSON Kit Domain Analyzer](https://img.shields.io/badge/🤖_Agent-JSON_Kit_Domain_Analyzer-8a3ffc)](json_kit/AGENTS.md)

**Chopper is a Python CLI that surgically trims VLSI EDA tool-flow domains down to exactly what a project actually needs** — specified by JSON, reproducible on every run, and audited automatically after every trim.

Instead of editing Tcl by hand and hoping you caught every dependency, you write JSON to say which files, which procedures, and which run-script stages survive. Chopper parses your domain, compiles your selections, traces the call graph for visibility, trims the domain on disk, generates run scripts if needed, and writes a full audit bundle for review.

> Inspired by the works of **SNORT** by Mike McCurdy and **FlowBuilder** by Stelian Alupoaei.

---

## 🤖 Two AI Companions Ship With This Repo

You do not have to figure out domain boundaries or JSON structure by hand. Two purpose-built agents are included for VS Code Copilot Chat.

### Chopper Domain Companion

![Chopper Domain Companion](https://img.shields.io/badge/VS%20Code%20Agent-Chopper%20Domain%20Companion-0f62fe)

The **Chopper Domain Companion** (`.github/agents/chopper-domain-companion.agent.md`) guides you from a customer codebase all the way to a validated, trimmed output:

- Scans a codebase and identifies domain boundaries, entry points, proc libraries, and optional flows
- Authors `base.json`, feature JSONs, and `project.json` from your domain
- Runs `chopper validate` and `chopper trim --dry-run` and explains the results
- Reads `.chopper/` audit artifacts (manifests, trace graphs, diagnostics) and tells you what to fix
- Refines JSON selections when trim output does not match intent

> [!TIP]
> Open VS Code Copilot Chat and say: *"Analyze my domain at `path/to/domain/` and help me author the base JSON."* The companion takes it from there.

### JSON Kit Domain Analyzer

![JSON Kit Domain Analyzer](https://img.shields.io/badge/VS%20Code%20Agent-JSON%20Kit%20Domain%20Analyzer-8a3ffc)

The **JSON Kit Domain Analyzer** (`json_kit/AGENTS.md`) is a focused, standalone agent for JSON authoring. It is designed to be handed off before the Chopper runtime ships — use it to get all three JSON files authored and schema-validated early:

- Discovers domain structure from a file listing
- Extracts stage definitions from scheduler stack files (translating N/J/L/D/I/O fields into JSON)
- Classifies procs as core, feature-specific, or deprecated
- Splits content between `base.json` (universal) and feature JSONs (optional/conditional)
- Validates each output against the authoritative schemas in `json_kit/schemas/`

> [!TIP]
> Open the `json_kit/` folder in VS Code and ask Copilot Chat: *"Analyze my domain directory and help me author the base, feature, and project JSONs."*

---

## What Chopper Does

Chopper has three capabilities, all driven by JSON and all running through the same eight-phase pipeline:

| Capability | What It Does |
| --- | --- |
| **F1 — File trimming** | Copies or drops entire files based on `files.include` / `files.exclude` |
| **F2 — Proc trimming** | Surgically removes unwanted Tcl procedures inside a file, leaving the rest |
| **F3 — Run-file generation** | Emits `<stage>.tcl` run scripts from JSON stage definitions, replacing manual stack files |

The three commands that operate on those capabilities:

```text
chopper validate    # Full read-only analysis — checks schema, targets, Tcl, and call graph
chopper trim        # Runs validation then rebuilds the trimmed domain on disk
chopper cleanup     # Removes the backup directory after you have confirmed the trim
```

Every run — validate or trim — writes a `.chopper/` audit bundle with manifests, diagnostics, trace graphs, and reports so you can review and reproduce any result.

---

## How to Use Chopper

### Step 1 — Set up the environment

| Platform | Command |
| --- | --- |
| Windows PowerShell | `. .\setup.ps1` |
| Windows cmd.exe | `setup.bat` |
| Unix tcsh/csh | `source setup.csh` |
| Unix bash/zsh/sh | `source setup.sh` |

The bootstrap scripts create `.venv`, activate it, and install dependencies.

### Step 2 — Author your JSON selections

Chopper reads up to three JSON files:

```text
<domain_root>/
├── jsons/
│   ├── base.json              ← files, procs, stages for the base flow
│   └── features/
│       └── my_feature.feature.json   ← overrides and extensions
└── project.json               ← selects which base + features apply
```

Use the **JSON Kit Domain Analyzer** agent to generate these from your codebase, or copy from `json_kit/examples/` and adapt. The schemas in `json_kit/schemas/` enforce correctness.

### Step 3 — Validate first, always

```text
chopper validate --base jsons/base.json
chopper validate --project project.json
```

Validation is fully read-only. It parses Tcl, compiles selections, runs trace, checks the call graph, and reports every issue — without touching the domain on disk.

### Step 4 — Dry-run before you trim

```text
chopper trim --dry-run --project project.json
```

Dry-run produces the same analysis as validate but under the `trim` command surface, with trim-specific reporting in `.chopper/`. Review `.chopper/trim_report.txt` and `.chopper/dependency_graph.json` before committing to a live run.

### Step 5 — Trim live when dry-run matches intent

```text
chopper trim --project project.json
```

> [!IMPORTANT]
> Live trim renames your domain to `<domain>_backup/`, rebuilds a clean trimmed copy, and runs post-validation. Run live only after dry-run output matches intent.

### Step 6 — Review the audit bundle

Open `.chopper/` after any run. All artifacts are JSON and plain text, readable in any editor:

| Artifact | What to Look For |
| --- | --- |
| `trim_report.txt` | Which files were kept, dropped, or proc-trimmed |
| `dependency_graph.json` | Full trace of the call graph — what calls what |
| `compiled_manifest.json` | Final file, proc, and stage decisions before trim |
| `diagnostics.json` | Every diagnostic code emitted (errors, warnings, info) |
| `chopper_run.json` | Run metadata — exit code, phase reached, timing |

---

## The .chopper/ Audit Bundle

Chopper writes `.chopper/` on every run, including failed runs and dry-runs. Nothing is discarded on a re-run — the previous bundle is replaced. If you need to keep history, copy the folder before re-running.

The bundle is designed to be machine-readable. The `run-result-v1.schema.json` and `diagnostic-v1.schema.json` schemas in `json_kit/schemas/` document the format.

---

## Documentation

| Who You Are | Where to Start |
| --- | --- |
| First-time operator | [doc/USER_MANUAL.md](doc/USER_MANUAL.md) — commands, flags, tasks, troubleshooting |
| JSON author / domain owner | [doc/BEHAVIOR_GUIDE.md](doc/BEHAVIOR_GUIDE.md) — merge rules, tracing, patterns, FAQ |
| Integrator or contributor | [doc/TECHNICAL_GUIDE.md](doc/TECHNICAL_GUIDE.md) — pipeline, modules, ports, error model |
| Engineer reading the code | [doc/IMPLEMENTATION_GUIDE.md](doc/IMPLEMENTATION_GUIDE.md) — code-level walkthrough |
| Schema and examples | [json_kit/README.md](json_kit/README.md) — authoring kit, schemas, validator |
| Authoritative specification | [technical_docs/chopper_description.md](technical_docs/chopper_description.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) — workflow, quality gates, scope rules |

---

## Contributing

Contributor workflow, local quality gates, working rules, and the pull-request checklist live in [CONTRIBUTING.md](CONTRIBUTING.md). The short version: run `make check` before opening a pull request, and read the spec before adding anything new.

---

## Acknowledgments

Chopper was inspired by and builds on the foundational thinking behind:

- **SNORT** by Mike McCurdy — domain state detection and trim-lifecycle design
- **FlowBuilder** by Stelian Alupoaei — stage-driven flow modeling and the run-file generation concept
