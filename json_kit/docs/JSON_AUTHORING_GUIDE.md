# Chopper JSON Authoring Guide

**Standalone edition — no Chopper runtime required.**  
Use this guide to author and validate all three Chopper JSON types before Chopper is available.

---

## Contents

1. [The Three JSON Types](#1-the-three-json-types)
2. [Stack File Semantics — N J L D I O](#2-stack-file-semantics)
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
| **Base** | `chopper/base/v1` | Defines the minimal viable flow for a domain. Every project needs exactly one base. |
| **Feature** | `chopper/feature/v1` | Extends, overrides, or removes elements of the base. Zero or more features per project. |
| **Project** | `chopper/project/v1` | Selects and orders one base and zero or more features for a specific trim run. |

**Relationship:**

```
project.json
  └── base.json          (one, required)
  └── feature_a.json     (optional, applied first)
  └── feature_b.json     (optional, applied second)
  └── feature_c.json     (optional, applied third)
```

Features are applied in the order listed in the project file. Later features see the result of earlier ones.

---

## 2. Stack File Semantics — Optional Stage-to-Stackfile Mapping

**Stages are optional.** Chopper supports two workflows:

1. **Generated Script Workflow (with stages):** Users define stages in JSON, and Chopper generates `<stage>.tcl` run scripts. For users who want to inject or modify commands in their scripts, this workflow enables fine-grained control.
2. **Manual Workflow (without stages):** Users skip the `stages` section entirely and create stack files manually. Chopper will trim files and procs as requested (F1 + F2), but will not generate run files (F3).

**You are not required to define stages.** This section describes the optional mapping for users who choose to use stages.

When stages are defined in a base or feature JSON, Chopper can generate run scripts where each JSON stage maps to one run script file and optionally to stack-file nodes. The mapping is direct and deterministic:

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

> **Note on `load_from` vs `dependencies`:**  
> `load_from` feeds the generated `<stage>.tcl` script (data sourcing, `ivar(src_task)` semantics). It is **not** the stack `D` line.  
> `dependencies` is the explicit stack `D` line and controls scheduler execution order.
> 
> **Note on optional stack files:** If you are not using stages, you can manually create stack files without defining them in JSON. Chopper will still trim your domain files and procs (F1 + F2) when you provide base/feature JSONs.

---

## 3. Base JSON

### Minimal valid base

```json
{
  "$schema": "chopper/base/v1",
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
| `$schema` | `"chopper/base/v1"` | Yes | Schema identifier (literal string) |
| `domain` | string | Yes | Domain directory name (e.g., `my_domain`) |
| `owner` | string | No | Team responsible for this base |
| `vendor` | string | No | Vendor (e.g., `synopsys`, `cadence`) |
| `tool` | string | No | Tool name (e.g., `primetime`, `innovus`) |
| `description` | string | No | Human-readable summary |
| `options.cross_validate` | boolean | No | Cross-validate F3 output. Default: `true` |
| `options.template_script` | string | No | Reserved (v1): domain-relative script path. Schema-validated for path safety but not executed in v1. |
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
| `run_mode` | No | `R` | `"serial"` (default) or `"parallel"` |
| `language` | No | — | `"tcl"` (default) or `"python"` |

---

## 4. Feature JSON

### Minimal valid feature

```json
{
  "$schema": "chopper/feature/v1",
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
| `$schema` | `"chopper/feature/v1"` | Yes | Schema identifier |
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
  "$schema": "chopper/project/v1",
  "project": "PROJECT_ABC",
  "domain": "my_domain",
  "base": "my_domain/chopper/base.json"
}
```

### Full field reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `$schema` | `"chopper/project/v1"` | Yes | Schema identifier |
| `project` | string | Yes | Project identifier (e.g., `PROJECT_ABC`) |
| `domain` | string | Yes | Domain identifier — must match base `domain` field |
| `base` | string | Yes | Domain-relative path to the base JSON |
| `owner` | string | No | Project owner |
| `release_branch` | string | No | Git branch for this trim |
| `features` | string[] | No | Ordered feature JSON paths (earlier = lower-priority) |
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
// feature_dft_support.json — no prerequisites
{ "$schema": "chopper/feature/v1", "name": "dft_support", ... }

// feature_power_analysis.json — needs dft first
{ "$schema": "chopper/feature/v1", "name": "power_analysis", "depends_on": ["dft_support"], ... }

// feature_pipeline_signoff.json — needs both
{ "$schema": "chopper/feature/v1", "name": "pipeline_signoff", "depends_on": ["dft_support", "power_analysis"], ... }

// project.json — order must respect all depends_on
{
  "$schema": "chopper/project/v1",
  "project": "FULL_SIGNOFF",
  "domain": "my_domain",
  "base": "chopper/base.json",
  "features": [
    "chopper/features/dft_support.json",       // position 1: no deps
    "chopper/features/power_analysis.json",    // position 2: dft_support at 1 ✓
    "chopper/features/pipeline_signoff.json"   // position 3: both above ✓
  ]
}
```

**Invalid ordering** — would fail validation:

```json
"features": [
  "chopper/features/power_analysis.json",    // ERROR: dft_support not yet seen
  "chopper/features/dft_support.json"
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

1. Explicit `include` always overrides `exclude` at the same granularity
2. Later features override earlier ones for the same element
3. `depends_on` ordering is validated but does not auto-sort features

> **Trace is logging-only — it does not copy procs.**
> Chopper's P4 trace expansion walks your `procedures.include` set to build a call tree (`dependency_graph.json`) and emit `TW-*` warnings. Traced callees appear in the call tree and in `trim_report.json`, but **only procs explicitly listed in `procedures.include`** (or whole-file-included via `files.include`) are copied into the trimmed domain. Example: if you list `foo` and `foo` calls `bar`, `foo` is copied and `bar` is logged. To keep `bar`, list it explicitly. This is why `procedures.exclude` never needs to "hide" traced callees — they were never going to be copied.

**Per-file input interaction matrix:**

Chopper has four input sets per file: FI (`files.include`), FE (`files.exclude`), PI (`procedures.include`), PE (`procedures.exclude`). Authors must choose one proc-selection model per file:

| Model | Input | Meaning | Surviving procs |
|---|---|---|---|
| **Additive** | PI | "Keep only these procs" | PI procs from this file |
| **Subtractive** | PE | "Keep the file but remove these procs" | All procs minus PE procs |

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
| 10 | ✓ | — | ✓ | ✓ | `PROC_TRIM` | PI only (PE ignored) | `VW-12` |
| 11 | — | ✓ | ✓ | — | `PROC_TRIM` | PI only (FE overridden) | — |
| 12 | — | ✓ | — | ✓ | `REMOVE` | — | `VW-11` |
| 13 | — | ✓ | ✓ | ✓ | `PROC_TRIM` | PI only (PE+FE overridden) | `VW-12` |
| 14 | ✓ | ✓ | ✓ | — | `FULL_COPY` (literal) | all (PI redundant) | `VW-09` |
| 15 | ✓ | ✓ | — | ✓ | `PROC_TRIM` (literal) / `REMOVE` (glob) | all − PE / — | — |
| 16 | ✓ | ✓ | ✓ | ✓ | `PROC_TRIM` | PI only | `VW-12` |

**Key rules:**
- **PE downgrades FULL_COPY:** FI + PE → `PROC_TRIM` (case 9). 100 procs minus 4 PE = 96 survive.
- **FE + PE = both remove:** neither says "keep" → file removed (case 12). Use PE alone to keep the file.
- **PI wins over PE:** same file in both → PI takes precedence (cases 7, 10, 13, 16).
- **PI overrides FE:** PI forces file survival regardless of FE (cases 11, 13).
- **FI + PI (no PE) stays FULL_COPY:** PI is additive and redundant on a fully included file (cases 8, 14).

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

---

## 10. Validation Workflow

### Step 1 — JSON syntax check

Run any JSON validator or use Python's built-in:

```bash
python -m json.tool base.json > /dev/null
```

### Step 2 — Schema validation

Install `jsonschema`:

```bash
pip install jsonschema
```

Validate using Python:

```python
import json
import jsonschema

with open("json_kit/schemas/base-v1.schema.json") as sf:
    schema = json.load(sf)
with open("my_domain/chopper/base.json") as f:
    instance = json.load(f)

jsonschema.validate(instance, schema)  # raises if invalid
print("Valid!")
```

Or validate all three together:

```python
import json, jsonschema, pathlib

schema_dir = pathlib.Path("standalone_json_kit/schemas")
schemas = {
    "chopper/base/v1":    json.load(open(schema_dir / "base-v1.schema.json")),
    "chopper/feature/v1": json.load(open(schema_dir / "feature-v1.schema.json")),
    "chopper/project/v1": json.load(open(schema_dir / "project-v1.schema.json")),
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
"depends_on": ["chopper/features/dft_support.json"]

// CORRECT — use the feature's `name` value
"depends_on": ["dft_support"]
```

### Mistake 3 — Wrong ordering in project features

```json
// WRONG — power_analysis declared depends_on dft_support, but dft_support comes after
"features": [
  "chopper/features/power_analysis.json",
  "chopper/features/dft_support.json"
]

// CORRECT
"features": [
  "chopper/features/dft_support.json",
  "chopper/features/power_analysis.json"
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
