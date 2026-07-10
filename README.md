# Chopper

![Status](https://img.shields.io/badge/status-ready-0a7a3d)
![Python](https://img.shields.io/badge/python-3.13%2B-3776ab)
![License](https://img.shields.io/badge/license-Intel%20Proprietary-555555)
![Pipeline](https://img.shields.io/badge/pipeline-P0--P7-8a3ffc)

[![Chopper Agent](https://img.shields.io/badge/🤖_Agent-Chopper_Agent-0f62fe)](.github/agents/chopper-agent.agent.md)
[![Onboarding Presentation](https://img.shields.io/badge/📊_Onboarding-Presentation-8a3ffc)](https://rkudipud.github.io/chopper/)

**Chopper is a Python CLI that surgically trims VLSI EDA tool-flow domains down to exactly what a project actually needs** — specified by JSON, reproducible on every run, and audited automatically after every trim.

Instead of editing Tcl by hand and hoping you caught every dependency, you write JSON to say which files, which procedures, and which run-script stages survive. Chopper parses your domain, compiles your selections, traces the call graph for visibility, trims the domain on disk, generates run scripts if needed, and writes a full audit bundle for review.

> 📊 **New here?** Start with the [**onboarding presentation**](https://rkudipud.github.io/chopper/) — a 16-slide walk-through of what Chopper is, the F1/F2/F3 capabilities, the P0–P7 pipeline, and the JSON authoring surface. Source: [presentation/chopper_onboarding.html](presentation/chopper_onboarding.html).


---

## 🤖 Meet the Companion

You do not have to figure out domain boundaries or JSON structure by hand. A purpose-built agent ships in-repo for VS Code Copilot Chat.

### Chopper Agent

![Chopper Agent](https://img.shields.io/badge/VS%20Code%20Agent-Chopper%20Agent-0f62fe)

The **Chopper Agent** ([.github/agents/chopper-agent.agent.md](.github/agents/chopper-agent.agent.md)) is the **single user-facing agent** for anything Chopper-related — from a convoluted Tcl codebase all the way to a validated, trimmed output. It absorbs the former Domain Analyzer.

**What it does:**

- Runs the **Q1–Q5 discovery protocol** on an unfamiliar codebase (domain root, stack files, scripts, configs, utility dirs)
- Authors `base.json`, `*.feature.json`, and `project.json` from your domain
- Runs `chopper validate` and `chopper trim --dry-run` and explains the results
- Reads `.chopper/` audit artifacts (manifests, trace graphs, diagnostics) and tells you what to fix
- Explains any diagnostic code against [technical_docs/DIAGNOSTIC_CODES.md](technical_docs/DIAGNOSTIC_CODES.md)
- Runs named CLI playbooks: **bisect** a feature that broke trim, **compare** two runs, **prove-safe** a JSON change
- Works in two modes: **analyze-only** (JSON authoring, no CLI calls) or **full-loop** (analyze + run + audit)

**Prompt library** — ready-to-use starting points under [.github/prompts/](.github/prompts/): `bootstrap-domain`, `explain-last-run`, `why-was-dropped`, `validate-my-jsons`, `bisect-feature-breakage`, `report-chopper-bug`, `package-bug-artifacts`.

> [!TIP]
> Open VS Code Copilot Chat, pick the Chopper Agent, and say: *"bootstrap a starter JSON for my domain at `path/to/domain/`"* — or just *"hi"* and it will show you a two-tier menu of everything it can do.

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

Chopper uses two or three JSON files. **Base and feature JSONs live inside your domain. The project JSON is optional and can live anywhere.**

| JSON | Where it lives | Required? | Purpose |
| --- | --- | --- | --- |
| **`base.json`** | `<domain>/jsons/base.json` | Yes | Universal files, procs, and stages every project in this domain needs |
| **Feature JSON** (zero or more) | `<domain>/jsons/features/<name>.feature.json` | No | Adds files, procs, or stage modifications for one optional capability |
| **`project.json`** | Anywhere — inside the domain, in a shared configs dir, wherever | No | A named recipe: records one base path + an ordered list of feature paths so you can commit a specific combination and invoke it with a single `--project` flag |

You **do not need a project JSON** to use features. Pass `--base` and `--features` directly on the command line. The project JSON is simply a way to commit a named combination.

#### Invocation modes

```text
# Mode 1 — Base only (most common starting point)
chopper validate --base jsons/base.json

# Mode 2 — Base + features directly (no project file required)
chopper validate --base jsons/base.json \
    --features jsons/features/feature_a.feature.json,jsons/features/feature_b.feature.json

# Mode 2b — Validate every feature JSON in a directory at once
# (validate only; trim/--project still require explicit per-file paths)
chopper validate --base jsons/base.json --features jsons/features/

# Mode 3 — Project recipe (single flag for a committed base + feature combination)
chopper validate --project project.json
```

#### Directory layout

Base-only (simplest):

```text
<domain_root>/
└── jsons/
    └── base.json                          ← universal files/procs/stages
```

Base + feature JSONs (Mode 2 — no project file needed):

```text
<domain_root>/
└── jsons/
    ├── base.json
    └── features/
        ├── feature_a.feature.json         ← optional capability layer A
        └── feature_b.feature.json         ← optional capability layer B
```

Base + feature JSONs + project recipe (Mode 3):

```text
<domain_root>/
├── jsons/
│   ├── base.json
│   └── features/
│       ├── feature_a.feature.json
│       └── feature_b.feature.json
└── project.json                           ← optional recipe: names base + [feature_a, feature_b]
```

The project JSON can also sit outside the domain — in a separate `configs/` directory or a team repository. It just holds paths to the base and feature JSONs.

#### Worked examples in `examples/`

| Example folder | What it shows |
| --- | --- |
| `01_base_files_only/` | Base with file trimming only |
| `02_base_procs_only/` | Base with proc trimming only |
| `03_base_stages_only/` | Base with stage JSON for run-file generation |
| `07_base_full/` | Full base — files, procs, and stages |
| `08_base_plus_one_feature/` | Base + one feature JSON (includes a `project.json`) |
| `09_base_plus_multiple_features/` | Base + two independent features |
| `10_chained_features_depends_on/` | Features with `depends_on` ordering |
| `11_project_base_only/` | Project file referencing base only (no features) |
| `14_cross_feature_skip_if_no_stage/` | Cross-cutting feature injecting steps into stages other features create, using `skip_if_no_stage` |

Copy the nearest example into your domain root, replace every placeholder, then validate with `python schemas/scripts/validate_jsons.py <domain_root>/`. Full field reference is in [technical_docs/JSON_AUTHORING_GUIDE.md](technical_docs/JSON_AUTHORING_GUIDE.md).

Use the **Chopper Agent** ([.github/agents/chopper-agent.agent.md](.github/agents/chopper-agent.agent.md)) to generate JSONs from your codebase, or adapt from the examples above. The schemas in `schemas/` enforce correctness.

#### Include/exclude behavior quick-reference

| Author intent | JSON shape | Result |
| --- | --- | --- |
| Keep only listed files | `files.include: ["a.tcl"]` | `a.tcl` survives; unnamed files are removed. |
| Keep all files except a list | `files.include: ["**"]`, `files.exclude: [...]` | Chopper starts from every file under the domain, then removes paths matched by `files.exclude`. |
| Exclude-only file list | `files.exclude: [...]` | No file-level keep signal exists; under default-exclude, live trim can rebuild an almost empty domain. Add `files.include: ["**"]` for a negative-list trim. |
| Literal include plus matching exclude | `files.include: ["debug_old.tcl"]`, `files.exclude: ["debug*.tcl"]` | `debug_old.tcl` survives; literal include wins. |
| Glob include plus matching exclude | `files.include: ["*.tcl"]`, `files.exclude: ["debug*.tcl"]` | The glob-expanded include list is pruned; `debug*.tcl` matches are removed from that list. |
| Keep only certain procs | `procedures.include` | File becomes `PROC_TRIM`; only listed procs survive. |
| Keep file minus some procs | `procedures.exclude` | File becomes `PROC_TRIM`; all parsed procs except excluded procs survive. |
| File exclude plus proc exclude on the same file | `files.exclude` + `procedures.exclude` | Same-source contradiction; the source contributes nothing and emits `VW-11`. |
| Feature tries to remove a base file | Base includes file, a later feature excludes file | Feature is the later layer under R1 ordered overlay; the file is removed and `VW-21 layer-shadowed` records the transition. |

### Step 3 — Validate first, always

```text
# Base only
chopper validate --base jsons/base.json

# Base + features (no project file required)
chopper validate --base jsons/base.json \
    --features jsons/features/feature_a.feature.json

# Project recipe
chopper validate --project project.json
```

Validation is fully read-only. It parses Tcl, compiles selections, runs trace, checks the call graph, and reports every issue — without touching the domain on disk.

### Step 4 — Dry-run before you trim

```text
# Base only
chopper trim --dry-run --base jsons/base.json

# Base + features
chopper trim --dry-run --base jsons/base.json \
    --features jsons/features/feature_a.feature.json

# Project recipe
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

The bundle is designed to be machine-readable. The `run-result-v1.schema.json` and `diagnostic-v1.schema.json` schemas in `schemas/` document the format.

---

## Documentation

All end-user documentation lives under [user_docs/](user_docs/) — a consolidated three-part guide designed to take you from the onboarding deck to a working trim in 60–90 minutes.

| Who You Are | Where to Start |
| --- | --- |
| Anyone new to Chopper | [user_docs/](user_docs/) — start here |
| Just want the thesis | [user_docs/01_OVERVIEW.md](user_docs/01_OVERVIEW.md) — problem, solution, F1/F2/F3, JSON, BKMs, ownership |
| About to run the CLI | [user_docs/02_CLI_GUIDE.md](user_docs/02_CLI_GUIDE.md) — every subcommand, every flag, deep examples |
| Want to understand the pipeline | [user_docs/03_HOW_CHOPPER_WORKS.md](user_docs/03_HOW_CHOPPER_WORKS.md) — P0–P7, design rules, where Chopper fits, FAQ |
| JSON schemas and examples | [schemas/](schemas/) and [examples/](examples/) — authoritative schemas and 14 worked examples; see [technical_docs/JSON_AUTHORING_GUIDE.md](technical_docs/JSON_AUTHORING_GUIDE.md) |
| Authoritative specification | [technical_docs/ARCHITECTURE.md](technical_docs/ARCHITECTURE.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) — workflow, quality gates, scope rules |

---

## Reporting Issues

Found a bug? [Open a bug report](../../issues/new?template=bug_report.yml) on GitHub. The form guides you through providing everything needed to reproduce the problem quickly.

If you are in VS Code, ask the Chopper Agent to `report-chopper-bug`. It now packages local evidence, renders the GitHub issue body, and files the issue automatically when `gh` is installed and authenticated. If that step fails, it falls back to the simple local behavior automatically and leaves you with the ready-to-submit issue body and bundle paths.

**What to include:**

| What | How |
| --- | --- |
| Full terminal output | Run `chopper <command> 2>&1 \| tee chopper.log` and attach the log file |
| `.chopper/` audit bundle | Zip the `.chopper/` folder and drag it into the issue form — it contains `diagnostics.json`, `chopper_run.json`, and `trim_report.txt` |
| JSON configuration | Paste a minimal reproduction of your `base.json`, feature JSON, or `project.json` (remove sensitive paths) |
| Screenshots | Drag and drop PNG/JPG/GIF directly into any GitHub text field |

**From VS Code on Unix:** package local evidence first with `python schemas/scripts/package_bug_report.py /abs/path/to/.chopper /abs/path/to/report.md`, or ask the companion to run `report-chopper-bug` and it will package the paths plus file the GitHub issue automatically when host GitHub auth is available. If that create step fails, it falls back to local output automatically. Raw zip upload still uses the GitHub attachment UI.

> [!TIP]
> Run `chopper validate` before `chopper trim` — it often surfaces the root cause without modifying your domain. Attach the validate output alongside the trim output when both are relevant.

---

## CTH Ward Deployment

This section covers every step a release engineer needs to build a production-ready Chopper CTH package, install it into a ward, and verify it behaves correctly before submission to `eou_sandbox_pydev`.

### Prerequisites

- Active chopper dev venv (`source setup.csh` in the repo root creates `.venv`).
- A working CTH ward created with `cth_psetup`. The ward path is referred to as `$ward` below.

### Step 1 — Build the CTH release payload

Run from the **chopper repo root**:

```tcsh
cd /path/to/chopper
source setup.csh
make release-cth
```

This stages everything under `dist/chopper-cth/global/` and prints `chopper 4.0.0` as a smoke test. Review `dist/chopper-cth/RELEASE_CTH.txt` for a full layout description.

### Step 2 — Install into the ward (clean install)

`install-cth` **removes any previous Chopper installation** from the ward before copying the fresh build, so re-running it is always safe.

```tcsh
make install-cth WARD=/path/to/your/r2g.xxxx_dev
```

To avoid typing the full path each time, export the variable first:

```tcsh
setenv ward /nfs/site/disks/<disk>/global_dev/turn_in/r2g.1278_dev   # tcsh
make install-cth WARD=$ward
```

What this installs and removes:

| Action | Path under `$ward` |
|--------|-------------------|
| Removes previous source | `global/common/chopper/` (entire tree) |
| Removes previous launcher | `global/eouFW/bin/chopper` |
| Installs new source | `global/common/chopper/src/`, `schemas/`, `pyproject.toml` |
| Installs new launcher | `global/eouFW/bin/chopper` |

### Step 3 — Verify the installed CLI

Enter a CTH shell and confirm the installed binary works:

```tcsh
# Enter the CTH shell (adjust project / cfg / tech as needed)
setenv CTH_DISABLE_VSCODE 1
/p/hdk/bin/cth_psetup -proj pesg/2026.06.plus -cfg 78p6_i0m_opt17.cth \
    -x '$SETUP_R2G -w r2g.1278_dev -t eou_dev_1278 -tech 1278.6'

# Inside the CTH shell:
rehash
which chopper          # should resolve to $ward/global/eouFW/bin/chopper
chopper --version      # should print: chopper 4.0.0
```

Optionally run a quick validate against a real domain:

```tcsh
cd $ward/global/snps/fev_formality
chopper validate --domain . --base jsons/base.json --features jsons/features
```

Exit 0 with no errors confirms the installed package is functional.

### Step 4 — Run the pytest suite from the ward

From the **chopper repo root** (not the CTH shell), run:

```tcsh
make test-cth-ward WARD=$ward
```

This target:
1. Copies the test suite into the ward package temporarily.
2. Runs pytest with `--cov=src/chopper` pointed at the ward-installed source.
3. Removes the temporary test tree after the run.

Tests in `tests/unit/scripts/` are skipped because `schemas/scripts` is a developer-only set and is not shipped in the CTH bundle. All other tests must pass and coverage must reach the configured threshold.

Expected output on a clean install:

```text
[1/3] Copying test suite into ward Chopper package (temporary)...
[2/3] Running pytest against ward-installed Chopper source...
...
Required test coverage of 99% reached. Total coverage: 99.XX%
14XX passed in XX.XXs
[3/3] Cleaned up test artifacts from ward.
```

If anything fails, fix the root cause in the repo, rebuild with `make release-cth`, reinstall with `make install-cth WARD=...`, and rerun `make test-cth-ward WARD=...`.

### Step 5 — Stage the Perforce changes (edit / add / delete)

`install-cth` only touches the filesystem (`rm -rf` + `rsync`) — it never talks to `p4`. After installing, the ward's working files reflect the new release, but nothing is opened in Perforce yet. Two targets bridge that gap, both scoped to exactly `global/common/chopper/...` and `global/eouFW/bin/chopper`:

```tcsh
# Preview only -- opens nothing, safe to run any time after install-cth.
# Diffs the ward's working files against the depot have-revision (via
# `p4 reconcile -n`) and writes a plain p4 edit/add/delete command list.
make p4-plan-cth WARD=$ward
```

This prints (and writes to `dist/chopper-cth/p4_plan_cth.txt`) one line per file that changed, e.g.:

```text
p4 edit //depot/.../pyproject.toml
p4 edit //depot/.../src/chopper/cli/render.py
p4 add  //depot/.../src/chopper/trimmer/p4_checkout.py
p4 delete //depot/.../src/chopper/some_removed_module.py
```

Review the plan. `p4 reconcile` classifies every path correctly on its own — modified files become `edit`, new files become `add`, files present in the depot but no longer on disk (removed in this release) become `delete`. Once it matches your expectations:

```tcsh
# Actually opens the files (add/edit/delete) in a pending changelist.
# Reversible via 'p4 revert' -- never runs 'p4 submit'.
make p4-open-cth WARD=$ward
```

Review the pending changelist (`cd $ward && p4 opened`), then submit manually when ready:

```tcsh
cd $ward && p4 submit -d "chopper $(grep -E '^version' pyproject.toml | head -1 | cut -d'"' -f2) ward deploy"
```

> **Why copy-then-reconcile is correct here (and different from Chopper's own `--p4` trim flag):** `install-cth` fully deletes and recreates `global/common/chopper/`, so it never edits a synced (possibly read-only) file in place — there is nothing to "check out before overwriting." `p4 reconcile` is Perforce's native tool for exactly this scenario: diff the working tree against the depot *after* a build system has already regenerated it, and open files accordingly. This is the opposite of the checkout-before-edit ordering Chopper's own `chopper trim --p4` flag needs (see ARCHITECTURE.md §5.5.18) — that flag rewrites files itself, in place, inside a live domain still tracked at the same path, so it must open them before rewriting. The ward deploy process here never edits in place, so there is no equivalent risk to guard against.

### Step 6 — Production deployment

Once the P4 changelist is staged and reviewed:

1. Merge `dist/chopper-cth/requirements.chopper.txt` entries into the py-flow `requirements.txt` for the `eou_sandbox_pydev` venv.
2. Submit the ward changelist (see Step 5) to `eou_sandbox_pydev`.
3. On a flow host after the submit, run `rehash; chopper --version` as a final sanity check.

---

### Running Chopper from the CTH ward

Within the CTH shell / ward, follow these commands:

```tcsh
# Refresh PATH so the installed binary is visible
rehash

# Confirm which chopper is active
which chopper

# Check the version
chopper --version

# Validate a domain (read-only, no disk changes)
chopper validate --domain /path/to/domain --base jsons/base.json --features jsons/features

# Report lines-of-code reduction before trimming
chopper loc --domain /path/to/domain --base jsons/base.json --features jsons/features

# Dry-run trim — simulate the full trim without writing anything
chopper trim --dry-run --domain /path/to/domain --base jsons/base.json \
    --features jsons/features/feature_a.feature.json,jsons/features/feature_b.feature.json

# Live trim — rebuilds the domain on disk; creates <domain>_backup/ automatically
chopper trim --domain /path/to/domain --base jsons/base.json \
    --features jsons/features/feature_a.feature.json,jsons/features/feature_b.feature.json

# Remove the backup after confirming the trim result
chopper cleanup --domain /path/to/domain --confirm
```

> **Tip:** `validate` and `loc` accept a directory for `--features` (e.g. `jsons/features`).
> `trim` requires a comma-separated list of feature JSON paths or a `--project` file.
> Run from the domain directory to omit `--domain`.

---

## Contributing

Contributor workflow, local quality gates, working rules, and the pull-request checklist live in [CONTRIBUTING.md](CONTRIBUTING.md). The short version: run `make check` before opening a pull request, and read the spec before adding anything new.

---

## Changelog

Major milestones only. The canonical release version number lives in [pyproject.toml](pyproject.toml) (`[project].version`) and is exposed at runtime via `chopper.__version__`.

### 4.4.3 — 2026-07-09

- **Fixed: `--p4` checkout succeeded but the "P4 Files Opened for Edit" summary never printed for domains with companion-file sync.** Root cause: P5c (Tcl indentation, opt-in) and P5d (companion-file sync, e.g. `default_config.<sfx>.csv` / `default_milestone.<sfx>.tcl`) both rebuild `TrimReport` from scratch when they have byte-count updates to apply, and neither carried forward `TrimReport.p4_checkout` (or `.inputs_preserved`) onto the new object — silently resetting it to `None` even though `p4 edit` had genuinely opened the files (confirmed via `p4 opened`). Any domain that triggers P5d (any `PROC_TRIM` `default_rules.<sfx>.tcl` with a synced companion CSV/milestone file, e.g. `fev_formality`) lost the checkout data before it reached the CLI layer, so the summary silently rendered nothing. Fixed both rebuild paths to preserve `p4_checkout` and `inputs_preserved`. See ARCHITECTURE.md §5.5.18, FR-53.

### 4.4.2 — 2026-07-09

- **New `--p4 enabled` stdout notice.** Immediately after each domain's run header (and before the pipeline starts), `chopper trim --p4` now prints a one-line notice confirming the flag is active for that domain: `--p4 enabled: files will be checked out via 'p4 edit' before rewriting.` Suppressed under `--dry-run` (checkout never runs there). Repeats once per domain in multi-domain CSV `--domain` runs, matching the existing per-domain header convention. See ARCHITECTURE.md §5.5.18, FR-53.

### 4.4.1 — 2026-07-09

- **`--p4` bug fixes: checkout now actually opens files for edit.** Real CTH-ward testing found 4.4.0's `--p4` was a no-op (`p4 opened` showed nothing after trim). Fixed two root causes: (1) checkout ran before the domain-to-backup rename, but Perforce couldn't track the opened-for-edit state across that OS-level rename — fixed by copying (not renaming) `domain/` to `domain_backup/` before checkout, then clearing `domain/` for the rebuild afterward; (2) some Perforce client/server combinations silently fail relative-path `p4 edit`/`p4 revert` from a subprocess (exit 0, no file opened) — fixed by using absolute paths and by treating an exit-0-with-empty-stdout response as a failure.
- **`--p4` now supports re-trims.** Previously any re-trim (`<domain>_backup/` already present) unconditionally skipped checkout with a "P4 EDIT NOT POSSIBLE" notice. Chopper now restores the relevant files from the existing backup to their depot-synced content first, then checks them out normally, so re-running `chopper trim --p4` on the same domain works as expected. Skips only when the domain directory itself is absent (no file to open).
- **New `=== P4 Files Opened for Edit ===` stdout summary.** After a successful `--p4` checkout, Chopper prints the absolute paths it opened for edit directly to stdout — the same information a user would otherwise get from running `p4 opened` manually. See ARCHITECTURE.md §5.5.18, FR-53.

### 4.4.0 — 2026-07-09

- **`--p4` checkout-before-edit.** New opt-in, `chopper trim`-only flag: runs `p4 edit -t text+x` on every `PROC_TRIM` / regenerate-in-place `GENERATED` file *before* rebuilding the domain, so a later `p4 submit` doesn't fight Perforce's checkout-before-edit protocol. Only attempted on a genuine first trim; skipped with a red on-screen notice (not an error) when `p4` is unavailable, the domain isn't a working p4 client workspace, or this is a re-trim. Never active under `--dry-run`. On checkout failure the whole trim aborts (new `VE-37`) after reverting everything already checked out; a later failure after checkout succeeded additionally restores the domain from backup immediately. Chopper never runs `p4 add`, `p4 delete`, or `p4 submit` — only `p4 edit` and, on rollback, `p4 revert`. See ARCHITECTURE.md §5.5.18, FR-53.

### 4.3.0 — 2026-07-09

- **Standalone `files_exclude_p4.txt` audit artifact.** The `exclude_file_list` path set already written inside `p4_commands.txt` is now also emitted as its own file, `files_exclude_p4.txt`, so tooling that only needs the exclusion list doesn't have to parse it out of the Perforce command file. Byte-for-byte the same path set and `$ward`-relative-or-domain-relative formatting; both artifacts now share one `_compute_excluded_paths()` helper. Emitted on live trim and `--dry-run`; not by `validate`/`loc`/`cleanup`. See ARCHITECTURE.md §5.5.14, FR-51.
- **Audit bundle location message.** After `chopper trim` finishes processing every domain, Chopper now prints the resolved `.chopper/` audit bundle path to stdout, right after the P4 Branch Analysis summary — one line per domain under an `=== Audit Bundle Locations ===` banner for multi-domain CSV `--domain` runs. See ARCHITECTURE.md §5.5.17, FR-52.

### 4.2.1 — 2026-06-30

- **`files_removed.txt` now uses Ward-relative paths.** The removed-file audit artifact renders each path as `$ward`-relative when the domain resolves under `$ward` (falling back to domain-relative otherwise), matching the `exclude_file_list` section of `p4_commands.txt` introduced in 4.1.0. See ARCHITECTURE.md §14 revision history (4.2.1) and §3.7/§5.6.
- **Coverage gap closure (incidental).** Added unit tests for two pre-existing untested branches in `src/chopper/orchestrator/simulate.py` (a manifest-listed `.json` file missing from, or unreadable in, the source root during the `chopper loc` in-memory replay). No behavior change; both the fast (`make check`) and full (`make ci`) coverage gates are green again.
- Version bumped 4.2.0 → 4.2.1.

### 4.2.0 — 2026-06-30

- **Project-config auto-discovery.** When `--domain` resolves in name-mode and no explicit `--project`, `--base`, or `--features` is supplied, Chopper searches `$ward/project/<vendor>/<domain>/` for `<leaf>.project.json` (treated as `--project`) or `<leaf>.project.features.config` (plain-text feature list, one name per line — treated as `--features`). First match wins; discovery is silent when neither file is found. See ARCHITECTURE.md §5.1.3, FR-49.
- **Domain run header.** Before each domain's pipeline, Chopper prints a scannable header to stdout: domain label, domain root, base/project JSON path, auto-discovered config file path (for `.project.features.config` only), and numbered feature list. All lines are flushed immediately so they appear before stderr progress output. See ARCHITECTURE.md §5.5.16, FR-50.
- **New `RunConfig.project_config_path` field.** Stores the resolved `.project.features.config` path when auto-discovered; `None` otherwise.
- FR-49 and FR-50 added. Version bumped 4.1.0 → 4.2.0.

### 4.1.0 — 2026-06-17

- **Domain-name resolution via `$ward`.** `--domain` now accepts logical names (`fev_formality`, `snps/power`) resolved via `$ward/global/<vendor>/<name>`. Bare-name search finds unique vendor match automatically; ambiguous names require `vendor/name` notation (VE-34). Absolute paths bypass `$ward` for backward compat.
- **Base JSON auto-discovery.** When `--domain` provides a named domain and `--base` is not supplied, Chopper searches `<domain>/jsons/base.json` automatically (VE-35 if not found).
- **Feature-name lookup.** `--features` accepts feature names (e.g. `dft,power`) resolved from `<domain>/jsons/features/*.feature.json`, with close-match suggestions for typos (VE-36). Explicit file paths still accepted (backward compat).
- **Multi-domain sequential trim.** `--domain` accepts a CSV list for sequential multi-domain runs; final exit code is the maximum across all domains.
- **P4 branch analysis.** After every run, Chopper prints a P4 branch analysis: "NO BRANCH NEEDED" (pure removals — P4 template resync) vs "BRANCH NEEDED" (files modified or added). Multi-domain shows per-domain and aggregate verdicts.
- **`exclude_file_list` replaces `p4 delete`.** The `p4 delete` command section in `p4_commands.txt` is now an `exclude_file_list` section of bare `$ward`-relative paths for use in P4 client-spec exclusion mappings.
- **New diagnostics:** VE-32 (`ward-env-not-set`), VE-33 (`domain-not-found`), VE-34 (`ambiguous-domain-name`), VE-35 (`base-autodiscovery-failed`), VE-36 (`feature-name-not-found`). FR-48 added.
- Version bumped 4.0.0 → 4.1.0.

### 4.0.0 — 2026-06-05

- **MCP surface removed.** The stdio-only read-only Model Context Protocol server added in 0.4.0 is gone: the `chopper mcp-serve` subcommand, the `src/chopper/mcp/` package, the `mcp>=1.0,<2` runtime dependency, the `PE-04 mcp-protocol-error` diagnostic, and process exit code `4` are all removed. Chopper now ships **four** subcommands (`validate`, `trim`, `loc`, `cleanup`) and depends only on `jsonschema` at runtime.
- **Scope re-closed.** MCP returns to a closed decision — no read-only or destructive, stdio or networked surface may be reintroduced without explicit user approval and an architecture-doc-first cascade. `PE-04` is retired (slot preserved, never reused); the `RunResult` / `RunRecord` / `AuditManifest` exit-code surface and [schemas/run-result-v1.schema.json](schemas/run-result-v1.schema.json) narrow to `0/1/2/3`.
- **Docs cascaded.** [technical_docs/ARCHITECTURE.md](technical_docs/ARCHITECTURE.md) §3.9 retained as a closure record; ENGINEERING.md §7/§16 Q1, CLI_REFERENCE.md, DIAGNOSTIC_CODES.md (active codes 82 → 81), user docs, the scope-lock in [.github/instructions/project.instructions.md](.github/instructions/project.instructions.md), and the bundle/CTH Makefile targets all updated.
- Version bumped 3.5.1 → 4.0.0.

### 3.5.1 — 2026-05-23

- **100% coverage enforced on the full-suite gate.** The aggregate `test` target (run by `make ci`) now passes `--cov-fail-under=100`, locking the codebase at 100% line + branch coverage across every module — the full suite already reached every reachable line, so this prevents silent regressions. The fast unit-only gate (`make check`) keeps the pyproject default `--cov-fail-under=99`, since unit tests intentionally exercise only part of `src/` (integration/golden/property suites cover the rest). Stale Makefile comment (`78`) corrected. Coverage policy cascaded into [tests/TESTING_STRATEGY.md](tests/TESTING_STRATEGY.md), [technical_docs/ARCHITECTURE.md](technical_docs/ARCHITECTURE.md) §5.12.8, and the project instructions. No code or behavior change.
- **User-facing docs synced to the 14th example.** Example maps and counts updated for `examples/14_cross_feature_skip_if_no_stage/` (the canonical `skip_if_no_stage` demo) across [user_docs/01_OVERVIEW.md](user_docs/01_OVERVIEW.md), [user_docs/README.md](user_docs/README.md), [technical_docs/JSON_AUTHORING_GUIDE.md](technical_docs/JSON_AUTHORING_GUIDE.md), this README, and the Chopper Agent doc (stale "11 scenarios" → 14). Full `src/` was reviewed against the technical docs: no drift, no scope-lock violations.
- Version bumped 3.5.0 → 3.5.1.

### 3.5.0 — 2026-05-23

- **Optional flow-action stage targets (`skip_if_no_stage`).** Each entry in `flow_actions` now accepts an optional boolean `skip_if_no_stage` (default `false`). When `true` and the target stage is absent from the compiled stage sequence (typically because the partial project composition did not load it), the resolver emits new `VI-05 flow-action-skipped-no-stage` (info, exit 0) and skips the action silently instead of failing with `VE-05`. Step-level miss inside a present stage still emits `VE-05` — stage existence and step existence remain distinct contracts. Backward-compatible: omitting the field preserves the strict `VE-05` behaviour.
- **Use case.** Cross-cutting features (e.g. a `sequential_const_check` injecting a constraint step into every gate-level stage that *might* be loaded) can now declare their injections optional per action — without forcing the project author to redeclare them as feature-level or project-level opt-ins.
- **Implementation.** Per-action field threaded through `feature-v1.schema.json`, every `FlowAction` dataclass in [src/chopper/core/models_config.py](src/chopper/core/models_config.py), [src/chopper/config/loaders.py](src/chopper/config/loaders.py), and all seven stage-miss sites in [src/chopper/compiler/flow_resolver.py](src/chopper/compiler/flow_resolver.py). `VI-05` registered in [src/chopper/core/_diagnostic_registry.py](src/chopper/core/_diagnostic_registry.py) and [technical_docs/DIAGNOSTIC_CODES.md](technical_docs/DIAGNOSTIC_CODES.md). Architecture doc §6.7 documents the contract under "Optional Stage Targets".
- Version bumped 3.4.2 → 3.5.0.

### 3.4.2 — 2026-05-22

- **Fix: `options.cross_validate` now honored.** The flag in `BaseOptions` was loaded from JSON but never consumed; `_check_stage_steps()` ran VW-14/VW-15/VW-16 unconditionally. Threaded through `validate_post` → `_check_stage_steps` → `_classify_and_emit`. When `cross_validate: false`, VW-14/15/16 are suppressed entirely; VW-17 (external-path advisory) still fires because it does not depend on manifest lookups. See [src/chopper/validator/functions.py](src/chopper/validator/functions.py) and [src/chopper/orchestrator/runner.py](src/chopper/orchestrator/runner.py).
- **Docs decluttered.** Aggressive trim of the architecture-doc revision history (the canonical release log is git + this changelog). Removed `IMPLEMENTATION.md` Appendix A (out-of-scope items already covered by scope-lock in [.github/instructions/project.instructions.md](.github/instructions/project.instructions.md)). Renamed Appendix B → main-body "Future Considerations" section; dropped ADOPTED FD-14/FD-15 entries; compressed remaining `FD-xx` entries.
- **System review.** Full code-vs-spec audit confirmed the then-current CLI surface, all 83 diagnostic codes, all audit artifacts, generator outputs (aggregate + standalone), all 4 P5 sub-phases, and exit-code policy match the architecture doc. Only gap found was `cross_validate` (fixed above).
- Tests: 1506 passed, 100% coverage. Version bumped 3.4.1 → 3.4.2.

### 3.4.1 — 2026-05-22

- **P5d companion-file sync (FD-15 ADOPTED).** New `CompanionSyncService` in `src/chopper/trimmer/companion_sync.py`. For every `PROC_TRIM` `default_rules.<sfx>.tcl`, filters sibling `default_config.<sfx>.csv` (row-level, column 0) and `default_milestone.<sfx>.tcl` (`change_config <ProcName>` lines) to keep only rows/lines matching surviving proc short-names. Two new diagnostics: `VW-24 companion-file-missing`, `VI-04 companion-sync-applied`. Diagnostic registry active count 79→81.
- **Documentation refresh.** All technical and user docs updated to match actual v3.4 implementation: ENGINEERING.md §3 module layout rewritten with all 14 packages and files; tool-command pool descriptions updated to 6 bundled vendor pools (PrimeTime, PrimePower, PrimeECO, PrimeSim, Formality, PrimeClosure); user_docs live-trim steps, module map, FAQ, and flag descriptions updated. Version bumped 3.4.0 → 3.4.1.

### 3.4.0 — 2026-05-21

- **Aggregate `<domain>.stack` records now emitted in topological order.** Record order in the aggregate stack file (`options.generate_stack: true`) is now the topological sort of the stage dependency graph — edges are `dependencies ∪ {load_from}` per stage. Kahn's algorithm with **authored position** as the tiebreaker: deterministic, preserves authoring intent for unrelated subgraphs, no lexicographic shuffle. Materialized on a new `CompiledManifest.stack_order: tuple[str, ...]` field; `manifest.stages` itself remains in authored order so `<stage>.tcl` emission, trim report, and audit views continue to use authored sequencing.
- **`standalone_stack: true` now suppresses `<stage>.tcl`.** A stage with `standalone_stack: true` previously emitted both `<stage>.tcl` and `<stage>.stack`. As of 3.4.0 it emits **only** `<stage>.stack` (plus a record in the aggregate when `generate_stack` is on). The standalone stack becomes the stage's sole driver, eliminating the previous redundancy.
- **Two new diagnostics.** `VE-30 stage-dependency-cycle` and `VE-31 stage-dependency-unresolved` (both exit 1, phase 3) are emitted whenever `stages` is non-empty, regardless of `generate_stack` — a malformed dependency graph is an authoring bug independent of stack emission. Diagnostic registry summary updated: VE active 29→31, reserved 1→4 (band extended VE-30 → VE-35).
- **Hard cutover, no JSON knob.** No backward-compatibility shim; existing aggregate stacks regenerate in topological order on the next trim.
- Version bumped 3.3.0 → 3.4.0.

### 3.3.0 — 2026-05-21

- **Stack-file emission corrected to one aggregate per flow.** `options.generate_stack: true` now emits exactly one aggregate `<basename(domain_root)>.stack` at the domain root, containing one N/J/L/I/O/D record per resolved stage (R line added only for `run_mode: "parallel"`). Pre-3.3 emitted one `<stage>.stack` per stage, which contradicted the production artifact contract in `2025.06_json_exp/fev_formality/`. New `standalone_stack: boolean` flag on each stage definition is orthogonal and additive: when set, that stage additionally emits a per-stage `<stage>.stack` whose body is the Intel header + verbatim `steps` (no record-style derivation), intended for verbatim shell stacks such as `eco_apply_patch`. Three new diagnostics in the registry: `VE-28 aggregate-stack-collision`, `VE-29 standalone-stack-collision`, `VW-23 stack-stage-empty-command`. No backward-compatibility shim — legacy `emit_stage_stack` / `stack_output_path` symbols removed. New examples [examples/12_base_with_aggregate_stack/](examples/12_base_with_aggregate_stack/) and [examples/13_base_with_standalone_stack/](examples/13_base_with_standalone_stack/) demonstrate the two modes. Full gate green: 1448 passed, total coverage 99.99%. Version bumped 3.2.1 → 3.3.0.

### 3.2.1 — 2026-05-20

- **New `VW-22 proc-trim-no-drop` diagnostic (issue #26).** Chopper now emits a warning when a `PROC_TRIM` file’s backup contains zero procs to remove — i.e. every proc found in `<domain>_backup/` already belongs to the keep set. The built file is byte-identical to the backup. The canonical cause is a stale backup that holds a prior run’s post-trim output: `chopper cleanup --confirm` removed the real backup; a subsequent Case 1 run promoted the already-trimmed domain to backup; the second trim has nothing more to do. `VW-22` surfaces this in `diagnostics.json` so regression pipelines can distinguish a genuine “no change needed” trim from a “backup was already trimmed” silent no-op. Recovery: restore the original pre-trim source from version control, delete `<domain>_backup/`, and re-run. Version bumped 3.2.0 → 3.2.1.

### 3.2.0 — 2026-05-19

- **Coverage gate raised to 99% and validated at 100%.** Updated the project coverage threshold from 78% to 99% in active testing/config docs and pytest coverage enforcement (`--cov-fail-under=99`). Full regression gate run is green: **1410 passed, 0 failed; total coverage 100.00%** (5512 statements with 0 missed; 1912 branches with 0 partial). No schema, diagnostic-registry, CLI surface, exit-code, or runtime behavior changes. Version bumped 3.1.0 → 3.2.0.

### 3.1.0 — 2026-05-15

- **New `.chopper/p4_commands.txt` audit artifact (issue #24, FR-47).** Every `chopper trim` run — live and dry-run — now emits a deterministic, sorted Perforce command list under `.chopper/p4_commands.txt`. Three alphabetically-sorted sections, each with a `#`-comment header: (1) `p4 edit -t text+x <path>` for `PROC_TRIM` files and `GENERATED` files that overwrite an existing depot entry (regenerate-in-place), (2) `p4 add -t text+x <path>` for newly-created `GENERATED` files, (3) `p4 delete <path>` for files dropped from the rebuilt domain (parity with `files_removed.txt`). `FULL_COPY` files emit no command (byte-identical to depot). `-t text+x` matches the cross-phase `ensure_executable()` contract (every rebuilt file carries `a+x`). Operators review the file and run `p4 submit` manually — Chopper never invokes `p4` itself. Not emitted by `validate`, `loc`, or `cleanup`. Architecture doc §5.5.14, FR-47. Version bumped 3.0.0 → 3.1.0.

### 3.0.0 — 2026-05-15

- **Test-coverage hardening — 99.92% across all source files.** Distributed 30+ surgical `test_*_coverage.py` unit tests into their native `tests/unit/<module>/` locations, covering defensive branches, OSError/ValueError handlers, protocol error paths, and edge cases across every pipeline phase (parser, compiler, trimmer, validator, orchestrator, CLI, audit, adapters, core). Added `[tool.coverage.report].exclude_also` block to `pyproject.toml` so standard `# pragma: no cover` markers properly exclude unreachable defensive guards. Four targeted pragma annotations placed on provably-unreachable branches in `merge_service.py` and `proc_extractor.py`. Final gate: **1368 tests passing, 0 failed; total coverage 99.92%** (5454 lines, 0 missed lines, 6 partial branches — all pragma-annotated). `make ci` fully green across all six quality stages. Version bumped 2.10.0 → 3.0.0.
- **R1 ordered-overlay + FlowAction torture suite.** `tests/integration/test_cli_chained_actions.py` (19 scenarios A1–O) and `tests/integration/test_cli_chained_overlay.py` (16 scenarios) added as permanent regression anchors. Scenarios exercise all 7 `FlowAction` kinds × F1 (FE/FI) × F2 (PE/PI) interactions, including ambiguous-anchor `VE-20`, instance-index overflow `VE-10`, F3-vs-FI collision (exit 3), add+remove net-zero, replace-step last-layer-wins, and chained `add_*_after` order-preservation across three features.

### 2.10.0 — 2026-05-14

- **Full `jsons/` directory preserved in the rebuilt domain (§5.6).** The P5a tail now mirrors the entire `<domain_backup>/jsons/` directory verbatim into the rebuilt `<domain>/jsons/`. Every JSON that existed in the original domain — the base JSON, all feature JSONs (selected and unselected), and any other file under `jsons/` — is present in the trimmed output without ambiguity. Users no longer need to consult the backup to find an unselected feature JSON. Out-of-tree inputs (JSON files outside the domain root) continue to land in `<domain>/jsons/_external/<NN>_<basename>`. Implementation: `src/chopper/trimmer/input_preserver.py` rewritten with a new `_copy_dir()` recursive helper; old `_resolve_target()` removed. Version bumped 2.9.1 → 2.10.0.

### 2.9.0 — 2026-05-12

- **Production-hardening refactor (no spec / registry / schema changes).**
  - **Shared full-domain BFS walker** — new `src/chopper/core/fs_walk.py` exposing `walk_files()` + `TEXT_LIKE_EXTENSIONS`. The audit summary (`audit/writers.py`) and `chopper loc` (`cli/loc_report.py`) now enumerate the domain through the same helper, eliminating the two divergent BFS implementations and the drift between them. File counts walk every regular file; SLOC math is constrained to `TEXT_LIKE_EXTENSIONS` so binary-decodable artifacts no longer inflate the count.
  - **Batched `cloc` invocations** — new `count_sloc_via_cloc_batch()` in `audit/cloc_backend.py` runs a single `perl cloc.pl --by-file --json --quiet` per tree instead of one subprocess per file. New `count_sloc_many()` public API in `audit/sloc.py`. Hot trim domains (~thousands of files) go from O(N) subprocess starts to O(1). Whitespace-only payloads short-circuit to `0` without invoking cloc. The single-file `count_sloc()` API is unchanged for back-compat.
  - **Symmetric trim-stats totals** — `cli/render.py` totals row is unconditionally labelled `TOTAL` and uses identical aggregation for live and `--dry-run` invocations (`_collect_rows` falls back to `domain_root` for `sloc_in` when no backup exists), so the two tables can be diffed byte-for-byte.
  - **`files_skipped_decode` surfaced** — `chopper_run.json` summary and `trim_stats.json` now expose a `files_skipped_decode: int` field counting SLOC-eligible files that failed to decode (binary content, bad encoding, or OS error). Previously these were silently treated as 0-SLOC.
  - **Cross-phase exec-bit helper hoisted to `core/`** — `ensure_executable()` and `EXEC_BITS` moved from `trimmer/file_writer.py` to new `src/chopper/core/file_perms.py`, plus a new `mirror_perms_plus_exec(src, dst)` helper. Every file written into `<domain>/` now carries the **source file's full mode bits** (read/write/setuid/sticky, etc., via `shutil.copymode`) **plus** `a+x` for user/group/other. This applies uniformly to all three trimmer treatments (`FULL_COPY`, `PROC_TRIM`) and to the regenerate-in-place `GENERATED` case (where the artifact path also existed in `<domain>_backup/`); newly emitted `GENERATED` artifacts that have no source counterpart still get `a+x` only. The generator no longer reaches across services into the trimmer; `lint-imports` `Services are independent` contract is now green.
  - **Python 3.13 baseline** — `pyproject.toml` `requires-python = ">=3.13"`; ruff `target-version = "py313"`; mypy `python_version = "3.13"`. Build/runtime now align on the same interpreter floor.
  - **Indentation-pass docs cleanup** — `trimmer/indentation.py` docstrings dropped the misleading "ports the legacy Perl formatter" framing (no `indent.pl` ships with Chopper; the algorithm is brace-driven and Python-native).
- **Gate status:** ruff lint + format ✅, mypy ✅ (78 source files), `lint-imports` ✅ (4/4 contracts kept, 0 broken), pytest **1097 passed / 10 skipped**, coverage **94.34%** (gate 78%). No diagnostic-registry, schema, CLI, or audit-bundle field-shape changes (additive `files_skipped_decode` field only).

### 2.6.4 — 2026-05-11

- **`chopper trim` UX cluster (no spec/registry/schema changes).**
  - **Per-run trim stats table.** After a live `chopper trim` finishes, the CLI now prints a console-width-aware table to stderr summarising every output file: `File`, `Op` (`COPY` / `TRIM` / `DROP` / `GEN`), `SLOC (in → out)` with delta, and `Procs (kept/dropped)`. A `TOTAL` row aggregates the run. Generated artifacts (`<stage>.tcl`, `<stage>.stack`) are included; when a generated path was already present in the source domain (regenerate-in-place, e.g. `fev_fm_rtl2gate.tcl`), the row's `in` SLOC is taken from the pre-trim source rather than 0 so the delta reflects the real before→after. Dry-run skips the table (nothing on disk to count). Rendered by the new `render_trim_stats()` in `src/chopper/cli/render.py`.
  - **`chopper loc` aligned.** The `GENERATED` bucket in `cli/loc_report.py` now also captures pre-existing source as the `lines_before`/`sloc_before` baseline (was unconditionally 0). `files.before` is incremented once per regenerate-in-place path so it isn't double-counted with `REMOVE`.
  - **Executable bit on every rebuilt domain file.** P5a (trimmer) and P5b (generator) now `chmod a+x` every file they write to `<domain>/`, so trimmed `.tcl`/`.pl`/`.csh`/`.py` and emitted `<stage>.tcl`/`<stage>.stack` are runnable regardless of source mode or process umask. Errors from `chmod` are swallowed defensively (NFS exports that reject the call do not break the trim). Shared helper `ensure_executable()` in `src/chopper/core/file_perms.py`.
  - **TI-01 suppressed from console.** The `INFO TI-01 known-tool-command` lines (one per tool-command-pool match, often hundreds per run) are no longer emitted to stderr by `render_diagnostics()` — they were drowning out actionable `WARN`/`ERROR` lines. The diagnostics are **still recorded in the audit bundle** (`.chopper/`) unchanged; the registry, severity, and exit-code policy are untouched. Suppression list in `cli/render.py` (`_SUPPRESSED_STDERR_CODES`). `--strict` accounting is unaffected (TI-* never escalated).
  - **NFS-stale-cwd guard.** When `chopper trim` is invoked from inside `<domain>/` and no `<domain>_backup/` exists yet (the case-1 prep that renames `<domain>` → `<domain>_backup`), the CLI now emits a stderr notice up front explaining the parent shell's cwd will go stale on NFS (`pwd: Stale file handle`) and recommends `cd <parent> && cd <domain>` to recover, or simply running trim from the parent directory. Python cannot repair the parent shell's working-directory fd, so this is documentation-only at the surface. New helper `_warn_if_cwd_will_be_renamed()` in `cli/commands.py`.
  - **`Path.cwd()` failure paths hardened.** `cli/commands.py::_resolve_domain_root` and `audit/internal_error.py::_resolve_audit_root` now catch `FileNotFoundError`/`OSError` from `os.getcwd()` (stale NFS inode after a sibling rename). The CLI exits with a single readable line recommending `--domain <path>`; the internal-error writer falls back to `tempfile.gettempdir()/chopper` so a crash log still lands somewhere.
- **Docs cascaded:** `user_docs/02_CLI_GUIDE.md` `## chopper trim` section grew a "Trim stats" subsection and a "File permissions" bullet; `technical_docs/ARCHITECTURE.md` §14 revision history row added. No new diagnostic codes, no schema field additions, no audit-bundle shape changes.

### 2.6.3 — 2026-05-11

- **Docs-only patch.** Expanded user-facing and architecture documentation of `chopper loc` to cover what file types are counted, the source-root resolution rule (preferring `<domain>_backup/` when present, mirroring the parser), accounting caveats (PROC_TRIM dry-run reconstruction; all-procs-dropped collapses to REMOVE; P5c indentation pass not modeled; default-exclude under R2; `.chopper/` excluded; decode fallback), and a set of worked corner-case examples. Cascaded across `technical_docs/ARCHITECTURE.md` §5.7, `technical_docs/CLI_REFERENCE.md` `## chopper loc`, and `user_docs/02_CLI_GUIDE.md`. No code, schema, registry, or test changes.

### 2.6.2 — 2026-05-11

- **Patch bump.** Renderer change for `chopper loc` from ASCII table to line-oriented `key: value` output (grep/awk/CI-friendly). VW-10 false-positive fix in `validator/functions.py`: post-trim logical-size normalization now applies only to `PROC_TRIM` outcomes (which record `bytes_out` from LF-normalized text), not to `FULL_COPY` `.tcl` files (which record `bytes_out` from raw `stat()` and so must be compared byte-for-byte) — resolves a Windows CRLF false-positive in `_check_trim_output_for_each_outcome`. Runner `finally`-block guard added (`if command != "loc":`) so the audit-skip path no longer clobbers `RunResult` with `None`. User-facing docs (`user_docs/02_CLI_GUIDE.md`) and onboarding presentation (`presentation/chopper_onboarding.html`) cascaded with a dedicated `chopper loc` slide and updated subcommand counts. No spec/registry/schema changes.

### 2.6.0 — 2026-05-11

- **New `chopper loc` read-only LOC report subcommand.** Same input flags as `validate`/`trim` (`--base [--features]` or `--project`). Runs the same P0–P4 + dry-run-P6 pipeline as `chopper trim --dry-run`, additionally invokes `GeneratorService` in no-write mode so generated stage `.tcl` content is countable, then prints a stdout LOC table comparing the source domain against the planned trimmed domain: files before/after, physical lines before/after, SLOC before/after, percent reduction, plus a per-treatment breakdown (FULL_COPY / PROC_TRIM / REMOVE / GENERATED). Writes **nothing** to the filesystem — no domain modifications and no `.chopper/` audit bundle. The runner branches on `command == "loc"` to (a) run `GeneratorService` even in dry-run mode and (b) skip the P7 audit `finally` block. Per-treatment line accounting: `FULL_COPY` reuses source line count; `PROC_TRIM` masks out `procs_removed` line spans (body + DPA + leading comment when present); `REMOVE` is 0; `GENERATED` counts the rendered artifact content. Files present in the source domain but absent from `manifest.file_decisions` are treated as REMOVE for the after totals (default-exclude under R2). Exit-code policy matches `validate` (0/1/2/3). New `src/chopper/cli/loc_report.py` module owns the math and table render. **FR-46** added in the architecture doc; §5.1.1 example block, §5.7 dry-run section, §5.9 subcommand enumeration, and CLI_REFERENCE.md top-level + new `## chopper loc` section all cascaded. No diagnostic-registry, schema, or audit-bundle surface changes.

### 2.5.0 — 2026-05-09

- **Parser bug fix (P-01a literal-quote-in-braced-data-word).** The structural tokenizer in `src/chopper/parser/tokenizer.py` was opening a phantom quoted word whenever an unescaped `"` appeared as the first byte inside a literal data word (e.g. `set q {"}`, `regexp {".*"} $line`). The phantom quote silently consumed the matching `}`, desyncing brace depth and producing a false-positive `PE-02 unbalanced-braces` later in the file. Real-world repro: Synopsys Formality `default_fm_procs.tcl` emitted `PE-02` at line 2535 caused by `set q {"}` at line 2480 (verified with `tclsh info complete` → `complete=1`). Fix is a one-byte peek-back at quote-open time: if `text[i-1]` is an unescaped structural `{`, the `"` is treated as the literal first content byte of the braced word (Tcl Endekas rule 6) instead of opening a quoted word. Closing `}` handling is unchanged. New regression fixture `tests/fixtures/edge_cases/parser_literal_quote_in_braced_word.tcl` and three new tokenizer unit tests. IMPLEMENTATION.md §1.3.3 "Literal-data-word exception" and §12 P-01a row added in place. **No diagnostic-registry, schema, or CLI surface changes.**
- **Pre-existing baseline cleanups landed in the same release:** ruff format drift on `src/chopper/trimmer/indentation.py` reformatted; mypy `Literal` narrowing on `src/chopper/compiler/merge_service.py:625` (`ShadowEvent.action` arg) fixed by adding a `Literal["replace", "downgrade-whole-to-trim"]` annotation on the local `action` variable. `make check` is now end-to-end clean (lint + format-check + mypy + 1087 tests).
- **Version policy:** alpha tag dropped. Minor bumped 2.0 → 2.5 to mark the parser as production-validated against the snps Formality real-world fixture.

### 2.0.0a3 — 2026-05-09

- **P5c Tcl indentation pass is now opt-in (`base.options.indent`, default `false`).** Real-world domains were tripping `VW-10` reconciliation and misindenting valid inputs because the legacy Perl-port formatter lacks quote/comment awareness, line-continuation handling, multi-`}` dedent, and braced-literal whitespace preservation. P5c now runs only when `base.options.indent: true` is set explicitly. When off (the default), `TclIndentationService.run` is a no-op pass-through: PROC_TRIM and GENERATED `.tcl` outputs reach disk verbatim from P5a/P5b. P6's brace-balance check (`VE-16`) still runs over those outputs because the runner computes the rewritten-path set even when the formatter is skipped (new public helper `tcl_output_paths(manifest)` in `trimmer/indentation.py`). The formatter algorithm itself is unchanged in this release — the limitations and the conditions for opting in are documented inline in the architecture doc §3.1 (`options.indent` row) and §5.5 (P5c paragraph). New `options.indent` boolean property added to `schemas/base-v1.schema.json`; `BaseOptions.indent: bool = False` added to `core/models_config.py`; `loaders.py` reads `options.indent`. Architecture doc §3.1 row + §5.5 P5c paragraph, JSON_AUTHORING_GUIDE §2 options table, and ENGINEERING `TclIndentationService` rows updated in place. No diagnostic-registry or CLI surface changes.

### 2.0.0a2 — 2026-05-08

- **Intel-standard copyright header is now prepended to every Chopper-generated artifact.** F3 emitters (`<stage>.tcl` and, when `options.generate_stack: true`, `<stage>.stack`) now begin with the canonical Intel legal-compliant copyright block, byte-for-byte verbatim from the reference Intel-owned EDA file (rule width, `--`-prefixed `INTEL CONFIDENTIAL` / `Copyright (c) <YEAR> Intel Corporation` lines, the trailing-whitespace lines, and the `Intel Legal compliant copyright header` title line are all preserved). The `<YEAR>` token is computed at emission time from `datetime.now().year` so generated files always carry the current calendar year. The header is **not** prepended to F1 `FULL_COPY` or F2 `PROC_TRIM` files — those originate on disk and already carry their own headers. Implemented in `src/chopper/core/header.py` (`intel_header_text` / `intel_header_lines`); wired into `generators/stage_emitter.py` and `generators/stack_emitter.py`. Architecture doc §6.6.1 (Generated File Header) added; §6.6 stack-format snippet and JSON_AUTHORING_GUIDE §2.1 stack-format snippet updated in place.
- **Bug fix: `add_step_after` and `add_stage_after` now preserve selected feature order when multiple features share an anchor.** "Selected feature order" is the order in which features are loaded into `LoadedConfig.features`, and it is the same whether the selection comes from `project.json` `features[]` (`--project`) or a comma-separated `--features` CLI list. Prior behavior re-resolved the anchor on every call, which silently **reversed** that order for N-feature shared-anchor scenarios (e.g. `--features lcp.feature.json,td.feature.json,scan.feature.json` each running `add_step_after setup:S` would emit scan-then-td-then-lcp). Resolver now tracks a per-resolve cumulative insertion offset for each `(stage, anchor)` pair and walks past prior same-anchor insertions before emitting, so the output preserves selected feature order: `..., S, <items from lcp>, <items from td>, <items from scan>, ...`. `add_step_before` and `add_stage_before` are unchanged — they already preserve order naturally because each insertion sits immediately before a (now-shifted) anchor. The order-independent F3 actions (`replace_step`, `replace_stage`, `remove_step`, `remove_stage`, `load_from`) follow last-layer-wins semantics, which is consistent with the R1 ordered-overlay contract that already governs F1 (file decisions) and F2 (proc decisions) in `merge_service.py`. Architecture doc §6.7 "Order Preservation for `add_*_after` Actions" added; resolver module docstring updated; two new regression tests in `tests/unit/compiler/test_flow_resolver.py` (`test_add_step_after_preserves_project_order_for_shared_anchor`, `test_add_stage_after_preserves_project_order_for_shared_anchor`).
- **No diagnostic-registry, schema, or CLI surface changes.** Pure generator + resolver bug-fix release.

### 2.0.0a1 — 2026-05-08

- **Bug fix (GitHub #22 / Pitfall P-45): `FULL_COPY` outputs are now byte-for-byte verbatim again.** Scoped P5c indentation normalization to `PROC_TRIM` and `GENERATED` `.tcl` outputs only. `FULL_COPY` `.tcl` files are never read or rewritten by P5c; they reach disk byte-identical to their source regardless of indentation style or trailing-brace balance. Fixes the 1.2.6 regression where `onepower/basic.tcl` was reformatted (tab/space normalization) and had a stray closing `}` synthesized by the brace counter, falsely tripping `VE-16` post-trim. `TrimReport.bytes_out` for `FULL_COPY` is now pinned at the source byte size during P5a and never re-stamped. P6 `validate_post` re-tokenizes only `PROC_TRIM` and `GENERATED` `.tcl` outputs (not `FULL_COPY`). Architecture doc §3.4 (F1), §3.5 (F2), §5.2.1 (P5 walkthrough), and §5.2.2 (P6 validate_post contract) updated in place; ENGINEERING.md `TclIndentationService.run` row updated; IMPLEMENTATION.md P-44 narrowed and new P-45 added.

### 2.0.0-alpha — 2026-05-08

- **R1 collapses to a single rule: ordered overlay, last layer wins.** Features are no longer additive — they are **layered**. Layers (`base` first, then each selected feature in declared order) are applied left-to-right; for each file/proc, the last layer that mentions it wins. A feature can now add new content, remove base content, or replace base content with its own. Same-layer authoring conveniences (`VW-09`, `VW-11`, `VW-12`, `VW-13`) are unchanged. `project.json` `features` ordering is now authoritative for **F1, F2, and F3** (was F3-only). Mental model: kustomize / Docker layers / CSS cascade. Full spec in [technical_docs/ARCHITECTURE.md](technical_docs/ARCHITECTURE.md) §4 (R1) and §5.3 (P3 algorithm).
- **Diagnostic registry: `VW-21` and `VE-27` added; `VW-18` and `VW-19` retired.** New `VW-21 layer-shadowed` (warning, exit 0) records every layer transition that changes a prior decision. New `VE-27 no-op-exclude` (error, exit 1) catches typo-class `files.exclude` / `procedures.exclude` entries that match nothing in the running set or via glob. Retired `VW-18 cross-source-pe-vetoed` and `VW-19 cross-source-fe-vetoed` cannot fire under the overlay model (a later layer's PE/FE *actually removes* the proc/file rather than being vetoed). Slot rows preserved per registry policy (slug `RETIRED`); never reuse the slots. VW band ceiling extended to `VW-30` to accommodate `VW-21` and future overlay diagnostics.
- **`FileProvenance` shape changed.** `vetoed_entries: tuple[str, ...]` field **removed**. Two new fields: `contributed_by: str | None` (the single last layer that positively contributed to the file) and `shadowed_by: tuple[ShadowEvent, ...]` (the audit trail of every layer transition that changed a prior decision). New frozen dataclass `ShadowEvent(layer, prior_layer, action)` with `action ∈ {"replace", "remove", "downgrade-whole-to-trim", "add-proc", "remove-proc"}`. `FileProvenance.proc_model` literal narrowed from `"additive" | "subtractive" | None` to `"overlay" | None`. `input_sources` field kept (P5 needs it for input-JSON copy logic in `<domain>/jsons/`).
- **Audit artifact provenance lines updated.** `files_kept.txt` provenance column changed from a comma-separated `<source_key>:<json_field>` list (formerly `FileProvenance.input_sources`) to a single `<contributed_by>` token (the last winning layer key). `files_removed.txt` provenance column changed from `vetoed-by:<src1>,<src2>,...` / `default-exclude` to one of `removed-by:<layer_key>:files.exclude` (last `ShadowEvent` action `"remove"`), `shadowed-by:<layer_key>:procedures.exclude` (last shadow event was a PE-driven removal), or `default-exclude` (file was never positively contributed to by any layer). Header comments in both artifacts updated.
- **Compiler `merge_service.py` rewritten as an ordered fold.** Replaces the previous two-pass per-source classification + cross-source aggregation (cases A/B/C, `_classify_source`, `_aggregate`) with a single-pass fold over `(base, *features_in_order)` carrying a `running` map. `tests/unit/compiler/test_aggregate.py` and `tests/unit/compiler/test_per_source.py` deleted (tested helpers that no longer exist). The compiler emits `VE-27 no-op-exclude` directly at three sites: literal `files.exclude` not matching the running set, glob `files.exclude` matching zero files at the layer, and `procedures.exclude` proc-name typo (short name does not resolve to a canonical proc in the file).
- **No backward compatibility** — alpha release. JSON-authoring surface is unchanged for the additive subset (a base-only domain or a feature whose excludes only target paths the same JSON includes still behaves exactly as in 1.x), but any `project.json` whose features removed or replaced base content via `VW-18` / `VW-19` cross-source vetoes will produce different output: the later layer now wins outright.

### 1.2.7 — 2026-05-07

- **Idempotent, source-only setup scripts.** All four scripts ([setup.csh](setup.csh), [setup.sh](setup.sh), [setup.ps1](setup.ps1), [setup.bat](setup.bat)) now reuse a healthy existing `.venv` instead of wiping and rebuilding it on every invocation; opt out with `CHOPPER_FRESH=1`. Removed the redundant `pip install -e . --force-reinstall --no-deps` step that caused full dependency reinstalls on every run; pip now short-circuits when nothing changed. Added explicit must-be-sourced guards (`if (! $?prompt)` for tcsh, `(return 0 2>/dev/null)` for bash, `$MyInvocation.InvocationName -ne '.'` for PowerShell) so executing instead of sourcing fails fast with a remediation hint rather than silently dropping the activated venv when the subshell exits.
- **Three-tier Python resolution strategy** applied uniformly across all four setup scripts: (1) probe PATH for `python3.13` / `python3` / `python` requiring `sys.version_info >= (3, 13)`; (2) Intel EC system Python at `/usr/intel/bin/python3.13.2` (Unix only); (3) local `uv python install 3.13.4` into `<repo>/.local-python/3.13/` if `uv` is available, or winget-installed Python 3.13 on Windows. Replaces the previous strict pin to a single EC interpreter — Chopper now adapts to whatever ≥ 3.13 the host already has.
- **TFM bundle de-hardcoded.** [Makefile](Makefile) `bundle` target replaces `EC_PYTHON := /usr/intel/bin/python3.13.2` with `BUNDLE_PYTHON ?= python`, so `vendor/` is populated using whichever Python is active in the developer's env (typically the `.venv` resolved by `setup.csh`); guards against accidentally building under `< 3.13`. The shipped launcher [scripts/dist/chopper.launcher.csh](scripts/dist/chopper.launcher.csh) now resolves Python at deploy time using the same PATH-first → EC-fallback strategy as `setup.csh`, instead of executing a baked-in `/usr/intel/bin/python3.13.2`. Bundles built before this release continue to run; new bundles work on any host with Python ≥ 3.13 on PATH or the EC mount available. Manifest field renamed `ec_python:` → `build_python:`.
- **No source-package, schema, diagnostic-registry, CLI surface, exit-code, runtime, or pipeline-phase changes.** Pure setup / packaging release. Version bumped 1.2.6 → 1.2.7.

### 1.2.6 — 2026-05-07

- **Dual-mode launcher.** Chopper can now be invoked as either the installed console script (`chopper ...`) **or** as a module (`python -m chopper ...`). Added [src/chopper/__main__.py](src/chopper/__main__.py) and updated [setup.csh](setup.csh), [setup.sh](setup.sh), [setup.ps1](setup.ps1), and [setup.bat](setup.bat) to prepend `<repo>/src` to `PYTHONPATH` and validate both invocation forms during setup. The existing `pip install -e .` step is retained, so `git pull` continues to pick up source changes immediately for both forms. The module form is the failsafe path: it always reads the working tree, even when the editable-install shim gets out of sync. No source-package, schema, diagnostic-registry, CLI surface, exit-code, runtime, or pipeline-phase changes — pure DX release.

### 1.2.5 — 2026-05-07

- **Validation-pass version bump.** Patch-level bump after the post-1.2.0 documentation cross-validation pass. Two prose drifts repaired in place: the `ARCHITECTURE.md` 1.1.0 revision-history row referenced a `_copy_input_sources` helper in `trimmer/service.py`; the live implementation is `preserve_input_sources` in [src/chopper/trimmer/input_preserver.py](src/chopper/trimmer/input_preserver.py) (called from the runner at the P5a tail). The README 1.1.0 entry pointed at `ARCHITECTURE.md §5.5` for preserved inputs; the subsection lives at §5.6. No source, schema, diagnostic-registry, CLI surface, exit-code, runtime, or pipeline-phase changes.

### 1.2.0 — 2026-05-07

- **Conditional `_backup` redirect for the resolved domain root.** Per [technical_docs/ARCHITECTURE.md](technical_docs/ARCHITECTURE.md) §5.1, the domain-root resolver now applies a single rule to both `--domain` and cwd: if the candidate's basename ends in `_backup` **and** the stripped sibling exists as a directory, the operational target is redirected to that sibling. Pointing `--domain /work/foo_backup` (or `cd`'ing into a `_backup/`) when a live `foo/` exists no longer produces a `foo_backup_backup/` artifact — it transparently retargets the live domain. A `_backup`-suffixed path with **no** live sibling is honored as-is, so coincidentally-named domains keep working.
- **New diagnostic `VI-03 domain-suffix-strip-applied`.** Info severity, exit 0, never escalated by `--strict`; carries the original candidate and the resolved domain root in its context. Emitted from the CLI sink so the redirect is visible in stderr and recorded in the audit bundle.
- **Tests.** Reworked [tests/unit/cli/test_commands.py](tests/unit/cli/test_commands.py): seven `_resolve_domain_root` cases (cwd fallback, conditional cwd redirect, no-redirect cwd, `--domain` precedence, conditional `--domain` redirect, no-redirect `--domain`, single-shot guard) and two `_make_context` emission tests for VI-03. Bumped active diagnostic count 72 → 73 in [tests/unit/core/test_diagnostics.py](tests/unit/core/test_diagnostics.py).

### 1.1.0 — 2026-05-07

- **`--domain` is now the highest-priority resolution input.** Per [technical_docs/ARCHITECTURE.md](technical_docs/ARCHITECTURE.md) §5.1, when `--domain PATH` is supplied the operational domain root is always `Path(args.domain).resolve()`; cwd is consulted only as a fallback when `--domain` is omitted. The pre-1.1 "must resolve to cwd or exit 2" guard has been removed — running `chopper trim --domain /elsewhere` from any cwd now succeeds. Cascaded into [technical_docs/CLI_REFERENCE.md](technical_docs/CLI_REFERENCE.md), [technical_docs/IMPLEMENTATION.md](technical_docs/IMPLEMENTATION.md) (P-25, P-31), and [technical_docs/DIAGNOSTIC_CODES.md](technical_docs/DIAGNOSTIC_CODES.md) (VE-17).
- **Selected JSON inputs are preserved in the rebuilt domain.** Per [technical_docs/ARCHITECTURE.md](technical_docs/ARCHITECTURE.md) §5.6, after a successful live trim the project / base / selected-feature JSONs are copied into the rebuilt `<domain>/jsons/` so the output is self-contained. In-tree inputs land at their original domain-relative path; out-of-tree inputs land in `<domain>/jsons/_external/<NN>_<basename>` with a deterministic two-digit ordering prefix. New `TrimReport.inputs_preserved` field reports the count. Dry-run skips this step. I/O failures emit `VW-20 audit-write-failed` and the run continues.
- **Tests.** Added two unit tests in [tests/unit/cli/test_commands.py](tests/unit/cli/test_commands.py) and one in [tests/unit/validator/test_validator.py](tests/unit/validator/test_validator.py) for the `--domain` priority lock; added five integration tests in [tests/integration/test_cli_e2e.py](tests/integration/test_cli_e2e.py) covering `--domain` from an unrelated cwd, in-tree preservation, out-of-tree `_external/` preservation, selective preservation (unselected features stay out), and dry-run no-op.

### 1.0.0 — 2026-05-07

- **Coverage hardened to ≥98% across all source files.** Added 74 surgical unit tests in [tests/unit/test_coverage_98.py](tests/unit/test_coverage_98.py) covering previously-unhit defensive branches across the validator, parser, compiler (trace + merge + flow resolver), config, audit, adapters, trimmer, and CLI modules. Total line+branch coverage: 92% → **98.75%**. Test suite: 1005 → **1079 passing**, 7 skipped.
- **No production code drift.** No schema, diagnostic-registry, CLI surface, exit-code, runtime, or pipeline-phase changes. Pure test-coverage release.
- **v1 stability milestone.** All six pipeline phases (P0–P7) now ship at near-complete branch coverage; version bumped 0.9.2 → 1.0.0 to mark the v1 stability line.

### 0.9.2 — 2026-05-06

- **End-user documentation consolidated and renamed.** The four-guide `doc/` folder (`README.md`, `USER_MANUAL.md`, `BEHAVIOR_GUIDE.md`, `TECHNICAL_GUIDE.md`, `IMPLEMENTATION_GUIDE.md`) was deleted and replaced with a leaner three-part suite under [user_docs/](user_docs/): [01_OVERVIEW.md](user_docs/01_OVERVIEW.md) (problem → solution → F1/F2/F3 → JSON structure → optional switches → BKMs → ownership), [02_CLI_GUIDE.md](user_docs/02_CLI_GUIDE.md) (every subcommand, every flag, deep examples, troubleshooting, bug-reporting), and [03_HOW_CHOPPER_WORKS.md](user_docs/03_HOW_CHOPPER_WORKS.md) (P0–P7 pipeline, design rules, where Chopper fits, FAQ). The new structure follows a thesis-style abstraction: descriptive opening, then commands, then internals — designed to ramp a reader up after the onboarding presentation in 60–90 minutes without fatigue. The Chopper-vs-Flow-Builder framing is now stated explicitly in the overview so the "Chopper" name does not mislead.
- **All back-references cascaded.** [README.md](README.md) documentation table, [CONTRIBUTING.md](CONTRIBUTING.md) "Before You Start" table, [.github/agents/chopper-agent.agent.md](.github/agents/chopper-agent.agent.md) Documentation Index, and [.github/ISSUE_TEMPLATE/config.yml](.github/ISSUE_TEMPLATE/config.yml) all point at `user_docs/`. Historical revision-history entries that mention the old `doc/` paths are left intact as point-in-time records (per project documentation convention).
- **No schema, diagnostic-registry, CLI surface, exit-code, runtime, or pipeline-phase changes.** Pure docs release.

### 0.9.1 — 2026-05-06

- **Documentation restructure.** Renamed `CLI_HELP_TEXT_REFERENCE.md` → `CLI_REFERENCE.md`, `ARCHITECTURE_PLAN.md` → `ENGINEERING.md`, and `chopper_description.md` → `ARCHITECTURE.md`. Consolidated `TCL_PARSER_SPEC.md`, `RISKS_AND_PITFALLS.md`, `IMPLEMENTATION_DECISION_LOG.md`, and `FUTURE_PLANNED_DEVELOPMENTS.md` into `IMPLEMENTATION.md` (parser §1, pitfalls §2–3, Appendix B `FD-xx`).
- **Cross-reference + semantic doc-vs-code validation.** Eight-stage sweep cleaned every stale citation across `src/`, `doc/`, `examples/`, `schemas/`, `tests/`, and `.github/`; fixed four behavioral drifts (scope-lock wording, audit-bundle table, module table, fixture-catalog references).
- **Agent consolidation.** Deleted four redundant `.github/agents/*.agent.md` files (`devils-advocate`, `principal-software-engineer`, `swe-subagent`, `Thinking-Beast-Mode`) and absorbed their behaviors into the surviving agents as internalized personas. Renamed `chopper-domain-companion.agent.md` → `chopper-agent.agent.md`.
- **System Check.** Added a System Check section to `.github/instructions/project.instructions.md` and to every active agent so they detect tcsh (Unix primary) / PowerShell (Windows secondary) / cmd.exe / bash-zsh (fallback) before issuing shell commands.
- **Chopper Agent upgrade.** Rewrote `chopper-agent.agent.md` with a Documentation Index, an explicit conversational style (one focused question + 2–3 active suggestions per turn), and a strengthened bug-reporting flow that funnels users to the GitHub issue template.
- **No schema, diagnostic-registry, CLI surface, exit-code, runtime, or pipeline-phase changes.** Pure tooling-and-docs release.

### 0.9.0 — 2026-05-06

- **Documented permitted validator→parser import exception (VW-10 proc-set reconciliation).** The validator module now explicitly documents its import of `parse_file` from the parser service for post-trim validation accuracy. This is the only permitted cross-phase import in the codebase, justified by the need to verify trimmed outputs contain exactly the proc set promised in `CompiledManifest` and `TrimReport`. This validation mechanism catches real bugs (dropped/kept procs that shouldn't be) with no bidirectional coupling. Architecture doc §5.12.9 added; project.instructions.md §1.1 and ENGINEERING.md §10.1 updated for clarity and cross-reference.

### 0.8.4 — 2026-05-06

- **P5c Tcl indentation normalization.** Live trims now run a deterministic Tcl formatting pass after proc trimming and F3 generation, before P6 validation. Every emitted `.tcl` output is covered: `FULL_COPY` Tcl files, `PROC_TRIM` Tcl files, and generated stage `<stage>.tcl` files.
- **P6 byte-count alignment.** The formatter updates `TrimReport.bytes_out` for `FULL_COPY` and `PROC_TRIM` `.tcl` outcomes after normalization so P6 `VW-10` compares against the final filesystem state rather than pre-format bytes.
- **Non-Tcl opacity preserved.** Binary and non-Tcl `FULL_COPY` files still use byte-preserving filesystem copies and are never decoded.
- **No schema, diagnostic-registry, CLI surface, or exit-code changes.**

### 0.8.3 — 2026-05-06

- **P5 opaque-file copy contract tightened (bug fix: GitHub #21 / Pitfall P-44).** The `FULL_COPY` path in `trimmer/file_writer.py` was incorrectly round-tripping every surviving file through UTF-8 text I/O (`read_text` → `write_text`). This crashed with a `UnicodeDecodeError` whenever a domain included non-UTF-8 or binary artifacts via F1 `files.include` (e.g., `.sn.gz` compressed sidecars, vendor binary payloads). The fix introduces a dedicated `copy_file(src, dst)` operation on `FileSystemPort` — implemented with `shutil.copy2` in `LocalFS` (preserves mode bits) and an in-memory clone in `InMemoryFS` — and rewires `full_copy_file()` to use it. The `remove_file()` byte-accounting is likewise fixed to use `stat().size` rather than reading file contents. `PROC_TRIM` remains the only P5 path that reads file text, and only for `.tcl` files selected for F2 proc trimming. Architecture doc §3.4 (F1), §3.5 (F2), and §5.2.1 (P5 walkthrough) updated in place with the write-semantics contract. Pitfall **P-44** added to `technical_docs/IMPLEMENTATION.md` (pitfalls).
- **Technical docs tightened.** F1, F2, P5, and `FileSystemPort` sections of `technical_docs/ARCHITECTURE.md` now state the write contract at the first mention; the "FULL_COPY = opaque copy" decision is no longer implied by absence of explicit description.
- **No schema, diagnostic-registry, CLI surface, or exit-code changes.**

### 0.8.2 — 2026-05-06

- **F1 glob-matched non-Tcl file gap fixed (Pitfall P-42).** Non-Tcl files (`.py`, `.pl`, `.csh`, config files) reachable *only* via a `files.include` glob pattern were silently absent from `compiled_manifest.json` with exit code 0. Fixed in `compiler/merge_service.py`.
- **No schema, diagnostic-registry, CLI surface, or exit-code changes.**

### 0.8.1 — 2026-05-01

- **Performance uplift: O1–O6 optimization wave complete.** This release integrates all six optimizations tracked as O1–O6 across the pipeline and activates the cache-reuse pattern introduced in the architecture doc.
  - **O1 — domain file cache.** P1 glob-expansion now caches the BFS domain walk in `LoadedConfig.domain_file_cache`. P2's full-domain harvest phase filters that cache for `.tcl` files instead of re-walking the filesystem, eliminating a second full-directory scan on every trim run.
  - **O2 — `short_to_canonical` cache.** The per-file short-name → canonical-name dict in the compiler merge service is now built once per `ParseResult` (in `_build_short_to_canonical()`) and reused across the classify and aggregate passes, cutting the rebuild count from `2 × S × F` to `S`.
  - **O3 / O4 — verified no-op.** Both candidates were audited and confirmed to require no code change (see [IMPROVEMENTS.md](IMPROVEMENTS.md)).
  - **O5 / O6 — structural refactor.** Shipped in 0.8.0 (core model split, call-extractor modularization).
- **Setup scripts: proxy applied before first network op, uninstall is now conditional.** [setup.ps1](setup.ps1), [setup.sh](setup.sh), [setup.csh](setup.csh), and [setup.bat](setup.bat) now export `HTTP_PROXY` / `HTTPS_PROXY` to the current shell session immediately after resolving `CHOPPER_PROXY`, so the step-[1/6] `git pull` already runs through the proxy. The step-[5/6] uninstall is now conditional: `pip show chopper` is checked first and the uninstall command is skipped when the package is not present, making fresh-venv installs cleaner.
- **No behavioral, schema, diagnostic-registry, or CLI-surface changes.**

### 0.8.0 — 2026-05-01

- **Wave B refactor completion (O5/O6).** The core model god-module and parser call-extractor monolith were split into direct, readable modules with no compatibility shims. Frozen dataclasses now live only in phase-owned modules: [src/chopper/core/models_common.py](src/chopper/core/models_common.py), [src/chopper/core/models_parser.py](src/chopper/core/models_parser.py), [src/chopper/core/models_config.py](src/chopper/core/models_config.py), [src/chopper/core/models_compiler.py](src/chopper/core/models_compiler.py), [src/chopper/core/models_trimmer.py](src/chopper/core/models_trimmer.py), and [src/chopper/core/models_audit.py](src/chopper/core/models_audit.py). Code imports from the module that owns the model.
- **Parser call extraction modularized.** Parser call extraction now uses focused direct modules: [src/chopper/parser/call_extractor_body.py](src/chopper/parser/call_extractor_body.py) owns `extract_body_refs`, [src/chopper/parser/call_extractor_constants.py](src/chopper/parser/call_extractor_constants.py) owns the public suppression sets, and the classification/source/structural helpers live beside them. The high-risk `extract_body_refs` dependency path is covered by parser tests after the import rewrite.
- **Setup scripts refresh proxy, reinstall cleanly, and validate handoff.** [setup.ps1](setup.ps1), [setup.sh](setup.sh), [setup.csh](setup.csh), and [setup.bat](setup.bat) now update proxy settings for the current shell plus pip/Git using `CHOPPER_PROXY` or the default Intel proxy, uninstall any stale `chopper` package from the venv before reinstalling editable dev dependencies, validate both `sys.prefix` and `chopper --help`, and finish by handing control back with the venv active.
- **Validation.** Focused gates passed after each split: core model tests (186 passed), parser extraction/service tests (143 passed), mypy for affected packages, and all import-linter contracts. Final validation: static/docs/import gates passed, unit coverage stayed well above threshold (91.52% total coverage vs 78% required), and the full functional matrix passed (895 passed, 6 skipped).

### 0.7.0 — 2026-05-01

- **Programmer-error contract closed end-to-end.** A 2026-05-01 audit found two coupled drifts: [schemas/run-result-v1.schema.json](schemas/run-result-v1.schema.json) declared an `internal_error` field on `RunResult` but the model had no such field, and the runner caught only `ChopperError` so any other unhandled exception escaped as a raw Python traceback. Both are fixed in this release. New `InternalError` frozen dataclass `{kind, message, log_path}` lives in [src/chopper/core/models_audit.py](src/chopper/core/models_audit.py); `RunResult.internal_error` and `RunRecord.internal_error` are populated by a new [src/chopper/audit/internal_error.py](src/chopper/audit/internal_error.py) writer that emits `.chopper/internal-error.log` (run_id, timestamp, version, platform, full traceback, diagnostic snapshot, RunConfig) per architecture doc §5.5.10. The runner catches both `ChopperError` and generic `Exception` (both → exit 3 + log); the CLI gained a top-level `try/except Exception` for pre-runner failures (exit 1, ctx-less log fallback).
- **Audit failures are no longer silent.** New `VW-20 audit-write-failed` (warning, phase 7, source `audit`, exit 0) — emitted from [src/chopper/audit/service.py](src/chopper/audit/service.py) when an artifact under `.chopper/` fails to write (`OSError`: disk full, permission denied, etc.). The previous behaviour silently swallowed the exception and produced a partial bundle with no signal to the user (NFR-13 violation). Active diagnostic-code count: **70 → 71**. The runner's `finally` audit hook also lost its bare `except Exception: pass`; audit-code bugs now surface to stderr as `[chopper] internal: audit bundle failed to write: ...`.
- **Tcl-aware brace counter.** [src/chopper/validator/functions.py](src/chopper/validator/functions.py) `_brace_delta` (the post-trim VE-16 internal-consistency check) was previously a naive `text.count('{') - text.count('}')` that would false-positive on legal Tcl such as `puts "{"` and trip exit 3. Rewritten as a small Tcl tokenizer that honours backslash escapes, skips braces inside `"..."` quoted strings, and skips full-line `#` comments. Mid-line `;#` trailing comments are intentionally not skipped (Tcl-correct: trailing comments after `;` still parse as commands; counting their braces matches the parser's authoritative behaviour at P2).
- **Python version policy aligned.** Spec §5.12 had said "≥ 3.13" while [pyproject.toml](pyproject.toml) said `>=3.11` and ruff/mypy targeted 3.11 — three-way drift. Spec narrative reconciled to "≥ 3.11 (3.13 preferred)"; pyproject / ruff / mypy unchanged (already 3.11). 3.11 is the floor so Chopper installs cleanly on long-lived workstations; 3.13 is the recommended target where available. PEP 695 type-parameter syntax remains forbidden in `src/`.
- **SLOC counter language coverage.** [src/chopper/audit/sloc.py](src/chopper/audit/sloc.py) (the engine behind the `sloc_before` / `sloc_after` / `sloc_removed` / `trim_ratio_sloc` fields in `trim_report.json` and `trim_stats.json`) was previously hash-comment-aware for Tcl, Perl, and Bourne-family shells only — Python was missing entirely, and `.tcsh`, `.zsh`, `.ksh` were treated as unknown. Extension set widened from 6 to 10 (`.tcl, .sh, .csh, .tcsh, .bash, .zsh, .ksh, .pl, .pm, .py`). Module docstring documents Python triple-quoted module docstring behaviour explicitly: counted as code, not skipped, for predictability across SLOC-counter dialects.
- **Compiler optimization (O2): `short_to_canonical` cached once per `ParseResult`.** [src/chopper/compiler/merge_service.py](src/chopper/compiler/merge_service.py) previously rebuilt the per-file short-name → canonical-name dict per source per pass (classify pass + aggregate pass with PE entries), totalling `2 × S × F` rebuilds where `S` is the number of JSON sources and `F` is the file count. New `_build_short_to_canonical()` helper called once per parsed file at the top of `CompilerService.run()`; the resulting `dict[Path, dict[str, str]]` is threaded into `_classify_one` and `_aggregate`. Internal refactor only — zero behavioural change, byte-identical golden outputs.
- **Spec / code drift audit captured in [IMPROVEMENTS.md](IMPROVEMENTS.md).** The full audit (10 drifts, 6 optimisations, 5 architectural holes) plus per-decision rationale, implementation log, and Wave B verdicts (O3 / O4 verified no-op; O1 / O5 / O6 deferred to dedicated PRs) is recorded in [IMPROVEMENTS.md](IMPROVEMENTS.md) §1–§6 alongside the user decisions that drove each fix.

### 0.6.0 — 2026-05-01

- **Layered-architecture cleanup — all four import-linter contracts now KEPT.** The codebase has long declared a four-tier layered architecture in `pyproject.toml` `[tool.importlinter]` (cli → orchestrator → services → core; core stdlib-only; services independent of each other; adapters core-only), but two pre-existing violations had been silently tolerated: `chopper.config.service` imported `chopper.compiler.tool_commands` (service → service), and `chopper.validator.functions` imported `chopper.config.service._glob_to_regex_local` (service → service). Both are now fixed by hoisting the shared logic into `chopper.core`:
  - **`tool_commands` moved to core.** `src/chopper/compiler/tool_commands.py` → [src/chopper/core/tool_commands.py](src/chopper/core/tool_commands.py) (pure data parser — no service dependencies). Two callers updated: [src/chopper/config/service.py](src/chopper/config/service.py) (P1 surface-file collection) and [tests/unit/compiler/test_tracer.py](tests/unit/compiler/test_tracer.py).
  - **`glob_to_regex` consolidated in core.** [src/chopper/core/globs.py](src/chopper/core/globs.py) is now the single canonical POSIX-glob-with-`**`-semantics translator. The three pre-existing copies (one each in `config/service.py`, `compiler/merge_service.py`, `validator/functions.py`) collapse to thin re-export aliases at the original call sites — zero call-site churn and zero behavioral change, but services no longer reach sideways into each other to share the helper (the previous `validator.functions` → `config.service._glob_to_regex_local` import was the last remaining service-to-service edge).
  - **Result:** `lint-imports --config pyproject.toml` reports `Contracts: 4 kept, 0 broken` for the first time. Layered-architecture, core-stdlib-only, services-independent, and adapters-core-only contracts are all green and now CI-enforced via `make imports-check`.
- **`make docs-gate` repaired.** The `docs-gate` Makefile target had been pointing at `scripts/check_diagnostic_registry.py` and `scripts/check_service_signatures.py`, but the canonical location after the 0.3.0 `json_kit/` dissolution is [schemas/scripts/](schemas/scripts/). Fixed the Makefile path **and** fixed both scripts' `ROOT = Path(__file__).resolve().parent.parent.parent` (was `.parent.parent`, broken when invoked from any CWD). The `check_service_signatures.py` `normalise_signature` helper gained a `re.sub(r"\s*=\s*", "=", collapsed)` pass to handle the `ast.unparse` `=None` vs prose `= None` whitespace mismatch that was producing false-positive drift reports. Documentation cascade applied in the same pass: [technical_docs/ENGINEERING.md](technical_docs/ENGINEERING.md) §9.2 `TracerService` row updated to match the actual `(ctx, manifest, parsed, loaded?) -> DependencyGraph` source signature.
- **CHANGELOG consolidation.** The standalone `CHANGELOG.md` was deleted; the canonical changelog now lives at the bottom of this README so new contributors see release history alongside install / usage / architecture in a single document.
- **No runtime, schema, diagnostic-registry, exit-code, or CLI-surface changes.** The version bump reflects the magnitude of the architectural-discipline change (every service now actually obeys the layered-import contract that was always declared) — not a behavioral change.

### 0.5.4 — 2026-05-01

- **`files_removed.txt` now reflects physical deletions, byte-identical between `--dry-run` and live trim** ([#15], subsumes [#17]). Earlier releases iterated only `CompiledManifest.file_decisions[REMOVE]`, which silently omitted every file the trim physically deleted because no `files.include` pattern named it (`.pl` / `.csh` / `.py` companion scripts in real EDA domains). A live trim could delete 161 files and report zero in the audit artifact. The writer now computes `set(walk(source_root)) − set(kept_paths)` where `source_root` is whichever of `<domain>_backup/` or `<domain>/` holds the original (pre-trim) file set — `backup_root` after a live trim (P5 has moved the original domain there), `domain_root` for first-trim `--dry-run` (no backup created yet), `backup_root` for re-trim `--dry-run` (backup is from the prior live trim). Each removed path is tagged `default-exclude` (the file was either named by a losing intent or never named at all) or `vetoed-by:<src1>,<src2>,...` (cross-source veto via `FileProvenance.vetoed_entries`). The artifact's leading-comment header was updated to "paths physically removed from the rebuilt domain". **Consistency contract:** for the same input filesystem state and the same JSONs, `--dry-run` and live trim produce byte-identical `files_removed.txt`; this is locked by `tests/unit/audit/test_audit.py::test_render_files_removed_dry_run_and_live_byte_identical`. The fallback (no source root visible — audit running after a P0/P1 abort or a stub filesystem) preserves the prior manifest-only view so the artifact is still well-formed. Architecture Doc §3.7 updated to specify the new semantics.
- **Issue #14 follow-up.** [tests/unit/trimmer/test_file_writer_modes.py](tests/unit/trimmer/test_file_writer_modes.py) (the mode-bit-preservation regression suite shipped in 0.5.3) now skips on Windows where POSIX mode bits aren't honored by `os.chmod`. The bug it covers (silent loss of executable / group / world perms during trim, fixed by `_mirror_mode` in `src/chopper/trimmer/file_writer.py`) is Linux-only.

[#14]: https://github.com/rkudipud/chopper/issues/14
[#15]: https://github.com/rkudipud/chopper/issues/15
[#17]: https://github.com/rkudipud/chopper/issues/17

### 0.5.3 — 2026-05-01

- **`files_kept.txt` / `files_removed.txt` now carry JSON provenance per file.** Both audit artifacts already shipped as flat sorted path lists, which answered "how many?" but not "which JSON pulled this in?". Each line is now tab-separated as `<path>\t<provenance>`. In `files_kept.txt`, `<provenance>` is a comma-separated list of `<source_key>:<json_field>` tags taken from `CompiledManifest.provenance[<path>].input_sources` (e.g. `base:files.include,feature_a:procedures.include`), or `-` for paths with no JSON authoring entry. In `files_removed.txt`, `<provenance>` is `vetoed-by:<src1>,<src2>,...` when the file was named but vetoed cross-source (`FileProvenance.vetoed_entries`), or `default-exclude` when no JSON named the file. Output stays alphabetically sorted by path so regression pipelines using `cut -f1` / `diff` keep working. Architecture Doc §3.7 updated to specify the new per-line format. Two new unit tests in `tests/unit/audit/test_audit.py` lock the multi-source-provenance and vetoed-by paths.

### 0.5.2 — 2026-04-30

- **P2 now builds a full-domain proc index (Option A).** The parser was previously parsing only `loaded.surface_files` (the JSON-named subset), so a surfaced proc that called a helper defined in a non-surfaced file produced a noisy `TW-02 unresolved-proc-call` with no defining file. Architecture Doc §5.4 has long specified the index is built from the entire domain (`sorted(domain_path.rglob('*.tcl'))`); the implementation now matches the spec. `ParserService.run` runs in two phases: **Phase 2a** parses `surface_files` with full diagnostics, and **Phase 2b** silently parses every other `.tcl` file under `domain_root` (`.chopper/` excluded) for index population only — diagnostics from non-surfaced files are dropped because the user did not ask Chopper to scrutinise them. `ParseResult.__post_init__` invariant relaxed from `set(files.procs) == set(index)` to `set(files.procs) ⊆ set(index)`. **Trace remains reporting-only (Critical Principle #7)** — the wider index never adds survivors; it only sharpens `dependency_graph.json` so `TW-02` truly means "no in-domain proc with this name" (a real external/cross-domain call) rather than "I never looked at the file it lives in". Two new integration tests in `tests/integration/test_cli_e2e.py::TestFullDomainProcIndex` lock the contract.
- **Architecture Doc §5.2 / §5.2.1 / §5.4.1 updated** to document the surface vs full-domain split, the relaxed model invariant, and reaffirm Critical Principle #7. No diagnostic-registry, schema, exit-code, or scope-lock changes.
- **Pre-existing test cleanup.** [tests/unit/scripts/test_file_bug_report.py](tests/unit/scripts/test_file_bug_report.py) and [tests/unit/scripts/test_package_bug_report.py](tests/unit/scripts/test_package_bug_report.py) were pointing at `scripts/*.py` at the repo root; the canonical location after the `json_kit/` dissolution (0.3.0) is `schemas/scripts/*.py`. Two `gh issue create` tests that depend on a `#!/bin/sh` `gh` stub now skip cleanly on Windows. Result: 7 pre-existing failures → 5 pass + 2 skip.

### 0.5.1 — 2026-04-27

- **`$schema` IDs are now short, path-agnostic identifiers.** The `$schema` field in all Chopper JSONs changed from slash-delimited paths (`chopper/base/v1`, `chopper/feature/v1`, `chopper/project/v1`) to short identifiers (`base-v1`, `feature-v1`, `project-v1`). Chopper resolves each ID by looking it up in `schemas/` relative to its own install root — no file-system path is encoded in the value, so the JSONs work regardless of where the repo is checked out or where `schemas/` is on disk. The schema files themselves (`base-v1.schema.json`, `feature-v1.schema.json`, `project-v1.schema.json`) were updated in lockstep (`$id` and `const`). All examples, test fixtures, tests, docs, and the Chopper Agent were updated in the same pass.

### 0.5.0 — 2026-04-25

- **Tool-command pool (`TI-01`).** Real EDA domains emit thousands of `TW-02 unresolved-proc-call` warnings per trim run, one per vendor-tool-command call (`get_app_var`, `set_dont_touch`, `report_timing`, …), burying genuine hits on actually-missing procs. Chopper now ships a domain-agnostic registry of known external tool-command names, seeded with PrimeTime (~850 commands at `src/chopper/data/tool_commands/pt.commands`) and extensible via the repeatable CLI flag `--tool-commands <path>`. Matches against the pool are reported as the new info-severity diagnostic `TI-01 known-tool-command` (exit 0, not counted against `--strict`). Architecture Doc §3.10 and **FR-44** specify the contract.
- **`chopper validate --features` accepts directories.** For `validate` only, any entry in the `--features` comma-separated list may be a directory path; it expands in place to the sorted, non-recursive set of its immediate `*.json` children. Files and directories may be mixed freely. `chopper trim` and `--project` still require explicit per-file paths so the ordered feature sequence recorded in audit artifacts stays unambiguous. Added as **FR-43** in the architecture doc. Intended use: CI/regression pipelines that need to validate an entire `jsons/features/` tree in one command.

### 0.4.0 — 2026-04-24

- **Historical note.** This release originally added a temporary protocol surface that was fully removed in 4.0.0. The 4.0.0 changelog entry above is the current contract.

### 0.3.3 — 2026-04-24

- **`options.generate_stack` end-to-end tested (D1 + D2).** The F3 stack-file generation path now has full integration-test coverage: a new `tests/fixtures/stages_domain/` fixture exercises a three-stage domain with `generate_stack: true`, and four new integration tests in `tests/integration/test_runner_localfs_e2e.py` verify the full P0→P7 pipeline on real disk — dry-run manifest shape, live-trim file emission, stack-file content (N/J/L/D/R correctness), and audit-bundle recording of `.stack` entries. Eight unit tests in `tests/unit/orchestrator/test_runner.py` cover the same paths via `InMemoryFS`. The `(new, untested)` label and pilot-user callouts have been removed from `JSON_AUTHORING_GUIDE.md`, `README.md`, and the companion agent memory; `options.generate_stack` is now a fully supported and tested feature.

### 0.3.2 — 2026-04-24

- **Companion consolidation + discoverability.** The former `domain-analyzer` agent was absorbed into the [Chopper Agent](.github/agents/chopper-agent.agent.md), now the **single user-facing agent** for anything Chopper-related. The companion card gained explicit **Operating Modes** (`analyze-only` vs `full-loop`), a **Q1–Q5 Discovery Protocol** for unfamiliar codebases, **JSON Templates & Checklists**, a **Schema Error → Fix Mapping** table, a **Bootstrapping-a-new-domain** playbook, and named **Common CLI Workflows** (Bisect / Compare-two-runs / Prove-JSON-safe / Explain-a-diagnostic). The greeting is now a tier-2 menu (Tier 1 "where are you starting from?" table → Tier 2 full capability list).
- **Prompt library.** New [`.github/prompts/`](.github/prompts/) directory with six ready-to-use starting points: `bootstrap-domain`, `explain-last-run`, `why-was-dropped`, `validate-my-jsons`, `bisect-feature-breakage`, `report-chopper-bug`.
- **USER_MANUAL cross-ref.** [doc/USER_MANUAL.md](doc/USER_MANUAL.md) now points at the companion at the top of the Operating Tasks section.
- No runtime, schema, diagnostic-registry, or scope-lock changes — agents, docs, and version files only.

### 0.3.1 — 2026-04-24

- **First-time-user setup hardened across all four shells.** [setup.ps1](setup.ps1), [setup.sh](setup.sh), [setup.csh](setup.csh), and [setup.bat](setup.bat) now (1) detect stale / relocated `.venv` directories by comparing the venv's reported `sys.prefix` against the script directory and recreate automatically on mismatch, (2) invoke pip exclusively through `python -m pip` so a stale `pip.exe` shim (the common failure mode when a `.venv` is copied from another repo) can no longer block the install, (3) unconditionally regenerate the `chopper` console-script launcher on every run via `pip install -e . --force-reinstall --no-deps`, and (4) smoke-test `chopper --help` and report `Chopper : <version> (launcher OK)` in the "Setup complete" banner. The result: `git clone … && . setup.ps1 && chopper --help` now works end-to-end without manual recovery steps.
- The `chopper` command is already wired as a standard `[project.scripts]` console entry point in [pyproject.toml](pyproject.toml), so activating the venv puts `chopper` directly on `PATH` — the setup hardening above ensures the shim that gets there is always valid.

### 0.3.0 — 2026-04-24

- **F3 stack-file auto-generation (`options.generate_stack`).** Base JSON gains an optional `options.generate_stack` boolean (default `false`). When enabled alongside `stages`, the generator (P5b) emits one `<stage>.stack` per resolved stage alongside `<stage>.tcl`, using the N/J/L/D/I/O/R format documented in the architecture doc §3.6. Dependency-line derivation follows `dependencies` > `load_from` > bare `D`. Generated `.stack` files participate in `compiled_manifest.json`, the trimmer skip-set, and the audit bundle exactly like `.tcl` run scripts.
...it/` dissolved.** Now that the Chopper runtime has shipped, the standalone authoring kit was absorbed into the main repository: schemas moved to `schemas/`, examples to `examples/`, the authoring guide to [technical_docs/JSON_AUTHORING_GUIDE.md](technical_docs/JSON_AUTHORING_GUIDE.md), the domain-analyzer agent to `.github/agents/domain-analyzer.agent.md` (later absorbed into the Chopper Agent in 0.3.2), and the validator to [scripts/validate_jsons.py](scripts/validate_jsons.py). The kit's private version file was folded into the main package metadata.
- Authoring guide §2.1 added; example 03 and example 07 opted in to `generate_stack` for demonstration.

### 0.2.0 — 2026-04-23

- Release channel and packaging metadata stabilized; canonical version surface consolidated into [pyproject.toml](pyproject.toml) as the single source of truth.
- Documentation suite modernized: user manual expanded with detailed JSON usage and invocation examples; audience-targeted formatting pass across all technical guides.
- Repository rebranded to **Chopper** (from earlier internal name), with all schemas, help text, and audit artifacts updated in lockstep.

### 0.1.x — Early Buildout

- **CLI surface complete.** Three subcommands — `validate`, `trim`, `cleanup` — with `--project`, `--base`, feature selection, `--dry-run`, and `--strict` all wired through.
- **Pre- and post-trim validators.** `validate_pre()` and `validate_post()` enforce schema, structural, and cross-validation invariants; `VE-*` / `VW-*` / `VI-*` families registered and emitted.
- **Trimmer + generator path.** File-level, proc-level, and stage-based trimming land; `GeneratorService` emits `<stage>.tcl` run files from resolved stages.
- **Parser hardening.** Tokenizer state machine and proc extractor cover the Tcl edge cases catalogued in [technical_docs/IMPLEMENTATION.md (parser section)](technical_docs/IMPLEMENTATION.md) and the `tests/fixtures/edge_cases/` corpus.
- **Audit bundle.** Every run (success or failure) writes `.chopper/` with `compiled_manifest.json`, `dependency_graph.json`, `trim_report.json`, `trim_report.txt`, and JSON-Lines event log.
- **JSON Kit extraction (superseded in 0.3.0).** Base/feature/project schemas, validator, authoring guide, and eleven worked examples were packaged as a standalone kit under `json_kit/` so domain owners could author JSON before the runtime shipped. The kit was absorbed into the main repository in 0.3.0.
- **Agentic workflow.** Chopper Buildout Agent and Chopper Agent shipped with the repository, each backed by a local memory file under `.github/agent_memory/`.
- **Spec-first foundation.** Eight-phase pipeline (P0–P7), R1 merge rules, diagnostic-code registry, and risks/pitfalls catalogue established as the authoritative basis for every subsequent change.

---

## Acknowledgments

Chopper was inspired by and builds on the foundational thinking behind:

- **SNORT** by Mike McCurdy ([michael.mccurdy@intel.com](mailto:michael.mccurdy@intel.com)) — domain state detection and trim-lifecycle design
- **FlowBuilder** by Stelian Alupoaei ([stelian.alupoaei@intel.com](mailto:stelian.alupoaei@intel.com)) — stage-driven flow modeling and the run-file generation concept
