# Chopper — User Manual

Practical reference for day-to-day operators. This guide is about running Chopper safely and efficiently, not about JSON merge theory or internal code structure. For detailed behavior, see [`BEHAVIOR_GUIDE.md`](BEHAVIOR_GUIDE.md). For architecture, see [`TECHNICAL_GUIDE.md`](TECHNICAL_GUIDE.md). For the code-level implementation walkthrough, see [`IMPLEMENTATION_GUIDE.md`](IMPLEMENTATION_GUIDE.md).

---

## What Chopper Does

Chopper trims a VLSI EDA tool-flow domain down to a project-specific subset. You describe what you want to keep in JSON; Chopper produces a minimal, audit-ready domain directory.

It supports three capability classes, used individually or together:

| Capability | Meaning |
| --- | --- |
| **F1 — File trimming** | Keep or drop whole `.tcl`, `.pl`, `.py`, `.csh` files |
| **F2 — Proc trimming** | Keep or drop individual Tcl procs inside a file |
| **F3 — Run-file generation** | Emit `<stage>.tcl` run scripts from JSON stage definitions |

---

## Installation

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

Fresh-user path:

1. Open a shell in your domain directory, or stay elsewhere and pass `--domain PATH`
2. Run `chopper validate ...`
3. Run `chopper trim --dry-run ...`
4. Read `.chopper/trim_report.txt` and `.chopper/dependency_graph.json`
5. Run live `chopper trim ...` only when the dry-run output matches your intent

---

## The Three Subcommands

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

Global options such as `--plain`, `--strict`, `-v`, and `-q` belong before the subcommand:

```text
chopper --plain --strict trim --project configs/project_abc.json
```

---

## Operating Tasks

### Task 1. Validate a Selection Before You Trim

Inputs:

- Domain root directory
- Either `jsons/base.json` or `project.json`

Procedure:

Direct mode:

```text
cd /path/to/my_domain
chopper validate --base jsons/base.json
```

Project mode:

```text
cd /path/to/my_domain
chopper validate --project project.json
```

Expected Output:

- No domain files are renamed, copied, or removed
- `.chopper/` is refreshed with analysis artifacts
- Schema, file-target, proc-target, trace, and manifest-derived validation issues are reported before any rebuild

Common Failure Modes:

- `VE-17`: the JSON `domain` field does not match the operational domain directory
- `VE-03`: a `procEntry` contains an empty `procs` list
- `PW-01`: Tcl uses computed proc names and Chopper cannot index them safely

### Task 2. Preview the Trim With `--dry-run`

Inputs:

- A validated base JSON or project JSON

Procedure:

```text
chopper trim --dry-run --base jsons/base.json
```

Or:

```text
chopper trim --dry-run --project project.json
```

Expected Output:

- Chopper compiles file/proc decisions and runs the trace phase
- Chopper does **not** rename `<domain>/` to `<domain>_backup/`
- Chopper does **not** rewrite domain content files
- Chopper does **not** write generated `<stage>.tcl` files into the domain
- `.chopper/compiled_manifest.json`, `.chopper/dependency_graph.json`, and `.chopper/trim_report.txt` are available for review

Common Failure Modes:

- Operators assume dry-run is write-free; it still refreshes `.chopper/`
- Feature order is wrong for F3 `flow_actions`, so the generated-stage plan is not what you expected

### Task 3. Execute the First Live Trim

Inputs:

- Dry-run output reviewed and accepted
- Original domain still present at `<domain>/`

Procedure:

Direct mode:

```text
chopper trim --base jsons/base.json
```

Project mode:

```text
chopper trim --project project.json
```

Expected Output:

1. Chopper renames `my_domain/` to `my_domain_backup/`
2. Chopper builds a new trimmed `my_domain/`
3. Chopper writes `.chopper/` inside the rebuilt domain
4. If `stages` are defined, Chopper writes one generated `<stage>.tcl` file per resolved stage

Common Failure Modes:

- The operator runs live trim before checking `.chopper/compiled_manifest.json`
- The wrong domain root is active when the command starts

### Task 4. Re-Trim After Updating JSON

Inputs:

- Existing `<domain>_backup/`
- Updated JSON selection files

Procedure:

```text
chopper trim --base jsons/base.json
```

Or:

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

### Task 5. Use Stage JSON and Manual Stack Files Correctly

Inputs:

- Base or feature JSON containing `stages` or `flow_actions`

Procedure:

1. Define stage names, command lines, dependencies, and steps in JSON
2. Run `chopper validate` or `chopper trim --dry-run`
3. Inspect `.chopper/compiled_manifest.json` for `GENERATED` entries
4. Run live `chopper trim` when the compiled stage plan is correct

Expected Output:

| You define | Live `trim` writes | Validation and dry-run show |
| --- | --- | --- |
| No `stages` | No generated run files | No generated run files |
| `stages` in base only | One `<stage>.tcl` per base stage | Generated entries in the manifest |
| `stages` plus feature `flow_actions` | One `<stage>.tcl` per final compiled stage | Generated entries in the manifest |

Stack files stay manual. Use the same stage metadata to author scheduler lines yourself:

| Stage field | Manual stack line |
| --- | --- |
| `name` | `N <name>` |
| `command` | `J <command>` |
| `exit_codes` | `L <codes>` |
| `dependencies` | `D <deps>` |
| `inputs` | `I <artifact>` |
| `outputs` | `O <artifact>` |
| `run_mode` | `R <value>` |

Common Failure Modes:

- Expecting Chopper to auto-write the scheduler stack file
- Confusing `load_from` with scheduler dependency ordering

### Task 6. Start From the Correct JSON Example

Inputs:

- A customer domain you want to trim
- The `json_kit/examples/` folder

Procedure:

1. Pick the nearest example pattern from the table below
2. Copy the example JSON into your domain root
3. Replace every placeholder with actual domain paths, proc names, and stage steps
4. Run `chopper validate`
5. Run `chopper trim --dry-run`
6. Run live `chopper trim` only after the reports match your intent

| Need | Start with | What to copy |
| --- | --- | --- |
| File trimming only | `json_kit/examples/01_base_files_only/` | `jsons/base.json` |
| Proc trimming only | `json_kit/examples/02_base_procs_only/` | `jsons/base.json` |
| Generated run scripts from stage JSON | `json_kit/examples/03_base_stages_only/` | `jsons/base.json` |
| Files plus stages | `json_kit/examples/05_base_files_and_stages/` | `jsons/base.json` |
| Proc trimming plus stages | `json_kit/examples/06_base_procs_and_stages/` | `jsons/base.json` |
| Full starting point | `json_kit/examples/07_base_full/` | `jsons/base.json` |
| Base plus one optional feature | `json_kit/examples/08_base_plus_one_feature/` | `jsons/` and `project.json` |
| Base plus multiple features | `json_kit/examples/09_base_plus_multiple_features/` | `jsons/` and `project.json` |
| Feature dependency chain | `json_kit/examples/10_chained_features_depends_on/` | `jsons/` and `project.json` |
| Project mode without features | `json_kit/examples/11_project_base_only/` | `jsons/base.json` and `project.json` |

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

## All CLI Flags

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

## Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | Success. No errors. |
| `1` | One or more user-visible errors were emitted, or `--strict` escalated warnings to a non-zero exit. |
| `2` | CLI or environment precondition failure, such as bad flag usage or an unrecoverable domain/backup state. |
| `3` | Internal programmer error. Capture stderr plus the `.chopper/` bundle and file a bug. |

`--strict` turns exit `0` with warnings into exit `1`.

---

## The `.chopper/` Audit Bundle

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

You can safely commit `.chopper/` alongside trimmed domain content, or gitignore it — it's rewritten every run.

---

## Minimum JSON You Need to Start

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

More patterns are in [`BEHAVIOR_GUIDE.md`](BEHAVIOR_GUIDE.md).

---

## Troubleshooting

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

## Where to Go Next

- **How Chopper decides what survives, JSON patterns, and FAQs** → [`BEHAVIOR_GUIDE.md`](BEHAVIOR_GUIDE.md)
- **Pipeline, modules, ports** → [`TECHNICAL_GUIDE.md`](TECHNICAL_GUIDE.md)
- **JSON schemas and worked examples** → [`../json_kit/`](../json_kit/)
- **Full spec (for contributors)** → [`../technical_docs/`](../technical_docs/)
