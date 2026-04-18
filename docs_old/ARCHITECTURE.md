# Chopper — EDA TFM Trimming Tool

> **Status:** Draft — Consolidated Architecture Baseline 
> **Author:** rkudipud  

---

## 1. Problem Statement

### 1.1 Context

The **Cheetah R2G (CTH R2G)** flow FLow spans the full VLSI backend pipeline, from **Fusion Compiler** through **final signoff**, across multiple EDA tools. **CTH Tool Flow Manager (TFM)** orchestrates tool invocations, configuration, and handoff data.

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
|---|---|
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
|---|---|
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
- Transitive proc dependency tracing only for logging
- run-file generation
- Audit trail and reproducibility

System is classified into three broad features:

**F1:** File-level granularity; users can choose which files to include and which to remove.
**F2:** Proc-level granularity; users can choose which procs to include from which file and which procs to remove from which file.
**F3:** Stage-level granularity; users can use the stage/step section to define run files and these scripts "<stage>.tcl" files will be generated.

**NOTE:** Users have complete freedom to choose any one or combination of all three feature sets, and JSON ensures that at least one of these feature keys is always present.

### 2.2 Out of Scope

Chopper is not intended to do the following:
- Trim directories outside the selected domain path. The domain owner is responsible for ensuring that the domain path is properly scoped to contain all relevant files and procs.
- Perform repo-wide global trimming across all domains in one dependency graph.
- Evaluate runtime Tcl semantics completely. Chopper performs static analysis and tracing based on the source code, but it does not attempt to fully resolve dynamic Tcl patterns such as `eval`, `uplevel`, or runtime-generated proc/file names. Such patterns are logged as warnings and require explicit owner input.
- Automatically include traced proc call trees in the final proc-included section; users read trace logs and modify JSONs accordingly.
- Execute or simulate tool flows to infer feature selections.
- Partially trim non-Tcl languages at subroutine level.
- Infer undeclared feature dependency graphs automatically. Feature JSON may declare `depends_on`, but semantic enforcement is handled by validation rather than by schema alone.

### 2.3 Roles

| Role | Responsibility |
|---|---|
| **Global Flow Owner** | Owns the full mainline flow code for a domain and authors base/features JSONs for that domain. |
| **Project Lead / Release Manager** | Creates the project branch, coordinates the trim window, and drives final cleanup and branch readiness. |
| **Domain Deployment Owner** | Chooses project-specific features, maintains JSON combinations, runs Chopper, reviews output, and commits trimmed domain results. |

### 2.4 Repo Layout — Actual CTH R2G Structure

The TFM repo has this top-level structure under `global/`:

```
global/
├── snps/
│   ├── common/                ◄── INFRASTRUCTURE (never trimmed)
│   │   ├── setup.tcl
│   │   ├── snps_procs.tcl
│   │   ├── infra_procs.tcl
│   │   └── ...
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
    ├── common/                ◄── INFRASTRUCTURE (never trimmed)
    │   ├── setup.tcl
    │   ├── cdns_procs.tcl
    │   ├── infra_procs.tcl
    │   └── ...
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

**Key rule: anything outside the domains's boundary is considered "DO NOT TOUCH ZONE" and is NEVER trimmed.**

### 2.5 Per-Domain Structure (Actual)

Each domain is typically flat or shallow, with Tcl at the root and optional subdirectories:

```
domain_X/
├── jsons/
│   ├── base.json
│   └── features/
│       └── ...
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

```
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
|---|---|---|
| **Tcl** | Primary flow language | File-level and proc-level |
| **Perl** | Utility and support scripts | File-level only |
| **Python** | Utility and reporting scripts and primary sometimes | File-level only |
| **tcsh / csh** | Shell wrappers and environment setup | File-level only |

### 2.8 Backup and Re-trim Strategy

Chopper uses a **backup-and-rebuild** workflow:

```
BEFORE first trim:
  domain/                    ← original full domain

AFTER first trim:
  domain_backup/             ← original untouched source
  domain/                    ← new trimmed domain

AFTER re-trim:
  domain_backup/             ← still original untouched source
  domain/                    ← rebuilt from backup

FINAL CLEANUP:
  domain_backup/             ← deleted on the last day
  domain/                    ← final trimmed domain retained
```

**Operational rule:** Backups stay in the project branch during the trim window and are deleted during final cleanup.

**Partial-failure or re-run recovery:** if Chopper crashes mid-trim after creating `_backup` but before completing output or users want to rerun the trim after making changes to the JSON, the action is to re-run Chopper. The second run detects `_backup` and treats the invocation as a re-trim, rebuilding the domain from the intact backup.

### 2.8.1 Domain Lifecycle State Machine

The trim lifecycle is a formal state machine. Each domain has exactly one state at any point:

```python
class DomainState(Enum):
    VIRGIN = "virgin"                    # domain/ exists, no _backup
    BACKUP_CREATED = "backup_created"    # domain_backup/ exists, domain/ removed or empty
    STAGING = "staging"                  # domain_backup/ + staging dir in progress
    TRIMMED = "trimmed"                  # domain_backup/ + domain/ (trimmed)
    CLEANED = "cleaned"                  # domain/ only, no _backup
```

**State transition table:**

| From | To | Trigger | Failure Recovery |
|---|---|---|---|
| VIRGIN | BACKUP_CREATED | `os.rename(domain, domain_backup)` | Re-run detects BACKUP_CREATED |
| BACKUP_CREATED | STAGING | Start writing staging dir | Remove staging, domain stays BACKUP_CREATED |
| STAGING | TRIMMED | Atomic promote staging → domain | Remove staging, restore domain from backup |
| TRIMMED | STAGING (re-trim) | Start writing new staging dir | Preserve last good domain, remove staging |
| TRIMMED | CLEANED | `chopper cleanup` removes _backup | Irreversible — require `--confirm` flag |

**Invariants:**

- At any point, there is either a valid `domain/` or a valid `domain_backup/` (or both). Never neither.
- `domain_backup/` is read-only input during all trim and re-trim operations.
- The CLEANED state is terminal and irreversible within a single trim cycle.
- Re-invoking `chopper cleanup` on an already CLEANED domain is an informational no-op; it does not recreate or mutate state.

### 2.8.2 Domain Coordination and Advisory Locking

During the trim window, multiple owners may work in the same project branch. Chopper must prevent concurrent mutation of the same domain, but it does not attempt branch-wide locking.

Rules:

- `trim` and `cleanup` acquire a per-domain advisory lock before any filesystem mutation. `scan` and `validate` are read-only and do not require the lock.
- The lock path must remain stable across the `domain/` → `domain_backup/` rename, so it lives beside the domain as a sibling path such as `<domain_parent>/<domain_name>.chopper.lock`, not inside either tree.
- The lock records at least `run_id`, `pid`, `hostname`, `user`, `command`, `domain`, and `started_at`.
- If a mutating command cannot acquire the advisory `flock()`, the lock is active and the command fails fast with a clear diagnostic rather than waiting indefinitely.
- A leftover lock path with no active advisory lock is treated as abandoned metadata or an orphaned lock file and may be replaced after recording an audit event.
- `--force` never breaks a live advisory lock. It may clean up only abandoned lock metadata or orphaned lock files after Chopper has already proven no active advisory lock is held.
- The lock is advisory. It reduces accidental same-domain concurrency; it does not replace Git conflict resolution or release-manager coordination.

### 2.9 Cross-Domain Dependencies

**Current architectural assumption:** cross-domain dependencies do not materially exist in practice.

This means:
- Domains are trimmed independently.
- Tracing is bounded to the selected domain path.
- `common/` is treated as always available infrastructure.

If cross-domain references are discovered later, they may be added as a future validation pass, but they are not a launch requirement.

### 2.10 Feature Ownership and Selection

**Domain owners own feature selection.**

This includes:
- Choosing the base JSON for their domain
- Choosing the selected feature JSONs for a project
- Reviewing scan output and draft JSONs
- Deciding final run-file generation content for their domain
- Reviewing warnings, trace reports, and validation output

---

## 3. Core Concepts and Capability Model

### 3.1 Base JSON

The **Base JSON** defines the minimum viable flow for a domain.

It may contain any subset of the F1, F2, and F3 sections. Omitted capability blocks are treated as empty.

By default, the curated base JSON is stored at `jsons/base.json` under the selected domain.

It represents:
- Files that must remain - the field is optional
- Proc entry points that must remain - the field is optional
- Optional stage/step structure for F3 - the field is optional
- Domain-level metadata and options - the field is optional

### 3.2 Feature JSON

The **Feature JSON** expresses optional behavior layered on top of the base.

It may contain any subset of the F1, F2, and F3 sections. Omitted capability blocks are treated as empty.

By default, curated feature JSONs are stored under `jsons/features/` under the selected domain.

It represents:
- Additional files to keep - the field is optional
- Additional procs to keep - the field is optional
- Owner override rules that prune derived keep candidates when safe - the field is optional
- Optional stage/step actions for F3 - the field is optional

`files.exclude` and `procedures.exclude` are meaningful in v1, but only as owner overrides on derived keep candidates:
- `files.exclude` prunes files brought in by broad wildcard `files.include` patterns.
- `procedures.exclude` prunes procs brought in only by conservative trace expansion.
- Literal file paths in `files.include` and explicit `procedures.include` entries always win.

### 3.3 Project JSON

The **Project JSON** is the reproducible project-specific selection file.

It represents:
- Project identifier
- Domain identifier
- Selected base JSON
- Selected feature JSONs
- Optional feature ordering and project notes - the field is optional

### 3.4 F1 — File Chopping

F1 performs whole-file trimming.

| Behavior | Description |
|---|---|
| **Input unit** | File or glob pattern |
| **Output unit** | Whole file copied or removed |
| **Best for** | Tcl scripts without shared proc libraries, configs, stack files, hooks, Perl/Python/csh |

### 3.5 F2 — Proc Chopping

F2 performs Tcl proc-level trimming.

| Behavior | Description |
|---|---|
| **Input unit** | `{ file, procs[] }` |
| **Output unit** | Original file copied, unwanted proc definitions deleted |
| **Best for** | `*_procs.tcl`, shared utility proc files, rule libraries |

### 3.6 F3 — Run-File Generation (Optional)

F3 generates stage-based run files from JSON definitions. **Stages are optional.** Users who want to generate run scripts from JSON can define stages; others can create stack files manually or skip this feature entirely.

| Behavior | Description |
|---|---|
| **Input unit** | Ordered stages and steps |
| **Output unit** | `<stage>.tcl` (when stages are defined), optional manually-created stack files |
| **Purpose** | Build clean project-facing run orchestration for domains that want generated run scripts with injectable step sequences |

**F3 is an optional capability of Chopper.** Chopper ships F1/F2/F3 as first-class capabilities; domain owners choose which capabilities to use per domain/project. Users without stages still get F1 and F2 (file and proc trimming). Users with stages get generated `<stage>.tcl` run scripts for fine-grained step control.

### 3.7 Supporting Capability — `chopper scan`

`chopper scan` is part of the architecture and exists to automate the discovery work domain owners already perform manually.

**Purpose:** generate draft authoring material, not final truth.

**Expected outputs:**
- Domain file inventory (JSON + text)
- Draft base JSON skeleton (marked `_draft: true`)
- Proc inventory per Tcl file (JSON)
- `iproc_source` and `source` dependency inventory
- Auto-detected proc call graph (dependency_graph.json)
- Draft scan report for owner review
- Optional: diff report if previous `jsons/base.json` exists (A-02)

**Ownership model:**
- Chopper generates the draft
- Domain owner curates the final JSONs

#### Scan-to-Trim Workflow

The full scan-to-trim workflow supports both direct CLI mode and project JSON mode:

All workflow examples below assume Chopper is invoked from the domain root. In v1, the current working directory is the operational domain root and `jsons/base.json` plus `jsons/features/*.json` are resolved from there.

**Direct CLI mode (base ± features):**

```
1. chopper scan --output scan_output/
   → Produces draft_base.json, inventories, dependency graphs, scan reports

2. Owner copies draft_base.json → jsons/base.json, curates it
   (adds/removes files, procs, stages as needed)

3. chopper validate --base jsons/base.json
   → Validates curated JSON against domain reality

4. chopper trim --dry-run --base jsons/base.json
   → Full pipeline simulation without file writes

5. chopper trim --base jsons/base.json
   → Live trim
```

**Project JSON mode (same trim semantics, single-file packaging):**

```
1. chopper scan --output scan_output/
   → Produces draft_base.json, inventories, dependency graphs, scan reports

2. Owner curates `jsons/base.json` and feature JSONs under `jsons/features/` from scan output

3. Owner creates a project JSON at any chosen path that bundles the selection:
  <project_json_path> → { base: "jsons/base.json", features: ["jsons/features/..."], project metadata, notes }

4. chopper validate --project configs/project_abc.json
   → Validates all referenced JSONs via Phase 1 checks

5. chopper trim --dry-run --project configs/project_abc.json
   → Full pipeline simulation without file writes

6. chopper trim --project configs/project_abc.json
   → Live trim (project metadata recorded in audit artifacts)

7. chopper cleanup --confirm
   → Last-day backup removal
```

**Scan output contracts (finalized in TECHNICAL_REQUIREMENTS.md §7.2.2):**
- `draft_base.json` MUST conform to `chopper/base/v1` schema AND carry `"_draft": true` metadata flag
- `file_inventory.json` lists all discovered files with language and classification
- `proc_inventory.json` lists all discovered procs with canonical names and source locations
- `scan_report.json` summarizes discoveries with diagnostics and follow-up items
- `scan_report.txt` is human-readable projection of scan_report.json
- `dependency_graph.json` contains all source, iproc_source, and proc call edges
- `diff_report.json` (optional) shows changes from previous scan if `jsons/base.json` exists (A-02)
- Scan SHOULD detect existing `jsons/base.json` in the domain and produce diff report (A-02: owner decides format)
- Scan is idempotent and re-runnable; re-running scan overwrites previous scan output
- Scan does not modify domain files — it only reads and produces artifacts in the output directory
- All machine-readable scan artifacts carry `chopper_version`; `draft_base.json` also carries `$schema` because it is itself a Base JSON document (per §7.2.3)

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

## 4. Architecture Decisions

### 4.1 Decision 1: Explicit File-Level Promotion Only

**Full-file copy is allowed only when a selected JSON explicitly requires that file.**

This is the final rule for file-level promotion.

**Terminology:**
- **Promotion** = escalating a proc-trimmed file to a full-file copy.
- **Hook-file discovery** = detecting related hook files (e.g., `pre_*/post_*`) from `iproc_source -use_hooks` during analysis/scan; discovery alone does not copy them.

| Case | Result |
|---|---|
| File appears only in `procedures.include` | Proc-level trimming applies |
| File appears in `files.include` in any selected base/feature JSON | Full-file copy applies |
| File is discovered by trace only | No automatic full-file promotion |
| Hook file is discovered via `-use_hooks` (A-01) | Hook file is reported in scan/discovery outputs only; it is copied only when explicitly included in selected JSON (`files.include`) |
| File is mentioned only by validation warnings | No automatic full-file promotion |

**Why this matters:** file-level promotion is dangerous because it can silently re-bloat a carefully trimmed domain. Therefore, promotion is permitted only when some selected JSON explicitly asks for the full file.

**Rule:** implicit discovery never escalates a file from proc-level to file-level.

### 4.2 Decision 2: Default Action Is Exclude

**Default exclude is fixed.**

This is no longer configurable.

| Policy | Result |
|---|---|
| File explicitly kept by F1 | Survives as a whole file |
| File explicitly kept by F2 | Survives only as a proc-trimmed file |
| File not explicitly kept anywhere | Removed |

**Architectural consequence:** remove any notion of a global default-include mode from the design.

### 4.3 Decision 3: Tracing Is Default-On and Conservative

**Tracing is the most important feature in Chopper.** It is enabled by default and designed conservatively.

#### Why tracing matters from a product perspective

- It is the primary difference between Chopper and file-only tools.
- It reduces domain-owner authoring cost by removing manual dependency enumeration from the happy path.
- It lowers trim risk during the 2-week delivery window.
- It improves adoption because users can describe entry-point procs instead of entire call chains.
- It improves auditability because Chopper can explain *why* a proc survived.
- It makes re-trim viable because the dependency expansion can be reproduced from saved inputs and trace logs.

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

#### What Chopper does not automatically resolve

- `$cmd $args`
- `eval "..."`
- `uplevel ...`
- Runtime command aliasing or other dynamic metaprogramming

#### Conservative behavior

```
[EXPERIMENTAL-TRACE][AUTO] flow_procs.tcl::read_libs -> setup_library_paths
[EXPERIMENTAL-TRACE][AUTO] flow_procs.tcl::setup_library_paths -> resolve_lib_path
[EXPERIMENTAL-TRACE][WARN] utils.tcl::helper -> <dynamic dispatch $cmd> (unresolvable)
```

**Conservative policy:** when Chopper cannot prove a dependency, it warns instead of inventing one.



#### Trace expansion algorithm

Trace expansion is a fixed-point walk over a per-run proc index built from every Tcl file in the selected domain. The walk is **breadth-first with a lexicographically sorted frontier** to guarantee deterministic output regardless of filesystem walk order.

1. Parse all domain Tcl files **in lexicographic order of domain-relative path** (`sorted(domain_path.rglob('*.tcl'))`) and build the proc index before evaluating any `procedures.include` entry.
2. Normalize every proc to canonical form `relative/path.tcl::qualified_name`.
3. Seed the trace frontier with all explicit PI entries after validating that the requested file/proc pairs exist. Sort the frontier lexicographically by canonical proc name.
4. While the frontier is non-empty, pop the **smallest** canonical proc name from the frontier. If it is already in the traced set, skip it. Otherwise add it to the traced set, then inspect its proc body span and extract:
  - direct proc calls whose first token is a literal proc name
  - bracketed proc calls such as `[helper_proc ...]`
  - literal `source` and `iproc_source` file dependencies
5. Resolve literal proc calls with a deterministic lexical namespace contract:
  - `::ns::helper` means the absolute qualified proc name `ns::helper` only.
  - `ns::helper` means "look in the caller namespace first, then global". For a caller in `a::b`, the ordered candidates are `a::b::ns::helper`, then `ns::helper`.
  - `helper` means "look in the caller namespace first, then global". For a caller in `a::b`, the ordered candidates are `a::b::helper`, then `helper`.
  - `namespace import`, command-path lookup, aliasing, and `namespace unknown` are out of scope for v1 and are never guessed.
6. For each candidate qualified name in order, resolve only when exactly one canonical proc inside the selected domain has that qualified name.
7. If multiple canonical procs match the same candidate qualified name, emit `TRACE-AMBIG-01` and do NOT resolve.
8. If no in-domain proc matches after lexical namespace resolution, emit `TRACE-CROSS-DOMAIN-01` and do NOT resolve. Chopper does not search other domains.
9. Dynamic or syntactically unresolvable call forms emit `TRACE-UNRESOLV-01`.
10. If a newly resolved callee is already in the traced set (cycle), do NOT add it to the frontier again. This naturally terminates cycles. Emit `TRACE-CYCLE-01` WARNING diagnostic listing the cycle path (e.g., `A → B → A`). Both procs in the cycle are included in PI+ — cycles mean mutual dependency.
11. Append any newly resolved callees (not yet in the traced set) to the frontier in sorted order.
12. Emit PI+ in deterministic order: source file path, then canonical proc name.

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

Hard rules:
- Duplicate `canonical_name` entries are errors.
- Duplicate `short_name` values within the same file are errors.
- If a call token resolves to zero candidates, Chopper warns and does not auto-include a guess.
- If a call token resolves to multiple candidates, Chopper raises an ambiguous-call warning and does not auto-include any candidate.

#### `iproc_source`, `source`, and hook semantics

Chopper treats file sourcing as a file-dependency graph separate from proc tracing.

| Pattern | Contract |
|---|---|
| `source foo.tcl` | File edge to `foo.tcl` when the argument is a literal relative path |
| `iproc_source -file foo.tcl` | File edge to `foo.tcl` |
| `iproc_source -file foo.tcl -optional` | File edge remains recorded; missing target is non-fatal unless explicitly required elsewhere |
| `iproc_source -file foo.tcl -required` | Surviving reference to missing target is a validation error |
| `iproc_source -file foo.tcl -quiet` | Does not suppress Chopper diagnostics; it only affects original flow behavior |
| `iproc_source -file foo.tcl -use_hooks` | Discover `pre_foo.tcl` / `post_foo.tcl` candidates for scan reporting; do not copy unless explicitly included in selected JSON |

Additional rules:
- Hook discovery is informational unless selected JSON explicitly includes the hook file.
- Hook resolution is same-directory only and uses the literal basename of the referenced file.
- Hook files not explicitly included in selected JSON are ignored during trim, but are still captured in scan artifacts and diagnostics.
- Hook files are file-level artifacts; Chopper does not proc-trim them unless they are independently selected as Tcl proc files.
- Dynamic sourcing expressions containing unresolved `$`, `eval`, `uplevel`, or runtime-generated file names are never guessed; they produce diagnostics and require explicit owner input.

### 4.4 Decision 4: F3 Uses Plain Strings by Design

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

### 4.5 Decision 5: Explicit Include Wins Over Exclude — Final Rule

**Decision 5 is final and authoritative.**

Explicit include wins over exclude across all selected inputs.

Excludes remain meaningful in v1, but only as owner overrides on derived keep candidates:
- `files.exclude` prunes files brought in by wildcard `files.include` patterns.
- `procedures.exclude` prunes procs brought in only by conservative trace expansion.
- A literal file path in `files.include` always survives.
- A proc explicitly listed in `procedures.include` always survives.

#### Canonical resolution model

1. Partition `files.include` entries from the selected base and features into literal paths (**FI_literal**) and wildcard patterns (**FI_glob_patterns**).
2. Expand **FI_glob_patterns** into **FI_glob**.
3. Compile all `files.exclude` patterns into **FE**.
4. Compile all explicit `procedures.include` entries into **PI**.
5. Compile all `procedures.exclude` entries into **PE**.
6. Expand PI via default-on tracing into **PI+**.
7. Compute traced-only procs as **PT = PI+ - PI**.
8. Surviving full files are **FI_literal ∪ (FI_glob - FE)**.
9. Surviving procs are **PI ∪ (PT - PE)**.
10. If a file is in both the surviving full-file set and the surviving proc set, full-file copy wins because the file was explicitly requested as a file.
11. Anything not preserved by the surviving full-file set or the surviving proc set is removed.

#### Implications

| Conflict | Final Result |
|---|---|
| File listed literally in `files.include` and also excluded | File survives |
| File matched only by wildcard include and also excluded | File is removed |
| Proc explicitly included and also excluded | Proc survives |
| Proc reached only by trace and also excluded | Proc is removed |
| Base explicitly includes item and feature excludes item | Item survives |
| Feature A adds item only by wildcard or trace and Feature B excludes it | Later exclude can prune the derived item |
| **File in `files.exclude` but contains proc(s) in PI+ (surviving procs)** | **File survives as PROC_TRIM** — only surviving procs are kept; file-level exclusion does not override proc-level needs. Emit a compiler warning noting that the file was explicitly excluded but is still required by surviving proc dependencies. |

**File treatment derivation:** A file's treatment in the compiled manifest is determined as follows:

1. If the file is in the surviving full-file set (FI_literal or FI_glob − FE) → `FULL_COPY`.
2. Else if the file contains one or more procs in the surviving proc set (PI+) → `PROC_TRIM`.
3. Else if the file is targeted by an F3 generator → `GENERATED`.
4. Else → `REMOVE`.

This means a file can survive as `PROC_TRIM` even if it appears in `files.exclude`, because proc-level include-wins takes precedence over file-level exclusion.

**Feature safety statement:** selected features cannot remove something that the base or another selected feature explicitly requested.

### 4.6 Decision 6: Backup-and-Rebuild Is Kept

This remains an explicit architecture decision.

| Rule | Behavior |
|---|---|
| **First trim** | Rename original domain to `_backup`, build new trimmed domain |
| **Re-trim** | Rebuild from `_backup` |
| **Cleanup timing** | Delete backups on the last day of the trim window |
| **Why** | Safety first; clean retrim; no destructive incremental editing |


---

## 5. High-Level Workflow and Compilation Model

### 5.1 Input Modes

Chopper supports three input modes. Exactly one mode is used per invocation.

| Mode | CLI Form | Description |
|---|---|---|
| **Base-only** | `--base jsons/base.json` | Trim using only the base JSON, no features |
| **Base + Features** | `--base jsons/base.json --features jsons/features/f1.json,jsons/features/f2.json` | Trim using base JSON with one or more feature overlays |
| **Project** | `--project <path-to-project.json>` | A single project JSON that packages the same base path, ordered feature paths, project metadata, and selection rationale in one file |

By default, owner-curated base and feature JSONs live under the current working directory, which is the domain root for normal v1 operation, at `jsons/base.json` and `jsons/features/*.json`. Project JSON has no fixed home and is always passed explicitly to `--project`.

`--project` is mutually exclusive with `--base` and `--features`. Providing both is a CLI usage error (exit code 2).

Given the same current working directory, base JSON, and ordered feature list, project mode and direct CLI mode must produce identical compilation and trim results.

When `--project` is provided, Chopper assumes it is being run from the domain root. The current working directory is therefore the root for resolving `base` and `features`, not the project JSON file location. The resolved inputs then enter the same compilation pipeline as `--base`/`--features`. The `project`, `owner`, `release_branch`, and `notes` fields from the project JSON are recorded in audit artifacts.

When `--project` is provided, the project JSON `domain` field is a required identifier for audit and consistency. It must match the basename of the current working directory. If `--domain` is also provided, it must resolve to that same current working directory. Any mismatch is a CLI usage error (exit code 2).

The detailed CLI reference with all arguments, flags, and per-subcommand usage is in `docs/TECHNICAL_REQUIREMENTS.md` §9.1.3.

### 5.1.1 Example Invocations

```bash
# Base only
chopper trim --base jsons/base.json

# Base + features
chopper trim --base jsons/base.json \
  --features jsons/features/feature_dft.json,jsons/features/feature_power.json

# Project JSON at a user-supplied path (same result as equivalent resolved --base/--features)
chopper trim --project configs/project_abc.json

# Dry-run with project JSON
chopper trim --dry-run --project configs/project_abc.json
```

### 5.2 Internal Pipeline

```
  Domain owner invokes Chopper
            │
            ▼
  ┌──────────────────────────┐
  │  0. Detect trim state    │  first trim vs re-trim
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  1. Read inputs          │  base JSON + selected feature JSONs (from CLI or project JSON)
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  1.5 Pre-trim validate   │  Phase 1 checks (Section 5.7)
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  2. Compile selections   │  FI / FE / PI / PE
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  3. Trace proc deps      │  PI -> PI+
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  4. Build output         │  file copy + proc delete + F3 output
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  5. Validate             │  Phase 2 checks (Section 5.7)
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  6. Emit audit trail     │  .chopper/
  └──────────────────────────┘
```

### 5.3 Compilation Model

```
  Input: jsons/base.json + selected features under jsons/features/ (from CLI args OR project JSON)
                 │
                 ▼
         compile FI / FE / PI / PE
                 │
                 ▼
           expand PI to PI+
                 │
                 ▼
     apply Decision 1 + Decision 5
                 │
                 ▼
        final resolved file/proc set
```

When `--project` is used, Chopper resolves the base and selected feature paths from the project JSON before entering the compilation pipeline. Equivalent resolved selections produce identical results regardless of input mode.

### 5.3.1 Internal Compilation Contract

Detailed compilation data models, execution-freeze rules, and implementation contracts now live in `docs/TECHNICAL_REQUIREMENTS.md`.

This architecture document defines what Chopper must do; the technical requirements document defines how the implementation must structure and preserve those contracts.

### 5.4 Audit Trail

Each run emits `.chopper/` under the trimmed domain:

```
domain/
├── .chopper/
│   ├── chopper_run.json
│   ├── input_base.json
│   ├── input_features/
│   ├── input_project.json        ◄── optional; present only when `--project` is used
│   ├── compiled_manifest.json
│   ├── dependency_graph.json
│   ├── trim_report.json
│   └── trim_report.txt
└── ...
```

#### Audit artifact contract

The detailed artifact structures and minimum field contracts are defined in `docs/TECHNICAL_REQUIREMENTS.md`.

### 5.5 Output Expectations

Chopper output must be:
- Deterministic
- Reproducible from saved inputs
- Explainable through trace and trim reports
- Safe to review in code review

#### Determinism, staging, and atomic promotion

Determinism and write-safety remain architectural requirements. The detailed staging, atomic-promotion, and restore rules are defined in `docs/TECHNICAL_REQUIREMENTS.md`.

### 5.6 Scan Pipeline

```
  Domain owner invokes chopper scan
            │
            ▼
  ┌──────────────────────────┐
  │  1. Read domain path     │  locate all files in domain
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  2. Classify files       │  Tcl vs non-Tcl, naming patterns
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  3. Parse Tcl files      │  extract proc definitions
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  4. Build dependency map │  iproc_source / source / proc calls
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  5. Generate drafts      │  draft base JSON + inventories
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  6. Emit scan report     │  what was found + what needs review
  └──────────────────────────┘
```

### 5.7 Validation Model

Chopper has three validation phases:
- Phase 1: pre-trim input validation
- Phase 2: post-trim output validation
- Phase 3: dry-run full-pipeline simulation

`chopper validate` remains the Phase 1-only command.

The detailed validation check matrix, diagnostics contract, and exit semantics are defined in `docs/TECHNICAL_REQUIREMENTS.md`.

### 5.8 CLI Contract, Diagnostics, and Exit Semantics

Chopper exposes the `scan`, `validate`, `trim`, and `cleanup` subcommands as first-class user interfaces.

Chopper supports three input modes: base-only (`--base`), base-plus-features (`--base --features`), and project JSON (`--project`). Project JSON mode packages the same selection decisions into a single auditable file without changing trim semantics. `--project` is mutually exclusive with `--base`/`--features`.

The complete CLI reference — including all subcommands, arguments, flags, per-mode examples, and the project JSON workflow — is defined in `docs/TECHNICAL_REQUIREMENTS.md` §9.1.3.

Detailed CLI behavior, diagnostics fields, exit codes, presentation constraints, and usability requirements are defined in `docs/TECHNICAL_REQUIREMENTS.md`.

### 5.9 Python Implementation Guidance

Python coding standards, repository structure, package boundaries, configuration policy, logging policy, and future GUI-readiness are defined in `docs/TECHNICAL_REQUIREMENTS.md`.

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
- Literal file paths (no special characters) refer to exact single files and take precedence over glob patterns per Decision 5.

**Decision 5 Application to Glob Patterns:**
- Literal paths in `files.include` **always survive**, even if they match an `files.exclude` pattern.
- Wildcard-expanded `files.include` candidates **are pruned** by matching `files.exclude` patterns (normal set subtraction).
- Glob expansion happens **before** Decision 5 rules are applied, so the conflict resolution operates on the fully expanded sets.

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

Full normalization, glob expansion, deduplication, and manifest-emission rules are defined in `docs/TECHNICAL_REQUIREMENTS.md`.

By default, owner-curated configuration JSONs live under the selected domain at `jsons/base.json` and `jsons/features/*.json`.

### 6.4 Base JSON Structure

```json
{
  "$schema": "chopper/base/v1",
  "domain": "fev_formality",
  "description": "Bare-minimum formality flow for rtl2gate and gate2gate verification",
  "options": {
    "cross_validate": true,
    "template_script": "templates/generate_fev_release_files.py"
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

For users who define stages, the optional mapping to stack files is direct: `name` -> `N`, `command` -> `J`, `exit_codes` -> `L`, `dependencies` -> `D`, `inputs` -> `I`, and `outputs` -> `O`. Stack files themselves are optional; users can create them manually or use Chopper's generated scripts as is.

**Validation rule:** an entry in `procedures.include` with an empty `procs` array (`"procs": []`) is a **hard error**. If the author intended to keep the whole file, the correct action is to move the file into `files.include`. Chopper rejects this during validation and dry-run, with an actionable error message directing the author to use `files.include` instead.

**Template script rule:** `options.template_script` keeps the proposal's field name for continuity. In Chopper v1 it is a domain-relative path to a script that already exists under the selected domain directory. Chopper resolves it relative to the domain root, treats it as a required kept file, and executes it once at the end of a successful `trim` run before the process exits. It is a path, not a general command string, and it must not point outside the domain.

### 6.5 Feature JSON Structure

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

The **Project JSON** is the single-file packaging form for reproducible, auditable trim runs. It bundles the complete selection — base path, ordered feature paths, project metadata, and selection rationale — into one file that can be version-controlled, shared across team members, and used in CI pipelines.

**Project JSON vs direct CLI arguments:**

| Scenario | Typical Packaging |
|---|---|
| Initial exploration / scan-to-trim authoring | `--base` (± `--features`) |
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
    "jsons/features/scan_common.json",
    "jsons/features/feature_dft.json",
    "jsons/features/feature_power.json"
  ],
  "notes": [
    "scan_common is ordered ahead of feature_dft because DFT inserts steps into scan-owned setup content",
    "feature_power remains enabled because compare_lp is replaced by the selected feature set"
  ]
}
```

**Required fields:**

| Field | Type | Description |
|---|---|---|
| `$schema` | string | Must be `"chopper/project/v1"` |
| `project` | string | Project identifier (e.g., `PROJECT_ABC`) |
| `domain` | string | Domain identifier. In v1 it must match the basename of the current working directory, which is the operational domain root. |
| `base` | string | Path to the base JSON file (resolved relative to the current working directory / domain root). Default expected location: `jsons/base.json`. |

**Optional fields:**

| Field | Type | Description |
|---|---|---|
| `owner` | string | Domain deployment owner for this project |
| `release_branch` | string | Git branch name for this project trim |
| `features` | array of strings | Ordered list of feature JSON paths (resolved relative to the current working directory / domain root). Default expected location pattern: `jsons/features/*.json`. Order is authoritative. |
| `notes` | array of strings | Human-readable notes explaining feature ordering or selection rationale |

**Path resolution rules:**
- Chopper assumes it is invoked from the domain root. The current working directory is therefore the root for resolving `base` and `features`.
- `base` and `features` paths are resolved relative to the current working directory, not relative to the project JSON file location.
- This means a project JSON can live anywhere — `configs/`, `projects/`, outside the repo — and still correctly reference the domain's base and feature JSONs under the default `jsons/` layout.
- The default expected curated JSON layout under the domain root is `jsons/base.json` and `jsons/features/*.json`.
- All path rules from §6.3.1 apply (forward slashes, no `..` traversal, no absolute paths).
- The project JSON `domain` field must match the basename of the current working directory. If `--domain` is provided with `--project`, it must resolve to that same directory. Mismatches are CLI usage errors.

**CLI usage:**
```bash
# Validate a project JSON
chopper validate --project configs/project_abc.json

# Dry-run using a project JSON
chopper trim --dry-run --project configs/project_abc.json

# Live trim using a project JSON
chopper trim --project configs/project_abc.json
```

**Mutual exclusivity:** `--project` is mutually exclusive with `--base` and `--features`. Providing both is a CLI usage error (exit code 2).

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
- `@n` where `n` exceeds the actual count of that step string is a validation error (V-12)
- `@n` is supported on: `replace_step`, `remove_step`, `add_step_before`, `add_step_after`
- `@n` is NOT supported on stage-level actions (stage names must be unique)

Action application contract:
- Features are applied in selected order.
- Within one feature, actions are applied top-to-bottom.
- `reference` and `stage` matching is exact (with optional `@n` instance targeting for steps).
- If a stage contains the same step string multiple times, `replace_step` and `remove_step` use `@n` targeting to resolve ambiguity. Without `@n`, duplicate step strings are a validation error.
- `replace_stage` removes the target stage, inserts the replacement stage at the same position, and rewrites existing `load_from` references to the new stage name before later actions run.
- Removing a stage or step that is still referenced elsewhere is a validation error until repaired by subsequent actions in the same ordered compile pass.

### 6.8 `chopper scan` Output Model

`chopper scan` should generate machine-usable and human-usable artifacts.

| Output | Purpose |
|---|---|
| **Draft base JSON** | Starting point for owner curation |
| **File inventory** | Visible complete domain content |
| **Proc inventory** | See proc-bearing files and proc names |
| **File dependency graph** | Show `iproc_source` / `source` relationships |
| **Proc call graph** | Show traceable proc call relationships |
| **Scan report** | Explain what was discovered and what needs manual review |

Minimum scan artifact set:
- `draft_base.json`
- `file_inventory.json`
- `proc_inventory.json`
- `dependency_graph.json`
- `scan_report.json`
- `scan_report.txt`

These artifacts are part of Chopper's public data contract. Their documented structures, minimum required fields, and the rule that text reports are projections of the corresponding JSON artifact are defined in `docs/TECHNICAL_REQUIREMENTS.md`.

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
| FR-08 | Support include, exclude, and override semantics. |
| FR-09 | Apply Decision 5 consistently across all selected inputs. |
| FR-10 | Deduplicate output so each surviving proc appears once. |
| FR-11 | Validate syntax and obvious dangling references after trimming. |
| FR-12 | Emit `.chopper/` audit artifacts for every run. |
| FR-13 | Support first trim and re-trim using `_backup`. |
| FR-14 | Provide cleanup support to remove backups at project finalization. |
| FR-15 | Treat `common/` as always-present infrastructure. |
| FR-16 | Treat non-Tcl files at whole-file granularity only. |
| FR-17 | Support dry-run preview mode. Dry-run is mandatory for domain owners to validate JSON files before live trim. |
| FR-18 | Understand `iproc_source -file ...` including `-optional`, `-use_hooks`, `-quiet`, and `-required`. |
| FR-19 | Support optional domain-relative `template_script` execution for F3-related output generation. |
| FR-20 | Discover hook files from `-use_hooks` in scan/analysis output; copy them only when explicitly included in selected JSON. |
| FR-21 | Support step replacement (`replace_step`) and stage replacement (`replace_stage`) as action keywords. Support `@n` instance targeting for duplicate steps. |
| FR-22 | Emit trim statistics in JSON and text form (LOC excludes blank lines and comment-only lines). |
| FR-23 | Emit a VCS-agnostic manifest that includes (a) file operations and (b) semantic operations (procs removed/kept, `replace_step` / `replace_stage` actions applied, auto-trace expansions). |
| FR-24 | Keep F3 as a first-class required capability. |
| FR-25 | Keep tracing default-on and conservative. |
| FR-26 | Provide `chopper scan` to generate draft JSONs and dependency reports. |
| FR-27 | Keep full-file promotion explicit only; never promote implicitly from trace or warnings. |
| FR-28 | Provide pre-trim JSON validation (Phase 1) that catches schema errors, empty procs arrays, missing files/procs, and invalid actions before any files are modified. |
| FR-29 | Provide standalone `chopper validate` command that runs Phase 1 checks without requiring domain source files. Its a structural only check. |
| FR-30 | Build a per-run proc index before tracing and serialize the resolved trace outcome into audit artifacts. |
| FR-31 | Apply feature order deterministically and apply `flow_actions` top-to-bottom within each feature. |
| FR-32 | Perform live trim through staging and atomic promotion so partially rebuilt output is never the final visible state. |
| FR-33 | Emit stable machine-readable diagnostics with severity, code, location, and hint fields. |
| FR-34 | Provide explicit `chopper cleanup` support for last-day backup deletion. |
| FR-35 | Accept a project JSON (`--project`) as an alternative to `--base`/`--features`, resolving base and feature paths from it and recording project metadata in audit artifacts. |
| FR-36 | `--project` is mutually exclusive with `--base` and `--features`; providing both is a CLI usage error (exit code 2). |
| FR-37 | Equivalent resolved selections must produce identical compilation and trim results regardless of whether they came from direct CLI arguments or a project JSON. |

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
| NFR-09 | Use same-filesystem staging and atomic promotion for generated and rewritten artifacts. |
| NFR-10 | Normalize all paths and sort all discovery/glob results before compilation. |
| NFR-11 | Keep library code side-effect free; logging configuration belongs only in the CLI entrypoint. |
| NFR-12 | Separate structural schema validation from semantic validation. |
| NFR-13 | Failures must leave either a validated active domain or a restored pre-run state; no half-written domain is acceptable. |
| NFR-14 | Tests must cover parser/trimmer invariants with both fixture-based and property-based techniques. |
| NFR-15 | Audit JSON and text artifacts must remain stable and machine-usable within a major schema version. |

### 7.3 Acceptance Criteria

Chopper is architecturally successful if a domain owner can:
1. Scan a real domain and obtain a usable draft baseline.
2. Author or refine base/feature JSONs for that domain.
3. Create a project JSON bundling the selection for reproducibility.
4. Run trim using `--base`/`--features` or `--project` and obtain a deterministic rebuilt domain.
5. See why every surviving proc/file remained.
6. Re-trim from backup without manual restore work.
7. Generate F3 output when their domain requires it.
8. Use the same project JSON in CI for automated, reproducible trim runs.

### 7.4 Test and Quality Strategy

The implementation must follow the layered testing and release-quality gates defined in `docs/TECHNICAL_REQUIREMENTS.md`.

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

### 8.3 FEV Formality Domain Notes

- Medium complexity and a good proc-trimming candidate
- Contains meaningful shared proc libraries and rule libraries
- Good representative domain for validating F1 + F2 + F3 together

### 8.4 STA/PT Domain Notes

- High sourcing density
- Heavy use of hooks and conditional sourcing
- Strong validation target for `iproc_source`, hooks, and F2 + F3 alignment

### 8.5 Power Domain Notes

- Highest structural complexity of the three sampled domains
- Deepest subdirectory use
- Strong future validation domain once core parser and scan are stable

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

### TC-01: Tcl Proc Boundary Detection

Chopper must correctly find proc boundaries even with nested braces and namespace constructs.

**Risk:** without a reliable parser, F2 is not viable.

### TC-02: Canonical Proc Naming

This is resolved to **file + proc name**, with namespace-qualified synthesis where needed.

**Canonical form:** `file.tcl::proc_name`

**Namespace rules:**
- A proc defined as `proc foo {...} {...}` in `bar.tcl` is canonicalized as `bar.tcl::foo`.
- A proc defined as `proc ::ns::foo {...} {...}` in `bar.tcl` is canonicalized as `bar.tcl::ns::foo` (leading `::` stripped).
- A proc defined inside `namespace eval ns { proc foo {...} {...} }` in `bar.tcl` is canonicalized as `bar.tcl::ns::foo`.
- JSON authoring uses the short proc name (e.g., `foo`) in the `procs` array; Chopper resolves the canonical form internally.

**Risk:** incorrect canonicalization breaks JSON stability and traceability.

### TC-03: Transitive Proc Tracing

This is the center of the product.

**Main challenge areas:**
- Correct static call extraction
- Conservative behavior for dynamic Tcl
- Cross-file proc mapping within the domain boundary, based on a per-run proc index built by scanning all Tcl files in the domain (source of truth)
- Clear warnings when trace cannot prove correctness

**Per-run proc index:** the proc index contract is defined in Section 4.3 and must exist before F2 trimming or trace expansion runs.

### TC-04: Copy-and-Delete Correctness

F2 depends on preserving top-level Tcl while deleting only unwanted proc definitions.

Deletion contract:
- Chopper deletes only recorded proc spans from the proc index; it never deletes ad hoc text ranges.
- Text between surviving spans is preserved byte-for-byte except for newline normalization chosen by the writer.
- If a proc-trimmed file has no surviving proc definitions and no non-comment, non-whitespace top-level Tcl, the file still survives as the remaining blank/comment-only stub and Chopper emits V-24.
- If top-level Tcl remains, the file survives even if all proc definitions were removed.

**Risk:** malformed deletion breaks Tcl syntax or leaves dangling structure.

### TC-05: File Dependency Detection

Chopper must correctly capture `source` and `iproc_source` references, including flags and hooks.

**Implementation contract:** required vs optional references and `-use_hooks` behavior must follow Section 4.3 exactly and must be reflected in diagnostics and manifests.

### TC-06: Non-Tcl Handling

Non-Tcl files are intentionally file-level only.

**Risk:** attempting to over-interpret non-Tcl files adds cost without strong product value.

### TC-07: Validation Quality

Validation must catch the failures users actually care about:
- Broken Tcl syntax
- Obvious missing files
- Proc references that cannot be justified
- F3 output pointing to trimmed-away content

**Implementation contract:** validation diagnostics must use stable IDs, severities, and actionable hints so CI, text reports, and future UIs all consume the same signal.

### TC-08: Override and Ordering Semantics

Multiple selected features may touch the same proc or stage.

**Current rule:** selected input order governs last-wins behavior where explicit `replace_step` or `replace_stage` actions conflict, while Decision 5 governs include/exclude survival. Within one feature, action order is top-to-bottom and later actions see the results of earlier ones.

### TC-09: Template Generation

Some domains may need template-generated artifacts.

**Architectural rule:** generation is supported through an optional domain-relative `template_script` executed once at the end of a successful trim run; domain-specific generation logic stays outside the Chopper core.

### TC-10: Boundary Discipline

Chopper must never accidentally reach and trim outside the domain trim scope.

### TC-11: Scan Quality

`chopper scan` must be good enough to reduce authoring effort without pretending that draft output is final truth.

**Risk:** a weak scan feature becomes noise and loses user trust.

---

## 10. Process Analysis and Operational Optimizations

### 10.1 Current Process Assessment

| Strength | Why It Matters |
|---|---|
| **Clear ownership** | Each domain owner owns one bounded slice of work |
| **Time-boxed trim window** | Creates delivery pressure and prioritization |
| **Per-domain isolation** | Keeps the product scope realistic |
| **Backup strategy** | Makes re-trim operationally safe |

| Risk | Why It Matters |
|---|---|
| **Authoring overhead** | Manual JSON creation is expensive without scan |
| **Tracing correctness** | Incorrect tracing breaks F2 output |
| **Validation late discovery** | Runtime failures are expensive during deployment windows |
| **Branch drift** | Long-lived project branches may miss fixes from mainline |


---

## 11. Question Ledger

### 11.1 Resolved Questions

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
| Q9 | What is the final conflict rule? | **Resolved** | Decision 5: include wins over exclude. |
| Q10 | How are procs identified? | **Resolved** | File + canonical proc name. |
| Q11 | How is top-level Tcl outside procs handled? | **Resolved** | Copy-and-delete model. |
| Q12 | How are hook files handled? | **Resolved** | Hook files discovered through `-use_hooks` are captured in scan output, but they are copied only if explicitly included in selected JSON; otherwise they are ignored during trim. |
| Q13 | What does override mean? | **Resolved** | Step replacement (`replace_step`); stage replacement (`replace_stage`). Proc-level control uses `procedures.include` / `procedures.exclude` with tracing. |
| Q14 | Are backups deleted? | **Resolved** | Yes, on the last day during cleanup. |
| Q15 | Is scan part of the architecture? | **Resolved** | Yes. |
| Q16 | Is default action configurable? | **Resolved** | No. Default exclude is fixed. |
| Q17 | Is product implemented already? | **Resolved** | No. It is currently framework/scaffold plus architecture work. |
| Q18 | How is live trim made write-safe? | **Resolved** | Staging plus same-filesystem atomic promotion and restore rules. |
| Q19 | How is feature ordering interpreted? | **Resolved** | Selected feature order is authoritative; actions within a feature are top-to-bottom. |
| Q20 | How are warnings and errors represented? | **Resolved** | Stable machine-readable diagnostics with severity, code, location, and hint. |

### 11.2 Open Questions

| ID | Question | Status |
|---|---|---|
| OQ-01 | For `.stack` files, which domains generate them and which domains keep them as-is? | **Open — domain-specific** |
| OQ-02 | For each domain, what exact template-generated outputs are required under F3? | **Open — domain-specific** |
| OQ-03 | Which domains should be used first as implementation proving grounds? | **Open — decided by domain leadership** |

---

## 12. FAQ and Corner Cases

### 12.1 General FAQ

**Q: What is Chopper in one sentence?**  
Chopper is a per-domain trimming tool that keeps only the files, procs, and generated run artifacts needed for a project-specific flow.

**Q: Is Chopper a working product today?**  
No. The repository is still at framework/scaffold stage. The architecture is ahead of the implementation.

**Q: Who is the main user?**  
The primary user is the domain deployment owner.

**Q: What does Chopper replace conceptually?**  
It replaces manual trimming and parts of the FlowBuilder/SNORT/template-generation workflow for signoff domains where file-level trim/build is not feasible.

### 12.2 Trimming FAQ

**Q: What gets trimmed?**  
Domain-local files and Tcl proc definitions that are not required by the selected base and features.

**Q: What never gets trimmed?**  
Anything outside the selected domain trim scope, including `common/` infrastructure.

**Q: Does Chopper edit proc bodies?**  
No. It keeps or removes whole proc definitions only.

**Q: Does Chopper partially trim Perl or Python?**  
No. Non-Tcl files are file-level only.

**Q: What happens if a file is both proc-trimmed and full-file included?**  
The full-file include wins only if some selected JSON explicitly requested the file in `files.include`.

**Q: Can tracing alone force a full file to survive?**  
No. Tracing can justify proc survival, not implicit file-level promotion.

### 12.3 Tracing FAQ

**Q: Why is tracing so important?**  
Because without tracing, proc-level trimming collapses back into manual dependency bookkeeping, which destroys the main product value.

**Q: What if proc A calls proc B and proc B calls proc C?**  
If A is explicitly kept, tracing attempts to keep B and C as well, as long as those dependencies are statically provable and within the domain boundary.

**Q: What if tracing sees `$cmd $args`?**  
That is dynamic dispatch. Chopper warns conservatively and does not invent a dependency.

**Q: What if tracing needs a proc from a file that the JSON never mentioned?**  
Chopper warns. Because default exclude is fixed, the owner must explicitly add the missing file or proc.

**Q: Does Chopper trace into `common/`?**  
No. `common/` is treated as external infrastructure.

**Q: Can tracing be turned off globally?**  
Not in the current architecture baseline. Default-on tracing is a core product rule.

### 12.4 F3 FAQ

**Q: Why are F3 steps plain strings instead of structured objects?**  
Because the real step vocabulary is heterogeneous: filenames, raw Tcl commands, ivar expressions, conditionals, and optional flags all coexist. Plain strings keep the model practical.

**Q: What is the downside of plain-string steps?**  
Chopper cannot semantically understand every arbitrary string. It can compose and partially validate, but not fully interpret all Tcl content.

**Q: Why is that acceptable?**  
Because forcing a deeply typed model for all step content would make the tool more brittle and harder to adopt than the problem justifies.

**Q: How is that risk controlled?**  
By validation, optional cross-validation, trace reporting, and domain-owner review.

### 12.5 Backup and Re-trim FAQ

**Q: Why keep backups in the branch at all?**  
Because the trim window requires safe re-trim capability without depending on manual restore work.

**Q: Why not delete backups immediately?**  
Because requirements can change during the trim window and owners need deterministic rebuild from the original domain source.

**Q: When are backups deleted?**  
On the last day during final cleanup.

### 12.6 Scan FAQ

**Q: Is `chopper scan` a convenience feature or a real product feature?**  
It is a real architecture feature.

**Q: Does scan replace domain-owner judgment?**  
No. It produces drafts and inventories. The domain owner still owns final curation.

**Q: Why include proc call graphs in scan output?**  
Because tracing is the main product differentiator and the draft authoring flow should expose the same dependency model users rely on during trim.

### 12.7 Corner Case FAQ

**Q: What if two features disagree about a proc?**  
If one includes it and another excludes it, the proc survives.

**Q: What if two features replace the same step differently?**  
Selected input ordering governs explicit `replace_step` and `replace_stage` conflicts.

**Q: What if a file ends up with no procs left after trimming?**  
The file is kept. If only blank lines and comments remain after proc deletion, Chopper writes that remaining stub, emits V-24, and leaves owner review in the workflow. If the same file was also explicitly requested in `files.include`, the full-file copy rule still applies and the file survives as a whole file.

**Q: What if a hook file exists but is not needed?**  
Hook discovery is not permission for silent bloat. Hook files stay out unless they are explicitly included in selected JSON.

**Q: What if a feature excludes a base item?**  
It does not win. The selected base still includes it, so the item survives.

**Q: What if a proc is defined twice in one file?**  
The last definition wins, matching Tcl runtime behavior.

**Q: What if a domain does not need F3?**  
Then the domain can use any combination of F1, F2, and F3 that fits the domain.

**Q: What if a domain needs only F3 and no trimming?**  
That is valid. F3-only remains a supported capability combination.

**Q: Can an LLM use this document safely?**  
Yes. The document is intentionally explicit about boundaries, defaults, resolved rules, and corner cases so that both humans and LLMs can follow the same architecture contract.

---

## 13. Reference Documents and External Inputs

| Document | Purpose |
|---|---|
| `docs/TECHNICAL_REQUIREMENTS.md` | Defines implementation standards, runtime contracts, CLI engineering behavior, and test gates |
| Python logging cookbook | Confirms that library code should not configure global logging handlers |
| Python `argparse` docs | Confirms subcommand-oriented CLI structure for `scan`, `validate`, `trim`, and `cleanup` |
| Python `pathlib`, `tempfile`, and `os.replace` docs | Support deterministic path handling, safe temp writes, and atomic promotion |
| `jsonschema` documentation | Supports the Phase 1 schema-validation contract |
| pytest good practices and Hypothesis docs | Support the layered fixture plus property-based test strategy |

---

## 14. Implementation Work Queue

### 14.1 Priority Work Items

| ID | Action | Priority | Status |
|---|---|---|---|
| **AI-01** | Build and validate the Tcl parser / lexer prototype, proc index, and brace-aware structure checker against real domain files | **P0** | Not started |
| **AI-02** | Implement `chopper scan` with file inventory, proc inventory, and dependency graphs | **P0** | Not started |
| **AI-03** | Implement compiler logic for FI / FE / PI / PE, ordered feature application, and Decision 5 | **P0** | Not started |
| **AI-04** | Implement F2 copy-and-delete trimming engine plus staging writer and promote/restore flow | **P0** | Not started |
| **AI-05** | Implement audit trail generation under `.chopper/` with the artifact contracts in Section 5.4 | **P1** | Not started |
| **AI-06** | Ship JSON Schema files and semantic validators for base, feature, and project JSONs | **P1** | Not started |
| **AI-07** | Implement validation (Phase 1 + Phase 2), diagnostics, exit codes, and standalone `chopper validate` command | **P0** | Not started |
| **AI-08** | Implement F3 generation and template hook integration behind a narrow generator interface | **P1** | Not started |
| **AI-09** | Implement dry-run mode (full pipeline simulation without file writes) | **P0** | Not started |
| **AI-10** | Build fixture, golden, integration, and property-based tests for tracing, trimming, and retrim flows | **P0** | Not started |
| **AI-11** | Implement `chopper cleanup` and the explicit last-day backup removal workflow | **P1** | Not started |
| **AI-12** | Implement CLI logging setup and module-scoped diagnostic plumbing | **P1** | Not started |

### 14.2 Operational Follow-Ups

| ID | Action | Priority | Status |
|---|---|---|---|
| **OP-01** | Define per-domain F3 expectations for stack/run outputs | **P1** | Open |
| **OP-02** | Approve operational ownership and timing for executing `chopper cleanup` on the last day | **P1** | Open |
| **OP-03** | Establish domain-owner feature catalog conventions: naming standard, central registry, and review expectations | **P2** | Open |

### 14.3 Near-Term Business Priorities (1-Week Horizon)

| ID | Item | Description |
|---|---|---|
| **BP-01** | Define architecture-to-implementation gate criteria | What triggers the transition from docs-first to implementation-first |
| **BP-02** | Resolve OQ-03 (proving-ground domain) | Unblocks AI-10 (real-domain test fixtures) |
| **BP-03** | Complete adoption risk assessment | Authoring overhead, scan trust, learning-curve during 2-week window |
| **BP-04** | Define feature catalog convention | Naming standard, central registry, and review expectations |

### 14.4 Deferred Until Spec Finalization

| ID | Item | Rationale |
|---|---|---|
| **DF-01** | Add quick-start section to architecture doc | Deferred until spec is final |
| **DF-02** | Add example error/warning messages to doc | Deferred until spec is final |
| **DF-03** | Add terminology note distinguishing "capability" from "feature JSON" | Deferred until spec is final |

---

## 15. Revision History

| Date | Change |
|---|---|
| 2026-04-03 | Initial draft — problem statement, terminology, roles, high-level workflow, requirements. |
| 2026-04-03 | Rev 2 — corrected scope to per-domain trimming; added project branch lifecycle and process analysis. |
| 2026-04-04 | Rev 4 — proc-level trimming model, compilation model, audit trail design, technical challenges deep dive. |
| 2026-04-04 | Rev 5 — real codebase analysis for FEV, STA/PT, and Power; common exclusion; `iproc_source` handling; non-Tcl decision. |
| 2026-04-04 | Rev 6 — FlowBuilder and Proposal 1 analysis; three-feature architecture; JSON design principles. |
| 2026-04-04 | Rev 7 — default-on tracing, backup strategy, include-wins semantics, and cross-validation concepts refined. |
| 2026-04-04 | Rev 8 — canonical proc naming, copy-and-delete model, hook handling, trim stats, VCS-agnostic manifest, action items. |
| 2026-04-04 | **Rev 9 — consolidated rewrite:** deduplicated repeated content, normalized resolved/open question state, fixed Decision 5 ambiguity, made default exclude final, limited file-level promotion to explicit file requests only, elevated scan into the architecture, clarified that the product is still framework-stage, expanded tracing rationale, and added FAQ/corner-case coverage. |
| 2026-04-04 | **Rev 10:** added `replace_step` (F3 step replacement) and `replace_stage` (F3 stage replacement) as new action keywords (9 total); defined `procs: []` as hard error with actionable fix guidance; removed `depends`, `related_ivars`, and `exit_codes` from Feature JSON schema; added scan pipeline diagram; expanded canonical proc naming rules with namespace examples; file with zero surviving procs is deleted; idempotency guarantee added; partial-failure recovery model defined; EXPERIMENTAL-TRACE graduation criteria added; dry-run made mandatory; near-term business priorities and deferred items tracked. |
| 2026-04-04 | **Rev 11:** added Section 5.7 Validation Model with three formal phases: Phase 1 (pre-trim JSON quality, 12 checks), Phase 2 (post-trim output correctness, 6 checks), Phase 3 (dry-run full pipeline simulation). Standalone `chopper validate` command specified. AI-07 and AI-09 promoted to P0. FR-28 and FR-29 added. |
| 2026-04-05 | **Rev 12:** formalized trace expansion and proc index contracts; defined `source` / `iproc_source` / hook semantics; added immutable compilation, audit artifact, determinism, staging, restore, CLI, diagnostics, exit-code, and Python implementation guidance; defined path/glob semantics and action ordering; added layered test strategy; corrected FlowBuilder reference paths; expanded implementation work queue. |
| 2026-04-05 | **Rev 13:** split implementation-level guidance into `docs/TECHNICAL_REQUIREMENTS.md`; moved detailed runtime, validation, CLI, Python, and testing requirements out of the architecture document so this document stays architecture-focused. |
| 2026-04-04 | **Rev 14:** Closed 28 architecture review gaps. Added §2.8.1 Domain Lifecycle State Machine (GAP-02). Expanded §3.7 scan-to-trim workflow (GAP-03). Added `@n` instance targeting to §6.7 (GAP-04). Added optional `metadata` block to Feature JSON §6.5 (GAP-05). Added `!feature` negation to Out of Scope §2.2 — permanently removed, no V2 (GAP-08). Removed `replace_proc` action entirely — action count now 9 (GAP-13). Proc-level control uses `procedures.include`/`procedures.exclude` with tracing. Created `docs/TCL_PARSER_SPEC.md` (GAP-09). Created JSON Schema files under `schemas/` (GAP-12). Glob patterns now support `*`, `?`, `**` (GAP-10). |
| 2026-04-05 | **Rev 15:** Added per-domain advisory locking for mutating commands during the shared-branch trim window. |
| 2026-04-05 | **Rev 16:** Corrected `options.template_script` semantics: it is a domain-relative script path under the selected domain, preserved as required output, and executed once at the end of a successful `trim` run before Chopper exits. |
| 2026-04-05 | **Rev 17:** Tightened the source-of-truth scan contract by delegating exact artifact field contracts for all scan artifacts to `docs/TECHNICAL_REQUIREMENTS.md`, and clarified that advisory-lock stale/orphan cleanup never breaks a live `flock()` lock. |
| 2026-04-05 | **Rev 18:** Added full project JSON input mode coverage. Added §5.1 Input Modes (base-only, base+features, project JSON) with mutual exclusivity rules. Expanded §6.6 Project JSON Structure with required/optional fields, path resolution rules, CLI usage examples, and audit traceability. Updated §5.1.1 invocations, §5.3 compilation model, §5.8 CLI contract stub, and scan-to-trim workflow to include project JSON paths. Added FR-35 (accept project JSON) and FR-36 (mutual exclusivity). Updated acceptance criteria. Updated hook semantics in §4.1, §4.3 to match explicit-JSON-inclusion rule. |
| 2026-04-05 | **Rev 19:** Corrected the parser contract to match Tcl Rule 6 for quotes inside braced proc bodies. Clarified that omitted F1/F2/F3 capability blocks are treated as empty. Made project JSON mode explicitly semantics-equivalent to direct `--base`/`--features` mode, requiring the same effective domain when both `--project` and `--domain` are provided. Removed formal schema-ID wording for runtime artifacts and aligned audit wording around saved inputs and documented field contracts. |
| 2026-04-05 | **Rev 20:** Standardized the default owner-curated JSON layout under each domain to `jsons/base.json` and `jsons/features/*.json`. Updated per-domain structure, scan-to-trim workflow, CLI examples, project JSON examples, and path-resolution wording to reflect the `jsons/` convention. Clarified that project JSON itself has no fixed default location and is always supplied explicitly via `--project <path>`. |
| 2026-04-05 | **Rev 21:** Clarified that normal v1 operation runs Chopper from the domain root and resolves project `base`/`features` paths from the current working directory rather than the project JSON location. Reworked Decision 5 so excludes remain meaningful by pruning only wildcard-expanded file candidates and trace-derived proc candidates while explicit includes still win. Added a deterministic namespace lookup contract for trace resolution, normalized cross-domain trace diagnostics to `TRACE-CROSS-DOMAIN-01`, aligned `@n` overflow to V-12, and changed empty F2 output to survive with V-24 instead of deleting the file. |
| 2026-04-05 | **Rev 22:** Resolved pre-coding review items B-06, B-08, H-19. Made trace expansion explicitly breadth-first with lexicographically sorted frontier (B-08). Added `TRACE-CYCLE-01` diagnostic for circular proc call graphs (H-19). Added explicit FE∩PI+ → PROC_TRIM file treatment derivation rule and its accompanying compiler warning to Decision 5 implications (B-06). Added file treatment derivation algorithm (FULL_COPY / PROC_TRIM / GENERATED / REMOVE). |