# 🧰 Chopper JSON Kit — Standalone Package

![Version](https://img.shields.io/badge/version-1.0.2-0a7a3d)
![Status](https://img.shields.io/badge/status-shippable%20standalone-0f62fe)
![Schemas](https://img.shields.io/badge/schemas-base%20%7C%20feature%20%7C%20project-8a3ffc)

> [!NOTE]
> This package is **self-contained**. You can hand off this folder before the Chopper runtime ships. When Chopper is installed, it reads its schema files from `json_kit/schemas/` automatically.

---

## 🔍 What Is This?

Chopper trims EDA tool domain codebases via three JSON configuration files:

| File | Purpose |
| --- | --- |
| **Base JSON** | Defines the minimal viable flow for a domain (files, procs, stages) |
| **Feature JSON** | Extends or overrides the base for optional or project-specific scenarios |
| **Project JSON** | Selects and orders one base + zero or more features for a specific trim run |

You author these JSONs now. When Chopper is released, you run `chopper trim --project project.json` and it does the rest.

If your JSON defines `stages`, Chopper emits generated `<stage>.tcl` run files. Scheduler stack files remain manually authored; use the same stage fields as the source for those files when your environment requires them.

---

## 📂 Package Contents

```text
json_kit/
├── AGENTS.md                        ← AI agent instructions (GitHub Copilot / Copilot Chat)
├── README.md                        ← You are here
├── VERSION.txt                      ← Schema version tracking
├── requirements.txt                 ← Local Python dependency list for the validator
├── setup.csh                        ← Bootstrap Python venv on tcsh/csh (Unix primary)
├── setup.ps1                        ← Bootstrap Python venv on Windows PowerShell
├── validate_jsons.py                ← One-command schema validation helper
├── schemas/
│   ├── base-v1.schema.json          ← Base JSON schema (authoritative validator)
│   ├── feature-v1.schema.json       ← Feature JSON schema
│   └── project-v1.schema.json       ← Project JSON schema
├── docs/
│   └── JSON_AUTHORING_GUIDE.md      ← Complete field reference, rules, decision guide
├── examples/
│   ├── 01_base_files_only/          ← files.include + files.exclude only
│   ├── 02_base_procs_only/          ← procedures.include + procedures.exclude only
│   ├── 03_base_stages_only/         ← stages only (run-file generation)
│   ├── 04_base_files_and_procs/     ← files + procedures (no stages)
│   ├── 05_base_files_and_stages/    ← files + stages
│   ├── 06_base_procs_and_stages/    ← procedures + stages
│   ├── 07_base_full/                ← files + procedures + stages (maximum control)
│   ├── 08_base_plus_one_feature/    ← base + one feature + project
│   ├── 09_base_plus_multiple_features/ ← base + two independent features + project
│   ├── 10_chained_features_depends_on/ ← three-level depends_on chain + project
│   └── 11_project_base_only/        ← base-only trim (no features)
└── agent/
    └── DOMAIN_ANALYZER.md           ← 8-phase domain analysis protocol for AI-assisted JSON authoring
```

---

## 🚀 10-Minute Quick Start

### 0. Bootstrap Python environment

```tcsh
source setup.csh
```

This creates and activates `.venv` automatically and installs `jsonschema`, which is required for schema validation examples in this repo. Both scripts configure the Intel pip/git proxy by default. Add `. ~/.tcshrc` auto-activation if desired.

Windows PowerShell:

```powershell
. .\setup.ps1
```

> [!TIP]
> Pass `-NoProxy` to skip Intel proxy config on environments that don't need it: `. .\setup.ps1 -NoProxy`

### 1. Choose your starting example

| Your situation | Start with |
| --- | --- |
| Need to trim files only | `examples/01_base_files_only/` |
| Need proc-level surgical trimming | `examples/02_base_procs_only/` |
| Have existing stack files to translate into stage JSON | `examples/03_base_stages_only/` |
| Full control (files + procs + stages) | `examples/07_base_full/` |
| Single optional feature | `examples/08_base_plus_one_feature/` |
| Multiple independent features | `examples/09_base_plus_multiple_features/` |
| Features depend on each other | `examples/10_chained_features_depends_on/` |

### 2. Copy and adapt

The examples are templates. Copy the closest one into your domain root, then replace every placeholder value.

PowerShell:

```powershell
Copy-Item -Recurse .\examples\07_base_full\jsons .\my_domain\
Copy-Item .\examples\11_project_base_only\project.json .\my_domain\
cd .\my_domain
```

Bash or zsh:

```bash
cp -r ./examples/07_base_full/jsons ./my_domain/
cp ./examples/11_project_base_only/project.json ./my_domain/
cd ./my_domain
```

Then edit:

1. `jsons/base.json` to set the real `domain`, file patterns, proc selections, and stage steps.
2. `jsons/features/*.feature.json` only if you need optional layers.
3. `project.json` only if you want project mode.

Use direct mode when you only have a base JSON:

```text
chopper validate --base jsons/base.json
chopper trim --dry-run --base jsons/base.json
```

Use project mode when you copied a project file:

```text
chopper validate --project project.json
chopper trim --dry-run --project project.json
```

> [!IMPORTANT]
> Run `chopper validate` before `chopper trim`. Dry-run first, live trim only when the report matches intent.

### 3. Validate against schemas (one command)

```bash
python validate_jsons.py my_domain/
```

Examples:

```bash
python validate_jsons.py
python validate_jsons.py examples/08_base_plus_one_feature/
python validate_jsons.py my_domain/
python validate_jsons.py --schema-dir /custom/schemas/ my_domain/
```

The script validates Base/Feature/Project JSONs based on `$schema`, prints clear `OK/ERR/SKIP` lines, and returns non-zero on validation failures. Use `--schema-dir` if your schema files live outside the default `schemas/` directory.

### 4. Use the domain analyzer agent

**GitHub Copilot / Copilot Chat (VS Code):** The repo ships with `AGENTS.md` at the root, which is automatically loaded as agent context in Copilot Chat. Just open a Copilot Chat session in this workspace and ask:

> "Analyze my domain directory at `my_domain/` and help me author the base, feature, and project JSONs."

**Other AI assistants (Claude, ChatGPT, etc.):** Open `agent/DOMAIN_ANALYZER.md` as a system prompt or instruction file and ask the same question.

The agent follows an 8-phase process: discover domain structure → extract stack-file stage definitions → extract and classify procs → split base vs. feature content → author base JSON → author feature JSONs → author project JSON → validate. Collaboration checkpoints are built in — the agent pauses after key findings to confirm before finalizing JSON decisions.

---

## 📦 Self-Contained Handoff Contract

If you copy only `json_kit/` to another machine or repository, the folder still works as an authoring kit as long as Python and `jsonschema` are available.

What remains usable after copy-out:

- `schemas/` — authoritative validators
- `docs/JSON_AUTHORING_GUIDE.md` — field-by-field authoring reference
- `examples/` — working templates
- `validate_jsons.py` — local validator
- `AGENTS.md` and `agent/DOMAIN_ANALYZER.md` — AI-assisted authoring instructions
- `setup.csh` and `setup.ps1` — environment bootstrap helpers

What Chopper uses from this folder at runtime:

- `json_kit/schemas/base-v1.schema.json`
- `json_kit/schemas/feature-v1.schema.json`
- `json_kit/schemas/project-v1.schema.json`

Chopper does not need the examples or authoring docs to execute a trim; those are here for JSON authors.

---

## 📁 Where to Put Your JSON Files

The authoritative layout is:

```text
<domain_root>/
├── jsons/
│   ├── base.json
│   └── features/
│       ├── feature_a.feature.json
│       └── feature_b.feature.json
└── project.json
```

`project.json` lives at the domain root and references the other files with paths relative to that root:

```json
{
  "$schema": "chopper/project/v1",
  "project": "PROJECT_ABC",
  "domain": "my_domain",
  "base": "jsons/base.json",
  "features": [
    "jsons/features/feature_a.feature.json",
    "jsons/features/feature_b.feature.json"
  ]
}
```

Chopper is invoked from `<domain_root>/`, so all paths in every JSON are relative to that directory.

---

## 🔑 Key Rules (Quick Reference)

**Naming scheme:** Base JSON is `jsons/base.json`; feature JSONs are `jsons/features/<feature_name>.feature.json`.

| Rule | Detail |
| --- | --- |
| `$schema` required | Must be the exact literal string (e.g., `"chopper/base/v1"`). |
| Base needs content | At least one of `files`, `procedures`, `stages`. |
| Non-empty arrays | `minItems: 1` enforced by schema — never pass an empty array. |
| Paths format | Forward slashes only; no `..`, `//`, or absolute paths. |
| `depends_on` values | Use feature `name` values, not file paths. |
| Feature order | Must satisfy all `depends_on` prerequisites; F3 `flow_actions` are applied in order. |
| `load_from` vs `dependencies` | `load_from` = data predecessor for run script; `dependencies` = scheduler `D` line. |
| `flow_actions` scope | Feature-only; modify base flow at stage level (insert/remove/replace). Applied cumulatively in feature order. |
| `metadata` scope | Feature-only; documentation fields only — Chopper never evaluates them. |

> [!IMPORTANT]
> **`$schema` is always required.** JSONs without it will fail schema validation immediately.

---

## 📊 Input Interaction Matrix

Chopper has four input sets per file. Mixing them creates ambiguity — this matrix resolves all 16 combinations.

**Inputs:** FI = `files.include`, FE = `files.exclude`, PI = `procedures.include`, PE = `procedures.exclude`

**Proc-selection models (choose one per file):**

| Model | Input | Meaning | Surviving procs |
| --- | --- | --- | --- |
| **Additive** | PI | "Keep only these procs" | PI procs from this file |
| **Subtractive** | PE | "Keep the file but remove these procs" | All procs minus PE procs |

**Per-file interaction matrix:**

| # | FI | FE | PI | PE | Treatment | Surviving procs | Warning |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | — | — | — | — | `REMOVE` | — | — |
| 2 | ✓ | — | — | — | `FULL_COPY` | all | — |
| 3 | — | ✓ | — | — | `REMOVE` | — | — |
| 4 | ✓ | ✓ | — | — | `FULL_COPY` (literal) / `REMOVE` (glob) | all / — | — |
| 5 | — | — | ✓ | — | `PROC_TRIM` | PI only | — |
| 6 | — | — | — | ✓ | `PROC_TRIM` | all − PE | — |
| 7 | — | — | ✓ | ✓ | `PROC_TRIM` | PI only (PE ignored) | `VW-12` |
| 8 | ✓ | — | ✓ | — | `FULL_COPY` | all (PI redundant) | `VW-09` |
| 9 | ✓ | — | — | ✓ | `PROC_TRIM` | all − PE | — |
| 10 | ✓ | — | ✓ | ✓ | `PROC_TRIM` | PI only (PE ignored) | `VW-12` |
| 11 | — | ✓ | ✓ | — | `PROC_TRIM` | PI only (FE overridden) | — |
| 12 | — | ✓ | — | ✓ | `REMOVE` | — | `VW-11` |
| 13 | — | ✓ | ✓ | ✓ | `PROC_TRIM` | PI only (PE+FE overridden) | `VW-12` |
| 14 | ✓ | ✓ | ✓ | — | `FULL_COPY` (literal) | all (PI redundant) | `VW-09` |
| 15 | ✓ | ✓ | — | ✓ | `PROC_TRIM` (literal) / `REMOVE` (glob) | all − PE / — | — |
| 16 | ✓ | ✓ | ✓ | ✓ | `PROC_TRIM` | PI only | `VW-12` |

**Key rules:**

- **PE downgrades FULL_COPY:** FI + PE → `PROC_TRIM` (case 9). A file with 100 procs and 4 in PE → 96 survive.
- **FE + PE = both remove:** neither says "keep" → file is removed (case 12). Use PE alone if you want to keep the file.
- **PI wins over PE:** if both reference the same file, PI takes precedence (cases 7, 10, 13, 16).
- **PI overrides FE:** PI forces file survival regardless of FE (cases 11, 13).
- **FI + PI (no PE) stays FULL_COPY:** PI is additive and redundant on a fully included file (cases 8, 14).

---

## 🧰 Where to Start

| Situation | Go Here |
| --- | --- |
| Using GitHub Copilot / Copilot Chat | Open a chat session — `AGENTS.md` is loaded automatically |
| Using another AI assistant | Open [`agent/DOMAIN_ANALYZER.md`](agent/DOMAIN_ANALYZER.md) as a system prompt |
| Reading docs | [`docs/JSON_AUTHORING_GUIDE.md`](docs/JSON_AUTHORING_GUIDE.md) |
| Copying an example | [`examples/`](examples/) — pick the folder matching your scenario |
| Analyzing a domain codebase | Open [`agent/DOMAIN_ANALYZER.md`](agent/DOMAIN_ANALYZER.md) and follow Phase 1 |
| Validating existing JSONs | Run `python validate_jsons.py <path>` from the repo root |

---

## 🔗 Getting Help

| Resource | Purpose |
| --- | --- |
| `validate_jsons.py` | One-command schema validation for any file or folder |
| [`docs/JSON_AUTHORING_GUIDE.md`](docs/JSON_AUTHORING_GUIDE.md) | Full field reference, all rules, decision flowchart |
| [`agent/DOMAIN_ANALYZER.md`](agent/DOMAIN_ANALYZER.md) | Step-by-step domain analysis instructions for AI assistants |
| [`examples/`](examples/) | Working JSON files for every combination |
| `schemas/` | Authoritative validators — when in doubt, validate |
