# Chopper — EDA TFM Trimming Tool

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Scope, Roles, and Operating Model](#2-scope-roles-and-operating-model)
3. [Core Concepts and Capability Model](#3-core-concepts-and-capability-model)
4. [Architecture Rules](#4-architecture-rules)
5. [Pipeline, Compilation, and Workflow](#5-pipeline-compilation-and-workflow)
6. [JSON Design Principles and Schema Model](#6-json-design-principles-and-schema-model)
7. [Requirements](#7-requirements)
8. [Codebase Analysis](#8-codebase-analysis)
9. [Technical Challenges and Risk Handling](#9-technical-challenges-and-risk-handling)
10. [Question Ledger](#10-question-ledger)
11. [FAQ and Corner Cases](#11-faq-and-corner-cases)
12. [Reference Documents and External Inputs](#12-reference-documents-and-external-inputs)
13. [Implementation Work Queue](#13-implementation-work-queue)
14. [Revision History](#14-revision-history)
15. [Glossary](#15-glossary)

---

## 1. Problem Statement

### 1.1 Context

The **Cheetah R2G (CTH R2G)** flow spans the full VLSI backend pipeline, from **Fusion Compiler** through **final signoff**, across multiple EDA tools. **CTH Tool Flow Manager (TFM)** orchestrates tool invocations, configuration, and handoff data.

The TFM is organized into **domains**. Each domain corresponds to one tool or one flow stage and has a designated **domain owner**. Every domain currently ships with a large amount of generalized flow code, optional behavior, legacy support, and customer-specific feature logic.

When a **new project** signs up for the TFM:

1. A **project branch** is created from the main repo.
2. A **2-week trim window** begins.
3. Each **domain deployment owner** trims only their own domain for that project.
4. Each owner commits the trimmed result back to the same project branch.
5. At the end of the window, the branch contains a customer-specific thin version of the flow.

### 1.2 The Problem

Each tool domain ships with the full feature set, whether or not a given customer needs it.

| Pain Point | Description |
| --- | --- |
| **Per-domain bloat** | Every domain carries all features, even when the customer needs only a subset. |
| **Intertwined flow code** | The flow is file/proc-call based and tightly coupled, not cleanly modular. |
| **No selective trimming** | There is no built-in mechanism to surgically remove unwanted files, procs, and code paths. |
| **Manual and error-prone** | Manual trimming risks broken references, inconsistent behavior, and missed cleanup. |
| **Time-boxed execution** | Domain owners have a strict delivery window and cannot afford repeated trial-and-error trimming. |
| **Shared branch pressure** | Many domain owners modify the same project branch and each trim must stay isolated and safe. |

### 1.3 The Goal

Build **Chopper** — a per-domain trimming tool that lets each domain deployment owner produce a clean, minimal, customer-specific version of their domain while preserving correctness, auditability, and re-trim safety.

### 1.4 Current Product Status

Chopper is currently in a **docs-first architecture phase**.

| Status Item | Current State |
| --- | --- |
| **Product maturity** | Early framework / scaffold stage |
| **Implementation state** | Core trim engine is not yet production-implemented |
| **Repository reality** | The repo currently contains package/framework scaffolding plus architecture and analysis docs |
| **Primary source of truth** | This architecture document |
| **Supporting document** | per component spec docs are available |
| **Implication** | Design clarity must come before feature implementation |

This document therefore describes the **intended architecture**, the **resolved design decisions**, the **current open questions**, and the **implementation work queue** required to turn the framework into a working product.

---

## 2. Scope, Roles, and Operating Model

### 2.1 In Scope

Chopper is in scope for:

- Per-domain trimming only
- Whole-file include/exclude
- Tcl proc-level trimming
- Transitive proc dependency tracing for diagnostics and deterministic dependency-graph generation
- run-file generation
- Audit trail and reproducibility

System is classified into three broad features:

- **F1:** File-level granularity; users can choose which files to include and which to remove.
- **F2:** Proc-level granularity; users can choose which procs to include from which file and which procs to remove from which file.
- **F3:** Stage-level granularity; users can use the stage/step section to define run files and these scripts `<stage>.tcl` files will be generated.

**NOTE:** Users have complete freedom to choose any one or combination of all three feature sets, and JSON ensures that at least one of these feature keys is always present.

### 2.2 Out of Scope

Chopper is not intended to do the following:

- Trim directories outside the selected domain path. The domain owner is responsible for ensuring that the domain path is properly scoped to contain all relevant files and procs.
- Perform repo-wide global trimming across all domains in one dependency graph.
- Evaluate runtime Tcl semantics completely. Chopper performs static analysis and tracing based on the source code, but it does not attempt to fully resolve dynamic Tcl patterns such as `eval`, `uplevel`, or runtime-generated proc/file names. Such patterns are logged as warnings and require explicit owner input.
- Auto-edit JSON authoring based on traced call trees. Chopper emits diagnostics/dependency graph, and users decide JSON updates explicitly.
- Execute or simulate tool flows to infer feature selections.
- Partially trim non-Tcl languages at subroutine level.
- Infer undeclared feature dependency graphs automatically. Feature JSON may declare `depends_on`, but semantic enforcement is handled by validation rather than by schema alone.

### 2.2.1 Permanently Excluded Items

The following items have been evaluated and **permanently excluded**. They will not be implemented in any version of Chopper.

| ID | Item | Rationale |
| --- | --- | --- |
| OOS-01 | Non-Tcl subroutine-level trimming | Non-Tcl files (Perl, Python, shell) are file-level only by design. Subroutine-level parsing for non-Tcl languages is not a requirement. |
| OOS-02 | Computed proc name extraction | Procs with dynamic names (`proc ${prefix}_helper`) are skipped with `PW-01`. Heuristic resolution adds complexity with no practical value. |
| OOS-03 | Pipeline checkpointing | No domain exceeds 200 MB. Full restart from Phase 1 is acceptable. |
| OOS-04 | Auto-draft JSON / scan mode | Scan mode was explicitly removed. Chopper does not generate draft JSONs. Domain owners author JSONs manually; `--dry-run` is the authoring iteration feedback loop. |
| OOS-05 | File-mutation detection via timers or locks (during a run) | Chopper **assumes the filesystem is static for the duration of a single invocation**. No mtime polling between P2 and P5. No file locks. No stale-lock recovery. No in-flight re-stat. If a user (or another process) modifies files under `<domain>/` or `<domain>_backup/` while Chopper is running, the result is undefined behavior and is classified as a **programmer error on the operator side** — not an engineering problem Chopper tries to detect or mitigate. The CLI help text and [`technical_docs/IMPLEMENTATION.md` (pitfalls)](IMPLEMENTATION.md) make this contract explicit so operators know to run Chopper against a quiesced domain. This boundary is drawn deliberately: adding timers or locks would (a) pull in platform-specific primitives (`fcntl`/`msvcrt`), (b) introduce stale-lock recovery paths, and (c) make testing non-deterministic. All three were rejected in [`technical_docs/ENGINEERING.md`](ENGINEERING.md) §16 Q3. **Never reintroduce.** |

### 2.3 Roles

| Role | Responsibility |
| --- | --- |
| **Global Flow Owner** | Owns the full mainline flow code for a domain and authors base/features JSONs for that domain. |
| **Project Lead / Release Manager** | Creates the project branch, coordinates the trim window, and drives final cleanup and branch readiness. |
| **Domain Deployment Owner** | Chooses project-specific features, maintains JSON combinations, runs Chopper, reviews output, and commits trimmed domain results. |

### 2.4 Repo Layout — Actual CTH R2G Structure

The TFM repo has this top-level structure under `global/`:

```text
global/
├── snps/
│   ├── fev_formality/         ◄── DOMAIN (trimmable)
│   ├── sta_pt/                ◄── DOMAIN (trimmable)
│   ├── power/                 ◄── DOMAIN (trimmable)
│   ├── apr_fc/                ◄── DOMAIN (trimmable)
│   ├── dft_fc/                ◄── DOMAIN (trimmable)
│   ├── extraction/            ◄── DOMAIN (trimmable)
│   ├── hc/                    ◄── DOMAIN (trimmable)
│   ├── lv_icv/                ◄── DOMAIN (trimmable)
│   ├── intel_caliber/         ◄── DOMAIN (trimmable)
│   ├── hv_openrail/           ◄── DOMAIN (trimmable)
│   ├── assembly/              ◄── DOMAIN (trimmable)
│   ├── contourgen/            ◄── DOMAIN (trimmable)
│   └── caliber_eco/           ◄── DOMAIN (trimmable)
└── cdns/
    ├── fev_formality/         ◄── DOMAIN (trimmable)
    ├── sta_pt/                ◄── DOMAIN (trimmable)
    ├── power/                 ◄── DOMAIN (trimmable)
    ├── apr_fc/                ◄── DOMAIN (trimmable)
    ├── dft_fc/                ◄── DOMAIN (trimmable)
    ├── extraction/            ◄── DOMAIN (trimmable)
    ├── hc/                    ◄── DOMAIN (trimmable)
    ├── lv_icv/                ◄── DOMAIN (trimmable)
    ├── intel_caliber/         ◄── DOMAIN (trimmable)
    ├── hv_openrail/           ◄── DOMAIN (trimmable)
    ├── assembly/              ◄── DOMAIN (trimmable)
    ├── contourgen/            ◄── DOMAIN (trimmable)
    └── caliber_eco/           ◄── DOMAIN (trimmable)
```

**Key rule: anything outside the selected domain's boundary is a “DO NOT TOUCH” zone and is NEVER trimmed.** Chopper operates strictly on the single domain directory it is invoked from; sibling domains, vendor roots, shared `global/` infrastructure, and any path that escapes the domain are never read, written, or backed up. References from domain code into external paths are surfaced as advisory diagnostics (`VW-17 external-reference`) but never cause trimming or survival decisions.

**Reserved path: `.chopper/`.** The `.chopper/` directory is a **reserved** audit-artifact location that lives only at `<domain>/.chopper/`. It is not user-authored content and is not part of the trimmable surface. Chopper guarantees:

- `.chopper/` is **never** backed up. When `<domain>/` is renamed to `<domain>_backup/` on first trim, any pre-existing `.chopper/` is moved aside first and then re-created fresh under the new rebuilt `<domain>/`.
- `.chopper/` is **never** copied from `<domain>_backup/` into the rebuilt `<domain>/` during a re-trim. Each run produces a fresh `.chopper/` for that run.
- `.chopper/` is **never** walked by the P2 parser and **never** matched by any `files.include` glob (including `**`).
- `.chopper/` is owner-managed between runs (domain owners are expected to add it to `.gitignore`); Chopper does not prune it automatically.

### 2.5 Per-Domain Structure (Actual)

Each domain is typically flat or shallow, with Tcl at the root and optional subdirectories:

```text
domain_X/
├── jsons/
│   ├── base.json
│   └── features/
│       ├── <feature_a>.feature.json
│       └── <feature_b>.feature.json
├── *.tcl
├── *_procs.tcl
├── vars.tcl
├── promote.tcl
├── *.stack
├── *.csv
├── *.pl / *.py / *.csh
└── subdirs/
    └── ...
```

Owner-curated base and feature JSONs are expected by default under the domain-local `jsons/` directory:

- `<domain>/jsons/base.json`
- `<domain>/jsons/features/<feature>.feature.json`

Project JSON does not have a fixed default location. The user provides its path explicitly via `--project <path>`.

### 2.6 Project Branch Lifecycle

```text
main branch (full TFM, all domains, all features)
  │
  ├── git branch project_ABC
  │
  │   ┌─── 2-week trim window ───┐
  │   │                           │
  │   │  Domain Owner 1           │──► trims Domain A
  │   │  Domain Owner 2           │──► trims Domain B
  │   │  Domain Owner 3           │──► trims Domain C
  │   │  ...                      │
  │   └───────────────────────────┘
  │
  └── final project branch contains trimmed domains
```

### 2.7 Flow Code Languages

| Language | Usage | Chopper Treatment |
| --- | --- | --- |
| **Tcl** | Primary flow language | File-level and proc-level |
| **Perl** | Utility and support scripts | File-level only |
| **Python** | Utility and reporting scripts and primary sometimes | File-level only |
| **tcsh / csh** | Shell wrappers and environment setup | File-level only |

### 2.8 Backup and Re-trim Strategy

Chopper uses a **backup-and-rebuild** workflow. The domain directory is the operational unit; `<domain>_backup/` is a sibling created on first trim and consumed on re-trim.

```text
BEFORE first trim:
  domain/                    ← original full domain

AFTER first trim:
  domain_backup/             ← original untouched source
  domain/                    ← new trimmed domain

AFTER re-trim:
  domain_backup/             ← still original untouched source
  domain/                    ← rebuilt from backup

FINAL CLEANUP:
  domain_backup/             ← deleted via `chopper cleanup --confirm`
  domain/                    ← final trimmed domain retained
```

**Edge-case behavior matrix** (evaluated at invocation, in the current working directory):

| # | `<domain>/` | `<domain>_backup/` | Chopper behavior |
| --- | --- | --- | --- |
| 1 | exists | missing | First trim. Create `<domain>_backup/` as a full copy (excluding any pre-existing `.chopper/`, which is moved aside and re-created fresh under the new `<domain>/`), then build the trimmed `<domain>/` in place. |
| 2 | exists | exists | Re-trim. Do **not** re-backup. Rebuild `<domain>/` from `<domain>_backup/` using the current JSONs. This branch also handles recovery from a prior failed run (the half-rebuilt `<domain>/` is discarded and rebuilt from the intact backup). Any hand edits to `<domain>/` since the last run are discarded — Chopper does not detect or warn about them at the diagnostic level; the CLI always prints a fixed pre-flight line *"Re-trim rebuilds `<domain>/` from `<domain>_backup/`. Any manual edits in `<domain>/` will be discarded."* so the user is informed every run. |
| 3 | missing | exists | Recovery re-trim. Restore `<domain>/` from `<domain>_backup/` and proceed as case 2. |
| 4 | missing | missing | Fatal. Emit `VE-21 no-domain-or-backup`; exit 2. Nothing to trim. |

**Failure recovery (no staging, no atomic promotion).** Chopper does not stage trimmed output into a temporary tree and does not atomically swap trees on success. If a trim run aborts between P5 and P7 (for example, disk full, permission denied, DPA atomic drop failed), `<domain>/` is left in whatever half-rebuilt state the failure produced, and `<domain>_backup/` remains intact. On the next invocation, the edge-case matrix observes both directories present and selects **Case 2** (re-trim): the trimmer treats `<domain>_backup/` as the authoritative source, discards the half-rebuilt `<domain>/`, and rebuilds cleanly. Operators who want a pristine manual reset may run `rm -rf <domain> && mv <domain>_backup <domain>` at any time — this returns the workspace to the pre-Chopper state.

**Operational rule:** backups stay in the project branch throughout the trim window and are removed explicitly by `chopper cleanup --confirm`. Users are expected to commit or move hand-edits before re-running; Chopper always rebuilds from `_backup` and does not attempt to merge.

### 2.9 Cross-Domain Dependencies

**Current architectural assumption:** cross-domain dependencies do not materially exist in practice.

This means:

- Domains are trimmed independently.
- Tracing is bounded to the selected domain path.

If cross-domain references are discovered, they may show up in the call tree, but they play no role in Chopper's trimming or selection. Cross-domain code is assumed to always be available.

### 2.10 Feature Ownership and Selection

**Domain owners own feature selection.**

This includes:

- Choosing the base JSON for their domain
- Choosing the selected feature JSONs for a project
- Deciding final run-file generation content for their domain
- Reviewing warnings, trace reports, and validation output

---

## 3. Core Concepts and Capability Model

> **Canonical JSON reference:** All schemas live in `schemas/`, 14 progressive examples in `examples/`, and the full authoring guide in [`technical_docs/JSON_AUTHORING_GUIDE.md`](JSON_AUTHORING_GUIDE.md). The examples below are sourced from that set.

### 3.1 Base JSON

The **Base JSON** defines the minimum viable flow for a domain.
Schema: `schemas/base-v1.schema.json`
It may contain any subset of the F1, F2, and F3 sections. Omitted capability blocks are treated as empty.

By default, the curated base JSON is stored at `jsons/base.json` under the selected domain.

**Minimal valid example** (from `examples/01_base_files_only/jsons/base.json`):

```json
{
  "$schema": "base-v1",
  "domain": "my_domain",
  "owner": "platform-team",
  "description": "Base with file-level includes only.",
  "files": {
    "include": [
      "setup.tcl",
      "utils/*.tcl",
      "procs/core_procs.tcl"
    ],
    "exclude": [
      "procs/legacy_procs.tcl"
    ]
  }
}
```

**Full example with all three sections** (from `examples/07_base_full/jsons/base.json`):

```json
{
  "$schema": "base-v1",
  "domain": "my_domain",
  "owner": "platform-team",
  "vendor": "synopsys",
  "tool": "my_tool",
  "description": "Full base with files, procedures, and stages.",
  "files": {
    "include": ["setup.tcl", "vars.tcl", "procs/**/*.tcl", "milestone.tcl"],
    "exclude": ["procs/legacy/*.tcl"]
  },
  "procedures": {
    "include": [
      { "file": "procs/core_procs.tcl", "procs": ["run_setup", "load_design", "verify_netlist", "report_summary"] }
    ],
    "exclude": [
      { "file": "procs/core_procs.tcl", "procs": ["debug_dump", "old_verify_netlist"] }
    ]
  },
  "stages": [
    {
      "name": "setup",
      "load_from": "",
      "command": "-xt vw Imy_shell -B BLOCK -T setup",
      "exit_codes": [0],
      "steps": ["source setup.tcl", "source vars.tcl", "run_setup"]
    }
  ]
}
```

**Rules:**

- `$schema` and `domain` are required.
- At least one of `files`, `procedures`, or `stages` must be present.
- All three sections can coexist.

**Key fields:**

| Field | Required | Description |
| --- | --- | --- |
| `$schema` | Yes | Must be `"base-v1"` |
| `domain` | Yes | Domain directory name (e.g., `my_domain`) |
| `owner` | No | Team responsible for this base |
| `vendor` | No | Vendor (e.g., `synopsys`, `cadence`) |
| `tool` | No | Tool name (e.g., `primetime`, `innovus`) |
| `description` | No | Human-readable summary |
| `options.cross_validate` | No | Cross-validate F3 run-file output against the F1/F2 surviving set. When `true` (default), every step in every surviving stage is checked against the set of files and procs that survived trim; missing targets emit `VW-14` (step file missing), `VW-15` (step proc missing), or `VW-16` (step source missing) — all warnings, never errors. Set to `false` to suppress those warnings when F3 intentionally references content outside the trimmed domain. |
| `options.generate_stack` | No | When `true`, F3 emits one aggregate scheduler stack file at the domain root named `<basename(domain_root)>.stack` containing one record per resolved stage. Record order is the **topological sort** of the stage dependency graph (edges = `dependencies` ∪ `{load_from}`), with authored position as the tiebreaker; see §3.6. Default: `false`. No effect when `stages` is empty. Per-stage `standalone_stack: true` is orthogonal in artifact terms but **suppresses** that stage's `<stage>.tcl` (the standalone `.stack` becomes the stage's sole driver); see §3.6. |
| `options.indent` | No | When `true`, P5c re-indents every `PROC_TRIM` and `GENERATED` `.tcl` output before P6 validation runs (legacy four-space brace-driven formatter; see §5.5). Default: `false` — Chopper writes those outputs verbatim and skips the indentation pass entirely. The current formatter is intentionally minimal (no quote/comment awareness, no line-continuation handling); leave this off unless you have explicitly verified it on your domain. P6's brace-balance check (`VE-16`) runs over `PROC_TRIM`/`GENERATED` outputs regardless of this flag. |
| `files.include` | No* | Glob patterns or literal paths to include |
| `files.exclude` | No | Glob patterns to exclude |
| `procedures.include` | No* | Proc-level includes — array of `{ file, procs[] }` |
| `procedures.exclude` | No | Proc-level excludes |
| `stages` | No* | Ordered stage definitions for F3 run-file generation |

*At least one of `files`, `procedures`, or `stages` is required.

### 3.2 Feature JSON

The **Feature JSON** expresses optional behavior layered on top of the base.
Schema: `schemas/feature-v1.schema.json`
It may contain any subset of the F1, F2, and F3 sections. Omitted capability blocks are treated as empty.

By default, curated feature JSONs are stored under `jsons/features/` under the selected domain.

**Example** (from `examples/08_base_plus_one_feature/jsons/features/dft.feature.json`):

```json
{
  "$schema": "feature-v1",
  "name": "dft",
  "domain": "my_domain",
  "description": "DFT feature: adds scan-chain related procs and a dedicated dft_check stage.",
  "metadata": {
    "owner": "dft-team",
    "tags": ["dft", "scan", "signoff"],
    "wiki": "https://wiki.example.com/dft-feature"
  },
  "files": {
    "include": ["procs/dft_procs.tcl"]
  },
  "procedures": {
    "include": [
      { "file": "procs/dft_procs.tcl", "procs": ["setup_scan_chains", "verify_scan", "report_dft_coverage"] }
    ]
  },
  "flow_actions": [
    {
      "action": "add_stage_after",
      "name": "dft_check",
      "reference": "main",
      "load_from": "main",
      "command": "-xt vw Imy_shell -B BLOCK -T dft_check",
      "exit_codes": [0, 3],
      "dependencies": ["main"],
      "steps": ["source procs/dft_procs.tcl", "setup_scan_chains", "verify_scan", "report_dft_coverage"]
    }
  ]
}
```

**Rules:**
- `$schema` and `name` are required. Everything else is optional.
- `name` must be unique across all features in a project.
- At least one of `files`, `procedures`, or `flow_actions` should be present (otherwise the feature does nothing).

**Key fields:**

| Field | Required | Description |
|-------|----------|--------------|
| `$schema` | Yes | Must be `"feature-v1"` |
| `name` | Yes | Feature identifier — referenced by `depends_on` and project `features` list |
| `domain` | No | Target domain. Chopper warns if mismatched with selected base |
| `description` | No | Human-readable summary |
| `depends_on` | No | Prerequisite feature names (must appear earlier in project) |
| `metadata` | No | Documentation fields: `owner`, `tags`, `wiki`, `related_ivars`, `related_appvars` |
| `files.include` | No | Additional files to include |
| `files.exclude` | No | Files to remove from the effective include set |
| `procedures.include` | No | Additional proc-level includes |
| `procedures.exclude` | No | Proc-level excludes |
| `flow_actions` | No | Stage modifications: add/remove/replace steps or stages (F3) |

**Features are layered, not additive.** Sources (base + each selected feature in declared order) are applied as an ordered overlay: each layer can include and exclude freely, and the **last layer that says something about a file or proc wins**. A feature can therefore add new content, remove base content, or replace base content with its own. In detail:

- `files.include` adds the file to the running set at this layer.
- `files.exclude` removes the file from the running set at this layer, regardless of which earlier layer (base or another feature) put it there. `VE-27 no-op-exclude` is emitted only when the exclude contributes no removal signal: no earlier-layer contribution and no same-layer `files.include` touch (literal or glob).
- `procedures.include` adds the proc (and forces its file to survive as `PROC_TRIM` if no whole-file include is in effect).
- `procedures.exclude` removes the proc from the running set at this layer, regardless of source. If the proc is not present in the running set when this layer runs, `VE-27` is emitted.
- When a later layer actually changes an earlier layer's decision (cancels an include, replaces a file, removes a proc that an earlier layer contributed), `VW-21 layer-shadowed` is emitted — informational, exit 0, audit trail only.
- **An empty `procs` array in any `procEntry` fires `VE-03`** — both `procedures.include` and `procedures.exclude` require at least one proc name per entry.
- Within a single JSON, mixing `procedures.include` and `procedures.exclude` on the same file is an authoring conflict: PI wins, PE is ignored for that file, and `VW-12` is emitted.
- Within a single JSON, mixing `files.exclude` and `procedures.exclude` on the same file with no PI is redundant: both are removal-within-this-source signals, the file is not contributed by this JSON, and `VW-11` is emitted.
- The full conflict-resolution, file-treatment, and interaction-warning rules are defined in R1.

### 3.3 Project JSON

The **Project JSON** is the reproducible project-specific selection file.
Schema: `schemas/project-v1.schema.json`

**Example** (from `examples/08_base_plus_one_feature/project.json`, with `jsons/base.json` and `jsons/features/dft.feature.json` as siblings):

```json
{
  "$schema": "project-v1",
  "project": "PROJECT_ABC",
  "domain": "my_domain",
  "owner": "integration-team",
  "base": "jsons/base.json",
  "features": [
    "jsons/features/dft.feature.json"
  ],
  "notes": [
    "DFT feature adds scan chain verification stage after main"
  ]
}
```

**Rules:**
- `$schema`, `project`, `domain`, and `base` are required. Everything else is optional.
- `domain` must match the basename of the operational domain root (resolved per §5.1), compared case-insensitively via `casefold()`.
- `base` and `features` paths are resolved relative to the current working directory, not the project JSON file location. `..` and absolute paths are forbidden.
- `--project` is mutually exclusive with `--base` and `--features`.

**Key fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `$schema` | Yes | Must be `"project-v1"` |
| `project` | Yes | Project identifier (e.g., `PROJECT_ABC`) |
| `domain` | Yes | Domain identifier — must match the basename of the current working directory |
| `base` | Yes | Domain-relative path to the base JSON file |
| `owner` | No | Domain deployment owner for this project |
| `release_branch` | No | Git branch name for this project trim |
| `features` | No | List of feature JSON paths in declared application order. **Order is authoritative for everything** — F1, F2, and F3. Layers are applied left-to-right; the last layer that mentions a file/proc/step wins. |
| `notes` | No | Human-readable notes explaining feature ordering or selection rationale |

### 3.4 F1 — File Chopping

F1 performs whole-file trimming via `files.include` and `files.exclude` in base and feature JSONs.

| Behavior | Description |
|---|---|
| **Input unit** | Literal file path or glob pattern |
| **Output unit** | Whole file copied or removed |
| **File-type scope** | **All file types** — Tcl, Perl, Python, shell, config, and any other file under the domain. F1 is fully file-type agnostic. |
| **Write semantics** | `FULL_COPY` copies bytes verbatim from `<domain>_backup/` into the rebuilt `domain/` tree. The copy is byte-for-byte identical to the source for **every file type**, including `.tcl`. The P5c Tcl indentation-normalization pass rewrites only files that Chopper itself produced — `PROC_TRIM` outputs and `GENERATED` `.tcl` artifacts — and never touches `FULL_COPY` outputs. |
| **Best for** | Tcl scripts without shared proc libraries, configs, stack files, hooks, Perl/Python/csh |

> **F1 is file-type agnostic.** `files.include` and `files.exclude` glob patterns match every file under the domain regardless of extension. Non-Tcl files (`.py`, `.pl`, `.csh`, config, etc.) receive a `FULL_COPY` or `REMOVE` treatment decision through F1 file-level trimming. They are never parsed by P2 (OOS-01) and are therefore never eligible for F2 proc-level trimming, but they participate in F1 copy/remove decisions identically to `.tcl` files. Glob-matched non-Tcl files enter the manifest universe directly from the compiler's universe-construction step, not from the parser output.

> **F1 keeps every `FULL_COPY` file verbatim.** When F1 keeps a file as `FULL_COPY`, P5 copies it byte-for-byte from backup to output regardless of extension. Compressed reports, binary payloads, vendor sidecar files, **and `.tcl` files** are never decoded or normalized. The P5c indentation-normalization pass applies only to `PROC_TRIM` and `GENERATED` `.tcl` outputs (files Chopper itself rewrote or synthesized).

**Glob patterns** are supported in `files.include` and `files.exclude` only. Three special characters are recognized:

| Pattern | Matches | Does NOT match |
|---------|---------|----------------|
| `*` | Any characters except `/` at one directory level | Files in subdirectories |
| `?` | Exactly one character except `/` | More than one character |
| `**` | Any number of directory levels (including zero) | — (matches all depths) |

**Examples:**

| Pattern | Result |
|---------|--------|
| `procs/*.tcl` | All `.tcl` files directly under `procs/` |
| `rule?.fm.tcl` | `rule1.fm.tcl`, `rule2.fm.tcl` — not `rule12.fm.tcl` |
| `reports/**` | All files anywhere under `reports/` |
| `rules/**/*.fm.tcl` | All `.fm.tcl` files anywhere under `rules/` |
| `*_procs.tcl` | All proc files at the domain root only |

**Rules:**
- Literal paths (no special characters) in `files.include` always survive even if they match a `files.exclude` pattern (R1).
- Wildcard-expanded includes are pruned by matching `files.exclude` entries.
- Glob patterns match **all file types** — `.tcl`, `.py`, `.pl`, `.csh`, and any other extension. F1 is file-type agnostic; extension filtering is never applied during glob expansion.
- Non-Tcl files matched by a glob receive `FULL_COPY` or `REMOVE` treatment (F1). They are excluded from P2 parsing (OOS-01) and are therefore never eligible for F2 proc-level trimming.
- `FULL_COPY` is byte-preserving for **every** file type, including `.tcl`. The `TrimReport.bytes_out` for a `FULL_COPY` outcome equals the source byte count and never shifts after P5c. Indentation normalization applies only to `PROC_TRIM` and `GENERATED` `.tcl` outputs.
- When a glob pattern expands to zero files it is silently ignored.
- A literal path in `files.exclude` whose target is already absent from the domain emits `VW-25 exclude-target-absent` (the exclusion is a no-op — the file the author wanted dropped is already gone) and does **not** block the trim. A missing literal in `files.include`, by contrast, remains a hard `VE-06` error.
- All expansions are normalized, deduplicated, and sorted lexicographically before compilation.
- Patterns are case-sensitive.
- Glob patterns do NOT apply to `procedures.include` / `procedures.exclude` — those use exact file paths and proc names.

### 3.5 F2 — Proc Chopping

F2 performs Tcl proc-level trimming via `procedures.include` and `procedures.exclude` in base and feature JSONs.

| Behavior | Description |
|---|---|
| **Input unit** | `{ file, procs[] }` — exact file path and proc name list |
| **Output unit** | Original Tcl file copied, unwanted proc definitions deleted |
| **File-type scope** | Tcl files only. F2 is the only trimming mode that deletes proc bodies; P5c subsequently normalizes indentation for `PROC_TRIM` and `GENERATED` `.tcl` outputs. |
| **Best for** | `*_procs.tcl`, shared utility proc files, rule libraries |

**`procEntry` structure:**

```json
{
  "file": "procs/core_procs.tcl",
  "procs": ["run_setup", "load_design"]
}
```

- `file`: domain-relative path (forward slashes, no `..`, no `//`)
- `procs`: non-empty array of proc short names as they appear in the file

**Rules:**
- An entry with an empty `procs` array (`"procs": []`) is a **hard validation error**. Use `files.include` to keep a whole file.
- Proc names in `procs` are the short names as authored in the file; Chopper resolves canonical form (`file.tcl::qualified_name`) internally.
- Only `.tcl` files participate in F2. If a file must survive unchanged, even when it contains Tcl-adjacent text, the correct surface is F1 `files.include`, not F2.
- In P5a, `PROC_TRIM` is the only path that reads file contents for proc-body deletion, and it does so only for Tcl files selected for proc trimming. P5c later reads every emitted `PROC_TRIM` and `GENERATED` `.tcl` output for indentation normalization; `FULL_COPY` outputs are not read by P5c.
- Tracing is default-on: explicitly included procs are expanded transitively for diagnostics and call-tree reporting (PI+), but only explicitly listed procs survive in the trimmed output. See R3.

### 3.6 F3 — Run-File Generation

F3 generates stage-based run files from JSON stage definitions. Users who want generated run scripts define stages; users who still maintain scheduler stack files can have Chopper assemble one aggregate stack file from the same stage metadata via `options.generate_stack`, or skip stages entirely. A per-stage `standalone_stack: true` flag emits a verbatim `<stage>.stack` (Intel header + authored `steps` verbatim) and **suppresses** the otherwise-always-emitted `<stage>.tcl` for that stage — the standalone stack is the stage's sole driver. The aggregate `<basename(domain_root)>.stack` still includes a record for a standalone stage when `generate_stack` is on.

| Behavior | Description |
|---|---|
| **Input unit** | Ordered `stages` array in base JSON; `flow_actions` in feature JSONs |
| **Output unit** | `<stage>.tcl` per stage **unless** the stage sets `standalone_stack: true`. Additionally one aggregate `<basename(domain_root)>.stack` when `options.generate_stack` is `true`. Additionally `<stage>.stack` for any stage with `standalone_stack: true` (verbatim `steps`). See the truth table below. |
| **Purpose** | Build clean project-facing run orchestration for domains that want generated run scripts with injectable step sequences |

**`stageDefinition` fields:**

| Field | Required | Stack line | Notes |
|-------|----------|-----------|-------|
| `name` | Yes | `N` | Unique within domain |
| `load_from` | Yes | — | Data predecessor for generated script; can be empty string |
| `steps` | Yes | — | Ordered plain-string step list written into `<stage>.tcl` |
| `command` | No | `J` | Scheduler job command |
| `exit_codes` | No | `L` | Legal exit codes (integers) |
| `dependencies` | No | `D` | Scheduler dependency (parent task names) |
| `inputs` | No | `I` | Input artifact markers |
| `outputs` | No | `O` | Output artifact markers |
| `run_mode` | No | `R` | `"serial"` (default) or `"parallel"`. The aggregate stack emits an `R parallel` line only when `run_mode == "parallel"`; serial is implicit (no `R` line). |
| `language` | No | — | `"tcl"` (default) or `"python"` |
| `standalone_stack` | No | — | When `true`, F3 emits a `<stage>.stack` whose body is the Intel header followed by the authored `steps` verbatim (no N/J/L/D record derivation) and **suppresses** that stage's `<stage>.tcl` — the standalone stack is the stage's sole driver. The stage is still included in the aggregate `<domain>.stack` record set when `generate_stack` is on. Default: `false`. |

> **`run_mode` semantics.** `run_mode` is advisory metadata surfaced to the scheduler via the aggregate stack `R` line; Chopper itself does not parallelize trim execution. Its only effect is to annotate the aggregate stack record. Default is `"serial"`, in which case the `R` line is omitted entirely (matching the production stack-file convention).

> **`load_from` vs `dependencies`:** `load_from` feeds the generated `<stage>.tcl` script (data sourcing, `ivar(src_task)` semantics). `dependencies` is the stack `D` line controlling scheduler execution order. They serve different purposes.

**Aggregate stack-file auto-generation (`options.generate_stack`).** When the base JSON sets `options.generate_stack: true` and `stages` is non-empty, F3 emits **one** scheduler stack file at the domain root named `<basename(domain_root)>.stack`. The filename is sourced from the runtime domain-root basename (`Path.cwd().name` after `--domain` resolution per §5.1) — there is no JSON field for it. The file contains a single Intel header followed by one record per resolved stage, with records separated by exactly one blank line. **Record order is the topological sort of the stage dependency graph** (see below), *not* the authored order of `manifest.stages`. The per-stage `<stage>.tcl` emission and the trim report continue to use authored order; only stack-record order is topologically derived.

**Stage dependency graph.** For each resolved stage `S`, the directed edges entering `S` are the union of (1) one edge `P → S` for every `P` in `S.dependencies` and (2) one edge `S.load_from → S` when `S.load_from` is non-empty. The graph is built once per compile; cycles and dangling references are hard errors:

* `VE-30 stage-dependency-cycle` — any cycle (including a self-loop via `load_from == name` or `name ∈ dependencies`) aborts compilation (exit 1). The diagnostic message names the cycle in the order discovered.
* `VE-31 stage-dependency-unresolved` — any edge whose source is not a defined stage in the resolved flow aborts compilation (exit 1). The diagnostic names the referrer stage, the unresolved name, and the field (`dependencies` or `load_from`) that carried it.

These errors fire whenever `stages` is non-empty, regardless of `options.generate_stack` — a malformed dependency graph is an authoring bug independent of stack emission.

**Topological ordering algorithm.** Kahn's algorithm over `(in_degree, authored_position)`: at every step, choose the lowest-in-degree node, breaking ties by **authored position** (the index of the stage in `manifest.stages` as produced by `flow_resolver`). This is fully deterministic, preserves intuitive authoring intent for unrelated subgraphs, and avoids lexicographic shuffling. The result is recorded on `CompiledManifest.stack_order` (a tuple of stage names) and consumed by the stack emitter; it is empty when `stages` is empty.

Per-record layout (one record per stage, separated by exactly one blank line):

```
####################################################################################################
# INTEL CONFIDENTIAL
# Copyright (c) <YEAR> Intel Corporation
# ... (full Intel notice; see §6.6.1)
####################################################################################################

# Chopper-generated stack: <stage1.name>
N <stage1.name>
J <stage1.command>     (omitted when command is empty)
L <c1> <c2> ...        (omitted when exit_codes is empty)
I <input>              (one line per entry; omitted when empty)
O <output>             (one line per entry; omitted when empty)
D <dependency>         (always; see derivation below)
R parallel             (only when run_mode == "parallel"; omitted for serial)

# Chopper-generated stack: <stage2.name>
...
```

Per-record line order is fixed: `N` → `J` → `L` → `I` → `O` → `D` → (optional `R parallel`). The `D` line is derived in this order: (1) if `dependencies` is non-empty, emit one `D <dep>` line per entry in authored order; (2) else if `load_from` is non-empty, emit `D <load_from>`; (3) else emit a bare `D` line.

A `# Chopper-generated stack: <stage.name>` provenance banner precedes every record (matching the historical per-stage emitter's banner style) so audit consumers can correlate records to their authoring stage without opening `compiled_manifest.json`.

The aggregate path is registered in `CompiledManifest.file_decisions` as `GENERATED` (reason `fi-literal`), skipped by the trimmer, and surfaced in the audit bundle exactly like generated `.tcl` files. If a stage's `command` is empty (the `J` line is omitted), Chopper emits `VW-23 stack-stage-empty-command` once per such stage — the scheduler will almost certainly reject that record at runtime. The flag has no effect when `stages` is empty (silent no-op, no diagnostic). Default is `false`.

A `<basename(domain_root)>.stack` collision with any existing `files.*` entry is reported as `VE-28 aggregate-stack-collision` and aborts compilation (exit 1). Resolve by renaming the domain root, excluding the colliding entry, or disabling `options.generate_stack`.

**Per-stage standalone stack files (`standalone_stack: true`).** Independent of `options.generate_stack`, any individual stage may set `standalone_stack: true`. When set, F3 emits a `<stage.name>.stack` at the domain root whose body is the Intel header followed by a single blank line and then `"\n".join(stage.steps)` — the authored `steps` are written verbatim with no further interpretation. The aggregate-stack N/J/L/D/I/O/R derivation is **not** applied; `command`, `exit_codes`, `dependencies`, `inputs`, `outputs`, `load_from`, and `run_mode` are ignored for standalone-stack body construction. Standalone emission **replaces** the per-stage `<stage>.tcl`: a stage with `standalone_stack: true` does not emit `<stage>.tcl` at all (the standalone stack is the stage's sole driver). The stage is still represented as a record in the aggregate `<domain>.stack` when `options.generate_stack: true`, and that record participates in the topological ordering described above (its `dependencies` / `load_from` edges contribute to the graph).

Standalone paths are registered in `CompiledManifest.file_decisions` as `GENERATED` (reason `fi-literal`) per stage. A `<stage>.stack` collision with `files.*` or with the aggregate `<domain>.stack` path is reported as `VE-29 standalone-stack-collision` and aborts compilation (exit 1).

**Truth table** for the four artifact combinations per stage:

| `options.generate_stack` | stage `standalone_stack` | Artifacts emitted for this stage |
|---|---|---|
| `false` | `false` | `<stage>.tcl` |
| `false` | `true` | `<stage>.stack` (verbatim `steps`) — **no `<stage>.tcl`** |
| `true` | `false` | `<stage>.tcl` + record in `<domain>.stack` (record order topological) |
| `true` | `true` | `<stage>.stack` (verbatim `steps`) + record in `<domain>.stack` — **no `<stage>.tcl`** |

The aggregate stack inclusion is independent of `<stage>.tcl` / `<stage>.stack` selection; the standalone-stack flag controls only which per-stage driver (`.tcl` vs `.stack`) is emitted, never whether the stage appears in the aggregate.

Steps are stored and processed as **plain strings** — a step may be a Tcl filename, a raw `source` command, an ivar-based reference, or a conditional directive such as `#if` / `#else` / `#endif`. See R4 for the rationale.

Feature JSONs modify the base stage sequence via `flow_actions`. The full action vocabulary (`add_step_before`, `add_step_after`, `replace_step`, `remove_step`, `add_stage_before`, `add_stage_after`, `replace_stage`, `remove_stage`, `load_from`) is defined in §6.7.


Chopper ships F1/F2/F3 as first-class capabilities; domain owners choose which capabilities to use per domain/project. Users without stages still get F1 and F2 (file and proc trimming). Users with stages get generated `<stage>.tcl` run scripts for fine-grained step control.

### 3.7 Trim Workflow

The trim workflow supports both direct CLI mode and project JSON mode.

All examples below assume Chopper is invoked from the domain root (or with an explicit `--domain`). The operational domain root is resolved per §5.1, and `jsons/base.json` plus `jsons/features/*.feature.json` are resolved from there.

**Direct CLI mode (base ± features):**

```
1. Author jsons/base.json (and optionally feature JSONs under jsons/features/)
   Domain owners write JSON manually based on their domain knowledge.

2. chopper validate --base jsons/base.json
   → Phase 1 checks: schema, missing files/procs, empty procs arrays

3. chopper trim --dry-run --base jsons/base.json
   → Full pipeline simulation without file writes
  → Emits: compiled_manifest.json, dependency_graph.json, trim_report.json, trim_report.txt, and optional JSON-lines log events with `diagnostic_code`.

4. chopper trim --base jsons/base.json
   → Live trim
```

**Project JSON mode (same trim semantics, single-file packaging):**

```
1. Author jsons/base.json and feature JSONs; create a project JSON at any chosen path:
   { "$schema": "project-v1", "project": "...", "domain": "...", "base": "...", "features": [...] }

2. chopper validate --project configs/project_abc.json
   → Validates all referenced JSONs via Phase 1 checks

3. chopper trim --dry-run --project configs/project_abc.json
  → Full pipeline simulation; emits reports without writing domain files, plus optional JSON-lines log events with `diagnostic_code`.

4. chopper trim --project configs/project_abc.json
   → Live trim (project metadata recorded in audit artifacts)

5. chopper cleanup --confirm
   → Last-day backup removal
```

**Dry-run output (`--dry-run` emits these; no domain files are written or modified):**
- `compiled_manifest.json` — resolved file and proc treatment decisions (`FULL_COPY`, `PROC_TRIM`, `GENERATED`, `REMOVE`)
- `dependency_graph.json` — full proc trace results including `source`/`iproc_source` and proc call edges
- `trim_report.json` — what would be trimmed, and why each file/proc survives or is removed
- `trim_report.txt` — human-readable projection of `trim_report.json`
- `files_removed.txt` — sorted list of Ward-relative paths physically removed from the rebuilt domain when `$ward` is available, otherwise domain-relative paths, computed as `set(walk(source_root)) − set(kept_paths)` where `source_root` is `<domain>_backup/` after a live trim and `<domain>/` for first-trim `--dry-run`. Each line is `<path>\t<provenance>` where `<provenance>` is one of: `removed-by:<layer_key>:<json_field>` (a later layer's `files.exclude` removed a file that an earlier layer contributed — see `FileProvenance.shadowed_by`), `shadowed-by:<layer_key>:<json_field>` (a later layer downgraded the file out of the kept set via PE/PI overlay), or `default-exclude` (no layer ever named the file — typical of helper `.pl` / `.csh` / `.py` files in EDA domains). Files that no `files.include` pattern named are still listed; this artifact is the user-facing answer to *what did this trim physically delete and why?*. The leading `#` lines document the format.
- `files_kept.txt` — sorted list of domain-relative paths that survive trimming. Each line is `<path>\t<contributor>` where `<contributor>` is `<layer_key>:<json_field>` identifying the **last layer** whose signal won (`FileProvenance.contributed_by`), or `-` if no JSON named the file directly (e.g., F3-`GENERATED` outputs). The leading `#` lines document the format.
- log with all diagnostics emitted with severity, code, location, and hint fields

### 3.8 Valid Capability Combinations

| Combination | Meaning |
|---|---|
| **F1 only** | Whole-file trimming only |
| **F2 only** | Proc-level trimming only |
| **F3 only** | Run-file generation without trimming |
| **F1 + F2** | Mixed file and proc trimming |
| **F1 + F3** | File trimming plus generated run files |
| **F2 + F3** | Proc trimming plus generated run files |
| **F1 + F2 + F3** | Full Chopper capability set |

### 3.9 MCP Integration — removed (out of scope as of 4.0.0)

Chopper previously shipped a stdio-only, read-only **Model Context Protocol** server (`chopper mcp-serve`, the `src/chopper/mcp/` package, and the `PE-04 mcp-protocol-error` diagnostic). It was **removed in 4.0.0**. There is no MCP surface of any kind: no `mcp-serve` subcommand, no `src/chopper/mcp/` package, no `mcp` runtime dependency, and no exit code `4`. `PE-04` is retired (slot preserved, never reused).

MCP is a **closed decision**. No MCP surface — read-only or destructive, stdio or networked — may be reintroduced without explicit user approval and an architecture-doc-first cascade. See `.github/instructions/project.instructions.md` §1 (Closed Decisions) for the authoritative rejection record.

### 3.10 Tool-Command Pool — 0.5.0+

The P4 trace phase resolves every non-dynamic proc call token against the domain's proc index (see §5.4). Tokens that do not resolve to any canonical proc currently emit `TW-02 unresolved-proc-call`. On real EDA domains this fires on every call to a vendor tool command (`get_app_var`, `set_dont_touch`, `create_clock`, `report_timing`, …) — dozens to thousands of warnings per domain, all of which are **not** authoring errors. The volume hides genuine `TW-02` hits on actual missing procs.

The **tool-command pool** is a domain-agnostic set of known external tool-command names. When P4 cannot resolve a token *and* the token's bare leaf name is a member of the pool, the tracer emits `TI-01 known-tool-command` (trace info, exit 0) instead of `TW-02`, and does not add the edge to `dependency_graph.json`.

**Pool composition.** The pool is the union of two sources:

- **Built-in lists**, shipped under `src/chopper/data/tool_commands/*.commands`, always loaded on every run. Six vendor pools are bundled: `pt.commands` (PrimeTime, ~1 050 commands), `pwr.commands` (PrimePower, ~1 110), `pe.commands` (PrimeECO, ~1 000), `ps.commands` (PrimeSim, ~1 000), `fm.commands` (Formality, ~650), `pc.commands` (PrimeClosure, ~350). No per-vendor opt-in is required — the pool is a single flat union of all built-in files.
- **User-supplied lists**, passed via the repeatable CLI flag `--tool-commands <path>` (see §5.1 CLI surface). Each path points to a plain-text file authored outside the domain (infrastructure-owned, not checked into the domain tree); the paths **are not** stored in any JSON, the base schema, or the project JSON. Users layer their own PDK / lib / internal-wrapper command lists on top of the built-ins.

**File format.** Plain text, UTF-8. Tokens are separated by any whitespace (space, tab, newline). Blank lines and lines beginning with `#` (after stripping leading whitespace) are skipped. Token ordering, casing, and duplication are preserved on read and normalized to a single `frozenset[str]` of bare names. No escaping, no quoting, no namespacing — the format matches vendor `help` dumps verbatim (e.g. `primetime -help` → one-line or multi-line token list).

**Matching rule.** A call token matches the pool when **either** of the following holds:

1. The raw token equals a pool entry exactly (e.g. `get_app_var`).
2. The token's namespace-stripped leaf equals a pool entry (e.g. `::snps::get_app_var` → `get_app_var` matches).

This covers the two shapes EDA tool commands appear in (bare and namespace-qualified) without the pool having to enumerate both. The pool contains **bare names only**; qualified names must not appear as entries.

**Emission contract.** When a token matches the pool, the tracer:

1. Emits `TI-01 known-tool-command` (severity info, exit 0) at the call site's line.
2. Records an `Edge` with `status = "tool_command"` and `diagnostic_code = "TI-01"` — visible in `dependency_graph.json` under `unresolved_tokens` so users can still see which tool commands are invoked and from where, without it counting against the warning tally.
3. Does **not** emit `TW-02` for that token.
4. Does **not** add a graph node for the token (tool commands are external and not part of the domain's proc index).

**Non-interference with TW-01 and TW-03.** A token that matches the pool can still be ambiguous (`TW-01`) or dynamic (`TW-03`). The pool is checked **only on the TW-02 unresolved branch** — after namespace resolution has failed. Ambiguity (multiple in-domain matches) and dynamic form are independent conditions and are reported regardless of pool membership.

**Pool is never user-authored per-domain.** Tool-command lists describe tools (PrimeTime, Formality, etc.), not domains. They belong to infrastructure, not to the domain being trimmed. There is no base-JSON field, no feature-JSON field, and no project-JSON field for tool commands. The CLI flag is the sole user-side extension point, and authors typically point it at a single shared `/nfs/.../known_tool_commands/<tool>.commands` file their site maintains.

**Scope cap.** Tool-command pool entries do **not** influence file-level decisions (F1), proc-level decisions (F2), or run-file generation (F3). They are a P4 diagnostic-routing mechanism and nothing else. A tool-command match never causes a file or proc to survive, be copied, or be dropped.

---

## 4. Architecture Rules

> **Vocabulary convention.** Treatment tokens appear in **kebab-case** in JSON payloads and on-disk artifacts (`full-copy`, `proc-trim`, `generated`, `remove`) and in **UPPER_SNAKE_CASE** in prose, tables, diagnostics, and diagrams (`FULL_COPY`, `PROC_TRIM`, `GENERATED`, `REMOVE`). The two forms are interchangeable; Chopper normalizes them on read.

### R1 — Conflict Resolution and File Treatment

This is the single authoritative rule for all include/exclude resolution and file-treatment derivation. R1 is an **ordered overlay**: the base JSON and each selected feature JSON are applied in declared order as successive layers, and the last layer that says something about an item wins. Earlier-layer contributions can be added to, replaced, or removed by later layers.

#### The single rule (R1)

> **R1.** Sources are evaluated in declared order: `base` first, then each entry of `project.features[]` (or `--features`) left-to-right. For each file `F` and each proc `p`, walk the layers in order and apply that layer's signals to a running set:
>
> 1. **`files.include`** — literal path adds `F` to the running set as a `WHOLE` signal at this layer; glob pattern expands against the surface and adds matched files (after the *same layer's own* `files.exclude` glob pruning) as `WHOLE` signals.
> 2. **`files.exclude`** — removes `F` from the running set at this layer, regardless of which earlier layer contributed it. Emit `VE-27 no-op-exclude` (compiler-side; almost always a typo) only when this FE contributes no removal signal: no earlier-layer contribution and no same-layer FI touch (literal or glob).
> 3. **`procedures.include`** — adds `p` (in file `F`) to the running set. If no earlier layer kept `F` whole, this layer contributes `F` as `TRIM(keep += {p})`.
> 4. **`procedures.exclude`** — removes `p` from the running set; if no earlier layer kept `F` whole, this layer contributes `F` as `TRIM(keep = all_procs(F) − PE)`. If `p` is not present in the running set when this layer runs, emit `VE-27`.
> 5. **Same-layer authoring conveniences** still apply (`VW-09 fi-pi-overlap`, `VW-11 fe-pe-same-source-conflict`, `VW-12 pi-pe-same-file`, `VW-13 pe-removes-all-procs`).
> 6. **Shadowing diagnostic** — when a layer actually changes a previous layer's decision (cancels a contribution, removes a proc that was in the running set, replaces a file), emit `VW-21 layer-shadowed` (info-class, exit 0). This is audit-trail only; the layer's intent stands.
>
> After the last layer is applied, the final `treatment` per file is read off the running set:
>
> - `WHOLE` signal still present at end → `FULL_COPY`, all procs survive.
> - `TRIM(keep)` signal still present at end → `PROC_TRIM`, surviving procs = `keep`.
> - No signal present → `REMOVE` (or `GENERATED` if the F3 generator emits the file).
>
> **`provenance.contributed_by`** records the *last* layer whose signal survived. **`provenance.shadowed_by`** records each `(layer, prior_layer)` pair where a `VW-21` fired. Together they form the full overlay timeline.

#### Worked example

Given `base.json` + `feat_a.json` + `feat_b.json` selected in that order:

| File / proc | Base | feat_a | feat_b | Final |
|---|---|---|---|---|
| `core/init.tcl` | FI | — | — | `FULL_COPY` (kept by base) |
| `legacy/old.tcl` | FI | FE | — | `REMOVE` (feat_a shadows base; `VW-21`) |
| `legacy/old.tcl` (alt run) | FI | FE | FI | `FULL_COPY` (feat_b re-includes; `VW-21` for feat_a's veto being overridden) |
| `procs/util.tcl::foo` | PI | — | PE | proc removed; file becomes `TRIM(keep = ...) − {foo}` (`VW-21`) |
| `procs/util.tcl::bar` | — | PI | — | survives (added by feat_a) |
| `optional/x.tcl` | — | FE | — | `VE-27 no-op-exclude` (nothing to remove) |

#### Terminology

| Term | Meaning |
|---|---|
| **Layer** | One JSON applied at one position in the overlay sequence: `base`, then each selected feature in declared order. |
| **Running set** | The mutable `{file → treatment}` and `{proc → kept?}` map carried left-to-right through the layers. |
| **FI_literal(L)** | Literal file paths in layer `L`'s `files.include` |
| **FI_glob(L)** | Files matched by wildcard patterns in layer `L`'s `files.include`, after `L`'s own `files.exclude` glob pruning |
| **FE(L)** | `files.exclude` patterns in layer `L` |
| **PI(L)** | `procedures.include` entries in layer `L` |
| **PE(L)** | `procedures.exclude` entries in layer `L` |
| **Global PI** | The set of procs in the running set at end of fold (used to seed P4 trace) |
| **PI+** | Transitive trace expansion of Global PI — **reporting-only; no survival effect** |
| **PT** | Traced-only procs: PI+ − Global PI — **reporting-only** |

#### Per-layer signal classification (within one JSON)

Within one layer `L` and one file `F`, the layer's authored signals classify into a single contribution to the running set:

| Inputs in layer `L` for file `F` | `L`'s effect on the running set | Note |
|---|---|---|
| Nothing | no change | — |
| Only FI (literal or surviving glob), no PE, no PI | set `F → WHOLE` | Layer claims whole file. |
| Only PI entries, no FI, no PE | set `F → TRIM(keep = running_keep(F) ∪ PI(L, F))` | Per-proc include adds to the running keep set. |
| FI **and** PE (any combination of PI) | set `F → TRIM(keep = all_procs(F) − PE(L, F))` | Same-layer PE qualifies same-layer FI. If PI is also present, emit `VW-09` and ignore PI here. |
| PE only, no FI | set `F → TRIM(keep = (running_keep(F) or all_procs(F)) − PE(L, F))` | If `F` was already kept whole by an earlier layer, this layer demotes it to `TRIM` and removes PE procs (`VW-21` fires). |
| FI **and** PI (no PE) | set `F → WHOLE` | Emit `VW-09` (PI redundant on WHOLE). |
| Only FE (no FI, no PI, no PE) | remove `F` from running set | If `F` was contributed by an earlier layer, emit `VW-21`. If no earlier layer contributes `F` and no glob match at this layer, emit `VE-27`. |
| FE **and** PE, no FI, no PI | no change for this layer (same-layer contradiction) | Emit `VW-11`. |

#### End-of-fold treatment derivation

After all layers are applied, for each file `F`:

1. If running set has `F → WHOLE` → **treatment = `FULL_COPY`**, all procs survive.
2. Else if running set has `F → TRIM(keep)` → **treatment = `PROC_TRIM`**, surviving procs = `keep`.
3. Else → if `F` is F3-`GENERATED`, treatment is `GENERATED`; otherwise **treatment = `REMOVE`**.

**Key invariants implied by the overlay:**
- The final state of any file or proc is determined by the **last layer** that mentioned it.
- A feature can remove or replace anything an earlier layer contributed, including base content. Order of features is therefore semantically authoritative — not just for F3.
- Same-layer authoring conveniences (`VW-09`, `VW-11`, `VW-12`, `VW-13`) are unchanged: those rules are local invariants within one JSON.
- Every layer transition that actually changes a prior decision emits `VW-21 layer-shadowed` so the audit bundle records the overlay history.
- Excludes that match nothing in the running set and nothing on disk via glob fire `VE-27 no-op-exclude` — the typo safety net.

#### Interaction warnings

These warnings are non-fatal (exit 0) and escalate to errors in `--strict`.

| Code | Slug | Scope | Condition |
|---|---|---|---|
| `VW-09` | `fi-pi-overlap` | Same-layer | Layer `L` has file `F` in FI and also has procs of `F` in PI (no PE in `L`). PI is redundant. |
| `VW-11` | `fe-pe-same-source-conflict` | Same-layer | Layer `L` has `F` in both `files.exclude` and has PE entries for `F`, with no PI in `L`. Both are removal-within-`L` signals; `L` makes no change for `F`. |
| `VW-12` | `pi-pe-same-file` | Same-layer | Layer `L` has PI and PE entries for the same file `F`. PI wins; PE is ignored for `F` within `L`. |
| `VW-13` | `pe-removes-all-procs` | Same-layer | Layer `L`'s PE set covers every proc in `F` and no PI restores any. File survives as comment/blank-only. |
| `VW-21` | `layer-shadowed` | Cross-layer | Layer `L` actually changed a decision made by an earlier layer (cancelled an include, replaced a file, removed a proc that was in the running set). Informational; audit trail only. |
| `VE-27` | `no-op-exclude` | Validation error | A layer's `files.exclude` or `procedures.exclude` entry does not match anything in the running set and (for FE) does not match any file via glob. Almost always a typo. |

> **Retired codes.** `VW-18 cross-source-pe-vetoed` and `VW-19 cross-source-fe-vetoed` were the cross-source veto warnings under the prior additive-only model. Under the ordered-overlay R1 they cannot fire (a later layer's PE/FE *actually removes* the proc/file rather than being vetoed). Both slots are marked `RETIRED` in the diagnostic registry.

#### Per-file interaction matrix (single layer)

Retained for authoring reference. Columns describe what **one** layer's authored signals do to the running set when the layer is applied.

| # | FI | FE | PI | PE | Effect on running set | Diagnostic |
|---|---|---|---|---|---|---|
| 1 | — | — | — | — | no change | — |
| 2 | ✓ | — | — | — | set `F → WHOLE` | `VW-21` if earlier layer had different state |
| 3 | — | ✓ | — | — | remove `F` from running set | `VW-21` if `F` was present; `VE-27` if not present and no glob match |
| 4 | ✓ | ✓ | — | — | literal FI: `F → WHOLE`; glob-only pruned by same-layer FE: no change | — |
| 5 | — | — | ✓ | — | union PI into `F`'s `keep` (or downgrade `WHOLE` → `TRIM(keep = running_keep ∪ PI)`) | `VW-21` if downgrading WHOLE |
| 6 | — | — | — | ✓ | `F → TRIM(keep = (running_keep or all_procs(F)) − PE)` | `VW-21` if removing procs that were kept |
| 7 | — | — | ✓ | ✓ | union PI; PE ignored | `VW-12` |
| 8 | ✓ | — | ✓ | — | `F → WHOLE` (PI redundant) | `VW-09` |
| 9 | ✓ | — | — | ✓ | `F → TRIM(keep = all − PE)` | — |
| 10 | ✓ | — | ✓ | ✓ | `F → TRIM(keep = all − PE)` (PI redundant with FI; PE qualifies it) | `VW-09` |
| 11 | — | ✓ | ✓ | — | union PI into `keep`; layer's FE on `F` is overridden by same-layer PI | — |
| 12 | — | ✓ | — | ✓ | no change (same-layer FE+PE contradiction) | `VW-11` |
| 13 | — | ✓ | ✓ | ✓ | union PI into `keep`; FE+PE both overridden by PI | `VW-12` |
| 14 | ✓ | ✓ | ✓ | — | literal FI: `F → WHOLE`; glob-only pruned by FE: no change | `VW-09` |
| 15 | ✓ | ✓ | — | ✓ | literal FI: `F → TRIM(keep = all − PE)`; glob-only pruned: no change | — |
| 16 | ✓ | ✓ | ✓ | ✓ | literal FI: `F → TRIM(keep = all − PE)`; glob-only: union PI into `keep` | `VW-09` or `VW-12` |

**Reading the matrix under the overlay model:**

- Each row describes what *this layer alone* does. The final treatment is read off the running set after all layers are applied.
- Row 3 (FE alone): under the new model, FE *actually removes* the file if an earlier layer contributed it. There is no veto — the layer wins.
- Row 6 (PE alone): if no earlier layer touched `F`, this layer establishes `F` as `PROC_TRIM` with all procs except PE. If an earlier layer kept `F` whole, this layer downgrades it to `TRIM` and emits `VW-21`.

#### Layered authority statement

Later layers win over earlier layers. The base is the first layer; selected features are subsequent layers in declared order. A feature can add new content, remove base content, replace base content, or strip individual procs from base files — and the audit bundle records every such change as a `VW-21 layer-shadowed` event with `(layer, prior_layer)` provenance. Order is semantically authoritative for F1, F2, **and** F3.

### R2 — Default Action Is Exclude

**Default exclude is fixed.**

This is no longer configurable.

| Policy | Result |
|---|---|
| File explicitly kept by F1 | Survives as a whole file |
| File explicitly kept by F2 | Survives only as a proc-trimmed file |
| File not explicitly kept anywhere | Removed |

**Architectural consequence:** remove any notion of a global default-include mode from the design.

### R3 — Tracing Is Default-On and Conservative

**Tracing is the most important feature in Chopper.** It is enabled by default and designed conservatively.

#### Why tracing matters from a product perspective

- It is the primary difference between Chopper and file-only tools.
- It reduces domain-owner authoring cost by removing manual dependency enumeration from the happy path.
- It lowers trim risk during the 2-week delivery window.
- It improves adoption because users can describe entry-point procs instead of entire call chains.
- It improves auditability because Chopper can explain *why* a proc survived.
- It makes re-trim viable because the dependency expansion can be reproduced from saved inputs and trace logs.
- Its conservative design means that users are always in control of the final proc set via explicit JSON entries, and they can trust that Chopper will never guess wrong and include an unexpected proc.
- The purpose is to help users find the minimal proc set without manual guesswork, not to automatically produce a final proc set without user input.

#### Why tracing matters from a software engineering perspective

- It is the main determinant of correctness for proc-chopped output.
- It defines whether F2 is a real architecture feature or just a text-deletion utility.
- It drives parser design, validation design, audit design, and test strategy.
- It forces deterministic domain-bounded dependency resolution.
- It dictates conservative behavior for unresolved dynamic Tcl patterns.

#### Tracing rules

| Rule | Behavior |
|---|---|
| **Default mode** | On for all proc-level selections |
| **Boundary** | Restricted to the selected domain path |
| **Static calls** | Traced |
| **Dynamic dispatch** | Not auto-resolved; logged as warning |
| **Outside-domain procs** | Assumed external; not auto-included |
| **Unknown file needed by traced proc** | Warning; owner must explicitly include file or proc |

#### What Chopper traces

- Direct Tcl command calls where the first token is a concrete proc name
- Bracketed proc calls such as `[helper_proc ...]`
- Calls inside standard control structures such as `if`, `foreach`, `while`, and `switch`
- Namespace-qualified proc calls when resolvable

**SNORT-absorbed extraction guardrails (hybrid approach):**

Chopper intentionally combines two approaches:
- **Keep Chopper's deterministic tracer core** (typed parser output, lexical namespace resolution, sorted BFS frontier, stable `TW-*` diagnostics).
- **Absorb SNORT's production-proven false-positive suppression** from `_IsProcFoundInLine()` so call extraction is robust on real EDA Tcl.

Suppression filter classes applied before a token becomes a trace candidate:
- Comment-only and metadata contexts (`# ...`, `define_proc_attributes`, proc-arg position)
- Variable and dynamic forms (`$token`, `eval`, `uplevel`)
- Logging/print string mentions (`iproc_msg`, `puts`, `echo`, similar log procs)
- Non-proc argument usage (`get_app_var` / `set_app_var`, label-only string positions)

Embedded bracket calls inside log strings remain real calls and are preserved (e.g., `iproc_msg -info "[helper_proc $x]"`).

#### What Chopper does not automatically resolve

- `$cmd $args`
- `eval "..."`
- `uplevel ...`
- Runtime command aliasing or other dynamic metaprogramming
- Vendor/tool built-ins not present in the domain proc index (treated as external/unresolved for proc tracing)

#### Conservative behavior

```
{"phase":"trace","event":"edge_resolved","caller":"flow_procs.tcl::read_libs","callee":"setup_library_paths","edge_type":"proc_call"}
{"phase":"trace","event":"edge_resolved","caller":"flow_procs.tcl::setup_library_paths","callee":"resolve_lib_path","edge_type":"proc_call"}
{"phase":"trace","event":"edge_unresolved","caller":"utils.tcl::helper","token":"$cmd","diagnostic_code":"TW-03","reason":"dynamic-call-form"}
```

**Conservative policy:** when Chopper cannot prove a dependency, it warns instead of inventing one.

#### Trace Log Pattern and Call-Tree Contract

Trace output must be consistent across parser extraction, tracer resolution, diagnostics, and artifacts.

1. **Streaming logs** (optional JSON lines, e.g. `.chopper/chopper.log`) emit per-event trace records during dry-run and live trim.
2. **Machine artifact** (`dependency_graph.json`) stores the complete resolved call tree and file-dependency edges.
3. **Diagnostics** use stable registry codes from `technical_docs/DIAGNOSTIC_CODES.md`.

**Trace warning code mapping:**

| Scenario | Diagnostic code |
|---|---|
| Ambiguous proc match | `TW-01` |
| Unresolved proc after namespace resolution (external/cross-domain) | `TW-02` |
| Dynamic or syntactically unresolvable call form (`$cmd`, `eval`, `uplevel`) | `TW-03` |
| Cycle in call graph | `TW-04` |

**Minimal call-tree edge record (`dependency_graph.json`):**

| Field | Meaning |
|---|---|
| `edge_type` | `proc_call`, `source`, or `iproc_source` |
| `from` | Caller canonical proc or source file context |
| `to` | Resolved callee canonical proc or file path |
| `status` | `resolved`, `ambiguous`, `unresolved`, or `dynamic` |
| `diagnostic_code` | Optional; present for warning edges (`TW-*`) |
| `line` | Source line where the edge was discovered |



#### Trace expansion algorithm

Trace expansion is a fixed-point walk over a per-run proc index built from every Tcl file in the selected domain. The walk is **breadth-first with a lexicographically sorted frontier** to guarantee deterministic output regardless of filesystem walk order.

1. Parse all domain Tcl files **in lexicographic order of domain-relative path** (`sorted(domain_path.rglob('*.tcl'))`) and build the proc index before evaluating any `procedures.include` entry.
2. Normalize every proc to canonical form `relative/path.tcl::qualified_name`.
3. For each indexed proc body, extract raw call tokens and file-source references using parser contracts and SNORT-absorbed suppression filters:
  - command-boundary aware parsing (newlines/semicolons respecting braces/quotes)
  - bracket call extraction (`[helper_proc ...]`)
  - suppression of false positives (comment/log/metadata/variable contexts)
  - extraction of literal `source` / `iproc_source` file edges
4. Seed the trace frontier with all explicit PI entries after validating that the requested file/proc pairs exist. Sort the frontier lexicographically by canonical proc name.
5. While the frontier is non-empty, pop the **smallest** canonical proc name from the frontier. If it is already in the traced set, skip it. Otherwise add it to the traced set and resolve all extracted call tokens.
6. Resolve literal proc calls with a deterministic lexical namespace contract:
  - `::ns::helper` means the absolute qualified proc name `ns::helper` only.
  - `ns::helper` means "look in the caller namespace first, then global". For a caller in `a::b`, the ordered candidates are `a::b::ns::helper`, then `ns::helper`.
  - `helper` means "look in the caller namespace first, then global". For a caller in `a::b`, the ordered candidates are `a::b::helper`, then `helper`.
  - `namespace import`, command-path lookup, aliasing, and `namespace unknown` are out of scope for v1 and are never guessed.
7. For each candidate qualified name in order, resolve only when exactly one canonical proc inside the selected domain has that qualified name.
8. If multiple canonical procs match the same candidate qualified name, emit `TW-01` and do NOT resolve.
9. If no in-domain proc matches after lexical namespace resolution, emit `TW-02` and do NOT resolve. Chopper does not search other domains.
10. Dynamic or syntactically unresolvable call forms emit `TW-03`.
11. If a newly resolved callee is already in the traced set (cycle), do NOT add it to the frontier again. This naturally terminates cycles. Emit `TW-04` WARNING diagnostic listing the cycle path (e.g., `A → B → A`). Both procs in the cycle are included in PI+ (trace set only, not auto-survival) — cycles mean mutual dependency.
12. Append any newly resolved callees (not yet in the traced set) to the frontier in sorted order.
13. Emit PI+ and call-tree edges in deterministic order: source file path, then canonical proc name.

The tracer must never guess across ambiguous candidates and must never cross the selected domain boundary.

#### Proc index contract

The proc index is the source of truth for F2 and tracing. Each entry must contain at least:

| Field | Meaning |
|---|---|
| `canonical_name` | `relative/path.tcl::qualified_name` |
| `short_name` | Name as authored in JSON for that file |
| `qualified_name` | Namespace-qualified proc name with leading `::` stripped |
| `source_file` | Domain-relative Tcl file path |
| `start_line` / `end_line` | Inclusive proc span in the source file |
| `body_start_line` / `body_end_line` | Inclusive body span used for trace extraction |
| `namespace_path` | Namespace context captured from `namespace eval` nesting |
| `dpa_start_line` / `dpa_end_line` | Optional span for `define_proc_attributes` / `define_proc_arguments` immediately associated with this proc |
| `comment_start_line` / `comment_end_line` | Optional contiguous doc-comment banner span immediately preceding this proc |
| `calls` | Deduplicated raw call tokens extracted from the proc body after false-positive suppression; tracer resolves these tokens |
| `source_refs` | Deduplicated literal file refs extracted from `source` / `iproc_source` in the proc body |

Hard rules:
- `canonical_name` must be unique in one domain parse/index.
- Duplicate proc definitions in one file are parser errors (`PE-01`); index materialization may keep last-definition for deterministic reporting but the file remains invalid until fixed.
- Unbalanced Tcl structure that prevents reliable proc boundaries is a parser error (`PE-02`).
- Duplicate `short_name` values within the same file are invalid for trace/trim selection and must emit a diagnostic.
- DPA association is strict: mismatched `define_proc_attributes` ownership emits `PW-11`; orphan DPA blocks emit `PI-04`.
- `calls` and `source_refs` are extraction outputs (parser contract), not resolved outcomes; resolution and warning emission happen in tracer/compiler.
- If a call token resolves to zero candidates, emit `TW-02` and do not auto-include a guess.
- If a call token resolves to multiple candidates, emit `TW-01` and do not auto-include any candidate.
- Dynamic/syntactically unresolvable call forms emit `TW-03`; cycles detected during expansion emit `TW-04`.

Parser-to-tracer handoff contract:
- Parser owns structural extraction (proc spans, comment spans, DPA spans, `calls`, `source_refs`) and parser diagnostics (`PE-*`, `PW-*`, `PI-*`).
- Tracer/compiler owns token resolution, namespace disambiguation, call-tree edge materialization, and trace diagnostics (`TW-*`).
- `dependency_graph.json` is the canonical call-tree artifact derived from this handoff.

#### `iproc_source`, `source`, and hook semantics

Chopper treats file sourcing as a file-dependency graph separate from proc tracing.

| Pattern | Contract |
|---|---|
| `source foo.tcl` | File edge to `foo.tcl` when the argument is a literal relative path |
| `iproc_source -file foo.tcl` | File edge to `foo.tcl` |
| `iproc_source -file foo.tcl -optional` | File edge remains recorded; missing target is non-fatal unless explicitly required elsewhere |
| `iproc_source -file foo.tcl -required` | Surviving reference to missing target is a validation error |
| `iproc_source -file foo.tcl -quiet` | Does not suppress Chopper diagnostics; it only affects original flow behavior |
| `iproc_source -file foo.tcl -use_hooks` | Discover `pre_foo.tcl` / `post_foo.tcl` candidates; report in dry-run diagnostics; do not copy unless explicitly included in selected JSON |

Additional rules:
- Hook discovery is informational unless selected JSON explicitly includes the hook file.
- Hook resolution is same-directory only and uses the literal basename of the referenced file.
- Hook files not explicitly included in selected JSON are ignored during trim, but are still captured in diagnostics and dry-run reports.
- Hook files are file-level artifacts; Chopper does not proc-trim them unless they are independently selected as Tcl proc files.
- Dynamic sourcing expressions containing unresolved `$`, `eval`, `uplevel`, or runtime-generated file names are never guessed; they produce diagnostics and require explicit owner input.

### R4 — F3 Uses Plain Strings by Design

In F3, steps are stored and processed as plain strings.

```json
"steps": [
    "source $ward/global/snps/$env(flow)/setup.tcl",
    "step_load.tcl",
    "fc.app_options.tcl",
    "#if {[info exists ivar(csi,extraction_dir)]}",
    "step_csi_recreate.tcl",
    "#else",
    "step_csi_load_spec.tcl",
    "#endif",
    "step_close.tcl"
]
```

#### Why this is intentional

Real flow steps are not one clean datatype. A step may be:
- A Tcl filename
- A raw `source` command
- An `iproc_source`-style expression
- An ivar-based reference
- An optional step
- A conditional directive such as `#if` / `#else` / `#endif`

Trying to force all of these into one rigid semantic step model recreates FlowBuilder complexity and makes the system harder to adopt.

#### The actual tradeoff

Treating steps as opaque strings makes composition easy, but it reduces how much Chopper can semantically validate.

**This is the problem:** Chopper can guarantee ordering and assembly, but it cannot fully understand the meaning of every arbitrary Tcl string step.

**This is the mitigation:**
- Keep F3 string-based for authoring flexibility
- Cross-validate generated steps against F1/F2 output where possible
- Warn on obvious missing file/proc references
- Keep domain-owner review in the workflow

This is an **architectural tradeoff**, not a bug in the design.

### R5 — Backup-and-Rebuild

Chopper always rebuilds from a clean backup rather than editing in place.

| Rule | Behavior |
|---|---|
| **First trim** | Rename original domain to `_backup`, build new trimmed domain |
| **Re-trim** | Rebuild from `_backup` |
| **Cleanup timing** | Delete backups on the last day of the trim window |
| **Why** | Safety first; clean retrim; no destructive incremental editing |


---

## 5. Pipeline, Compilation, and Workflow

Chopper executes an **eight-phase pipeline**. Every invocation — live trim or dry-run — follows the same decision sequence. The difference is operational: live trim rewrites the domain in P5 and emits the audit bundle in P7, while `--dry-run` suppresses domain mutations, runs only manifest-derivable post-validation checks in P6, and still emits report artifacts in `.chopper/`.

### 5.1 Input Modes

Chopper supports three input modes. Exactly one mode is used per invocation.

| Mode | CLI Form | Description |
|---|---|---|
| **Base-only** | `--base jsons/base.json` | Trim using only the base JSON, no features |
| **Base + Features** | `--base jsons/base.json --features jsons/features/f1.feature.json,jsons/features/f2.feature.json` | Trim using base JSON with one or more feature overlays |
| **Project** | `--project <path-to-project.json>` | A single project JSON that packages the same base path, ordered feature paths, project metadata, and selection rationale in one file |

By default, owner-curated base and feature JSONs live under the domain root at `jsons/base.json` and `jsons/features/*.feature.json`. Project JSON has no fixed home and is always passed explicitly to `--project`.

#### §5.1.0 — Domain-name resolution, base auto-discovery, feature-name lookup

**`--domain` accepts three forms (4.1.0+):**

| Form | Example | Behaviour |
|---|---|---|
| Absolute path | `--domain /work/fev_formality` | Used as-is; no `$ward` lookup |
| Existing relative directory | `--domain fev_formality` (if `./fev_formality/` exists) | Used as-is; no `$ward` lookup |
| Bare name or vendor-qualified name | `--domain fev_formality` or `--domain snps/fev_formality` | Searched under `$ward/global/<vendor>/<name>` |

When a bare name is supplied, Chopper enumerates direct children of `$ward/global/` and checks for a matching sub-directory. Unique match → used. Two or more matches → `VE-34 ambiguous-domain-name` (exit 2; use `vendor/name`). No match → `VE-33 domain-not-found` (exit 2). `$ward` not set → `VE-32 ward-env-not-set` (exit 2). Vendor-qualified `vendor/name` resolves directly to `$ward/global/<vendor>/<name>` without enumeration.

**`--domain` accepts a CSV list for multi-domain sequential trim** — see §5.1.2.

**`--base` auto-discovery (4.1.0+):** When `--domain` is provided and `--base` is not supplied (and `--project` is not used), Chopper searches:
1. `<domain_root>/jsons/base.json`
2. `<domain_root>/jsons/<domain_leaf_name>.json`

If neither is found → `VE-35 base-autodiscovery-failed` (exit 2). Pass `--base <path>` to override.

**`--features` as names (4.1.0+):** `--features` accepts feature names (e.g. `--features dft,power`) in addition to explicit file paths. A token is resolved as a name when it contains no path separator and does not end with `.json`. Resolution enumerates `<domain_root>/jsons/features/*.feature.json` — `dft` maps to `dft.feature.json`. Unresolved name → `VE-36 feature-name-not-found` (exit 2; message includes closest matches via difflib). Tokens with `/`, `\`, or `.json` suffix pass through as direct paths (backward compat).

#### §5.1.2 — Multi-domain sequential trim (4.1.0+)

`--domain` accepts a comma-separated list (e.g. `--domain fev_formality,fev_conformal`). Chopper processes domains **sequentially** — each domain runs completely before the next begins. Base auto-discovery and feature-name resolution run independently per domain. The final exit code is `max(exit_codes)` across all domains. `validate` and `loc` support multi-domain with the same semantics.

`--project` is mutually exclusive with `--base` and `--features`. Providing both is `VE-11` (`conflicting-cli-options`, exit code 2).

For `chopper validate` only, any entry in the `--features` comma-separated list may be a directory path instead of a file path. A directory entry expands in place to the sorted list of its immediate `*.json` children (non-recursive, lexicographic order, POSIX-normalized). File and directory entries may be mixed freely. This expansion is a validate-only authoring convenience — it lets regressions validate an entire `jsons/features/` folder in one command. `chopper trim` (and `--project` in any subcommand) require explicit per-file paths so that the ordered feature sequence recorded in audit artifacts is unambiguous; passing a directory to `trim` fails at config load.

Given the same domain root, base JSON, and ordered feature list, project mode and direct CLI mode must produce identical compilation and trim results.

When `--project` is provided, the project JSON resolves `base` and `features` against the operational domain root (see "Domain-root resolution" below), not against the project JSON file location. The resolved inputs then enter the same compilation pipeline as `--base`/`--features`. The `project`, `owner`, `release_branch`, and `notes` fields from the project JSON are recorded in audit artifacts.

#### §5.1.3 — Project-config auto-discovery (4.2.0+)

When `--domain` resolves in **name-mode** (ward root and domain logical name are both known) and **none** of `--project`, `--base`, or `--features` are explicitly supplied, Chopper performs a secondary lookup in `$ward/project/` to find a project-level configuration file for the domain.

**Discovery path:** `$ward/project/<domain_logical_name>/<leaf>.<type>` where `<domain_logical_name>` is the resolved `vendor/name` (e.g. `snps/fev_formality`) and `<leaf>` is the last component (e.g. `fev_formality`).

**Search order (first match wins):**

| File | Behaviour |
|---|---|
| `<leaf>.project.json` | Treated as `--project <path>`. All project JSON semantics apply (domain-field match, base/features resolution against `domain_root`, audit recording). |
| `<leaf>.project.features.config` | Plain-text feature list: one feature name per line. Blank lines and `#`-comment lines are ignored. Resolved as if `--features <names>` were passed; base JSON is still auto-discovered per §5.1.0. The resolved path is stored in `RunConfig.project_config_path` and surfaced in the domain run header (§5.5.16). |

**Auto-discovery is suppressed when any of the following are true:**
- `--project`, `--base`, or `--features` is explicitly provided (any one suppresses discovery).
- `--domain` resolved in path-mode (no ward root known).
- `$ward/project/<domain_logical_name>/` does not exist or neither probe file is present.

Auto-discovery is silent when neither file is found — Chopper continues with base-only mode (VE-35 applies if base auto-discovery also fails). No new diagnostic code is emitted for successful discovery; the found path is shown in the domain run header. See FR-49.

#### Domain-root resolution

Chopper computes the operational domain root from CLI flags before any other phase runs. The resolution rule is **two steps, applied in order**:

1. **Pick the candidate.** If `--domain <path>` is provided, the candidate is `Path(args.domain).resolve()` and the current working directory is **not** consulted. Otherwise, the candidate is `Path.cwd().resolve()`.
2. **Conditional `_backup` redirect.** If `candidate.name` ends in `_backup` **and** the stripped sibling exists as a directory, the operational domain root becomes that sibling; the original candidate is treated as the previous-run snapshot. The redirect is **applied at most once** — `foo_backup_backup` redirects to `foo_backup` only if `foo_backup/` exists, never recursively to `foo`. When the redirect fires, Chopper emits `VI-03 domain-suffix-strip-applied` (info severity, exit 0) so the resolution is visible in stderr and in the audit bundle. If the stripped sibling does **not** exist on disk, the candidate is honored as-is — a coincidentally `_backup`-suffixed domain that has no live sibling is a fresh domain, not a Chopper backup.

The `_backup` suffix is **Chopper-reserved** as the snapshot of the previous live trim. The conditional redirect protects two failure modes that share a single corrective action — but only when there is a live sibling to redirect to:

- **cwd accident** — user `cd`'d into `<domain>_backup/` (often because a Windows shell holds a handle on the renamed-to-backup directory after `mv`/rename) and ran `chopper trim` with no `--domain`. With a live `<domain>/` sibling present, the next run would otherwise build `<domain>_backup_backup/`; the redirect prevents that.
- **flag confusion** — user typed `--domain /work/mini_backup` thinking the backup is the source of truth, or via a script that stitched `${path}_backup` together. With a live `mini/` sibling present, Chopper would otherwise treat the backup as a fresh domain and build `mini_backup_backup/`, severing the link to the real domain; the redirect prevents that.

Both cases now resolve identically: redirect to the live sibling, emit `VI-03`, run the case-table lookup against the real `(domain_root, domain_root + "_backup")` pair. When no live sibling exists, the path is taken at face value and falls into the normal case-table (Case 1/3/4 as appropriate against the original candidate).

##### Operational target vs source of truth

The two roles are independent:

- **Operational target** — the path the run rebuilds. Selected by the resolution rule above (`--domain` → cwd, then conditional suffix redirect). This is the user's choice (modulo the redirect when the live sibling exists).
- **Source of truth** — the path Chopper *reads* file contents from for trimming. Selected by the case-table in §2.8 against `(domain_root, domain_root + "_backup")`:
  - **Case 1** (`domain_root` exists, backup missing) — source = `domain_root` itself; backup is created during P5 as the snapshot.
  - **Case 2** (both exist) — source = `<domain>_backup/` (the prior snapshot is authoritative; the half-rebuilt or stale `domain_root` is discarded).
  - **Case 3** (`domain_root` missing, backup exists) — source = `<domain>_backup/` (recovery rebuild).
  - **Case 4** (both missing) — fatal, `VE-21`, exit 2.

Users do not pick the source. The filesystem state does. This separation is what lets the conditional redirect be safe: when the redirect fires, the case-table behaves correctly because the live sibling exists by construction; when it does not fire, the candidate enters the case-table on its own merits.

When `--project` is provided, the project JSON `domain` field is a required identifier for audit and consistency. It must match the **basename of the resolved domain root** (after the conditional redirect) using a **case-insensitive** comparison: `domain_root.name.casefold() == project.domain.casefold()`. Full-path comparisons elsewhere in Chopper remain case-sensitive; only the domain-name field is case-folded because operators may author on Windows and run on Linux grid nodes. Any mismatch is reported as `VE-17 project-domain-mismatch` (exit 1; see also `VE-12` / `VE-13` for structural variants). `--domain` and the project `domain` field are reconciled by the same `VE-17` check — there is no separate "cwd does not match `--domain`" exit-2 gate, because `--domain` (after the conditional redirect) is the source of truth, not a constraint to validate against cwd.

The detailed CLI reference with all arguments, flags, and per-subcommand usage is in [technical_docs/CLI_REFERENCE.md](CLI_REFERENCE.md).

### 5.1.1 Example Invocations

```bash
# Base only
chopper trim --base jsons/base.json

# Base + features
chopper trim --base jsons/base.json \
  --features jsons/features/dft.feature.json,jsons/features/power.feature.json

# Project JSON at a user-supplied path (same result as equivalent resolved --base/--features)
chopper trim --project configs/project_abc.json

# Dry-run with project JSON
chopper trim --dry-run --project configs/project_abc.json

# Read-only LOC report (no domain or `.chopper/` writes)
chopper loc --base jsons/base.json
chopper loc --project configs/project_abc.json
```

### 5.2 Eight-Phase Pipeline

```
  P0  Detect trim state        first trim vs re-trim (backup detection)
   │
   ▼
  P1  Read & validate inputs   load base + feature JSONs; Phase 1 schema/structural checks;
   │                           expand `files.include` glob patterns against the on-disk
   │                           domain to populate `surface_files` (the set of files P2 parses)
   │
   ▼
  P2  Parse domain Tcl         build per-file ParsedFile entries for every `.tcl` in
   │                           `surface_files` (with diagnostics), and harvest a
   │                           full-domain proc index by silently parsing every
   │                           other `.tcl` under `domain_root` so P4 can resolve
   │                           calls into non-surfaced files
   │
   ▼
  P3  Compile selections       merge JSON rules → FI_literal, FI_glob, FE, PI, PE;
   │                           re-evaluate glob patterns against the parsed universe;
   │                           apply R1 conflict resolution;
   │                           resolve per-file PI/PE interaction; emit VW-09..VW-13;
   │                           produce surviving-files set and surviving-procs set
   │
   ▼
  P4  Trace dependencies       expand PI → PI+ via BFS call-tree walk;
   │                           emit dependency_graph.json and TW-* diagnostics;
   │                           PI+ is reporting-only — it does NOT modify the surviving sets
   │
   ▼
  P5  Build output             copy surviving files from backup; proc-delete unwanted
   │                           definitions from PROC_TRIM files; generate F3 stage scripts;
   │                           normalize indentation for every surviving/generated `.tcl`;
   │                           write directly into rebuilt domain/  [NO DOMAIN WRITES in --dry-run]
   │
   ▼
  P6  Post-trim validate       Phase 2 checks against the resolved output:
   │                           brace balance, dangling proc refs, missing source targets
   │
   ▼
  P7  Finalize & audit         emit .chopper/ artifacts for the run
                               [in --dry-run: report-only artifacts, no domain writes]
```

**Phase dependency rule:** each phase receives the output of the previous phase and produces a well-defined intermediate. No phase reaches back to re-run an earlier phase.

### 5.2.1 End-to-End Walkthrough

This walkthrough expands the pipeline diagram into the concrete data flow each phase consumes, produces, and hands off. It is the narrative companion to the boxes in §5.2.

#### P0 — Detect trim state

- Check for sibling `<domain>_backup/` next to the selected domain.
  - Present → this is a **re-trim** or recovery run; rebuild `domain/` from `<domain>_backup/` before any further work so P1–P7 always see the pristine source.
  - Absent → this is a **first trim**; the original domain will become `<domain>_backup/` before rebuild begins.
- Owner: `orchestrator/` (`DomainStateService`).
- Output: a boolean run mode (`first_trim` vs `re_trim`) attached to the run context; no JSON artifact yet.

#### P1 — Read and validate inputs

- Resolve the input mode: `--project <path>` (loads a project JSON which names `base` and ordered `features`), or explicit `--base <path> [--feature <path> ...]`.
- Schema-validate every loaded JSON against `schemas/*.schema.json`.
- Run Phase 1 structural checks: file existence, glob well-formedness, `feature.domain` matches `base.domain`, `depends_on` prerequisites precede dependents in the project `features` order, etc.
- Build `surface_files` — the union of every domain-relative path contributed by any source. Literal `files.include` entries and the file paths in `procedures.include` / `procedures.exclude` are added directly. `files.include` patterns containing `*`, `?`, or `[` are expanded against the on-disk domain via a single deterministic BFS walk (with `.chopper/` excluded), using the same `**`-aware glob semantics as P3 so that any file P1 surfaces will also be matched by P3's conflict resolution. `files.exclude` globs are *not* expanded here — they are resolved in P3 against the parsed universe. When a glob-driven walk occurs, the file list is cached in `LoadedConfig.domain_file_cache` for P2 reuse (O1 optimization).
- Emit `VE-*` on hard failures (non-zero exit); emit `VW-*` / `VI-*` on soft issues. `VW-03 glob-matches-nothing` is emitted by `validate_pre` when a `files.include` glob produces zero matches. A missing literal in `files.include` is the hard `VE-06`; a missing literal in `files.exclude` is the soft `VW-25 exclude-target-absent` (the exclusion is a no-op because the target is already gone) and the pipeline proceeds — the absent literal is harmlessly filtered at P3 (`merge_service` `_distill_facts`, which keeps only `files.exclude` literals present on the surface).
- Owner: `config/` + `validator/` (Phase 1 validation).
- Output: a frozen `LoadedConfig` carrying `(base_json, [feature_jsons], surface_files, domain_file_cache, ...)` — no on-disk artifact.

#### P2 — Parse domain Tcl

- Iterate `loaded.surface_files` (lex-sorted POSIX form) and parse only the `.tcl` entries; non-Tcl companion files in `surface_files` are file-level participants (F1) and never enter the tokenizer.
- After the surface parse, walk the rest of the domain via `ctx.fs` and silently parse every other `.tcl` file under `domain_root` (`.chopper/` excluded) for the sole purpose of populating the canonical-name index. If `loaded.domain_file_cache` is non-empty (P1 walked the domain for glob expansion), the cache is filtered for `.tcl` files instead of re-walking (O1 optimization). Diagnostics from these non-surfaced files are dropped — the user did not ask Chopper to scrutinise them, so emitting `PE-02` / `PW-*` against them would be misleading. The procs they define still enter the index so P4 can resolve a surfaced caller's call into a non-surfaced callee and report the actual defining file.
- For each surfaced file, read text through the filesystem service and call `parse_file(file_path=path, text=text, on_diagnostic=...)`, which returns `list[ProcEntry]`.
- Each `ProcEntry` carries `canonical_name`, `short_name`, `qualified_name`, `namespace_path`, body and DPA/comment spans, and the two handoff fields `calls` (raw call tokens) and `source_refs` (literal `source` / `iproc_source` targets). See [IMPLEMENTATION.md (parser section)](IMPLEMENTATION.md) §1.6 for the full field list.
- The parser **does not resolve** `calls` — those are textual tokens. Resolution is P4's job.
- Parser-family diagnostics (`PE-*` / `PW-*` / `PI-*`) flow through the `on_diagnostic` callback only for surfaced files.
- Owner: `parser/`.
- Output: `ParseResult(files, index)` where `files` is the surfaced subset (the compiler operates exclusively on this view) and `index` is the **full-domain** canonical-name map. The relaxed model invariant (see `ParseResult.__post_init__`) requires `files.procs ⊆ index` but allows `index` to carry extra entries whose `defined_in` is not in `files`. Trace remains reporting-only — a wider index never changes which files or procs survive (Critical Principle #7).

#### P3 — Compile selections

- Consumes the JSON bundle from P1 and the proc index from P2.
- Treats the base JSON and each selected feature JSON as successive *layers* in an ordered overlay, and applies the single-rule R1 fold from §5.3:
  1. Initialize an empty running set.
  2. For each layer in declared order (`base` first, then features left-to-right): apply the layer's `files.include` / `files.exclude` / `procedures.include` / `procedures.exclude` to the running set under R1. Emit same-layer warnings (`VW-09`, `VW-11`, `VW-12`, `VW-13`), cross-layer shadow events (`VW-21`), and no-op-exclude errors (`VE-27`) as encountered.
  3. After the last layer, derive each file's `treatment` from the final running set: `WHOLE → FULL_COPY`; `TRIM(keep) → PROC_TRIM`; absent → `REMOVE` (or `GENERATED` for F3 outputs).
- Record provenance on every manifest entry: `contributed_by` (the last layer whose signal survived), `treatment`, `surviving_procs[]`, and `shadowed_by[]` (layer transitions that fired `VW-21`).
- Ordering: F1, F2, **and** F3 are order-sensitive; later layers win over earlier ones. Feature order is authoritative throughout.
- Owner: `compiler/`.
- Output: `CompiledManifest` (frozen in-memory object) and `.chopper/compiled_manifest.json` (identical on disk). The manifest is immutable after P3 returns.

#### P4 — Trace dependencies

- Seed the BFS frontier with `PI` (the explicit `procedures.include` entries validated in P1 against the proc index from P2).
- Walk the call graph breadth-first using the deterministic lexical namespace contract from §5.4. For every popped proc, read its `calls` tokens and resolve each against the global proc index: exactly one match → resolved edge; multiple → `TW-01`; zero → `TW-02`; dynamic form → `TW-03`; cycle → `TW-04`.
- Produce `PI+` (full transitive closure) and `PT = PI+ − PI` (traced-only set).
- Owner: `compiler/` (`trace.py`).
- Output: `.chopper/dependency_graph.json` and `TW-*` diagnostics.
- **Critical contract:** `PI+` is reporting-only. P4 does not mutate the surviving files or surviving procs sets frozen by P3. See §5.4 and Critical Principle #7 in `.github/instructions/project.instructions.md`.

#### P5 — Build output (skipped under `--dry-run`)

- For each manifest entry:
  - `FULL_COPY` → copy the file from backup into the rebuilt `domain/` tree byte-for-byte, regardless of extension. `.tcl` files included as `FULL_COPY` are **not** rewritten by P5c.
  - `PROC_TRIM` → for `.tcl` manifest entries only, read the file from backup, delete the line spans of every proc not in `surviving_procs(F)`, rewrite directly into the rebuilt `domain/` tree. If the computed drop set is empty (every proc found in the backup already belongs to the keep set), Chopper still writes the rebuilt file and emits `VW-22 proc-trim-no-drop`. This typically indicates that `<domain>_backup/` was replaced with a prior run's post-trim output rather than the original pre-trim source; the rebuilt file will be byte-identical to the backup.
  - `GENERATED` → run the F3 generator (`flow_actions` is authoritative for ordering here).
  - `REMOVE` → record the omission; do not write or content-read the file during P5.
- After P5a/P5b writes complete, P5c indentation-normalizes every emitted `.tcl` file whose manifest treatment is `PROC_TRIM` or `GENERATED` **only when `base.options.indent` is `true`** (see §3.1). The flag defaults to `false`, in which case P5c is a no-op pass-through and the `PROC_TRIM`/`GENERATED` outputs reach disk exactly as P5a/P5b wrote them. `FULL_COPY` outputs (Tcl and non-Tcl alike) are never touched by P5c regardless of the flag. When enabled, the formatter mirrors the legacy Perl brace-driven logic: strip each line's leading whitespace, adjust a running four-space indent from unescaped `{` / `}` characters, outdent lines whose first structural token closes a block, and half-outdent `topology:`, `interface:`, `constraint:`, `action:`, `end`, and `pattern <name>` marker lines. P5c is also skipped under `--dry-run`.
- P5c updates the live `TrimReport` byte counts only for `PROC_TRIM` `.tcl` outcomes after formatting (P6 compares rebuilt-domain bytes against the final `TrimReport`; recording pre-format byte counts would falsely trigger `VW-10` size mismatches). `FULL_COPY` byte counts are never re-stamped — the source bytes already match the on-disk output.
- **P5d — Companion-file sync:** for every `PROC_TRIM` file whose POSIX basename matches `default_rules.<sfx>.tcl`, filter two companion files that were already `FULL_COPY`-written into the rebuilt domain:
  - `<dir>/default_config.<sfx>.csv` — each data row whose first comma-separated column (proc name) is absent from the final compiled PI set is deleted entirely; blank lines and `#`-comment lines are kept.
  - `<dir>/default_milestone.<sfx>.tcl` — each `change_config <ProcName> ...` line whose `<ProcName>` is absent from the final compiled PI set is deleted entirely; all other lines are kept.
  - The **surviving proc set** is the final compiled PI set from `CompiledManifest.proc_decisions` for the matching `default_rules.<sfx>.tcl` file, accounting for both `procedures.include` and `procedures.exclude` across all feature layers (R1 overlay).
  - The companion files are expected to be declared as `files.include` entries, so they are unconditionally present in the rebuilt domain before P5d runs.
  - If a companion file is absent, `VW-24 companion-file-missing` is emitted and sync is skipped for that file.
  - When sync succeeds, `VI-04 companion-sync-applied` is emitted for the filtered file.
  - P5d updates the `TrimReport` byte counts for the modified `FULL_COPY` companion outcomes so P6's `VW-10` size check remains accurate.
  - P5d is skipped under `--dry-run` (no files were written, so nothing to filter).
- Write `.chopper/trim_report.json` and `trim_report.txt` describing every file and proc operation and the diagnostics correlated with each.
- Owner: `trimmer/` + `generators/`.
- Output: the rebuilt `domain/` tree plus the trim-report artifacts. If P5 fails mid-run, the partially rebuilt `domain/` is left in place and the intact `<domain>_backup/` is the recovery source for the next invocation.

#### P6 — Post-trim validate

- Phase 2 validation runs against the rebuilt output (or, under `--dry-run`, against the synthetic trim plan):
  - under a live trim: brace balance across every `.tcl` file rewritten or indentation-normalized during P5,
  - dangling proc references (every call target in a surviving file must resolve to a surviving proc or an accepted external such as a vendor/Tcl built-in),
  - missing `source` / `iproc_source` targets (must resolve to a surviving file or an accepted external).
- Emit `VE-*` / `VW-*`; `--strict` changes the final process exit code if any warning is present, but does **not** rewrite diagnostic severity.
- Owner: `validator/` (Phase 2).
- Output: updated diagnostics log; optionally aborts the run before P7.

#### P7 — Finalize and audit

- Under a normal run: leave the rebuilt `domain/` in place, preserve `<domain>_backup/` per the re-trim model, and emit the `.chopper/` bundle for the run.
- Under `--dry-run`: leave the domain untouched and emit only the report artifacts under `.chopper/`.
- Write the full audit bundle under `.chopper/`: `chopper_run.json`, `compiled_manifest.json`, `dependency_graph.json`, `trim_report.json`, `trim_report.txt`, `diagnostics.json`, `trim_stats.json`, `files_kept.txt`, `files_removed.txt`, `p4_commands.txt`, `files_exclude_p4.txt`.
- Owner: `audit/`.
- Output: the audit trail (see §5.5).

### 5.3 Compilation Model (P3 Detail)

P3 is the deterministic core of the pipeline. It consumes the parsed JSON rules and the proc index from P2 and produces frozen sets that drive every subsequent phase. P3 is an **ordered overlay fold**: the base JSON and each selected feature JSON are applied in declared order as successive layers, and every manifest entry records the layer that last contributed it plus the chain of layer transitions that shadowed earlier decisions.

```
  Inputs from P1 + P2:
    base JSON + selected feature JSONs (in declared order)
    proc index (all procs in domain, from P2)
                    │
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  Initialize:                                    │
  │    running_files: dict[Path, FileSignal] = {}   │
  │    layers = [base, *features_in_order]          │
  └─────────────────────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  For each layer L in layers:                    │
  │    1. Expand L.files.include:                   │
  │       FI_literal(L) = exact paths               │
  │       FI_glob(L) = wildcard matches             │
  │           − L.files.exclude glob pruning        │
  │    2. For each F in (FI_literal ∪ FI_glob):     │
  │       prior = running_files.get(F)              │
  │       new = WHOLE  (or TRIM if same-layer PE)   │
  │       running_files[F] = new                    │
  │       if prior and prior != new: emit VW-21     │
  │           (record (L, prior_layer) shadow)      │
  │    3. For each F in L.files.exclude (literal):  │
  │       if F in running_files:                    │
  │           remove F; emit VW-21                  │
  │       elif F not matched by any glob and not    │
  │            in running_files:                    │
  │           emit VE-27                            │
  │    4. For each (F, p) in L.procedures.include:  │
  │       same-layer rules (VW-09 / VW-12)          │
  │       union p into running_files[F].keep        │
  │       emit VW-21 if downgrading prior WHOLE     │
  │    5. For each (F, p) in L.procedures.exclude:  │
  │       same-layer rules (VW-11 / VW-12 / VW-13)  │
  │       remove p from running_files[F].keep       │
  │       if p was kept by an earlier layer:        │
  │           emit VW-21                            │
  │       elif p not in running_files[F].keep and   │
  │            not in all_procs(F):                 │
  │           emit VE-27                            │
  └─────────────────────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  Derive treatment per file F:                   │
  │    if running_files[F] == WHOLE:                │
  │        treatment(F) = FULL_COPY                 │
  │        surviving_procs(F) = all                 │
  │    elif running_files[F] == TRIM(keep):         │
  │        treatment(F) = PROC_TRIM                 │
  │        surviving_procs(F) = keep                │
  │    else:                                        │
  │        if F is F3 generator output:             │
  │            treatment(F) = GENERATED             │
  │        else: treatment(F) = REMOVE              │
  └─────────────────────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  Record provenance on every manifest entry:     │
  │    contributed_by   (last layer whose signal    │
  │                       survived)                 │
  │    treatment        (FULL_COPY / PROC_TRIM /    │
  │                      GENERATED / REMOVE)        │
  │    surviving_procs[]                            │
  │    shadowed_by[]    ((layer, prior_layer)       │
  │                      pairs that fired VW-21)    │
  └─────────────────────────────────────────────────┘
                    │
                    ▼
            compiled_manifest.json
```

**Ordering:** R1 is order-sensitive end-to-end. Feature order in `project.features[]` (or `--features`) is authoritative for F1, F2, and F3.

**Iteration order (emission determinism).** Within a single layer, the compiler iterates in this fixed order so every diagnostic (`VW-09`..`VW-13`, `VW-21`, `VE-27`, etc.) is emitted in a reproducible sequence:

1. **Layers:** `base` first; then each entry of `project.features[]` in the order given (or the CLI `--features` order when no project JSON is used). Topological sort of `depends_on` runs before P3; by the time the fold starts, the sequence is fixed.
2. **Within a layer:** `files.include` (literals first, then globs in lex order); then `files.exclude` (lex order); then `procedures.include` (lex by file then proc); then `procedures.exclude` (lex by file then proc).
3. **Files within a step:** lexicographic POSIX order.
4. **Procs within a file:** lexicographic order on `qualified_name`.
5. **Emission:** every warning is emitted at the point it is detected during the fold. Later fold steps never reorder earlier emissions.

Golden tests in `tests/unit/compiler/` snapshot this ordering; any change to the iteration rule is a breaking change to the diagnostic sequence.

When `--project` is used, Chopper resolves the base and selected feature paths from the project JSON before entering P3. Equivalent resolved selections produce identical results regardless of input mode.

**Frozen output:** the compiled manifest is immutable after P3 completes. P4 (trace) reads it but does not modify the surviving sets.

### 5.3.1 Internal Compilation Contract

Detailed compilation data models, execution-freeze rules, and implementation contracts live alongside the phase-owned core model modules in `src/chopper/core/models_*.py` and the compiler implementation in `src/chopper/compiler/`.

This architecture document defines what Chopper must do. How the implementation structures and preserves those contracts is split across three peer documents: [`technical_docs/ENGINEERING.md`](ENGINEERING.md) (ports, services, stage layering), [`technical_docs/IMPLEMENTATION.md` (parser section)](IMPLEMENTATION.md) (P2 engineering baseline), and [`technical_docs/IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) (stage gates, DoD, checkpoints).

### 5.4 Trace Phase (P4 Detail)

P4 runs the BFS trace expansion (R3) seeded by PI. Its outputs are:

| Output | Consumer | Survival effect |
|---|---|---|
| **PI+** (full transitive call set) | `dependency_graph.json`, trim report | **None** — reporting only |
| **PT** (PI+ − PI, traced-only procs) | Trim report, diagnostics | **None** — reporting only |
| **Call-tree edges** | `dependency_graph.json` | **None** — reporting only |
| **TW-\* diagnostics** | Diagnostics log, trim report | **None** — advisory warnings |
| **TI-\* diagnostics** | Diagnostics log | **None** — informational, not counted against `--strict` warning tally |

PI+ helps the domain owner understand what their explicit selections depend on. It never adds procs or files to the surviving set.

**Per-token resolution order (deterministic).** For every non-dynamic call token the tracer applies this decision ladder exactly once and in this order:

1. **TW-03 dynamic guard** — if the token is dynamic (`$cmd`, bracketed substitution, empty after stripping), emit `TW-03` and stop.
2. **Candidate resolution** — build the lexical-namespace candidate list (absolute / relative-then-bare) and look each up in the domain proc index.
3. **Unique match → edge** — if exactly one candidate resolves, record a resolved `Edge` and enqueue the callee.
4. **Multiple matches → TW-01** — if any candidate resolves to more than one canonical proc, emit `TW-01 ambiguous-proc-match` and stop.
5. **No match → tool-command pool check** — if zero candidates resolve, the tracer checks the token against the tool-command pool (§3.10). The raw token and its namespace-stripped leaf are both tested. On a pool hit: emit `TI-01 known-tool-command`, record an `Edge` with `status = "tool_command"`, and stop.
6. **Pool miss → TW-02** — emit `TW-02 unresolved-proc-call` and record an `Edge` with `status = "unresolved"`.

Rule ordering is fixed: the pool is checked **only after** namespace resolution has failed, and **never** suppresses `TW-01` (ambiguity is an authoring issue even for tool-command names) or `TW-03` (dynamic call forms are always unresolvable statically). A pool hit is always the final rung that would have otherwise produced a `TW-02`; it cannot intercept any other diagnostic.

**Frontier and visited-set semantics (BFS contract).** The BFS frontier does **not** deduplicate on enqueue. If proc `A` calls `B` three times (from three different call sites), all three enqueue operations push `B` onto the frontier and all three are recorded as distinct `Edge` records in `dependency_graph.json` with their own `call_site` locations. Deduplication happens at the **visited-set level only**: when a canonical name is popped from the frontier, if it is already in `visited` the pop is a no-op (no call extraction, no re-enqueue, no duplicate `TW-*` diagnostic). This design preserves the full caller → callee edge set for downstream analysis (users routinely care *where* a proc was called from, not just *whether* it was called), while still guaranteeing BFS termination in the presence of cycles. The frontier is sorted lex-ascending before each pop so the traversal is deterministic.

**Source-edge survival rule (R3 corollary).** `source` and `iproc_source` call tokens extracted from proc bodies become edges in `dependency_graph.json` with `kind: "source"`, **identical in type to proc-call edges**. They are **reporting-only**: they never copy files, never retain procs, and never influence trimming. Survival of a sourced file still requires an explicit `files.include` entry; survival of a sourced proc still requires an explicit `procedures.include` entry. A `source` or `iproc_source` pointing at a file that did not survive trim emits `VW-06 source-file-removed` at P6.

**Worked BFS example (end-to-end).**

Given six procs across two files and a JSON selection of only `main`:

```tcl
# file: flow.tcl
proc main {} {      ;# explicitly included
    step_a
    step_b
    $dyn_cmd        ;# dynamic call → TW-03
}
proc step_a {} {
    helper          ;# two definitions exist for `helper` → TW-01
    recursive       ;# self-recursion → TW-04
}
proc step_b {} {
    missing_util    ;# not defined anywhere → TW-02
}
proc recursive {} { recursive }   ;# cycle terminator

# file: utils_a.tcl
proc helper {} { return 1 }
# file: utils_b.tcl
proc helper {} { return 2 }
```

JSON selection:

```json
{"procedures": {"include": [{"file": "flow.tcl", "procs": ["main"]}]}}
```

BFS trace (P4) with frontier `[main]`, visited `{}`:

| Step | Pop | Resolve calls | Emit | Enqueue | Visited after step |
|---|---|---|---|---|---|
| 1 | `flow.tcl::main` | `step_a` → `flow.tcl::step_a` (resolved); `step_b` → `flow.tcl::step_b` (resolved); `$dyn_cmd` → unresolvable | `TW-03 dynamic-call-form` at `flow.tcl::main` | `step_a`, `step_b` (lex-sorted) | `{main}` |
| 2 | `flow.tcl::step_a` | `helper` → **two matches** (`utils_a.tcl::helper`, `utils_b.tcl::helper` both have qualified name `helper`); `recursive` → `flow.tcl::recursive` (resolved) | `TW-01 ambiguous-proc-match` at `flow.tcl::step_a` line N listing both candidates | `recursive` | `{main, step_a}` |
| 3 | `flow.tcl::step_b` | `missing_util` → **zero matches** after namespace search | `TW-02 unresolved-proc-call` at `flow.tcl::step_b` line N | (none) | `{main, step_a, step_b}` |
| 4 | `flow.tcl::recursive` | `recursive` → already in visited set | `TW-04 cycle-in-call-graph` listing cycle path `recursive → recursive` | (none — visited-set terminates) | `{main, step_a, step_b, recursive}` |
| 5 | (frontier empty) | — | — | — | — |

**Outcomes:**

- **Trimmed `flow.tcl` contains only `main`.** Procs `step_a`, `step_b`, `recursive` appear as nodes in `dependency_graph.json` (reachable from PI via trace), but only `main` is named in `procedures.include`, so only `main` is copied. `step_a`/`step_b`/`recursive` are logged in `trim_report.json` as **traced-only (PT)**, not surviving.
- **Neither `utils_a.tcl::helper` nor `utils_b.tcl::helper` is copied.** Both were candidates for an ambiguous match but neither was selected (ambiguity is a warning, not a resolution); neither is named in any `procedures.include` entry.
- **`utils_a.tcl` and `utils_b.tcl` are removed from the trimmed domain** (not in `files.include`, no proc named from them is in `procedures.include`).
- **Diagnostic set emitted by P4:** `{TW-01, TW-02, TW-03, TW-04}`. All are warnings; P4 never blocks P5.
- **To retain `step_a` and `recursive`** the author adds them to `procedures.include`. To retain one of the ambiguous `helper` procs the author names it explicitly in `procedures.include` (keyed by its canonical `file::qualified_name`, e.g. `{"file": "utils_a.tcl", "procs": ["helper"]}`). To retain `utils_a.tcl` whole the author adds it to `files.include`.

**Worked example (trace is logging, not copying):**

Given a base JSON with `procedures.include = [{"file": "utils.tcl", "procs": ["foo"]}]` and a proc body:

```tcl
proc foo {} {
    bar
}
proc bar {} {
    return "helper"
}
```

Outcome after a full Chopper run:

| Artifact | `foo` | `bar` |
|---|---|---|
| Copied into trimmed `utils.tcl` (P5) | ✅ yes — named in `procedures.include` | ❌ no — not in any JSON |
| Node in `dependency_graph.json` (P4) | ✅ yes | ✅ yes (reached from `foo`) |
| Edge `foo → bar` in `dependency_graph.json` | — | ✅ yes, `status = resolved` |
| Row in `trim_report.json` `proc_operations` | ✅ kept | ✅ logged as traced-only (PT) |
| `TW-*` diagnostic | none unless ambiguous/dynamic/cycle | none unless ambiguous/dynamic/cycle |

To make `bar` survive trimming the author must add it to `procedures.include` (or include the whole file with `files.include`). Trace expansion is a visibility tool, not a survival mechanism.

**Frozen-manifest invariant.** `CompiledManifest` is constructed exactly once by `CompilerService.run()` (P3) as a `@dataclass(frozen=True)`. `TracerService` (P4) and `GeneratorService` (P5b) receive read-only references — they **MUST NOT** mutate the manifest, and the dataclass's frozen flag guarantees any attempt raises `FrozenInstanceError`, which the orchestrator treats as a programmer error (exit 3). The architectural consequence: **P4 cannot promote traced callees into `proc_decisions` or `file_decisions`.** Users inspect `dependency_graph.json` and then edit their JSONs if they want more content to survive — the engine never silently widens the surviving set on their behalf. This invariant is what makes the trace "reporting-only" more than a style guideline; it is structurally enforceable.

### 5.4.1 Per-File Parsing to Global Call Tree

The parser is strictly per-file and never reaches across file boundaries. The tracer is strictly global and relies on a single domain-wide index. This subsection makes the handoff between the two explicit.

**Step 1 — Per-file parse (P2, per file).**
`parse_file(file_path=tcl_file, text=text, on_diagnostic=...)` returns a `list[ProcEntry]` for that single file. The public parser entry point that the runner actually calls is `ParserService.run(ctx, files)` (see [`technical_docs/ENGINEERING.md`](ENGINEERING.md) §9.2); `parse_file()` is the pure internal utility the service wraps, and the service owns filesystem reads through `ctx.fs`. Each entry carries its `canonical_name` (`relative/path.tcl::qualified_name`), its `namespace_path` captured from enclosing `namespace eval` blocks, the body span, and two unresolved handoff fields:

- `calls: tuple[str, ...]` — raw call tokens extracted from the body after false-positive suppression. These are textual tokens such as `"helper"` or `"::foo::bar"`; the parser does not know whether they resolve and never attempts to.
- `source_refs: tuple[str, ...]` — literal `source` / `iproc_source` file targets.

At this point there is no cross-file knowledge. The parser runs file-by-file and holds no memory between files.

**Per-file return contract on `PE-*` diagnostics.** `parse_file()` never raises for user-input errors; it emits diagnostics and decides what to return based on how corrupted the file is:

| Emitted code | `parse_file()` returns | Rationale |
|---|---|---|
| `PE-01` duplicate proc | full `ProcEntry` list with **one** entry per name (last definition's span wins) | Index is still usable; the duplicate is recorded once. |
| `PE-02` unbalanced braces | **`[]`** (empty list) | The file's brace structure is untrustworthy; no proc span can be reliably extracted. Downstream `VE-07 proc-not-in-file` will fire if any JSON referenced procs in this file. |
| `PE-03` ambiguous short name | full list | Ambiguity is resolved at trace time (P4) by namespace rules; parser cannot pick. |
| Any `PW-*` / `PI-*` | full list | Warnings and info diagnostics never degrade the return value. |

The orchestrator treats any `ERROR`-severity P2 diagnostic as a phase-gate failure (see plan §6.2): the runner aborts before P3, so a corrupted proc index never reaches the compiler.

**Canonical-name test vectors.** The authoritative canonical-name derivation table (ten vectors covering file root, single/nested namespaces, absolute-name override, subdirectory files, and the computed-name skip case) lives in [`technical_docs/IMPLEMENTATION.md` (parser section)](IMPLEMENTATION.md) §1.4.3.1. Implementations and tests reference that table; this architecture doc keeps the format contract (`"<domain-relative-posix-path>::<qualified_name>"`) and the survival rules (this section, above) without duplicating the per-vector list.

**Step 2 — Assemble the global proc index (P2, parser-owned).**
The parser service concatenates every file's `ProcEntry` list into **one flat dictionary keyed by `canonical_name`** as part of P2. The walk covers the entire domain (`.chopper/` excluded) so the index is **full-domain**, not limited to the surfaced subset:

```python
# P2 — ParserService.run
proc_index: dict[str, ProcEntry] = {}
# 2a. Surface parse: emit diagnostics, populate ParsedFile entries.
for tcl_file in sorted(loaded.surface_files):  # only .tcl entries
    text = fs.read_text(domain_root / tcl_file)
    for entry in parse_file(file_path=tcl_file, text=text, on_diagnostic=ctx.diag.emit):
        proc_index[entry.canonical_name] = entry
# 2b. Full-domain harvest: silent index-only parse for non-surfaced files.
for tcl_file in sorted(domain_walk(fs, domain_root)):  # excludes .chopper/
    if tcl_file in loaded.surface_files:
        continue
    text = fs.read_text(domain_root / tcl_file)
    for entry in parse_file(file_path=tcl_file, text=text, on_diagnostic=lambda _d: None):
        proc_index.setdefault(entry.canonical_name, entry)
```

Files are walked in lexicographic order so the index is built the same way on every run and every host. The full-domain coverage lets P4 resolve a call from a surfaced caller into a callee defined in a file the user did not include, and `dependency_graph.json` records the actual defining path. Trace remains reporting-only: the wider index never adds survivors (Critical Principle #7) — it only sharpens the diagnostic so the user can see in the audit bundle which file holds the missing definition and add it to the JSON in the next run.

> **Why a single global index, not per-file tables?** Tcl namespaces cross file boundaries. A proc defined in `a.tcl` inside `namespace eval ::foo { ... }` is callable from `b.tcl` as either `foo::proc_name` or (if the caller is in `::foo`) just `proc_name`. Only a single domain-wide index can resolve that correctly; per-file tables would force a second stitching pass that does the same work.
>
> **Why full-domain, not surface-only?** A surface-only index (P2 parses only the user's selection) makes `TW-02 unresolved-proc-call` fire on every call into a non-surfaced helper — the warning says "I don't know where this is" when the truth is "I never looked at the file it lives in". A full-domain index lets the tracer resolve the call and report the callee's actual `defined_in` path. `TW-02` then truly means "no in-domain proc with this name exists" — an external/cross-domain call. The user reads `dependency_graph.json`, sees the resolved edge points at a file not in the JSON, and adds it (whole-file or proc-level) in the next iteration. The full-domain harvest stops at the domain boundary: files outside `domain_root` are never read (consistent with the "DO NOT TOUCH" rule in §2.4) and the `.chopper/` audit subtree is always excluded.

**Step 3 — Resolve calls during the BFS walk (P4, per popped proc).**
The tracer pops one proc off the frontier, reads its `calls` tokens, and resolves each token under the deterministic lexical namespace contract from §5.4 ("Trace expansion algorithm", step 6):

- `::ns::helper` — absolute; exact match on qualified name `ns::helper`.
- `ns::helper` — relative; try `<caller_namespace>::ns::helper`, then `ns::helper` at global scope.
- `helper` — bare; try `<caller_namespace>::helper`, then `helper` at global scope.

For each candidate qualified name, the tracer searches the proc index for exactly one match within the selected domain:

- Exactly one match → resolved edge, callee queued into the frontier if unseen.
- Multiple matches → `TW-01`, no resolution.
- Zero matches after all candidates exhausted → `TW-02`, no resolution.
- Dynamic / syntactically unresolvable token (`$cmd`, `[x] ...`) → `TW-03`.
- Callee already in the traced set → cycle; `TW-04` with the cycle path, and the callee is not re-queued (BFS visited-set terminates).

**Design consequences of this split:**

- The parser can be tested in complete isolation. No other files are required, no index assembly, no namespace walking.
- Trace resolution is deterministic independent of parse order because the index is built in sorted order and the frontier is always popped in lex order.
- Adding a new file to the domain cannot change any existing `ProcEntry`; it can only add new keys to the index and new resolution candidates.
- The parser-to-tracer handoff is the contract enforced by the `ProcEntry.calls` / `source_refs` fields and their invariants in [IMPLEMENTATION.md (parser section)](IMPLEMENTATION.md) §1.6.1. Violations of that contract are caught in parser unit tests, not in integration tests.

### 5.5 Audit Trail

Every Chopper run produces a `.chopper/` directory in the domain root containing machine-readable and human-readable artifacts that fully explain what happened and why. These artifacts enable reproducibility, code-review, diff tooling, and future GUI rendering.

> **Version control.** `.chopper/` is a per-run audit artifact, not a tracked source. Domain owners should add `.chopper/` to `.gitignore` and are expected to clean it up manually between runs if desired. Chopper does not prune `.chopper/` automatically.

#### 5.5.1 Directory layout

```
domain/
├── .chopper/
│   ├── run_id                        ← plain text UUID for log correlation
│   ├── chopper_run.json              ← run metadata (who, when, how, exit code)
│   ├── input_base.json               ← exact copy of base JSON used
│   ├── input_features/               ← exact copies of feature JSONs (ordered)
│   │   ├── 01_dft.feature.json
│   │   └── 02_power.feature.json
│   ├── input_project.json            ← optional; present only when --project is used
│   ├── compiled_manifest.json        ← frozen P3 output: file/proc treatments + reasons
│   ├── dependency_graph.json         ← P4 output: call-tree edges, PI+, TW-* warnings
│   ├── diagnostics.json              ← all VE/VW/VI/TW/PE/PW/PI diagnostics with context
│   ├── trim_report.json              ← summary: counts, before/after, validation results
│   ├── trim_report.txt              ← human-readable projection of trim_report.json
│   ├── trim_stats.json              ← numbers: files before/after, procs before/after, SLOC delta
│   ├── files_kept.txt               ← surviving paths + last-contributing layer
│   ├── files_removed.txt            ← physically-removed paths + provenance
│   ├── p4_commands.txt              ← Perforce command list (p4 edit / add / delete) — see §5.5.14
│   └── files_exclude_p4.txt         ← standalone exclude_file_list path set — see §5.5.14
└── ...trimmed domain files...
```

**Naming rule for input_features/:** feature JSONs are prefixed with a two-digit sequence number reflecting selected feature order (e.g., `01_`, `02_`). This preserves the application order that determined the compilation result.

#### 5.5.2 `chopper_run.json` — run metadata

This is the first artifact to read when investigating a trim result. It answers: who ran what, when, how, and what happened.

| Field | Type | Description |
|---|---|---|
| `chopper_version` | string | Chopper version string |
| `run_id` | string | UUID v4 unique to this run |
| `command` | string | Subcommand executed: `trim`, `validate`, `cleanup` |
| `mode` | string | `live` or `dry-run` |
| `domain` | string | Domain identifier (basename of domain root) |
| `domain_path` | string | Absolute path to domain root |
| `backup_path` | string | Absolute path to `_backup` directory (live trim only) |
| `base_json` | string | Domain-relative path to base JSON used |
| `feature_jsons` | string[] | Ordered list of domain-relative feature JSON paths |
| `project_json` | string \| null | Domain-relative path to project JSON, or null |
| `project_name` | string | From project JSON `project` field (empty if not using project mode) |
| `project_owner` | string | From project JSON `owner` field |
| `release_branch` | string | From project JSON `release_branch` field |
| `project_notes` | string[] | From project JSON `notes` field |
| `trim_state` | string | `first-trim` or `re-trim` (P0 result) |
| `timestamp_start` | string | ISO 8601 UTC start time |
| `timestamp_end` | string | ISO 8601 UTC end time |
| `duration_seconds` | number | Wall-clock duration |
| `exit_code` | integer | 0 = success, 1 = validation errors, 2 = CLI usage error |
| `diagnostics_summary` | object | `{"errors": N, "warnings": N, "info": N}` |

**Example:**

```json
{
  "chopper_version": "<package-version>",
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "command": "trim",
  "mode": "live",
  "domain": "fev_formality",
  "domain_path": "/tools/domains/fev_formality",
  "backup_path": "/tools/domains/fev_formality_backup",
  "base_json": "jsons/base.json",
  "feature_jsons": ["jsons/features/dft.feature.json", "jsons/features/power.feature.json"],
  "project_json": "configs/project_abc.json",
  "project_name": "ABC_tapeout",
  "project_owner": "jdoe",
  "release_branch": "release/2026q2",
  "project_notes": ["DFT enabled per ECO-1234", "Power feature for low-power mode"],
  "trim_state": "first-trim",
  "timestamp_start": "2026-04-19T14:30:00Z",
  "timestamp_end": "2026-04-19T14:31:12Z",
  "duration_seconds": 72,
  "exit_code": 0,
  "diagnostics_summary": {"errors": 0, "warnings": 3, "info": 5}
}
```

#### 5.5.3 `compiled_manifest.json` — frozen compilation result

This is the P3 output. It is the single source of truth for what Chopper decided to do with every file and proc in the domain. It is frozen before P4 and never modified after.

**Top-level structure:**

| Field | Type | Description |
|---|---|---|
| `chopper_version` | string | Chopper version |
| `run_id` | string | Correlates with `chopper_run.json` |
| `domain` | string | Domain identifier |
| `inputs` | object | `{ "base": "...", "features": [...], "project": "..." }` |
| `files` | object[] | Per-file treatment entries (see below) |
| `procedures` | object | `{ "surviving": [...], "excluded": [...], "traced": [...] }` |
| `flow_actions` | object[] | Resolved F3 stage/step actions |
| `interaction_warnings` | object[] | VW-09..VW-13 warnings emitted during compilation |

**Per-file entry in `files`:**

| Field | Type | Description |
|---|---|---|
| `path` | string | Domain-relative file path |
| `treatment` | string | `full-copy`, `proc-trim`, `generated`, `remove` |
| `reason` | string | Why this treatment was chosen (e.g., `fi-literal`, `pi-overlay`, `pe-overlay`, `fe-glob-pruned`, `fe-shadow`, `default-exclude`) |
| `contributed_by` | string \| null | The single last layer (`base` or feature `name`) whose signal produced the surviving treatment. `null` for `REMOVE` and `GENERATED`. |
| `input_sources` | string[] | Every layer that referenced this file at any point during the fold, keyed by `base` or feature `name` (e.g., `["base:files.include", "dft:procedures.include"]`). Used by P5 to copy the input JSONs into the rebuilt domain. |
| `shadowed_by` | object[] | Layer transitions that fired `VW-21` for this file. Each entry: `{ layer, prior_layer, action }` where `action ∈ {"replace", "remove", "downgrade-whole-to-trim", "add-proc", "remove-proc"}`. Empty array if no shadowing occurred. |
| `surviving_procs` | string[] \| null | For `proc-trim` files: canonical names of procs that survive. Null for other treatments. |
| `excluded_procs` | string[] \| null | For `proc-trim` files using PE model: canonical names of procs removed. Null otherwise. |
| `proc_model` | string \| null | `overlay` (the file's surviving proc set comes from the R1 fold), or null if not proc-trimmed |

**Per-proc entry in `procedures.surviving`:**

| Field | Type | Description |
|---|---|---|
| `canonical_name` | string | `relative/path.tcl::qualified_name` |
| `source_file` | string | Domain-relative file path |
| `selection_source` | string | Which input added this proc (e.g., `base:procedures.include`) |

**Per-proc entry in `procedures.traced`:**

| Field | Type | Description |
|---|---|---|
| `canonical_name` | string | `relative/path.tcl::qualified_name` |
| `source_file` | string | Domain-relative file path |
| `trace_depth` | integer | BFS depth from nearest PI seed |
| `survival_effect` | string | Always `"none"` — reporting only |

#### 5.5.4 `dependency_graph.json` — call-tree and file edges

This is the P4 output. It contains the full resolved call tree and file-dependency edges.

**Top-level structure:**

| Field | Type | Description |
|---|---|---|
| `chopper_version` | string | Chopper version |
| `run_id` | string | Correlates with other artifacts |
| `pi_seeds` | string[] | Canonical names of PI procs that seeded the trace |
| `pi_plus` | string[] | Full transitive closure (PI+) |
| `pt` | string[] | Traced-only procs (PI+ − PI) |
| `edges` | object[] | Call-tree and file-dependency edges (see below) |
| `unresolved` | object[] | Tokens that could not be resolved |

**Per-edge entry:**

| Field | Type | Description |
|---|---|---|
| `edge_type` | string | `proc_call`, `source`, or `iproc_source` |
| `from` | string | Caller canonical proc name or file context |
| `to` | string | Resolved callee canonical proc name or file path |
| `status` | string | `resolved`, `ambiguous`, `unresolved`, or `dynamic` |
| `diagnostic_code` | string \| null | Present for warning edges (`TW-01` through `TW-04`) |
| `line` | integer | Source line where the edge was discovered |

**Per-unresolved entry:**

| Field | Type | Description |
|---|---|---|
| `token` | string | Raw call token that could not be resolved |
| `caller` | string | Canonical name of proc containing the token |
| `line` | integer | Source line |
| `reason` | string | `dynamic-call-form`, `ambiguous-match`, `no-in-domain-match` |
| `diagnostic_code` | string | `TW-01`, `TW-02`, or `TW-03` |

#### 5.5.5 `trim_report.json` — what changed and why

This is the primary artifact for code review and domain-owner sign-off. It summarizes the entire trim result in a reviewable format.

**Top-level structure:**

| Field | Type | Description |
|---|---|---|
| `chopper_version` | string | Chopper version |
| `run_id` | string | Correlates with other artifacts |
| `mode` | string | `live` or `dry-run` |
| `summary` | object | High-level counts (see below) |
| `file_report` | object[] | Per-file summary with treatment and reason |
| `proc_report` | object[] | Per-proc summary with survival status |
| `validation_results` | object | Phase 1 and Phase 2 outcomes |
| `diagnostics` | object[] | All diagnostics emitted during this run |

**Summary fields:**

| Field | Type | Description |
|---|---|---|
| `total_domain_files` | integer | Files in domain before trim |
| `files_surviving` | integer | Files kept (FULL_COPY + PROC_TRIM + GENERATED) |
| `files_removed` | integer | Files with REMOVE treatment |
| `total_domain_procs` | integer | Procs in domain before trim |
| `procs_surviving` | integer | Procs kept in the trimmed output |
| `procs_removed` | integer | Procs deleted from PROC_TRIM files |
| `procs_traced` | integer | PI+ size (reporting only, not in surviving count) |
| `sloc_before` | integer | Logical source lines before trim (see §5.5.13 LOC counting) |
| `sloc_after` | integer | Logical source lines after trim |
| `sloc_removed` | integer | Logical source lines removed |
| `raw_lines_before` | integer | Total raw lines before trim (including comments and blanks) |
| `raw_lines_after` | integer | Total raw lines after trim |

**Per-diagnostic entry:**

| Field | Type | Description |
|---|---|---|
| `code` | string | Registry code (e.g., `VW-12`, `TW-03`) |
| `severity` | string | `error`, `warning`, or `info` |
| `message` | string | Human-readable message |
| `file` | string \| null | File context if applicable |
| `line` | integer \| null | Line number if applicable |
| `phase` | string | Pipeline phase that emitted it (e.g., `P1`, `P3`, `P4`, `P6`) |

#### 5.5.6 `trim_report.txt` — human-readable summary

This is a plain-text projection of `trim_report.json` designed for terminal display, email, and code-review comments. It must not contain facts absent from the JSON artifact.

**Sections:**

1. **Header:** run ID, domain, mode, timestamp, duration
2. **Input summary:** base JSON, features (ordered), project JSON (if used)
3. **File treatment summary:** table of files with treatment and reason
4. **Proc survival summary:** table of surviving procs with source file and selection source
5. **Trace summary:** PI+ size, PT size, unresolved count
6. **Diagnostics:** grouped by severity (errors first, then warnings, then info)
7. **Validation:** Phase 1 and Phase 2 pass/fail with details
8. **Footer:** exit code, "re-run with --dry-run for details" hint (on live trim), "no files were modified" note (on dry-run)

#### 5.5.7 `diagnostics.json` — full diagnostic log

All diagnostics emitted across all phases, with full context. This is the machine-readable equivalent of the diagnostics section in `trim_report.json`, but includes additional fields for tooling integration. The on-disk shape is fixed by `schemas/diagnostic-v1.schema.json`.

| Field | Type | Description |
|---|---|---|
| `chopper_version` | string | Chopper version |
| `run_id` | string | Correlates with other artifacts |
| `diagnostics` | object[] | Array of diagnostic entries |

Each diagnostic entry extends the `trim_report.json` diagnostic format with:

| Field | Type | Description |
|---|---|---|
| `slug` | string | Machine-readable slug (e.g., `pi-pe-same-file`) |
| `recovery_hint` | string | Suggested fix from the diagnostic registry |
| `related_inputs` | string[] | Which JSON inputs contributed to this diagnostic |

#### 5.5.8 `trim_stats.json` — numeric summary

Pure numbers for dashboards and trend tracking across multiple trim runs.

| Field | Type | Description |
|---|---|---|
| `chopper_version` | string | Chopper version |
| `run_id` | string | Correlates with other artifacts |
| `domain` | string | Domain identifier |
| `timestamp` | string | ISO 8601 UTC |
| `files_before` | integer | Total files in domain (see §5.5.13 authoring-artifact exclusions) |
| `files_after` | integer | Surviving files (same exclusions) |
| `procs_before` | integer | Total procs in domain |
| `procs_after` | integer | Surviving procs |
| `sloc_before` | integer | Logical source lines before trim (see §5.5.13) |
| `sloc_after` | integer | Logical source lines after trim |
| `sloc_removed` | integer | Logical source lines removed |
| `raw_lines_before` | integer | Total raw lines before trim |
| `raw_lines_after` | integer | Total raw lines after trim |
| `trim_ratio_files` | number | `files_after / files_before` |
| `trim_ratio_procs` | number | `procs_after / procs_before` |
| `trim_ratio_sloc` | number | `sloc_after / sloc_before` |

**Before-root selection.** The "before" tree is `<domain>_backup/` whenever it exists on disk at P7 audit time, otherwise `<domain>/`. The check uses the live filesystem (`ctx.fs.exists`), not the P0 `DomainState`: on a first live trim, P0 sees `backup_exists == False` but P5 creates the backup before P7 runs, so the audit must use the backup as the pristine "before". This mirrors the parser's `_source_root()` and `cli/loc_report._source_root()` so all three reporters agree on the baseline. On `--dry-run` no backup is taken; before-root collapses to `<domain>/` and the before/after numbers are equal (the trimmer never wrote).

#### 5.5.9 Input preservation contract

The `input_base.json`, `input_features/`, and `input_project.json` files are **exact byte-for-byte copies** of the JSON files used during the run. They are not normalized, re-serialized, or modified in any way. This ensures:

- The trim result can be reproduced by re-running Chopper with the saved inputs.
- Diff tools can compare saved inputs against current JSON files to detect authoring drift.
- Audit reviewers see exactly what the domain owner authored.

#### 5.5.10 Artifact emission rules

| Artifact | Live trim | Dry-run | `validate` | `cleanup` |
|---|---|---|---|---|
| `run_id` | ✓ | ✓ | ✓ | ✓ |
| `chopper_run.json` | ✓ | ✓ | ✓ | ✓ |
| `input_base.json` | ✓ | ✓ | ✓ | — |
| `input_features/` | ✓ | ✓ | ✓ | — |
| `input_project.json` | ✓ (if used) | ✓ (if used) | ✓ (if used) | — |
| `compiled_manifest.json` | ✓ | ✓ | — | — |
| `dependency_graph.json` | ✓ | ✓ | — | — |
| `diagnostics.json` | ✓ | ✓ | ✓ | — |
| `trim_report.json` | ✓ | ✓ | — | — |
| `trim_report.txt` | ✓ | ✓ | — | — |
| `files_removed.txt` | ✓ | ✓ | — | — |
| `files_kept.txt` | ✓ | ✓ | — | — |
| `p4_commands.txt` | ✓ | ✓ | — | — |
| `files_exclude_p4.txt` | ✓ | ✓ | — | — |
| `trim_stats.json` | ✓ | ✓ | — | — |
| `internal-error.log` | ✓ (exit 3 only) | ✓ (exit 3 only) | ✓ (exit 3 only) | ✓ (exit 3 only) |

**`internal-error.log` contract.** This file is written **only on exit code 3** (programmer error / internal-consistency failure). It is produced by the CLI's exit-3 handler rather than `AuditService`, because the audit stage itself may have failed. Contents:

- `run_id` (ISO-8601 UTC, matches the rest of the audit bundle)
- Timestamp of the crash
- Full Python traceback of the originating exception
- Snapshot of the `DiagnosticSink` at the moment of failure (all diagnostics emitted before the crash)
- Active `RunConfig` fields (paths and flags, no secrets)
- `python_version`, `chopper_version`, and platform string

The CLI also records the existence and path of this log in `RunResult.internal_error` (see `schemas/run-result-v1.schema.json`) so that GUI / CI consumers can surface the failure without reading the log directly. The log is plain text (not JSON) to remain readable even if the `core.serialization` layer itself is the source of the crash.

**Dry-run artifacts** are written to `.chopper/` in the domain root but no domain files are modified. This allows `diff` between dry-run and live-run artifacts.

**Overwrite policy:** each run overwrites the previous `.chopper/` contents. There is no history — the `.chopper/` directory represents only the most recent run. For history, use version control or external artifact storage.

#### 5.5.11 Determinism contract

All JSON artifacts must be serialized with:
- Keys sorted alphabetically at every nesting level
- 2-space indentation
- No trailing whitespace
- UTF-8 encoding, no BOM
- Trailing newline

This ensures that two runs with identical inputs produce byte-identical artifacts, enabling `diff` and `git diff` for regression detection.

#### 5.5.12 Correlation

All artifacts share `run_id` for cross-referencing. A reviewer can start from `trim_report.txt`, look up a specific file treatment in `compiled_manifest.json`, trace its dependencies in `dependency_graph.json`, and check which diagnostics were emitted in `diagnostics.json` — all correlated by `run_id`.

#### 5.5.13 LOC counting contract

All line-count fields labeled `sloc_*` report **logical source lines** — language-aware counts that exclude comments and blank lines. Raw line counts are reported separately as `raw_lines_*` for completeness.

**Counting rules by file language:**

| Language | Detection | Comment syntax | Blank line rule |
|---|---|---|---|
| **Tcl** | `.tcl` extension | Lines where the first non-whitespace token is `#` (full-line comments only; inline `#` after code counts as code) | Lines containing only whitespace |
| **Perl** | `.pl`, `.pm` extension | Lines where the first non-whitespace token is `#`; `=pod`..`=cut` block comments | Lines containing only whitespace |
| **Shell** | `.sh`, `.csh`, `.bash` extension | Lines where the first non-whitespace token is `#` (not `#!` shebang on line 1) | Lines containing only whitespace |
| **CSV** | `.csv` extension | No comment syntax; all non-blank lines are data lines | Lines containing only whitespace or only commas |
| **Other/unknown** | No recognized extension | **Fallback:** count all non-blank lines as SLOC | Lines containing only whitespace |

**Authoring artifacts excluded from all LOC accounting.** The following inputs are *authoring metadata*, not domain source code, and are skipped by every walk (`chopper loc`, `chopper trim` audit `trim_stats.json`, and the live console table). They never appear in `files_before` / `files_after` and contribute zero SLOC.

| Filter | What it excludes |
|---|---|
| Suffix `.json` (any case) | All `.json` files anywhere under the domain — Chopper's own base/feature/project inputs, the preserved `jsons/` subtree, and any user-authored JSON config. JSON is an authoring surface, not a runtime artifact. |
| Basename `instructions.md` (exact, case-sensitive) | Any file named `instructions.md` at any depth — the conventional domain-authoring README that ships alongside `jsons/`. Other `.md` files are still subject to the normal counted-types table. |

The exclusion is enforced centrally in `src/chopper/core/fs_walk.py` (`EXCLUDED_SUFFIXES`, `EXCLUDED_FILENAMES`) so every consumer — LOC report, audit before/after, live console — uses the same predicate.

**Rules:**

1. **Language detection is extension-based only.** No content sniffing. Unrecognized extensions use the fallback rule.
2. **Comment detection is line-level.** Chopper does not parse multi-line string literals or heredocs to distinguish "real comments" from comment characters inside strings. This is acceptable because the goal is a useful trim metric, not a research-grade SLOC tool.
3. **Backslash continuation lines** in Tcl are counted as separate source lines (consistent with parser line-counting).
4. **Shebang lines** (`#!/...` on line 1) count as source lines, not comments.
5. **SLOC is computed per file.** Domain totals are the sum of per-file SLOC values.
6. **Both metrics are always reported.** `sloc_*` for meaningful trim ratios; `raw_lines_*` for sanity-checking and auditors who want the unfiltered count.
7. **`trim_ratio_sloc`** is computed as `sloc_after / sloc_before`. This gives the most accurate picture of how much functional code was removed.

#### 5.5.14 `p4_commands.txt` — Perforce command list

A plain-UTF-8 text artifact that correlates each file-treatment decision to the Perforce command a reviewer must run to record the change against the depot. Chopper **never invokes `p4` itself to produce or act on this artifact** — the file is a ready-to-execute command list, not an automation surface. Operators inspect it, edit it if necessary, and then run `p4 submit` themselves. (The separate, opt-in `--p4` flag described in §5.5.18 does invoke `p4 edit`/`p4 revert` during the trim itself — a deliberate, narrowly-scoped exception; it never invokes `p4 add`, `p4 delete`, or `p4 submit`.)

**Sections.** The file contains up to three command sections, each prefixed by a `#`-comment section header, alphabetically sorted by POSIX path within the section, and separated from the next section by a blank line. The section order is fixed: edits, then adds, then deletes.

| Treatment in `manifest.file_decisions` | Emitted command | Notes |
|---|---|---|
| `PROC_TRIM` | `p4 edit -t text+x <path>` | Content of an existing depot file changes in place. |
| `GENERATED` where path exists in the pre-trim source root | `p4 edit -t text+x <path>` | Regenerate-in-place: the generator overwrites an existing depot file (e.g., `fev_fm_rtl2gate.tcl`-style stages). |
| `GENERATED` where path does **not** exist in the pre-trim source root | `p4 add -t text+x <path>` | Newly created stage file with no prior depot entry. |
| Physically removed (walk(source_root) − kept_set) | Listed in `exclude_file_list` section as `$ward`-relative path (or domain-relative when `$ward` is unavailable) | Same set as `files_removed.txt`. Use as P4 client-spec exclusion mapping lines. |
| `FULL_COPY` | *(no command)* | The rebuilt file is byte-identical to the depot copy; nothing to submit. |

The `-t text+x` filetype declares Perforce filetype `text` with the executable bit set, matching the cross-phase `ensure_executable()` contract (every rebuilt file in `<domain>/` carries `a+x`; see `core/file_perms.py`).

**`exclude_file_list` section (4.1.0+).** The former `p4 delete` command list is replaced by a bare path list for use as P4 client-spec exclusion mapping lines. When `$ward` is available and the domain root is under `$ward`, paths are `$ward`-relative (e.g. `global/snps/fev_formality/src/foo.tcl`). When `$ward` is not set, paths are domain-relative. Section header comments describe the path convention.

**Standalone `files_exclude_p4.txt` artifact (4.3.0+).** The `exclude_file_list` path set is also written as its own artifact, `files_exclude_p4.txt`, alongside `p4_commands.txt` — the identical sorted path list (same `$ward`-relative-or-domain-relative rule, same `_compute_excluded_paths(ctx, record)` computation backing both), without the `p4 edit`/`p4 add` sections. This lets tooling that only needs the exclusion list read one small, purpose-built file instead of parsing sections out of `p4_commands.txt`. Emission policy matches `p4_commands.txt` exactly: written on live trim and `--dry-run`; not by `validate`, `loc`, or `cleanup`. Empty-state emits the banner comments plus a `# (no files excluded)` marker line. See FR-51.

**Source-root resolution** mirrors `files_removed.txt`: `<domain>_backup/` after a live trim, `<domain>/` for a first-trim `--dry-run`. The same `_physical_source_root(ctx)` helper backs both artifacts so the `exclude_file_list` section is always coextensive with `files_removed.txt`. When neither root is readable (audit after a P0/P1 abort, unit-test stub filesystem), the writer falls back to a manifest-only view (explicit `REMOVE` decisions → exclude list, `GENERATED` decisions → `p4 add`).

**Determinism.** Each section is sorted lexicographically by POSIX path. Section order is fixed. Output uses LF line endings and ends with a trailing newline. Two runs with identical inputs produce byte-identical `p4_commands.txt`.

**Emission policy.** Written on both live trim and `--dry-run` (consistent with every other audit artifact). `validate`, `loc`, and `cleanup` do not produce it. Under `--dry-run` the commands are a preview — they reflect what *would* be submitted if the same JSON selection were run live — but no domain mutation has yet occurred, so `p4 submit` against a dry-run is premature.

**Empty-state.** When no section has any entries (e.g., aborted run with no manifest, or a no-op trim), the file still emits its banner comments plus a single `# (no Perforce commands — nothing to submit)` marker line, so the artifact is always present and well-formed.

#### 5.5.15 P4 Branch Analysis (stdout summary) — 4.1.0+

After every `trim`, `trim --dry-run`, `validate`, and `loc` run, Chopper prints a P4 branch analysis section to stdout. The classification is derived from `CompiledManifest.file_decisions`:

- **NO BRANCH NEEDED:** all surviving file treatments are `REMOVE` only. Pure P4 template deletions — a depot resync against an updated client spec is sufficient; no branch required.
- **BRANCH NEEDED:** at least one `PROC_TRIM` or `GENERATED` treatment exists — files will be modified or added in the depot, requiring a P4 branch.

**Single-domain output:**
```
=== P4 Branch Analysis ===
fev_formality: NO BRANCH NEEDED — only 14 removal(s); P4 template resync sufficient
```

**Multi-domain output (§5.1.2):**
```
=== P4 Branch Analysis ===
  snps/fev_formality             : NO BRANCH NEEDED — only 5 removal(s); P4 template resync sufficient
  cdns/fev_conformal             : BRANCH NEEDED (3 edit(s), 0 add(s))
  snps/power                     : BRANCH NEEDED (7 edit(s), 0 add(s))

Final verdict     : BRANCH NEEDED
Domains needing branch: cdns/fev_conformal, snps/power
```

See FR-48.

#### 5.5.16 Domain Run Header (stdout) — 4.2.0+

Before the pipeline starts for each domain, Chopper writes a scannable header block to **stdout** (all lines flushed immediately):

```
=== Domain: <domain_logical_name_or_leaf> ===
  Domain root      : <domain_root>
  Base JSON        : <base_path>               # base/features mode
  Base JSON        : <project_path>  (project) # project JSON mode
  config file found.. processing
  config file path : <project_config_path>     # only for §5.1.3 .project.features.config
  Features (N) :
    1. <name> : <feature_path>
    2. <name> : <feature_path>
```

**Line semantics:**

- `=== Domain: ... ===` — `domain_logical_name` when known (name-mode), otherwise `domain_root.name`.
- `Domain root` — resolved absolute path to the domain directory.
- `Base JSON` — `base_path` in base/features mode; `project_path + " (project)"` in project JSON mode; `"(none)"` when neither is set.
- `config file found.. processing` — emitted when `base_path` or `project_path` is non-null.
- `config file path` — emitted **only** when `RunConfig.project_config_path` is set, i.e. the auto-discovered `<leaf>.project.features.config` from §5.1.3. For project JSON inputs (explicit `--project` or auto-discovered `.project.json`), the path is already on the `Base JSON` line and is not repeated.
- `Features (N)` — emitted when one or more feature paths are active; each feature listed with a 1-based index, short name (stem minus `.feature` suffix), and resolved path.

The header is written before any stderr progress output. In multi-domain mode, one header block precedes each domain's pipeline. See FR-50.

#### 5.5.17 Audit Bundle Location Summary (stdout) — 4.3.0+

After `chopper trim` (live or `--dry-run`) finishes processing every domain in the run, Chopper prints the resolved `.chopper/` audit bundle path to **stdout**, immediately after the P4 Branch Analysis summary (§5.5.15). This tells the user exactly where to look for the run's diagnostics, manifests, and reports without them having to reconstruct `<domain_root>/.chopper` themselves — especially useful when `--domain` is a logical name resolved through `$ward` rather than a literal path the user typed.

**Single-domain output:**
```
The output logs and other files of this run can be found at: /ward/global/snps/fev_formality/.chopper

```

**Multi-domain output (§5.1.2).** `--domain` accepts a CSV list for sequential multi-domain trims, so each domain gets its own line rather than a single shared path:
```
=== Audit Bundle Locations ===
The output logs and other files of this run can be found at:
  snps/fev_formality             : /ward/global/snps/fev_formality/.chopper
  cdns/fev_conformal              : /ward/global/cdns/fev_conformal/.chopper

```

**Scope.** Emitted only by `chopper trim` (live and `--dry-run`); not by `validate`, `loc`, or `cleanup`. Domains that fail a pre-flight check (e.g. `VE-13` unresolvable `--project` paths) before a `ChopperContext` is built are excluded from the listing — there is no `.chopper/` path to report for a domain that never ran. Paths are printed via `Path.resolve()` so relative `--domain` inputs still print the real, absolute filesystem location. A trailing blank line separates this block from anything printed after it (e.g. the P4 Files Opened for Edit summary, §5.5.18). See FR-52.

#### 5.5.18 P4 Checkout-Before-Edit (`--p4`, opt-in) — P5, 4.4.0+

> This subsection documents a P5 **runtime mutation**, not an audit artifact — it lives here because of its tight coupling to the same file-treatment data that drives `p4_commands.txt` / `files_exclude_p4.txt` (§5.5.14). It is the one deliberate, narrowly-scoped exception to "Chopper never invokes `p4` itself": when a site's Perforce workflow requires `p4 edit` **before** a file's content changes on disk (the standard, default Perforce behavior — synced files are read-only until checked out), running Chopper's rebuild without checkout first can leave the depot's client-side bookkeeping out of sync with what actually landed on disk. `--p4` closes that gap. `p4 submit` remains a human's job; Chopper never runs it.

**CLI surface.** `--p4` is a `chopper trim`-only flag (`action="store_true"`, default `False`; not available on `validate`, `loc`, or `cleanup` — there is nothing to check out there). No JSON field exists for this; it is CLI-only by design, matching how ephemeral run-time behavior (like `--dry-run`) is expressed. Accepted but a strict no-op under `--dry-run`: dry-run never invokes `p4`, regardless of `--p4`.

**P4 checkout enabled notice (stdout).** Immediately after the domain run header (§5.5.16) and before the pipeline starts, Chopper prints a one-line notice when `--p4` was passed and the run is not a `--dry-run`:
```
  --p4 enabled: files will be checked out via 'p4 edit' before rewriting.
```
This is purely informational — it reflects that the flag was passed, not whether checkout will ultimately be attempted, skipped, or fail (those outcomes are reported separately once the pipeline finishes; see the detection/gating and failure-handling paragraphs below, and the "P4 Files Opened for Edit" summary at the end of this subsection). Suppressed under `--dry-run` (printing it there would imply checkout runs, when it never does). In multi-domain CSV `--domain` runs, this prints once per domain, right after that domain's own header, matching the per-domain header convention.

**Gating — first trim and re-trim, not a torn-down domain.** Checkout runs on `DomainState.case == 1` (domain exists, no `<domain>_backup/` yet) **and** `case == 2` (domain + backup both present — a re-trim). It is skipped only on `case == 3` (backup only, domain absent — there is no file on disk to open). The two supported cases use different preparation so `p4 edit` always sees depot-matching content:

- **Case 1:** `_p4_backup_phase` copies `domain/` to `domain_backup/` (not a rename) so the original, depot-synced files remain at their client-mapped paths. `p4 edit` runs against them, then `_p4_clear_phase` empties `domain/` for the normal per-file rebuild from the backup just created.
- **Case 2:** `domain/` already holds the *previous* trim's output, not depot content, which makes `p4 edit` fail silently (exit 0, no file opened) if attempted directly. `_p4_precopy_from_backup` first restores each `PROC_TRIM` / regenerate-in-place `GENERATED` file in `domain/` from `domain_backup/` (which still holds the last-synced depot revision), then checkout proceeds exactly as in Case 1. The subsequent Case 2 prep (delete domain, rebuild from backup) does not disturb Perforce's opened-for-edit bookkeeping, which is keyed by client path, not inode or file identity.

**Detection.** Two gates, deliberately simple (no per-file `p4 where` probe): (1) the `p4` binary must be resolvable on `PATH`; (2) `p4 info` must succeed (exit 0) when run with `cwd=domain_root`. If either gate fails, or gating above skips the case-3 scenario, or the Case 2 pre-copy step itself raises an OS error, Chopper prints a red, screen-visible notice to stderr (degrading to plain text under `--plain` or a non-terminal stream) explaining why, and the trim proceeds **normally** without any `p4` interaction — this is advisory only, never an error, never a non-zero exit.

**Subprocess paths are absolute.** `p4 edit` / `p4 revert` are invoked with the file's absolute path (not a path relative to `cwd=domain_root`) — some Perforce client/server combinations silently fail relative-path edits from a non-interactive subprocess (exit 0, empty stdout, `"file(s) not on client"` on stderr) even though the identical relative path succeeds from an interactive shell in the same workspace. `checkout_files` additionally treats an exit-0 response with empty stdout as a failure (P4's genuine `"opened for edit"` confirmation is never empty), so this silent-failure mode is caught rather than masked.

**Which files.** The exact `PROC_TRIM` + regenerate-in-place `GENERATED` file set (same semantic family as the `p4_commands.txt` edit section), resolved against `domain_root` (always intact or pre-copied to depot content by this point — see Gating above). Newly-created `GENERATED` files (no pre-trim counterpart) are excluded — they don't exist on disk yet, so there is nothing to check out; Chopper never runs `p4 add`. `p4 edit -t text+x <absolute-path>` is the only command issued.

**Failure handling — abort for all, asymmetric rollback cost:**

- **Checkout itself fails partway through the batch:** nothing has been renamed or rewritten yet, so rollback is just `p4 revert` on whatever succeeded before the failing file. The whole trim aborts (`VE-37`); `domain/` is left completely untouched.
- **A later P5 step fails after checkout already succeeded:** rollback additionally restores `domain/` from `domain_backup/` **immediately** — a deliberate, scoped deviation from NFR-09's default recovery timing (every other P5 failure defers recovery to the next invocation, which rebuilds cleanly from the intact backup). This immediate-restore path only fires when checkout actually opened at least one file; if zero files needed checkout (e.g. a `FULL_COPY`-only manifest), a later failure follows the existing default (deferred) recovery path unchanged.

**Diagnostics.** `VE-37 p4-checkout-failed` (phase 5, exit 1) is the only registered diagnostic for this feature — it fires exactly once, for the checkout-batch failure case, and is the sole path that changes the exit code. The "checkout skipped" notice (unavailable / Case 3 / pre-copy failure) is advisory CLI output only, with no diagnostic code and no effect on exit status — consistent with the existing `_warn_if_cwd_will_be_renamed` precedent elsewhere in the CLI layer.

**P4 Files Opened for Edit summary (stdout).** After a live trim with `--p4` successfully checks out at least one file, Chopper prints the absolute paths it opened for edit directly to stdout, immediately after the audit bundle location summary (§5.5.17):
```
=== P4 Files Opened for Edit ===
  /ward/global/snps/fev_formality/default_fm_procs.tcl
  /ward/global/snps/fev_formality/default_rules.fm.tcl
  /ward/global/snps/fev_formality/fev_fm_rtl2gate.tcl
```
This surfaces exactly the paths recorded in `P4CheckoutResult.checked_out` — no new `p4` subprocess call is made to produce it (Chopper does not invoke `p4 opened`); it simply reports data the checkout step already computed. No-op when `--p4` was not passed, checkout was skipped or failed, or under `--dry-run` (checkout never runs there). For multi-domain CSV `--domain` runs, each domain with checked-out files gets its own labeled block, matching the Audit Bundle Locations multi-domain convention.

See FR-53.


### 5.6 Output Expectations

Chopper output must be:
- Deterministic
- Reproducible from saved inputs
- Explainable through trace and trim reports
- Safe to review in code review

#### Determinism and write-safety

Determinism is a hard requirement (NFR-03): the same inputs must produce byte-identical output on every run. This is achieved through lex-sorted file discovery, lex-sorted BFS trace frontiers, stable JSON serialization, and a fixed phase sequence (no concurrency).

Write-safety does **not** use a staging tree or atomic promotion. Chopper writes directly to `<domain>/` during P5 and P5b; if a write fails mid-run, `<domain>_backup/` remains intact and the next invocation rebuilds from it (see §2.8 "Failure recovery"). Risks and recovery paths are tracked in [technical_docs/IMPLEMENTATION.md (pitfalls)](IMPLEMENTATION.md).

#### Preserved JSON inputs in the rebuilt domain

After P5 per-file dispatch succeeds and **only on a live (non-dry-run) trim**, the trimmer copies the entire `jsons/` directory from the backup into the rebuilt `<domain>/jsons/`. This makes the rebuilt domain unambiguous and self-contained: every JSON that existed in the original domain — selected or not — is present in the trimmed output without requiring the user to consult the backup.

Resolution rules:

1. **In-tree jsons/ directory** — the trimmer copies the whole `<domain>_backup/jsons/` subtree verbatim to `<domain>/jsons/`. Every file in that directory (base JSON, all feature JSONs — both selected and unselected — and any other JSON the original domain contained) is preserved at its original domain-relative path.
2. **Out-of-tree input** — for each selected JSON whose absolute path is anywhere outside the domain root (a wrapper script's shared config, a CI infrastructure path, or a project JSON authored alongside its repo), the trimmer additionally copies the file to `<domain>/jsons/_external/<NN>_<basename>` where `<NN>` is a two-digit zero-padded sequence number derived from `compiled_manifest.input_sources` ordering. The numeric prefix mirrors the audit-bundle convention under `.chopper/inputs/` and prevents name collisions when two external inputs share a basename.
3. **Project JSON** — when `--project` is used, the project JSON itself is preserved by the same in-tree / out-of-tree rule (it is part of `input_sources`).

Behavior contract:

- The in-tree copy is read from the backup tree (`<domain>_backup/jsons/...`) because P5 has already torn down the live domain by the time this step runs.
- I/O failures during the copy step emit `VW-20 audit-write-failed` (severity warning, exit code 0) and the run continues. The intent is identical to the audit-bundle write tolerance: the rebuilt domain is the primary deliverable; preservation is a convenience, not a hard guarantee.
- Dry-run skips this step entirely (consistent with §5.7 — no domain mutation under `--dry-run`).
- `<domain>/jsons/_external/` is regenerated fresh on every live run; previous runs' contents are not preserved across the rebuild (see §2.4 — the rebuilt domain mirrors the current run, not history).

### 5.7 Dry-Run vs Live Trim

Both modes execute the same eight-phase pipeline. The only difference is which phases write to disk.

| Phase | Live trim | `--dry-run` |
|---|---|---|
| P0 Detect trim state | Executes | Executes |
| P1 Read & validate inputs | Executes | Executes |
| P2 Parse domain Tcl | Executes | Executes |
| P3 Compile selections | Executes | Executes |
| P4 Trace dependencies | Executes | Executes |
| P5 Build output | **Writes directly to `<domain>/`** | **Skipped** |
| P6 Post-trim validate | Executes against the final rewritten/normalized `.tcl` files in `<domain>/` | Executes against the resolved sets only (manifest-derivable checks); filesystem re-read checks are skipped |
| P7 Finalize & audit | Writes `.chopper/` artifacts | Writes `.chopper/` artifacts (reports only; no domain writes) |

**Dry-run P6 scope.** Because no file is rewritten in dry-run, brace-balance and other filesystem-dependent checks (`VE-16`, `VE-26`, `VW-10`) cannot run. P6 under `--dry-run` runs only the manifest-derivable checks: `VW-05 dangling-proc-call`, `VW-06 source-file-removed`, `VW-14 step-file-missing`, `VW-15 step-proc-missing`, `VW-16 step-source-missing`, `VW-17 external-reference`. All other P6 behavior is unchanged.

Dry-run emits:
- `compiled_manifest.json` — file and proc treatment decisions
- `dependency_graph.json` — full call-tree edges (PI+ and TW-* diagnostics)
- `trim_report.json` + `trim_report.txt` — what would change and why
- Diagnostics log with all warnings/errors

**`chopper loc` (read-only LOC report).** A third execution mode runs the same P0–P4 + dry-run-P6 pipeline as `chopper trim --dry-run`, then **replays the real P5 trim phases against an in-memory copy of the source tree** (`cli/loc_report.build_loc_report` → `orchestrator/simulate.simulate_trim_in_memory`) and counts the *actual* rebuilt output. The replay seeds an `InMemoryFS` from the source root and runs the production `TrimmerService` (P5a), `GeneratorService` (P5b), `TclIndentationService` (P5c), and `CompanionSyncService` (P5d) with `dry_run=False` — the same services a live trim uses — so the before/after numbers are byte-for-byte identical to `chopper trim`. Unlike both live and dry-run trim, `chopper loc` writes **nothing to the real filesystem** — no domain modifications and **no `.chopper/` audit bundle**. The runner suppresses P7 audit when `command == "loc"`. Counts use the existing `audit/sloc.py` for SLOC and `len(text.splitlines())` for physical lines, read from the in-memory tree. Per-treatment accounting:

| Treatment | After count (read from the in-memory rebuilt domain) |
|---|---|
| `FULL_COPY` | The rebuilt file. Normally verbatim, but P5d companion-sync may shrink it (e.g. a `.csv`/`.tcl` companion pruned to match the surviving proc set), so the after-count is the actual on-disk size, not an assumption of "unchanged". |
| `PROC_TRIM` | The actual proc-dropped file produced by `ProcDropper` (P5a). |
| `REMOVE` | 0 (the file is never copied into the rebuilt domain). |
| `GENERATED` | The artifact written by `GeneratorService` (P5b), after the optional P5c indentation pass. |

Files present in the source domain but absent from `manifest.file_decisions` are treated as REMOVE for the after totals (default-exclude under R2). The output table reports files-before, files-after, lines-before, lines-after, SLOC-before, SLOC-after, and the percentage reduction for each. Diagnostics emitted along the P0–P4 path are still summarized to stderr; exit-code policy matches `validate` (0/1/2/3).

**Counted file types.** The source-domain walk in `cli/loc_report.py` accepts a closed extension allow-list mirrored from the SLOC counter language table. Files whose extension is **not** in this list are silently skipped — they neither contribute to "before" totals nor count as REMOVE candidates:

| Counted? | Extensions | Notes |
|---|---|---|
| Yes | `.tcl`, `.py`, `.pl`, `.pm`, `.sh`, `.bash`, `.csh`, `.tcsh`, `.zsh`, `.ksh` | Hash-comment family: SLOC excludes blank lines and full-`#`-leading lines; shell-family `#!` shebang on line 1 counts as SLOC. |
| Yes | `.csv` | A line counts only if it contains at least one non-comma, non-whitespace token. |
| No | `.json` (any path) | Authoring/metadata surface; see §5.5.13 "Authoring artifacts excluded". Never counted in any phase. |
| No | Basename `instructions.md` (any path) | Authoring README; see §5.5.13. Other `.md` files are not in the counted list anyway. |
| No | Everything else (`.v`, `.sv`, `.vhd`, `.lib`, `.def`, `.spef`, `.md`, `.txt`, binaries, etc.) | Skipped by the enumerator; never appears in any treatment bucket. |

Generated artifacts are language-detected the same way (by artifact path suffix). A generated `<stage>.tcl` follows hash-comment SLOC rules. A hypothetical generated `.json` would be excluded by the authoring-artifact filter and would not appear in any LOC bucket.

**Source-root resolution and `_backup` interaction.** `cli/loc_report._source_root(ctx)` mirrors the parser: it returns `ctx.config.backup_root` when that path exists on disk, and `ctx.config.domain_root` otherwise. Consequence: on a re-run after `chopper trim` has already produced `<domain>_backup/`, `chopper loc` enumerates the **backup** (the original pre-trim source), so "before" reflects what the parser actually sees — not the already-trimmed output. This matches the dry-run pipeline by construction.

**Accounting caveats users must know:**

1. **PROC_TRIM is the real trimmed output.** Because `loc` replays the real `ProcDropper` against an in-memory copy, the "after" count for a `PROC_TRIM` file is the *actual* trimmed file the live run would write — not a reconstruction from `ProcEntry` spans. It matches `chopper trim` exactly.
2. **P5c indentation and P5d companion-sync are modeled.** The in-memory replay runs the optional P5c whitespace-only indentation pass (when `base.options.indent: true`) and the P5d companion-file sync, exactly as live trim does. Consequence: a `FULL_COPY` file whose companion is pruned, or a file reindented by P5c, shows its real after-size — `loc` will not over-report it as "unchanged".
3. **Default-exclude.** A file under `<domain>/` whose extension is in the counted list but which the merged manifest never names is counted as REMOVE for the "after" totals — it is conceptually absent from the trimmed domain.
4. **Decode fallback.** Files that fail UTF-8 decode are retried as latin-1; both failures cause the file to be silently dropped from the report (it appears in neither "before" nor "after"). This is rare in practice for Tcl/JSON/CSV inputs.
5. **`.chopper/` is excluded.** The enumerator never descends into `.chopper/` even if a previous run left one behind.
6. **Byte-identical to a live trim.** Because `loc` reuses the production P5 services (just against an in-memory filesystem), its before/after totals are byte-for-byte identical to what `chopper trim` would produce and to the audit bundle's `trim_stats.json`. It is a real (in-memory) trim, not a separate projection that could drift.

**Corner-case worked examples:**

- *A `.tcl` file with one proc kept and one proc dropped —* before-lines = entire file; after-lines = the file `ProcDropper` actually produces (body + DPA + leading comment of the dropped proc removed). Treatment is `PROC_TRIM`.
- *A `.tcl` file with all procs dropped —* the compiler downgrades the file to whole-file removal *before* `loc` sees it; the file shows up under `treatment.REMOVE.*` with `after = 0`, not under `PROC_TRIM`.
- *A `.v` Verilog file or a `.lib` Liberty file in the domain —* not in the counted-extensions allow-list, so it does not appear in `files.before` and is invisible to the report regardless of what the manifest says about it.
- *A generated `<stage>.tcl` that doesn't exist as a source file —* contributes `0` to before-lines and `before-lines = 0, after-lines = rebuilt-artifact-line-count` to `treatment.GENERATED.*`.
- *A re-run with `<domain>_backup/` already present —* `loc` seeds the in-memory replay from the backup (the original pre-trim source), not the live (already-trimmed) `<domain>/`. The percent reduction is therefore stable whether the trim has been applied or not.

### 5.8 Validation Model

Chopper has two validation phases that run within the pipeline:

| Phase | When | Service | Input | What it checks |
|---|---|---|---|---|
| **Phase 1** (within P1) | Pre-trim | `validate_pre(ctx, loaded)` | `LoadedConfig` + manifest draft | Schema, missing files/procs, empty procs arrays, invalid actions, path rules, `@n` targeting, depends-on resolution, no-op-exclude detection (`VE-27`) |
| **Phase 2** (within P6) | Post-trim | `validate_post(ctx, manifest, graph, rewritten_paths, trim_report=None)` | `CompiledManifest` + `DependencyGraph` + sequence of final `.tcl` paths rewritten or indentation-normalized during P5 + optional live `TrimReport` | Re-tokenizes only the files listed in `rewritten_paths` to check brace balance (`VE-16` — internal-consistency assertion, exit 3); when a live `TrimReport` is present, first reconciles `CompiledManifest` vs `TrimReport` path/treatment/proc-set expectations, then verifies rebuilt-domain filesystem reality (removed files absent; surviving outputs present, file-typed, and byte-count aligned), then re-parses each rewritten `PROC_TRIM` file to confirm its surviving canonical proc set matches the expected set (`VW-10`); reads the P4 dependency graph to find surviving procs whose resolved calls or `source`/`iproc_source` edges point into trimmed-away targets (`VW-05`, `VW-06`); classifies F3 step tokens against the manifest for cross-validate (`VW-14`–`VW-17`) |

Phase 2 input contract: `rewritten_paths` contains every emitted `.tcl` path whose final contents were produced or modified by P5 (`PROC_TRIM` outputs and `GENERATED` stage `.tcl` artifacts). `FULL_COPY` outputs (Tcl and non-Tcl alike) are byte-for-byte copies of the source and are **not** re-tokenized: P5c never touches them, so there is nothing for P6 to re-check. When `trim_report` is supplied on the live path, P6 uses `CompiledManifest` as the dry-run-equivalent expectation source and enforces live conformance via `VW-10`; size reconciliation uses logical UTF-8 text bytes for normalized `.tcl` outcomes so Windows CRLF persistence does not false-positive, while `FULL_COPY` outputs use raw metadata size. Only `PROC_TRIM` files participate in the re-parse proc-set reconciliation step.

**Cross-validate contract (`options.cross_validate`).** The F3 cross-validate checks (`VW-14`/`VW-15`/`VW-16`) are part of P6 (`validate_post`) and derive their answers from `CompiledManifest` — never from a filesystem re-scan. For each step string in every surviving stage, the validator classifies the token by syntax:

- **File-path literal** ending in `.tcl`/`.pl`/`.py`/`.csh` → look up `manifest.file_decisions`; emit `VW-14 step-file-missing` on miss.
- **Bare proc token** (no path separator, no extension) → look up `manifest.proc_decisions`; emit `VW-15 step-proc-missing` on miss.
- **`source <path>` / `iproc_source <path>` command** → look up `manifest.file_decisions`; emit `VW-16 step-source-missing` on miss.

Because the check is manifest-derivable, it runs **identically in dry-run and live modes**. When `options.cross_validate` is `false`, `VW-14`/`VW-15`/`VW-16` are suppressed entirely. The flag defaults to `true` because silently emitting a run-file that calls into trimmed-away content is a high-cost authoring failure.

**Performance note.** Cross-validate is O(stages × steps × manifest-size) in the worst case and adds measurable runtime on domains with large `flow_actions` surfaces. Authors who are confident in their selection (or who are iterating quickly on feature JSONs) may disable it with `"options": { "cross_validate": false }`. For any run that will be committed or handed off, cross-validate **must** be enabled — it is the only check that catches stage references to files or procs that the F1/F2 merge removed. `VW-17 external-reference` (advisory) is emitted regardless of `cross_validate` because it does not depend on manifest lookups.

**Diagnostic authority.** All severities, exit codes, recovery hints, and phase assignments for `VE-16`, `VW-05`, `VW-06`, `VW-08`, `VW-14`..`VW-17` are defined in [`technical_docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md). This section names codes only; it does not restate their metadata.

**`chopper validate` standalone command.**

- **Default behavior (JSON-only):** When invoked without access to the domain source tree, `chopper validate` runs Phase 1 structural checks only — schema validation, path rules, empty-procs detection, depends-on resolution, and every other check that does not require reading `.tcl` files. Filesystem-existence checks (`VE-06`, `VE-07`, `VW-25`) and parser-time checks (`PE-*`) are **skipped** in this mode.
- **Full mode (with domain):** When invoked from inside the domain directory (so that `domain_root.name.casefold() == project.domain.casefold()` per §5.1) or with an explicit `--domain` argument, `chopper validate` additionally runs the parser (`PE-*`) and the filesystem-existence checks (`VE-06`, `VE-07`, `VW-25`). This is the pre-flight mode used before `chopper trim`.

The detailed validation check matrix, diagnostics contract, and exit semantics are defined in [technical_docs/DIAGNOSTIC_CODES.md](DIAGNOSTIC_CODES.md).

### 5.9 CLI Contract, Diagnostics, and Exit Semantics

Chopper exposes the `validate`, `trim`, `loc`, and `cleanup` subcommands as first-class user interfaces.

Chopper supports three input modes: base-only (`--base`), base-plus-features (`--base --features`), and project JSON (`--project`). Project JSON mode packages the same selection decisions into a single auditable file without changing trim semantics. `--project` is mutually exclusive with `--base`/`--features`.

The complete CLI reference — including all subcommands, arguments, flags, per-mode examples, and the project JSON workflow — is defined in [technical_docs/CLI_REFERENCE.md](CLI_REFERENCE.md).

Detailed CLI behavior, diagnostics fields, exit codes, presentation constraints, and usability requirements are defined in [technical_docs/CLI_REFERENCE.md](CLI_REFERENCE.md) and [technical_docs/DIAGNOSTIC_CODES.md](DIAGNOSTIC_CODES.md).

### 5.10 Python Implementation Guidance

Chopper's Python coding standards live in §5.12 below. GUI-readiness and the wire protocol live in §5.11. [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md) provides a short summary that points back to these sections; the architecture doc is authoritative.

### 5.11 GUI Readiness and Wire Protocol

Chopper is CLI-only. However, the architecture **must** enable a future GUI without rewriting the engine. This section defines the provisions that the current implementation must satisfy so that GUI-based file selection, proc selection, trim statistics, JSON viewing, dependency-graph visualization, and diagnostic browsing can be layered on top later.

#### 5.11.1 Architectural Requirements for GUI Enablement

The following rules are **non-negotiable** even though no GUI ships:

1. **Typed pipeline results.** The runner returns a frozen `RunResult`; individual phases exchange frozen dataclasses such as `ParseResult`, `CompiledManifest`, `DependencyGraph`, and `TrimReport`. No phase returns pre-rendered strings.
2. **Structured progress events.** Progress flows through `ProgressSink` with explicit phase and step notifications. The on-disk event shape is fixed by `schemas/progress-event-v1.schema.json`. The CLI renders them today; a GUI can render the same events later.
3. **Structured diagnostics.** Every diagnostic is a `Diagnostic` record with severity, code, message, location, and hint. No ad-hoc `print()` or unstructured error messages in library code.
4. **Deterministic serialization.** Core models are serializable through `dump_model()` in `src/chopper/core/serialization.py`, which is already the source for audit artifacts. A future GUI can consume the same shapes without changing the engine.
5. **No presentation in core logic.** The compiler, parser, trimmer, validator, and audit writer never import terminal-rendering libraries or format user-facing output.
6. **CLI rendering stays thin.** Human output lives in `cli/render.py`; engine code stays presentation-agnostic.
7. **Machine output is deferred, not promised.** Chopper does not freeze a `--json` CLI mode or a GUI wire protocol here. If structured stdout/stderr is needed later, it enters through `FD-10` in [`IMPLEMENTATION.md`](IMPLEMENTATION.md) Future Considerations section, not via an undocumented side channel.

#### 5.11.2 Service Layer Contract

The engine boundary between presentation (CLI today, GUI later) and domain logic is defined in [`technical_docs/ENGINEERING.md`](ENGINEERING.md) §6 (`ChopperContext`, `RunConfig`, `PresentationConfig`, `ChopperRunner.run()`) and §9.2 (per-phase signatures: `DomainStateService`, `ConfigService`, `validate_pre`, `ParserService`, `CompilerService`, `TracerService`, `TrimmerService`, `GeneratorService`, `validate_post`, `AuditService`).

**Invocation pattern (CLI today, future GUI later):**

1. The frontend parses its inputs into `RunConfig` (engine behavior) plus `PresentationConfig` (UX behavior).
2. The frontend constructs `ChopperContext` by binding concrete ports: filesystem, diagnostic sink, and progress sink.
3. The frontend calls `ChopperRunner().run(ctx) -> RunResult`.
4. The frontend renders `RunResult` and the collected diagnostics using its own presentation layer and exits with `RunResult.exit_code`.

**Rules:**

- Services accept `ctx` plus typed inputs they declare; never print to stdout/stderr directly.
- Services surface outcomes through `ctx.diag.emit(...)` and `ctx.progress.*`; never raise for user-visible conditions.
- A future GUI does **not** require new engine services; it binds the same context shape and consumes the same typed results and audit artifacts as the CLI.
- `cleanup` is the one exception to the runner pattern: it is a standalone CLI action that deletes `<domain>_backup/` and does not enter the eight-phase pipeline.

#### 5.11.3 Future GUI Integration Surface

The current design freezes the **data surface**, not a transport protocol. The future GUI can be added in one of two ways:

1. **In-process Python integration** using `ChopperRunner.run(ctx)` plus the same ports the CLI binds today.
2. **Structured CLI transport** added later through `FD-10` in [`IMPLEMENTATION.md`](IMPLEMENTATION.md) Future Considerations section, once the pipeline and artifact shapes have proven stable.

What is already stable is the engine-facing surface:

- `RunConfig` and `PresentationConfig`
- `ChopperContext`
- `RunResult`
- `Diagnostic` records via `ctx.diag`
- Audit artifacts emitted under `.chopper/`

#### 5.11.4 Serialization Contract

Every frozen dataclass in the core models must be JSON-serializable through `dump_model()` in `src/chopper/core/serialization.py`.

Contract:

- Paths serialize as POSIX strings.
- Enums serialize as `.value`.
- Mapping keys are recursively sorted for deterministic output.
- List order is preserved exactly.
- `None` values serialize as JSON `null`.

Audit artifacts use this contract today. A future GUI or machine-readable frontend consumes the same shapes rather than inventing a second schema.

#### 5.11.5 GUI-Relevant Data Surfaces

The following data is already produced by the current pipeline and available as typed, serializable models. A future GUI would consume these directly:

| GUI Feature | Data Source | Current Artifact |
|---|---|---|
| **File selection browser** | `CompiledManifest.files` — per-file treatment, reason, input sources | `compiled_manifest.json` |
| **Proc selection browser** | `CompiledManifest.procs` — per-proc decision, source file, keep reason | `compiled_manifest.json` |
| **Dependency graph viewer** | Call-tree edges, PI+, unresolved tokens | `dependency_graph.json` |
| **Trim statistics dashboard** | `RunResult.trim_stats` — files/procs/SLOC before/after, trim ratios | `trim_stats.json` |
| **JSON viewer / editor** | Base, feature, and project JSON schemas + validation diagnostics | `input_base.json`, `input_features/`, `input_project.json` |
| **Diagnostic browser** | `Diagnostic` records with severity, code, location, hint, phase | `diagnostics.json` |
| **Stage/flow viewer** | `CompiledManifest.flow_stages` — resolved stage sequence after flow actions | `compiled_manifest.json` |
| **Audit trail viewer** | `chopper_run.json` — run metadata, timestamps, exit code | `chopper_run.json` |

**No additional artifacts or data models are needed for GUI enablement.** The current pipeline already produces everything a GUI would need. The only future work is the presentation layer itself.

#### 5.11.6 Extension Points for a Future Frontend

The extension surface is deliberately small:

| Extension Point | Contract | Purpose |
|---|---|---|
| `FileSystemPort` | `read_text`, `write_text`, `copy_file`, `exists`, `rename`, `remove`, `mkdir`, `copy_tree`, ... | Lets tests and future frontends drive the engine without assuming a real on-disk tree in every scenario, while keeping Tcl text operations separate from opaque full-file copies |
| `ProgressSink` | `phase_started()`, `phase_done()`, `step()` | Progress panels, spinners, CI silence, or future GUI status widgets |
| `DiagnosticSink` | `emit()`, `snapshot()`, `finalize()` | Diagnostic collection and presentation-independent reporting |

Rendering itself is **not** a protocol here. The CLI renders directly in `cli/render.py`; a future GUI will render from typed data without requiring a `TableRenderer` abstraction.

#### 5.11.7 Companion-Assisted Bug Filing

The repository-scoped Chopper Agent and its prompt library are presentation-layer workflows that sit **above** the engine. They may automate bug-report preparation and issue filing without changing the eight-phase runtime or the audit-artifact contract.

Supported workflow:

1. Accept local evidence paths such as `<domain>/.chopper/`, terminal logs, markdown notes, screenshots, and minimal JSON reproductions.
2. Package those local paths into a single zip bundle for operator convenience.
3. Read the audit bundle when present and extract the concrete facts needed for a bug report (version, failing phase, exit code, top diagnostics, relevant JSON inputs).
4. Render a bug-report body that matches the GitHub issue template fields.
5. If the host environment exposes an authenticated GitHub issue-creation transport (for example `gh issue create`), create the GitHub issue automatically and return the created issue URL.
6. If the issue-creation transport is missing or fails, fall back in the same run to the simple local behavior: keep the rendered issue body and any local evidence bundle, and return those paths to the operator.

Non-goals and limits:

- This workflow is **presentation-only**. It does not change `ChopperRunner`, the CLI subcommands, audit artifacts, diagnostics, or schema files.
- The generated zip bundle is a convenience artifact for the operator. It is not a new Chopper runtime artifact and is not written under `.chopper/`.
- Binary attachment upload to GitHub issues is **not part of the v1 contract**. The companion may prepare the bundle and file the issue body automatically, but the final attachment upload remains a host-UI operation unless a future architecture revision explicitly standardizes an attachment transport.
- The companion must not simulate attachments by committing audit bundles into the repository or pushing them to ad-hoc external storage.

#### 5.11.8 What v1 Must NOT Do

- Must NOT embed terminal-specific formatting (ANSI codes, Rich markup) in any module outside `src/chopper/cli/`.
- Must NOT return pre-formatted strings from runner or phase functions.
- Must NOT use `print()` in library code (`src/chopper/compiler/`, `src/chopper/parser/`, `src/chopper/trimmer/`, `src/chopper/validator/`, `src/chopper/core/`).
- Must NOT require a TTY for correct operation — headless and piped invocations must work.
- Must NOT couple diagnostic emission to console rendering — diagnostics are data, not output.

### 5.12 Python Coding Standards

Chopper is a Python ≥ 3.13 CLI. The rules below are authoritative for every file under `src/chopper/`. They consolidate what was previously scattered between the instructions file and the architecture plan; the instructions file now carries a brief summary that defers here.

> **Python version policy.** The runtime floor is **Python 3.13**. The `pyproject.toml` `requires-python = ">=3.13"` pin and the `mypy`/`ruff` `python_version`/`target-version` targets are all aligned to 3.13. PEP 695 type-parameter syntax and other 3.13-only features are permitted in `src/`. If a future release needs to raise the floor further it does so explicitly through an FD entry, not by accident.

#### 5.12.1 Module Layout and Boundaries

- The repository layout is defined in [`technical_docs/ENGINEERING.md`](ENGINEERING.md) §3. Every source module lives under `src/chopper/`. No sibling-module imports across service packages — services depend only on `core/` and their own submodules. Cross-cutting data lives in phase-owned `core/models_*.py` modules that callers import directly; cross-cutting protocols live in `core/protocols.py`.
- Ports-and-adapters: the only engine ports are `FileSystemPort`, `DiagnosticSink`, and `ProgressSink` in `core/protocols.py`. Concrete adapters live in `adapters/`. Services receive them via `ChopperContext`. Clock access, serialization, audit writing, and rendering are direct helpers or CLI-local concerns, not additional ports.
- Services never construct adapters; the CLI does that at startup (see [`technical_docs/ENGINEERING.md`](ENGINEERING.md) §6.1).

#### 5.12.2 Path Handling

- **Always** use `pathlib.Path`. Never use `os.path` string manipulation.
- Always normalize to forward slashes on serialization (POSIX form). On Windows, `Path.as_posix()` is used before any path enters JSON output.
- Path comparisons that cross OS boundaries (e.g., project JSON `domain` field matched against cwd basename) use `casefold()` (§5.1). Every other path comparison is case-sensitive.
- Forbidden in user input: `..` traversal, absolute paths, drive letters. Validated at the schema boundary (§6.3.1).
- `Path.resolve()` is used once at CLI entry to normalize the domain root; downstream services use the resolved absolute path.

#### 5.12.3 Type Annotations

- Every public function and method has full type annotations.
- Every core model class is a frozen `@dataclass(frozen=True)`, whether defined in `core/models_parser.py`, `core/models_config.py`, `core/models_compiler.py`, `core/models_trimmer.py`, `core/models_audit.py`, or `core/models_common.py`. Immutability is a hard rule — services cannot mutate each other's outputs. There is no aggregate model re-export module; import from the phase-owned module that defines the class.
- Enums use `enum.Enum` (string-valued for JSON serializability) or `enum.IntEnum` where numeric comparison is meaningful (e.g., `Phase`).
- `typing.Protocol` (PEP 544) is preferred over `abc.ABC` for ports. Duck typing with static verification.
- `from __future__ import annotations` at the top of every module; forward references resolved lazily.
- `mypy` in strict mode for `core/`; non-strict (but no-`Any`) for the rest.

#### 5.12.4 Logging and Diagnostics

- **No `print()` in library code.** Any module under `src/chopper/{parser,compiler,trimmer,validator,core,config,audit,generators}` that calls `print()` is a review-blocking defect. The CLI and test harnesses may print.
- All user-facing outcomes go through `ctx.diag.emit(Diagnostic(...))` (§5.11.1). Every code is registered in [`technical_docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md).
- **Every diagnostic that is attributable to a specific source file MUST carry a non-null `path` field.** This is a serialisation invariant: `.chopper/diagnostics.json` and `.chopper/trim_report.json` may not contain `"file": null` for any diagnostic whose root cause is locatable in a `.tcl` source file. P4 trace diagnostics (`TW-01`, `TW-02`, `TW-03`, `TW-04`, `TI-01`) pass `caller.source_file`. P6 cross-validation diagnostics (`VW-05`, `VW-06`) recover the source path from the caller canonical name `<file>::<qname>` via the `_path_from_canonical` helper. See `technical_docs/IMPLEMENTATION.md` (pitfalls) Pitfall P-41 and bug report `diagnostics_file_null_for_p4_p6.md` for the production incident this invariant addresses.
- **There is no internal structured-logging channel.** Chopper has exactly two output surfaces for the operator: the `DiagnosticSink` (user-facing outcomes) and the `ProgressSink` (phase transitions and progress events). Library modules do not carry a logger handle and do not emit `log.info` / `log.debug` events. Every observation worth surfacing to a user is a diagnostic; every observation worth surfacing to downstream tooling is an audit artifact. Crash traces for programmer errors are written to `.chopper/internal-error.log` by the runner's final `except` block (§8.3, exit code 3).

#### 5.12.5 Errors and Exceptions

- User-visible conditions are **diagnostics**, not exceptions. Services never raise `ValueError` / `FileNotFoundError` to signal bad input.
- `ChopperError` (in `core/errors.py`) is the base for programmer-error exceptions. Subclasses: `UnknownDiagnosticCodeError` (registry mismatch at `Diagnostic` construction), `ProgrammerError` (internal-consistency assertions).
- An unhandled exception that escapes a service is an exit-code-3 programmer error; the runner catches it in `finally` (see [`technical_docs/ENGINEERING.md`](ENGINEERING.md) §6.2), writes a stack trace to `.chopper/internal-error.log`, and exits 3. `--debug` additionally re-raises so the trace hits stderr.

#### 5.12.6 Style and Formatting

- Ruff is the only linter + formatter (replaces flake8, isort, black).
- Line length: 120.
- `snake_case` for functions and variables, `CamelCase` for classes, `UPPER_CASE` for constants.
- 4-space indentation. No tabs.
- Imports grouped: stdlib, third-party, first-party (`chopper.*`), relative. Ruff enforces.
- Docstrings: Google style, required on every public function / class / method. Omitted on private helpers unless non-obvious.

#### 5.12.7 Configuration Policy

- No configuration files under the user's home directory, no `$CHOPPER_*` environment variables (except for CI overrides documented explicitly). All configuration enters via CLI flags, base/feature/project JSONs, and `.chopper/` audit artifacts.
- `RunConfig` ([`technical_docs/ENGINEERING.md`](ENGINEERING.md) §6.1) is the single source of engine-behavior configuration; `PresentationConfig` is the single source of CLI-UX configuration. Neither is mutable after construction.

#### 5.12.8 Testing Standards

Coverage gates, fixture conventions, and the integration-test harness are defined in [`tests/TESTING_STRATEGY.md`](../tests/TESTING_STRATEGY.md). Parser fixture catalog is in [`tests/FIXTURE_CATALOG.md`](../tests/FIXTURE_CATALOG.md). The full suite (`make ci`) is held at 100% line + branch coverage across every module; the fast unit-only gate (`make check`) holds ≥ 99.8% line.

#### 5.12.9 Permitted Cross-Phase Exception: Validator Imports Parser (VW-10 Proc-Set Reconciliation)

**Single permitted import across phase boundaries:**

```python
# In src/chopper/validator/functions.py
from chopper.parser.service import parse_file
```

This import is **explicitly permitted** and is **not** an architecture violation. It exists because post-trim validation (`validate_post`, Phase P6) must verify that trimmed output files contain exactly the proc set that the trim operation promised to keep. This is the `VW-10` check.

**Why this is cleaner than alternatives:**

1. **Direct, deterministic.** The validator re-parses the actual trimmed file and compares the canonical proc names discovered to the `TrimReport.procs_kept` set. No guessing, no heuristics, no reconstructed state.
2. **Catches real bugs.** If the trimmer has a bug that drops a proc it should have kept, or keeps a proc it should have dropped, `VW-10` catches it immediately and emits a clear mismatch report.
3. **Single source of truth.** Both validator and compiler use the same `parse_file()` function, so they agree on what constitutes a valid proc definition.
4. **Better than alternatives:**
   - Storing a pre-trim proc index in the manifest would require synchronization with post-trim state (error-prone).
   - Walking the AST of `TrimReport` to reconstruct proc names would reinvent the parser (maintenance burden).
   - Skipping the check would leave silent corruption (unacceptable).
5. **No bidirectional coupling.** The parser does not import anything from validator; only validator imports parser. Parser remains a lower-level service that does not know it is being called by a cross-phase checker.

**Scope:** This exception applies **only** to `src/chopper/validator/functions.py` importing `src/chopper/parser/service.parse_file`. No other cross-phase imports are permitted. Parser, compiler, and trimmer remain layered services that do not import each other.

**Testing:** The `VW-10` proc-set reconciliation is tested in `tests/unit/validator/test_validator.py` under the `validate_post_emits_vw10_*` test family. Integration tests validate end-to-end trim correctness under `tests/integration/test_cli_e2e.py`.

---

## 6. JSON Design Principles and Schema Model

### 6.1 Design Principle: No Data-as-Keys

Chopper must not replicate FlowBuilder's dynamic-key model.

**Rule:** top-level keys and nested structural keys are statically known.

### 6.2 Design Principle: Arrays of Objects, Not Objects-as-Maps

**Instead of:**
```json
"procedures": {
    "include": {
        "flow_procs.tcl": ["proc_a", "proc_b"]
    }
}
```

**Use:**
```json
"procedures": {
    "include": [
        { "file": "flow_procs.tcl", "procs": ["proc_a", "proc_b"] }
    ]
}
```

### 6.3 Design Principle: Schema Versioning

Every Chopper JSON carries a schema version.

```json
{ "$schema": "base-v1", ... }
```

### 6.3.1 Path and Glob Semantics

**Paths in JSON are domain-relative and use forward slashes.** All paths resolve relative to the current working directory (domain root) where Chopper is invoked.

**Path rules:**
- Always use forward slashes: `procs/core_procs.tcl` (not `procs\core_procs.tcl`)
- Never use `..` traversal: `../../other_domain/file.tcl` is rejected
- Never use absolute paths: `/home/user/file.tcl` is rejected
- Never use double slashes: `procs//core.tcl` is rejected

**Glob patterns in `files.include` and `files.exclude`:**

Glob patterns support three special characters to match multiple files:

| Pattern | Matches | Scope |
|---------|---------|-------|
| `*` | Any number of characters | Single directory level (does not cross `/` boundaries) |
| `?` | Exactly one character | Single directory level (does not cross `/` boundaries) |
| `**` | Any number of directories and subdirectories | Multiple levels and nested directories |

**Examples:**

| Pattern | Matches | Does NOT match |
|---------|---------|----------------|
| `procs/*.tcl` | `procs/core_procs.tcl`, `procs/rules.tcl` | `procs/sub/file.tcl` (in subdirectory) |
| `procs/??.tcl` | `procs/ab.tcl`, `procs/xy.tcl` | `procs/abc.tcl` (more than one char) |
| `reports/**` | `reports/base.txt`, `reports/sub/detail.txt`, `reports/a/b/c/file.txt` | (matches all files at any depth) |
| `rules/**/*.fm.tcl` | `rules/r1.fm.tcl`, `rules/sub/r2.fm.tcl` | `rules/r1.tcl` (different extension) |
| `*_procs.tcl` | `core_procs.tcl`, `dft_procs.tcl` (at domain root) | `procs/core_procs.tcl` (in subdirectory) |

**Glob expansion rules:**
- Glob patterns work with `files.include` and `files.exclude` only. Proc-level includes/excludes use exact file paths and proc names, not patterns.
- When a glob pattern expands to zero files, it is silently ignored (no error).
- All glob pattern expansions are normalized, deduplicated, and sorted in lexicographic order before compilation.
- Patterns are **case-sensitive**.
- Literal file paths (no special characters) refer to exact single files and take precedence over glob patterns per R1.

**R1 Application to Glob Patterns:**
- Literal paths in `files.include` **always survive**, even if they match an `files.exclude` pattern.
- Wildcard-expanded `files.include` candidates **are pruned** by matching `files.exclude` patterns (normal set subtraction).
- Glob expansion happens **before** R1 conflict rules are applied, so the conflict resolution operates on the fully expanded sets.

**Mixing literal and glob in one `files` block:**
```json
{
  "files": {
    "include": [
      "vars.tcl",                    // Literal: exact file must exist
      "procs/*.tcl",                 // Glob: all .tcl files directly under procs/
      "rules/**/*.fm.tcl",           // Glob: all .fm.tcl files anywhere under rules/
      "templates/base/**"            // Glob: all files anywhere under templates/base/
    ],
    "exclude": [
      "procs/debug/*.tcl",           // Glob: exclude debug Tcl files in procs/
      "rules/**/obsolete/**"         // Glob: exclude any obsolete subdirectories under rules/
    ]
  }
}
```

Full normalization, glob expansion, deduplication, and manifest-emission rules are implemented in `src/chopper/compiler/` (see also the R1 interaction matrix in §4).

By default, owner-curated configuration JSONs live under the selected domain at `jsons/base.json` and `jsons/features/*.feature.json`.

### 6.4 Base JSON Structure

> Schema: `schemas/base-v1.schema.json`
> Progressive examples: `examples/01_base_files_only/` through `07_base_full/`

```json
{
  "$schema": "base-v1",
  "domain": "fev_formality",
  "description": "Bare-minimum formality flow for rtl2gate and gate2gate verification",
  "options": {
    "cross_validate": true
  },
  "files": {
    "include": [
      "vars.tcl",
      "prepare_fev_formality.tcl",
      "promote.tcl",
      "utils/**",
      "reports/base/**"
    ],
    "exclude": [
      "utils/debug/**",
      "reports/base/obsolete/**"
    ]
  },
  "procedures": {
    "include": [
      {
        "file": "default_fm_procs.tcl",
        "procs": [
          "read_libs",
          "read_gate",
          "report_match_results",
          "report_verify_results"
        ]
      },
      {
        "file": "default_rules.fm.tcl",
        "procs": ["NonEquivalent", "Unverified"]
      }
    ],
    "exclude": [
      {
        "file": "default_fm_procs.tcl",
        "procs": ["legacy_debug_dump"]
      }
    ]
  },
  "stages": [
    {
      "name": "setup",
      "load_from": "",
      "command": "fm_shell -f run_setup.tcl",
      "inputs": [],
      "outputs": ["setup.done"],
      "run_mode": "serial",
      "steps": [
        "source $ward/global/snps/$env(flow)/setup.tcl",
        "step_load.tcl",
        "fc.app_options.tcl",
        "prepare_fev_formality.tcl",
        "$ivar(fev,project_setup) -optional",
        "step_close.tcl"
      ]
    },
    {
      "name": "verify",
      "load_from": "setup",
      "command": "fm_shell -f run_verify.tcl",
      "inputs": ["setup.done"],
      "outputs": ["verify.done"],
      "run_mode": "serial",
      "steps": [
        "source $ward/global/snps/$env(flow)/setup.tcl",
        "step_load.tcl",
        "fev_fm_rtl2gate.tcl",
        "step_verify.tcl",
        "step_signoff_summary.tcl -optional",
        "step_close.tcl"
      ]
    }
  ]
}
```

This base example intentionally shows:
- Whole-file include and exclude patterns
- Proc-level include and exclude shapes
- Two fully defined stages
- Raw `source` usage, normal step files, and optional step references
- Stage-level `load_from` (required), optional `dependencies`, `exit_codes`, `command`, `inputs`, `outputs`, `language`, and `run_mode`

For users who define stages, the optional mapping to stack records is direct: `name` -> `N`, `command` -> `J`, `exit_codes` -> `L`, `inputs` -> `I`, `outputs` -> `O`, `dependencies` -> `D`, and `run_mode` -> `R` (only when `parallel`). By default Chopper emits only the generated `<stage>.tcl` scripts; set `options.generate_stack: true` to additionally assemble one aggregate `<basename(domain_root)>.stack` containing one record per stage in topological order (see §3.6), or apply the mapping by hand when maintaining an external stack file. For wrapper stages whose `steps` are themselves a verbatim scheduler record, set `standalone_stack: true` on the stage to emit `<stage>.stack` instead of `<stage>.tcl`.

**Validation rule:** an entry in `procedures.include` or `procedures.exclude` with an empty `procs` array (`"procs": []`) is a **hard error (`VE-03`)**. For include: if the author intended to keep the whole file, the correct action is to move the file into `files.include`. For exclude: if there's nothing to exclude, omit the entry entirely. Chopper rejects empty procs arrays during validation and dry-run, with an actionable error message.

### 6.5 Feature JSON Structure

> Schema: `schemas/feature-v1.schema.json`
> Examples: `examples/08_base_plus_one_feature/`, `09_base_plus_multiple_features/`, `10_chained_features_depends_on/`

```json
{
  "$schema": "feature-v1",
  "name": "dft",
  "description": "DFT-related verification support, scan setup, and optional audit stages",
  "metadata": {
    "related_ivars": ["ivar(fev,enable_dft)", "ivar(fev,enable_scan_audit)"],
    "tags": ["signoff", "dft"],
    "wiki": "https://wiki.internal/fev/dft",
    "owner": "dft_team"
  },
  "files": {
    "include": [
      "addon_fm_procs.tcl",
      "scan/**",
      "reports/dft/**"
    ],
    "exclude": [
      "scan/legacy/**"
    ]
  },
  "procedures": {
    "include": [
      {
        "file": "default_fm_procs.tcl",
        "procs": [
          "add_fm_scan_constraints",
          "check_metaflop_settings"
        ]
      },
      {
        "file": "default_rules.fm.tcl",
        "procs": ["MetaflopErrgen"]
      }
    ],
    "exclude": [
      {
        "file": "default_fm_procs.tcl",
        "procs": ["legacy_scan_constraints"]
      }
    ]
  },
  "flow_actions": [
    {
      "action": "replace_step",
      "stage": "verify",
      "reference": "fev_fm_rtl2gate.tcl",
      "with": "fev_fm_rtl2gate_v2.tcl"
    },
    {
      "action": "replace_stage",
      "reference": "legacy_verify",
      "with": {
        "name": "enhanced_verify",
        "load_from": "setup",
        "command": "fm_shell -f run_enhanced_verify.tcl",
        "inputs": ["setup.done"],
        "outputs": ["enhanced_verify.done"],
        "run_mode": "serial",
        "steps": [
          "source $ward/global/snps/$env(flow)/setup.tcl",
          "step_load.tcl",
          "step_enhanced_verify.tcl",
          "step_close.tcl"
        ]
      }
    },
    {
      "action": "add_step_after",
      "stage": "setup",
      "reference": "fc.app_options.tcl",
      "items": [
        "step_dft_setup.tcl",
        "step_scan_collateral.tcl"
      ]
    },
    {
      "action": "add_step_before",
      "stage": "verify",
      "reference": "step_close.tcl",
      "items": [
        "#if {$ivar(fev,enable_scan_audit)}",
        "step_scan_audit.tcl",
        "#else",
        "step_scan_audit_stub.tcl",
        "#endif"
      ]
    },
    {
      "action": "add_stage_before",
      "name": "pre_verify_checks",
      "reference": "verify",
      "load_from": "setup",
      "command": "fm_shell -f run_pre_verify_checks.tcl",
      "inputs": ["setup.done"],
      "outputs": ["pre_verify_checks.done"],
      "run_mode": "serial",
      "steps": [
        "source $ward/global/snps/$env(flow)/setup.tcl",
        "step_load.tcl",
        "step_pre_verify_checks.tcl",
        "step_close.tcl"
      ]
    },
    {
      "action": "add_stage_after",
      "name": "scan_audit",
      "reference": "verify",
      "load_from": "verify",
      "command": "fm_shell -f run_scan_audit.tcl",
      "inputs": ["verify.done"],
      "outputs": ["scan_audit.done"],
      "run_mode": "serial",
      "steps": [
        "source $ward/global/snps/$env(flow)/setup.tcl",
        "step_load.tcl",
        "step_scan_audit_collect.tcl",
        "step_scan_audit_report.tcl",
        "step_close.tcl"
      ]
    },
    {
      "action": "remove_step",
      "stage": "setup",
      "reference": "legacy_scan_step.tcl"
    },
    {
      "action": "remove_stage",
      "reference": "obsolete_debug"
    },
    {
      "action": "load_from",
      "stage": "verify",
      "reference": "pre_verify_checks"
    }
  ]
}
```

This feature example intentionally covers all major reader-facing cases:
- File include and exclude
- Proc include and exclude
- Step replacement via `replace_step` action
- Stage replacement via `replace_stage` action
- All stage/step actions (FlowBuilder 7 + 2 Chopper additions) in one example set
- Optional `metadata` block with tags, wiki, owner, and related ivars (all informational)
- Multi-step insertion through `items`
- Stage creation with `load_from` (required), and optional `command`, `inputs`, `outputs`, and `run_mode`
- Conditional step insertion with `#if / #else / #endif`

In real domains, a feature JSON will usually use only the subset of actions it actually needs.

### 6.6 Project JSON Structure

> Schema: `schemas/project-v1.schema.json`
> Examples: `examples/08_base_plus_one_feature/project.json`, `11_project_base_only/`

The **Project JSON** is the single-file packaging form for reproducible, auditable trim runs. It bundles the complete selection — base path, ordered feature paths, project metadata, and selection rationale — into one file that can be version-controlled, shared across team members, and used in CI pipelines.

**Project JSON vs direct CLI arguments:**

| Scenario | Typical Packaging |
|---|---|
| Initial exploration / JSON authoring iteration | `--base` (± `--features`) |
| One-off quick trim with known inputs | `--base` (± `--features`) |
| Reproducible trim for a project branch | `--project` |
| CI/CD automated trim pipeline | `--project` |
| Shared trim recipe across team members | `--project` |
| Audit trail showing exactly what was selected and why | `--project` |

Equivalent resolved selections must produce the same trimmed output whether they are provided directly with `--base`/`--features` or indirectly through `--project`.

**Structure:**

```json
{
  "$schema": "project-v1",
  "project": "PROJECT_ABC",
  "domain": "fev_formality",
  "owner": "domain_owner",
  "release_branch": "project_abc_rtm",
  "base": "jsons/base.json",
  "features": [
    "jsons/features/scan_common.feature.json",
    "jsons/features/dft.feature.json",
    "jsons/features/power.feature.json"
  ],
  "notes": [
    "scan_common is ordered ahead of dft because DFT inserts steps into scan-owned setup content",
    "power remains enabled because compare_lp is replaced by the selected feature set"
  ]
}
```

**Required fields:**

| Field | Type | Description |
|---|---|---|
| `$schema` | string | Must be `"project-v1"` |
| `project` | string | Project identifier (e.g., `PROJECT_ABC`) |
| `domain` | string | Domain identifier. It must match the basename of the current working directory, which is the operational domain root. |
| `base` | string | Path to the base JSON file (resolved relative to the current working directory / domain root). Default expected location: `jsons/base.json`. |

**Optional fields:**

| Field | Type | Description |
|---|---|---|
| `owner` | string | Domain deployment owner for this project |
| `release_branch` | string | Git branch name for this project trim |
| `features` | array of strings | List of feature JSON paths (resolved relative to the current working directory / domain root). Default expected location pattern: `jsons/features/*.feature.json`. **Order is authoritative for everything** — F1, F2, and F3. Layers are applied left-to-right; the last layer that mentions a file/proc/step wins (R1). |
| `notes` | array of strings | Human-readable notes explaining feature ordering or selection rationale |

**Path resolution rules:**
- Chopper assumes it is invoked from the domain root. The current working directory is therefore the root for resolving `base` and `features`.
- `base` and `features` paths are resolved relative to the current working directory, not relative to the project JSON file location.
- **The operator MUST `cd` into the domain root before running `chopper trim --project <path>`.** The project JSON can live anywhere — `configs/`, outside the repo, anywhere on disk — but its `base` and `features` strings reference paths under the domain root, not under the project JSON's own location.
- `..` is **forbidden** in `base` and `features` strings (per §6.3.1). Absolute paths are also forbidden. Project JSONs stored outside the domain (e.g., `configs/project_abc.json` at the repo root) must still express their `base`/`features` as domain-relative paths such as `jsons/base.json`.
- The default expected curated JSON layout under the domain root is `jsons/base.json` and `jsons/features/*.feature.json`.
- All other path rules from §6.3.1 apply (forward slashes, no absolute paths).
- The project JSON `domain` field is compared case-insensitively against the basename of the current working directory (see §5.1). If `--domain` is provided with `--project`, it must resolve to that same directory. Mismatches are reported as `VE-17`.

**CLI usage:**
```bash
# Validate a project JSON
chopper validate --project configs/project_abc.json

# Dry-run using a project JSON
chopper trim --dry-run --project configs/project_abc.json

# Live trim using a project JSON
chopper trim --project configs/project_abc.json
```

**Mutual exclusivity:** `--project` is mutually exclusive with `--base` and `--features`. Providing both is `VE-11` (`conflicting-cli-options`, exit code 2).

**Audit traceability:** When `--project` is used, the `project`, `owner`, `release_branch`, and `notes` metadata are recorded in `chopper_run.json` and `compiled_manifest.json` so the audit trail captures not just what was selected but the project-level context.

This project example intentionally shows:
- A schema-tagged reproducible selection file
- One selected base and an ordered feature list
- Lightweight notes explaining why the chosen feature order matters

#### 6.6.1 Generated File Header

Every artifact emitted by Chopper's F3 generators is prefixed with the verbatim Intel-standard copyright header, applied **once at the top of the file** regardless of how many stage records the file contains. This covers: every `<stage>.tcl`, the aggregate `<basename(domain_root)>.stack` (header once, then one record per stage), and every per-stage `<stage>.stack` produced by `standalone_stack: true` (header once, then verbatim `steps`). The header is hard-coded in the generator (`chopper.core.header`) and is not configurable per domain — Chopper is domain-agnostic but every domain in scope is an Intel asset, so a single canonical header applies uniformly.

Header content (rendered with `#` comment style for both `.tcl` and `.stack` outputs):

```
####################################################################################################
#Intel Legal compliant copyright header
####################################################################################################
#
#-- INTEL CONFIDENTIAL
#-- Copyright (c) <YEAR> Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and your use of them
# is governed by the express license under which they were provided to you ("License"). Unless the
# License provides otherwise,you may not use,modify, copy, publish, distribute, disclose or transmit
# this software or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or implied warranties,
# other than those that are expressly stated in the License.
#
####################################################################################################
```

The wording and whitespace (including the trailing spaces preserved on a few lines and the `--` prefix on the `INTEL CONFIDENTIAL` / `Copyright` lines) match the canonical Intel-owned EDA file header byte-for-byte. `<YEAR>` is substituted at emission time using `datetime.now().year`, so generated files always carry the current calendar year without manual edits.

The provenance line (`# Chopper-generated stage: <name>` or `# Chopper-generated stack: <name>`) and the optional `# load_from: <name>` line follow immediately after the closing rule of the header. The header is **not** prepended to F1 `FULL_COPY` or F2 `PROC_TRIM` files: those originate on disk and already carry their own headers; rewriting them would be a destructive content edit outside the trimmer's contract.

### 6.7 Action Vocabulary

Chopper adopts FlowBuilder's 7-action vocabulary for stage/step modification, and adds two Chopper-specific action keywords for step and stage replacement:

| Action | Meaning |
|---|---|
| `add_step_before` | Insert steps before a reference step |
| `add_step_after` | Insert steps after a reference step |
| `add_stage_before` | Insert a new stage before a reference stage |
| `add_stage_after` | Insert a new stage after a reference stage |
| `remove_step` | Remove a step from a stage |
| `remove_stage` | Remove a stage |
| `load_from` | Change stage data dependency |
| `replace_step` | Replace a step in a stage with a different step |
| `replace_stage` | Replace a stage with a new stage definition |

#### Instance Targeting with `@n`

Real domains may contain duplicate steps within a stage (e.g., `step_load_post_compile_constraints.tcl` appears twice in `compile_initial_opto`). The `@n` suffix allows targeting a specific occurrence:

```json
{
  "action": "replace_step",
  "stage": "compile_initial_opto",
  "reference": "step_load_post_compile_constraints.tcl@2",
  "with": "step_load_constraints_v2.tcl"
}
```

**`@n` rules:**
- `@1` is equivalent to no `@` (first occurrence)
- `@n` where `n` exceeds the actual count of that step string is a validation error (`VE-10`)
- `@n` is supported on: `replace_step`, `remove_step`, `add_step_before`, `add_step_after`
- `@n` is NOT supported on stage-level actions (stage names must be unique)

Action application contract:
- Features are applied in selected order.
- Within one feature, actions are applied top-to-bottom.
- `reference` and `stage` matching is exact (with optional `@n` instance targeting for steps).
- If a stage contains the same step string multiple times, `replace_step` and `remove_step` use `@n` targeting to resolve ambiguity. Without `@n`, duplicate step strings are a validation error.
- `replace_stage` removes the target stage, inserts the replacement stage at the same position, and rewrites existing `load_from` references to the new stage name before later actions run.
- Removing a stage or step that is still referenced elsewhere is a validation error until repaired by subsequent actions in the same ordered compile pass.

#### Order Preservation for `add_*_after` Actions

When two or more features each carry an `add_step_after` (or `add_stage_after`) action that targets the **same anchor**, the resolver preserves the **selected feature order** in the emitted output. "Selected feature order" is whatever order `LoadedConfig.features` carries, and that order is the same regardless of selection source:

- **`--project <p>.json`** — the order declared in `project.json` `features[]`, after the loader's depends-on topo-sort (which is stable within equal-rank groups, so authored order is preserved when no `depends_on` constraints reorder it).
- **`--features f1.feature.json,f2.feature.json,...`** — the left-to-right order of the comma-separated CLI list, after the same topo-sort.

The two surfaces are equivalent: the same R1 ordered-overlay contract that governs F1 (file decisions) and F2 (proc decisions) in `merge_service.py` governs F3 (stage / step decisions) here.

Concretely, given anchor `X` in stage `S` and selection `features = [F1, F2, F3]` where each feature contributes `add_step_after S:X items=[...]`, the resolved step sequence around the anchor is:

```
..., X, <items from F1>, <items from F2>, <items from F3>, ...
```

The same contract holds for `add_stage_after` keyed on the `reference` stage name. The resolver tracks a per-resolve cumulative insertion offset for each `(stage, anchor)` pair so each subsequent same-anchor `add_*_after` lands *after* the prior feature's items, not directly adjacent to the anchor.

`add_step_before` and `add_stage_before` already preserve selected feature order naturally — each insertion sits immediately before a (now-shifted) anchor — so no offset bookkeeping is required for the `_before` family. The order-independent F3 actions (`replace_step`, `replace_stage`, `remove_step`, `remove_stage`, `load_from`) follow last-layer-wins semantics, which is consistent with R1 across F1, F2, and F3.

#### Optional Stage Targets — `skip_if_no_stage`

Cross-cutting features (e.g. a `sequential_const_check` that injects a constraint step into every gate-level stage that happens to be present) frequently target a *set* of stages that varies with the project selection. When the user composes a partial project (`--features` with only a subset of the stages loaded), a flow_action that names a stage which is not in the current compiled sequence is, by default, an authoring error (`VE-05 missing-action-target`, exit 1).

This default is correct when the action's stage name is the author's contract. It is wrong when the author's intent is *"apply this step everywhere the stage exists; otherwise leave the flow alone"*. To express that intent, every flow_action object accepts an optional boolean:

```json
{
  "action": "add_step_after",
  "stage": "fev_fm_gate2gate",
  "reference": "step_pre_eco.tcl",
  "items": ["step_sequential_const_check.tcl"],
  "skip_if_no_stage": true
}
```

**Semantics:**

- **Field:** `skip_if_no_stage: boolean`, default `false`. Applies to every action variant whose `stage` or `reference` names a base stage: `add_step_before`, `add_step_after`, `add_stage_before`, `add_stage_after`, `remove_step`, `remove_stage`, `replace_step`, `replace_stage`, `load_from`.
- **Scope:** **per-action.** Not per-feature, not per-project. Each action declares its own optionality so an author can opt one injection in and keep the rest hard.
- **Behaviour when `true` and the target stage is absent:** the resolver emits `VI-05 flow-action-skipped-no-stage` (info, exit 0) and skips the action. The working stage sequence is unchanged. Downstream P5 / P6 see exactly what they would have seen if the action had never been declared.
- **Behaviour when `true` and the target stage is present:** identical to `false`. The action runs normally; step-level resolution still applies, and a missing step inside a present stage still emits `VE-05` (see below).
- **Behaviour when `false` (the default):** unchanged. A missing stage emits `VE-05` and blocks output.
- **Step-level miss is unaffected.** `skip_if_no_stage: true` softens only the *stage-not-found* path. If the stage exists but the named step `reference` does not, that is still `VE-05` (exit 1). Rationale: stage existence is a structural property of which features the user selected; step existence inside a present stage is an authoring contract between this feature and the stage author. The two failure modes have different root causes and must remain separately observable.
- **`load_from`** uses `skip_if_no_stage` to gate the *modified* stage (`action.stage`), not the new predecessor (`action.reference`). A `load_from` whose `stage` is absent is skipped; a `load_from` whose `reference` predecessor is absent emits `VE-05` (the predecessor is a structural promise of the flow).
- **`add_stage_*`** uses `skip_if_no_stage` to gate the anchor (`action.reference`), since the new stage being inserted does not yet exist by definition.

`VI-05` carries the feature name, the action keyword, and the missing stage name in its diagnostic context so a `run_result.json` reader can summarise *which* injections degraded silently in this project composition. The info severity ensures `--strict` does not flip it into a failure (per `VI-*` policy): silent-skip is the author's explicitly chosen contract, and elevating it would defeat its purpose.

### 6.8 Dry-Run Output Model

`chopper trim --dry-run` runs the full pipeline and emits these artifacts without writing or modifying any domain files. This is the primary authoring feedback loop.

| Output | Purpose |
|---|---|
| **Compiled manifest** | Resolved file and proc treatment decisions (`FULL_COPY`, `PROC_TRIM`, `GENERATED`, `REMOVE`) |
| **Dependency graph** | Full proc trace results including `source`/`iproc_source` and proc call edges |
| **Trim report** | What would be trimmed, and why each file/proc survives or is removed |
| **Diagnostics** | All warnings and errors with severity, code, location, and hint fields |

Minimum dry-run artifact set:
- `compiled_manifest.json`
- `dependency_graph.json`
- `trim_report.json`
- `trim_report.txt`

These artifacts are part of Chopper's public data contract. Their documented structures, minimum required fields, and the rule that text reports are projections of the corresponding JSON artifact live with the serialization layer in `src/chopper/core/serialization.py` and the audit module in `src/chopper/audit/`.

---

## 7. Requirements

### 7.1 Functional Requirements

| ID | Requirement |
|---|---|
| FR-01 | Accept one base JSON as the required domain baseline. |
| FR-02 | Accept zero or more feature JSONs. |
| FR-03 | Accept input through CLI or project JSON. |
| FR-04 | Trace nested Tcl proc calls transitively by default. |
| FR-05 | Produce trimmed output containing only needed files and procs. |
| FR-06 | Copy only needed files from backup into the rebuilt domain. |
| FR-07 | Delete only unwanted Tcl proc definitions from copied files. |
| FR-08 | Apply ordered-overlay include/exclude semantics across layers (base + features in declared order): later layers win over earlier layers. A feature can add, remove, or replace anything an earlier layer contributed. Same-layer authoring conventions (`VW-09` / `VW-11` / `VW-12` / `VW-13`) still apply. |
| FR-09 | Apply R1 (conflict resolution) consistently across all selected inputs. |
| FR-10 | Deduplicate output so each surviving proc appears once. |
| FR-11 | Validate syntax and obvious dangling references after trimming. |
| FR-12 | Emit `.chopper/` audit artifacts for every run. |
| FR-13 | Support first trim and re-trim using `_backup`. |
| FR-14 | Provide cleanup support to remove backups at project finalization. |
| FR-15 | RETIRED — slot withdrawn pre-v1; never reused (per §5.11 registry-style numbering rules, retired rows stay in the table for audit trail). |
| FR-16 | Treat non-Tcl files at whole-file granularity only. |
| FR-17 | Support dry-run preview mode. Dry-run is mandatory for domain owners to validate JSON files before live trim. |
| FR-18 | Understand `iproc_source -file ...` including `-optional`, `-use_hooks`, `-quiet`, and `-required`. |
| FR-19 | RETIRED — slot withdrawn pre-v1; never reused (per §5.11 registry-style numbering rules, retired rows stay in the table for audit trail). |
| FR-20 | Discover hook files from `-use_hooks` during trim pipeline analysis; report in diagnostics and dry-run output; copy them only when explicitly included in selected JSON. |
| FR-21 | Support step replacement (`replace_step`) and stage replacement (`replace_stage`) as action keywords. Support `@n` instance targeting for duplicate steps. |
| FR-22 | Emit trim statistics in JSON and text form (LOC excludes blank lines and comment-only lines). |
| FR-23 | Emit a VCS-agnostic machine-readable audit set in `.chopper/`: `compiled_manifest.json` (file and proc treatment decisions), `dependency_graph.json` (resolved call edges plus `source` / `iproc_source` edges), `trim_report.json` (file operations and semantic operations — procs removed/kept, `replace_step` / `replace_stage` actions applied, auto-trace expansions), and `trim_report.txt` (human-readable projection of `trim_report.json`). JSON artifacts are the canonical form; text reports are derived. |
| FR-24 | Keep F3 as a first-class required capability. |
| FR-25 | Keep tracing default-on and conservative. |
| FR-26 | `--dry-run` emits compiled manifest, dependency graph, and trim reports without modifying any domain files. Domain owners author JSONs manually; dry-run is the authoring iteration loop. |
| FR-27 | Keep full-file promotion explicit only; never promote implicitly from trace or warnings. |
| FR-28 | Provide pre-trim JSON validation (Phase 1) that catches schema errors, empty procs arrays, missing files/procs, and invalid actions before any files are modified. |
| FR-29 | Provide standalone `chopper validate` command that runs Phase 1 checks without requiring domain source files. Its a structural only check. |
| FR-30 | Build a per-run proc index before tracing and serialize the resolved trace outcome into audit artifacts. |
| FR-31 | Apply feature order deterministically as the R1 overlay sequence, and apply `flow_actions` top-to-bottom within each feature. |
| FR-32 | Perform live trim through the backup-and-rebuild model: write directly into the rebuilt domain tree, preserve `<domain>_backup/` as the recovery source, and rely on re-trim to recover from partial failures. |
| FR-33 | Emit stable machine-readable diagnostics with severity, code, location, and hint fields. |
| FR-34 | Provide explicit `chopper cleanup` support for last-day backup deletion. |
| FR-35 | Accept a project JSON (`--project`) as an alternative to `--base`/`--features`, resolving base and feature paths from it and recording project metadata in audit artifacts. |
| FR-36 | `--project` is mutually exclusive with `--base` and `--features`; providing both emits `VE-11` (`conflicting-cli-options`, exit code 2). |
| FR-37 | Equivalent resolved selections must produce identical compilation and trim results regardless of whether they came from direct CLI arguments or a project JSON. |
| FR-38 | All library-layer operations return typed result objects (frozen dataclasses) — never bare prints — so a future GUI or alternate front-end can consume the same service surface the CLI uses. |
| FR-39 | All public result objects are JSON-serializable via a single canonical serializer; round-trip (serialize → deserialize → compare) produces structurally equivalent values. |
| FR-40 | Progress and log events are emitted through a `ProgressSink` protocol; the CLI attaches a renderer, but library code never binds to a concrete sink. (There is no internal structured-logging channel; see §5.12.4.) |
| FR-41 | Diagnostic codes, severities, and exit semantics are stable within a major schema version so downstream consumers (GUI, CI, dashboards) can rely on them. |
| FR-42 | **Removed in 4.0.0.** Previously: `chopper mcp-serve` started a stdio-only read-only Model Context Protocol server. The MCP surface (subcommand, `src/chopper/mcp/`, the `mcp` dependency, and `PE-04`/exit-code 4) was removed entirely and is a closed decision. See §3.9. |
| FR-43 | `chopper validate --features` accepts directory entries in its comma-separated list; each directory expands in place to the sorted (lexicographic), non-recursive set of its immediate `*.json` children. `chopper trim` and `--project` (in any subcommand) still require explicit per-file paths. See §5.1. |
| FR-44 | P4 maintains a **tool-command pool** (§3.10) — the union of built-in `.commands` files under `src/chopper/data/tool_commands/` and user-supplied files passed via the repeatable CLI flag `--tool-commands <path>`. When a call token fails namespace resolution and its raw or leaf name is in the pool, the tracer emits `TI-01 known-tool-command` instead of `TW-02 unresolved-proc-call` and records an `Edge` with `status = "tool_command"`. The pool is not surfaced in any JSON (base / feature / project); CLI flag is the sole user extension. The pool never affects file-level (F1), proc-level (F2), or run-file (F3) decisions. |
| FR-45 | `chopper --version` prints `chopper <version>` to stdout and exits 0. The version string is sourced from the installed package metadata (`importlib.metadata`) with a `pyproject.toml` fallback for source checkouts. `--version` is a top-level global flag; it does not require a subcommand. |
| FR-46 | `chopper loc` runs the same P0–P4 + dry-run-P6 pipeline as `chopper trim --dry-run`, then replays the real P5 trim phases (trim → generators → indentation → companion-sync) against an in-memory copy of the source tree and emits a stdout LOC report comparing the source domain against the actually-rebuilt trimmed domain (files-before/after, physical-lines-before/after, SLOC-before/after, percent reduction). Because the replay reuses the production trim services, the totals are byte-for-byte identical to a live `chopper trim`. The subcommand accepts the same input flags as `validate`/`trim` (`--base [--features]` or `--project`). It writes nothing to the real filesystem — no domain modifications and no `.chopper/` audit bundle (the runner suppresses P7 audit when `command == "loc"`). Exit-code policy matches `validate` (0/1/2/3). See §5.7. |
| FR-47 | The P7 audit bundle includes `.chopper/p4_commands.txt`: a deterministic, sorted Perforce command list. `p4 edit -t text+x` for `PROC_TRIM` and in-place `GENERATED` files; `p4 add -t text+x` for new `GENERATED` files; an `exclude_file_list` section (4.1.0+) with `$ward`-relative paths for removed files (replaces former `p4 delete` commands). Emitted on both live trim and `--dry-run`; not by `validate`, `loc`, or `cleanup`. Chopper never invokes `p4` itself to produce or act on this artifact (see FR-53 for the separate, opt-in `--p4` checkout step). See §5.5.14. |
| FR-48 | After every `trim`, `trim --dry-run`, `validate`, and `loc` run, Chopper prints a P4 branch analysis to stdout. "No branch needed" = all surviving file treatments are `REMOVE` only (pure depot deletions via P4 client-spec resync). "Branch needed" = at least one `PROC_TRIM` or `GENERATED` treatment exists (files modified or added; a P4 branch is required). In multi-domain mode (§5.1.2), per-domain verdicts are printed followed by an aggregate verdict and the list of domains that need a branch. See §5.5.15. |
| FR-49 | When `--domain` resolves in name-mode and no explicit `--project`, `--base`, or `--features` is supplied, Chopper searches `$ward/project/<vendor>/<domain>/` for `<leaf>.project.json` (→ project mode, all project JSON semantics) then `<leaf>.project.features.config` (→ features mode, one feature name per line, blank lines and `#` comments ignored). First match wins. No discovery when path-mode or when any explicit flag is provided. No diagnostic emitted on successful discovery. See §5.1.3. |
| FR-50 | Before the pipeline starts for each domain, Chopper writes a scannable domain run header to stdout (all lines flushed immediately). The header shows: domain label (`domain_logical_name` or leaf name), domain root, base/project JSON path, `config file path` (only for auto-discovered `.project.features.config`), and a numbered feature list. In multi-domain mode, one header precedes each domain's pipeline. See §5.5.16. |
| FR-51 | The P7 audit bundle includes `.chopper/files_exclude_p4.txt`: a standalone, deterministic, sorted list of the domain-relative (or `$ward`-relative, when available) paths excluded from the trimmed output — byte-for-byte the same path set and formatting as the `exclude_file_list` section of `p4_commands.txt`, both backed by the same `_compute_excluded_paths(ctx, record)` computation. Emitted on both live trim and `--dry-run`; not by `validate`, `loc`, or `cleanup`. See §5.5.14. |
| FR-52 | After `chopper trim` (live or `--dry-run`) finishes processing every domain in the run, Chopper prints the resolved `.chopper/` audit bundle path to stdout, immediately after the P4 Branch Analysis summary. In multi-domain mode (§5.1.2), one line per domain is printed under an `=== Audit Bundle Locations ===` banner. Domains that failed a pre-flight check before a context was built are excluded from the listing. See §5.5.17. |
| FR-53 | `chopper trim --p4` (opt-in, live trim only, `trim`-subcommand-only CLI flag, no JSON field) prints a one-line "`--p4` enabled" notice to stdout per domain (right after that domain's run header, suppressed under `--dry-run`), then runs `p4 edit -t text+x` on every `PROC_TRIM` / regenerate-in-place `GENERATED` file, using each file's absolute path, so a human's later `p4 submit` doesn't fight Perforce's checkout-before-edit protocol. Runs on `DomainState.case == 1` (first trim: `domain/` is copied, not renamed, to `domain_backup/` before checkout, then cleared for the rebuild) and `case == 2` (re-trim: the relevant files are first restored from `domain_backup/` to their depot-synced content, then checked out); skipped with an on-screen notice (not an error) when `p4` is unavailable, the domain is not a working p4 client workspace, or `case == 3` (backup only, domain absent — nothing to open). On checkout failure the whole trim aborts (`VE-37`) after `p4 revert` on whatever succeeded; on a later P5 failure after checkout succeeded, rollback additionally restores `domain/` from `domain_backup/` immediately. Chopper never runs `p4 add`, `p4 delete`, or `p4 submit` here. After a successful checkout, Chopper prints the absolute paths it opened for edit to stdout under a `=== P4 Files Opened for Edit ===` banner. Both the enabled notice and the opened-for-edit banner repeat per domain in multi-domain CSV `--domain` runs. See §5.5.18. |

### 7.2 Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Work with the real CTH R2G domain structure as it exists today. |
| NFR-02 | Avoid requiring codebase-wide refactoring before adoption. |
| NFR-03 | Be deterministic and idempotent: the same inputs must produce byte-identical output every time. |
| NFR-04 | Be safe for repeated re-trims within the trim window. |
| NFR-05 | Provide actionable warnings and reports, not silent behavior. |
| NFR-06 | Remain domain-isolated by default. |
| NFR-07 | Remain review-friendly in git and code review. |
| NFR-08 | Be understandable by both human users and downstream LLM tooling. |
| NFR-09 | Avoid staging, locking, and extra promotion machinery; keep the write model direct and recoverable through `<domain>_backup/`. |
| NFR-10 | Normalize all paths and sort all discovery/glob results before compilation. |
| NFR-11 | Keep library code side-effect free; logging configuration belongs only in the CLI entrypoint. |
| NFR-12 | Separate structural schema validation from semantic validation. |
| NFR-13 | Failures must leave an intact `<domain>_backup/` and a deterministic recovery path. A half-rebuilt active domain is acceptable temporarily because the next invocation rebuilds from backup. |
| NFR-14 | Tests must cover parser/trimmer invariants with both fixture-based and property-based techniques. |
| NFR-15 | Audit JSON and text artifacts must remain stable and machine-usable within a major schema version. |

### 7.3 Acceptance Criteria

Chopper is architecturally successful if a domain owner can:

1. Author or refine base/feature JSONs for their domain.
2. Create a project JSON bundling the selection for reproducibility.
3. Run trim using `--base`/`--features` or `--project` and obtain a deterministic rebuilt domain.
4. See why every surviving proc/file remained.
5. Re-trim from backup without manual restore work.
6. Generate F3 output when their domain requires it.
7. Use the same project JSON in CI for automated, reproducible trim runs.

**Measurable gate (byte-identical determinism):** running `chopper trim` twice against the reference fixture `tests/fixtures/mini_domain/` with the same project JSON produces two rebuilt domains whose trimmed file contents and `.chopper/` JSON artifacts are byte-identical (modulo ISO-8601 timestamps isolated in a single documented `run.meta.json` field). This is enforced by a golden-file regression test under `tests/golden/`.

### 7.4 Test and Quality Strategy

The implementation must follow the layered testing and release-quality gates described in [.github/instructions/project.instructions.md](../.github/instructions/project.instructions.md) and the test-suite layout under `tests/`.

---

## 8. Codebase Analysis

### 8.1 Domain Size Comparison

| Domain | Tcl Files | Proc Defs | Non-Tcl Files | Subdirs | Complexity |
|---|---|---|---|---|---|
| **fev_formality** | ~16 | ~60 | 3 | 1 | Medium |
| **sta_pt** | ~70 | ~30+ defined plus many hook files | 13 | 4 | High |
| **power** | ~60+ | ~150+ | 15+ | 8+ | High |

### 8.2 Common Patterns Across Domains

#### A. `iproc_source` Is the Primary Sourcing Mechanism

```tcl
iproc_source -file default_fm_procs.tcl
iproc_source -file addon_fm_procs.tcl -optional
iproc_source -file project_fm_procs.tcl -optional
iproc_source -file user_fm_procs.tcl -optional
```

#### B. Hook Files Exist as Pre/Post Placeholders

```tcl
pre_read_constraints.tcl
post_read_constraints.tcl
```



#### D. `ivar()` Is Configuration, Not Trim Logic

`vars.tcl` and related ivar usage are treated as configuration-bearing files, not something Chopper attempts to interpret semantically.

#### E. Naming Conventions Support Classification

| Pattern | Likely Treatment |
|---|---|
| `*_procs.tcl` | Proc-level candidate |
| `default_rules.*.tcl` | Proc-level candidate |
| `pre_*.tcl` / `post_*.tcl` | File-level hook file |
| `vars.tcl` | File-level keep |
| `*.stack` | File-level |
| `*.pl`, `*.py`, `*.csh` | File-level |



### 8.3 GUI-Readiness Implications

The GUI-readiness surface is defined in §5.11 above. At the architecture level the relevant invariants are:

- **Service layer first.** Every CLI subcommand (`validate`, `trim`, `cleanup`) is a thin adapter over a callable service returning a typed result object. A future GUI invokes the same service without re-implementing logic.
- **No `print()` in library code.** All user-visible output is emitted through a `ProgressSink` plus `DiagnosticSink` pipeline; the CLI attaches a text renderer, a GUI would attach a widget renderer.
- **JSON-first artifacts.** Every textual report is a projection of a JSON artifact; GUIs consume the JSON form directly.
- **Diagnostics are structured.** `(code, severity, message, location, hint)` tuples enable rich GUI surfaces (filterable lists, jump-to-source actions) without additional parsing.

### 8.4 Future Extensibility Hooks

- **Alternate front-ends.** The typed service surface (FR-38–FR-40) is the extension point for a future GUI, language-server integration, or CI dashboard. No additional abstraction is required.
- **Out-of-v1 roadmap.** Planned but non-v1 capabilities are tracked in [technical_docs/IMPLEMENTATION.md](IMPLEMENTATION.md) Future Considerations section. Nothing in this document commits v1 to those items.

### 8.5 Cross-Cutting References

- Parser engineering baseline: [technical_docs/IMPLEMENTATION.md (parser section)](IMPLEMENTATION.md).
- Diagnostic code registry: [technical_docs/DIAGNOSTIC_CODES.md](DIAGNOSTIC_CODES.md).
- Risk and pitfall ledger: [technical_docs/IMPLEMENTATION.md (pitfalls)](IMPLEMENTATION.md).
- CLI surface: [technical_docs/CLI_REFERENCE.md](CLI_REFERENCE.md).
- SNORT comparison and absorbed guardrails: [technical_docs/SNORT_ANALYSIS_AND_CHOPPER_COMPARISON.md](SNORT_ANALYSIS_AND_CHOPPER_COMPARISON.md).

### 8.6 Key Observations

1. Domains are mostly flat or shallow.
2. `*_procs.tcl` is the main proc-trimming opportunity.
3. `iproc_source` support is mandatory.
4. Hook handling must be explicit and predictable.
5. `vars.tcl` is almost certainly base content in most domains.
6. Stack/config files are file-level artifacts.
7. Power templates imply generation hooks must exist in the architecture.

---

## 9. Technical Challenges and Risk Handling

> Merged into [`technical_docs/IMPLEMENTATION.md` (pitfalls)](../technical_docs/IMPLEMENTATION.md).
> Contains TC-01 through TC-10 risk statements, P-01 through P-36 implementation
> pitfalls organized by module, and the process analysis / operational assessment.

---

## 10. Question Ledger

### 10.1 Resolved Questions

| ID | Question | Status | Resolution |
|---|---|---|---|
| Q1 | Are there cross-domain dependencies? | **Resolved** | Treat domains as isolated. |
| Q2 | In-place or output rebuild? | **Resolved** | Backup-and-rebuild. |
| Q3 | Who selects features? | **Resolved** | Domain owner. |
| Q4 | Can a domain be re-trimmed? | **Resolved** | Yes, from `_backup`. |
| Q5 | How are non-Tcl files handled? | **Resolved** | File-level only. |
| Q6 | Is tracing default-on? | **Resolved** | Yes. |
| Q7 | What tracing style do we use? | **Resolved** | Conservative. |
| Q8 | Is F3 required? | **Resolved** | Chopper ships F3 as a first-class capability, but domains may omit it when they do not need F3 behavior. |
| Q9 | What is the final conflict rule? | **Resolved** | R1: explicit include wins over exclude; tracing is reporting-only. |
| Q10 | How are procs identified? | **Resolved** | File + canonical proc name. |
| Q11 | How is top-level Tcl outside procs handled? | **Resolved** | Copy-and-delete model. |
| Q12 | How are hook files handled? | **Resolved** | Hook files discovered through `-use_hooks` during the trim pipeline are reported in diagnostics; they are copied only if explicitly included in selected JSON; otherwise they are ignored during trim. |
| Q13 | What does "override" mean in Chopper? | **Resolved** | F1/F2/F3 use a single ordered-overlay model (R1): later layers win over earlier layers. A feature can add, remove, or replace anything an earlier layer contributed. The audit bundle records every overlay shadow event as `VW-21 layer-shadowed`. F3 keeps its explicit `replace_step` / `replace_stage` action keywords for stage-level changes; F1/F2 do not need separate "override" syntax — `files.exclude` / `procedures.exclude` *are* the override surface. |
| Q14 | Are backups deleted? | **Resolved** | Yes, on the last day during cleanup. |
| Q15 | Is scan a Chopper subcommand? | **Resolved** | No. Scan mode has been removed. Chopper does not generate draft JSONs. Domain owners author JSONs manually; `--dry-run` is the authoring iteration feedback loop. |
| Q16 | Is default action configurable? | **Resolved** | No. Default exclude is fixed. |
| Q17 | Is product implemented already? | **Resolved** | No. It is currently framework/scaffold plus architecture work. |
| Q18 | How is live trim made write-safe? | **Resolved** | Backup-and-rebuild. Chopper writes directly into `domain/`, keeps `<domain>_backup/` intact, and recovers by re-running from backup rather than staging or locking. |
| Q19 | How is feature ordering interpreted? | **Resolved** | Feature order is authoritative end-to-end (F1, F2, and F3). Layers are applied left-to-right; later layers win over earlier ones for files, procs, and stages. Within a feature, `flow_actions` apply top-to-bottom. |
| Q20 | How are warnings and errors represented? | **Resolved** | Stable machine-readable diagnostics with severity, code, location, and hint. |

### 10.2 Open Questions

| ID | Question | Status |
|---|---|---|
| OQ-01 | For `.stack` files, which domains generate them and which domains keep them as-is? | **Resolved** — per-domain, author-controlled via `options.generate_stack` in the base JSON. Default `false` (Chopper does not touch stack files). Setting it to `true` causes F3 to assemble one aggregate `<basename(domain_root)>.stack` containing one record per stage using the derivation rules in §3.6. For wrapper stages whose `steps` already encode a verbatim scheduler record, the per-stage `standalone_stack: true` flag additionally emits `<stage>.stack` verbatim. |
| OQ-02 | For each domain, what exact template-generated outputs are required under F3? | **Open — domain-specific** |
| OQ-03 | Which domains should be used first as implementation proving grounds? | **Open — decided by domain leadership** |

---

## 11. FAQ and Corner Cases

### 11.1 General FAQ

**Q: What is Chopper in one sentence?**  
Chopper is a per-domain trimming tool that keeps only the files, procs, and generated run artifacts needed for a project-specific flow.

**Q: Is Chopper a working product today?**  
No. The repository is still at framework/scaffold stage. The architecture is ahead of the implementation.

**Q: Who is the main user?**  
The primary user is the domain deployment owner.

**Q: What does Chopper replace conceptually?**  
It replaces manual trimming and parts of the FlowBuilder/SNORT/template-generation workflow for signoff domains where file-level trim/build is not feasible.

### 11.2 Trimming FAQ

**Q: What gets trimmed?**  
Domain-local files and Tcl proc definitions that are not required by the selected base and features.

**Q: What never gets trimmed?**  
Anything outside the selected domain trim scope. Chopper operates only on the domain directory it is invoked from; sibling domains, shared infrastructure, and external paths are never read or written.

**Q: Does Chopper edit proc bodies?**  
No. It keeps or removes whole proc definitions only.

**Q: Does Chopper partially trim Perl or Python?**  
No. Non-Tcl files are file-level only.

**Q: What happens if a file is both proc-trimmed and full-file included?**  
The full-file include wins only if some selected JSON explicitly requested the file in `files.include`.

**Q: Can tracing alone force a full file to survive?**  
No. Tracing can justify proc survival, not implicit file-level promotion.

### 11.3 Tracing FAQ

**Q: Why is tracing so important?**  
Because without tracing, proc-level trimming collapses back into manual dependency bookkeeping, which destroys the main product value.

**Q: What if proc A calls proc B and proc B calls proc C?**  
If A is explicitly kept, tracing analyzes downstream calls from A and records B/C in diagnostics and dependency graph artifacts when statically provable within the domain boundary.

**Q: What if tracing sees `$cmd $args`?**  
That is dynamic dispatch. Chopper warns conservatively and does not invent a dependency.

**Q: What if tracing needs a proc from a file that the JSON never mentioned?**  
Chopper warns. Because default exclude is fixed, the owner must explicitly add the missing file or proc.

**Q: Does Chopper trace outside the domain boundary?**  
No. Tracing is strictly bounded to the selected domain path. Out-of-domain references are logged via `VW-17 external-reference` for awareness but are never auto-included or followed.

**Q: Can tracing be turned off globally?**  
Not in the current architecture baseline. Default-on tracing is a core product rule.

### 11.4 F3 FAQ

**Q: Why are F3 steps plain strings instead of structured objects?**  
Because the real step vocabulary is heterogeneous: filenames, raw Tcl commands, ivar expressions, conditionals, and optional flags all coexist. Plain strings keep the model practical.

**Q: What is the downside of plain-string steps?**  
Chopper cannot semantically understand every arbitrary string. It can compose and partially validate, but not fully interpret all Tcl content.

**Q: Why is that acceptable?**  
Because forcing a deeply typed model for all step content would make the tool more brittle and harder to adopt than the problem justifies.

**Q: How is that risk controlled?**  
By validation, optional cross-validation, trace reporting, and domain-owner review.

### 11.5 Backup and Re-trim FAQ

**Q: Why keep backups in the branch at all?**  
Because the trim window requires safe re-trim capability without depending on manual restore work.

**Q: Why not delete backups immediately?**  
Because requirements can change during the trim window and owners need deterministic rebuild from the original domain source.

**Q: When are backups deleted?**  
On the last day during final cleanup.

### 11.6 Corner Case FAQ

**Q: What if two features disagree about a proc?**  
The later-listed feature wins. If `feat_a` includes `foo` and `feat_b` (later in the list) excludes `foo`, the proc is removed and `VW-21 layer-shadowed` is emitted in the audit bundle.

**Q: What if two features replace the same step differently?**  
Later-listed feature wins. F3 follows the same overlay rule as F1/F2.

**Q: What if a PROC_TRIM file has no procs to drop?**  
Chopper still writes the file (byte-identical to the backup) and emits `VW-22 proc-trim-no-drop`. The most common cause is that `<domain>_backup/` holds an already-trimmed copy — for example because `chopper cleanup --confirm` removed the original backup and a subsequent Case 1 run then promoted the trimmed domain to backup. Restore the original source from version control, delete `<domain>_backup/`, and re-run. `trim_report.json` will show `bytes_in == bytes_out` and `procs_removed = []` for the affected file.

**Q: What if a file ends up with no procs left after trimming?**  
The file is kept. If only blank lines and comments remain after proc deletion, Chopper writes that remaining stub, emits `VW-08`, and leaves owner review in the workflow. If a later layer separately whole-file-includes the same file, the full-file copy rule applies and the file survives as a whole file (with `VW-21` recording the shadow).

**Q: What if a hook file exists but is not needed?**  
Hook discovery is not permission for silent bloat. Hook files stay out unless they are explicitly included in some selected layer.

**Q: What if a feature excludes a base item?**  
The feature wins. The base layer ran first and contributed the item; the feature layer ran later and removed it. The audit bundle records this as `VW-21 layer-shadowed` with `(layer = feature_name, prior_layer = base)`.

**Q: What if feature A includes a file and feature B (later) excludes it?**  
The file is removed. Feature B is the later layer and wins. `VW-21` is emitted with `(layer = feat_b, prior_layer = feat_a)`. To keep the file, list the includer after the excluder.

**Q: What if the base includes a whole file and a feature excludes a proc inside it via `procedures.exclude`?**  
The file is downgraded from `FULL_COPY` to `PROC_TRIM` with the named procs removed. The feature's PE entry actually fires; `VW-21` records that the prior whole-file decision was shadowed by a later proc-level intervention.

**Q: What if a feature excludes a file or proc that no earlier layer contributed?**  
That is `VE-27 no-op-exclude` — almost always a typo. Validation fails so the authoring error is caught before trim.

**Q: What if a proc is defined twice in one file?**  
The last definition wins, matching Tcl runtime behavior.

**Q: What if a domain does not need F3?**  
Then the domain can use any combination of F1, F2, and F3 that fits the domain.

**Q: What if a domain needs only F3 and no trimming?**  
That is valid. F3-only remains a supported capability combination.

**Q: Can an LLM use this document safely?**  
Yes. The document is intentionally explicit about boundaries, defaults, resolved rules, and corner cases so that both humans and LLMs can follow the same architecture contract.

---

## 12. Reference Documents and External Inputs

| Document | Purpose |
|---|---|
| [.github/instructions/project.instructions.md](../.github/instructions/project.instructions.md) | Project-wide implementation standards, runtime contracts, CLI engineering behavior, and test gates |
| [technical_docs/DIAGNOSTIC_CODES.md](DIAGNOSTIC_CODES.md) | Authoritative diagnostic code registry (VE / VW / VI / TW / PE / PW / PI families) |
| [technical_docs/CLI_REFERENCE.md](CLI_REFERENCE.md) | Complete CLI subcommand reference: `validate`, `trim`, `cleanup`, flags, examples |
| [technical_docs/IMPLEMENTATION.md (parser section)](IMPLEMENTATION.md) | Tcl parser engineering baseline: tokenizer, namespace resolution, edge cases |
| [technical_docs/IMPLEMENTATION.md (pitfalls)](IMPLEMENTATION.md) | Technical risks (TC-01–TC-10) and implementation pitfalls (P-01–P-36) |
| [technical_docs/ARCHITECTURE.md](ARCHITECTURE.md) §5.11 | GUI-readiness surface: typed results, deterministic serialization, service-layer discipline |
| [technical_docs/IMPLEMENTATION.md Future Considerations](IMPLEMENTATION.md) | Roadmap items explicitly out of v1 scope |
| [technical_docs/SNORT_ANALYSIS_AND_CHOPPER_COMPARISON.md](SNORT_ANALYSIS_AND_CHOPPER_COMPARISON.md) | SNORT comparison and absorbed proc-extraction guardrails |
| Python logging cookbook | Confirms that library code should not configure global logging handlers |
| Python `argparse` docs | Confirms subcommand-oriented CLI structure for `validate`, `trim`, and `cleanup` |
| Python `pathlib`, `shutil`, and `os` docs | Support deterministic path handling, directory rebuild mechanics, and direct-write recovery behavior |
| `jsonschema` documentation | Supports the Phase 1 schema-validation contract |
| pytest good practices and Hypothesis docs | Support the layered fixture plus property-based test strategy |

---

## 13. Implementation Work Queue

### 13.1 Priority Work Items

| ID | Action | Priority |
|---|---|---|
| **AI-01** | Build and validate the Tcl parser / lexer prototype, proc index, and brace-aware structure checker against real domain files | **P0** |
| **AI-02** | Implement dry-run reporting: compiled manifest, dependency graph, and trim report emission without domain file writes | **P0** |
| **AI-03** | Implement compiler logic for FI / FE / PI / PE, ordered feature application, and R1 conflict resolution | **P0** |
| **AI-04** | Implement F2 copy-and-delete trimming engine plus direct-write backup-and-rebuild recovery flow | **P0** |
| **AI-05** | Implement audit trail generation under `.chopper/` with the artifact contracts in Section 5.4 | **P1** |
| **AI-06** | Ship JSON Schema files and semantic validators for base, feature, and project JSONs | **P1** |
| **AI-07** | Implement validation (Phase 1 + Phase 2), diagnostics, exit codes, and standalone `chopper validate` command | **P0** |
| **AI-08** | Implement F3 generation behind a narrow generator interface using only the documented stage and flow-action model | **P1** |
| **AI-09** | Implement dry-run mode (full pipeline simulation without file writes) | **P0** |
| **AI-10** | Build fixture, golden, integration, and property-based tests for tracing, trimming, and retrim flows | **P0** |
| **AI-11** | Implement `chopper cleanup` and the explicit last-day backup removal workflow | **P1** |
| **AI-12** | Implement CLI logging setup and module-scoped diagnostic plumbing | **P1** |

### 13.2 Operational Follow-Ups

| ID | Action | Priority | Status |
|---|---|---|---|
| **OP-01** | Define per-domain F3 expectations for stack/run outputs | **P1** | Open |
| **OP-02** | Approve operational ownership and timing for executing `chopper cleanup` on the last day | **P1** | Open |
| **OP-03** | Establish domain-owner feature catalog conventions: naming standard, central registry, and review expectations | **P2** | Open |

### 13.3 Near-Term Business Priorities (1-Week Horizon)

| ID | Item | Description |
|---|---|---|
| **BP-01** | Define architecture-to-implementation gate criteria | What triggers the transition from docs-first to implementation-first |
| **BP-02** | Resolve OQ-03 (proving-ground domain) | Unblocks AI-10 (real-domain test fixtures) |
| **BP-03** | Complete adoption risk assessment | Authoring overhead and learning-curve during 2-week window |
| **BP-04** | Define feature catalog convention | Naming standard, central registry, and review expectations |

### 13.4 Deferred Until Spec Finalization

| ID | Item | Rationale |
|---|---|---|
| **DF-01** | Add quick-start section to architecture doc | Deferred until spec is final |
| **DF-02** | Add example error/warning messages to doc | Deferred until spec is final |
| **DF-03** | Add terminology note distinguishing "capability" from "feature JSON" | Deferred until spec is final |

---

## 14. Revision History

This log records the conscious **architectural** decisions that shaped the current document. It is **not** a release changelog (see [README.md](../README.md) `## Changelog` and the git log for that). Each row captures *what changed* and *why* — alternatives evaluated and rejected, not merely the final outcome.

| Date | Decision |
|---|---|
| 2024-06-01 | Initial draft. |
| 2026-04-19 | **R0 — Additive feature model (superseded).** Original cross-source aggregation with L1 (explicit-include-wins), L2 (same-source authoring conveniences), L3 (base inviolable, features additive-only). Replaced 2026-05-08; preserved here as the reasoning baseline for R1. |
| 2026-04-24 | **0.4.0 — MCP scope-lock narrowed to read-only stdio.** Reopened the closed MCP decision to permit a **stdio-only, read-only** server (`chopper.validate`, `chopper.explain_diagnostic`, `chopper.read_audit`). All destructive MCP tools, all networked transports, and all sink/progress adapters over MCP remain closed. New `PE-04 mcp-protocol-error` (exit 4); `src/chopper/mcp/` package; hard `mcp>=1.0,<2` dependency. |
| 2026-04-24 | **0.5.0 — Tool-command pool (TI-01).** Real EDA domains emit hundreds of `TW-02 unresolved-proc-call` warnings per run for vendor tool commands (`get_app_var`, `set_dont_touch`, …) burying genuine misses. Added domain-agnostic pool registry (§3.10, FR-44), new `TI` diagnostic family, `TI-01 known-tool-command` (info, exit 0, never strict-escalated). Deliberate non-features: no base-JSON `options.tool_commands` field, no feature-JSON surface, no per-vendor opt-in. Tools describe tools, not domains. |
| 2026-05-08 | **2.0.0-alpha — R1 ordered-overlay model (replaces R0).** Single rule: layers applied in declared order; the last layer that mentions a file/proc wins. Rules L1/L2/L3 deleted. `VW-18`/`VW-19` cross-source vetoes retired (slots preserved per registry policy). New `VW-21 layer-shadowed` (info) and `VE-27 no-op-exclude` (error). `FileProvenance.vetoed_entries` removed; replaced with `contributed_by` and `shadowed_by[]`. Feature ordering is now authoritative for F1, F2, **and** F3 (was F3-only). `FD-14` closed as the design baseline. |
| 2026-05-09 | **2.0.0a3 — P5c indentation made opt-in via `options.indent` (default `false`).** Legacy Perl-port formatter had known structural gaps (no quote/comment awareness, no line-continuation folding, single-`}` dedent only). Rather than rewrite, gate it: when disabled the runner passes through but still computes the rewritten-path tuple so P6 `VE-16` brace-balance coverage stays intact. PROC_TRIM / GENERATED outputs reach disk verbatim. |
| 2026-05-15 | **2.5.0 — Parser fidelity validated against production fixtures.** Fixed quote-context-in-braced-data-word (P-01a — `set q {"}`), switch-pattern-label misparse (P-39), regex-literal walk (P-38), DPA line-continuation (P-40), and `diagnostics.json` file-null-for-P4/P6 (P-41). Established the rule that **bug reports become fixture files**, never inline snippets. |
| 2026-05-15 | **3.0.0 — Coverage hardened to 100%.** Distributed surgical `test_*_coverage.py` files across native `tests/unit/<module>/` locations covering defensive branches, OSError/ValueError handlers, and protocol error paths. Established the rule that tests live in their **native** module locations — no catch-all coverage scripts. `# pragma: no cover` markers properly gate provably-unreachable branches. |
| 2026-06-30 | **4.2.0 — Project-config auto-discovery, domain run header.** When `--domain` resolves in name-mode and no explicit `--project`/`--base`/`--features` is given, Chopper searches `$ward/project/<vendor>/<domain>/` for `<leaf>.project.json` (→ project mode) or `<leaf>.project.features.config` (→ features mode, one name per line) (§5.1.3, FR-49). Before each domain's pipeline, a scannable header block is printed to stdout: domain label, root, base/project JSON path, auto-discovered config file path, and numbered feature list; all lines flushed immediately (§5.5.16, FR-50). New `RunConfig` field: `project_config_path: Path | None` stores the resolved `.project.features.config` path when auto-discovered (None otherwise). |
| 2026-06-17 | **4.1.0 — Domain-name resolution, multi-domain trim, feature-name lookup, base auto-discovery, P4 branch analysis, `exclude_file_list`.** `--domain` now accepts logical names (`fev_formality`, `snps/power`) resolved via `$ward/global/<vendor>/<name>`; vendor-qualified and absolute-path forms supported (§5.1.0). `--base` optional when domain is named (auto-discovery from `jsons/base.json`; VE-35). `--features` accepts feature names resolved from `<domain>/jsons/features/*.feature.json` with close-match suggestions (VE-36). `--domain` CSV for multi-domain sequential trim; `max()` exit code across domains (§5.1.2). P4 branch analysis printed to stdout after every run (§5.5.15, FR-48). `p4 delete` section in `p4_commands.txt` replaced by `exclude_file_list` section with `$ward`-relative paths (§5.5.14, FR-47 updated). New codes: VE-32 (`ward-env-not-set`), VE-33 (`domain-not-found`), VE-34 (`ambiguous-domain-name`), VE-35 (`base-autodiscovery-failed`), VE-36 (`feature-name-not-found`). |
| 2026-05-18 | **3.1.0 — `.chopper/p4_commands.txt` audit artifact (FR-47).** Deterministic Perforce command list correlating every file-treatment decision to `p4 edit` / `p4 add` / `p4 delete`. Three alphabetically-sorted sections; trailing LF; `-t text+x` matches `ensure_executable()`. Emitted on live trim and `--dry-run`; not by `validate` / `loc` / `cleanup`. Chopper never invokes `p4` — the file is a review artifact, not an automation surface. |
| 2026-05-21 | **3.3.0 — F3 aggregate `<domain>.stack` + per-stage `standalone_stack`.** Aggregate stack corrected to one file per flow (matches production EDA artifact contract — pre-3.3 per-stage stacks were wrong). Record-line order `N → J → L → I → O → D → (R parallel)`. `standalone_stack: true` is orthogonal and additive (per-stage verbatim emission). Three new diagnostics: `VE-28`, `VE-29`, `VW-23`. Hard cutover, no shim. |
| 2026-05-21 | **3.4.0 — Topological aggregate stack + `standalone_stack` suppresses `<stage>.tcl`.** Aggregate records now emitted in topological order over `dependencies ∪ {load_from}` (Kahn's algorithm, authored-position tiebreaker) — deterministic, preserves unrelated-subgraph authoring intent. Materialized on `CompiledManifest.stack_order`. `standalone_stack: true` now emits **only** `<stage>.stack` (was both `.tcl` and `.stack`). `VE-30 stage-dependency-cycle` / `VE-31 stage-dependency-unresolved` added. |
| 2026-05-22 | **3.4.1 — P5d companion-file sync (FD-15 ADOPTED).** `CompanionSyncService` runs after P5c. For every `PROC_TRIM` `default_rules.<sfx>.tcl`, filters sibling `default_config.<sfx>.csv` (column 0) and `default_milestone.<sfx>.tcl` (`change_config <ProcName>` lines) against surviving proc short-names. `VW-24 companion-file-missing` and `VI-04 companion-sync-applied` added. |
| 2026-05-23 | **3.5.0 — Optional flow-action stage targets (`skip_if_no_stage`).** Cross-cutting features (e.g. `sequential_const_check`) inject steps into N stages; in partial-project compositions, missing stages previously aborted with `VE-05`. Added per-action boolean `skip_if_no_stage` (default `false`, backward-compatible). When `true` and the target stage is absent, resolver emits new `VI-05 flow-action-skipped-no-stage` (info, exit 0) and skips silently. Step-level miss inside a present stage still emits `VE-05` — stage existence and step existence are distinct contracts. Rejected alternatives: feature-level `optional: true` (too coarse — author cannot opt one injection in); project-level allow-list (couples authoring to project shape); silent fallthrough on every `VE-05` (loses authoring-bug detection). §6.7 updated; `VI-05` registered; feature-v1 schema accepts the new field on every flow_action variant. |
| 2026-05-22 | **3.4.2 — Honor `options.cross_validate` + doc declutter.** The `cross_validate` flag was loaded but never consumed — VW-14/15/16 ran unconditionally. Threaded through `validate_post` → `_check_stage_steps` → `_classify_and_emit`; when `false`, VW-14/15/16 suppressed entirely; VW-17 still fires (does not depend on manifest lookups). Aggressive trim of this revision-history table (the canonical release log lives in git + README.md changelog). `IMPLEMENTATION.md` Appendix A removed (scope-lock in [.github/instructions/project.instructions.md](../.github/instructions/project.instructions.md) already covers OOS items); Appendix B → main-body "Future Considerations" section. |
| 2026-05-23 | **3.5.1 — 100% coverage enforced on the full-suite gate.** The aggregate `test` target (run by `make ci`) now passes `--cov-fail-under=100`; the codebase already hit every reachable line, so this locks it against silent regressions. The fast unit-only gate (`make check`) keeps `--cov-fail-under=99` because unit tests intentionally cover only part of `src/`. §5.12.8 wording updated; rejected alternative: forcing unit-only to 100% (would require contrived unit tests duplicating the integration suite, violating the deliberate suite separation). No code or behavior change. |
| 2026-06-05 | **4.0.0 — MCP surface removed (re-closed).** The stdio-only read-only Model Context Protocol server added in 0.4.0 (`chopper mcp-serve`, `src/chopper/mcp/`, the `mcp>=1.0,<2` runtime dependency, `PE-04 mcp-protocol-error`, and exit code `4`) is removed in full. MCP returns to a **closed decision** — no read-only or destructive, stdio or networked surface may be reintroduced without explicit user approval and an architecture-doc-first cascade. `PE-04` retired (slot preserved, never reused); exit-code surface narrows to `0/1/2/3` across `RunResult`/`RunRecord`/`AuditManifest` and `run-result-v1.schema.json`. Scope-lock §1 in [.github/instructions/project.instructions.md](../.github/instructions/project.instructions.md) restored to fully closed (§1.1 read-only exception deleted). §3.9 retained as a closure record only. |
| 2026-06-30 | **4.2.1 — `files_removed.txt` Ward-relative paths.** The removed-file audit artifact now renders paths as `$ward`-relative when the domain resolves under `$ward`, falling back to domain-relative paths otherwise — matching the `exclude_file_list` section of `p4_commands.txt` (FR-47, 4.1.0+). Both artifacts now share one `_format_exclusion_path` helper in `src/chopper/audit/writers.py` instead of duplicating the ward-prefix/`ValueError`-fallback logic. Incidental fix: closed two pre-existing unit-test coverage gaps in `src/chopper/orchestrator/simulate.py` (the `chopper loc` in-memory replay skipping a manifest-listed `.json` file that is missing from, or unreadable in, the source root) that were blocking both the fast and full coverage gates independent of this change. No new capability, no schema or CLI surface change. |
| 2026-07-09 | **4.3.0 — Standalone `files_exclude_p4.txt` audit artifact + audit bundle location stdout message.** The `exclude_file_list` path set (already written inside `p4_commands.txt`) is now also emitted as its own artifact, `files_exclude_p4.txt`, so tooling that only needs the exclusion list does not have to parse it out of the Perforce command file (FR-51, §5.5.14). Both artifacts now share one `_compute_excluded_paths(ctx, record)` helper in `src/chopper/audit/writers.py` instead of duplicating the walk-and-diff computation. Separately, after `chopper trim` finishes processing every domain, Chopper now prints the resolved `.chopper/` audit bundle path to stdout — one line per domain in multi-domain CSV `--domain` runs, under an `=== Audit Bundle Locations ===` banner (FR-52, §5.5.17). Rejected alternative for the stdout message: folding it into the existing P4 Branch Analysis summary — rejected because the two report different things (Perforce branch necessity vs. where to find this run's own logs) and conflating them would make the P4 analysis harder to script against. |
| 2026-07-09 | **4.4.0 — `--p4` checkout-before-edit (FR-53).** Opt-in, `chopper trim`-only flag: runs `p4 edit -t text+x` on every `PROC_TRIM` / regenerate-in-place `GENERATED` file before P5 rebuilds the domain, closing the gap between Chopper's silent rewrite-in-place model and Perforce's default checkout-before-edit protocol (synced files are read-only until opened; editing them out-of-band and running `p4 edit` afterward is an unsupported recovery path, not first-class Perforce workflow). Deliberately narrow, scoped exception to the "Chopper never invokes `p4` itself" principle (§5.5.14/FR-47, which still holds for `p4_commands.txt` itself — that artifact remains a read-only review file). Only attempted on `DomainState.case == 1` (a genuine first trim: `domain_root` no longer holds the original p4-synced files on a re-trim); skipped with an advisory on-screen notice (no diagnostic code, no exit-code effect) when `p4` is unavailable or the domain isn't a working p4 client workspace. Checkout runs strictly before `_prepare_workspace()` renames `domain/` → `domain_backup/`, because Perforce tracks "opened" state by client path, not inode. New `VE-37 p4-checkout-failed` (phase 5, exit 1) aborts the whole trim on any checkout failure, after `p4 revert` on whatever succeeded; a later P5 failure after checkout already succeeded additionally triggers an **immediate** restore of `domain/` from `domain_backup/` — a deliberate, scoped deviation from NFR-09's default deferred-to-next-run recovery timing, active only on this failure path. Chopper never runs `p4 add`, `p4 delete`, or `p4 submit` — submission remains a human's job. Rejected alternatives: a JSON `options` field (rejected — this is ephemeral per-invocation behavior, not domain-authoring state, matching `--dry-run`'s existing CLI-only precedent); a per-file `p4 where` confidence probe during detection (rejected as unnecessary complexity beyond `p4 info` for the target sites); auto-running `p4 add` for newly-generated stage files (rejected — asymmetric with `p4 edit` since the file must exist on disk first, and out of scope per explicit user direction). See §5.5.18. |
| 2026-07-09 | **4.4.1 — `--p4` bug fixes: rename-before-edit ordering, relative-path silent failure, Case 2 support (FR-53 revised).** Real-CTH-ward testing of 4.4.0 found `--p4` was a complete no-op: `p4 opened` showed nothing after every trim. Two independent bugs, both fixed: (1) checkout ran before `_prepare_workspace()` renamed `domain/` → `domain_backup/`, but Perforce's `p4 edit`/rename ordering assumption in the 4.4.0 design was wrong in practice — the fix replaces rename with `_p4_backup_phase` (copy `domain/` → `domain_backup/`, domain left intact) followed by checkout, then `_p4_clear_phase` empties `domain/` for the normal rebuild; (2) some Perforce client/server combinations silently fail relative-path `p4 edit`/`p4 revert` calls from a non-interactive subprocess (exit 0, empty stdout, `"file(s) not on client"` on stderr) even though the identical relative path succeeds interactively — fixed by invoking `p4 edit`/`p4 revert` with each file's **absolute** path, and by treating an exit-0-with-empty-stdout response as a checkout failure (`checkout_files` previously trusted the exit code alone). Additionally, `DomainState.case == 2` (re-trim, `<domain>_backup/` already exists) is now **supported** rather than unconditionally skipped: `_p4_precopy_from_backup` restores each `PROC_TRIM` / regenerate-in-place `GENERATED` file in `domain/` from `domain_backup/` (which still holds the last-synced depot revision) before checkout runs, so `p4 edit` sees depot-matching content instead of the previous trim's rebuilt output. `case == 3` (backup only, domain absent) remains skipped — there is no file on disk to open. New user-facing output: a `=== P4 Files Opened for Edit ===` stdout summary lists the absolute paths successfully checked out, reusing `P4CheckoutResult.checked_out` rather than shelling out to `p4 opened`. No new diagnostic codes; `VE-37` semantics unchanged. §5.5.18 rewritten in place to describe the corrected two-case (1 and 2) design; the original 4.4.0 row above is left as the historical record of the initial (buggy) release. |

| 2026-07-09 | **4.4.2 — `--p4` enabled stdout notice (FR-53 revised).** `chopper trim --p4` previously gave no indication at the start of a run that checkout-before-edit was active — the only feedback came after the fact (the skip notice on failure, or the "P4 Files Opened for Edit" summary on success), leaving a user watching a live run with no way to confirm `--p4` had actually registered. Added a one-line `--p4 enabled: files will be checked out via 'p4 edit' before rewriting.` notice, printed immediately after each domain's run header (§5.5.16) and before the pipeline starts, whenever `--p4` was passed and the run is not a `--dry-run`. Repeats once per domain in multi-domain CSV `--domain` runs. New `render_p4_checkout_enabled_notice()` in `src/chopper/cli/render.py`; purely informational, no diagnostic code, no exit-code effect — matches the existing advisory-notice precedent for this feature. §5.5.18 and FR-53 updated in place. |
| 2026-07-09 | **4.4.3 — P5c/P5d silently dropped `TrimReport.p4_checkout` (FR-53 revised).** Real CTH-ward testing found `--p4` genuinely opened files for edit (confirmed via `p4 opened`) but the "P4 Files Opened for Edit" stdout summary never printed for `fev_formality`. Root cause: `TclIndentationService` (P5c, opt-in) and `CompanionSyncService` (P5d, e.g. filtering `default_config.<sfx>.csv` / `default_milestone.<sfx>.tcl` companions of a `PROC_TRIM` `default_rules.<sfx>.tcl`) both reconstruct `TrimReport` from scratch whenever they have byte-count updates to apply (`_build_report` in `indentation.py`, `_with_updated_companion_bytes` in `companion_sync.py`), and neither explicitly carried forward the `p4_checkout` field (or `inputs_preserved`) onto the rebuilt object — both silently defaulted to `None`/`0`. Any domain whose manifest triggers P5d (a synced companion file exists for a `PROC_TRIM` rules file) lost the real `P4CheckoutResult` before it reached the CLI layer, even though the underlying `p4 edit` calls succeeded. Fixed both rebuild paths to explicitly thread through `p4_checkout=report.p4_checkout` and `inputs_preserved=report.inputs_preserved`. No behavior change for domains that never exercise P5c/P5d's byte-rewrite path. |

---

## 15. Glossary

| Term | Definition |
|---|---|
| **Domain** | A single EDA tool / flow-stage subtree under `global/<vendor>/<domain>/`. The unit of trimming. |
| **Base JSON** | Required domain baseline JSON (schema `base-v1`). Declares minimum viable F1/F2/F3 content for the domain. |
| **Feature JSON** | Optional overlay JSON (schema `feature-v1`) layered on top of base to add or remove files, procs, or stages. |
| **Project JSON** | Reproducible selection manifest (schema `project-v1`) bundling a base plus ordered feature list for a specific project branch. |
| **F1** | File-level capability: whole-file include/exclude via `files.include` / `files.exclude`. |
| **F2** | Proc-level capability: per-proc include/exclude inside Tcl files via `procedures.include` / `procedures.exclude`. |
| **F3** | Stage-level capability: generated `<stage>.tcl` run files driven by the `stages` array and `flow_actions`. |
| **FI** | `files.include` set (literal paths + expanded globs). |
| **FE** | `files.exclude` set (literal paths + patterns). |
| **PI** | `procedures.include` — additive proc-selection model (within a single layer). |
| **PE** | `procedures.exclude` — subtractive proc-selection model (within a single layer). |
| **PI+** | Transitive trace expansion of PI; reporting-only, never affects survival. |
| **PT** | Traced-only procs (PI+ minus PI); reporting-only. |
| **Layer** | One JSON applied at one position in the R1 overlay sequence (`base`, then each selected feature in declared order). |
| **Running set** | The mutable `{file → treatment}` and `{proc → kept?}` map carried left-to-right through the layers during the P3 fold. |
| **R1 (ordered overlay)** | The single conflict-resolution rule: layers are applied in declared order; the last layer that mentions a file/proc wins. See §4. |
| **FULL_COPY** / `full-copy` | File survives unchanged; all procs retained. |
| **PROC_TRIM** / `proc-trim` | File survives with only the surviving procs retained; other proc bodies deleted. |
| **GENERATED** / `generated` | File is produced by F3 run-file generation, not copied from source. |
| **REMOVE** / `remove` | File is not present in the trimmed output. |
| **TFM** | Tool Flow Manager — the CTH R2G orchestration layer Chopper operates within. |
| **FlowBuilder** | Legacy flow composition tool; Chopper replaces a subset of its manual trimming workflow. |
| **SNORT** | Prior-art proc extractor; Chopper absorbs its false-positive suppression heuristics (see §R3). |
| **ivar** | Internal variable registry used by TFM code (`ivar(key)`); treated as configuration, not trimmed. |
| **iproc_source** | TFM sourcing primitive (`iproc_source -file <path>`); understood by the parser, flags `-optional`, `-use_hooks`, `-quiet`, `-required`. |
| **Hook file** | Pre/post extension point (`pre_*.tcl`, `post_*.tcl`) loaded by `-use_hooks`; reported in diagnostics, copied only when explicitly included. |
| **Stack file** | Optional scheduler metadata file (`N`/`J`/`L`/`I`/`O`/`D`/`R` lines). Authored manually by default; when the base JSON sets `options.generate_stack: true` Chopper assembles one aggregate `<basename(domain_root)>.stack` containing one record per stage (see §3.6). Per-stage `standalone_stack: true` additionally emits `<stage>.stack` with the authored `steps` verbatim (no record derivation). |
| **Signoff** | Final verification stage of the VLSI flow (timing, power, DFT, formality); Chopper's primary adoption target. |
| **Domain boundary** | The directory tree rooted at the domain directory; Chopper never reads, writes, or backs up outside this boundary. |
| **Dry-run** | `--dry-run` mode: full pipeline simulation producing `.chopper/` artifacts without modifying any domain files. |
