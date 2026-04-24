# 📘 Chopper — User Manual

![Audience](https://img.shields.io/badge/audience-domain%20owners%20%7C%20operators-0a7a3d)
![Commands](https://img.shields.io/badge/commands-validate%20%7C%20trim%20%7C%20cleanup-8a3ffc)
![Python](https://img.shields.io/badge/python-3.11%2B-3776ab)

Practical reference for day-to-day operators. This guide is about running Chopper safely and efficiently, not about JSON merge theory or internal code structure.

> [!NOTE]
> For JSON authoring behavior, see [BEHAVIOR_GUIDE.md](BEHAVIOR_GUIDE.md). For architecture, see [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md). For the code-level walkthrough, see [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md).

---

## ✂️ What Chopper Does

Chopper trims a VLSI EDA tool-flow domain down to a project-specific subset. You describe what you want to keep in JSON; Chopper produces a minimal, audit-ready domain directory.

It supports three capability classes, used individually or together:

| Capability | Meaning |
| --- | --- |
| **F1 — File trimming** | Keep or drop whole `.tcl`, `.pl`, `.py`, `.csh` files |
| **F2 — Proc trimming** | Keep or drop individual Tcl procs inside a file |
| **F3 — Run-file generation** | Emit `<stage>.tcl` run scripts from JSON stage definitions |

---

## 🛠️ Installation

```powershell
# Windows (PowerShell 5.1+)
. .\setup.ps1
```

```bash
# Unix (tcsh — primary)
source setup.csh

# Unix (bash / zsh fallback)
source setup.sh
```

Each script creates `.venv`, activates it, and installs dev dependencies. Python ≥ 3.11 required.

Verify:

```text
chopper --help
```

> [!TIP]
> **First-time workflow:** open a shell in your domain directory (or pass `--domain PATH`), then: (1) run `chopper validate`, (2) run `chopper trim --dry-run`, (3) read `.chopper/trim_report.txt` and `.chopper/dependency_graph.json`, (4) run live `chopper trim` **only** when the dry-run output matches your intent.

---

## ⚡ The Three Subcommands

```text
chopper validate    # Check JSONs are well-formed and targets exist
chopper trim        # Run the full pipeline and produce trimmed domain/
chopper cleanup     # Remove domain_backup/ after trim window ends
```

The easiest workflow is to run from the domain directory, but you can also stay elsewhere and pass `--domain PATH`.

What each one really does:

| Command | What it does | Writes domain content? |
| --- | --- | --- |
| `validate` | Full read-only analysis: load config, validate schema and targets, parse Tcl, compile selections, run trace, run manifest-only post-validation | No |
| `trim --dry-run` | Same analysis as `validate`, but under the `trim` command surface and with trim-specific reporting | No domain content writes; updates `.chopper/` |
| `trim` | Full live run: analysis plus filesystem rebuild, stage generation, post-validation, and audit writing | Yes |
| `cleanup --confirm` | Deletes `<domain>_backup/` permanently | Yes |

> [!IMPORTANT]
> Global flags `--plain`, `--strict`, `-v`, and `-q` must appear **before** the subcommand — e.g., `chopper --plain --strict trim --project configs/project_abc.json`.

---

## 📋 Operating Tasks

### Task 1. Validate a Selection Before You Trim

Inputs:

- Domain root directory
- `jsons/base.json` (required), plus any feature JSONs you want to apply (optional), or a `project.json` recipe (optional)

Procedure:

Base only:

```text
cd /path/to/my_domain
chopper validate --base jsons/base.json
```

Base + feature JSONs (no project file required):

```text
cd /path/to/my_domain
chopper validate --base jsons/base.json \
    --features jsons/features/dft.feature.json
```

Project recipe (committed combination of base + features):

```text
cd /path/to/my_domain
chopper validate --project project.json
```

Expected Output:

- No domain files are renamed, copied, or removed
- `.chopper/` is refreshed with analysis artifacts
- Schema, file-target, proc-target, trace, and manifest-derived validation issues are reported before any rebuild

> [!WARNING]
> **Common failure modes:** `VE-17` — the JSON `domain` field does not match the operational domain directory. `VE-03` — a `procEntry` contains an empty `procs` list. `PW-01` — Tcl uses computed proc names and Chopper cannot index them safely.

### Task 2. Preview the Trim With `--dry-run`

Inputs:

- A validated base JSON (plus any feature JSONs) or project JSON

Procedure:

Base only:

```text
chopper trim --dry-run --base jsons/base.json
```

Base + feature JSONs:

```text
chopper trim --dry-run --base jsons/base.json \
    --features jsons/features/dft.feature.json
```

Project recipe:

```text
chopper trim --dry-run --project project.json
```

Expected Output:

- Chopper compiles file/proc decisions and runs the trace phase
- Chopper does **not** rename `<domain>/` to `<domain>_backup/`
- Chopper does **not** rewrite domain content files
- Chopper does **not** write generated `<stage>.tcl` files into the domain
- `.chopper/compiled_manifest.json`, `.chopper/dependency_graph.json`, and `.chopper/trim_report.txt` are available for review

> [!WARNING]
> **Common failure modes:** Dry-run is not write-free — it still refreshes `.chopper/` (that is expected). Feature order matters for F3 `flow_actions` — check the compiled stage plan before trimming live.

### Task 3. Execute the First Live Trim

Inputs:

- Dry-run output reviewed and accepted
- Original domain still present at `<domain>/`

Procedure:

Base only:

```text
chopper trim --base jsons/base.json
```

Base + feature JSONs:

```text
chopper trim --base jsons/base.json \
    --features jsons/features/dft.feature.json
```

Project recipe:

```text
chopper trim --project project.json
```

Expected Output:

1. Chopper renames `my_domain/` to `my_domain_backup/`
2. Chopper builds a new trimmed `my_domain/`
3. Chopper writes `.chopper/` inside the rebuilt domain
4. If `stages` are defined, Chopper writes one generated `<stage>.tcl` file per resolved stage (plus a matching `<stage>.stack` when `options.generate_stack: true`)

> [!IMPORTANT]
> **Always validate and dry-run first.** Run live trim only after reviewing `.chopper/compiled_manifest.json` and confirming the domain root is correct.

### Task 4. Re-Trim After Updating JSON

Inputs:

- Existing `<domain>_backup/`
- Updated JSON selection files

Procedure:

```text
chopper trim --base jsons/base.json
```

Or with features:

```text
chopper trim --base jsons/base.json \
    --features jsons/features/dft.feature.json
```

Or via project recipe:

```text
chopper trim --project project.json
```

Expected Output:

- Chopper rebuilds `<domain>/` from `<domain>_backup/`
- Hand-edits inside the trimmed `<domain>/` are discarded
- A fresh `.chopper/` bundle is written for the new run

Common Failure Modes:

- Operators edit files directly inside the trimmed domain and expect those changes to survive a re-trim
- Backup content no longer matches the manifest assumptions, which can trigger backup-content diagnostics

### Task 5. Use Stage JSON and Stack Files Correctly

Inputs:

- Base or feature JSON containing `stages` or `flow_actions`
- Optional: `options.generate_stack: true` in the base JSON to auto-emit `<stage>.stack`

Procedure:

1. Define stage names, command lines, dependencies, and steps in JSON
2. Optionally set `options.generate_stack: true` in the base JSON to also auto-emit scheduler stack files
3. Run `chopper validate` or `chopper trim --dry-run`
4. Inspect `.chopper/compiled_manifest.json` for `GENERATED` entries
5. Run live `chopper trim` when the compiled stage plan is correct

Expected Output:

| You define | Live `trim` writes | Validation and dry-run show |
| --- | --- | --- |
| No `stages` | No generated run files | No generated run files |
| `stages` in base only | One `<stage>.tcl` per base stage | Generated entries in the manifest |
| `stages` plus feature `flow_actions` | One `<stage>.tcl` per final compiled stage | Generated entries in the manifest |
| `stages` with `options.generate_stack: true` | One `<stage>.tcl` **and** one `<stage>.stack` per resolved stage | Both files as `GENERATED` entries in the manifest |

Stage field → stack line mapping (used by the auto-generator and for hand-authored stack files):

| Stage field | Stack line |
| --- | --- |
| `name` | `N <name>` |
| `command` | `J <command>` |
| `exit_codes` | `L <codes>` |
| `dependencies` | `D <deps>` (one `D` line per dependency; falls back to `load_from`, else bare `D`) |
| `inputs` | `I <artifact>` |
| `outputs` | `O <artifact>` |
| `run_mode` | `R <value>` |

When `options.generate_stack` is `false` (the default), scheduler stack files stay manual and Chopper does not touch them — use the table above to author them by hand.

Common Failure Modes:

- Setting `options.generate_stack: true` but authoring no `stages` (the flag is a no-op in that case)
- Hand-editing a generated `<stage>.stack` and expecting the edit to survive a re-trim
- Confusing `load_from` with scheduler dependency ordering

### Task 6. Start From the Correct JSON Example

Inputs:

- A customer domain you want to trim
- The `examples/` folder

Procedure:

1. Pick the nearest example pattern from the table below
2. Copy the example JSON into your domain root
3. Replace every placeholder with actual domain paths, proc names, and stage steps
4. Run `chopper validate`
5. Run `chopper trim --dry-run`
6. Run live `chopper trim` only after the reports match your intent

| Need | Start with | What to copy |
| --- | --- | --- |
| File trimming only | `examples/01_base_files_only/` | `jsons/base.json` |
| Proc trimming only | `examples/02_base_procs_only/` | `jsons/base.json` |
| Generated run scripts from stage JSON | `examples/03_base_stages_only/` | `jsons/base.json` |
| Files plus stages | `examples/05_base_files_and_stages/` | `jsons/base.json` |
| Proc trimming plus stages | `examples/06_base_procs_and_stages/` | `jsons/base.json` |
| Full starting point | `examples/07_base_full/` | `jsons/base.json` |
| Base plus one optional feature | `examples/08_base_plus_one_feature/` | `jsons/` and `project.json` |
| Base plus multiple features | `examples/09_base_plus_multiple_features/` | `jsons/` and `project.json` |
| Feature dependency chain | `examples/10_chained_features_depends_on/` | `jsons/` and `project.json` |
| Project mode without features | `examples/11_project_base_only/` | `jsons/base.json` and `project.json` |

Expected Output:

- The chosen template gives you the correct starting structure without guessing field shapes
- Validation errors point to your real domain data, not to template placeholders

Common Failure Modes:

- Copying an example and running it unchanged
- Choosing a files-only example when the domain actually needs proc trimming or stage generation

### Task 7. Remove the Backup When the Trim Window Closes

Inputs:

- A domain with an existing `<domain>_backup/`

Procedure:

```text
chopper cleanup --confirm
```

Expected Output:

- `<domain>_backup/` is deleted permanently

Common Failure Modes:

- Running cleanup before the team agrees the trim window is over
- Omitting `--confirm`

---

## 🎛️ All CLI Flags

### Global (apply to every subcommand)

These flags must appear before `validate`, `trim`, or `cleanup`.

| Flag | Effect |
| --- | --- |
| `-h`, `--help` | Show help |
| `-v`, `--verbose` | Increase CLI verbosity. `-v` gives more progress detail; `-vv` is the most verbose mode. |
| `-q`, `--quiet` | Suppress progress output. Diagnostics and final summary still print. Useful in CI or scripted runs. |
| `--plain` | Force plain-text output with no Rich live rendering and no ANSI color styling. Use for log capture or plain terminals. |
| `--strict` | Exit with code 1 if any warning is emitted. Warning severities stay as warnings; only the final exit-code policy changes. |

### `chopper validate`

```text
chopper validate [--domain PATH]
                 (--base PATH [--features PATHS] | --project PATH)
```

`validate` is a safe preflight command. It does more than schema checking: it also parses Tcl, compiles the selection, runs the trace phase, and performs read-only post-validation checks. It never rebuilds the domain.

| Flag | Effect |
| --- | --- |
| `--domain PATH` | Domain root to analyze. Default is the current working directory. |
| `--base PATH` | Base JSON to load. Required unless you use `--project`. |
| `--features PATHS` | Comma-separated ordered list of feature JSON paths. Order is preserved and matters for F3 `flow_actions`. |
| `--project PATH` | Project JSON to load. Mutually exclusive with `--base` and `--features`. |

### `chopper trim`

All `validate` flags, plus:

| Flag | Effect |
| --- | --- |
| `--dry-run` | Run the trim command in read-only mode. Chopper still analyzes, compiles, traces, and writes `.chopper/` reports, but it does not rename the domain, rewrite files, or emit generated stage files into the domain. |

### `chopper cleanup`

```text
chopper cleanup [--domain PATH] --confirm
```

| Flag | Effect |
| --- | --- |
| `--domain PATH` | Domain root whose sibling backup directory should be removed. Default is the current working directory. |
| `--confirm` | **Required.** Cleanup refuses to run without it. Deletion is irreversible. |

---

## 🔢 Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | Success. No errors. |
| `1` | One or more user-visible errors were emitted, or `--strict` escalated warnings to a non-zero exit. |
| `2` | CLI or environment precondition failure, such as bad flag usage or an unrecoverable domain/backup state. |
| `3` | Internal programmer error. Capture stderr plus the `.chopper/` bundle and file a bug. |

> [!TIP]
> Use `--strict` in CI pipelines so any warning causes a non-zero exit.

---

## 📦 The `.chopper/` Audit Bundle

Every run writes `.chopper/` inside the current domain. Contents:

| File | Purpose |
| --- | --- |
| `run_id` | Unique ID for this run |
| `chopper_run.json` | CLI args, timing, outcome |
| `compiled_manifest.json` | Per-file / per-proc decisions (FULL_COPY, PROC_TRIM, GENERATED, REMOVE). Generated stage scripts show up here as `GENERATED` even during `validate` and `--dry-run`. |
| `dependency_graph.json` | Full proc call graph from the trace phase |
| `trim_report.json` | Machine-readable summary of what changed |
| `trim_report.txt` | Human-readable projection of the above |
| `diagnostics.json` | Every diagnostic emitted (code, severity, location, hint) |
| `trim_stats.json` | File and SLOC counts before/after |
| `input_base.json` | Verbatim copy of the base JSON used for the run |
| `input_features/NN_name.json` | Verbatim copies of selected feature JSONs, prefixed by feature order |

Even `validate` and `trim --dry-run` update `.chopper/`. Treat it as run output, not as proof that the domain was rebuilt.

> [!NOTE]
> `validate` and `trim --dry-run` also update `.chopper/`. Treat it as run output, not as proof that the domain was rebuilt. You can safely commit it or gitignore it — it is rewritten every run.

---

## 🔧 Minimum JSON to Start

Save as `jsons/base.json`:

```json
{
  "$schema": "chopper/base/v1",
  "domain": "my_domain",
  "files": {
    "include": ["setup.tcl", "procs/**/*.tcl"],
    "exclude": ["procs/legacy/*.tcl"]
  }
}
```

That is enough to start. Run `chopper validate --base jsons/base.json` first, then `chopper trim --dry-run --base jsons/base.json`, and only then run live `chopper trim --base jsons/base.json`.

> [!TIP]
> More JSON patterns, caveats, and best-known methods are in [BEHAVIOR_GUIDE.md](BEHAVIOR_GUIDE.md).

---

## 🔍 Troubleshooting

| Symptom | Fix |
| --- | --- |
| `VE-17 project-domain-mismatch` | The `domain` field in your JSON doesn't match your cwd's folder name. `cd` into the right folder. |
| `VE-21 no-domain-or-backup` | You're in a folder with neither `<domain>/` nor `<domain>_backup/`. Nothing to trim. |
| `VE-03 empty-procs-array` | A `procEntry` has `"procs": []`. Either list procs, or use `files.include` instead. |
| `PW-01 dynamic-proc-name` | Your Tcl has `proc ${prefix}_foo`. Chopper skips it — see the warning for file/line. |
| `TW-04 cycle-in-call-graph` | Two procs call each other. Safe — trace terminates via visited-set. Review reported cycle for intent. |
| `--dry-run still created .chopper/` | Expected. Dry-run skips domain rebuilds, not audit/report writing. Inspect the reports, then run live `trim` if they look right. |
| "Hand edits discarded" | You edited `<domain>/` directly between runs. Move edits to source JSONs, or commit before re-running. |
| Exit code 3 | Internal bug. Save stderr plus `.chopper/chopper_run.json`, `.chopper/diagnostics.json`, and `.chopper/compiled_manifest.json`, then file an issue. |

Full diagnostic registry: [`../technical_docs/DIAGNOSTIC_CODES.md`](../technical_docs/DIAGNOSTIC_CODES.md).

---

## 🔗 Where to Go Next

| 📖 Resource | Purpose |
| --- | --- |
| [BEHAVIOR_GUIDE.md](BEHAVIOR_GUIDE.md) | How Chopper decides what survives, JSON patterns, and FAQs |
| [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md) | Pipeline, modules, ports, and diagnostic codes |
| [../schemas/](../schemas/) and [../examples/](../examples/) | JSON schemas and 11 worked examples |
| [../technical_docs/](../technical_docs/) | Full specification (for contributors) |
