# Chopper Technical Presentation — Diagrams

> **Companion to:** `docs/TECHNICAL_PRESENTATION_DECK.md`
> **Format:** Mermaid diagrams — render in any Mermaid-compatible tool, or paste into draw.io / PowerPoint SmartArt as reference.
> **Usage:** Each diagram corresponds to a slide visual reference. Copy the Mermaid source into [mermaid.live](https://mermaid.live) to preview, then export as SVG/PNG for PowerPoint.

---

## Diagram 2 — Before/After Domain Reduction

```mermaid
graph LR
    subgraph BEFORE["Full Domain (Before Trim)"]
        direction TB
        A1["vars.tcl"] ~~~ A2["main_flow.tcl<br/>12 procs"]
        A2 ~~~ A3["helper_procs.tcl<br/>28 procs"]
        A3 ~~~ A4["legacy_debug.tcl"]
        A4 ~~~ A5["feature_dft.tcl"]
        A5 ~~~ A6["feature_power.tcl"]
        A6 ~~~ A7["utils.pl"]
        A7 ~~~ A8["report_gen.py"]
        A8 ~~~ A9["obsolete_hooks.csh"]
        A9 ~~~ A10["extra_utils.tcl<br/>15 procs"]
    end

    subgraph AFTER["Trimmed Domain (After Chopper)"]
        direction TB
        B1["vars.tcl"] ~~~ B2["main_flow.tcl<br/>5 procs ✂"]
        B2 ~~~ B3["helper_procs.tcl<br/>8 procs ✂"]
        B3 ~~~ B5["feature_dft.tcl"]
        B5 ~~~ B7["utils.pl"]
    end

    BEFORE -->|"chopper trim"| AFTER

    style BEFORE fill:#fce8e6,stroke:#ea4335
    style AFTER fill:#e6f4ea,stroke:#34a853
```

---

## Diagram 3 — Decision Tree: FlowBuilder vs Chopper

```mermaid
flowchart TD
    START(["What does your flow look like?"]) --> Q1{"Is your domain<br/>apr_fc?"}
    Q1 -->|NO| CHOPPER1["✅ USE CHOPPER<br/>FlowBuilder does not<br/>support your domain"]
    Q1 -->|YES| Q2{"Is your flow<br/>file-based?<br/>(steps = file sources)"}
    Q2 -->|NO| CHOPPER2["✅ USE CHOPPER<br/>FlowBuilder has no<br/>proc awareness"]
    Q2 -->|YES| Q3{"Do you need<br/>proc-level trimming?"}
    Q3 -->|YES| CHOPPER3["✅ USE CHOPPER<br/>FlowBuilder is<br/>file-level only"]
    Q3 -->|NO| Q4{"Do you want to<br/>keep static run files<br/>and trim content?"}
    Q4 -->|YES| CHOPPER4["✅ USE CHOPPER<br/>trim + dynamic<br/>run-file generation"]
    Q4 -->|NO| Q5{"Are you happy with<br/>FlowBuilder generating<br/>run scripts from JSON?"}
    Q5 -->|YES| FB["✅ KEEP USING<br/>FLOWBUILDER"]
    Q5 -->|NO| CHOPPER5["✅ USE CHOPPER"]

    style START fill:#fff,stroke:#333,stroke-width:2px
    style FB fill:#e8f0fe,stroke:#4285f4,stroke-width:2px
    style CHOPPER1 fill:#e6f4ea,stroke:#34a853,stroke-width:2px
    style CHOPPER2 fill:#e6f4ea,stroke:#34a853,stroke-width:2px
    style CHOPPER3 fill:#e6f4ea,stroke:#34a853,stroke-width:2px
    style CHOPPER4 fill:#e6f4ea,stroke:#34a853,stroke-width:2px
    style CHOPPER5 fill:#e6f4ea,stroke:#34a853,stroke-width:2px
```

---

## Diagram 4 — FlowBuilder vs Chopper Side-by-Side

```mermaid
graph TB
    subgraph FB["FlowBuilder"]
        direction TB
        FB_IN["Base JSON + Feature JSONs<br/>(file-level only)"] --> FB_ENGINE["File Sequencer<br/>(merge features → order files)"]
        FB_ENGINE --> FB_OUT["Generated run_&lt;stage&gt;.tcl<br/>(iproc_source sequences)"]
        FB_NOTE["❌ No proc awareness<br/>❌ No trimming<br/>❌ No backup lifecycle<br/>❌ apr_fc only"]
    end

    subgraph CH["Chopper"]
        direction TB
        CH_IN["Base + Feature + Project JSONs<br/>(file + proc + stage level)"] --> CH_ENGINE["Static Analysis Engine<br/>(parse → compile → trace → build)"]
        CH_ENGINE --> CH_OUT["Trimmed domain/<br/>+ .chopper/ audit trail<br/>+ optional run files"]
        CH_NOTE["✅ Proc-level trimming<br/>✅ Dependency tracing<br/>✅ Backup lifecycle<br/>✅ All 30 domains"]
    end

    style FB fill:#fce8e6,stroke:#ea4335
    style CH fill:#e6f4ea,stroke:#34a853
```

---

## Diagram 5 — JSON Structure Comparison

```mermaid
graph TB
    subgraph FB_JSON["FlowBuilder JSON (Anti-Pattern)"]
        direction TB
        FB_TOP["Top-level object<br/>6 fixed keys + N dynamic keys"]
        FB_STAGES["'stages': ['import_design', 'read_upf', ...]"]
        FB_DYN1["'import_design': { 'steps': [...] }"]
        FB_DYN2["'read_upf': { 'steps': [...] }"]
        FB_TOP --> FB_STAGES
        FB_TOP --> FB_DYN1
        FB_TOP --> FB_DYN2
        FB_WARN["⚠ Keys are DATA<br/>⚠ Schema incomplete<br/>⚠ Collision risk<br/>⚠ Dual source of truth"]
    end

    subgraph CH_JSON["Chopper JSON (Standards-Compliant)"]
        direction TB
        CH_TOP["Top-level object<br/>ALL keys statically known"]
        CH_STAGES["'stages': [<br/>  { 'name': 'import_design', 'steps': [...] },<br/>  { 'name': 'read_upf', 'steps': [...] }<br/>]"]
        CH_TOP --> CH_STAGES
        CH_OK["✅ additionalProperties: false<br/>✅ Full schema validation<br/>✅ Single source of truth<br/>✅ IDE autocompletion"]
    end

    style FB_JSON fill:#fce8e6,stroke:#ea4335
    style CH_JSON fill:#e6f4ea,stroke:#34a853
```

---

## Diagram 7 — Three-Schema Relationship

```mermaid
graph LR
    BASE["Base JSON<br/>(chopper/base/v1)<br/>─────────────<br/>files.include/exclude<br/>procedures.include/exclude<br/>stages<br/>options"]
    FEATURE["Feature JSON<br/>(chopper/feature/v1)<br/>─────────────<br/>files.include/exclude<br/>procedures.include/exclude<br/>flow_actions (9 types)<br/>metadata"]
    PROJECT["Project JSON<br/>(chopper/project/v1)<br/>─────────────<br/>project, domain, owner<br/>base (path)<br/>features (ordered paths)<br/>release_branch, notes"]

    PROJECT -->|"references"| BASE
    PROJECT -->|"references (ordered)"| FEATURE
    FEATURE -->|"layers on top of"| BASE

    style BASE fill:#e8f0fe,stroke:#4285f4
    style FEATURE fill:#fef7e0,stroke:#f9ab00
    style PROJECT fill:#e6f4ea,stroke:#34a853
```

---

## Diagram 8 — Six-Phase Workflow

```mermaid
flowchart LR
    P1["Phase 1<br/>DISCOVER<br/>──────<br/>chopper scan<br/>→ draft JSONs"] --> P2["Phase 2<br/>AUTHOR<br/>──────<br/>Curate base.json<br/>Create features/"]
    P2 --> P3["Phase 3<br/>VALIDATE<br/>──────<br/>chopper validate<br/>→ Phase 1 checks"]
    P3 --> P4["Phase 4<br/>TRIM<br/>──────<br/>--dry-run first<br/>then live trim"]
    P4 --> P5["Phase 5<br/>ITERATE<br/>──────<br/>Adjust JSONs<br/>Re-trim from backup"]
    P5 --> P3
    P4 --> P6["Phase 6<br/>FINALIZE<br/>──────<br/>chopper cleanup<br/>--confirm"]

    style P1 fill:#e8f0fe,stroke:#4285f4
    style P2 fill:#fef7e0,stroke:#f9ab00
    style P3 fill:#fce8e6,stroke:#ea4335
    style P4 fill:#e6f4ea,stroke:#34a853
    style P5 fill:#f3e8fd,stroke:#a142f4
    style P6 fill:#e8eaed,stroke:#5f6368
```

---

## Diagram 9 — Trim Engine Pipeline

```mermaid
flowchart TD
    S0["0. Detect Trim State<br/>(VIRGIN vs re-trim)"] --> S1["1. Read Inputs<br/>base + features or project JSON"]
    S1 --> S15["1.5 Phase 1 Validate<br/>Schema + structural checks"]
    S15 --> S2["2. Compile Selections<br/>FI / FE / PI / PE"]
    S2 --> S3["3. Trace Proc Dependencies<br/>BFS: PI → PI+"]
    S3 --> S4["4. Build Output<br/>FULL_COPY │ PROC_TRIM │ GENERATED"]
    S4 --> S5["5. Phase 2 Validate<br/>Post-trim verification"]
    S5 --> S6["6. Emit Audit Trail<br/>.chopper/ package"]

    style S0 fill:#e8eaed,stroke:#5f6368
    style S2 fill:#e8f0fe,stroke:#4285f4
    style S3 fill:#fce8e6,stroke:#ea4335
    style S4 fill:#e6f4ea,stroke:#34a853
    style S6 fill:#fef7e0,stroke:#f9ab00
```

---

## Diagram 11 — Architecture Stack

```mermaid
block-beta
    columns 1
    block:PRES["PRESENTATION LAYER"]
        CLI["CLI (argparse)"]
        RICH["Rich/Plain Renderer"]
        JSON_OUT["--json output"]
        FUTURE["Future: GUI, TUI"]
    end
    block:SVC["SERVICE LAYER"]
        TRIM["TrimService"]
        SCAN["ScanService"]
        VAL["ValidateService"]
        CLEAN["CleanupService"]
    end
    block:ENGINE["CORE ENGINE"]
        PARSER["Parser"]
        COMPILER["Compiler"]
        TRACER["Tracer"]
        TRIMMER["Trimmer"]
        VALIDATOR["Validator"]
        SCANNER["Scanner"]
    end
    block:CORE["SHARED CORE (core/)"]
        MODELS["models.py"]
        ERRORS["errors.py"]
        DIAG["diagnostics.py"]
        PROTO["protocols.py"]
        SER["serialization.py"]
    end

    PRES --> SVC
    SVC --> ENGINE
    ENGINE --> CORE
```

NOTE: If `block-beta` is not supported in your Mermaid version, use this alternative:

```mermaid
graph TD
    subgraph PRES["Presentation Layer"]
        CLI["CLI (argparse)"]
        RICH["Rich/Plain Renderer"]
        JSON_OUT["--json output"]
    end

    subgraph SVC["Service Layer"]
        TRIM["TrimService"]
        SCAN["ScanService"]
        VAL["ValidateService"]
        CLEAN["CleanupService"]
    end

    subgraph ENGINE["Core Engine"]
        PARSER["Parser"]
        COMPILER["Compiler"]
        TRACER["Tracer"]
        TRIMMER["Trimmer"]
    end

    subgraph CORE["Shared Core"]
        MODELS["models.py"]
        DIAG["diagnostics.py"]
        PROTO["protocols.py"]
    end

    PRES --> SVC --> ENGINE --> CORE

    style PRES fill:#e8f0fe,stroke:#4285f4
    style SVC fill:#fef7e0,stroke:#f9ab00
    style ENGINE fill:#e6f4ea,stroke:#34a853
    style CORE fill:#fce8e6,stroke:#ea4335
```

---

## Diagram 12 — Proc Index Structure

```mermaid
graph LR
    subgraph INDEX["Per-Run Proc Index"]
        E1["flow_procs.tcl::read_libs<br/>──────<br/>file: flow_procs.tcl<br/>ns: (global)<br/>lines: 10–25<br/>body: 11–24"]
        E2["flow_procs.tcl::setup_library_paths<br/>──────<br/>file: flow_procs.tcl<br/>ns: (global)<br/>lines: 42–67<br/>body: 43–66"]
        E3["utils.tcl::ns::helper<br/>──────<br/>file: utils.tcl<br/>ns: ns<br/>lines: 5–18<br/>body: 6–17"]
    end

    TCL1["flow_procs.tcl"] -->|parse| E1
    TCL1 -->|parse| E2
    TCL2["utils.tcl"] -->|parse| E3

    style INDEX fill:#e8f0fe,stroke:#4285f4
```

---

## Diagram 13 — Trace Expansion Walk

```mermaid
flowchart TD
    SEED["Seeds (PI)<br/>read_libs, setup_timing"] -->|"sorted frontier"| POP["Pop smallest:<br/>read_libs"]
    POP --> CHECK{"Already<br/>traced?"}
    CHECK -->|NO| ADD["Add to traced set<br/>Extract calls from body"]
    CHECK -->|YES| SKIP["Skip"]
    ADD --> CALLS["Discovered calls:<br/>setup_library_paths<br/>resolve_lib_path<br/>$cmd (dynamic)"]
    CALLS --> RESOLVE["Resolve each call"]
    RESOLVE --> STATIC["setup_library_paths<br/>→ RESOLVED ✅"]
    RESOLVE --> STATIC2["resolve_lib_path<br/>→ RESOLVED ✅"]
    RESOLVE --> DYNAMIC["$cmd<br/>→ TRACE-UNRESOLV-01 ⚠"]
    STATIC --> FRONTIER["Add to frontier<br/>(sorted)"]
    STATIC2 --> FRONTIER
    FRONTIER --> POP

    style SEED fill:#fef7e0,stroke:#f9ab00
    style ADD fill:#e6f4ea,stroke:#34a853
    style DYNAMIC fill:#fce8e6,stroke:#ea4335
```

---

## Diagram 14 — Include/Exclude Resolution Flow

```mermaid
flowchart TD
    FI["files.include"] --> SPLIT{"Literal or<br/>glob?"}
    SPLIT -->|Literal| FI_LIT["FI_literal"]
    SPLIT -->|Glob| EXPAND["Expand globs"] --> FI_GLOB["FI_glob"]
    FE["files.exclude"] --> FE_SET["FE"]
    FI_GLOB --> DIFF["FI_glob − FE"]
    FI_LIT --> UNION1["FI_literal ∪ (FI_glob − FE)<br/>= Surviving Files"]
    DIFF --> UNION1

    PI["procedures.include"] --> TRACE["BFS Trace"] --> PI_PLUS["PI+"]
    PE["procedures.exclude"] --> PE_SET["PE"]
    PI_PLUS --> PT["PT = PI+ − PI"]
    PT --> DIFF2["PT − PE"]
    PI --> UNION2["PI ∪ (PT − PE)<br/>= Surviving Procs"]
    DIFF2 --> UNION2

    UNION1 --> TREAT["File Treatment<br/>Derivation"]
    UNION2 --> TREAT
    TREAT --> FC["FULL_COPY"]
    TREAT --> PTRIM["PROC_TRIM"]
    TREAT --> GEN["GENERATED"]
    TREAT --> RM["REMOVE"]

    style UNION1 fill:#e6f4ea,stroke:#34a853
    style UNION2 fill:#e6f4ea,stroke:#34a853
    style FC fill:#e8f0fe,stroke:#4285f4
    style PTRIM fill:#fef7e0,stroke:#f9ab00
    style RM fill:#fce8e6,stroke:#ea4335
```

---

## Diagram 15 — Domain Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> VIRGIN

    VIRGIN --> BACKUP_CREATED : os.rename(domain, domain_backup)
    BACKUP_CREATED --> STAGING : Start writing staging dir
    STAGING --> TRIMMED : Atomic promote staging → domain
    TRIMMED --> STAGING : Re-trim (new staging dir)
    TRIMMED --> CLEANED : chopper cleanup --confirm

    BACKUP_CREATED --> BACKUP_CREATED : Crash recovery (rerun)
    STAGING --> BACKUP_CREATED : Crash recovery (remove staging)

    note right of VIRGIN : domain/ exists, no _backup
    note right of BACKUP_CREATED : domain_backup/ exists
    note right of TRIMMED : domain_backup/ + domain/ (trimmed)
    note right of CLEANED : domain/ only — IRREVERSIBLE
```

---

## Diagram 16 — Audit Artifact Tree

```mermaid
graph TD
    DOMAIN["domain/"] --> CHOPPER[".chopper/"]
    CHOPPER --> RUN["chopper_run.json<br/>(run_id, timing, exit_code)"]
    CHOPPER --> BASE["input_base.json<br/>(frozen copy)"]
    CHOPPER --> FEAT["input_features/<br/>(frozen copies)"]
    CHOPPER --> PROJ["input_project.json<br/>(optional)"]
    CHOPPER --> MANIFEST["compiled_manifest.json<br/>(resolved file/proc decisions)"]
    CHOPPER --> GRAPH["dependency_graph.json<br/>(call graph + sourcing edges)"]
    CHOPPER --> REPORT_J["trim_report.json"]
    CHOPPER --> REPORT_T["trim_report.txt"]

    style CHOPPER fill:#fef7e0,stroke:#f9ab00
    style MANIFEST fill:#e8f0fe,stroke:#4285f4
```

---

## Diagram 17 — Command Matrix

```mermaid
graph LR
    subgraph COMMANDS["Chopper Commands"]
        SCAN["scan<br/>Read-only"]
        VALIDATE["validate<br/>Read-only"]
        TRIM["trim<br/>Mutating"]
        CLEANUP["cleanup<br/>Mutating"]
    end

    subgraph INPUT_MODES["Input Modes"]
        BASE_ONLY["--base only"]
        BASE_FEAT["--base + --features"]
        PROJECT["--project"]
    end

    subgraph FLAGS["Key Flags"]
        DRYRUN["--dry-run"]
        JSON_FLAG["--json"]
        STRICT["--strict"]
        CONFIRM["--confirm"]
    end

    BASE_ONLY --> VALIDATE
    BASE_ONLY --> TRIM
    BASE_FEAT --> VALIDATE
    BASE_FEAT --> TRIM
    PROJECT --> VALIDATE
    PROJECT --> TRIM
    DRYRUN --> TRIM
    CONFIRM --> CLEANUP

    style SCAN fill:#e6f4ea,stroke:#34a853
    style VALIDATE fill:#e8f0fe,stroke:#4285f4
    style TRIM fill:#fce8e6,stroke:#ea4335
    style CLEANUP fill:#e8eaed,stroke:#5f6368
```

---

## Diagram 18 — Test Pyramid

```mermaid
graph TD
    subgraph PYRAMID["Test Strategy Pyramid"]
        UNIT["Unit Tests<br/>──────<br/>Fast, isolated, per-module<br/>Parser ≥85% │ Compiler ≥80%<br/>Trimmer ≥80% │ Validator ≥75%"]
        INTEGRATION["Integration Tests<br/>──────<br/>Full lifecycle via ChopperRunner<br/>scan → validate → trim → cleanup"]
        PROPERTY["Property Tests<br/>──────<br/>Hypothesis: max_examples=500<br/>Parser + trimming invariants"]
        GOLDEN["Golden Tests<br/>──────<br/>Output regression<br/>pytest-regressions"]
    end

    subgraph FIXTURES["Fixture Packs (33 files)"]
        MINI["mini_domain/"]
        NS["namespace_domain/"]
        TRACE["tracing_domain/"]
        EDGE["edge_cases/"]
    end

    UNIT --> FIXTURES
    INTEGRATION --> FIXTURES

    style UNIT fill:#e6f4ea,stroke:#34a853
    style INTEGRATION fill:#e8f0fe,stroke:#4285f4
    style PROPERTY fill:#fef7e0,stroke:#f9ab00
    style GOLDEN fill:#fce8e6,stroke:#ea4335
```

---

## Diagram 19 — Five Pillars of Engineering Credibility

```mermaid
graph TD
    subgraph PILLARS["Technical Differentiators"]
        P1["🔒 DETERMINISTIC<br/>──────<br/>Sorted parsing<br/>Sorted tracing<br/>Stable artifacts"]
        P2["🛡 CONSERVATIVE<br/>──────<br/>Warns on ambiguity<br/>Never fabricates<br/>behavior"]
        P3["📋 TYPED CONTRACTS<br/>──────<br/>Request/Result objects<br/>CLI + GUI + CI<br/>share one contract"]
        P4["♻ RECOVERY-SAFE<br/>──────<br/>Backup lifecycle<br/>State machine<br/>Crash = rerun"]
        P5["📊 AUDIT-GRADE<br/>──────<br/>Full I/O package<br/>Explainable<br/>Reproducible"]
    end

    style P1 fill:#e8f0fe,stroke:#4285f4
    style P2 fill:#fce8e6,stroke:#ea4335
    style P3 fill:#e6f4ea,stroke:#34a853
    style P4 fill:#fef7e0,stroke:#f9ab00
    style P5 fill:#f3e8fd,stroke:#a142f4
```

---

## Diagram 20 — Implementation Roadmap

```mermaid
gantt
    title Chopper Implementation Roadmap
    dateFormat YYYY-MM-DD
    section Foundation
        Core models + scaffolding          :done, d0, 2026-04-05, 1d
    section Parser
        Tcl parser + proc index            :active, d1, after d0, 1d
    section Compiler
        Compiler + Tracer                  :d2, after d1, 1d
    section Trimmer
        Trimmer + Audit                    :d3, after d2, 1d
    section CLI
        Validator + CLI                    :d4, after d3, 1d
    section Integration
        Scanner + E2E + Polish             :d5, after d4, 1d
```

---

## Diagram 6 — Anti-Pattern Anatomy (FlowBuilder JSON)

```mermaid
graph TD
    subgraph FB_BASE["FlowBuilder Base JSON (24 keys)"]
        FIXED["Fixed Keys (6)<br/>owner, description, vendor,<br/>tool, command, stages"]
        DYN["Dynamic Keys (17)<br/>import_design, read_upf,<br/>redefine, init_floorplan,<br/>... (data-dependent)"]
        WARN1["⚠ Shape changes with data"]
        WARN2["⚠ additionalProperties: true"]
    end

    subgraph FB_FEAT["FlowBuilder Feature JSON"]
        NAME_ARR["'name': ['step_csi.tcl', 'csi', 'csi_bundle']"]
        KEY1["'step_csi.tcl': { action: ... }"]
        KEY2["'csi': { action: ... }"]
        KEY3["'csi_bundle': { action: ... }"]
        WARN3["⚠ Mixes filenames + stage names + invented IDs"]
        WARN4["⚠ Suffix hacks: step_clock_stamping.tcl_lo"]
    end

    subgraph CH_ALT["Chopper Alternative"]
        STAGES_ARR["'stages': [{name, steps}, ...]"]
        ACTIONS_ARR["'flow_actions': [{action, stage, items}, ...]"]
        OK1["✅ Fixed keys"]
        OK2["✅ Array of typed objects"]
        OK3["✅ No suffix hacks"]
    end

    style FB_BASE fill:#fce8e6,stroke:#ea4335
    style FB_FEAT fill:#fce8e6,stroke:#ea4335
    style CH_ALT fill:#e6f4ea,stroke:#34a853
```

---

## Diagram 10 — Scope Boundary

```mermaid
graph TB
    subgraph IN_SCOPE["IN SCOPE"]
        IS1["Per-domain trimming"]
        IS2["File include/exclude"]
        IS3["Tcl proc-level extraction"]
        IS4["Transitive dependency tracing"]
        IS5["Backup + re-trim lifecycle"]
        IS6["Audit trail"]
        IS7["Draft JSON generation (scan)"]
        IS8["Run-file generation (F3)"]
    end

    subgraph OUT_SCOPE["OUT OF SCOPE"]
        OS1["Repo-wide global trimming"]
        OS2["Non-Tcl subroutine trimming"]
        OS3["Full runtime Tcl eval"]
        OS4["Dynamic behavior inference"]
        OS5["Cross-domain dependencies"]
        OS6["Trimming common/"]
    end

    BOUNDARY["Static Analysis Boundary<br/>──────<br/>Deterministic │ Conservative │ Domain-scoped"]

    IN_SCOPE --> BOUNDARY
    BOUNDARY --> OUT_SCOPE

    style IN_SCOPE fill:#e6f4ea,stroke:#34a853
    style OUT_SCOPE fill:#fce8e6,stroke:#ea4335
    style BOUNDARY fill:#fef7e0,stroke:#f9ab00,stroke-width:3px
```

---

## Diagram 21 — Closing Summary

```mermaid
graph LR
    subgraph BUILDS_UP["FlowBuilder: BUILDS UP"]
        FB1["File lists → ordered run scripts<br/>apr_fc only │ No trimming"]
    end

    subgraph TRIMS_DOWN["Chopper: TRIMS DOWN"]
        CH1["Full domain → minimal project subset<br/>All domains │ Proc-level │ Audit-grade"]
    end

    USER{"Domain Owner"} --> DECISION{"Decision Tree<br/>(Slide 3)"}
    DECISION -->|"apr_fc +<br/>file-only +<br/>OK with generated<br/>run files"| BUILDS_UP
    DECISION -->|"Everything<br/>else"| TRIMS_DOWN

    style BUILDS_UP fill:#e8f0fe,stroke:#4285f4
    style TRIMS_DOWN fill:#e6f4ea,stroke:#34a853
    style DECISION fill:#fef7e0,stroke:#f9ab00
```
