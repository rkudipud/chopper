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
| OOS-05 | File-mutation detection via timers or locks (during a run) | Chopper **assumes the filesystem is static for the duration of a single invocation**. No mtime polling between P2 and P5. No file locks. No stale-lock recovery. No in-flight re-stat. If a user (or another process) modifies files under `<domain>/` or `<domain>_backup/` while Chopper is running, the result is undefined behavior and is classified as a **programmer error on the operator side** — not an engineering problem Chopper tries to detect or mitigate. The CLI help text and [`technical_docs/RISKS_AND_PITFALLS.md`](RISKS_AND_PITFALLS.md) make this contract explicit so operators know to run Chopper against a quiesced domain. This boundary is drawn deliberately: adding timers or locks would (a) pull in platform-specific primitives (`fcntl`/`msvcrt`), (b) introduce stale-lock recovery paths, and (c) make testing non-deterministic. All three were rejected in [`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §16 Q3. **Never reintroduce.** |

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

> **Canonical JSON reference:** All schemas, examples (11 progressive scenarios), and the full authoring guide live in `json_kit/`. That package is self-contained and shippable before the Chopper runtime. The examples below are sourced from it.

### 3.1 Base JSON

The **Base JSON** defines the minimum viable flow for a domain.
Schema: `json_kit/schemas/base-v1.schema.json`
It may contain any subset of the F1, F2, and F3 sections. Omitted capability blocks are treated as empty.

By default, the curated base JSON is stored at `jsons/base.json` under the selected domain.

**Minimal valid example** (from `json_kit/examples/01_base_files_only/jsons/base.json`):

```json
{
  "$schema": "chopper/base/v1",
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

**Full example with all three sections** (from `json_kit/examples/07_base_full/jsons/base.json`):

```json
{
  "$schema": "chopper/base/v1",
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
| `$schema` | Yes | Must be `"chopper/base/v1"` |
| `domain` | Yes | Domain directory name (e.g., `my_domain`) |
| `owner` | No | Team responsible for this base |
| `vendor` | No | Vendor (e.g., `synopsys`, `cadence`) |
| `tool` | No | Tool name (e.g., `primetime`, `innovus`) |
| `description` | No | Human-readable summary |
| `options.cross_validate` | No | Cross-validate F3 run-file output against the F1/F2 surviving set. When `true` (default), every step in every surviving stage is checked against the set of files and procs that survived trim; missing targets emit `VW-14` (step file missing), `VW-15` (step proc missing), or `VW-16` (step source missing) — all warnings, never errors. Set to `false` to suppress those warnings when F3 intentionally references content outside the trimmed domain. |
| `options.generate_stack` | No | When `true`, F3 emits one `<stage>.stack` file per resolved stage alongside `<stage>.tcl` (N/J/L/D/I/O/R format derived from the stage's authored fields; see §3.6). Default: `false`. No effect when `stages` is empty. |
| `files.include` | No* | Glob patterns or literal paths to include |
| `files.exclude` | No | Glob patterns to exclude |
| `procedures.include` | No* | Proc-level includes — array of `{ file, procs[] }` |
| `procedures.exclude` | No | Proc-level excludes |
| `stages` | No* | Ordered stage definitions for F3 run-file generation |

*At least one of `files`, `procedures`, or `stages` is required.

### 3.2 Feature JSON

The **Feature JSON** expresses optional behavior layered on top of the base.
Schema: `json_kit/schemas/feature-v1.schema.json`
It may contain any subset of the F1, F2, and F3 sections. Omitted capability blocks are treated as empty.

By default, curated feature JSONs are stored under `jsons/features/` under the selected domain.

**Example** (from `json_kit/examples/08_base_plus_one_feature/jsons/features/dft.feature.json`):

```json
{
  "$schema": "chopper/feature/v1",
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
| `$schema` | Yes | Must be `"chopper/feature/v1"` |
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

**Features are purely additive.** A feature's `files.exclude` and `procedures.exclude` only prune that *same feature's own* include contributions; they cannot remove content contributed by the base or by another feature. Explicit include from any source always wins over exclude from any other source. In detail:

- `files.exclude` prunes glob expansions of the *same JSON's* `files.include` patterns. A feature's FE has no effect on a file contributed by the base or by another feature; when it would, the FE is discarded and `VW-19 cross-source-fe-vetoed` is emitted.
- `procedures.exclude` means "keep the file but remove these procs" — the file survives as `PROC_TRIM` with the excluded procs dropped from *that source's* contribution. If another source (base or any feature) whole-file-includes the same file, or explicitly includes any of the PE'd procs via `procedures.include`, the PE is vetoed and `VW-18 cross-source-pe-vetoed` is emitted. Base content is never stripped by a feature. **An empty `procs` array in any `procEntry` fires `VE-03`** — both `procedures.include` and `procedures.exclude` require at least one proc name per entry; an entry with no procs is an authoring error (likely incomplete edits). If you have nothing to exclude for a file, omit the entry entirely.
- Within a single JSON, mixing `procedures.include` and `procedures.exclude` on the same file is an authoring conflict: PI wins, PE is ignored for that file, and `VW-12` is emitted.
- Within a single JSON, mixing `files.exclude` and `procedures.exclude` on the same file with no PI is redundant: both are removal-within-this-source signals, the file is not contributed by this JSON, and `VW-11` is emitted.
- The full conflict-resolution, file-treatment, and interaction-warning rules are defined in R1.

### 3.3 Project JSON

The **Project JSON** is the reproducible project-specific selection file.
Schema: `json_kit/schemas/project-v1.schema.json`

**Example** (from `json_kit/examples/08_base_plus_one_feature/project.json`, with `jsons/base.json` and `jsons/features/dft.feature.json` as siblings):

```json
{
  "$schema": "chopper/project/v1",
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
- `domain` must match the basename of the current working directory (the domain root), compared case-insensitively via `casefold()` (see §5.1).
- `base` and `features` paths are resolved relative to the current working directory, not the project JSON file location. `..` and absolute paths are forbidden.
- `--project` is mutually exclusive with `--base` and `--features`.

**Key fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `$schema` | Yes | Must be `"chopper/project/v1"` |
| `project` | Yes | Project identifier (e.g., `PROJECT_ABC`) |
| `domain` | Yes | Domain identifier — must match the basename of the current working directory |
| `base` | Yes | Domain-relative path to the base JSON file |
| `owner` | No | Domain deployment owner for this project |
| `release_branch` | No | Git branch name for this project trim |
| `features` | No | List of feature JSON paths (order is authoritative for F3 `flow_actions` sequencing only; F1/F2 merges are order-independent) |
| `notes` | No | Human-readable notes explaining feature ordering or selection rationale |

### 3.4 F1 — File Chopping

F1 performs whole-file trimming via `files.include` and `files.exclude` in base and feature JSONs.

| Behavior | Description |
|---|---|
| **Input unit** | Literal file path or glob pattern |
| **Output unit** | Whole file copied or removed |
| **Best for** | Tcl scripts without shared proc libraries, configs, stack files, hooks, Perl/Python/csh |

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
- When a glob pattern expands to zero files it is silently ignored.
- All expansions are normalized, deduplicated, and sorted lexicographically before compilation.
- Patterns are case-sensitive.
- Glob patterns do NOT apply to `procedures.include` / `procedures.exclude` — those use exact file paths and proc names.

### 3.5 F2 — Proc Chopping

F2 performs Tcl proc-level trimming via `procedures.include` and `procedures.exclude` in base and feature JSONs.

| Behavior | Description |
|---|---|
| **Input unit** | `{ file, procs[] }` — exact file path and proc name list |
| **Output unit** | Original file copied, unwanted proc definitions deleted |
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
- Tracing is default-on: explicitly included procs are expanded transitively for diagnostics and call-tree reporting (PI+), but only explicitly listed procs survive in the trimmed output. See R3.

### 3.6 F3 — Run-File Generation

F3 generates stage-based run files from JSON stage definitions. Users who want generated run scripts define stages; users who still maintain scheduler stack files author those stack files separately from the same stage metadata, or skip stages entirely. When the base JSON sets `options.generate_stack: true`, F3 additionally emits one `<stage>.stack` file per resolved stage alongside `<stage>.tcl` using the same authored metadata.

| Behavior | Description |
|---|---|
| **Input unit** | Ordered `stages` array in base JSON; `flow_actions` in feature JSONs |
| **Output unit** | `<stage>.tcl` (always, when stages are defined). Additionally `<stage>.stack` when `options.generate_stack` is `true` — otherwise any scheduler stack file remains manually authored. |
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
| `run_mode` | No | `R` | `"serial"` (default) or `"parallel"` |
| `language` | No | — | `"tcl"` (default) or `"python"` |

> **`run_mode` semantics.** `run_mode` is advisory metadata surfaced to the scheduler via the stack `R` line; Chopper itself does not parallelize trim execution. Its only effect is to annotate the generated stack entry. Default is `"serial"`.

> **`load_from` vs `dependencies`:** `load_from` feeds the generated `<stage>.tcl` script (data sourcing, `ivar(src_task)` semantics). `dependencies` is the stack `D` line controlling scheduler execution order. They serve different purposes.

**Stack-file auto-generation (`options.generate_stack`).** When the base JSON sets `options.generate_stack: true`, F3 also emits one `<stage>.stack` per resolved stage. The file contains one record per stage rendered as:

```
# Chopper-generated stack: <name>
N <name>
J <command>         (omitted when command is empty)
L <c1> <c2> ...     (omitted when exit_codes is empty)
D <dependency>      (always; see derivation below)
I <input>           (one line per entry; omitted when empty)
O <output>          (one line per entry; omitted when empty)
R <run_mode>        (always; "serial" or "parallel")
```

The `D` line is derived in this order: (1) if `dependencies` is non-empty, emit one `D <dep>` line per entry in authored order; (2) else if `load_from` is non-empty, emit `D <load_from>`; (3) else emit a bare `D` line. Generated `.stack` files are registered in `CompiledManifest.file_decisions` as `GENERATED` (reason `fi-literal`), skipped by the trimmer, and surfaced in the audit bundle exactly like generated `.tcl` files. The flag has no effect when `stages` is empty. Default is `false`.

Steps are stored and processed as **plain strings** — a step may be a Tcl filename, a raw `source` command, an ivar-based reference, or a conditional directive such as `#if` / `#else` / `#endif`. See R4 for the rationale.

Feature JSONs modify the base stage sequence via `flow_actions`. The full action vocabulary (`add_step_before`, `add_step_after`, `replace_step`, `remove_step`, `add_stage_before`, `add_stage_after`, `replace_stage`, `remove_stage`, `load_from`) is defined in §6.7.


Chopper ships F1/F2/F3 as first-class capabilities; domain owners choose which capabilities to use per domain/project. Users without stages still get F1 and F2 (file and proc trimming). Users with stages get generated `<stage>.tcl` run scripts for fine-grained step control.

### 3.7 Trim Workflow

The trim workflow supports both direct CLI mode and project JSON mode.

All examples below assume Chopper is invoked from the domain root. The current working directory is the operational domain root and `jsons/base.json` plus `jsons/features/*.feature.json` are resolved from there.

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
   { "$schema": "chopper/project/v1", "project": "...", "domain": "...", "base": "...", "features": [...] }

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

---

## 4. Architecture Rules

> **Vocabulary convention.** Treatment tokens appear in **kebab-case** in JSON payloads and on-disk artifacts (`full-copy`, `proc-trim`, `generated`, `remove`) and in **UPPER_SNAKE_CASE** in prose, tables, diagnostics, and diagrams (`FULL_COPY`, `PROC_TRIM`, `GENERATED`, `REMOVE`). The two forms are interchangeable; Chopper normalizes them on read.

### R1 — Conflict Resolution and File Treatment

This is the single authoritative rule for all include/exclude resolution and file-treatment derivation. R1 is **provenance-aware**: it treats the base JSON and each selected feature JSON as distinct contributing *sources*, not as a merged anonymous set.

#### Rule L1 — The Law of Explicit Include (cross-source)

> **L1.** If **any** selected source contributes an include signal for a file or a proc, that item survives. Include signals are:
>
> 1. `files.include` literal path (the source's FI_literal),
> 2. `files.include` glob pattern that matched the file, after the *same source's own* `files.exclude` pruning (the source's FI_glob_surviving),
> 3. `procedures.include` entry for the proc (the source's PI),
> 4. `procedures.exclude` entry on the file (the source's PE) — PE implies "keep the file," so it counts as a weak file-level include signal.
>
> An exclude signal from a different source can never remove an item that L1 keeps alive. Same-source exclude signals follow L2.

#### Rule L2 — Same-source authoring conveniences

> **L2.** Within a single JSON, these subtractive patterns are allowed and mean what they look like:
>
> 1. `files.exclude` prunes this source's own `files.include` glob expansions. Literal FI in the same source always survives.
> 2. `procedures.exclude` on a file where the same source also has `files.include` whole-file entry qualifies this source's contribution: this source contributes the file as `PROC_TRIM` with PE procs removed (not as `FULL_COPY`).
> 3. `procedures.exclude` on a file where the same source has no `files.include` for the file means this source contributes the file as `PROC_TRIM` with all procs except PE. This is itself an include signal under L1.
> 4. Same file has both PI and PE in the same source → PI wins, PE is ignored for that file (`VW-12`).
> 5. Same file has both FI (any form) and PI in the same source → PI is redundant (`VW-09`); the file's treatment is decided by whether the same source also has PE on it (L2.2).

#### Rule L3 — Cross-source additivity (base inviolable)

> **L3.** Across sources, contributions union. Concretely:
>
> 1. If **any** source's contribution treats file F as a full include with no same-source PE qualification (call this a `WHOLE` signal), F is `FULL_COPY` in the output. Any other source's PE or FE on F is vetoed and reported.
> 2. Otherwise, if any source contributes F at all (via PI or via same-source FI+PE or same-source PE-only), F is `PROC_TRIM`. Surviving procs are the union of every contributing source's per-source kept set. A PE from one source never removes a proc that another source includes.
> 3. If no source contributes F and F is not F3-`GENERATED`, F is `REMOVE`.
> 4. Consequence: a feature can never remove a file or proc that the base (or any other feature) contributed. The base is inviolable; features are additive.

#### Terminology

| Term | Meaning |
|---|---|
| **Source** | One JSON: the base, or any one selected feature. |
| **FI_literal(s)** | Literal file paths in source `s`'s `files.include` |
| **FI_glob(s)** | Files matched by wildcard patterns in source `s`'s `files.include` |
| **FI_glob_surviving(s)** | `FI_glob(s) − FE(s)` — within-source glob pruning |
| **FI(s)** | `FI_literal(s) ∪ FI_glob_surviving(s)` |
| **FE(s)** | `files.exclude` patterns in source `s` |
| **PI(s)** | `procedures.include` entries in source `s` |
| **PE(s)** | `procedures.exclude` entries in source `s` — implies file survival per L1/L2 |
| **Global FI** | `⋃ₛ FI(s)` — any file included by any source |
| **Global PI** | `⋃ₛ PI(s)` — any proc included by any source |
| **PI+** | Transitive trace expansion of Global PI — **reporting-only; no survival effect** |
| **PT** | Traced-only procs: PI+ − Global PI — **reporting-only** |

#### Per-source per-file contribution model

For each source `s` and each file `F` in the domain, classify `s`'s contribution to `F`:

| Inputs in source `s` for file `F` | `s`'s contribution to `F` | Note |
|---|---|---|
| Nothing | `NONE(s, F)` | — |
| Only FI (literal or surviving glob), no PE, no PI | `WHOLE(s, F)` | Source wants whole file. |
| Only PI entries, no FI, no PE | `TRIM(s, F, keep = PI(s, F))` | Additive per-proc include. |
| FI **and** PE (any combination of PI) | `TRIM(s, F, keep = all_procs(F) − PE(s, F))` | L2.2. Same-source PE qualifies same-source FI. If PI is also present, emit `VW-09` and ignore PI here (redundant with FI minus PE). |
| PE only, no FI | `TRIM(s, F, keep = all_procs(F) − PE(s, F))` | L2.3. Source wants file survival as PROC_TRIM. |
| FI **and** PI (no PE) | `WHOLE(s, F)` | L2.5. Emit `VW-09` (PI redundant on WHOLE). |
| Only FE (no FI, no PI, no PE) | `NONE(s, F)`, plus candidate veto if another source contributes `F` | See cross-source aggregation below. |
| FE **and** PE, no FI, no PI | `NONE(s, F)` (same-source contradiction) | Emit `VW-11`. Source contributes nothing for F. |

#### Cross-source aggregation (file treatment)

Let `Signals(F) = { c(s, F) : s ∈ sources, c(s, F) ≠ NONE }` and `FE_Sources(F) = { s : F ∈ FE(s) }`.

1. If **any** `c(s, F)` is `WHOLE(s, F)` → **treatment = `FULL_COPY`**, all procs survive.
   - For every `s' ≠ s` where `c(s', F) = TRIM(s', F, keep)` and `keep ⊊ all_procs(F)`: emit `VW-18` (the excluded procs from `s'` are vetoed by `s`'s WHOLE include).
   - For every `s'' ∈ FE_Sources(F)`: emit `VW-19` (FE from `s''` vetoed by WHOLE from `s`).
2. Else if every non-NONE signal is `TRIM` → **treatment = `PROC_TRIM`**, surviving procs = `⋃ₛ keep(s)` over every `TRIM(s, F, keep)`.
   - For every `s'' ∈ FE_Sources(F)`: emit `VW-19` (FE vetoed by another source's PROC_TRIM contribution).
   - For every `TRIM(s', F, keep)` where some proc `p ∈ all_procs(F) − keep(s', F)` appears in `keep(s)` for some `s ≠ s'`: emit `VW-18` (PE of `p` by `s'` vetoed by include from `s`).
3. Else (no signals on F) → if `F` is F3-`GENERATED`, treatment is `GENERATED`; otherwise **treatment = `REMOVE`**.

**Key invariants implied by the aggregation:**
- Any source's literal or glob-surviving FI forces `FULL_COPY`.
- Any source's explicit PI of a proc forces that proc to survive regardless of any PE from any other source.
- A feature's FE can only remove files that *no other source contributes*.
- Same-source subtractive authoring (base-internal "keep file minus X procs") is preserved and behaves exactly as before, provided no other source separately includes the file whole-file or PIs the removed procs.

#### Interaction warnings

These warnings are non-fatal (exit 0) and escalate to errors in `--strict`.

| Code | Slug | Scope | Condition |
|---|---|---|---|
| `VW-09` | `fi-pi-overlap` | Same-source | Source `s` has file `F` in FI and also has procs of `F` in PI (no PE in `s`). PI is redundant. |
| `VW-19` | `cross-source-fe-vetoed` | Cross-source | Source `s` has `F` in `files.exclude`, but `F` survives because another source `s' ≠ s` contributes `F` (via FI, PI, or PE). `s`'s FE entry is discarded. |
| `VW-11` | `fe-pe-same-source-conflict` | Same-source | Source `s` has `F` in both `files.exclude` and has PE entries for `F`, with no PI in `s`. Both are removal-within-`s` signals; `s` contributes nothing for `F`. |
| `VW-12` | `pi-pe-same-file` | Same-source | Source `s` has PI and PE entries for the same file `F`. PI wins; PE is ignored for `F` within `s`. |
| `VW-13` | `pe-removes-all-procs` | Same-source | A source's PE set covers every proc in `F` and no PI restores any. File survives as comment/blank-only. |
| `VW-18` | `cross-source-pe-vetoed` | Cross-source | Source `s'` has proc `p` in file `F` in PE, but `p` survives because another source `s ≠ s'` includes `F` whole-file or includes `p` via PI. `s'`'s PE entry for `p` is discarded. |

#### Per-file interaction matrix (single source)

Retained for authoring reference. Columns describe what **one** source contributes. Cross-source vetoes (`VW-19`, `VW-18`) are applied after per-source classification and do not appear in this table.

| # | FI | FE | PI | PE | Source's contribution | Surviving procs in source's contribution | Diagnostic |
|---|---|---|---|---|---|---|---|
| 1 | — | — | — | — | `NONE` | — | — |
| 2 | ✓ | — | — | — | `WHOLE` | all | — |
| 3 | — | ✓ | — | — | `NONE` (FE alone contributes nothing; see VW-19 at aggregation) | — | — |
| 4 | ✓ | ✓ | — | — | `WHOLE` (literal FI) or `NONE` (glob-only pruned by same-source FE) | all or — | — |
| 5 | — | — | ✓ | — | `TRIM(keep = PI)` | PI only | — |
| 6 | — | — | — | ✓ | `TRIM(keep = all − PE)` | all − PE | — |
| 7 | — | — | ✓ | ✓ | `TRIM(keep = PI)` (PE ignored) | PI only | `VW-12` |
| 8 | ✓ | — | ✓ | — | `WHOLE` (PI redundant) | all | `VW-09` |
| 9 | ✓ | — | — | ✓ | `TRIM(keep = all − PE)` | all − PE | — |
| 10 | ✓ | — | ✓ | ✓ | `TRIM(keep = all − PE)` (PI redundant with FI; PE qualifies it) | all − PE | `VW-09` |
| 11 | — | ✓ | ✓ | — | `TRIM(keep = PI)` (FE is moot — PI contributes F directly) | PI only | — |
| 12 | — | ✓ | — | ✓ | `NONE` (same-source FE+PE conflict) | — | `VW-11` |
| 13 | — | ✓ | ✓ | ✓ | `TRIM(keep = PI)` | PI only | `VW-12` |
| 14 | ✓ | ✓ | ✓ | — | `WHOLE` (literal FI beats same-source FE) or `NONE` (glob-only, pruned) | all or — | `VW-09` |
| 15 | ✓ | ✓ | — | ✓ | `TRIM(keep = all − PE)` (literal FI) or `NONE` (glob-only, pruned) | all − PE or — | — |
| 16 | ✓ | ✓ | ✓ | ✓ | `TRIM(keep = all − PE)` (literal FI) or `TRIM(keep = PI)` (glob-only) | all − PE / PI only | `VW-09` or `VW-12` |

**Reading the matrix under the additive model:**

- Row 9 (FI+PE, one source): that source contributes the file as `PROC_TRIM` minus PE procs. If another source has a `WHOLE` signal on the same file, L3.1 lifts treatment to `FULL_COPY` and row 9's PE is vetoed with `VW-18`.
- Row 11 (FE+PI, one source): the source contributes via PI; its own FE has no effect on its own PI contribution. If another source also FE's the same file, aggregation still keeps the file (PI wins).
- Rows 3 and 12 (FE alone, FE+PE): these contribute nothing from this source. If another source contributes the file, the file survives and this source's FE is surfaced as `VW-19`.

#### Feature safety statement

Selected features cannot remove anything that the base or another selected feature contributes. A feature's `files.exclude` and `procedures.exclude` only prune that feature's own include contributions. Every cross-source veto — FE against another source's include, or PE against another source's PI or whole-file include — is reported via `VW-19` or `VW-18` so the domain owner can see which feature authoring intent was discarded and why.

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

By default, owner-curated base and feature JSONs live under the current working directory, which is the domain root for normal operation, at `jsons/base.json` and `jsons/features/*.feature.json`. Project JSON has no fixed home and is always passed explicitly to `--project`.

`--project` is mutually exclusive with `--base` and `--features`. Providing both is `VE-11` (`conflicting-cli-options`, exit code 2).

Given the same current working directory, base JSON, and ordered feature list, project mode and direct CLI mode must produce identical compilation and trim results.

When `--project` is provided, Chopper assumes it is being run from the domain root. The current working directory is therefore the root for resolving `base` and `features`, not the project JSON file location. The resolved inputs then enter the same compilation pipeline as `--base`/`--features`. The `project`, `owner`, `release_branch`, and `notes` fields from the project JSON are recorded in audit artifacts.

When `--project` is provided, the project JSON `domain` field is a required identifier for audit and consistency. It must match the basename of the current working directory using a **case-insensitive** comparison: `Path.cwd().name.casefold() == project.domain.casefold()`. Full-path comparisons elsewhere in Chopper remain case-sensitive; only the domain-name field is case-folded because operators may author on Windows and run on Linux grid nodes. If `--domain` is also provided, it must resolve (case-insensitively) to that same current working directory. Any mismatch is reported as `VE-17 project-domain-mismatch` (or `VE-12` / `VE-13` for structural variants).

The detailed CLI reference with all arguments, flags, and per-subcommand usage is in [technical_docs/CLI_HELP_TEXT_REFERENCE.md](CLI_HELP_TEXT_REFERENCE.md).

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
```

### 5.2 Eight-Phase Pipeline

```
  P0  Detect trim state        first trim vs re-trim (backup detection)
   │
   ▼
  P1  Read & validate inputs   load base + feature JSONs; Phase 1 schema/structural checks
   │
   ▼
  P2  Parse domain Tcl         build proc index from all *.tcl in the domain
   │
   ▼
  P3  Compile selections       merge JSON rules → FI_literal, FI_glob, FE, PI, PE;
   │                           apply glob expansion; apply R1 conflict resolution;
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
- Schema-validate every loaded JSON against `json_kit/schemas/*.schema.json`.
- Run Phase 1 structural checks: file existence, glob well-formedness, `feature.domain` matches `base.domain`, `depends_on` prerequisites precede dependents in the project `features` order, etc.
- Emit `VE-*` on hard failures (non-zero exit); emit `VW-*` / `VI-*` on soft issues.
- Owner: `config/` + `validator/` (Phase 1 validation).
- Output: a frozen in-memory bundle of `(base_json, [feature_jsons], resolved_domain_path)` — no on-disk artifact.

#### P2 — Parse domain Tcl

- Walk `sorted(domain_path.rglob('*.tcl'))` so traversal order is lexicographic and deterministic.
- For each file, read text through the filesystem service and call `parse_file(file_path=path, text=text, on_diagnostic=...)`, which returns `list[ProcEntry]`.
- Each `ProcEntry` carries `canonical_name`, `short_name`, `qualified_name`, `namespace_path`, body and DPA/comment spans, and the two handoff fields `calls` (raw call tokens) and `source_refs` (literal `source` / `iproc_source` targets). See [TCL_PARSER_SPEC.md](TCL_PARSER_SPEC.md) §6 for the full field list.
- The parser **does not resolve** `calls` — those are textual tokens. Resolution is P4's job.
- Parser-family diagnostics (`PE-*` / `PW-*` / `PI-*`) flow through the `on_diagnostic` callback.
- Owner: `parser/`.
- Output: the **global proc index** — a dictionary keyed by `canonical_name` that concatenates every file's `ProcEntry` list in lex order. This single flat map is the source of truth for every later phase that needs to resolve a proc name. (See §5.4.1 for why a flat global index is required instead of per-file tables.)

#### P3 — Compile selections

- Consumes the JSON bundle from P1 and the proc index from P2.
- Treats the base JSON and each selected feature JSON as a distinct *source*, and applies the three-step provenance-aware algorithm from §5.3:
  1. Per-source partition: expand `files.include` into `FI_literal` + `FI_glob`, subtract `FE`, and compile `PI` / `PE`.
  2. Per-source per-file classification into `NONE` / `WHOLE` / `TRIM(keep_set)` under the same-source L2 rules (emits `VW-09`, `VW-11`, `VW-12`, `VW-13`).
  3. Cross-source aggregation under L1 + L3: any `WHOLE` wins (→ `FULL_COPY`); otherwise union of `TRIM` keep sets (→ `PROC_TRIM`); else `REMOVE` (or `GENERATED` for F3 outputs). Emits cross-source `VW-19` / `VW-18` for vetoed `FE` / `PE`.
- Record provenance on every manifest entry: `input_sources[]`, `treatment`, `surviving_procs[]`, `vetoed_entries[]`.
- Ordering: F1 and F2 aggregation is set-union and therefore order-independent; feature order is authoritative only in the F3 `flow_actions` pass and in P4's BFS.
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
  - `FULL_COPY` → copy the file verbatim from the backup into the rebuilt `domain/` tree.
  - `PROC_TRIM` → read the file from backup, delete the line spans of every proc not in `surviving_procs(F)`, rewrite directly into the rebuilt `domain/` tree.
  - `GENERATED` → run the F3 generator (`flow_actions` is authoritative for ordering here).
  - `REMOVE` → record the omission; do not write.
- Write `.chopper/trim_report.json` and `trim_report.txt` describing every file and proc operation and the diagnostics correlated with each.
- Owner: `trimmer/` + `generators/`.
- Output: the rebuilt `domain/` tree plus the trim-report artifacts. If P5 fails mid-run, the partially rebuilt `domain/` is left in place and the intact `<domain>_backup/` is the recovery source for the next invocation.

#### P6 — Post-trim validate

- Phase 2 validation runs against the rebuilt output (or, under `--dry-run`, against the synthetic trim plan):
  - under a live trim: brace balance across every rewritten file,
  - dangling proc references (every call target in a surviving file must resolve to a surviving proc or an accepted external such as a vendor/Tcl built-in),
  - missing `source` / `iproc_source` targets (must resolve to a surviving file or an accepted external).
- Emit `VE-*` / `VW-*`; `--strict` changes the final process exit code if any warning is present, but does **not** rewrite diagnostic severity.
- Owner: `validator/` (Phase 2).
- Output: updated diagnostics log; optionally aborts the run before P7.

#### P7 — Finalize and audit

- Under a normal run: leave the rebuilt `domain/` in place, preserve `<domain>_backup/` per the re-trim model, and emit the `.chopper/` bundle for the run.
- Under `--dry-run`: leave the domain untouched and emit only the report artifacts under `.chopper/`.
- Write the full audit bundle under `.chopper/`: `chopper_run.json`, `compiled_manifest.json`, `dependency_graph.json`, `trim_report.json`, `trim_report.txt`, `diagnostics.json`, `trim_stats.json`.
- Owner: `audit/`.
- Output: the audit trail (see §5.5).

### 5.3 Compilation Model (P3 Detail)

P3 is the deterministic core of the pipeline. It consumes the parsed JSON rules and the proc index from P2 and produces frozen sets that drive every subsequent phase. P3 is **provenance-aware**: the base JSON and each selected feature JSON are treated as distinct contributing *sources*, and every manifest entry records which sources contributed to it.

```
  Inputs from P1 + P2:
    base JSON + selected feature JSONs (each = one source s)
    proc index (all procs in domain, from P2)
                    │
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  1. For each source s (base + each feature):    │
  │     Partition files.include(s) →                │
  │       FI_literal(s)   (exact paths)             │
  │       FI_glob(s)      (wildcard matches)        │
  │     FI_glob_surviving(s) = FI_glob(s) − FE(s)   │
  │     FI(s) = FI_literal(s) ∪ FI_glob_surviving(s)│
  │     Compile FE(s), PI(s), PE(s)                 │
  └─────────────────────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  2. Per-source per-file contribution (L2):      │
  │     For each (s, F), classify c(s, F) as:       │
  │       NONE(s, F)                                │
  │       WHOLE(s, F)                               │
  │       TRIM(s, F, keep_set)                      │
  │     Apply same-source authoring rules:          │
  │       • FI + PI (no PE)      → WHOLE (VW-09)    │
  │       • FI + PE (any PI)     → TRIM(all − PE)   │
  │                                   (VW-09 if PI) │
  │       • PI only              → TRIM(keep = PI)  │
  │       • PE only              → TRIM(all − PE)   │
  │       • PI + PE (no FI)      → TRIM(PI), VW-12  │
  │       • FE + PE only         → NONE, VW-11      │
  │       • FE only              → NONE (candidate  │
  │                                  cross-source   │
  │                                  veto target)   │
  └─────────────────────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  3. Cross-source aggregation (L1 + L3):         │
  │     For each file F:                            │
  │       Signals(F) = {c(s, F) : c(s, F) ≠ NONE}   │
  │       FE_Sources(F) = {s : F ∈ FE(s)}           │
  │                                                 │
  │       if any c(s, F) = WHOLE:                   │
  │         treatment(F) = FULL_COPY                │
  │         surviving_procs(F) = all procs in F     │
  │         for s' in FE_Sources(F): emit VW-19     │
  │         for every TRIM(s', F, keep') where      │
  │             keep' ⊊ all_procs(F): emit VW-18    │
  │                                                 │
  │       elif every non-NONE signal is TRIM:       │
  │         treatment(F) = PROC_TRIM                │
  │         surviving_procs(F) = ⋃ keep(s')         │
  │                           over all TRIM(s',F,·) │
  │         for s' in FE_Sources(F): emit VW-19     │
  │         for each TRIM(s', F, keep') with some   │
  │             p ∈ all_procs(F) − keep' that is in │
  │             keep(s) for some s ≠ s':            │
  │             emit VW-18                          │
  │                                                 │
  │       else (Signals(F) empty):                  │
  │         if F is F3 generator output:            │
  │             treatment(F) = GENERATED            │
  │         else: treatment(F) = REMOVE             │
  │                                                 │
  │       input_sources(F) = sources whose          │
  │         contribution to F was non-NONE and      │
  │         not fully vetoed                        │
  └─────────────────────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  4. Emit same-source warnings VW-09, VW-11,     │
  │     VW-12, VW-13 from step 2; cross-source      │
  │     warnings VW-19, VW-18 from step 3.          │
  └─────────────────────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  5. Record provenance on every manifest entry:  │
  │     input_sources[]   (which JSONs contributed) │
  │     treatment         (FULL_COPY / PROC_TRIM /  │
  │                        GENERATED / REMOVE)      │
  │     surviving_procs[] (for PROC_TRIM only)      │
  │     vetoed_entries[]  (FE/PE discarded here)    │
  └─────────────────────────────────────────────────┘
                    │
                    ▼
            compiled_manifest.json
```

**Ordering:** F1 and F2 aggregation (steps 2–3) is set-union over sources and is **order-independent** — the same base and feature selections in any order produce the same surviving files and procs. Feature order is authoritative only in P3's F3 pass (`flow_actions` sequencing) and in P4's deterministic BFS traversal.

**Iteration order (emission determinism).** During P3 cross-source aggregation, the compiler iterates in this fixed order so every diagnostic (`VW-09`..`VW-13`, `VW-19`, `VW-18`, etc.) is emitted in a reproducible sequence:

1. **Sources:** `base` first; then each entry of `project.features[]` in the order given (or the CLI `--features` order when no project JSON is used). Topological sort of `depends_on` runs before P3; by the time L3 aggregation starts, the sequence is fixed.
2. **Files within a source:** lexicographic POSIX order (`sorted()` on the domain-relative path string).
3. **Procs within a file:** lexicographic order on `qualified_name`.
4. **Emission:** every per-file and cross-source warning is emitted in the traversal order above, at the point the conflict is first detected. Later traversal steps never reorder earlier emissions.

Golden tests in `tests/unit/compiler/` snapshot this ordering; any change to the iteration rule is a breaking change to the diagnostic sequence.

When `--project` is used, Chopper resolves the base and selected feature paths from the project JSON before entering P3. Equivalent resolved selections produce identical results regardless of input mode.

**Frozen output:** the compiled manifest is immutable after P3 completes. P4 (trace) reads it but does not modify the surviving sets.

### 5.3.1 Internal Compilation Contract

Detailed compilation data models, execution-freeze rules, and implementation contracts live alongside the core models in `src/chopper/core/models.py` and the compiler implementation in `src/chopper/compiler/`.

This architecture document defines what Chopper must do. How the implementation structures and preserves those contracts is split across three peer documents: [`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) (ports, services, stage layering), [`technical_docs/TCL_PARSER_SPEC.md`](TCL_PARSER_SPEC.md) (P2 engineering baseline), and [`technical_docs/IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) (stage gates, DoD, checkpoints).

### 5.4 Trace Phase (P4 Detail)

P4 runs the BFS trace expansion (R3) seeded by PI. Its outputs are:

| Output | Consumer | Survival effect |
|---|---|---|
| **PI+** (full transitive call set) | `dependency_graph.json`, trim report | **None** — reporting only |
| **PT** (PI+ − PI, traced-only procs) | Trim report, diagnostics | **None** — reporting only |
| **Call-tree edges** | `dependency_graph.json` | **None** — reporting only |
| **TW-\* diagnostics** | Diagnostics log, trim report | **None** — advisory warnings |

PI+ helps the domain owner understand what their explicit selections depend on. It never adds procs or files to the surviving set.

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
`parse_file(file_path=tcl_file, text=text, on_diagnostic=...)` returns a `list[ProcEntry]` for that single file. The public parser entry point that the runner actually calls is `ParserService.run(ctx, files)` (see [`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §9.2); `parse_file()` is the pure internal utility the service wraps, and the service owns filesystem reads through `ctx.fs`. Each entry carries its `canonical_name` (`relative/path.tcl::qualified_name`), its `namespace_path` captured from enclosing `namespace eval` blocks, the body span, and two unresolved handoff fields:

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

**Canonical-name test vectors.** The authoritative canonical-name derivation table (ten vectors covering file root, single/nested namespaces, absolute-name override, subdirectory files, and the computed-name skip case) lives in [`TCL_PARSER_SPEC.md`](TCL_PARSER_SPEC.md) §4.3.1. Implementations and tests reference that table; this bible keeps the format contract (`"<domain-relative-posix-path>::<qualified_name>"`) and the survival rules (this section, above) without duplicating the per-vector list.

**Step 2 — Assemble the global proc index (start of P4).**
The compiler concatenates every file's `ProcEntry` list into **one flat dictionary keyed by `canonical_name`**:

```python
proc_index: dict[str, ProcEntry] = {}
for tcl_file in sorted(domain_path.rglob("*.tcl")):
  text = fs.read_text(tcl_file)
  for entry in parse_file(file_path=tcl_file, text=text, on_diagnostic=sink):
        proc_index[entry.canonical_name] = entry
```

Files are walked in lexicographic order so the index is built the same way on every run and every host. This flat map is the single lookup table the tracer consults for the entire run.

> **Why a single global index, not per-file tables?** Tcl namespaces cross file boundaries. A proc defined in `a.tcl` inside `namespace eval ::foo { ... }` is callable from `b.tcl` as either `foo::proc_name` or (if the caller is in `::foo`) just `proc_name`. Only a single domain-wide index can resolve that correctly; per-file tables would force a second stitching pass that does the same work.

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
- The parser-to-tracer handoff is the contract enforced by the `ProcEntry.calls` / `source_refs` fields and their invariants in [TCL_PARSER_SPEC.md](TCL_PARSER_SPEC.md) §6.1. Violations of that contract are caught in parser unit tests, not in integration tests.

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
│   └── trim_stats.json              ← numbers: files before/after, procs before/after, SLOC delta
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
| `reason` | string | Why this treatment was chosen (e.g., `fi-literal`, `pi-additive`, `pe-subtractive`, `fe-glob-pruned`, `default-exclude`) |
| `input_sources` | string[] | Which inputs referenced this file, keyed by source (base or feature `name`). For features, the key is the feature's `name` field, not the filename (e.g., `["base:files.include", "dft:procedures.include"]`) |
| `surviving_procs` | string[] \| null | For `proc-trim` files: canonical names of procs that survive. Null for other treatments. |
| `excluded_procs` | string[] \| null | For `proc-trim` files using PE model: canonical names of procs removed. Null otherwise. |
| `proc_model` | string \| null | `additive` (PI), `subtractive` (PE), or null if not proc-trimmed |

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

All diagnostics emitted across all phases, with full context. This is the machine-readable equivalent of the diagnostics section in `trim_report.json`, but includes additional fields for tooling integration.

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
| `files_before` | integer | Total files in domain |
| `files_after` | integer | Surviving files |
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
| `trim_stats.json` | ✓ | ✓ | — | — |
| `internal-error.log` | ✓ (exit 3 only) | ✓ (exit 3 only) | ✓ (exit 3 only) | ✓ (exit 3 only) |

**`internal-error.log` contract.** This file is written **only on exit code 3** (programmer error / internal-consistency failure). It is produced by the CLI's exit-3 handler rather than `AuditService`, because the audit stage itself may have failed. Contents:

- `run_id` (ISO-8601 UTC, matches the rest of the audit bundle)
- Timestamp of the crash
- Full Python traceback of the originating exception
- Snapshot of the `DiagnosticSink` at the moment of failure (all diagnostics emitted before the crash)
- Active `RunConfig` fields (paths and flags, no secrets)
- `python_version`, `chopper_version`, and platform string

The CLI also records the existence and path of this log in `RunResult.internal_error` (see `json_kit/schemas/run-result-v1.schema.json`) so that GUI / CI consumers can surface the failure without reading the log directly. The log is plain text (not JSON) to remain readable even if the `core.serialization` layer itself is the source of the crash.

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
| **JSON** | `.json` extension | No comments in JSON; all non-blank lines count | Lines containing only whitespace |
| **Other/unknown** | No recognized extension | **Fallback:** count all non-blank lines as SLOC | Lines containing only whitespace |

**Rules:**

1. **Language detection is extension-based only.** No content sniffing. Unrecognized extensions use the fallback rule.
2. **Comment detection is line-level.** Chopper does not parse multi-line string literals or heredocs to distinguish "real comments" from comment characters inside strings. This is acceptable because the goal is a useful trim metric, not a research-grade SLOC tool.
3. **Backslash continuation lines** in Tcl are counted as separate source lines (consistent with parser line-counting).
4. **Shebang lines** (`#!/...` on line 1) count as source lines, not comments.
5. **SLOC is computed per file.** Domain totals are the sum of per-file SLOC values.
6. **Both metrics are always reported.** `sloc_*` for meaningful trim ratios; `raw_lines_*` for sanity-checking and auditors who want the unfiltered count.
7. **`trim_ratio_sloc`** is computed as `sloc_after / sloc_before`. This gives the most accurate picture of how much functional code was removed.

### 5.6 Output Expectations

Chopper output must be:
- Deterministic
- Reproducible from saved inputs
- Explainable through trace and trim reports
- Safe to review in code review

#### Determinism and write-safety

Determinism is a hard requirement (NFR-03): the same inputs must produce byte-identical output on every run. This is achieved through lex-sorted file discovery, lex-sorted BFS trace frontiers, stable JSON serialization, and a fixed phase sequence (no concurrency).

Write-safety does **not** use a staging tree or atomic promotion. Chopper writes directly to `<domain>/` during P5 and P5b; if a write fails mid-run, `<domain>_backup/` remains intact and the next invocation rebuilds from it (see §2.8 "Failure recovery"). Risks and recovery paths are tracked in [technical_docs/RISKS_AND_PITFALLS.md](RISKS_AND_PITFALLS.md).

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
| P6 Post-trim validate | Executes against the rewritten files in `<domain>/` | Executes against the resolved sets only (manifest-derivable checks); filesystem re-read checks are skipped |
| P7 Finalize & audit | Writes `.chopper/` artifacts | Writes `.chopper/` artifacts (reports only; no domain writes) |

**Dry-run P6 scope.** Because no file is rewritten in dry-run, brace-balance and other filesystem-dependent checks (`VE-16`, `VE-26`) cannot run. P6 under `--dry-run` runs only the manifest-derivable checks: `VW-05 dangling-proc-call`, `VW-06 source-file-removed`, `VW-14 step-file-missing`, `VW-15 step-proc-missing`, `VW-16 step-source-missing`, `VW-17 external-reference`. All other P6 behavior is unchanged.

Dry-run emits:
- `compiled_manifest.json` — file and proc treatment decisions
- `dependency_graph.json` — full call-tree edges (PI+ and TW-* diagnostics)
- `trim_report.json` + `trim_report.txt` — what would change and why
- Diagnostics log with all warnings/errors

### 5.8 Validation Model

Chopper has two validation phases that run within the pipeline:

| Phase | When | Service | Input | What it checks |
|---|---|---|---|---|
| **Phase 1** (within P1) | Pre-trim | `validate_pre(ctx, loaded)` | `LoadedConfig` + manifest draft | Schema, missing files/procs, empty procs arrays, invalid actions, path rules, `@n` targeting, depends-on resolution, cross-source veto detection |
| **Phase 2** (within P6) | Post-trim | `validate_post(ctx, manifest, graph, rewritten_paths)` | `CompiledManifest` + `DependencyGraph` + sequence of paths the trimmer actually rewrote | Re-tokenizes only the files listed in `rewritten_paths` to check brace balance (`VE-16` — internal-consistency assertion, exit 3); reads the P4 dependency graph to find surviving procs whose resolved calls or `source`/`iproc_source` edges point into trimmed-away targets (`VW-05`, `VW-06`); classifies F3 step tokens against the manifest for cross-validate (`VW-14`–`VW-17`) |

Phase 2 input contract: `rewritten_paths` contains only files the trimmer touched during P5 (copied-and-edited or newly generated). Files copied verbatim from `<domain>_backup/` are **not** re-tokenized — they were already validated at P2 and the trimmer did not change them.

**Cross-validate contract (`options.cross_validate`).** The F3 cross-validate checks (`VW-14`/`VW-15`/`VW-16`) are part of P6 (`validate_post`) and derive their answers from `CompiledManifest` — never from a filesystem re-scan. For each step string in every surviving stage, the validator classifies the token by syntax:

- **File-path literal** ending in `.tcl`/`.pl`/`.py`/`.csh` → look up `manifest.file_decisions`; emit `VW-14 step-file-missing` on miss.
- **Bare proc token** (no path separator, no extension) → look up `manifest.proc_decisions`; emit `VW-15 step-proc-missing` on miss.
- **`source <path>` / `iproc_source <path>` command** → look up `manifest.file_decisions`; emit `VW-16 step-source-missing` on miss.

Because the check is manifest-derivable, it runs **identically in dry-run and live modes**. When `options.cross_validate` is `false`, `VW-14`/`VW-15`/`VW-16` are suppressed entirely. The flag defaults to `true` because silently emitting a run-file that calls into trimmed-away content is a high-cost authoring failure.

**Performance note.** Cross-validate is O(stages × steps × manifest-size) in the worst case and adds measurable runtime on domains with large `flow_actions` surfaces. Authors who are confident in their selection (or who are iterating quickly on feature JSONs) may disable it with `"options": { "cross_validate": false }`. For any run that will be committed or handed off, cross-validate **must** be enabled — it is the only check that catches stage references to files or procs that the F1/F2 merge removed. `VW-17 external-reference` (advisory) is emitted regardless of `cross_validate` because it does not depend on manifest lookups.

**Diagnostic authority.** All severities, exit codes, recovery hints, and phase assignments for `VE-16`, `VW-05`, `VW-06`, `VW-08`, `VW-14`..`VW-17` are defined in [`technical_docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md). This section names codes only; it does not restate their metadata.

**`chopper validate` standalone command.**

- **Default behavior (JSON-only):** When invoked without access to the domain source tree, `chopper validate` runs Phase 1 structural checks only — schema validation, path rules, empty-procs detection, depends-on resolution, and every other check that does not require reading `.tcl` files. Filesystem-existence checks (`VE-06`, `VE-07`) and parser-time checks (`PE-*`) are **skipped** in this mode.
- **Full mode (with domain):** When invoked from inside the domain directory (so that `Path.cwd().name.casefold() == project.domain.casefold()` per §5.1) or with an explicit `--domain .` argument, `chopper validate` additionally runs the parser (`PE-*`) and the filesystem-existence checks (`VE-06`, `VE-07`). This is the pre-flight mode used before `chopper trim`.

The detailed validation check matrix, diagnostics contract, and exit semantics are defined in [technical_docs/DIAGNOSTIC_CODES.md](DIAGNOSTIC_CODES.md).

### 5.9 CLI Contract, Diagnostics, and Exit Semantics

Chopper exposes the `validate`, `trim`, and `cleanup` subcommands as first-class user interfaces.

Chopper supports three input modes: base-only (`--base`), base-plus-features (`--base --features`), and project JSON (`--project`). Project JSON mode packages the same selection decisions into a single auditable file without changing trim semantics. `--project` is mutually exclusive with `--base`/`--features`.

The complete CLI reference — including all subcommands, arguments, flags, per-mode examples, and the project JSON workflow — is defined in [technical_docs/CLI_HELP_TEXT_REFERENCE.md](CLI_HELP_TEXT_REFERENCE.md).

Detailed CLI behavior, diagnostics fields, exit codes, presentation constraints, and usability requirements are defined in [technical_docs/CLI_HELP_TEXT_REFERENCE.md](CLI_HELP_TEXT_REFERENCE.md) and [technical_docs/DIAGNOSTIC_CODES.md](DIAGNOSTIC_CODES.md).

### 5.10 Python Implementation Guidance

Chopper's Python coding standards live in §5.12 below. GUI-readiness and the wire protocol live in §5.11. [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md) provides a short summary that points back to these sections; the bible is authoritative.

### 5.11 GUI Readiness and Wire Protocol

Chopper is CLI-only. However, the architecture **must** enable a future GUI without rewriting the engine. This section defines the provisions that the current implementation must satisfy so that GUI-based file selection, proc selection, trim statistics, JSON viewing, dependency-graph visualization, and diagnostic browsing can be layered on top later.

#### 5.11.1 Architectural Requirements for GUI Enablement

The following rules are **non-negotiable** even though no GUI ships:

1. **Typed pipeline results.** The runner returns a frozen `RunResult`; individual phases exchange frozen dataclasses such as `ParseResult`, `CompiledManifest`, `DependencyGraph`, and `TrimReport`. No phase returns pre-rendered strings.
2. **Structured progress events.** Progress flows through `ProgressSink` with explicit phase and step notifications. The CLI renders them today; a GUI can render the same events later.
3. **Structured diagnostics.** Every diagnostic is a `Diagnostic` record with severity, code, message, location, and hint. No ad-hoc `print()` or unstructured error messages in library code.
4. **Deterministic serialization.** Core models are serializable through `dump_model()` in `src/chopper/core/serialization.py`, which is already the source for audit artifacts. A future GUI can consume the same shapes without changing the engine.
5. **No presentation in core logic.** The compiler, parser, trimmer, validator, and audit writer never import terminal-rendering libraries or format user-facing output.
6. **CLI rendering stays thin.** Human output lives in `cli/render.py`; engine code stays presentation-agnostic.
7. **Machine output is deferred, not promised.** Chopper does not freeze a `--json` CLI mode or a GUI wire protocol here. If structured stdout/stderr is needed later, it enters through [`FD-10`](FUTURE_PLANNED_DEVELOPMENTS.md#fd-10-machine-readable-cli-output), not via an undocumented side channel.

#### 5.11.2 Service Layer Contract

The engine boundary between presentation (CLI today, GUI later) and domain logic is defined in [`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6 (`ChopperContext`, `RunConfig`, `PresentationConfig`, `ChopperRunner.run()`) and §9.2 (per-phase signatures: `DomainStateService`, `ConfigService`, `validate_pre`, `ParserService`, `CompilerService`, `TracerService`, `TrimmerService`, `GeneratorService`, `validate_post`, `AuditService`).

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
2. **Structured CLI transport** added later through [`FD-10`](FUTURE_PLANNED_DEVELOPMENTS.md#fd-10-machine-readable-cli-output) once the pipeline and artifact shapes have proven stable.

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
| `FileSystemPort` | `read_text`, `write_text`, `exists`, `rename`, `remove`, `mkdir`, `copy_tree`, ... | Lets tests and future frontends drive the engine without assuming a real on-disk tree in every scenario |
| `ProgressSink` | `phase_started()`, `phase_done()`, `step()` | Progress panels, spinners, CI silence, or future GUI status widgets |
| `DiagnosticSink` | `emit()`, `snapshot()`, `finalize()` | Diagnostic collection and presentation-independent reporting |

Rendering itself is **not** a protocol here. The CLI renders directly in `cli/render.py`; a future GUI will render from typed data without requiring a `TableRenderer` abstraction.

#### 5.11.7 What v1 Must NOT Do

- Must NOT embed terminal-specific formatting (ANSI codes, Rich markup) in any module outside `src/chopper/cli/`.
- Must NOT return pre-formatted strings from runner or phase functions.
- Must NOT use `print()` in library code (`src/chopper/compiler/`, `src/chopper/parser/`, `src/chopper/trimmer/`, `src/chopper/validator/`, `src/chopper/core/`).
- Must NOT require a TTY for correct operation — headless and piped invocations must work.
- Must NOT couple diagnostic emission to console rendering — diagnostics are data, not output.

### 5.12 Python Coding Standards

Chopper is a Python ≥ 3.13 CLI. The rules below are authoritative for every file under `src/chopper/`. They consolidate what was previously scattered between the instructions file and the architecture plan; the instructions file now carries a brief summary that defers here.

> **Python version policy.** v1 targets **Python 3.13 or newer only**. Older Pythons (3.9–3.12) are unsupported — supporting them would require backporting type-syntax workarounds (PEP 585 / PEP 604) and duplicating CI matrices for no user benefit, since the deployment environment ships 3.13+. The `pyproject.toml` `requires-python = ">=3.13"` pin and the `mypy`/`ruff` targets enforce this. If a future release needs to widen the matrix it does so explicitly through an FD entry, not by accident.

#### 5.12.1 Module Layout and Boundaries

- The repository layout is defined in [`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §3. Every source module lives under `src/chopper/`. No sibling-module imports across service packages — services depend only on `core/` and their own submodules. Cross-cutting data lives in `core/models.py`; cross-cutting protocols live in `core/protocols.py`.
- Ports-and-adapters: the only engine ports are `FileSystemPort`, `DiagnosticSink`, and `ProgressSink` in `core/protocols.py`. Concrete adapters live in `adapters/`. Services receive them via `ChopperContext`. Clock access, serialization, audit writing, and rendering are direct helpers or CLI-local concerns, not additional ports.
- Services never construct adapters; the CLI does that at startup (see [`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6.1).

#### 5.12.2 Path Handling

- **Always** use `pathlib.Path`. Never use `os.path` string manipulation.
- Always normalize to forward slashes on serialization (POSIX form). On Windows, `Path.as_posix()` is used before any path enters JSON output.
- Path comparisons that cross OS boundaries (e.g., project JSON `domain` field matched against cwd basename) use `casefold()` (§5.1). Every other path comparison is case-sensitive.
- Forbidden in user input: `..` traversal, absolute paths, drive letters. Validated at the schema boundary (§6.3.1).
- `Path.resolve()` is used once at CLI entry to normalize the domain root; downstream services use the resolved absolute path.

#### 5.12.3 Type Annotations

- Every public function and method has full type annotations.
- Every `core/models.py` class is a frozen `@dataclass(frozen=True)`. Immutability is a hard rule — services cannot mutate each other's outputs.
- Enums use `enum.Enum` (string-valued for JSON serializability) or `enum.IntEnum` where numeric comparison is meaningful (e.g., `Phase`).
- `typing.Protocol` (PEP 544) is preferred over `abc.ABC` for ports. Duck typing with static verification.
- `from __future__ import annotations` at the top of every module; forward references resolved lazily.
- `mypy` in strict mode for `core/`; non-strict (but no-`Any`) for the rest.

#### 5.12.4 Logging and Diagnostics

- **No `print()` in library code.** Any module under `src/chopper/{parser,compiler,trimmer,validator,core,config,audit,generators}` that calls `print()` is a review-blocking defect. The CLI and test harnesses may print.
- All user-facing outcomes go through `ctx.diag.emit(Diagnostic(...))` (§5.11.1). Every code is registered in [`technical_docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md).
- **There is no internal structured-logging channel.** Chopper has exactly two output surfaces for the operator: the `DiagnosticSink` (user-facing outcomes) and the `ProgressSink` (phase transitions and progress events). Library modules do not carry a logger handle and do not emit `log.info` / `log.debug` events. Every observation worth surfacing to a user is a diagnostic; every observation worth surfacing to downstream tooling is an audit artifact. Crash traces for programmer errors are written to `.chopper/internal-error.log` by the runner's final `except` block (§8.3, exit code 3).

#### 5.12.5 Errors and Exceptions

- User-visible conditions are **diagnostics**, not exceptions. Services never raise `ValueError` / `FileNotFoundError` to signal bad input.
- `ChopperError` (in `core/errors.py`) is the base for programmer-error exceptions. Subclasses: `UnknownDiagnosticCodeError` (registry mismatch at `Diagnostic` construction), `ProgrammerError` (internal-consistency assertions).
- An unhandled exception that escapes a service is an exit-code-3 programmer error; the runner catches it in `finally` (see [`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6.2), writes a stack trace to `.chopper/internal-error.log`, and exits 3. `--debug` additionally re-raises so the trace hits stderr.

#### 5.12.6 Style and Formatting

- Ruff is the only linter + formatter (replaces flake8, isort, black).
- Line length: 120.
- `snake_case` for functions and variables, `CamelCase` for classes, `UPPER_CASE` for constants.
- 4-space indentation. No tabs.
- Imports grouped: stdlib, third-party, first-party (`chopper.*`), relative. Ruff enforces.
- Docstrings: Google style, required on every public function / class / method. Omitted on private helpers unless non-obvious.

#### 5.12.7 Configuration Policy

- No configuration files under the user's home directory, no `$CHOPPER_*` environment variables (except for CI overrides documented explicitly). All configuration enters via CLI flags, base/feature/project JSONs, and `.chopper/` audit artifacts.
- `RunConfig` ([`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6.1) is the single source of engine-behavior configuration; `PresentationConfig` is the single source of CLI-UX configuration. Neither is mutable after construction.

#### 5.12.8 Testing Standards

Coverage gates, fixture conventions, and the integration-test harness are defined in [`tests/TESTING_STRATEGY.md`](../tests/TESTING_STRATEGY.md). Parser fixture catalog is in [`tests/FIXTURE_CATALOG.md`](../tests/FIXTURE_CATALOG.md). Minimum line coverage is 78% overall; parser 85%, compiler 80%, trimmer 80%, config 85%, core 80%.

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
{ "$schema": "chopper/base/v1", ... }
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

> Schema: `json_kit/schemas/base-v1.schema.json`
> Progressive examples: `json_kit/examples/01_base_files_only/` through `07_base_full/`

```json
{
  "$schema": "chopper/base/v1",
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

For users who define stages, the optional mapping to stack files is direct: `name` -> `N`, `command` -> `J`, `exit_codes` -> `L`, `dependencies` -> `D`, `inputs` -> `I`, `outputs` -> `O`, and `run_mode` -> `R`. By default Chopper emits only the generated `<stage>.tcl` scripts; set `options.generate_stack: true` to additionally auto-generate `<stage>.stack` files from this mapping (see §3.6), or apply the mapping by hand when maintaining an external stack file.

**Validation rule:** an entry in `procedures.include` or `procedures.exclude` with an empty `procs` array (`"procs": []`) is a **hard error (`VE-03`)**. For include: if the author intended to keep the whole file, the correct action is to move the file into `files.include`. For exclude: if there's nothing to exclude, omit the entry entirely. Chopper rejects empty procs arrays during validation and dry-run, with an actionable error message.

### 6.5 Feature JSON Structure

> Schema: `json_kit/schemas/feature-v1.schema.json`
> Examples: `json_kit/examples/08_base_plus_one_feature/`, `09_base_plus_multiple_features/`, `10_chained_features_depends_on/`

```json
{
  "$schema": "chopper/feature/v1",
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

> Schema: `json_kit/schemas/project-v1.schema.json`
> Examples: `json_kit/examples/08_base_plus_one_feature/project.json`, `11_project_base_only/`

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
  "$schema": "chopper/project/v1",
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
| `$schema` | string | Must be `"chopper/project/v1"` |
| `project` | string | Project identifier (e.g., `PROJECT_ABC`) |
| `domain` | string | Domain identifier. It must match the basename of the current working directory, which is the operational domain root. |
| `base` | string | Path to the base JSON file (resolved relative to the current working directory / domain root). Default expected location: `jsons/base.json`. |

**Optional fields:**

| Field | Type | Description |
|---|---|---|
| `owner` | string | Domain deployment owner for this project |
| `release_branch` | string | Git branch name for this project trim |
| `features` | array of strings | List of feature JSON paths (resolved relative to the current working directory / domain root). Default expected location pattern: `jsons/features/*.feature.json`. Order is authoritative for F3 `flow_actions` sequencing only; F1/F2 merges are order-independent. |
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
| FR-08 | Apply additive include/exclude semantics across sources (base + features): explicit include from any source always wins; a source's excludes prune only that source's own include contributions. |
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
| FR-31 | Apply feature order deterministically and apply `flow_actions` top-to-bottom within each feature. |
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
- **Out-of-v1 roadmap.** Planned but non-v1 capabilities are tracked in [technical_docs/FUTURE_PLANNED_DEVELOPMENTS.md](FUTURE_PLANNED_DEVELOPMENTS.md). Nothing in this document commits v1 to those items.

### 8.5 Cross-Cutting References

- Parser engineering baseline: [technical_docs/TCL_PARSER_SPEC.md](TCL_PARSER_SPEC.md).
- Diagnostic code registry: [technical_docs/DIAGNOSTIC_CODES.md](DIAGNOSTIC_CODES.md).
- Risk and pitfall ledger: [technical_docs/RISKS_AND_PITFALLS.md](RISKS_AND_PITFALLS.md).
- CLI surface: [technical_docs/CLI_HELP_TEXT_REFERENCE.md](CLI_HELP_TEXT_REFERENCE.md).
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

> Merged into [`technical_docs/RISKS_AND_PITFALLS.md`](../technical_docs/RISKS_AND_PITFALLS.md).
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
| Q13 | What does "override" mean in Chopper? | **Resolved** | There is no override in F1/F2 — features are purely additive and include-wins is the sole conflict rule. "Override"-style behavior exists only in F3 via `replace_step` and `replace_stage` action keywords. Proc-level control uses `procedures.include` / `procedures.exclude` with tracing. |
| Q14 | Are backups deleted? | **Resolved** | Yes, on the last day during cleanup. |
| Q15 | Is scan a Chopper subcommand? | **Resolved** | No. Scan mode has been removed. Chopper does not generate draft JSONs. Domain owners author JSONs manually; `--dry-run` is the authoring iteration feedback loop. |
| Q16 | Is default action configurable? | **Resolved** | No. Default exclude is fixed. |
| Q17 | Is product implemented already? | **Resolved** | No. It is currently framework/scaffold plus architecture work. |
| Q18 | How is live trim made write-safe? | **Resolved** | Backup-and-rebuild. Chopper writes directly into `domain/`, keeps `<domain>_backup/` intact, and recovers by re-running from backup rather than staging or locking. |
| Q19 | How is feature ordering interpreted? | **Resolved** | Feature order is authoritative for F3 `flow_actions` sequencing only (earlier features' stage/step insertions are visible to later features). F1 and F2 merges (files and procedures) are purely additive and order-independent. Within a feature, `flow_actions` apply top-to-bottom. |
| Q20 | How are warnings and errors represented? | **Resolved** | Stable machine-readable diagnostics with severity, code, location, and hint. |

### 10.2 Open Questions

| ID | Question | Status |
|---|---|---|
| OQ-01 | For `.stack` files, which domains generate them and which domains keep them as-is? | **Resolved** — per-domain, author-controlled via `options.generate_stack` in the base JSON. Default `false` (Chopper does not touch stack files). Setting it to `true` causes F3 to emit `<stage>.stack` alongside `<stage>.tcl` using the derivation rules in §3.6. |
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
If one includes it and another excludes it, the proc survives.

**Q: What if two features replace the same step differently?**  
Selected input ordering governs explicit `replace_step` and `replace_stage` conflicts.

**Q: What if a file ends up with no procs left after trimming?**  
The file is kept. If only blank lines and comments remain after proc deletion, Chopper writes that remaining stub, emits `VW-08`, and leaves owner review in the workflow. If the same file was also explicitly requested in `files.include`, the full-file copy rule still applies and the file survives as a whole file.

**Q: What if a hook file exists but is not needed?**  
Hook discovery is not permission for silent bloat. Hook files stay out unless they are explicitly included in selected JSON.

**Q: What if a feature excludes a base item?**  
It does not win. The selected base still includes it, so the item survives.

**Q: What if feature A includes a file and feature B excludes it?**  
The file survives. Explicit include from any source wins over exclude from any other source. Feature B's `files.exclude` entry is surfaced as `VW-19 cross-source-fe-vetoed` so the authoring conflict is visible in the audit trail.

**Q: What if the base includes a whole file and a feature excludes a proc inside it via `procedures.exclude`?**  
The file survives as `FULL_COPY`, including the proc the feature tried to exclude. The feature's PE entry is surfaced as `VW-18 cross-source-pe-vetoed`. Features cannot strip procs from a file that the base contributed whole.

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
| [technical_docs/CLI_HELP_TEXT_REFERENCE.md](CLI_HELP_TEXT_REFERENCE.md) | Complete CLI subcommand reference: `validate`, `trim`, `cleanup`, flags, examples |
| [technical_docs/TCL_PARSER_SPEC.md](TCL_PARSER_SPEC.md) | Tcl parser engineering baseline: tokenizer, namespace resolution, edge cases |
| [technical_docs/RISKS_AND_PITFALLS.md](RISKS_AND_PITFALLS.md) | Technical risks (TC-01–TC-10) and implementation pitfalls (P-01–P-36) |
| [technical_docs/chopper_description.md](chopper_description.md) §5.11 | GUI-readiness surface: typed results, deterministic serialization, service-layer discipline |
| [technical_docs/FUTURE_PLANNED_DEVELOPMENTS.md](FUTURE_PLANNED_DEVELOPMENTS.md) | Roadmap items explicitly out of v1 scope |
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

This log records the conscious design decisions that shaped the current document. Each row captures *what changed* and *why*, so later readers understand which alternatives were evaluated and rejected, not only what the final spec says.

| Date | Change |
|---|---|
| 2024-06-01 | Initial draft. |
 | 2026-04 | Consolidated review pass: removed `common/` infrastructure references; removed `template_script` execution contract (schema field retained for forward compatibility, not executed at that point); replaced archived forward-references with links to the live `technical_docs/*.md`; promoted Trim Workflow to §3.7; added Rule L1 (The Law of Explicit Include) and the treatment-token vocabulary to §4; added backup edge-case matrix to §2.8 with `VE-23` and `VI-03`; added GUI-readiness sections §8.3–8.5; added FR-38–FR-41 (service layer, JSON serialization, ProgressSink, diagnostic stability); rewrote FR-23 to name concrete audit artifacts; registered `VE-19`–`VE-23`, `VW-14`–`VW-17`, `VI-03`, `PE-03` in the diagnostic registry. |
| 2026-04-19 | Locked in purely additive feature semantics. R1 rewritten around provenance-aware cross-source aggregation with rules L1 (explicit include wins cross-source), L2 (same-source authoring conveniences), L3 (base inviolable, features additive-only). P3 algorithm in §5.3 rewritten to classify per-source contributions (WHOLE / TRIM / NONE) and then aggregate across sources with full provenance recorded on every manifest entry. Feature ordering scoped to F3 `flow_actions` sequencing only; F1/F2 merges declared order-independent. FR-08 rewritten. Q13 and Q19 updated. New §11.6 FAQ entries for cross-source include/exclude disagreements. Diagnostic registry: `VW-10` un-retired and re-assigned to `cross-source-fe-vetoed`; `VW-11` scoped to same-source as `fe-pe-same-source-conflict`; new `VW-18 cross-source-pe-vetoed` added; VW active count 15 → 17. Project-v1 schema `features` description rewritten to reflect additive-only semantics and F3-only ordering authority. |
 | 2026-04-19 | Public-surface cleanup to eliminate schema/doc contradictions. Removed `_draft` field entirely from `json_kit/schemas/base-v1.schema.json` and `json_kit/docs/JSON_AUTHORING_GUIDE.md`: scan mode and draft-JSON generation were considered and explicitly rejected (see OOS-04) — domain owners author JSONs manually and `--dry-run` is the authoring feedback loop. Rewrote `options.template_script` schema description to state the field is reserved at that point and not executed; narrowed `VE-18 template-script-path-escapes` to Phase 1 static path validation (symlink/containment only). Updated RISKS_AND_PITFALLS.md TC-09 to match. Corrected stale non-registry diagnostic codes in schemas and authoring guide: feature-v1 `V-19` → `VW-04 feature-domain-mismatch`; authoring-guide `V-19 family` → `VE-15`/`VE-16`. |
| 2026-04-19 | Scan-mode artifact purge across the live surface. Rewrote `tests/TESTING_STRATEGY.md` Scenario 14 to cite registered `TW-04 cycle-in-call-graph` instead of a fictional code, and Scenario 21 to assert the dry-run artifact set (`compiled_manifest.json`, `dependency_graph.json`, `trim_report.json`, `trim_report.txt`) rather than the removed `diff_report.json`. Extended the scenario table with six additive-model scenarios (23–28) covering cross-source FE/PE vetoes (`VW-10`, `VW-18`), same-source FE/PE conflict (`VW-11`), F3 `flow_actions` ordering authority, F1/F2 merge order-independence, and per-entry provenance in the compiled manifest. Replaced remaining ad-hoc parser diagnostic code strings with authoritative registry codes across `tests/FIXTURE_CATALOG.md`, `technical_docs/SNORT_ANALYSIS_AND_CHOPPER_COMPARISON.md`, and `tests/fixtures/tracing_domain/dynamic.tcl`. OOS-04 in §2.1 and Q15 in §11 remain as the definitional statements of record for the scan-mode rejection. |
| 2026-04-20 | Propagated the "trace is reporting-only" contract so the PI+/PT semantics are unmistakable at every authoring and implementation surface. Added a concrete worked example to §5.4 showing `foo` (listed in `procedures.include`) is copied while `bar` (reached only via trace) appears in `dependency_graph.json` and `trim_report.json` but is not copied. Promoted Scenario 14 in `tests/TESTING_STRATEGY.md` from a "no diagnostic" assertion to a real `TW-04 cycle-in-call-graph` assertion that also pins the no-auto-copy rule. Rewrote `technical_docs/RISKS_AND_PITFALLS.md` Pitfall P-09 to strike the stale "`procedures.exclude` filters trace-derived proc candidates" mental model — under the additive L1/L2/L3 model, trace never adds survivors and PE is a same-source proc-trimming instruction governed by VW-09/VW-10/VW-11/VW-12/VW-18. Added Critical Principle #7 ("Trace Is Reporting-Only (Never Copies)") to `AGENTS.md`. Added a pull-quote callout to `json_kit/docs/JSON_AUTHORING_GUIDE.md` merge-semantics section. No diagnostic-registry changes were required. |
| 2026-04-20 | Docs-hygiene pass. Reframed implementation timeline in terms of stage boundaries tied to module dependency order (Stage 0 `core/` → Stage 1 `parser/` → Stage 2 `compiler/` → Stage 3 `trimmer/` → Stage 4 `validator/` → Stage 5 `cli/`) across `AGENTS.md`, `tests/TESTING_STRATEGY.md`, `tests/FIXTURE_CATALOG.md`, `tests/GOLDEN_FILE_GUIDE.md`, `tests/fixtures/gen_large_domain.py`, and `tests/integration/crash_harness.py`, replacing the previous Day/Sprint/Week labels which implied calendar time. Removed `Status: Draft` / `Author:` / `Last Updated:` banners from the live spec set (the revision history is the living record of authorship and currency). Folded `TCL_PARSER_SPEC.md` §11 "Addendum A" into the main body: A.1 (PE-01 timing and error-message format) became new §6.3 so the timing rule sits next to the §6.1 invariants it enforces, and A.2 (namespace-resolution cross-reference) was dropped as redundant with §5.3.1. The general rule against Addendum sections in specs is recorded as a **Documentation Convention** in `AGENTS.md` (with rationale) so it is discoverable to future authors rather than buried in this log. |
| 2026-04-20 | Consolidated `AGENTS.md` into `.github/instructions/project.instructions.md` and deleted the root `AGENTS.md`. The split between an "agent instructions" file (`AGENTS.md`) and a "project conventions" file (`.github/instructions/project.instructions.md`) had become a distinction without a difference — both held the same category of guardrail (architecture, critical principles, code style, testing standards, module guidance, diagnostic-code rules). Keeping two files meant rules drifted and contributors had to hunt. The consolidated file is the single entry point applied to every file (`applyTo: '**'`) so Copilot and humans read the same source. Updated live pointers in `README.md` and `technical_docs/chopper_description.md` (§9.x, §11.x cross-reference table). Revision-history mentions of `AGENTS.md` in this log and in `TCL_PARSER_SPEC.md` are kept as historical references; only the active pointer in TCL_PARSER_SPEC Rev 11 was retargeted. |
| 2026-04-20 | Embedded two narrative walkthroughs into §5 so the pipeline contract is understandable without cross-referencing code or test fixtures. Added §5.2.1 "End-to-End Walkthrough" expanding the compact P0–P7 ASCII diagram into the concrete data flow each phase consumes, produces, and hands off (run context → proc index → compiled manifest → dependency graph → staging → audit bundle). Added §5.4.1 "Per-File Parsing to Global Call Tree" making the parser-to-tracer handoff explicit: per-file `parse_file()` returns `list[ProcEntry]` with unresolved `calls` / `source_refs`; the compiler concatenates them into one flat global `dict[canonical_name, ProcEntry]` walked in lexicographic order; P4 BFS resolves call tokens against that index under the deterministic namespace contract, emitting `TW-01`/`TW-02`/`TW-03`/`TW-04` as warranted. No normative behavior changed — this is documentation of already-contracted semantics that were previously only discoverable by reading §5.4 step-by-step plus the §6 proc-index contract. A dedicated `technical_docs/TECHNICAL_IMPLEMENTATION.md` covering service wiring, global data stores, and diagnostic routing will be authored as a separate peer document; §5.3.1 now links to it by name. |
| 2026-04-21 | Re-synchronised chopper docs with `json_kit/` 1.0.2, which standardised feature JSON filenames to `<feature_name>.feature.json` and moved example instances under `jsons/` subdirectories. Updated every `json_kit/examples/*` citation in `chopper_description.md` (§3.1 base minimal/full examples, §3.2 feature example, §3.3 project example) to reference the `jsons/base.json` and `jsons/features/<name>.feature.json` layout. Replaced stale `feature_<name>.json` tokens in §5.1.1 CLI invocation examples, §5.5 audit-artifact tree (`input_features/01_dft.feature.json`, `02_power.feature.json`), the `chopper_run.json` example (`feature_jsons`), the `compiled_manifest.json` `input_sources` row (keyed by feature `name`, not filename), and the §6.6 extended project example (`scan_common.feature.json`, `dft.feature.json`, `power.feature.json`). Expanded §2.5 per-domain tree to show the `<feature>.feature.json` filename convention directly. No schema fields, diagnostic codes, or merge/trace semantics changed — this was a naming- and path-only alignment pass triggered by the json_kit release, cascading the new convention into every subordinate chopper doc reference. |
| 2026-04-21 | Day-0 handoff-readiness cleanup driven by `technical_docs/DAY0_REVIEW.md` decisions. **Diagnostic registry renumbered for compactness** (F1): `DIAGNOSTIC_CODES.md` rewritten to remove all "retired" slots, since Chopper is still in ideation and no code has ever shipped. `VE-17 brace-error-post-trim` → `VE-16`; `VE-19 project-domain-mismatch` → `VE-17`; `VE-20 duplicate-feature-entry` → `VE-18`; `VE-21 occurrence-suffix-zero` → `VE-19`; `VE-22 ambiguous-step-target` → `VE-20`; `VE-23 no-domain-or-backup` → `VE-21`; `VE-25 feature-depends-on-cycle` → `VE-22`; `VE-26 filesystem-error-during-trim` → `VE-23`; `VE-27 backup-contents-missing` → `VE-24`; `VE-28 domain-write-failed` → `VE-25`; `VE-29 proc-atomic-drop-failed` → `VE-26`. Dropped `VE-16` (old `depends-on-out-of-order`), `VE-18` (old `template-script-path-escapes`), `VE-24` (old concurrent-invocation), `VI-03` (old `domain-hand-edited`), `VI-04`, and `VI-05` entirely — no active codes have historical usage to preserve. **Scope cuts applied** (G1, G2, G3): `options.template_script` field and its diagnostic removed from `json_kit/schemas/base-v1.schema.json`, `JSON_AUTHORING_GUIDE.md`, and `RISKS_AND_PITFALLS.md` TC-09 — a reserved seam with a registered diagnostic is a scope-lock violation (filed as `FD-12` in `FUTURE_PLANNED_DEVELOPMENTS.md`). `options.cross_validate` rewritten from "Cross-validate F3 output against F1/F2" to a behavioural definition (emits `VW-14`/`VW-15`/`VW-16` warnings, never errors). Hand-edit-detection code `VI-03` killed per G3(c): replaced with a fixed CLI pre-flight warning printed every re-trim; bible §2.8 Case 2, `ARCHITECTURE_PLAN.md` §12 scenarios 16–17 and §16 Q2, and `DIAGNOSTIC_CODES.md` §3 all updated. **Doc-structure cleanup**: §5.3.1 stopped forward-referencing the never-authored `technical_docs/TECHNICAL_IMPLEMENTATION.md` and instead cites the three live peer documents (`ARCHITECTURE_PLAN.md`, `TCL_PARSER_SPEC.md`, `IMPLEMENTATION_ROADMAP.md`); `ARCHITECTURE_PLAN.md` §8.5 retired-codes table replaced with a single sentence stating the registry is compact; §15 adoption roadmap collapsed to a pointer to `technical_docs/IMPLEMENTATION_ROADMAP.md`; §12 scenarios 30/31/32 dropped (Windows case-insensitive paths, symlinks, non-ASCII paths — absorbed into general `pathlib` behaviour, not worth a row each). Stray `json_kit/base-v1.schema.json`, `feature-v1.schema.json`, `project-v1.schema.json` duplicates at `json_kit/` root deleted (canonical location is `json_kit/schemas/`). `FD-10 machine-readable-cli-output`, `FD-11 multi-platform-domain-support`, and `FD-12 template-script-generation` filed. `docs_old/` archive directory deleted. |
| 2026-04-22 | **Final handoff review fixes.** Fixed `json_kit/schemas/feature-v1.schema.json` line 110: incorrect VW-10 reference changed to VW-18 (VW-10 is reserved, VW-19 is `cross-source-fe-vetoed`, and only VW-18 applies to `procedures.exclude` being vetoed). Unified empty-procs-array handling: `VE-03` now fires for both `procedures.include` and `procedures.exclude` (schema enforces `minItems: 1` on `procEntry.procs`); previous "silent no-op" text for exclude removed. Updated DIAGNOSTIC_CODES.md VE-03 description to reflect unified behavior. Created comprehensive FINAL_HANDOFF_REVIEW.md with devil's advocate analysis and sign-off for agent buildout. |

---

## 15. Glossary

| Term | Definition |
|---|---|
| **Domain** | A single EDA tool / flow-stage subtree under `global/<vendor>/<domain>/`. The unit of trimming. |
| **Base JSON** | Required domain baseline JSON (schema `chopper/base/v1`). Declares minimum viable F1/F2/F3 content for the domain. |
| **Feature JSON** | Optional overlay JSON (schema `chopper/feature/v1`) layered on top of base to add or remove files, procs, or stages. |
| **Project JSON** | Reproducible selection manifest (schema `chopper/project/v1`) bundling a base plus ordered feature list for a specific project branch. |
| **F1** | File-level capability: whole-file include/exclude via `files.include` / `files.exclude`. |
| **F2** | Proc-level capability: per-proc include/exclude inside Tcl files via `procedures.include` / `procedures.exclude`. |
| **F3** | Stage-level capability: generated `<stage>.tcl` run files driven by the `stages` array and `flow_actions`. |
| **FI** | `files.include` set (literal paths + expanded globs). |
| **FE** | `files.exclude` set (literal paths + patterns). |
| **PI** | `procedures.include` — additive proc-selection model. |
| **PE** | `procedures.exclude` — subtractive proc-selection model. |
| **PI+** | Transitive trace expansion of PI; reporting-only, never affects survival. |
| **PT** | Traced-only procs (PI+ minus PI); reporting-only. |
| **Rule L1** | The Law of Explicit Include: an explicit include always wins over any exclude. See §4 R1. |
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
| **Stack file** | Optional scheduler metadata file (`N`/`J`/`L`/`D`/`I`/`O`/`R` lines). Authored manually by default; auto-generated per-stage when the base JSON sets `options.generate_stack: true` (see §3.6). |
| **Signoff** | Final verification stage of the VLSI flow (timing, power, DFT, formality); Chopper's primary adoption target. |
| **Domain boundary** | The directory tree rooted at the domain directory; Chopper never reads, writes, or backs up outside this boundary. |
| **Dry-run** | `--dry-run` mode: full pipeline simulation producing `.chopper/` artifacts without modifying any domain files. |