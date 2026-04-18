
# Chopper Technical Presentation Deck

## How To Use This File

- One-slide-per-section format for direct PowerPoint authoring.
- Each slide: title, subtitle, on-slide bullets, speaker notes, visual recommendation.
- Keep on-slide text concise; use speaker notes for engineering depth.
- Mermaid diagrams for every visual are provided in a companion file: `docs/TECHNICAL_PRESENTATION_DIAGRAMS.md`.
- Recommended deck length: 20 to 25 minutes.

---

## Slide 1 — Title Slide

**Title:** Chopper

**Subtitle:** Technical Architecture for Domain-Aware Trimming of EDA Tool Flows

**On-Slide Content:**

- Static-analysis-driven trim engine for CTH R2G tool-flow domains
- Designed to turn large generalized TFM domains into project-specific thin deployments
- Built for per-domain isolation, deterministic output, safe re-trim, and full auditability

**Speaker Notes:**

Chopper is a domain-scoped trimming system for EDA Tool Flow Manager codebases. Its purpose is to reduce a large, generalized flow domain into the minimal project-specific subset that a delivery owner actually needs. The core value is controlled reduction with traceability, deterministic behavior, and recovery-safe domain lifecycle handling.

**Visual:** See Diagram 1 — Title Graphic

---

## Slide 2 — Problem Context

**Title:** Why Chopper Exists

**Subtitle:** The operational problem inside CTH R2G TFM domains

**On-Slide Content:**

- Each domain ships with full feature breadth, legacy logic, and customer-specific variants
- Domain owners work on a shared project branch under a strict 2-week trim window
- Manual trimming is slow, risky, and hard to validate
- Flow logic is tightly coupled through Tcl procs, sourced files, and indirect dependencies
- All signoff and analysis domains, ~6000 users — the system needs safe, repeatable reduction

**Speaker Notes:**

The core issue is domain bloat under delivery pressure. A domain contains far more logic than a single project should carry. Manual edits are dangerous because dependencies are intertwined across Tcl procs and sourced files. Chopper enables explainable, auditable, and safe reduction instead of ad hoc deletion.

**Visual:** See Diagram 2 — Before/After Domain Reduction

---

## Slide 3 — Decision Tree: FlowBuilder vs Chopper

**Title:** Which System Do I Use?

**Subtitle:** Onboarding decision tree for domain owners

**On-Slide Content:**

```
START: What does your flow look like?
  │
  ├─ Q1: Is your domain apr_fc (Fusion Compiler)?
  │   ├─ YES ──► Q2
  │   └─ NO  ──► USE CHOPPER (FlowBuilder does not support your domain)
  │
  ├─ Q2: Is your flow file-based (steps = file sources)?
  │   ├─ YES ──► Q3
  │   └─ NO  ──► USE CHOPPER (FlowBuilder has no proc awareness)
  │
  ├─ Q3: Do you need proc-level trimming (remove unused procs from shared libs)?
  │   ├─ YES ──► USE CHOPPER (FlowBuilder is file-level only)
  │   └─ NO  ──► Q4
  │
  ├─ Q4: Do you want to KEEP static run files and trim domain content?
  │   ├─ YES ──► USE CHOPPER (trim + dynamic run-file generation)
  │   └─ NO  ──► Q5
  │
  └─ Q5: Are you happy with FlowBuilder generating run scripts from JSON?
      ├─ YES ──► KEEP USING FLOWBUILDER (it works for your workflow)
      └─ NO  ──► USE CHOPPER
```

**Decision Summary Table (on-slide):**

| Your situation | Use |
|---|---|
| apr_fc, file-based steps, no proc trimming needed, run-file generation is fine | **FlowBuilder** |
| apr_fc, but you need proc-level trimming or static run files | **Chopper** |
| Any other domain (sta_pt, fev_formality, power, etc.) | **Chopper** |
| You need to trim unused code, not just reorder file sources | **Chopper** |
| You need audit trail, backup lifecycle, dependency tracing | **Chopper** |

**Speaker Notes:**

The key distinction is direction: FlowBuilder builds UP (assembles run scripts from JSON + feature configs). Chopper trims DOWN (removes unused files and procs from a full domain). FlowBuilder is apr_fc/rtlfp only, operates at file-level only, and has zero awareness of what is inside the sourced files — unused procs, dead paths, and legacy logic all still ship. Chopper covers all signoff and analysis domains, operates at proc-level within Tcl files, and traces transitive call dependencies.

An important subtlety: FlowBuilder applies full semantic intelligence when constructing run scripts — it classifies every command in a step (iproc_source call, proc invocation, conditional, comment) and wires them correctly. Chopper's F3 run-file generation is string-based and does not apply that level of intelligence. If you are on apr_fc/rtlfp and need intelligent run-script construction, FlowBuilder is the right tool.

Also important for FlowBuilder users: files that are not referenced in run scripts are invisible to SNORT. You must explicitly configure SNORT to keep them — this means maintaining two separate config surfaces (the flow JSON and SNORT config). Chopper handles this natively via files.include/files.exclude with no separate tool required.

For apr_fc users already on FlowBuilder: keep using it. Switch to Chopper only if you need proc-level trimming or have files that must survive trimming outside the run-script dependency graph.

**Visual:** See Diagram 3 — Decision Tree Flowchart

---

## Slide 4 — FlowBuilder vs Chopper: System Comparison

**Title:** FlowBuilder vs Chopper — Head to Head

**Subtitle:** Two systems, fundamentally different operating models

**On-Slide Content:**

| Dimension | FlowBuilder | Chopper |
|---|---|---|
| **Direction** | Builds UP (assembles run scripts from JSON + feature configs) | Trims DOWN (removes unused from full domain) |
| **Domain coverage** | apr_fc, rtlfp only | All signoff and analysis domains |
| **Granularity** | File-level only | File-level + Tcl proc-level |
| **Run-script construction** | Full semantic parsing — classifies every command (iproc_source, proc call, conditional, comment) with intelligence | F3 feature available but string-based only — no command-level intelligence |
| **Code awareness** | Knows which files are sourced; zero visibility inside files | Static analysis: proc index, call graph, transitive dependency tracing |
| **File pass-through** | Files not in run scripts are invisible to SNORT — must be manually configured in SNORT config separately | Native: `files.include` / `files.exclude` keep any file regardless of run-script reference |
| **Trimming** | None — full code ships; only ordering changes | Surgical: removes files, procs, and unreachable dead code |
| **Config surface** | Two places: flow JSON (run script content) + SNORT config (file filter template) | One place: JSON only |
| **Backup/re-trim** | No concept | Formal backup lifecycle with state machine |
| **Audit trail** | No | Full audit package: manifest, graph, report, saved inputs |
| **Validation** | No schema validation | Schema-validated + 2-phase structural/semantic checks |
| **Trigger** | Every `Ifc_shell` startup (run-script regeneration) | Explicit operator invocation |

**Speaker Notes:**

FlowBuilder's generated `run_<stage>.tcl` files are built with full semantic intelligence — it reads every command inside a step and classifies it: an iproc_source file source, a proc call, an if/else/endif conditional block, or a comment. This intelligence is what makes the assembled run scripts correct. SNORT then walks those run scripts to find all transitively sourced files and constructs the P4 filter template. Any file not reached by SNORT's traversal is not included unless you explicitly tell SNORT to keep it — a separate configuration step that is easy to miss.

Chopper's F3 (run-file generation) feature produces run scripts, but it works by string-processing the step list — it does not apply FlowBuilder's command-level semantic classification. For signoff domains where the run scripts are simpler and the main problem is domain bloat, this is sufficient. For apr_fc/rtlfp where the run-script construction complexity is the point, FlowBuilder is the right tool and should stay in place.

**Visual:** See Diagram 4 — Side-by-Side Comparison Chart

---

## Slide 5 — JSON Model Comparison: FlowBuilder vs Chopper vs Standard

**Title:** JSON Schema Design: Anti-Pattern vs Standard

**Subtitle:** Why Chopper's JSON model is structurally superior

**On-Slide Content — FlowBuilder's "Data as Keys" Anti-Pattern:**

```json
{
    "stages": ["import_design", "read_upf"],
    "import_design": { "load_from": "", "steps": [...] },
    "read_upf": { "load_from": "import_design", "steps": [...] }
}
```

- Top-level keys are **data-dependent** — shape changes when stages are added/removed
- Fixed metadata keys (`owner`, `stages`) share namespace with dynamic stage keys
- JSON Schema can only use `additionalProperties: true` — **no real validation possible**
- Feature JSON overloads item IDs as filenames, requires `_0` suffix hacks for duplicates

**On-Slide Content — Chopper's Standards-Compliant Model:**

```json
{
    "$schema": "chopper/base/v1",
    "stages": [
        { "name": "import_design", "load_from": "", "steps": [...] },
        { "name": "read_upf", "load_from": "import_design", "steps": [...] }
    ]
}
```

- Top-level keys are **fixed and statically known** — `additionalProperties: false`
- Stages are an **array of typed objects** — order is intrinsic, schema is complete
- Fully validatable with JSON Schema Draft-07 (RFC draft-handrews-json-schema-01)
- IDE autocompletion, linting, and refactoring all work without custom tooling

**Speaker Notes:**

The JSON Schema specification (Draft-07, which Chopper uses, references RFC 8259 for JSON syntax) defines a vocabulary for annotating and validating JSON documents. When top-level keys are data-driven, the schema cannot describe or validate them — everything falls into an `additionalProperties` catch-all. FlowBuilder has this exact problem: its apr_fc.json has 24 top-level keys, only 6 are fixed, the other 17 are stage names.

Chopper's model follows the standard design principle: arrays of objects instead of objects-as-maps. This means every key at every level is statically known, the schema is self-describing, and standard validators can check the full document without custom code. RFC 8259 also specifies that JSON objects are unordered — FlowBuilder relies on a separate `stages` array for ordering but scatters the data across top-level keys. Chopper keeps ordering and data in the same array, eliminating the dual-source-of-truth problem.

**Reference Standards:**
- JSON syntax: RFC 8259 (IETF STD 90)
- JSON Schema: Draft-07 (`http://json-schema.org/draft-07/schema#`)
- JSON Schema Validation: `draft-handrews-json-schema-validation-01`

**Visual:** See Diagram 5 — JSON Structure Comparison

---

## Slide 6 — JSON Anti-Pattern Deep Dive

**Title:** The "Data as Keys" Problem in Detail

**Subtitle:** Concrete consequences for validation, tooling, and maintenance

**On-Slide Content:**

| Problem | FlowBuilder Impact | Chopper Avoidance |
|---|---|---|
| **Schema completeness** | `additionalProperties: true` — catch-all, no real validation | `additionalProperties: false` — every key validated |
| **Key collision risk** | Stage named `"description"` collides with metadata key | Fixed keys only — impossible |
| **Dual source of truth** | `stages` array = order, top-level keys = data — can desync | Array of objects = single source |
| **Duplicate items** | Requires `_lo`, `_id`, `_0` suffix hacks | Multiple array entries (natural) |
| **Two-pass parsing** | Read index array, then look up keys | One-pass: iterate array |
| **IDE support** | Broken for dynamic keys — no autocompletion | Full autocompletion and validation |
| **Refactoring** | Rename requires 3+ places | Rename requires 1 place (`name` field) |

**Feature JSON is Worse:**

```json
{
    "name": ["step_csi_load_spec.tcl", "csi", "csi_stage_bundle"],
    "step_csi_load_spec.tcl": { "action": "add_step_after", ... },
    "csi": { "action": "add_stage_after", ... }
}
```

- `name` array mixes filenames, stage names, and invented identifiers — no type distinction
- You must read each key's `action` field to determine what it actually is
- Same step in two stages requires invented suffixes: `step_clock_stamping.tcl_lo`

**Speaker Notes:**

Per RFC 8259 §4: "The names within an object SHOULD be unique." FlowBuilder does enforce uniqueness, but works around the constraint with suffix hacks when the same logical step appears in multiple contexts. The JSON Schema specification (§6.5.6 `additionalProperties`) explicitly calls out the limitation: when the set of property names is not known at schema-authoring time, validation is incomplete. Chopper avoids this entirely by never using data values as property names.

**Visual:** See Diagram 6 — Anti-Pattern Anatomy

---

## Slide 7 — Chopper JSON Schema Reference

**Title:** Chopper's Three-Schema Model

**Subtitle:** Base, Feature, and Project — each with a clear contract

**On-Slide Content:**

| Schema | File | Purpose | Required Fields |
|---|---|---|---|
| **Base v1** | `chopper/base/v1` | Minimum viable flow for a domain | `$schema`, `domain` |
| **Feature v1** | `chopper/feature/v1` | Extension that adds/removes/replaces | `$schema`, `name` |
| **Project v1** | `chopper/project/v1` | Reproducible selection for CI/audit | `$schema`, `project`, `domain`, `base` |

**Base JSON capabilities:**

- `files.include` / `files.exclude` — whole-file ops with glob support
- `procedures.include` / `procedures.exclude` — proc-level ops as `[{file, procs}]`
- `stages` — ordered array of `{name, load_from, steps, command?, inputs?, outputs?, run_mode?}`
- `options.template_script` — post-trim script hook

**Feature JSON capabilities (all of the above plus):**

- `flow_actions` — ordered array of 9 action types (7 from FlowBuilder + 2 Chopper additions)
- `metadata` — informational block (tags, wiki, related_ivars, owner)

**Chopper Action Vocabulary (9 actions):**

| Action | Origin | Purpose |
|---|---|---|
| `add_step_before` | FlowBuilder | Insert steps before reference |
| `add_step_after` | FlowBuilder | Insert steps after reference |
| `add_stage_before` | FlowBuilder | Insert stage before reference |
| `add_stage_after` | FlowBuilder | Insert stage after reference |
| `remove_step` | FlowBuilder | Remove step from stage |
| `remove_stage` | FlowBuilder | Remove entire stage |
| `load_from` | FlowBuilder | Change stage data dependency |
| `replace_step` | **Chopper** | Replace step with substitute |
| `replace_stage` | **Chopper** | Replace entire stage definition |

**Speaker Notes:**

Chopper adopts FlowBuilder's entire 7-action vocabulary so apr_fc owners can express the same feature directives without learning new semantics. The two Chopper additions (`replace_step`, `replace_stage`) address a gap where FlowBuilder required paired remove+add to achieve replacement. Instance targeting with `@n` suffix handles duplicate steps within a stage — no invented suffix hacks needed.

All three schemas use JSON Schema Draft-07 (`$schema: "http://json-schema.org/draft-07/schema#"`) and enforce `additionalProperties: false` at every level.

**Visual:** See Diagram 7 — Three-Schema Relationship

---

## Slide 8 — Process Flow: End-to-End Workflow

**Title:** Operator Workflow: From Scan to Cleanup

**Subtitle:** The recommended onboarding and trim lifecycle

**On-Slide Content:**

```
 PHASE 1: DISCOVER                    PHASE 2: AUTHOR
 ─────────────────                    ──────────────────
 chopper scan                         Edit draft_base.json → jsons/base.json
   ├─ draft_base.json                 Create jsons/features/*.json
   ├─ file_inventory.json             (Optional) Create project.json
   ├─ proc_inventory.json
   ├─ dependency_graph.json
   └─ scan_report.json

 PHASE 3: VALIDATE                    PHASE 4: TRIM
 ──────────────────                   ─────────────────
 chopper validate --base ...          chopper trim --dry-run --base ...
   ├─ Phase 1 structural checks       ├─ Full pipeline simulation
   ├─ Schema compliance                ├─ No files modified
   └─ File/proc existence             └─ Review output

                                      chopper trim --base ...
                                        ├─ domain/ → domain_backup/
                                        ├─ Build trimmed domain/
                                        ├─ Phase 2 post-trim checks
                                        └─ Emit .chopper/ audit trail

 PHASE 5: ITERATE                     PHASE 6: FINALIZE
 ────────────────                     ──────────────────
 (Adjust JSONs → re-validate →       chopper cleanup --confirm
  re-trim from backup)                  └─ Remove domain_backup/ (irreversible)
```

**Speaker Notes:**

This six-phase lifecycle is the recommended onboarding path for any domain. Phase 1 (scan) generates machine-produced drafts that the domain owner curates. Phase 3 (validate) catches errors before any file mutation. Phase 4 (trim) supports dry-run for safe preview. The backup lifecycle in Phase 5 enables safe iteration without losing the original domain. Phase 6 is irreversible and requires explicit confirmation.

**Visual:** See Diagram 8 — Six-Phase Workflow

---

## Slide 9 — Execution Pipeline Internals

**Title:** Trim Engine Pipeline

**Subtitle:** The seven-stage compilation and trim pipeline

**On-Slide Content:**

```
  ┌──────────────────────┐
  │ 0. Detect trim state │  FRESH vs re-trim
  └──────────┬───────────┘
             ▼
  ┌──────────────────────┐
  │ 1. Read inputs       │  base + features (or project JSON)
  └──────────┬───────────┘
             ▼
  ┌──────────────────────┐
  │ 1.5 Phase 1 validate │  Schema + structural pre-checks
  └──────────┬───────────┘
             ▼
  ┌──────────────────────┐
  │ 2. Compile selections│  FI / FE / PI / PE resolution
  └──────────┬───────────┘
             ▼
  ┌──────────────────────┐
  │ 3. Trace proc deps   │  BFS: PI → PI+
  └──────────┬───────────┘
             ▼
  ┌──────────────────────┐
  │ 4. Build output      │  File copy + proc extraction + F3
  └──────────┬───────────┘
             ▼
  ┌──────────────────────┐
  │ 5. Phase 2 validate  │  Post-trim verification
  └──────────┬───────────┘
             ▼
  ┌──────────────────────┐
  │ 6. Emit audit trail  │  .chopper/ package
  └──────────────────────┘
```

**Speaker Notes:**

Chopper is a compiler pipeline for domain reduction. Steps 2-3 are where the core intelligence lives: the compilation phase resolves include/exclude conflicts using Decision 5 (include wins), and the trace phase performs breadth-first expansion with sorted frontier for determinism. The build phase produces three types of output: FULL_COPY (whole file), PROC_TRIM (extracted procs only), and GENERATED (F3 run-script generation).

**Visual:** See Diagram 9 — Pipeline Flowchart

---

## Slide 10 — Scope and Product Boundary

**Title:** Scope Model

**Subtitle:** What the system does and does not do

**On-Slide Content:**

| In Scope | Out of Scope |
|---|---|
| Per-domain trimming | Repo-wide global graph trimming |
| Whole-file include/exclude | Non-Tcl subroutine-level trimming |
| Tcl proc-level extraction | Full runtime Tcl evaluation |
| Transitive dependency tracing | Dynamic behavior inference (`eval`, `$cmd`) |
| Backup and re-trim lifecycle | Cross-domain dependency resolution |
| Audit trail and reproducibility | `!feature` negation syntax |
| Draft JSON generation (scan) | Trimming `common/` infrastructure |
| Run-file generation (F3) | Partial Perl/Python/csh trimming |

**Speaker Notes:**

Chopper is intentionally conservative. It performs deterministic static analysis within one selected domain and escalates unresolved dynamic patterns as diagnostics. `common/` is treated as always-available infrastructure and is never trimmed. Cross-domain dependencies do not materially exist in practice; if discovered later, they may be added as a future validation pass.

**Visual:** See Diagram 10 — Scope Boundary

---

## Slide 11 — Architecture Layering

**Title:** Layered System Design

**Subtitle:** Presentation, service, and core engine separation

**On-Slide Content:**

```
┌─────────────────────────────────────────────┐
│            PRESENTATION LAYER               │
│  CLI (argparse) │ Rich/Plain renderer │ JSON │
│  Future: GUI, TUI, CI automation            │
├─────────────────────────────────────────────┤
│            SERVICE LAYER                    │
│  TrimService  │ ScanService │ ValidateService│
│  CleanupService                             │
│  Typed Request → execute() → Typed Result   │
├─────────────────────────────────────────────┤
│            CORE ENGINE                      │
│  Parser │ Compiler │ Tracer │ Trimmer       │
│  Validator │ Scanner │ Generators           │
├─────────────────────────────────────────────┤
│            SHARED CORE (core/)              │
│  models.py │ errors.py │ diagnostics.py     │
│  protocols.py │ serialization.py            │
└─────────────────────────────────────────────┘
```

**Speaker Notes:**

The service boundary is critical. Each command maps to a typed request/result pair. Services never print to stdout directly. The presentation layer owns rendering, color, and terminal width. Core logic depends on abstractions and typed contracts, not on terminal libraries. This makes the engine GUI-ready: a future GUI reads the same JSON format, uses the same serializer, and programs against the same service contracts.

**Visual:** See Diagram 11 — Architecture Stack

---

## Slide 12 — Static Analysis Engine

**Title:** Parser and Proc Index

**Subtitle:** The structural foundation for everything else

**On-Slide Content:**

- All Tcl files parsed in **lexicographic order** before tracing begins
- Parser builds a per-run **proc index** keyed by canonical identity
- Canonical form: `relative/path.tcl::qualified_name`
- Each entry records: source file, namespace path, proc span, body span, call sites
- Duplicate canonical names are **errors**, not silent overwrites
- Context-type stack tracks: `FILE_ROOT`, `NAMESPACE_EVAL`, `CONTROL_FLOW`

**Example Proc Index Entry:**

| Field | Value |
|---|---|
| `canonical_name` | `flow_procs.tcl::setup_library_paths` |
| `source_file` | `flow_procs.tcl` |
| `qualified_name` | `setup_library_paths` |
| `namespace_path` | `` (global) |
| `start_line` / `end_line` | `42` / `67` |
| `body_start_line` / `body_end_line` | `43` / `66` |

**Speaker Notes:**

The proc index is the source of truth for proc-level trimming and dependency expansion. Chopper does not trace against raw text heuristics alone. It first builds a structured domain-wide index with canonical names, file paths, namespace context, and precise source spans. That makes later decisions deterministic and auditable. The parser handles namespace eval nesting, backslash line continuations, brace-in-string literals, and adversarial edge cases (14 fixtures in the test suite).

**Visual:** See Diagram 12 — Proc Index Structure

---

## Slide 13 — Trace Expansion Algorithm

**Title:** Dependency Tracing Under The Hood

**Subtitle:** Deterministic BFS expansion from PI to PI+

**On-Slide Content:**

**Algorithm:**
1. Parse all domain Tcl files in lex-sorted order → build proc index
2. Seed frontier with explicit `procedures.include` entries (sorted)
3. Pop smallest canonical name from frontier
4. If already traced, skip. Otherwise add to traced set
5. Extract: direct calls, bracketed calls, `source`/`iproc_source` edges
6. Resolve namespace with deterministic lexical rules
7. Append resolved callees to frontier (sorted)
8. Repeat until frontier is empty

**Diagnostic Emissions:**

| Code | Trigger |
|---|---|
| `TRACE-AMBIG-01` | Multiple procs match a qualified name |
| `TRACE-CROSS-DOMAIN-01` | No in-domain match found |
| `TRACE-UNRESOLV-01` | Dynamic/syntactically unresolvable call (`$cmd`, `eval`) |
| `TRACE-CYCLE-01` | Cycle detected (both procs included conservatively) |

**Speaker Notes:**

The trace walk is fixed-point, breadth-first, with lexicographically sorted frontier. This ensures identical output regardless of filesystem walk order, OS locale, or directory structure. The tracer never guesses across ambiguous candidates and never crosses the domain boundary. Cycles are terminated naturally (already-traced procs are not re-added to frontier) and both procs in a cycle are included conservatively.

**Visual:** See Diagram 13 — Trace Expansion Walk

---

## Slide 14 — Selection Semantics (Decision 5)

**Title:** Include/Exclude Resolution

**Subtitle:** The rule system that makes trim behavior predictable

**On-Slide Content:**

**Resolution Algorithm (11-step):**
1. Partition `files.include` → **FI_literal** (exact paths) + **FI_glob** (patterns → expanded)
2. Compile `files.exclude` → **FE**
3. Compile `procedures.include` → **PI**; `procedures.exclude` → **PE**
4. Trace PI → **PI+** (with BFS expansion)
5. Traced-only procs: **PT = PI+ − PI**
6. Surviving files: **FI_literal ∪ (FI_glob − FE)**
7. Surviving procs: **PI ∪ (PT − PE)**

**File Treatment Derivation:**

| Condition | Treatment |
|---|---|
| File in surviving full-file set | `FULL_COPY` |
| File contains surviving procs (PI+) | `PROC_TRIM` |
| File targeted by F3 generator | `GENERATED` |
| Everything else | `REMOVE` |

**The Core Rule:** Explicit include **always wins** over exclude.

**Speaker Notes:**

This means a file can survive as PROC_TRIM even if it appears in `files.exclude`, because proc-level include-wins takes precedence. Selected features cannot remove something that the base or another selected feature explicitly requested. Wildcard-expanded files and trace-derived procs CAN still be pruned by excludes — the protection applies only to explicit entries.

**Visual:** See Diagram 14 — Resolution Flow

---

## Slide 15 — Write Safety and Re-Trim Lifecycle

**Title:** Filesystem Lifecycle and State Machine

**Subtitle:** Backup-and-rebuild, never in-place mutation

**On-Slide Content:**

**State Machine:**

```
  FRESH ──────► BACKUP_CREATED ──────► STAGING ──────► TRIMMED ──────► CLEANED
    │                  │                    │                │
    │                  │                    │                │
    │            (crash: rerun         (crash: remove    (re-trim:
    │             detects BACKUP)       staging, stay     rebuild from
    │                                   BACKUP_CREATED)   backup)
```

**Invariants:**
- At any point: valid `domain/` or valid `domain_backup/` or both — **never neither**
- `domain_backup/` is **read-only** during all operations
- CLEANED is **terminal and irreversible** (requires `--confirm`)
- Re-run after crash always finds a safe recovery path

**Speaker Notes:**

Chopper avoids in-place mutation because it is too risky. The backup is the single source of truth. Every re-trim rebuilds from the backup, never modifying it. The staging directory is an intermediate build area; if the build fails, staging is removed and the system stays in BACKUP_CREATED state. Advisory domain-level locking prevents concurrent mutation of the same domain.

**Visual:** See Diagram 15 — State Machine

---

## Slide 16 — Diagnostics, Audit, and Observability

**Title:** Operational Safety Mechanisms

**Subtitle:** Machine-readable diagnostics and audit-grade traceability

**On-Slide Content:**

**Diagnostic Record Structure:**

```json
{
    "code": "V-04",
    "severity": "WARNING",
    "location": "feature_dft.json:files.include[2]",
    "message": "Duplicate file in include and exclude",
    "hint": "Remove from files.exclude or files.include"
}
```

**Audit Trail (`.chopper/` per trim):**

```
domain/.chopper/
 ├── chopper_run.json          ← run metadata, timing, exit code
 ├── input_base.json           ← frozen copy of base input
 ├── input_features/           ← frozen copies of feature inputs
 ├── input_project.json        ← (optional, when --project used)
 ├── compiled_manifest.json    ← resolved file/proc decisions
 ├── dependency_graph.json     ← proc call graph + file sourcing edges
 ├── trim_report.json          ← machine-readable report
 └── trim_report.txt           ← human-readable report
```

**Speaker Notes:**

Operational trust comes from observability. Every diagnostic has a stable code, severity, location, and actionable hint. The trimmed domain carries its own audit package — the exact inputs, compiled selections, dependency graph, and reports are all preserved. Structured logging via structlog correlates all log events with run_id, domain, and command context. JSON lines format (UTC ISO 8601) supports machine consumption.

**Visual:** See Diagram 16 — Audit Artifact Tree

---

## Slide 17 — CLI and Automation Contract

**Title:** Automation Surface

**Subtitle:** Four commands, three input modes, full CI readiness

**On-Slide Content:**

| Command | Purpose | Mutates Domain? |
|---|---|---|
| `chopper scan` | Discover files/procs, generate draft JSONs | No |
| `chopper validate` | Phase 1 structural checks on JSONs | No |
| `chopper trim` | Full trim pipeline | Yes (unless `--dry-run`) |
| `chopper cleanup` | Remove `domain_backup/` | Yes (requires `--confirm`) |

**Input Modes:**

| Mode | CLI | Use Case |
|---|---|---|
| Base only | `--base jsons/base.json` | Initial exploration |
| Base + features | `--base ... --features f1.json,f2.json` | Iterative authoring |
| Project JSON | `--project configs/project.json` | CI, reproducibility, audit |

**Key Flags:** `--dry-run`, `--json`, `--plain`, `--strict`, `--debug`, `--force`

**Speaker Notes:**

`--project` is semantically equivalent to `--base` + `--features` after resolution. Equivalent resolved selections produce identical results regardless of input mode. This preserves reproducibility and avoids hidden behavior splits between manual and CI usage. Exit codes are deterministic: 0 (success), 1 (validation failure), 2 (usage error), 3 (write failed/restored), 4 (internal error).

**Visual:** See Diagram 17 — Command Matrix

---

## Slide 18 — Quality Strategy

**Title:** Verification Strategy

**Subtitle:** Four-layer testing with explicit coverage gates

**On-Slide Content:**

| Layer | Location | Purpose |
|---|---|---|
| **Unit** | `tests/unit/` | Isolated module tests, no FS side effects |
| **Integration** | `tests/integration/` | Full lifecycle: scan → validate → trim → cleanup |
| **Property** | `tests/property/` | Hypothesis-based invariant testing |
| **Golden** | `tests/golden/` | Output regression via pytest-regressions |

**Coverage Targets:**

| Module | Target |
|---|---|
| Parser | ≥ 85% branch |
| Compiler | ≥ 80% branch |
| Trimmer | ≥ 80% branch |
| Validator | ≥ 75% branch |
| **Project-wide** | **≥ 78% line** |

**Test Fixtures:** 33 files across 4 fixture packs (mini_domain, namespace_domain, tracing_domain, edge_cases)

**Speaker Notes:**

The testing model is layered to match the architecture. Parser and compiler correctness are verified in isolation for fast feedback. Integration tests use a `ChopperRunner` harness that wraps CLI invocation and validates end-to-end lifecycle behavior. Property tests target parser and trimming invariants with adversarial inputs via Hypothesis. The crash harness tests 5 transition points in the state machine.

**Visual:** See Diagram 18 — Test Pyramid

---

## Slide 19 — Technical Differentiators

**Title:** Why The Design Is Strong

**Subtitle:** Five pillars of engineering credibility

**On-Slide Content:**

| Pillar | What It Means |
|---|---|
| **Deterministic** | Sorted parsing, sorted tracing, stable artifacts — same input = same output, always |
| **Conservative** | Warns on ambiguity instead of fabricating runtime behavior |
| **Typed Contracts** | Service layer returns typed results — CLI, CI, and GUI all share one contract |
| **Recovery-Safe** | Backup lifecycle with formal state machine — crash recovery is rerun |
| **Audit-Grade** | Full input/output package per trim — explainable, reproducible, reviewable |

**Speaker Notes:**

Chopper is strong not because it is flashy, but because the design choices are disciplined. Every module has clear I/O contracts, every decision is traceable, and every failure path has a defined recovery. The combination of determinism + conservatism + typed contracts + backup safety + audit completeness is what makes the system credible for production flow ownership.

**Visual:** See Diagram 19 — Five Pillars

---

## Slide 20 — Current Status and Forward Path

**Title:** Delivery Status and Evolution Path

**Subtitle:** Docs-first architecture, implementation-ready contracts

**On-Slide Content:**

| Asset | Status |
|---|---|
| Architecture spec (Rev 22) | Complete |
| Technical requirements (Rev 11) | Complete |
| Parser spec (Rev 7) | Complete |
| JSON schemas (base/feature/project v1) | Complete |
| Diagnostic codes registry | Complete |
| Test fixtures (33 files) | Complete |
| Core engine implementation | In progress |

**Next Steps:**
- Day 0: Foundation scaffolding + core models
- Day 1: Tcl parser implementation
- Day 2: Compiler + tracer
- Day 3: Trimmer + audit
- Day 4: Validator + CLI
- Day 5: Scanner + end-to-end integration

**Speaker Notes:**

The project is early in implementation but mature in specification. The current asset is not just documentation — it is a full implementation contract covering lifecycle, diagnostics, testing boundaries, module interfaces, and operator behavior. The under-the-hood strength is visible in the design discipline: 45 pre-coding review findings all resolved, 0 blockers in final production review.

**Visual:** See Diagram 20 — Implementation Roadmap

---

## Slide 21 — Closing Summary

**Title:** Chopper: Safe Domain Reduction for EDA Flows

**Subtitle:** From manual art to deterministic engineering

**On-Slide Content:**

- **FlowBuilder** builds UP — assembles run scripts from file lists (apr_fc only)
- **Chopper** trims DOWN — removes unused files and procs across all domains
- Combined: FlowBuilder for file-sequenced apr_fc workflows; Chopper for everything else
- Chopper provides: static analysis, conservative tracing, typed contracts, backup safety, audit completeness
- The result: credible, repeatable, reviewable project-specific thin flows

**Speaker Notes:**

The closing message is that Chopper and FlowBuilder serve complementary purposes. FlowBuilder is a domain-specific run-script generator for apr_fc. Chopper is a general-purpose domain reduction engine for the entire TFM. For apr_fc users, keep using FlowBuilder if it meets your needs. If you need proc-level precision, static run files, audit-grade traceability, or you are outside apr_fc, Chopper is the system.

**Visual:** See Diagram 21 — Closing Summary Graphic
