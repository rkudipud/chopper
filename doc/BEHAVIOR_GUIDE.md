# 🧠 Chopper — Behavior Guide

![Audience](https://img.shields.io/badge/audience-JSON%20authors%20%7C%20domain%20owners-0a7a3d)
![Topics](https://img.shields.io/badge/topics-merge%20rules%20%7C%20tracing%20%7C%20JSON%20patterns%20%7C%20FAQ-8a3ffc)

How Chopper decides what survives, what to watch out for, and how to solve common authoring problems. Written for domain owners who already know the CLI.

> [!NOTE]
> Assumes you know the CLI. For command reference see [USER_MANUAL.md](USER_MANUAL.md). For the code walkthrough see [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md).

---

## Table of Contents

1. [Mental Model in 60 Seconds](#1-mental-model-in-60-seconds)
2. [How Chopper Merges Your JSONs](#2-how-chopper-merges-your-jsons)
3. [What Tracing Really Does](#3-what-tracing-really-does)
4. [JSON Patterns by Intent](#4-json-patterns-by-intent)
5. [Caveats and Gotchas](#5-caveats-and-gotchas)
6. [Best Known Methods](#6-best-known-methods)
7. [Easy Hacks](#7-easy-hacks)
8. [FAQ](#8-faq)

---

## 1. Mental Model in 60 Seconds

Chopper is a **static, additive trimmer**.

> [!IMPORTANT]
> **Three rules that govern everything:**
>
> 1. 🚫 **Default is exclude.** If no JSON keeps a file, it gets removed. There is no “keep everything unless I say otherwise” mode.
> 2. ✅ **Explicit include always wins.** If any JSON says “keep `foo.tcl`”, nothing else can remove it. Features cannot override the base’s inclusions.
> 3. 🔍 **Tracing is reporting-only.** The call-graph trace produces warnings and `dependency_graph.json` so you understand coupling, but it **never auto-copies** procs into the output. Only procs you listed explicitly survive.

Everything else in this guide is a consequence of these three rules.

If you're new, use this loop:

1. `chopper validate ...`
2. `chopper trim --dry-run ...`
3. Read `.chopper/trim_report.txt`
4. Read `.chopper/dependency_graph.json`
5. Run live `chopper trim ...` only after the dry-run result matches your intent

---

## 2. How Chopper Merges Your JSONs

### Sources

A **source** is one JSON file — the base, or any one selected feature. The project JSON is not a source; it's a list of sources.

### Per-source classification (what each JSON contributes)

For each file `F`, each source can contribute one of three things:

| Source's inputs for `F` | Contribution |
| --- | --- |
| File listed in `files.include` (literal or matching glob), no `procedures.exclude` | **Whole file** |
| Procs listed in `procedures.include`, no `files.include` | **Trim: keep only those procs** |
| `procedures.exclude` present (with or without same-source `files.include`) | **Trim: keep all procs except those** |
| `files.exclude` only | **Nothing** (but may veto another source — see below) |
| Nothing | **Nothing** |

### Cross-source aggregation (what happens when sources disagree)

When two sources both touch the same file, Chopper unions the includes:

| Situation | Result |
| --- | --- |
| Any source says "whole file" | File survives as `FULL_COPY`. All procs kept. |
| No whole-file signal, but some source has includes | File survives as `PROC_TRIM`. Surviving procs = union of every source's kept set. |
| No source includes anything for the file | File is removed (or `GENERATED` if it's an F3 stage output). |

### Veto diagnostics (features trying to remove base content)

Features are **additive only**. A feature's exclude cannot remove what another source included. When it tries, Chopper tells you:

| Code | When it fires | What got vetoed |
| --- | --- | --- |
| `VW-18` cross-source-pe-vetoed | Feature excludes proc `p`, but another source includes the file whole or lists `p` explicitly | Feature's PE entry ignored |
| `VW-19` cross-source-fe-vetoed | Feature excludes file `F`, but another source includes `F` | Feature's FE entry ignored |

These are warnings, not errors. Run with `--strict` if you want CI to fail on them.

### Same-source conflicts (authoring mistakes in one JSON)

| Code | Meaning | Fix |
| --- | --- | --- |
| `VW-09` fi-pi-overlap | You listed file in `files.include` AND individual procs in `procedures.include` | Drop the PI — FI alone keeps everything |
| `VW-11` fe-pe-same-source-conflict | Same JSON has `files.exclude` and `procedures.exclude` for the same file, no `files.include` | Pick one: exclude the whole file, or keep it and trim procs |
| `VW-12` pi-pe-same-file | Same JSON lists procs in both `procedures.include` and `procedures.exclude` for one file | PI wins, PE ignored |
| `VW-13` pe-removes-all-procs | Your PE set covers every proc in the file | File survives as comment-only. Consider `files.exclude` instead |

---

## 3. What Tracing Really Does

Tracing runs in phase P4 and produces:

- `dependency_graph.json` — who calls whom
- `TW-01`..`TW-04` warnings for ambiguous / cyclic / unresolved calls
- The “PI+” set in `trim_report.json` — every proc reachable from your explicit includes

> [!IMPORTANT]
> **Tracing does not copy traced procs.** This is the most-missed point in Chopper. Only procs you explicitly listed in `procedures.include` (or files you listed in `files.include`) survive in the trimmed output.

### Worked example

`jsons/base.json`:

```json
{
  "$schema": "chopper/base/v1",
  "domain": "my_domain",
  "procedures": {
    "include": [{"file": "procs/core.tcl", "procs": ["foo"]}]
  }
}
```

`procs/core.tcl`:

```tcl
proc foo {} { bar }
proc bar {} { puts "hi" }
```

After trim:

| Proc | In output? | In `dependency_graph.json`? |
| --- | --- | --- |
| `foo` | Yes (explicitly included) | Yes |
| `bar` | **No** (only reached via trace) | Yes (as a PT — traced-only proc) |

Run `foo` in the trimmed domain → **broken at runtime**. Fix by adding `bar` explicitly:

```json
{"procedures": {"include": [{"file": "procs/core.tcl", "procs": ["foo", "bar"]}]}}
```

Or by including the whole file:

```json
{"files": {"include": ["procs/core.tcl"]}}
```

### Trace diagnostics cheatsheet

| Code | Meaning | Recommended action |
| --- | --- | --- |
| `TW-01` resolved-ambiguous | Call could match multiple procs (same short name in different files) | Pick one or qualify with namespace |
| `TW-02` namespace-unresolved | Namespace-qualified call couldn't be resolved inside the domain | Verify namespace path, or accept that callee lives outside the domain |
| `TW-03` dynamic-call-form | `$cmd`, `eval "..."`, `uplevel` — can't be statically resolved | Add explicitly if needed, or accept the ambiguity |
| `TW-04` cycle-in-call-graph | Two procs call each other | Review — usually safe, but can mask intent bugs |

---

## 4. JSON Patterns by Intent

### "Keep this directory tree of Tcl files"

```json
{"files": {"include": ["procs/**/*.tcl"]}}
```

Globs: `*` (one segment), `?` (one char), `**` (any depth).

### "Keep everything except legacy"

```json
{"files": {"include": ["**/*.tcl"], "exclude": ["procs/legacy/**"]}}
```

`files.exclude` prunes glob expansions but **never literal includes**.

### "Keep the file, but drop a handful of procs"

```json
{
  "files":      {"include": ["procs/shared.tcl"]},
  "procedures": {"exclude": [{"file": "procs/shared.tcl", "procs": ["debug_dump", "old_helper"]}]}
}
```

Result: `procs/shared.tcl` is `PROC_TRIM`, not `FULL_COPY`.

### "Only a few procs from a big file"

```json
{"procedures": {"include": [{"file": "procs/core.tcl", "procs": ["run_setup", "load_design"]}]}}
```

Don't also add the file to `files.include` — that silently upgrades to whole-file and emits `VW-09`.

### "Layer a feature on top of base"

`jsons/features/dft.feature.json`:

```json
{
  "$schema": "chopper/feature/v1",
  "name": "dft",
  "files": {"include": ["procs/dft_procs.tcl"]},
  "flow_actions": [{
    "action": "add_stage_after",
    "name": "dft_check",
    "reference": "main",
    "steps": ["source procs/dft_procs.tcl", "verify_scan"]
  }]
}
```

Selected via project JSON `features` array. Feature order matters for `flow_actions` sequencing (F3); it doesn't matter for F1/F2 merging.

### "Feature depends on another feature"

```json
{
  "$schema": "chopper/feature/v1",
  "name": "scan_eco",
  "depends_on": ["dft"]
}
```

Chopper topologically sorts features, validates `depends_on`, and errors if you reference a feature not in the project's `features` list.

### "Generate a run script"

Base JSON:

```json
{
  "stages": [{
    "name": "main",
    "load_from": "",
    "command": "-xt vw Imy_shell -B BLOCK -T main",
    "exit_codes": [0],
    "steps": ["source setup.tcl", "run_setup", "load_design"]
  }]
}
```

After trim: `my_domain/main.tcl` exists with those steps in order.

---

## 5. Caveats and Gotchas

### The filesystem is static during a run

> [!WARNING]
> Chopper assumes no process touches `<domain>/` or `<domain>_backup/` while it runs. No locks, no mtime polling. If you edit files mid-run, behavior is undefined. **Run Chopper against a quiesced domain.**

### Re-trim always rebuilds from backup

> [!WARNING]
> Every re-trim **discards** the current `<domain>/` and rebuilds from `<domain>_backup/`. Hand-edits to `<domain>/` between runs are lost. The CLI prints a warning every re-trim. If you want to persist a tweak, either:
>
> 1. Add it to the source files in `<domain>_backup/` (then re-trim picks it up), or
> 2. Commit the trimmed `<domain>/` to git and re-apply after trim.

### Tracing is bounded to the domain path

Calls to procs defined outside the selected domain are treated as external and not traced. Cross-domain dependencies are assumed globally available.

### Dynamic Tcl is not resolved

`${prefix}_helper`, `eval "..."`, `uplevel`, `$cmd $args` — these emit warnings (`PW-01`, `TW-03`) and are not followed. If your domain relies on dynamic dispatch, include the targets explicitly.

### Globs only apply to `files.*`

`procedures.include` / `procedures.exclude` require **exact** file paths and proc names. No `*` patterns in proc entries.

### Empty `procs: []` is a hard error

`VE-03` — an entry with no procs is an authoring bug (usually incomplete edits). Either list procs or remove the entry.

### `domain` field must match cwd basename

`VE-17` project-domain-mismatch. Chopper refuses to run if your JSON's `domain` doesn't match the basename of the current working directory (case-insensitive via `casefold()`).

### Non-Tcl files are file-level only

Perl, Python, shell — F1 treats them as opaque. No subroutine-level trimming. This is deliberate (`OOS-01`) and permanent.

### `--strict` is exit-code policy only

It does not rewrite severities. Warnings stay warnings in diagnostics; `--strict` just makes their presence cause exit code 1.

---

## 6. Best Known Methods

### Author JSON top-down

1. Start with `files.include` globs covering the big strokes.
2. Run `chopper trim --dry-run` and read `trim_report.txt`.
3. Narrow with `files.exclude` and `procedures.include` / `procedures.exclude`.
4. Re-run dry run. Iterate.
5. Only run live `trim` when the dry-run report matches intent.

### Keep base minimal; push variability into features

The base should describe the common spine. Features express optional behavior. A base that requires every feature JSON to function is a smell.

### Validate before trim, every time

`chopper validate` is cheap (seconds) and catches:

- Schema violations
- Missing files
- Unknown procs referenced in `procedures.include`
- Broken `depends_on` graphs
- `domain` field mismatches

Add it to your workflow:

```powershell
chopper validate --project configs/project_abc.json ; if ($LASTEXITCODE -eq 0) { chopper trim --project configs/project_abc.json }
```

### Review `dependency_graph.json` before shipping

Open `.chopper/dependency_graph.json` and search for `TW-01`/`TW-02`/`TW-03`. Every one is a place where Chopper couldn't prove a dependency. Decide — include explicitly or accept.

### Commit JSONs, not the trimmed domain (ideally)

If your branch strategy allows, commit only the authoring JSONs + `.chopper/trim_report.json`. Teammates can reproduce your trim exactly from those inputs.

### Use `--strict` in CI

Warnings in CI should fail the build. They always indicate something worth reviewing.

---

## 7. Easy Hacks

### Fast "what if?" iteration

```text
chopper trim --dry-run --base jsons/base.json
cat .chopper/trim_report.txt
```

No domain content files are touched. Only `.chopper/` is refreshed. Compare before/after states of a JSON edit by running this twice with a diff.

### List exactly what survived

```powershell
python -c "import json; m = json.load(open('.chopper/compiled_manifest.json')); [print(f['path'], f['treatment']) for f in m['files']]"
```

### Find why a proc was excluded

Search `trim_report.json` for the proc name. The `reason` field tells you whether it was never included, PE'd, or not reached.

### Prove a feature is doing something

Trim with and without the feature; diff the two `compiled_manifest.json` outputs. Anything different is the feature's real contribution (separate from `flow_actions`).

### Prevent accidental re-trim

Before handing a trimmed domain to the release manager, run:

```text
chopper cleanup --confirm
```

This deletes `<domain>_backup/` so a future `chopper trim` exits with `VE-21` instead of silently rebuilding.

### Reset to pristine state manually

If a run leaves things in a weird state:

```powershell
Remove-Item -Recurse -Force my_domain
Rename-Item my_domain_backup my_domain
```

This restores the pre-Chopper state in one step. The next `chopper trim` invocation is treated as a first trim.

---

## 8. FAQ

### Why did my feature's `files.exclude` do nothing?

Another source is including that file. Feature excludes cannot remove base-included content. Look for `VW-19` in the diagnostics.

### Why did my proc survive even though I excluded it?

Either it appears in another source's `procedures.include`, or it lives in a file another source is including whole. Look for `VW-18`.

### Why is my traced callee not in the output?

Tracing is reporting-only. Add it explicitly to `procedures.include`, or include the whole file. See [section 3](#3-what-tracing-really-does).

### Can I trim across domains?

No. Cross-domain trimming is out of scope (`OOS` policy). Each domain owner trims their own domain independently.

### Can I auto-generate a JSON from my existing flow?

No. "Scan mode" and draft-JSON generation were evaluated and rejected (`OOS-04`). The `--dry-run` feedback loop is the authoring tool — iterate on it.

### What exactly does `--dry-run` skip?

It skips domain rebuild work only. Chopper still loads JSONs, parses Tcl, compiles selections, runs the trace phase, runs manifest-only post-validation, and writes `.chopper/` reports. It does not rename `<domain>/`, rewrite files, remove files, or emit generated `<stage>.tcl` files into the domain.

### Can I preserve manual edits to `<domain>/` across re-trims?

No. Re-trim is deliberately destructive. Either move the edit into source files under `<domain>_backup/`, or apply it post-trim outside Chopper's workflow.

### Does Chopper run in parallel?

No. Chopper is single-threaded and deterministic. Runtime of 3–5 minutes per domain is acceptable. Parallelism was deferred (`FD-09`) because correctness matters more than speed at this scale.

### What Python version do I need?

3.11 or later. The default venv uses 3.13.

### What happens if Chopper crashes mid-trim?

`<domain>_backup/` is untouched. The next invocation sees both directories, classifies as "re-trim", and rebuilds cleanly from backup. You can also reset manually (see [section 7](#7-easy-hacks)).

### Can I use Chopper on non-EDA Tcl code?

Yes. Chopper has no EDA-specific dependencies at its core; the parser handles standard Tcl constructs (`proc`, `namespace eval`, `source`, control flow). EDA-specific suppression filters (`iproc_msg`, `define_proc_attributes`, `foreach_in_collection`) are conservative — they won't break on generic Tcl.

### Where do I file a bug?

Include:

1. The full command that was run
2. Your JSON(s) (redact secrets)
3. `.chopper/chopper_run.json`
4. `.chopper/diagnostics.json`
5. `.chopper/compiled_manifest.json` if it exists

---

---

## 🔗 See Also

| 📖 Resource | Purpose |
| --- | --- |
| [USER_MANUAL.md](USER_MANUAL.md) | CLI reference and installation |
| [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md) | Architecture and module layout |
| [../json_kit/examples/](../json_kit/examples/) | 11 progressive worked examples |
| [../technical_docs/DIAGNOSTIC_CODES.md](../technical_docs/DIAGNOSTIC_CODES.md) | Full diagnostic registry |
