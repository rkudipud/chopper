# Chopper User Reference Manual

**Document Type:** User Reference Manual for Chopper v1  
**Audience:** Domain deployment owners, domain maintainers, and feature authors  
**Primary Goal:** Help domain users prepare their codebase, author JSON inputs, run the standard workflow, and troubleshoot common problems  
**Scope:** User-facing behavior only. This manual avoids implementation internals and focuses on what authors and operators need to do.

> Important: The JSON examples in this manual follow the schema files under `schemas/`. If an older design note or example disagrees with this manual, use the schema-valid examples here.

## Table of Contents

1. [Purpose and Audience](#1-purpose-and-audience)
2. [What Chopper Does](#2-what-chopper-does)
3. [Core Concepts](#3-core-concepts)
4. [Before You Start](#4-before-you-start)
5. [Domain Layout and File Placement](#5-domain-layout-and-file-placement)
6. [Choosing the Right Trimming Method](#6-choosing-the-right-trimming-method)
7. [JSON Authoring Rules](#7-json-authoring-rules)
8. [Base JSON Reference](#8-base-json-reference)
9. [Feature JSON Reference](#9-feature-json-reference)
10. [Project JSON Reference](#10-project-json-reference)
11. [Preparing Your Tcl and Domain Files](#11-preparing-your-tcl-and-domain-files)
12. [CLI Command Reference](#12-cli-command-reference)
13. [Recommended End-to-End Workflow](#13-recommended-end-to-end-workflow)
14. [Common Diagnostics and Fixes](#14-common-diagnostics-and-fixes)
15. [Authoring Checklists](#15-authoring-checklists)
16. [Appendix A: JSON Configuration Templates](#16-appendix-a-json-configuration-templates)

## 1. Purpose and Audience

This manual is for the people who own or curate one tool-flow domain and need to make that domain work well with Chopper.

You should use this manual if you need to:

- prepare a domain for trimming
- write or update `base.json`, feature JSONs, or a project JSON
- understand when to keep whole files versus selected Tcl procs
- add flow actions for stage and step changes
- fix common validation, tracing, and parser warnings

This manual is not a developer internals guide. It does not explain parser algorithms, internal dataclasses, or service-layer implementation details.

## 2. What Chopper Does

Chopper trims one domain at a time so that a project branch keeps only the files, Tcl procedures, and optional run-script content that the selected project needs.

At a high level, Chopper supports three authoring feature families:

- **File include/exclude feature:** keep or remove whole files through `files.include` and `files.exclude`
- **Procedure include/exclude feature:** keep selected Tcl procedures and prune trace-derived extras through `procedures.include` and `procedures.exclude`
- **Run-script/stage-script generation feature:** define stages, edit stages or steps, and optionally run a domain-local post-trim script through `stages`, `flow_actions`, and `options.template_script`

This manual uses the JSON field names shown in the examples and reference tables.

Chopper is intentionally conservative. When it cannot prove something safely, it warns instead of guessing.

In normal user operation, Chopper provides the following capabilities:

- domain scanning that generates draft JSON inputs and dependency inventories without modifying the domain
- structural validation for authored JSON inputs before any trim is attempted
- full trim execution with dry-run support, audit artifact generation, backup/retrim handling, and automatic recovery on failure
- cleanup of the preserved domain backup when the trim window is complete
- machine-readable JSON output and plain-text rendering modes for automation and CI usage

### Known limitations in v1

- It does not trim `common/` or any content outside the selected domain root.
- It does not partially trim Perl, Python, csh, or other non-Tcl files.
- It does not reliably infer dynamic Tcl behavior such as `$cmd`, `eval`, runtime-generated proc names, or runtime-generated file names.
- It does not automatically copy hook files discovered through `iproc_source -use_hooks`.
- It does not trim multiple domains as one global dependency graph.

## 3. Core Concepts

### 3.1 Domain

A **domain** is one tool-flow directory such as `fev_formality/`, `sta_pt/`, or `power/`.

Chopper operates on one domain root at a time.

### 3.2 Base JSON

The **Base JSON** defines the minimum viable content for a domain.

Typical use:

- files that must always remain
- proc entry points that must always remain
- optional run-script and stage-script generation definitions

Default location:

- `jsons/base.json`

### 3.3 Feature JSON

A **Feature JSON** adds optional behavior on top of the base.

Typical use:

- feature-specific files
- additional Tcl procs
- selective pruning of wildcard-expanded files or trace-derived procs
- stage and step changes through `flow_actions`

Default location:

- `jsons/features/<feature>.json`

### 3.4 Project JSON

A **Project JSON** packages one project-specific selection into a single file.

Typical use:

- reproducible project trims
- CI usage
- shared selection recipes across team members
- audit traceability

Unlike base and feature JSON files, a project JSON does not have a fixed default location.

### 3.5 Feature families used in this manual

| Manual term | What you author | Best used for |
| --- | --- | --- |
| file include/exclude feature | `files.include` / `files.exclude` | whole Tcl scripts, non-Tcl files, configs, hooks, stacks, CSVs |
| procedure include/exclude feature | `procedures.include` / `procedures.exclude` | shared Tcl proc libraries where only some procedures are needed |
| run-script/stage-script generation feature | `stages`, `flow_actions`, `options.template_script` | run-script composition, stage ordering, step insertion, step replacement, and post-trim script hooks |

This manual uses these field-level names consistently.

## 4. Before You Start

### 4.1 Working assumptions

Normal operation assumes you run Chopper from the domain root.

Example:

```bash
cd global/snps/fev_formality
```

That means:

- `jsons/base.json` is resolved from the current working directory
- `jsons/features/*.json` are resolved from the current working directory
- paths inside a project JSON are also resolved from the current working directory, not from the location of the project JSON file

### 4.2 Prerequisites

Before authoring JSON files, gather:

- the list of Tcl files that form the minimum working flow
- the shared proc files that are safe to trim at proc level
- the optional feature groups you want to expose
- the run-stage structure, if your domain uses run-script or stage-script generation definitions
- the hook files and support scripts that must remain available at runtime

### 4.3 Best starting point

The recommended onboarding path is:

1. Run `chopper scan`.
2. Start from the generated `draft_base.json`.
3. Copy it into `jsons/base.json` and curate it.
4. Add feature JSON files under `jsons/features/`.
5. Run `validate`.
6. Run `trim --dry-run`.
7. Run live `trim` only after the dry-run looks correct.

## 5. Domain Layout and File Placement

### 5.1 Typical domain structure

```text
domain_name/
|- jsons/
|  |- base.json
|  `- features/
|     |- feature_a.json
|     `- feature_b.json
|- *.tcl
|- *_procs.tcl
|- vars.tcl
|- promote.tcl
|- *.stack
|- *.csv
|- *.pl / *.py / *.csh
`- subdirs/
```

### 5.2 What gets trimmed at what level

| File type | Chopper treatment |
| --- | --- |
| Tcl | whole-file or proc-level |
| Perl | whole-file only |
| Python | whole-file only |
| csh / tcsh | whole-file only |
| stack / csv / other support files | whole-file only |

### 5.3 Backup behavior during live trim

On the first live trim:

- `domain/` becomes `domain_backup/`
- a new trimmed `domain/` is created

On later re-trims:

- Chopper rebuilds `domain/` from the existing `domain_backup/`

If a live trim fails after work has started:

- Chopper restores the pre-run state automatically rather than leaving a partial trimmed output behind

After sign-off:

- `chopper cleanup --confirm` removes `domain_backup/`

## 6. Choosing the Right Trimming Method

Use this section when deciding whether content belongs in `files.include`, `files.exclude`, `procedures.include`, `procedures.exclude`, or the run-script/stage-script generation part of the JSON.

| Need | Recommended approach | Why |
| --- | --- | --- |
| Keep an entire file exactly as-is | `files.include` | simplest and safest |
| Remove a few files from a broad include glob | `files.exclude` | prunes only wildcard-expanded file candidates |
| Keep only selected Tcl procedures from a library-style file | `procedures.include` | avoids copying unused procs |
| Prune a helper proc that was pulled in only by conservative tracing | `procedures.exclude` | removes trace-derived extras without overriding explicit includes |
| Keep a non-Tcl script | `files.include` | non-Tcl is not trimmed at subroutine level |
| Keep a hook file discovered through `-use_hooks` | `files.include` | hook discovery alone does not copy the file |
| Add optional project behavior | feature JSON | keeps base minimal and reusable |
| Capture one project's exact selection | project JSON | best for repeatability and audit |
| Change stage ordering or insert/remove steps | `flow_actions` | intended mechanism for stage/step/run-script changes |
| Run a domain-local post-trim generator | `options.template_script` | last-step build hook; use only when `flow_actions` and `stages` are not enough |

### Recommended selection criteria

Use `procedures.include` and `procedures.exclude` when a Tcl file primarily serves as a shared procedure library.

Use `files.include` when a Tcl file has heavy top-level execution, significant dynamic behavior, or mixed setup logic and procedure definitions, unless the file is first refactored into a cleaner library-style structure.

## 7. JSON Authoring Rules

These rules apply to all Chopper JSON inputs.

### 7.1 Required schema tag

Every JSON file must contain the correct `$schema` value.

| File type | Required `$schema` |
| --- | --- |
| Base JSON | `chopper/base/v1` |
| Feature JSON | `chopper/feature/v1` |
| Project JSON | `chopper/project/v1` |

### 7.2 Path rules

All paths must be:

- relative to the domain root
- written with forward slashes
- inside the domain

All paths must **not** be:

- absolute paths
- paths containing `..`
- paths containing `//`

Examples:

| Valid | Invalid |
| --- | --- |
| `vars.tcl` | `/tmp/vars.tcl` |
| `utils/common.tcl` | `../common.tcl` |
| `reports/base/**` | `reports//base/**` |

### 7.3 Supported glob syntax

Chopper supports:

- `*`
- `?`
- `**`

### 7.3.1 Glob Pattern Reference

**What each pattern does:**

| Pattern | Matches | Example | Matches | Does NOT match |
|---------|---------|---------|---------|----------------|
| `*` | Any characters at one directory level (no `/` crossing) | `procs/*.tcl` | `procs/core.tcl`, `procs/rules.tcl` | `procs/sub/deep.tcl` |
| `?` | Exactly one character at one directory level | `step_?.tcl` | `step_a.tcl`, `step_1.tcl` | `step_ab.tcl`, `step_.tcl` |
| `**` | Any number of directories and subdirectories (recursive) | `rules/**/*.fm.tcl` | `rules/r.fm.tcl`, `rules/sub/r.fm.tcl`, `rules/a/b/r.fm.tcl` | `r.fm.tcl` (outside `rules/`) |

**Common use cases:**

| Need | Pattern | Location | Reason |
|------|---------|----------|--------|
| Include all Tcl procs in one directory | `procs/*.tcl` | `files.include` | `*` matches all `.tcl` files directly under `procs/` |
| Include config files with a naming pattern | `default_*.csv` | `files.include` | `*` matches the variable part of the filename |
| Include all files in a nested report tree | `reports/**` | `files.include` | `**` matches files at any depth under `reports/` |
| Exclude debug utilities in a subdirectory | `utils/debug/**` | `files.exclude` | `**` removes everything under `debug/` |
| Include rules files with specific extension anywhere | `**/*.fm.tcl` | `files.include` | `**` finds `.fm.tcl` files at any directory level |
| Exclude old versions of files | `*_old.tcl` | `files.exclude` | `*` matches old-versioned files at domain root |

**Important:** Patterns are applied to discover files. Literal paths always survive even if they match an exclude pattern, but wildcard-expanded paths are pruned by exclude patterns.

Use globs when a feature or base should include a family of files. Use `files.exclude` only to prune results from wildcard-style includes.

### 7.4 Include wins over exclude

Explicit includes are authoritative.

- A literal file in `files.include` stays.
- A proc explicitly named in `procedures.include` stays.
- `files.exclude` is mainly for pruning wildcard-expanded file candidates.
- `procedures.exclude` is mainly for pruning trace-derived proc candidates.

### 7.5 Do not use empty proc lists

This is invalid:

```json
{
  "file": "helper_procs.tcl",
  "procs": []
}
```

If you want the whole file, put the file in `files.include` instead.

### 7.6 Feature order matters

Selected features are applied in order.

- Later features see the results of earlier features.
- `flow_actions` are applied top-to-bottom within each feature.
- If two features try to change the same stage or step, selection order decides which change is seen last.

## 8. Base JSON Reference

### 8.1 Purpose

The base JSON defines the minimum viable flow for the domain.

It can include any subset of:

- `options`
- `files`
- `procedures`
- `stages`

All of those sections are optional except where required by your real flow needs.

### 8.2 Required fields

| Field | Required | Meaning |
| --- | --- | --- |
| `$schema` | yes | must be `chopper/base/v1` |
| `domain` | yes | domain directory name |

### 8.3 Common optional fields

| Field | Meaning |
| --- | --- |
| `description` | human-readable summary |
| `options.cross_validate` | whether generated stage or run-script output should be cross-checked against file and procedure selections |
| `options.template_script` | domain-relative script path run after a successful live trim |
| `files.include` | whole files to keep |
| `files.exclude` | prune wildcard-expanded file candidates |
| `procedures.include` | explicit Tcl proc seeds |
| `procedures.exclude` | prune trace-derived proc candidates |
| `stages` | run-script/stage-script generation definition |

### 8.4 Minimal base JSON example using all three authoring feature families

This minimal example intentionally advertises all three authoring families together: file include/exclude, procedure include/exclude, and run-script/stage-script generation.

```json
{
  "$schema": "chopper/base/v1",
  "domain": "fev_formality",
  "description": "Minimum formality flow for standard projects",
  "options": {
    "template_script": "templates/generate_release_manifest.py"
  },
  "files": {
    "include": [
      "vars.tcl",
      "promote.tcl",
      "utils.pl"
    ]
  },
  "procedures": {
    "include": [
      {
        "file": "default_fm_procs.tcl",
        "procs": ["read_libs", "run_verify"]
      }
    ]
  },
  "stages": [
    {
      "name": "verify",
      "load_from": "",
      "steps": [
        "step_run_verify.tcl"
      ]
    }
  ]
}
```

### 8.5 Full base JSON example using all three authoring feature families

This example intentionally uses the file include/exclude feature, the procedure include/exclude feature, and the run-script/stage-script generation feature in one schema-valid base JSON:

```json
{
  "$schema": "chopper/base/v1",
  "domain": "fev_formality",
  "description": "Baseline formality flow with curated files, selected Tcl procedures, and ordered run stages",
  "options": {
    "cross_validate": true,
    "template_script": "templates/generate_release_manifest.py"
  },
  "files": {
    "include": [
      "vars.tcl",
      "promote.tcl",
      "hooks/common_postcheck.tcl",
      "reports/base/**"
    ],
    "exclude": [
      "reports/base/legacy/**"
    ]
  },
  "procedures": {
    "include": [
      {
        "file": "default_fm_procs.tcl",
        "procs": ["read_libs", "run_verify", "publish_summary"]
      }
    ],
    "exclude": [
      {
        "file": "default_fm_procs.tcl",
        "procs": ["legacy_banner"]
      }
    ]
  },
  "stages": [
    {
      "name": "setup",
      "load_from": "",
      "command": "fm_shell -f run_setup.tcl",
      "outputs": ["setup.done"],
      "steps": [
        "step_load_env.tcl",
        "step_load_libs.tcl",
        "step_load_constraints.tcl"
      ]
    },
    {
      "name": "verify",
      "load_from": "setup",
      "dependencies": ["setup"],
      "exit_codes": [0, 3, 5],
      "command": "fm_shell -f run_verify.tcl",
      "inputs": ["setup.done"],
      "outputs": ["verify.done"],
      "steps": [
        "step_run_verify.tcl",
        "step_publish_summary.tcl"
      ]
    }
  ]
}
```

What this example demonstrates:

- `files.include` keeps required scripts and a broad report directory.
- `files.exclude` trims only the unwanted wildcard results under that report directory.
- `procedures.include` declares the explicit Tcl entry procedures that must survive.
- `procedures.exclude` gives you a place to prune conservative trace extras if they appear.
- `stages` define the ordered build/run script structure.
- In generated stack files, `name` maps to `N`, `command` maps to `J`, `exit_codes` maps to `L`, and `dependencies` maps to `D`.
- `options.template_script` is a path to a domain-local post-trim generator, not an arbitrary shell command.

### 8.6 When to add `files.exclude` in the base

Use `files.exclude` only when your base deliberately uses a broad include pattern and needs to prune some of the wildcard results.

Good example:

```json
"files": {
  "include": ["reports/base/**"],
  "exclude": ["reports/base/obsolete/**"]
}
```

### 8.7 `template_script` guidance

Use `options.template_script` only when your domain genuinely needs a post-trim script.

Rules:

- it must be a path, not a shell command string
- it must exist under the selected domain
- it must not escape the domain root
- it is preserved in the trimmed domain so it is available when executed
- it runs exactly once after a successful live `trim`
- it does not run during `scan`, `validate`, `trim --dry-run`, or `cleanup`
- if the script cannot be resolved or executed, Chopper reports a warning and completes the trim
- its working directory is the active trimmed domain root

## 9. Feature JSON Reference

### 9.1 Purpose

Feature JSON files add optional behavior on top of the base.

Use them to model real project-level choices such as:

- DFT enablement
- power-flow support
- extra reports
- optional debug collateral
- stage or step edits for one feature family

### 9.2 Required fields

| Field | Required | Meaning |
| --- | --- | --- |
| `$schema` | yes | must be `chopper/feature/v1` |
| `name` | yes | unique feature name within a selected project |

### 9.3 Useful optional fields

| Field | Meaning |
| --- | --- |
| `domain` | optional domain identifier; mismatch is a warning |
| `description` | human-readable summary |
| `metadata` | documentation-only block such as owner, wiki, tags |
| `files.include` | whole files the feature needs |
| `files.exclude` | prune wildcard-expanded file candidates |
| `procedures.include` | explicit additional procs |
| `procedures.exclude` | prune trace-derived procs |
| `flow_actions` | stage, step, and run-script generation changes |

### 9.4 Minimal feature example

This minimal feature example also advertises all three authoring families together.

```json
{
  "$schema": "chopper/feature/v1",
  "name": "feature_dft",
  "description": "DFT-related flow additions",
  "files": {
    "include": [
      "scan/**"
    ],
    "exclude": [
      "scan/legacy/**"
    ]
  },
  "procedures": {
    "include": [
      {
        "file": "default_fm_procs.tcl",
        "procs": ["add_fm_scan_constraints"]
      }
    ]
  },
  "flow_actions": [
    {
      "action": "add_step_after",
      "stage": "setup",
      "reference": "step_load_constraints.tcl",
      "items": [
        "step_apply_scan_mode.tcl"
      ]
    }
  ]
}
```

### 9.5 Full feature example using all three authoring feature families

This feature example uses file include/exclude, procedure include/exclude, and run-script/stage-script generation changes together:

```json
{
  "$schema": "chopper/feature/v1",
  "name": "scan_debug",
  "domain": "fev_formality",
  "description": "Adds scan collateral, prunes legacy scan content, keeps scan procedures, and extends the verify pipeline",
  "metadata": {
    "owner": "fm_team",
    "tags": ["scan", "debug"]
  },
  "files": {
    "include": [
      "scan/**",
      "hooks/scan_debug_hook.tcl"
    ],
    "exclude": [
      "scan/legacy/**",
      "scan/tmp/**"
    ]
  },
  "procedures": {
    "include": [
      {
        "file": "default_fm_procs.tcl",
        "procs": ["add_fm_scan_constraints", "emit_scan_summary"]
      }
    ],
    "exclude": [
      {
        "file": "default_fm_procs.tcl",
        "procs": ["legacy_scan_banner"]
      }
    ]
  },
  "flow_actions": [
    {
      "action": "add_step_after",
      "stage": "setup",
      "reference": "step_load_constraints.tcl",
      "items": [
        "step_apply_scan_mode.tcl",
        "step_load_scan_views.tcl"
      ]
    },
    {
      "action": "remove_step",
      "stage": "verify",
      "reference": "step_legacy_scan_checks.tcl"
    },
    {
      "action": "add_stage_after",
      "name": "scan_debug_reports",
      "reference": "verify",
      "load_from": "verify",
      "command": "fm_shell -f run_scan_debug_reports.tcl",
      "steps": [
        "step_emit_scan_debug_report.tcl"
      ],
      "outputs": ["scan_debug_reports.done"]
    }
  ]
}
```

What this example demonstrates:

- `files.exclude` only prunes results from the broad `scan/**` include.
- `procedures.exclude` is for trace-derived extras; it does not override an explicitly included procedure.
- `flow_actions` are where you express stage and step edits instead of inventing custom JSON fields.
- One feature file may use all three authoring families when that feature is genuinely cohesive.
- In `add_stage_after`, `name`, `reference`, `load_from`, and `steps` are required; `command`, `inputs`, and `outputs` are optional.

### 9.6 Flow action vocabulary

Supported `action` values are:

| Action | Meaning |
| --- | --- |
| `add_step_before` | insert steps before a reference step |
| `add_step_after` | insert steps after a reference step |
| `add_stage_before` | insert a new stage before a reference stage |
| `add_stage_after` | insert a new stage after a reference stage |
| `remove_step` | remove a step from a stage |
| `remove_stage` | remove a stage |
| `load_from` | change a stage's `load_from` dependency |
| `replace_step` | replace one step with another |
| `replace_stage` | replace one stage with a full new stage definition |

### 9.7 Required fields by action type

| Action | Required fields |
| --- | --- |
| `add_step_before` | `action`, `stage`, `reference`, `items` |
| `add_step_after` | `action`, `stage`, `reference`, `items` |
| `remove_step` | `action`, `stage`, `reference` |
| `replace_step` | `action`, `stage`, `reference`, `with` |
| `add_stage_before` | `action`, `name`, `reference`, `load_from`, `steps` |
| `add_stage_after` | `action`, `name`, `reference`, `load_from`, `steps` |
| `remove_stage` | `action`, `reference` |
| `replace_stage` | `action`, `reference`, `with` |
| `load_from` | `action`, `stage`, `reference` |

> Authoring note: For replacement actions, the target key is `reference`, consistent with all other action types.

### 9.8 Simple flow-action examples

Add two steps after an existing step:

```json
{
  "action": "add_step_after",
  "stage": "setup",
  "reference": "fc.app_options.tcl",
  "items": [
    "step_dft_setup.tcl",
    "step_scan_collateral.tcl"
  ]
}
```

Replace one step:

```json
{
  "action": "replace_step",
  "stage": "verify",
  "reference": "fev_fm_rtl2gate.tcl",
  "with": "fev_fm_rtl2gate_v2.tcl"
}
```

Remove one stage:

```json
{
  "action": "remove_stage",
  "reference": "obsolete_debug"
}
```

Change `load_from`:

```json
{
  "action": "load_from",
  "stage": "verify",
  "reference": "pre_verify_checks"
}
```

### 9.9 Instance targeting with `@n`

If the same step string appears multiple times in one stage, use `@n` to target a specific occurrence.

Example:

```json
{
  "action": "replace_step",
  "stage": "compile_initial_opto",
  "reference": "step_load_post_compile_constraints.tcl@2",
  "with": "step_load_constraints_v2.tcl"
}
```

Rules:

- `@1` is the first occurrence
- `@n` is supported only for step-targeting actions
- if `n` is larger than the real number of matches, validation fails with `V-12`

## 10. Project JSON Reference

### 10.1 Purpose

Use a project JSON when you want one file that fully describes a project's trim selection.

It is the best choice when you need:

- reproducibility
- team sharing
- CI automation
- audit traceability

### 10.2 Required fields

| Field | Required | Meaning |
| --- | --- | --- |
| `$schema` | yes | must be `chopper/project/v1` |
| `project` | yes | project identifier |
| `domain` | yes | must match the domain root directory name |
| `base` | yes | path to the base JSON, resolved from the current working directory |

### 10.3 Optional fields

| Field | Meaning |
| --- | --- |
| `owner` | domain deployment owner |
| `release_branch` | branch name for the project trim |
| `features` | ordered list of feature JSON paths |
| `notes` | human-readable rationale for the selection |

### 10.4 Project JSON example

```json
{
  "$schema": "chopper/project/v1",
  "project": "PROJECT_ABC",
  "domain": "fev_formality",
  "owner": "domain_owner",
  "release_branch": "project_abc_rtm",
  "base": "jsons/base.json",
  "features": [
    "jsons/features/scan_files.json",
    "jsons/features/scan_logic.json",
    "jsons/features/scan_pipeline.json"
  ],
  "notes": [
    "scan_files owns the file include/exclude behavior and must run first",
    "scan_logic adds and prunes Tcl procedures after file selection is stable",
    "scan_pipeline changes stages and steps after file and procedure selection are defined"
  ]
}
```

### 10.5 Critical path-resolution rule

This is one of the most important user rules in Chopper:

- the `base` and `features` entries are resolved relative to the current working directory
- they are **not** resolved relative to the project JSON file's own location

That means this command is valid if you run it from the domain root:

```bash
chopper trim --project configs/project_abc.json
```

Even though the project JSON is under `configs/`, the `base` and `features` paths inside it still point to files relative to the domain root.

### 10.6 When to use direct CLI mode instead

Use direct `--base` and `--features` when:

- you are still exploring the domain
- you are iterating quickly during authoring
- you do not yet want to package the selection into one file

### 10.7 Recommended way to split one project across three feature files

When a project needs all three authoring families, the cleanest pattern is usually to split them by concern rather than putting everything into one giant feature JSON.

| Feature file | Primary job | Typical content |
| --- | --- | --- |
| `feature_files.json` | file include/exclude feature | file globs, hook files, non-Tcl collateral, wildcard pruning |
| `feature_logic.json` | procedure include/exclude feature | Tcl procedure seeds and conservative trace pruning |
| `feature_pipeline.json` | run-script/stage-script generation feature | stage definitions, `flow_actions`, optional run-script generation details |

This split makes feature ordering easier to explain in the project JSON and easier to debug during `validate` and `trim --dry-run`.

## 11. Preparing Your Tcl and Domain Files

This section is the most important part of the manual for teams that want to make an existing domain easy to trim.

### 11.1 Code patterns that work well with Chopper

| Preferred pattern | Why it helps |
| --- | --- |
| top-level `proc` definitions | reliably indexable |
| `proc` inside literal `namespace eval my_ns { ... }` | reliably indexable with namespace context |
| literal proc names | traceable and addressable in JSON |
| brace-delimited proc bodies | parseable and stable |
| literal `source` or `iproc_source -file file.tcl` | file dependencies can be detected |
| shared utility procs isolated into `*_procs.tcl` style files | better procedure include/exclude candidate |
| optional logic split into separate files | easier file include/exclude authoring |

### 11.2 Code patterns that cause trouble

| Pattern | Typical result | Recommended fix |
| --- | --- | --- |
| `proc ${prefix}_name ...` | `PARSE-DYNA-01` warning, proc skipped | use a literal proc name |
| `namespace eval $ns { ... }` | `PARSE-COMPNS-01` warning, body not indexed | use a literal namespace name when possible |
| `proc` defined inside `if`, `for`, `while`, `catch`, or `eval` | proc not indexed | move proc definition to file top level or literal namespace block |
| `$cmd arg1` or `eval ...` dynamic dispatch | `TRACE-UNRESOLV-01` warning | simplify call form or explicitly include the missing proc |
| duplicate proc names in the same file | `PARSER-DUP-01` error | remove or rename the duplicate |
| quoted or non-braced proc body | `PARSE-NOBODY-01` warning | rewrite the body with braces |
| `source $var` or `iproc_source -file $var` | unresolved file dependency warning | use a literal path or keep the file explicitly via `files.include` |
| hook file discovered via `-use_hooks` but not explicitly included | hook not copied | add the hook file to `files.include` |

### 11.3 Recommended refactoring patterns

If your domain is difficult to trim, these changes usually help:

- move reusable helper logic into dedicated Tcl proc library files
- keep driver or step files small and explicit
- separate optional behavior into feature-specific files
- use stable, literal namespace names
- avoid hiding required dependencies behind dynamic calls when a literal call is practical

### 11.4 Compliant and non-compliant examples

Non-compliant example: computed proc name

```tcl
proc ${prefix}_helper {} {
    return "dynamic"
}
```

Compliant example:

```tcl
proc feature_helper {} {
    return "stable"
}
```

Non-compliant example: proc defined inside control flow

```tcl
if {$feature_enabled} {
    proc conditional_proc {} {
        return "maybe"
    }
}
```

Compliant example:

```tcl
proc conditional_proc {} {
    return "always indexable"
}

if {$feature_enabled} {
    conditional_proc
}
```

Non-compliant example: dynamic source path

```tcl
source $setup_file
```

Compliant example:

```tcl
source project_setup.tcl
```

### 11.5 When to prefer `file-level trimming` over `proc-level trimming`

Prefer whole-file inclusion when:

- the file contains non-Tcl content
- the file is a runtime script rather than a reusable proc library
- the file has heavy top-level side effects that you do not want to reason about after proc deletion
- the file depends on dynamic behavior that Chopper cannot model cleanly

### 11.6 Tcl parsing behavior and supported features

Chopper performs structural Tcl parsing. It does not execute Tcl, evaluate runtime expressions, or simulate tool behavior. Its parser is designed to identify procedure definitions, namespace context, file dependencies, and statically visible procedure calls so that procedure-level trimming and trace expansion remain deterministic.

#### What the Tcl parser recognizes reliably

| Parsing feature | What Chopper recognizes | Why it matters |
| --- | --- | --- |
| top-level `proc` detection | `proc` definitions at file root | enables procedure-level indexing |
| literal `namespace eval` support | `proc` definitions inside literal `namespace eval name { ... }` blocks | preserves namespace-qualified procedure names |
| nested namespace accumulation | nested literal namespace blocks such as `a::b::proc_name` | improves trace accuracy in library-style Tcl |
| brace-aware parsing | balanced `{ ... }` bodies with correct nesting | gives stable procedure boundaries |
| backslash-newline continuation | logical commands split across physical lines | preserves source line numbers while parsing long definitions |
| comment-aware parsing | `#` comments at command position | prevents comment text from corrupting brace matching |
| direct call extraction | commands such as `helper_proc arg1` | supports transitive procedure tracing |
| bracketed call extraction | expressions such as `[helper_proc arg1]` | captures common Tcl helper-call patterns |
| literal file dependency extraction | `source file.tcl` and `iproc_source -file file.tcl` | helps retain required Tcl files |
| encoding fallback | UTF-8 first, then Latin-1 with a warning if needed | allows legacy Tcl files to remain analyzable |

#### What Chopper extracts from Tcl files

When a Tcl file is suitable for procedure-level analysis, Chopper can extract:

- procedure names for use in `procedures.include` and `procedures.exclude`
- namespace-qualified procedure names when procedures live inside literal namespace blocks
- source and `iproc_source` file dependencies when the referenced path is literal
- direct and bracketed procedure-call tokens used for conservative trace expansion
- procedure source spans so unwanted procedures can be removed while preserving surrounding top-level content

#### Important parsing rules for authors

- Procedure bodies should be brace-delimited. Non-braced bodies may be skipped with `PARSE-NOBODY-01`.
- Literal procedure names are preferred. Computed names such as `proc ${prefix}_name ...` are skipped with `PARSE-DYNA-01`.
- Literal namespace names are preferred. Computed `namespace eval $ns { ... }` blocks are not indexed and emit `PARSE-COMPNS-01`.
- Procedures defined inside `if`, `for`, `foreach`, `while`, `catch`, `eval`, or another procedure body are not treated as stable top-level definitions.
- Inside brace-delimited bodies, quotes do not suppress braces for structural parsing. If braces are unbalanced, Chopper reports a parse error instead of guessing intent.
- Braces inside comments do not affect brace depth.

#### Dynamic Tcl patterns that Chopper does not resolve

Chopper intentionally does not guess through dynamic Tcl behavior. The following patterns require explicit owner action when they affect kept content:

| Pattern | Typical outcome | Recommended author action |
| --- | --- | --- |
| `$cmd arg1` | unresolved call warning such as `TRACE-UNRESOLV-01` | simplify the call or explicitly include the required procedure |
| `eval ...` or `uplevel ...` | unresolved trace behavior | retain the dependency explicitly in JSON |
| computed proc names | procedure skipped | rename the procedure to a literal stable name |
| computed namespace names | body not indexed for procedures | use a literal namespace name |
| `source $var` or `iproc_source -file $var` | unresolved file dependency warning | use a literal path or keep the file explicitly |
| hook discovery through `-use_hooks` alone | hook file discovered but not kept automatically | add the hook file to `files.include` |

#### Practical authoring guidance

If you want Tcl files to trim well at procedure level, use literal procedure names, literal namespace blocks, brace-delimited procedure bodies, and literal file-source paths. If a file relies heavily on dynamic dispatch, runtime-generated names, or top-level side effects, it is usually a better candidate for `files.include` than for procedure-level trimming.

## 12. CLI Command Reference

### 12.1 Global command form

```text
chopper [-h] [-v] [--debug] [--plain] [--no-color] [--json] [--strict]
        {scan,validate,trim,cleanup} ...
```

### 12.2 Global options

| Option | Meaning |
| --- | --- |
| `-v`, `--verbose` | increase verbosity; `-v` is typically sufficient for interactive review |
| `--debug` | maximum verbosity with full stack traces for troubleshooting |
| `--plain` | disable rich terminal rendering and use plain text output |
| `--no-color` | disable ANSI color codes while preserving the standard text layout |
| `--json` | emit machine-readable JSON to stdout for scripts, CI, or future GUI integration |
| `--strict` | treat warnings as errors |

User guidance:

- Use `--json` when Chopper is called from scripts or CI pipelines.
- Use `--plain` when terminal formatting is undesirable or when logs are being captured in plain text.
- Use `--no-color` when your terminal supports layout but color codes are unwanted.
- Use `--debug` only when the normal summary does not provide enough failure detail.

### 12.3 `scan`

Purpose:

- discover files, procs, and dependencies
- generate a draft base JSON and inventories
- generate dependency graph artifacts for review
- give you a safe starting point
- avoid modifying domain files

Key options:

- `--domain PATH`: scan a domain other than the current working directory
- `--output DIR`: write scan artifacts to a custom output directory

Typical scan outputs include:

- `draft_base.json` for owner curation
- file and procedure inventories
- dependency graph artifacts used to review discovered relationships

Example:

```bash
chopper scan --output scan_output/
```

### 12.4 `validate`

Purpose:

- run Phase 1 checks on JSON inputs
- confirm schemas, file paths, proc names, and action targets
- avoid modifying domain files

Important behavior:

- `validate` checks input structure and references only
- `validate` does not build trimmed output
- `validate` does not run tracing expansion
- `validate` does not execute `template_script`

Key options:

- `--domain PATH`: validate a domain other than the current working directory
- `--base PATH`: validate a base JSON directly
- `--features PATHS`: validate an ordered feature set together with the base JSON
- `--project PATH`: validate a packaged project selection instead of direct base/feature inputs

Examples:

```bash
chopper validate --base jsons/base.json

chopper validate --base jsons/base.json \
  --features jsons/features/feature_a.json,jsons/features/feature_b.json

chopper validate --project configs/project_abc.json
```

### 12.5 `trim`

Purpose:

- run the full pipeline
- compile selections
- trace proc dependencies
- build trimmed output
- validate results
- emit audit artifacts

Important behavior:

- first live trim creates `domain_backup/` and rebuilds `domain/` as trimmed output
- later live trims rebuild from the preserved backup
- `--dry-run` simulates the full pipeline without writing files
- on failure, Chopper restores the pre-run state automatically
- a successful trim produces audit artifacts that record the run inputs and results

Key options:

- `--domain PATH`: trim a domain other than the current working directory
- `--base PATH`: trim from a base JSON directly
- `--features PATHS`: trim with an ordered feature set
- `--project PATH`: trim from a packaged project selection
- `--dry-run`: verify the planned trim without modifying files
- `--force`: clean abandoned lock metadata when no active trim owns the lock

Typical audit artifacts include machine-readable run records such as compiled manifest details and trim reports for traceability.

Examples:

```bash
chopper trim --dry-run --base jsons/base.json

chopper trim --base jsons/base.json \
  --features jsons/features/feature_a.json,jsons/features/feature_b.json

chopper trim --dry-run --project configs/project_abc.json
```

### 12.6 `cleanup`

Purpose:

- remove `domain_backup/` permanently after the trim window is complete

Key options:

- `--domain PATH`: clean up a domain other than the current working directory
- `--confirm`: required safeguard for an irreversible cleanup
- `--force`: clean abandoned lock metadata when no active cleanup owns the lock

Example:

```bash
chopper cleanup --confirm
```

### 12.7 Operational guidance

- Always run `validate` before `trim`.
- Always run `trim --dry-run` before live `trim`.
- Use `--strict` during sign-off if you want warnings to block the run.
- Do not use `--project` together with `--base` or `--features`.
- Use `--domain` when you need to operate on a domain without changing your shell working directory.
- Use `--force` only to clear abandoned lock metadata after confirming no active Chopper process is running.
- Use `--json` when another tool or script needs to consume Chopper results programmatically.

## 13. Recommended End-to-End Workflow

### 13.1 Authoring workflow for a new domain

1. From the domain root, run `chopper scan --output scan_output/`.
2. Review `scan_output/draft_base.json`.
3. Copy or convert that draft into `jsons/base.json`.
4. Remove anything that is not part of the minimum viable flow.
5. Add `jsons/features/*.json` for optional behavior.
6. Validate the base alone.
7. Validate the base plus selected features.
8. Run a dry-run trim.
9. Review warnings, inventories, and the resulting audit outputs.
10. Run live trim only after the dry-run is acceptable.

### 13.2 Suggested first-pass strategy

For your first usable Chopper setup, keep it simple:

- use the file include/exclude feature for obvious whole-file content
- use the procedure include/exclude feature only for clearly library-style Tcl proc files
- add only the most important features first
- keep stage, step, and run-script generation changes minimal until the base and core features are stable

### 13.3 Re-trim workflow

If you update your JSON files after a live trim:

1. edit the JSON files
2. run `validate`
3. run `trim --dry-run`
4. run live `trim` again

Chopper rebuilds the trimmed domain from `domain_backup/`.

### 13.4 Sign-off workflow

Before final cleanup:

1. make sure the domain behaves as expected
2. resolve or accept all warnings intentionally
3. store the final project JSON if you use project mode
4. keep `domain_backup/` until the trim window closes
5. run `chopper cleanup --confirm` only when you are sure the backup is no longer needed

### 13.5 Recommended practices for first successful trims

These practices consistently make domains easier to author, validate, and retrim:

- Keep the base JSON minimal, literal, and easy to review. Place only the minimum viable flow in the base.
- Split optional behavior by a single clear purpose so that each feature file remains easy to describe and validate.
- Stabilize file selection before procedure selection. Resolving missing-file issues first reduces later ambiguity in trace results.
- Use `procedures.exclude` only after a real over-retention case has been observed during tracing.
- Place hook files, Python helpers, Perl scripts, CSVs, and stack files in `files.include`, not in procedure-level logic.
- Use `flow_actions` for standard pipeline edits. Reserve `options.template_script` for cases that require a domain-local post-trim generator.
- Record ordering notes in project JSON whenever one feature depends on an earlier feature's file or stage decisions.

## 14. Common Diagnostics and Fixes

This section translates the most common diagnostics into practical author actions.

### 14.1 JSON authoring problems

| Code | What it usually means | What you should do |
| --- | --- | --- |
| `V-01` | missing or wrong `$schema` | use the exact schema string for the file type |
| `V-02` | required field missing | add the required field such as `domain`, `name`, or `project` |
| `V-03` | `procs` array is empty | move the file to `files.include` |
| `V-08` | included file not found | fix the relative path |
| `V-09` | listed proc not found in the file | fix the proc name or the file path |
| `V-10` | duplicate stage name | rename one of the stages |
| `V-11` | malformed glob | fix the pattern |
| `V-12` | `@n` points past the real match count | use a smaller instance number or fix the stage content |
| `V-13` | `--project` used with `--base` or `--features` | use only one input mode |
| `V-15` | project JSON path cannot be resolved | make paths relative to the domain root |
| `V-18` | two selected feature JSONs have the same `name` | rename or remove one feature |

### 14.2 Code-structure problems

| Code | What it usually means | What you should do |
| --- | --- | --- |
| `PARSER-DUP-01` | duplicate proc definitions in one file | remove or rename duplicates |
| `PARSE-DYNA-01` | computed proc name skipped | use a literal proc name |
| `PARSE-COMPNS-01` | computed namespace skipped | use a literal `namespace eval` name |
| `PARSE-NOBODY-01` | proc body is not brace-delimited | rewrite the body with braces |
| `PARSE-UNBRACE-01` | brace mismatch in surviving Tcl | fix Tcl syntax before trimming |

### 14.3 Trace warnings

| Code | What it usually means | What you should do |
| --- | --- | --- |
| `TRACE-AMBIG-01` | more than one proc could match a call | namespace-qualify the call or explicitly include the needed proc |
| `TRACE-CROSS-DOMAIN-01` | no in-domain proc matched the call | verify it really lives outside the domain, or explicitly include the proc if needed |
| `TRACE-UNRESOLV-01` | dynamic Tcl call form could not be resolved | simplify the code or explicitly include the dependency |
| `TRACE-CYCLE-01` | proc cycle detected | usually safe, but review the cycle for correctness |

### 14.4 Post-trim warnings

| Code | What it usually means | What you should do |
| --- | --- | --- |
| `V-21` | a surviving proc still calls a missing proc | include the missing proc or accept the dangling call if intentional |
| `V-22` | a surviving file still sources a removed file | add the file to `files.include` or remove the source statement |
| `V-23` | generated run file still references a removed step file | add the step file or remove the step from stages |
| `V-24` | procedure trimming removed all procedures and only blank/comment content remains | decide whether the file should really be a full-file include |
| `V-25` | file survives with top-level Tcl only | informational only |
| `V-26` | `template_script` is invalid or escapes the domain root | fix or remove the path |

### 14.5 Common authoring questions

**Q: Should I think in feature families or in JSON field names?**

Use the JSON field names. Think in terms of the file include/exclude feature, the procedure include/exclude feature, and the run-script/stage-script generation feature. That maps directly to what you write.

**Q: Why did an excluded file still survive in the trimmed output?**

Because a surviving Tcl procedure still needed that file. In that case, the file survives as a proc-trimmed file rather than a full-file copy.

**Q: Why didn't `procedures.exclude` remove a procedure I explicitly listed in `procedures.include`?**

Explicit includes win. `procedures.exclude` is mainly for pruning procedures that tracing added conservatively.

**Q: Why didn't a hook file get copied even though Chopper discovered it?**

Hook discovery is not the same as keep behavior. If a hook file must survive, list it explicitly in `files.include`.

**Q: When should I use `flow_actions` versus `options.template_script`?**

Use `flow_actions` for normal stage and step editing. Use `options.template_script` only when the domain truly needs a domain-local post-trim generator after the standard pipeline is complete.

**Q: Why does project JSON resolve paths from the domain root instead of from the project JSON file's own directory?**

Because the current working directory is the operational domain root in v1. Chopper treats the project JSON as a packaged selection, not as a second path root.

**Q: Can I use procedure-level selection on Python, Perl, or csh files?**

No. Procedure-level selection is Tcl-only. Non-Tcl files are whole-file only.

### 14.6 Corner case scenarios users should understand

| Scenario | What Chopper does | What the user should do |
| --- | --- | --- |
| broad `files.include` glob plus `files.exclude` | keeps the broad match set, then prunes the excluded wildcard results | use this when a feature owns a directory but must drop a few legacy paths |
| file appears in `files.exclude` but a surviving procedure lives in that file | keeps the file as proc-trimmed content | review whether the procedure should stay, or move the whole file to `files.include` if the file should survive intact |
| procedure trimming leaves only comments or top-level Tcl | keeps the file and emits `V-24` or `V-25` | decide whether the file should be whole-file kept instead |
| same step string appears twice in one stage | requires `@n` to target the intended occurrence | use `@1`, `@2`, and so on; otherwise actions may hit the wrong step or fail with `V-12` |
| feature ordering changes the final pipeline | applies later features after earlier ones | record the intended order in the project JSON `notes` field |
| dynamic `source`, `iproc_source`, `$cmd`, `eval`, or computed proc names | warns instead of guessing | add explicit `files.include` or `procedures.include` entries for the dependencies you know must survive |
| `template_script` points outside the domain or through a symlink escape | fails with `V-26` during live trim | keep the path domain-relative and inside the selected domain root |

## 15. Authoring Checklists

### 15.1 Base JSON checklist

- `$schema` is `chopper/base/v1`
- `domain` matches the actual domain directory name
- all paths are relative and use forward slashes
- no `procs: []` entries exist
- whole-file content is in `files.include`
- procedure-level content is limited to Tcl files that are good procedure include/exclude candidates
- `stages` are present only if the domain really uses run-script/stage-script generation behavior

### 15.2 Feature JSON checklist

- `$schema` is `chopper/feature/v1`
- `name` is unique within the selected feature set
- only optional behavior is modeled here
- `files.exclude` is used only to prune wildcard-style include results
- `procedures.exclude` is used only to prune trace-derived procs
- every `flow_actions` target exists in the ordered flow at the time the action runs

### 15.3 Project JSON checklist

- `$schema` is `chopper/project/v1`
- `domain` matches the current working directory name
- `base` points to `jsons/base.json` or another valid domain-relative file
- `features` are listed in the intended order
- `notes` explain any ordering choices that might confuse future users

### 15.4 Codebase readiness checklist

- critical procs have literal names
- important procs are defined at file top level or inside literal `namespace eval` blocks
- shared helper libraries are separated from top-level run scripts where practical
- dynamic calls are minimized or explicitly accounted for in JSON
- hook files needed at runtime are explicitly listed in `files.include`

### 15.5 Pre-live-trim checklist

- `validate` passes for the intended selection
- `trim --dry-run` passes
- warnings have been reviewed and either fixed or consciously accepted
- the selected project JSON is saved if project mode is being used
- the team understands that live trim creates `domain_backup/`

## 16. Appendix A: JSON Configuration Templates

### 16.1 Minimal base template

```json
{
  "$schema": "chopper/base/v1",
  "domain": "your_domain_name",
  "description": "Minimum viable flow for this domain",
  "options": {
    "template_script": "templates/generate_release_manifest.py"
  },
  "files": {
    "include": [
      "vars.tcl"
    ]
  },
  "procedures": {
    "include": [
      {
        "file": "shared_procs.tcl",
        "procs": ["entry_proc"]
      }
    ]
  },
  "stages": [
    {
      "name": "setup",
      "load_from": "",
      "steps": [
        "step_load.tcl"
      ]
    }
  ]
}
```

### 16.2 Minimal feature template

```json
{
  "$schema": "chopper/feature/v1",
  "name": "feature_name",
  "description": "What this feature adds",
  "files": {
    "include": [
      "feature_dir/**"
    ]
  },
  "procedures": {
    "include": [
      {
        "file": "shared_procs.tcl",
        "procs": ["feature_proc"]
      }
    ]
  },
  "flow_actions": [
    {
      "action": "add_step_after",
      "stage": "setup",
      "reference": "step_load.tcl",
      "items": [
        "step_feature_enable.tcl"
      ]
    }
  ]
}
```

### 16.3 Minimal project template

```json
{
  "$schema": "chopper/project/v1",
  "project": "PROJECT_NAME",
  "domain": "your_domain_name",
  "owner": "domain_owner",
  "release_branch": "project_branch_name",
  "base": "jsons/base.json",
  "features": [
    "jsons/features/feature_name.json"
  ],
  "notes": [
    "Add ordering notes here if needed"
  ]
}
```

### 16.4 Simple stage definition template

Required fields: `name`, `load_from`, `steps`. Optional fields: `dependencies`, `exit_codes`, `command`, `inputs`, `outputs`, `run_mode`, `language`.

`name` becomes the stack-file `N` line, `command` becomes `J`, `exit_codes` becomes `L`, and `dependencies` becomes `D`. `load_from` is still important, but it feeds the generated run script rather than the stack dependency graph line.

```json
{
  "name": "setup",
  "load_from": "",
  "steps": [
    "source $ward/global/snps/$env(flow)/setup.tcl",
    "step_load.tcl",
    "step_close.tcl"
  ]
}
```

With all optional fields:

```json
{
  "name": "setup",
  "load_from": "",
  "command": "tool_shell -f run_setup.tcl",
  "exit_codes": [0],
  "outputs": ["setup.done"],
  "run_mode": "serial",
  "steps": [
    "source $ward/global/snps/$env(flow)/setup.tcl",
    "step_load.tcl",
    "step_close.tcl"
  ]
}
```

### 16.5 Simple replace-step template

```json
{
  "action": "replace_step",
  "stage": "verify",
  "reference": "old_step.tcl",
  "with": "new_step.tcl"
}
```

---

## Summary and Authoring Principles

It is recommended that teams begin with a minimal base JSON and add features incrementally.

If Chopper reports a warning for dynamic behavior, treat that warning as an indication that the domain should be made more explicit or that the dependency should be retained directly in JSON.

When ambiguity exists, apply the following principles:

1. Prefer explicit file paths over dynamic behavior.
2. Prefer literal proc names over computed names.
3. Run `trim --dry-run` before live `trim`.
4. Use a project JSON for any trim that must be repeatable.
5. Use JSON field names when teaching or reviewing author intent.
