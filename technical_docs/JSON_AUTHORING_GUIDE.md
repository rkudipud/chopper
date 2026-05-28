# Chopper JSON Authoring Guide

**Standalone edition — no Chopper runtime required.**  
Use this guide to author and validate all three Chopper JSON types before Chopper is available.

---

## Contents

1. [The Three JSON Types](#1-the-three-json-types)
2. [Stack File Semantics — N J L I O D R](#2-stack-file-semantics)
3. [Base JSON — Complete Field Reference](#3-base-json)
4. [Feature JSON — Complete Field Reference](#4-feature-json)
5. [Project JSON — Complete Field Reference](#5-project-json)
6. [Feature Dependency Chains (depends_on)](#6-feature-dependency-chains)
7. [Flow Actions Reference](#7-flow-actions-reference)
8. [Authoring Rules and Constraints](#8-authoring-rules-and-constraints)
9. [Decision Guide — Which JSON to Use](#9-decision-guide)
10. [Validation Workflow](#10-validation-workflow)
11. [Common Mistakes](#11-common-mistakes)

---

## 1. The Three JSON Types

| JSON Type | Schema `$id` | Purpose |
|-----------|-------------|---------|
| **Base** | `base-v1` | Defines the minimal viable flow for a domain. Every project needs exactly one base. |
| **Feature** | `feature-v1` | Extends or removes elements of the base via file/proc/stage selections. Zero or more features per project. |
| **Project** | `project-v1` | Selects and orders one base and zero or more features for a specific trim run. |

**Relationship:**

```
project.json
  └── jsons/base.json                           (one, required)
  └── jsons/features/feature_a.feature.json    (optional)
  └── jsons/features/feature_b.feature.json    (optional)
  └── jsons/features/feature_c.feature.json    (optional)
```

Feature order in the project file is **authoritative for everything** — F1 (file trimming), F2 (proc trimming), and F3 (flow_actions). The base is layer 0; each entry of `project.features[]` is the next layer in declared order. Layers are folded as an **ordered overlay**: the last layer that mentions a file or proc wins. Reordering features can therefore change which files and procs survive (an earlier feature's include may be cancelled by a later feature's exclude, and vice versa). `depends_on` validation also uses this order: each prerequisite must appear earlier in the list.

### Starting from `examples/`

Use the example folders as templates, not as production-ready inputs. Pick the closest pattern, copy it into your domain root, and then replace every placeholder.

| Need | Example folder |
|-----------|-------------|
| File trimming only | `examples/01_base_files_only/` |
| Proc trimming only | `examples/02_base_procs_only/` |
| Stage JSON that drives generated `<stage>.tcl` files | `examples/03_base_stages_only/` |
| Full starting point | `examples/07_base_full/` |
| Base plus one feature | `examples/08_base_plus_one_feature/` |
| Feature chains with `depends_on` | `examples/10_chained_features_depends_on/` |
| Aggregate scheduler stack (`generate_stack`) | `examples/12_base_with_aggregate_stack/` |
| Aggregate + per-stage standalone stack | `examples/13_base_with_standalone_stack/` |

Recommended sequence:

1. Copy `jsons/` from the nearest example into `<domain_root>/`.
2. Copy `project.json` too if you want project mode.
3. Change every `domain`, path, proc, and stage field to match the real domain.
4. Validate with `python schemas/scripts/validate_jsons.py <domain_root>/` before you run Chopper.

---

## 2. Stack File Semantics

**Stages are optional.** Chopper supports two workflows:

1. **Generated Script Workflow (with stages):** Users define stages in JSON, and Chopper generates `<stage>.tcl` run scripts.
2. **Manual Workflow (without stages):** Users skip the `stages` section entirely. Chopper will still trim files and procs as requested (F1 + F2), but will not generate run files (F3).

**You are not required to define stages.** This section describes the optional stack-file mapping for users who choose to use stages.

When stages are defined in a base or feature JSON, Chopper generates one `<stage>.tcl` run script per final stage. If your environment also requires a scheduler stack file, author that file manually from the same stage metadata. The mapping is direct and deterministic:

| JSON field | Stack line | Example |
|------------|-----------|---------|
| `name` | `N <name>` | `N run_analysis` |
| `command` | `J <command>` | `J -tool run_script -B BLOCK -T run_analysis` |
| `exit_codes` | `L <codes>` | `L 0 3 5` |
| `dependencies` | `D <deps>` | `D run_analysis` |
| `inputs` | `I <artifact>` | `I $ward/runs/BLOCK/TECH/release/latest/finish/design.v.gz` |
| `outputs` | `O <artifact>` | `O $ward/runs/BLOCK/TECH/my_domain/outputs/result.rpt` |

**Example — direct translation from stack file to JSON stage:**

Stack file (`run_analysis.stack`):
```
N run_analysis
J -tool run_script -B BLOCK -T run_analysis
L 0 3 5
D

N promote_run_analysis
J tool_wrapper $ward/global/my_domain/promote.tcl -B BLOCK -T run_analysis -force
D run_analysis
```

Equivalent JSON stage definition:
```json
{
  "name": "run_analysis",
  "load_from": "",
  "command": "-tool run_script -B BLOCK -T run_analysis",
  "exit_codes": [0, 3, 5],
  "steps": ["source core_procs.tcl", "run_verify"]
}
```

> **What Chopper emits:**  
> By default, Chopper writes only the generated `<stage>.tcl` file and leaves stack-file authoring to you. Set `options.generate_stack: true` in the base JSON to additionally emit one aggregate `<basename(domain_root)>.stack` containing one record per stage — record order is the **topological sort** of the stage dependency graph (`dependencies` ∪ `{load_from}` edges); see the auto-generation subsection below. For wrapper stages whose `steps` are themselves a verbatim scheduler record, set `standalone_stack: true` on the stage to emit `<stage>.stack` **instead of** `<stage>.tcl` (the standalone stack becomes the stage's sole driver).
>
> **Note on `load_from` vs `dependencies`:**  
> `load_from` feeds the generated `<stage>.tcl` script (data sourcing, `ivar(src_task)` semantics). It is **not** the stack `D` line.  
> `dependencies` is the explicit stack `D` line and controls scheduler execution order.
>
> **Note on optional stack files:** If you are not using stages, keep your stack file workflow separate. Chopper will still trim your domain files and procs (F1 + F2) when you provide base/feature JSONs.

### 2.1 Auto-generation via `options.generate_stack`

Set `"generate_stack": true` in the base JSON `options` block to have Chopper assemble **one** aggregate scheduler stack file at the domain root named `<basename(domain_root)>.stack` (filename sourced from the runtime domain-root basename — there is no JSON field for it). The file contains a single Intel header followed by one record per resolved stage, with records separated by a single blank line. **Record order is the topological sort of the stage dependency graph**, *not* authored order — see the ordering rules below. The flag has no effect when the base declares no stages.

```json
{
  "$schema": "base-v1",
  "domain": "my_domain",
  "options": { "generate_stack": true },
  "stages": [ ... ]
}
```

**Emitted format (one aggregate file per domain):**

```
####################################################################################################
# INTEL CONFIDENTIAL
# Copyright (c) <YEAR> Intel Corporation
# ... (full Intel notice; see ARCHITECTURE.md §6.6.1)
####################################################################################################

# Chopper-generated stack: <stage1.name>
N <stage1.name>
J <stage1.command>     # omitted when command is empty
L <c1> <c2> ...        # omitted when exit_codes is empty
I <input>              # one line per entry; block omitted when empty
O <output>             # one line per entry; block omitted when empty
D <dependency>         # always emitted; see derivation rules below
R parallel             # only when run_mode == "parallel"; omitted for serial

# Chopper-generated stack: <stage2.name>
...
```

Per-record line order is fixed: `N` → `J` → `L` → `I` → `O` → `D` → (optional `R parallel`). The `R` line is **omitted** for the default `serial` mode (matches the production stack-file convention — no reference `.stack` file emits an `R` line for serial stages). The Intel header appears once at the top of the file regardless of how many records follow. The provenance line (`# Chopper-generated stack: <name>`) precedes every record so audit consumers can correlate.

**`D`-line derivation (in order):**

1. If `dependencies` is non-empty → one `D <dep>` line per entry, in authored order.
2. Else if `load_from` is non-empty → a single `D <load_from>` line.
3. Else → a bare `D` line (first stage, no predecessor).

The aggregate `<domain>.stack` participates in `compiled_manifest.json`, the trimmer skip-set, and the audit bundle exactly like generated `.tcl` files (treatment `GENERATED`, reason `fi-literal`). If a stage in the aggregate has an empty `command` (the `J` line is omitted), Chopper emits `VW-23 stack-stage-empty-command` — the scheduler will almost certainly reject that record at runtime.

**Record ordering — topological sort.** Records in the aggregate stack are emitted in topological order over the stage dependency graph. For each stage `S`, the incoming edges are the union of (1) `P → S` for every `P` in `S.dependencies` and (2) `S.load_from → S` when `S.load_from` is non-empty. Ordering uses Kahn's algorithm with **authored position** as the tiebreaker: among stages of equal in-degree at any step, the one declared earliest in the resolved `stages` array wins. This is fully deterministic and preserves authoring intent for unrelated subgraphs.

**Cycles and dangling references are hard errors** — they fire whenever `stages` is non-empty, regardless of `generate_stack`:

* `VE-30 stage-dependency-cycle` — the graph contains a cycle (including a self-loop where a stage names itself in `dependencies` or `load_from`). Compilation aborts with exit 1. The diagnostic names the cycle in the order discovered.
* `VE-31 stage-dependency-unresolved` — a `dependencies` entry or `load_from` reference names a stage that does not exist in the resolved flow. The diagnostic names the referrer, the unresolved name, and which field carried it.

Break cycles by removing the offending edge; resolve unresolved references by defining the missing stage or correcting the name.

### 2.2 Per-stage standalone stacks via `standalone_stack`

A stage may set `"standalone_stack": true` (default `false`) to emit a `<stage>.stack` whose body is the Intel header followed by the authored `steps` verbatim — no N/J/L/D record derivation. This is the right surface for wrapper stages whose `steps` field already encodes a scheduler-format record (ECO hooks, scheduler-only sub-flows).

The flag **suppresses** that stage's `<stage>.tcl`: the standalone stack becomes the stage's sole driver. The stage is still included as a derived record in the aggregate `<domain>.stack` when `options.generate_stack` is on, and its `dependencies` / `load_from` edges still participate in the topological ordering. The four combinations:

| `options.generate_stack` | stage `standalone_stack` | Artifacts emitted for this stage |
|---|---|---|
| `false` | `false` | `<stage>.tcl` |
| `false` | `true` | `<stage>.stack` (verbatim `steps`) — **no `<stage>.tcl`** |
| `true` | `false` | `<stage>.tcl` + record in `<domain>.stack` (topological order) |
| `true` | `true` | `<stage>.stack` (verbatim `steps`) + record in `<domain>.stack` — **no `<stage>.tcl`** |

Working example: a stage that wraps an external scheduler invocation —

```json
{
  "name": "eco_apply_patch",
  "load_from": "",
  "standalone_stack": true,
  "steps": [
    "N eco_apply_patch",
    "J -xt vw Ifc_shell -B BLOCK -F apr_fc -T apply_patch -output_log_file logs/fc.apply_patch.log -f $ward/global/snps/fev_formality/utils/targ_synth/run_apply_patch.tcl",
    "D eco_post_synth"
  ]
}
```

Produces a `eco_apply_patch.stack` containing the Intel header followed by exactly those three lines.

A standalone `<stage>.stack` collision with `files.*` entries or with the aggregate `<domain>.stack` path is reported as `VE-29 standalone-stack-collision`. Aggregate `<domain>.stack` collisions with `files.*` are reported as `VE-28 aggregate-stack-collision`.

---

## 3. Base JSON

### Minimal valid base

```json
{
  "$schema": "base-v1",
  "domain": "my_domain",
  "files": {
    "include": ["setup.tcl"]
  }
}
```

**Rules:**
- `$schema` and `domain` are required.
- At least one of `files`, `procedures`, or `stages` must be present.
- All three sections can coexist.

### Full field reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `$schema` | `"base-v1"` | Yes | Schema identifier (literal string) |
| `domain` | string | Yes | Domain directory name (e.g., `my_domain`) |
| `owner` | string | No | Team responsible for this base |
| `vendor` | string | No | Vendor (e.g., `synopsys`, `cadence`) |
| `tool` | string | No | Tool name (e.g., `primetime`, `innovus`) |
| `description` | string | No | Human-readable summary |
| `options.cross_validate` | boolean | No | Cross-validate F3 output. Default: `true` |
| `options.indent` | boolean | No | Run the P5c Tcl indentation pass on `PROC_TRIM`/`GENERATED` outputs. Default: `false` (skip indentation entirely). |
| `options.generate_stack` | boolean | No | Emit aggregate `<basename(domain_root)>.stack` with one record per stage (see §2.1). Default: `false` |
| `files.include` | string[] | No* | Glob patterns to include |
| `files.exclude` | string[] | No | Glob patterns to exclude |
| `procedures.include` | procEntry[] | No* | Proc-level includes |
| `procedures.exclude` | procEntry[] | No | Proc-level excludes |
| `stages` | stageDefinition[] | No* | Ordered stage definitions |

*At least one of `files`, `procedures`, or `stages` required.

### `procEntry` structure

```json
{
  "file": "procs/core_procs.tcl",
  "procs": ["run_setup", "load_design"]
}
```

- `file`: domain-relative path (forward slashes, no `..`, no `//`)
- `procs`: non-empty array of proc names

### `stageDefinition` structure

```json
{
  "name": "run_analysis",
  "load_from": "",
  "command": "-tool run_script -B BLOCK -T run_analysis",
  "exit_codes": [0, 3, 5],
  "dependencies": ["setup"],
  "inputs": ["$ward/runs/BLOCK/TECH/release/latest/finish/design.v.gz"],
  "outputs": ["$ward/runs/BLOCK/TECH/my_domain/outputs/result.rpt"],
  "run_mode": "serial",
  "language": "tcl",
  "steps": [
    "source core_procs.tcl",
    "setup_env",
    "run_verify"
  ]
}
```

| Field | Required | Stack line | Notes |
|-------|----------|-----------|-------|
| `name` | Yes | `N` | Unique within domain |
| `load_from` | Yes | — | Data predecessor for generated script; can be empty string |
| `steps` | Yes | — | Ordered step strings written into `<stage>.tcl` |
| `command` | No | `J` | Scheduler job command |
| `exit_codes` | No | `L` | Legal exit codes (integers) |
| `dependencies` | No | `D` | Scheduler dependency (parent task names) |
| `inputs` | No | `I` | Input artifact markers |
| `outputs` | No | `O` | Output artifact markers |
| `run_mode` | No | `R` | `"serial"` (default) or `"parallel"`. Aggregate stack emits `R parallel` only when set to `"parallel"`; serial is implicit. |
| `language` | No | — | `"tcl"` (default) or `"python"` |
| `standalone_stack` | No | — | When `true`, additionally emit `<stage>.stack` with the authored `steps` verbatim (see §2.2). Orthogonal to `options.generate_stack` and to `<stage>.tcl` emission. Default: `false`. |

---

## 4. Feature JSON

### Minimal valid feature

```json
{
  "$schema": "feature-v1",
  "name": "dft",
  "files": {
    "include": ["procs/dft_procs.tcl"]
  }
}
```

**Rules:**
- `$schema` and `name` are required. Everything else is optional.
- `name` must be unique across all features in a project.
- At least one of `files`, `procedures`, or `flow_actions` should be present (otherwise the feature does nothing).

### Full field reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `$schema` | `"feature-v1"` | Yes | Schema identifier |
| `name` | string | Yes | Feature identifier — referenced by `depends_on` and project `features` list |
| `domain` | string | No | Target domain. If set, Chopper warns if mismatched with selected base |
| `description` | string | No | Human-readable summary |
| `depends_on` | string[] | No | Prerequisite feature names (must appear earlier in project) |
| `metadata` | object | No | Documentation fields: `owner`, `tags`, `wiki`, `related_ivars`, `related_appvars` |
| `files.include` | string[] | No | Additional files to include |
| `files.exclude` | string[] | No | Files to remove from the effective include set |
| `procedures.include` | procEntry[] | No | Additional proc-level includes |
| `procedures.exclude` | procEntry[] | No | Proc-level excludes |
| `flow_actions` | flowAction[] | No | Stage modifications (add/remove/replace steps or stages) |

### `metadata` example

```json
{
  "metadata": {
    "owner": "signoff-team",
    "tags": ["dft", "signoff", "pipeline"],
    "wiki": "https://wiki.example.com/dft-feature",
    "related_ivars": ["dft_mode", "scan_enable"],
    "related_appvars": ["dft_app_var_1"]
  }
}
```

---

## 5. Project JSON

### Minimal valid project

```json
{
  "$schema": "project-v1",
  "project": "PROJECT_ABC",
  "domain": "my_domain",
  "base": "jsons/base.json"
}
```

### Full field reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `$schema` | `"project-v1"` | Yes | Schema identifier |
| `project` | string | Yes | Project identifier (e.g., `PROJECT_ABC`) |
| `domain` | string | Yes | Domain identifier — must match base `domain` field |
| `base` | string | Yes | Domain-relative path to the base JSON |
| `owner` | string | No | Project owner |
| `release_branch` | string | No | Git branch for this trim |
| `features` | string[] | No | Feature JSON paths in declared application order. Order is authoritative for F1, F2, **and** F3 under the R1 ordered-overlay model: layers are applied left-to-right and the last layer that mentions a file/proc/step wins. |
| `notes` | string[] | No | Human-readable rationale for feature order |

### Path conventions

All paths in `base` and `features` must be:
- Relative to the domain root (current working directory when Chopper is invoked)
- Forward slashes only
- No `..` traversal
- No double slashes `//`
- No absolute paths

---

## 6. Feature Dependency Chains

`depends_on` declares prerequisite features that must be selected and applied **before** the declaring feature.

### Rules

1. Values in `depends_on` are **feature `name` strings**, not file paths.
2. Each prerequisite must appear in the project `features` list.
3. Each prerequisite must appear **earlier** in the list than the feature declaring the dependency.
4. Chopper validates this at project-level (`VE-15 missing-depends-on-feature` and `VE-16 depends-on-out-of-order`).

### Example — three-level chain

```json
// dft_support.feature.json — no prerequisites
{ "$schema": "feature-v1", "name": "dft_support", ... }

// power_analysis.feature.json — needs dft first
{ "$schema": "feature-v1", "name": "power_analysis", "depends_on": ["dft_support"], ... }

// pipeline_signoff.feature.json — needs both
{ "$schema": "feature-v1", "name": "pipeline_signoff", "depends_on": ["dft_support", "power_analysis"], ... }

// project.json — order must respect all depends_on
{
  "$schema": "project-v1",
  "project": "FULL_SIGNOFF",
  "domain": "my_domain",
  "base": "jsons/base.json",
  "features": [
    "jsons/features/dft_support.feature.json",       // position 1: no deps
    "jsons/features/power_analysis.feature.json",    // position 2: dft_support at 1 ✓
    "jsons/features/pipeline_signoff.feature.json"   // position 3: both above ✓
  ]
}
```

**Invalid ordering** — would fail validation:

```json
"features": [
  "jsons/features/power_analysis.feature.json",    // ERROR: dft_support not yet seen
  "jsons/features/dft_support.feature.json"
]
```

---

## 7. Flow Actions Reference

Flow actions modify the base flow during feature application. All actions go in `flow_actions` array.

### Action types

| Action | Required fields | Description |
|--------|----------------|-------------|
| `add_step_before` | `stage`, `reference`, `items` | Insert steps before a reference step |
| `add_step_after` | `stage`, `reference`, `items` | Insert steps after a reference step |
| `remove_step` | `stage`, `reference` | Remove a step from a stage |
| `replace_step` | `stage`, `reference`, `with` | Replace one step with another |
| `add_stage_before` | `name`, `reference`, `load_from`, `steps` | Insert a new stage before a reference stage |
| `add_stage_after` | `name`, `reference`, `load_from`, `steps` | Insert a new stage after a reference stage |
| `remove_stage` | `reference` | Remove a stage entirely |
| `replace_stage` | `reference`, `with` | Replace a stage with a new definition |
| `load_from` | `stage`, `reference` | Change the data predecessor of a stage |

### `add_stage_after` example

```json
{
  "action": "add_stage_after",
  "name": "dft_check",
  "reference": "main",
  "load_from": "main",
  "command": "-xt vw Imy_shell -B BLOCK -T dft_check",
  "exit_codes": [0, 3],
  "dependencies": ["main"],
  "steps": [
    "source procs/dft_procs.tcl",
    "setup_scan_chains",
    "verify_scan"
  ]
}
```

### `add_step_after` example (step-level targeting)

```json
{
  "action": "add_step_after",
  "stage": "main",
  "reference": "source procs/core_procs.tcl",
  "items": [
    "source procs/dft_procs.tcl"
  ]
}
```

### Instance targeting with `@n`

If a step string appears multiple times, use `@n` to target the nth instance:

```json
{
  "action": "remove_step",
  "stage": "main",
  "reference": "source debug.tcl@2"
}
```

### Optional stage targets with `skip_if_no_stage`

Cross-cutting features often inject steps into stages that may not be loaded in every project composition. By default, targeting an absent stage is a hard error (`VE-05`). To make the injection optional, add `"skip_if_no_stage": true`:

```json
{
  "action": "add_step_after",
  "stage": "eco_pre_synth",
  "reference": "#Anchor for SEQ_CONST_CHECK if enabled\n",
  "items": ["set verification_assume_reg_init None\n"],
  "skip_if_no_stage": true
}
```

**Behaviour:**
- **Stage absent + flag `true`:** Emits `VI-05 flow-action-skipped-no-stage` (info, exit 0), action skipped.
- **Stage present + flag `true`:** Action runs normally (identical to the strict path).
- **Stage absent + flag `false` (default):** Emits `VE-05 missing-action-target` (error, exit 1).
- **Step miss inside a present stage:** Always `VE-05` regardless of the flag. `skip_if_no_stage` softens only the *stage-not-found* path.

**When to use:**
- The action targets a stage created by another feature (not the base).
- The feature is intended to work in partial compositions (user selects only a subset of features).
- Example: `sequential_const_check` injects into `eco_pre_synth` (created by `fm_eco`). When `fm_eco` is not selected, the injection is correctly skipped.

**When NOT to use:**
- The action targets a base stage (always present — no skip needed).
- The action targets a stage created earlier in the same feature (intra-feature chaining — always present by top-to-bottom application).

`skip_if_no_stage` is accepted on every flow_action variant: `add_step_before`, `add_step_after`, `remove_step`, `replace_step`, `add_stage_before`, `add_stage_after`, `remove_stage`, `replace_stage`, `load_from`.

---

## 8. Authoring Rules and Constraints

### Paths and Glob Patterns

**Domain-relative paths:** All paths must be relative to the domain root (current working directory when Chopper is invoked).

**Path rules:**
- Always use forward slashes: `procs/core_procs.tcl` not `procs\core_procs.tcl`
- Never use `..` traversal: `../../other_domain/file.tcl` is rejected
- Never use absolute paths: `/home/user/file.tcl` is rejected
- Never use double slashes: `procs//core.tcl` is rejected

**Glob patterns in `files.include` and `files.exclude`:**

Glob patterns support three special characters to match multiple files:

| Pattern | Matches | Example | Result |
|---------|---------|---------|--------|
| `*` | Any number of characters **except path separator** (`/`) | `procs/*.tcl` | `procs/core_procs.tcl`, `procs/rules.tcl` (but NOT `procs/sub/file.tcl`) |
| `?` | Exactly one character **except path separator** (`/`) | `rule?.fm.tcl` | `rule1.fm.tcl`, `rule2.fm.tcl` (but NOT `rule12.fm.tcl`) |
| `**` | Any number of directories and subdirectories (including none) | `reports/**` | `reports/base.txt`, `reports/sub/detail.txt`, `reports/a/b/c/file.txt` |

**Glob pattern rules:**
- Glob patterns work with `files.include` and `files.exclude` only.
- Literal file paths (no special characters) always refer to exact files and are also supported in `files.include`.
- Literal paths take precedence over excludes (Decision 5).
- When a `*` or `?` pattern expands to zero files, it is silently ignored (no error).
- When a `**` pattern expands to zero files, it is silently ignored (no error).
- All glob pattern expansions are normalized, deduplicated, and sorted before compilation.
- Patterns are case-sensitive.

**Mixing literal and glob:**
```json
{
  "files": {
    "include": [
      "vars.tcl",                    // literal file (must exist)
      "procs/*.tcl",                 // glob: all .tcl files in procs/ directly
      "rules/**/*.fm.tcl",           // glob: all .fm.tcl files in rules/ and subdirectories
      "templates/base/**"            // glob: all files in templates/base/ and subdirectories
    ],
    "exclude": [
      "procs/debug/*.tcl",           // glob: exclude debug Tcl files
      "rules/**/obsolete/**"         // glob: exclude any obsolete subdirectories anywhere in rules/
    ]
  }
}
```

**Important:**
- Literal paths in `files.include` survive even if they match an `files.exclude` pattern.
- Wildcarded includes in `files.include` are pruned by matching `files.exclude` patterns (normal set subtraction).
- Glob expansion happens **before** conflict rules are applied.


### Arrays

- `files.include` / `files.exclude`: `minItems: 1` — never leave empty arrays
- `procedures.include` / `procedures.exclude`: `minItems: 1`
- `procedures[*].procs`: `minItems: 1` — use `files.include` for whole-file inclusion
- `stages`: `minItems: 1`
- `flow_actions`: `minItems: 1`
- `dependencies`, `exit_codes`, `inputs`, `outputs`, `steps`: all `minItems: 1`
- `depends_on`: `minItems: 1`

**Correct:**
```json
"dependencies": ["setup"]
```

**Wrong — will fail schema validation:**
```json
"dependencies": []
```

### Merge and conflict semantics (when Chopper runs)

**F1/F2/F3 — Ordered Overlay (later layer wins):**
1. Within a single layer, literal `files.include` beats matching `files.exclude`; glob `files.include` is pruned by matching `files.exclude` (set subtraction). Same-layer FI+FE subtraction is intentional and does not raise `VE-27` by itself.
2. Across layers, the **base is layer 0** and each entry of `project.features[]` is the next layer in declared order. Layers are folded left-to-right and the last layer that mentions a file/proc/step **wins**.
3. A later layer's `files.exclude` / `procedures.exclude` can therefore remove content contributed by an earlier layer; a later layer's `files.include` / `procedures.include` can re-add content removed by an earlier layer; and a later layer's `flow_actions` see the cumulative result of all preceding layers.
4. Every transition that actually changes a prior decision (cancelled include, removed proc, downgraded whole-file include) emits `VW-21 layer-shadowed` with `(layer, prior_layer, action)` provenance recorded in the audit bundle.
5. `depends_on` ordering is validated: each prerequisite feature must appear earlier in the `features` list than the dependent feature.

> **F1/F2/F3 Aggregation — Ordered Overlay, Later Layer Wins**
> All `files.include`, `files.exclude`, `procedures.include`, `procedures.exclude`, and `flow_actions` selections are folded as an ordered overlay: base first, then each feature in declared order. Reordering features in the project file **does** change which files and procs are included in the trimmed domain, because a later layer can cancel or replace an earlier layer's contribution. The compiler emits `VW-21 layer-shadowed` for every transition that actually changes a prior decision.
>
> **Trace is logging-only — it does not copy procs.**
> Chopper's P4 trace expansion walks your `procedures.include` set to build a call tree (`dependency_graph.json`) and emit `TW-*` warnings. Traced callees appear in the call tree and in `trim_report.json`, but **only procs explicitly listed in `procedures.include`** (or whole-file-included via `files.include`) by the winning layer are copied into the trimmed domain. Example: if you list `foo` and `foo` calls `bar`, `foo` is copied and `bar` is logged. To keep `bar`, list it explicitly. This is why `procedures.exclude` never needs to "hide" traced callees — they were never going to be copied.

**Per-file input interaction matrix:**

Chopper has four input sets per file: FI (`files.include`), FE (`files.exclude`), PI (`procedures.include`), PE (`procedures.exclude`). Authors must choose one proc-selection model per file:

| Model | Input | Meaning | Surviving procs |
|---|---|---|---|
| **Include-list** | PI | "Keep only these procs" | PI procs from this file |
| **Exclude-list** | PE | "Keep the file but remove these procs" | All procs minus PE procs |

| # | FI | FE | PI | PE | Treatment | Surviving procs | Warning |
|---|---|---|---|---|---|---|---|
| 1 | — | — | — | — | `REMOVE` | — | — |
| 2 | ✓ | — | — | — | `FULL_COPY` | all | — |
| 3 | — | ✓ | — | — | `REMOVE` | — | — |
| 4 | ✓ | ✓ | — | — | `FULL_COPY` (literal) / `REMOVE` (glob) | all / — | — |
| 5 | — | — | ✓ | — | `PROC_TRIM` | PI only | — |
| 6 | — | — | — | ✓ | `PROC_TRIM` | all − PE | — |
| 7 | — | — | ✓ | ✓ | `PROC_TRIM` | PI only (PE ignored) | `VW-12` |
| 8 | ✓ | — | ✓ | — | `FULL_COPY` | all (PI redundant) | `VW-09` |
| 9 | ✓ | — | — | ✓ | `PROC_TRIM` | all − PE | — |
| 10 | ✓ | — | ✓ | ✓ | `PROC_TRIM` | all − PE (PI redundant with FI) | `VW-09` |
| 11 | — | ✓ | ✓ | — | `PROC_TRIM` | PI only (FE overridden) | — |
| 12 | — | ✓ | — | ✓ | `REMOVE` | — | `VW-11` |
| 13 | — | ✓ | ✓ | ✓ | `PROC_TRIM` | PI only (PE+FE overridden) | `VW-12` |
| 14 | ✓ | ✓ | ✓ | — | `FULL_COPY` (literal) | all (PI redundant) | `VW-09` |
| 15 | ✓ | ✓ | — | ✓ | `PROC_TRIM` (literal) / `REMOVE` (glob) | all − PE / — | — |
| 16 | ✓ | ✓ | ✓ | ✓ | `PROC_TRIM` (literal FI) / `PROC_TRIM` (glob-only) | all − PE / PI only | `VW-09` / `VW-12` |

**Key rules:**
- **PE downgrades FULL_COPY:** FI + PE → `PROC_TRIM` (cases 9 and 10; literal side of 15 and 16). 100 procs minus 4 PE = 96 survive.
- **FE + PE = both remove:** neither says "keep" → file removed (case 12). Use PE alone to keep the file.
- **PI wins over PE only without a whole-file FI signal:** same file in PI and PE with no FI keeps PI and ignores PE (cases 7 and 13). With FI + PI + PE, PI is redundant and PE qualifies the FI contribution.
- **PI overrides FE:** PI forces file survival regardless of FE (cases 11, 13).
- **FI + PI (no PE) stays FULL_COPY:** PI is redundant on a fully included file (cases 8, 14).

**Behavior quick-reference:**

| Author intent | JSON shape | Result |
|---|---|---|
| Keep only listed files | `files.include: ["a.tcl"]` | `a.tcl` survives; unnamed files are removed. |
| Keep all files except a list | `files.include: ["**"]`, `files.exclude: [...]` | Chopper starts from every file under the domain, then removes paths matched by `files.exclude`. |
| Exclude-only file list | `files.exclude: [...]` | No file-level keep signal exists; under default-exclude, live trim can rebuild an almost empty domain. Add `files.include: ["**"]` for a negative-list trim. |
| Literal include plus matching exclude | `files.include: ["debug_old.tcl"]`, `files.exclude: ["debug*.tcl"]` | `debug_old.tcl` survives; literal FI always wins. |
| Glob include plus matching exclude | `files.include: ["*.tcl"]`, `files.exclude: ["debug*.tcl"]` | The glob-expanded include list is pruned; `debug*.tcl` matches are removed from that list. This same-layer subtraction is valid and does not trigger `VE-27`. |
| Keep only certain procs | `procedures.include` | File becomes `PROC_TRIM`; only PI procs survive from that file. |
| Keep file minus some procs | `procedures.exclude` | File becomes `PROC_TRIM`; all parsed procs except PE procs survive. |
| File exclude plus proc exclude on the same file | `files.exclude` + `procedures.exclude` | Same-source contradiction; the source contributes nothing for the file and emits `VW-11`. |
| Feature tries to remove a base file | Base includes file, a later feature excludes file | Feature is the later layer under R1 ordered overlay; the file is removed and `VW-21 layer-shadowed` records the transition. |

### Proc call tracing workflow for JSON curation

When deciding `procedures.include`, `procedures.exclude`, `files.include`, and `files.exclude`, build a proc call tree first and review a generated trace log.

**Recommended process:**
1. Identify entry procs from stage scripts or top-level run scripts.
2. Traverse proc-to-proc calls and build call edges.
3. Mark each proc as reachable or unreachable from the selected roots.
4. Group results per file and classify unresolved calls.
5. Author JSON include/exclude entries from this evidence.

**Interactive checkpoints (required for curation quality):**
1. Ask user for top-level domain files/directories before tracing.
2. Ask user which top-level files are authoritative entry points.
3. If user points to a proc file, trace from every proc in that file across other files.
4. Show inventory and trace log, then ask user to confirm/correct classification before writing final JSON decisions.

**EDA command vs proc disambiguation:**
- Treat Synopsys/Cadence shell and app commands as external commands, not proc edges.
- Add call-tree edges only when callee resolves to a discovered proc definition.
- Keep uncertain tokens in unresolved/external review list and confirm with user before include/exclude decisions.

**Generated log template:**

```text
PROC TRACE LOG
roots:
  - <entry_proc>

edges:
  - <caller> -> <callee>

unresolved:
  - <missing_or_external_proc>

files:
  - <path/to/file.tcl>
    defined: [<p1>, <p2>]
    reachable: [<p1>]
    unreachable: [<p2>]
```

**How to convert trace results into JSON:**
- Reachable core procs: add to `procedures.include`.
- Reachable scenario-specific procs: place in the relevant feature `procedures.include`.
- Unreachable debug/deprecated procs in needed files: add to `procedures.exclude`.
- Files containing only unreachable legacy/debug procs: add to `files.exclude`.
- Files with predominantly reachable procs used across projects: add to base `files.include`.

This trace-first workflow improves explainability for users and speeds up authoring by making include/exclude decisions auditable.

### Stage naming

- Stage `name` values must be unique within the compiled flow
- Feature `add_stage_*` introduces new names — ensure no collision with base stage names
- `reference` in `add_stage_after` / `add_stage_before` must match an existing stage name

---

## 9. Decision Guide

```
Does the domain have existing stack files?
  YES → Extract N/J/L/D/I/O → Put in base.stages (or feature flow_actions)
  NO  → Skip stages section; use files/procedures only

Do you want file-level trimming?
  YES → Add files.include (and optionally files.exclude) to base or feature
  NO  → Skip files section

Do you need proc-level granularity?
  YES → Add procedures.include (procs that MUST survive) and/or procedures.exclude (procs to remove)
  NO  → Rely on file-level trimming only

Does the change apply to ALL projects?
  YES → Put it in base JSON
  NO  → Create a feature JSON

Is the feature optional or project-specific?
  YES → It is a feature
  NO  → It belongs in the base

Does feature A require feature B to be applied first?
  YES → Add depends_on: ["feature_b_name"] to feature A's JSON
  NO  → No depends_on needed

Are you selecting which features to apply for a specific project run?
  YES → Create a project JSON, list base path + ordered feature paths
  NO  → Not needed (single-base-only trim)
```

When using an agent or assistant, the expected task is: inspect the user-provided codebase, help generate `jsons/base.json` and any needed feature JSONs, and then validate them with `schemas/scripts/validate_jsons.py`.

This work should be collaborative. Best UX comes from analyzing the codebase hand-in-hand with the user, showing inventories and trace logs, collecting corrections, and only then finalizing JSON content.

Before broad scanning, ask the user where the domain boundary stops. In most cases this is the current working directory, but do not assume it. Keep inventory, tracing, and recommendations within that user-confirmed boundary.

---

## 10. Validation Workflow

### Step 1 — JSON syntax check

Run any JSON validator or use Python's built-in:

```bash
python -m json.tool jsons/base.json > /dev/null
```

### Step 2 — Schema validation

Use the repository helper script (recommended):

```bash
python schemas/scripts/validate_jsons.py my_domain/
```

Examples:

```bash
python schemas/scripts/validate_jsons.py
python schemas/scripts/validate_jsons.py examples/08_base_plus_one_feature/
```

The script validates every JSON file with recognized `$schema` values and reports `OK`, `ERR`, or `SKIP` per file.

Manual fallback (advanced): install `jsonschema`:

```bash
pip install jsonschema
```

Validate using Python:

```python
import json
import jsonschema

with open("schemas/base-v1.schema.json") as sf:
    schema = json.load(sf)
with open("jsons/base.json") as f:
    instance = json.load(f)

jsonschema.validate(instance, schema)  # raises if invalid
print("Valid!")
```

Or validate all three together:

```python
import json, jsonschema, pathlib

schema_dir = pathlib.Path("schemas")  # relative to the Chopper repo root
schemas = {
    "base-v1":    json.load(open(schema_dir / "base-v1.schema.json")),
    "feature-v1": json.load(open(schema_dir / "feature-v1.schema.json")),
    "project-v1": json.load(open(schema_dir / "project-v1.schema.json")),
}

for json_file in pathlib.Path(".").rglob("*.json"):
    try:
        data = json.load(open(json_file))
        schema_id = data.get("$schema")
        if schema_id in schemas:
            jsonschema.validate(data, schemas[schema_id])
            print(f"OK  {json_file}")
    except jsonschema.ValidationError as e:
        print(f"ERR {json_file}: {e.message}")
```

### Step 3 — Semantic checks (manual)

These are not enforced by JSON schema but are validated at runtime by Chopper:

| Check | How to verify manually |
|-------|----------------------|
| `depends_on` prerequisites appear earlier in project | Review `features` list order vs each feature's `depends_on` |
| `add_stage_after` reference exists in base | Confirm `reference` value matches a stage `name` in base |
| `add_step_after` reference step exists in stage | Confirm step string appears in base stage's `steps` array |
| Paths resolve within domain root | Ensure no `..` traversal in any path field |
| Stage names unique across compiled flow | Collect all stage names from base + features, check no duplicates |
| Feature `domain` matches base `domain` | If feature has `domain` set, it should match base `domain` |

---

## 11. Common Mistakes

### Mistake 1 — Empty array where minItems:1 is enforced

```json
// WRONG
"dependencies": []

// CORRECT — omit the field if empty, or provide at least one value
"dependencies": ["setup"]
```

### Mistake 2 — `depends_on` with file paths instead of feature names

```json
// WRONG
"depends_on": ["jsons/features/dft_support.feature.json"]

// CORRECT — use the feature's `name` value
"depends_on": ["dft_support"]
```

### Mistake 3 — Wrong ordering in project features

```json
// WRONG — power_analysis declared depends_on dft_support, but dft_support comes after
"features": [
  "jsons/features/power_analysis.feature.json",
  "jsons/features/dft_support.feature.json"
]

// CORRECT
"features": [
  "jsons/features/dft_support.feature.json",
  "jsons/features/power_analysis.feature.json"
]
```

### Mistake 4 — `load_from` and `dependencies` confused

```json
{
  "name": "eco_targ_synth",
  "load_from": "eco_pre_synth",       // script reads from eco_pre_synth
  "dependencies": ["eco_pre_synth"]   // stack D: eco_pre_synth must complete first
}
```

### Mistake 5 — Backslashes in paths

```json
// WRONG — backslashes are rejected
"file": "procs\\core_procs.tcl"

// CORRECT
"file": "procs/core_procs.tcl"
```

### Mistake 6 — Referencing a non-existent stage in a flow action

```json
// WRONG — if base has no stage named "main_verify", this will fail at runtime
{
  "action": "add_stage_after",
  "name": "dft_check",
  "reference": "main_verify"
}

// CORRECT — use the exact stage name from base JSON
{
  "action": "add_stage_after",
  "name": "dft_check",
  "reference": "main"
}
```

### Mistake 7 — Duplicate stage name from feature

```json
// WRONG — if base already has a stage named "setup", adding another "setup" causes a collision
{
  "action": "add_stage_after",
  "name": "setup",   // already exists in base
  "reference": "main"
}

// CORRECT — use a new unique name
{
  "action": "add_stage_after",
  "name": "dft_setup",
  "reference": "main"
}
```
