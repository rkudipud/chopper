# 01 — Chopper Overview

> **Audience:** anyone who just finished the onboarding deck and wants the full picture before touching the CLI.
> **Goal:** by the end you can describe what Chopper does, what F1/F2/F3 mean, what JSON you need, and the rules that govern every trim.

---

## 1. The problem

A typical VLSI EDA tool-flow **domain** is a directory of Tcl, Perl, Python, csh, and config files that has accreted over years to support every project, every block, every methodology, every vendor tool the team has ever needed. A single project usually needs only a small slice of it.

Today, teams cope by:

- **Hand-editing** the domain on a project branch — fast to start, painful to maintain, impossible to audit.
- **Forking** the domain per project — explodes in count, drifts immediately, doubles the maintenance load.
- **Conditional flags inside Tcl** (`if {$project eq "abc"} { ... }`) — embeds project knowledge in the wrong place, makes the domain harder to read for everyone.

All three approaches fail the same way: there is no machine-checkable record of *which files, which procs, which run-script stages a given project actually depends on*. When something breaks two months later, nobody can say why a particular helper was kept or dropped.

---

## 2. The solution

**Chopper is a static, additive trimmer.** You write JSON that declares the slice of the domain a project needs. Chopper parses your domain, compiles your JSON into per-file and per-proc decisions, traces the call graph for visibility, rebuilds the trimmed domain on disk, optionally generates run scripts, and writes a complete audit bundle.

```text
        +------------------+
JSONs  >|                  |>  trimmed domain/
Tcl    >|     chopper      |>  generated run scripts
        |                  |>  .chopper/ audit bundle
        +------------------+
```

The output is **deterministic** (same inputs → byte-identical output) and **reproducible** (commit the JSON; anyone can rebuild the slice). The `.chopper/` bundle records every decision, every diagnostic, and every trace edge so a reviewer can answer *"why did this survive?"* without rerunning the tool.

### Conceptual relative

Chopper is closest in spirit to **Flow Builder**: both derive a specialised flow from a fully feature-rich domain. The distinction:

| | Flow Builder | Chopper |
|---|---|---|
| File-based flows | Yes | Yes (**F1**) |
| Proc-based flows | No | **Yes (F2)** |
| Run-file generation from JSON stages | Yes | **Yes (F3)** |
| Proc-level call-graph trace | No | Yes (reporting) |

The "Chopper" name suggests aggressive deletion. In practice it is a *declarative subset selector* — closer to a build system than to a chainsaw.

---

## 3. The three capabilities — F1, F2, F3

Every trim runs through the same pipeline. Capabilities are orthogonal: use one, two, or all three.

### F1 — File trimming

Keep or drop entire files (`.tcl`, `.pl`, `.py`, `.csh`, configs, binaries) by literal path or glob.

```json
{
  "files": {
    "include": ["setup.tcl", "procs/**/*.tcl"],
    "exclude": ["procs/legacy/**"]
  }
}
```

- Globs accepted: `*` (one segment), `?` (one char), `**` (any depth).
- Non-Tcl files are treated as opaque byte streams — copied verbatim, never decoded.
- `files.exclude` prunes glob expansions but **never** literal includes.

### F2 — Proc trimming

Keep or drop individual Tcl procedures inside a file, leaving the rest of the file intact.

```json
{
  "procedures": {
    "include": [{"file": "procs/core.tcl", "procs": ["foo", "bar"]}],
    "exclude": [{"file": "procs/shared.tcl", "procs": ["debug_dump"]}]
  }
}
```

- Proc entries require **exact** file paths and proc names — no glob patterns.
- The chosen file becomes a `PROC_TRIM` output: kept procs survive, the rest are removed; comments and surrounding code stay.
- Empty `procs: []` is an authoring error (`VE-03`).

### F3 — Run-file generation

Emit `<stage>.tcl` run scripts (and optional `<stage>.stack` scheduler files) from JSON stage definitions, replacing hand-authored stack files.

```json
{
  "stages": [{
    "name": "main",
    "command": "-xt vw Imy_shell -B BLOCK -T main",
    "exit_codes": [0],
    "dependencies": [],
    "steps": ["source setup.tcl", "run_setup", "load_design"]
  }],
  "options": { "generate_stack": true }
}
```

- One `<stage>.tcl` is emitted per resolved stage. With `generate_stack: true`, Chopper also emits `<stage>.stack` using the N/J/L/D/I/O/R format.
- Stage step references (procs, sourced files) are validated post-trim — broken refs become `VW-*` warnings.
- Features can extend stages with `flow_actions` (`add_stage_after`, `replace_steps`, etc.). Feature **order** matters here.

---

## 4. JSON inputs — base, feature, project

Chopper uses **two or three** JSON files. Base and feature JSONs live inside the domain. The project JSON is optional and can live anywhere.

| JSON | Location | Required? | Purpose |
|---|---|---|---|
| **`base.json`** | `<domain>/jsons/base.json` | Yes | Universal files / procs / stages every project in this domain needs |
| **Feature JSON** (0..N) | `<domain>/jsons/features/<name>.feature.json` | No | Adds files / procs / stage modifications for one optional capability |
| **`project.json`** | Anywhere — domain, configs/, team repo | No | A named recipe: one base path + ordered list of feature paths |

You **do not need** a project JSON to use features — pass `--base` and `--features` directly. The project JSON is a way to *commit* a named combination so a single `--project` flag invokes it.

### Directory layouts

**Base only** (simplest case):

```text
<domain>/
└── jsons/
    └── base.json
```

**Base + features**, no project file:

```text
<domain>/
└── jsons/
    ├── base.json
    └── features/
        ├── dft.feature.json
        └── scan_eco.feature.json
```

**Base + features + project recipe**:

```text
<domain>/
├── jsons/
│   ├── base.json
│   └── features/
│       ├── dft.feature.json
│       └── scan_eco.feature.json
└── project.json     ← names base + [dft, scan_eco]
```

The project JSON can also sit outside the domain (a shared `configs/` dir, a release repo). It just stores paths.

### Minimum viable JSON

```json
{
  "$schema": "base-v1",
  "domain": "my_domain",
  "files": {
    "include": ["setup.tcl", "procs/**/*.tcl"]
  }
}
```

That is enough. The full field reference lives in [../technical_docs/JSON_AUTHORING_GUIDE.md](../technical_docs/JSON_AUTHORING_GUIDE.md). Worked patterns for every common intent are in §6 below.

### `$schema` IDs

Always one of: `"base-v1"`, `"feature-v1"`, `"project-v1"`. These are short identifiers Chopper resolves against the bundled `schemas/` directory — they are **not** filesystem paths and stay valid regardless of where the repo is checked out.

---

## 5. The rules that govern everything

> **Three rules. Memorise these. Every result follows from them.**

1. **Default is exclude.** If no JSON keeps a file, it is removed. There is no "keep everything unless I say otherwise" mode.
2. **Explicit include always wins.** If any JSON says "keep `foo.tcl`", nothing else can remove it. Features cannot override base inclusions.
3. **Tracing is reporting-only.** The call-graph trace produces `dependency_graph.json` and `TW-*` warnings so you understand coupling. It **never auto-copies** procs into the output — only procs you listed explicitly survive.

### Cross-source aggregation (when JSONs disagree)

A **source** is one JSON file: the base, or any one selected feature. The project JSON is *not* a source — it is a list of sources.

| Situation | Result |
|---|---|
| Any source says "whole file" (`files.include`) | File survives as `FULL_COPY`. All procs kept. |
| No whole-file signal, some source has proc includes | File survives as `PROC_TRIM`. Surviving procs = union of every source's kept set. |
| No source includes anything for the file | File is removed (or `GENERATED` if it is an F3 stage output). |

### Veto warnings (when features try to remove base content)

Features are **additive only**. A feature's exclude cannot remove what another source included. When it tries, Chopper still trims correctly and warns you:

| Code | When it fires |
|---|---|
| `VW-18` cross-source-pe-vetoed | Feature excludes proc `p`, but another source includes the file whole or lists `p` |
| `VW-19` cross-source-fe-vetoed | Feature excludes file `F`, but another source includes `F` |

These are warnings, not errors. Run with `--strict` if CI should fail on them.

### Same-source authoring conflicts

| Code | Meaning | Fix |
|---|---|---|
| `VW-09` fi-pi-overlap | Same JSON has both `files.include` and `procedures.include` for the same file | Drop the PI — FI alone keeps everything |
| `VW-11` fe-pe-same-source-conflict | Same JSON has `files.exclude` and `procedures.exclude` for the same file, no `files.include` | Pick one |
| `VW-12` pi-pe-same-file | Same JSON includes and excludes procs in the same file | PI wins, PE ignored |
| `VW-13` pe-removes-all-procs | The PE set covers every proc in the file | File survives as comment-only — consider `files.exclude` |

---

## 6. JSON patterns by intent

| You want to... | Snippet |
|---|---|
| Keep a directory tree of Tcl files | `{"files": {"include": ["procs/**/*.tcl"]}}` |
| Keep everything except legacy | `{"files": {"include": ["**/*.tcl"], "exclude": ["procs/legacy/**"]}}` |
| Keep a file, drop a few procs | `{"files": {"include": ["procs/shared.tcl"]}, "procedures": {"exclude": [{"file": "procs/shared.tcl", "procs": ["debug_dump"]}]}}` |
| Keep only a few procs from a big file | `{"procedures": {"include": [{"file": "procs/core.tcl", "procs": ["run_setup"]}]}}` (do **not** also list the file in `files.include` — emits `VW-09`) |
| Layer a feature on top of base | Feature JSON with its own `files.include` / `procedures.include` / `flow_actions`, selected via `--features` or in `project.json`'s `features` array |
| Express feature dependency | `{"$schema": "feature-v1", "name": "scan_eco", "depends_on": ["dft"]}` |

For each pattern, copy from the matching folder in [../examples/](../examples/) — see the example map at the end of this document.

---

## 7. Optional switches inside JSON

| Field | Where | Default | Effect |
|---|---|---|---|
| `options.generate_stack` | `base.json` | `false` | When `stages` are defined, emit `<stage>.stack` alongside `<stage>.tcl` |
| `depends_on` | feature JSON | `[]` | Topologically order this feature after the named features |
| `flow_actions` | feature JSON | none | Append/insert/replace stage entries from the base or earlier features |

CLI-side switches (covered in [02_CLI_GUIDE.md](02_CLI_GUIDE.md)):

| Flag | Purpose |
|---|---|
| `--strict` | Promote any warning to a non-zero exit code (severities themselves stay unchanged) |
| `--dry-run` | Run the analysis under `trim` but skip the filesystem rebuild |
| `--plain` | Disable Rich live rendering and ANSI colour |
| `-v` / `-vv` / `-q` | Verbosity controls |
| `--tool-commands <path>` | Add a vendor tool-command file to silence `TW-02` noise via `TI-01` |

---

## 8. Best Known Methods (BKMs)

1. **Author top-down.** Start with broad `files.include` globs. Run `chopper trim --dry-run`. Read `trim_report.txt`. Narrow with `files.exclude` and proc-level entries. Re-run dry. Iterate. Live-trim only when dry-run matches intent.
2. **Keep base minimal; push variability into features.** A base that needs every feature JSON to function is a smell.
3. **Validate before trim, every time.** `chopper validate` is cheap (seconds) and catches schema, missing-file, unknown-proc, broken `depends_on`, and domain-mismatch problems before you touch disk.
4. **Review `dependency_graph.json` before shipping.** Every `TW-01`/`TW-02`/`TW-03` is a place Chopper could not prove a dependency. Decide consciously: include explicitly or accept.
5. **Commit JSONs, not the trimmed domain.** Teammates can reproduce your trim exactly from the JSONs alone — and `.chopper/trim_report.json` for cross-checking.
6. **Use `--strict` in CI.** Warnings in CI should fail the build; they always indicate something worth a human glance.
7. **Use a tool-command pool.** For PrimeTime / vendor-heavy domains, pass `--tool-commands` so vendor commands surface as `TI-01` (info, exit 0) rather than `TW-02` (warning) — keeps the diagnostic stream signal-rich.

---

## 9. Caveats — read before you author

- **The filesystem must be quiesced during a run.** No locks, no mtime polling. If something else mutates `<domain>/` or `<domain>_backup/` mid-run, behaviour is undefined.
- **Re-trim is destructive.** Every re-trim discards `<domain>/` and rebuilds from `<domain>_backup/`. **Hand-edits to the trimmed domain are lost.** Move edits into source files under the backup, or commit the trimmed output to git and re-apply post-trim.
- **Tracing is bounded to the domain path.** Calls to procs defined outside the selected domain are treated as external (the `TW-02` family), not followed.
- **Dynamic Tcl is not resolved.** `${prefix}_helper`, `eval "..."`, `uplevel`, `$cmd $args` emit `PW-01` / `TW-03` and are not followed. If your domain relies on dynamic dispatch, list the targets explicitly.
- **Globs only apply to `files.*`.** Proc entries require exact file paths and proc names.
- **`domain` field must match the cwd basename** (case-insensitive). Mismatch → `VE-17`.
- **Non-Tcl files are file-level only.** No subroutine-level trimming for Perl/Python/shell. This is a permanent design decision (`OOS-01`).
- **`--strict` is exit-code policy only.** It never rewrites `Diagnostic.severity`.

---

## 10. Roles and ownership

| Role | Owns |
|---|---|
| **Domain owner** | The domain itself, `base.json`, the catalogue of feature JSONs, and the BKMs for trimming it |
| **Project lead** | The project's `project.json` (or the base+features combination), and the validated `.chopper/` audit bundle for each release |
| **Release engineer** | Cleanup window — running `chopper cleanup --confirm` once the team agrees the trim window is closed |
| **Tool maintainer** | Chopper itself — schemas, parser, pipeline, diagnostics |

If you are reading this because you inherited a domain you did not author, the [Chopper Agent](../.github/agents/chopper-agent.agent.md) can run a **Q1–Q5 discovery protocol** that produces starter JSON from a cold scan.

---

## 11. Worked examples — pick the closest one

Copy the nearest example into your domain root, replace placeholders, validate, then trim.

| Need | Folder |
|---|---|
| File trimming only | [../examples/01_base_files_only/](../examples/01_base_files_only/) |
| Proc trimming only | [../examples/02_base_procs_only/](../examples/02_base_procs_only/) |
| Generated run scripts only | [../examples/03_base_stages_only/](../examples/03_base_stages_only/) |
| Files + procs | [../examples/04_base_files_and_procs/](../examples/04_base_files_and_procs/) |
| Files + stages | [../examples/05_base_files_and_stages/](../examples/05_base_files_and_stages/) |
| Procs + stages | [../examples/06_base_procs_and_stages/](../examples/06_base_procs_and_stages/) |
| Full base — files + procs + stages | [../examples/07_base_full/](../examples/07_base_full/) |
| Base + one feature | [../examples/08_base_plus_one_feature/](../examples/08_base_plus_one_feature/) |
| Base + multiple features | [../examples/09_base_plus_multiple_features/](../examples/09_base_plus_multiple_features/) |
| Feature dependency chain | [../examples/10_chained_features_depends_on/](../examples/10_chained_features_depends_on/) |
| Project-mode without features | [../examples/11_project_base_only/](../examples/11_project_base_only/) |

---

## Next

Go to **[02_CLI_GUIDE.md](02_CLI_GUIDE.md)** to actually run Chopper.
