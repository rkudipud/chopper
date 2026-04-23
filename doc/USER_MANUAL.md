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

## Common Workflows

### 1. First-time trim (direct mode)

```text
cd /path/to/my_domain
chopper validate --base jsons/base.json
chopper trim --dry-run --base jsons/base.json
chopper trim --base jsons/base.json
```

What happens:

1. `my_domain/` is renamed to `my_domain_backup/` (your original, untouched)
2. A new trimmed `my_domain/` is built from it
3. `.chopper/` audit bundle is written inside `my_domain/`

### 2. First-time trim (project mode)

Keep your selection reproducible by wrapping it in a project JSON:

```json
{
  "$schema": "chopper/project/v1",
  "project": "PROJECT_ABC",
  "domain": "my_domain",
  "base": "jsons/base.json",
  "features": ["jsons/features/dft.feature.json"]
}
```

Then:

```text
chopper validate --project configs/project_abc.json
chopper trim --dry-run --project configs/project_abc.json
chopper trim --project configs/project_abc.json
```

### 3. Re-trim (iterative authoring)

You've edited JSONs and want to rebuild. Just run `trim` again:

```text
chopper trim --base jsons/base.json
```

Chopper detects `my_domain_backup/` exists and rebuilds `my_domain/` from it. **Any hand-edits to `my_domain/` are discarded** — the CLI prints a warning every re-trim so you can't miss it. Commit or move hand-edits before re-running.

### 4. End-of-window cleanup

When the 2-week trim window closes and you're ready to finalize:

```text
chopper cleanup --confirm
```

This deletes `my_domain_backup/` permanently. `--confirm` is mandatory — there's no default.

### 5. Dry run (no writes)

Prefix any trim with `--dry-run`:

```text
chopper trim --dry-run --base jsons/base.json
```

What `--dry-run` means in practice:

1. Chopper still loads JSONs, parses Tcl, compiles file/proc decisions, runs the trace phase, and runs post-validation checks that can be derived from the manifest
2. Chopper does **not** rename `<domain>/` to `<domain>_backup/`
3. Chopper does **not** copy, remove, or rewrite domain content files
4. Chopper does **not** write generated `<stage>.tcl` files into the domain
5. Chopper **does** update `.chopper/` inside the domain so you can inspect reports

Use `--dry-run` whenever you change JSON authoring and want to confirm the outcome before touching the domain itself.

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
| `compiled_manifest.json` | Per-file / per-proc decisions (FULL_COPY, PROC_TRIM, GENERATED, REMOVE) |
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

That's it. Run `chopper trim --base jsons/base.json` from `my_domain/`.

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
