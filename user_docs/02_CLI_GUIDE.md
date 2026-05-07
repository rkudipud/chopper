# 02 — CLI Guide

> **Audience:** anyone about to run Chopper. Assumes you have read [01_OVERVIEW.md](01_OVERVIEW.md) (or are willing to skim back when something is unclear).
> **Goal:** every subcommand, every flag, with the deep examples you need to operate safely.

---

## Quick start (the 5-step loop)

```text
1.  chopper validate ...         # read-only sanity check
2.  chopper trim --dry-run ...   # full analysis, no filesystem rebuild
3.  review .chopper/             # trim_report.txt, compiled_manifest.json, dependency_graph.json
4.  chopper trim ...             # live trim; renames domain → backup, rebuilds clean
5.  chopper cleanup --confirm    # remove the backup once the trim window closes
```

Steps 1 and 2 are **safe and free** — run them as often as you want. Step 4 is **destructive** in the sense that it overwrites `<domain>/` (the original is preserved as `<domain>_backup/`). Step 5 is **irreversible**.

---

## Installation

| Platform | Shell | Command |
|---|---|---|
| Unix/Linux/macOS | tcsh / csh (**primary**) | `source setup.csh` |
| Unix/Linux/macOS | bash / zsh | `source setup.sh` |
| Windows | PowerShell 5.1+ | `. .\setup.ps1` |
| Windows | cmd.exe | `setup.bat` |

Each script creates `.venv`, activates it, and installs dependencies. Python ≥ 3.11 required (3.13 preferred). Verify:

```text
chopper --help
chopper --version
```

---

## The four subcommands

```text
chopper validate      # read-only analysis
chopper trim          # full pipeline; rebuilds the trimmed domain on disk
chopper cleanup       # delete <domain>_backup/ permanently
chopper mcp-serve     # stdio-only read-only Model Context Protocol server
```

| Command | Reads JSONs? | Parses Tcl? | Compiles? | Traces? | Rewrites disk? | Writes `.chopper/`? |
|---|---|---|---|---|---|---|
| `validate` | yes | yes | yes | yes | **no** | yes |
| `trim --dry-run` | yes | yes | yes | yes | **no** | yes |
| `trim` (live) | yes | yes | yes | yes | **yes** | yes |
| `cleanup --confirm` | no | no | no | no | yes (deletes backup) | no |
| `mcp-serve` | on request | on request | on request | on request | **never** | on request |

> **Global flags must come before the subcommand.** Example: `chopper --plain --strict trim --project project.json`. `--version` prints the installed version and exits.

---

## Global flags

| Flag | Effect |
|---|---|
| `-h`, `--help` | Show help |
| `--version` | Print version and exit |
| `-v`, `--verbose` | Increase verbosity. `-v` = more progress detail. `-vv` = most verbose. |
| `-q`, `--quiet` | Suppress progress. Diagnostics and the final summary still print. Useful in CI. |
| `--plain` | Disable Rich live rendering and ANSI colour. Use for log capture or plain terminals. |
| `--strict` | Exit `1` if any warning is emitted. Severities themselves are unchanged. |
| `--tool-commands PATH` | Repeatable. Add a vendor tool-command file (one command name per line). Calls matching the pool become `TI-01` info, not `TW-02` warnings. A PrimeTime pool is bundled by default. |

---

## `chopper validate`

Read-only preflight. Loads JSON, validates schemas, parses Tcl, compiles selections, runs trace, runs manifest-only post-validation. **Never rewrites the domain.**

```text
chopper validate [--domain PATH]
                 (--base PATH [--features PATHS] | --project PATH)
```

| Flag | Effect |
|---|---|
| `--domain PATH` | Domain root to analyse. Defaults to the current working directory. |
| `--base PATH` | Base JSON. Required unless `--project` is used. |
| `--features PATHS` | Comma-separated ordered list of feature JSON paths. **Order matters for F3 `flow_actions`.** For `validate` only, any entry may also be a directory; it expands in place to the sorted, non-recursive list of its immediate `*.json` children. |
| `--project PATH` | Project JSON. Mutually exclusive with `--base` and `--features`. |

### Three invocation modes

```text
# Mode 1 — base only (most common starting point)
chopper validate --base jsons/base.json

# Mode 2 — base + features directly
chopper validate --base jsons/base.json \
    --features jsons/features/dft.feature.json,jsons/features/scan_eco.feature.json

# Mode 2b — validate every feature in a directory at once (validate only)
chopper validate --base jsons/base.json --features jsons/features/

# Mode 3 — project recipe (committed combination)
chopper validate --project project.json
```

### Common validate failures

| Code | Meaning | Fix |
|---|---|---|
| `VE-17` project-domain-mismatch | JSON `domain` field doesn't match cwd basename | `cd` into the right folder |
| `VE-21` no-domain-or-backup | Neither `<domain>/` nor `<domain>_backup/` exists | Nothing to trim from |
| `VE-03` empty-procs-array | A `procEntry` has `"procs": []` | List procs, or use `files.include` |
| `PW-01` dynamic-proc-name | Tcl uses `proc ${prefix}_foo` | Chopper skips it — see warning location |

---

## `chopper trim`

Same flags as `validate`, plus `--dry-run`. Live trim renames `<domain>/` → `<domain>_backup/`, rebuilds a clean trimmed `<domain>/`, generates run scripts (if any), runs post-validation, and writes `.chopper/`.

```text
chopper trim [--domain PATH] [--dry-run]
             (--base PATH [--features PATHS] | --project PATH)
```

| Flag | Effect |
|---|---|
| `--dry-run` | Run the full analysis under the `trim` command surface, but **skip** the rename, the file rewrites, and the generated stage emission. `.chopper/` still updates. |

### Dry-run vs validate

Both are read-only. The difference is reporting context: `trim --dry-run` writes the trim-flavoured `.chopper/trim_report.txt` and exposes the trim-time `compiled_manifest.json`, including `GENERATED` entries for stages. Use `validate` for the cheapest possible check; use `trim --dry-run` when you specifically want the trim report shape.

### Live trim — what actually happens on disk

1. `<domain>/` is renamed to `<domain>_backup/` (first trim) or the existing backup is reused (re-trim).
2. A fresh `<domain>/` is built by walking the backup and applying per-file decisions:
   - **`FULL_COPY`** — opaque byte-for-byte copy via `shutil.copy2` (mode bits preserved on POSIX).
   - **`PROC_TRIM`** — Tcl file rewritten in place: kept procs survive, the rest are removed.
   - **`REMOVE`** — file is not copied across.
   - **`GENERATED`** — `<stage>.tcl` (and `<stage>.stack` if `options.generate_stack: true`) written into the rebuilt domain.
3. P5c — every emitted Tcl file is normalised by a deterministic indentation pass.
4. P6 — the rebuilt output is re-parsed; brace-balance, dangling proc references, and stage-step references are checked. Issues become `VW-*` warnings.
5. P7 — `.chopper/` is written.

> **You always have a recoverable state.** If the run fails between phases, `<domain>_backup/` is untouched and the next invocation rebuilds cleanly from it.

### Re-trim

Just run `chopper trim` again. Chopper detects the existing backup, discards the current `<domain>/`, and rebuilds from backup using your latest JSONs.

> **Hand-edits to `<domain>/` are lost on re-trim.** Move them into source files under `<domain>_backup/` (then re-trim picks them up) or commit the trimmed domain to git and re-apply after each trim.

---

## `chopper cleanup`

```text
chopper cleanup [--domain PATH] --confirm
```

| Flag | Effect |
|---|---|
| `--domain PATH` | Domain root whose sibling backup directory should be removed. Defaults to cwd. |
| `--confirm` | **Required.** Cleanup refuses to run without it. Deletion is irreversible. |

Use it when the team agrees the trim window is closed. Once `<domain>_backup/` is gone, `chopper trim` will exit with `VE-21` instead of silently rebuilding from backup — that is the intended safety net.

---

## `chopper mcp-serve`

```text
chopper mcp-serve
```

Starts a **stdio-only** JSON-RPC Model Context Protocol server. Reads frames on stdin, writes responses on stdout, logs to stderr. No TCP, no HTTP, no daemon, no discovery beacon. Blocks until the client disconnects (stdin EOF) or SIGINT.

### Tools exposed (exactly three, all read-only)

| Tool | Parameters | Returns |
|---|---|---|
| `chopper.validate` | `{ domain_root, base?, features?, project?, strict? }` | Typed `RunResult` JSON — same code path as the CLI. |
| `chopper.explain_diagnostic` | `{ code }` (e.g. `"VE-06"`) | Registry entry (slug, severity, phase, source, exit code, description, recovery hint) |
| `chopper.read_audit` | `{ bundle_path }` | Full JSON contents of every file under the `.chopper/` bundle, keyed by relative path |

`chopper.trim` and `chopper.cleanup` are **never** advertised over MCP — by design, by code, and by an enforcing integration test.

### Example: Claude Desktop config

```json
{
  "mcpServers": {
    "chopper": {
      "command": "chopper",
      "args": ["mcp-serve"]
    }
  }
}
```

### MCP-specific exit code

`4` — `PE-04 mcp-protocol-error` (malformed JSON-RPC frame or unknown tool name). Only `mcp-serve` ever produces exit 4.

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | One or more user-visible errors, or `--strict` escalated warnings to non-zero |
| `2` | CLI / environment precondition failure (bad flag, unrecoverable domain state) |
| `3` | Internal programmer error. `.chopper/internal-error.log` has the full traceback. File a bug. |
| `4` | `PE-04 mcp-protocol-error`. Only from `mcp-serve`. |

> **CI tip:** `chopper --strict trim --project project.json` returns `1` on any warning — wire that into your build to surface drift early.

---

## The `.chopper/` audit bundle

Every run writes `.chopper/` inside the current domain — including failed runs and dry-runs. The bundle is replaced on each run; copy it elsewhere if you need history.

| File | Purpose |
|---|---|
| `run_id` | Unique ID for this run |
| `chopper_run.json` | CLI args, timing, outcome |
| `compiled_manifest.json` | Per-file/per-proc decisions (`FULL_COPY`, `PROC_TRIM`, `GENERATED`, `REMOVE`) |
| `dependency_graph.json` | Full proc call graph from the trace phase |
| `trim_report.json` | Machine-readable summary — file counts, proc counts, SLOC fields |
| `trim_report.txt` | Human-readable projection of the above |
| `trim_stats.json` | File and SLOC counts before/after |
| `diagnostics.json` | Every diagnostic emitted (code, severity, location, hint) |
| `files_kept.txt` | Sorted list of paths that survived, with per-line provenance (`<path>\t<source>:<field>,...`) |
| `files_removed.txt` | Sorted list of paths physically removed, with `default-exclude` or `vetoed-by:<sources>` |
| `internal-error.log` | **Only on exit 3.** Run ID, timestamp, version, platform, full traceback, diagnostic snapshot, RunConfig. |
| `input_base.json` | Verbatim copy of the base JSON used |
| `input_features/NN_name.json` | Verbatim copies of feature JSONs, prefixed by feature order |

All JSON is written with deterministic key order, UTF-8, trailing newline.

---

## Deep examples

### Example A — first-time trim of an unknown domain

```text
cd /work/projects/abc
ls
# my_domain/   project.json   jsons/

chopper validate --project project.json
# read .chopper/diagnostics.json — fix any VE-* errors first

chopper trim --dry-run --project project.json
# read .chopper/trim_report.txt — confirm file/proc counts look right
# read .chopper/dependency_graph.json — scan for TW-* warnings

chopper trim --project project.json
# my_domain_backup/ now exists; my_domain/ is the trimmed copy

# ... project work happens against my_domain/ ...

chopper cleanup --confirm   # once the team agrees the window is closed
```

### Example B — iterating on a feature JSON

```text
# Edit jsons/features/dft.feature.json
chopper trim --dry-run --base jsons/base.json --features jsons/features/dft.feature.json

# Compare manifests across two iterations:
cp .chopper/compiled_manifest.json /tmp/manifest_before.json
# (edit JSON)
chopper trim --dry-run --base jsons/base.json --features jsons/features/dft.feature.json
diff /tmp/manifest_before.json .chopper/compiled_manifest.json
```

### Example C — bisect a feature that broke trim

```text
# Run with the full feature list, fails:
chopper trim --base jsons/base.json --features jsons/features/a.json,jsons/features/b.json,jsons/features/c.json

# Drop features one at a time to find the culprit:
chopper trim --dry-run --base jsons/base.json --features jsons/features/a.json,jsons/features/b.json
chopper trim --dry-run --base jsons/base.json --features jsons/features/a.json,jsons/features/c.json
# ...

# Or ask the Chopper Agent: prompt "bisect-feature-breakage"
```

### Example D — CI gate

```text
# Fail the build on any warning, log everything plainly for the CI viewer:
chopper --plain --strict validate --project project.json 2>&1 | tee chopper.log
```

### Example E — quiesce a tool-command-heavy domain

```text
# PrimeTime is bundled by default. For Genus, ICC2, etc., pass extra pools:
chopper validate --tool-commands /shared/eda/genus.commands \
                 --tool-commands /shared/eda/icc2.commands \
                 --project project.json
```

### Example F — generate stage + stack files

`base.json`:

```json
{
  "$schema": "base-v1",
  "domain": "my_domain",
  "files": { "include": ["procs/**/*.tcl"] },
  "stages": [
    {
      "name": "main",
      "command": "-xt vw Imy_shell -B BLOCK -T main",
      "exit_codes": [0],
      "dependencies": [],
      "steps": ["source setup.tcl", "run_setup", "load_design"]
    }
  ],
  "options": { "generate_stack": true }
}
```

After `chopper trim --base jsons/base.json`:

- `my_domain/main.tcl` — three sourced steps in order
- `my_domain/main.stack` — `N main`, `J -xt vw ...`, `L 0`, `D` (no dependencies), etc.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `VE-17 project-domain-mismatch` | `cd` into the folder whose name matches the JSON `domain` field |
| `VE-21 no-domain-or-backup` | You are in a folder with neither `<domain>/` nor `<domain>_backup/` |
| `VI-03 domain-suffix-strip-applied` | Info, not an error. Your `--domain` (or cwd) ended in `_backup` and a live sibling exists, so Chopper redirected to the live sibling. If you genuinely meant the `_backup` path, rename the colliding live sibling or run from inside the intended domain. |
| `VE-03 empty-procs-array` | `procEntry` has `"procs": []` — list procs or use `files.include` |
| `PW-01 dynamic-proc-name` | Tcl uses `proc ${prefix}_foo`. Chopper cannot index it — list the resolved name(s) explicitly. |
| `TW-02` flood | Pass `--tool-commands` so vendor commands surface as `TI-01` info instead. |
| `TW-04 cycle-in-call-graph` | Two procs call each other. Trace terminates safely via visited-set. Review for intent. |
| Dry-run still created `.chopper/` | Expected. Dry-run skips domain rebuild, not audit/report writing. |
| "Hand edits discarded" | You edited `<domain>/` directly between runs. Move edits to source JSONs or to `<domain>_backup/`. |
| Exit code 3 | Internal bug. Save `.chopper/internal-error.log`, `.chopper/chopper_run.json`, and `.chopper/diagnostics.json`. Use the `report-chopper-bug` Copilot prompt or file an issue manually. |
| Exit code 4 | Only from `mcp-serve` — malformed/unknown MCP request. Inspect the client's JSON-RPC frame. |

Full diagnostic registry: [../technical_docs/DIAGNOSTIC_CODES.md](../technical_docs/DIAGNOSTIC_CODES.md).

---

## Reporting bugs

Fastest path: open VS Code Copilot Chat, pick the **Chopper Agent**, and run the `report-chopper-bug` prompt. It packages local evidence, drafts the GitHub issue body, and (when `gh` is installed and authenticated) files the issue automatically. If `gh` is not available it falls back to a local issue body and bundle paths you can paste manually.

Manual path — open a [GitHub bug report](https://github.com/rkudipud/chopper/issues/new?template=bug_report.yml) and include:

1. The full command that was run
2. Your JSON(s) (redact secrets)
3. `.chopper/chopper_run.json`
4. `.chopper/diagnostics.json`
5. `.chopper/compiled_manifest.json` if it exists
6. `.chopper/internal-error.log` if the run exited with code 3

Package multiple paths into one zip:

```text
python schemas/scripts/package_bug_report.py /abs/path/to/.chopper /abs/path/to/report.md
```

---

## Next

Go to **[03_HOW_CHOPPER_WORKS.md](03_HOW_CHOPPER_WORKS.md)** to see the pipeline, the design rules, and the broader context for *where* and *when* to use Chopper.
