# Proposal 1 — Signoff Feature Filtering (ww12 2026)

> **Source:** "Signoff Flow Options for Feature Filtering" — STA, FEV, Power, TCM collaboration  
> **Date:** ww12 2026  
> **Analyzed:** 2026-04-04  
> **PDF:** `docs/Signoff Feature Filtering Options.pdf`

---

## 1. Context

This proposal was created by signoff domain owners (STA, FEV, Power, TCM) to define how feature filtering should work for their flows. It presents two approaches side by side and recommends the "Signoff Alternative" — a standalone tool that replaces FlowBuilder, SNORT, p4 template generation, and ward generation.

The "Signoff Alternative" is essentially what we are building as **Chopper**.

---

## 2. Two Approaches Compared

### Approach A: Current Construction Mechanism (FlowBuilder-based)

Reuse FlowBuilder in project mode + SNORT for signoff domains.

```
Project feature config file
        │
        ▼
FlowBuilder (PM mode) ──► Run Scripts
        │
        ▼
SNORT ──► Source file reports ──► Parse for exclude list
        │
        ▼
p4 template ──► Generate new ward ──► Submit to program branch
```

**Requirements:**
- Flow must have stage/step sequence (or create one)
- Must generate `$flow.json` and `$feature.feature.json` per FlowBuilder spec
- SNORT must be configured for each signoff flow (requires developer bandwidth)
- p4 template issues with multiple deployment owners per flow

**Verdict:** Too rigid. Forces all domains into FlowBuilder's file-only model. No proc-level extraction.

### Approach B: Signoff Alternative (The Proposal — basis for Chopper)

Standalone "File Trimming & Procedure Pruning Tool" that consumes JSON files directly.

```
Flow *.json files + Feature config
        │
        ▼
File Trimming & Procedure Pruning Tool
        │
        ├──► p4 commands file
        ├──► modified procedure files (optional)
        └──► updated run files (optional)
        │
        ▼
User reviews p4 commands ──► Submit to program branch
```

**Replaces:** FlowBuilder, SNORT, p4 template generation, ward generation — all four tools.

---

## 3. JSON Schema — Base Flow (`$flow.json`)

```json
{
    "vendor": "snps",
    "tool": "my_flow",
    "generate_stack": 1,
    "template_script": "",
    "files": {
        "include": [
            "load_collateral.tcl",
            "run_analysis.tcl",
            "common_dir/**",
            "report_base/**"
        ],
        "exclude": [
            "common_dir/file1.tcl"
        ]
    },
    "procedures": {
        "include": {
            "flow_procs.tcl": [],
            "feature_procs.tcl": [
                "common_proc",
                "common_proc2"
            ]
        },
        "exclude": {
            "flow_procs.tcl": [
                "procN"
            ]
        }
    },
    "stages": [],
    "stage": { }
}
```

### Schema breakdown

| Field | Type | Required | Description |
|---|---|---|---|
| `vendor` | string | Yes | Vendor identifier (e.g., "snps") |
| `tool` | string | Yes | Flow/tool name |
| `generate_stack` | 0/1 | No | Whether to generate the stack file |
| `template_script` | string | No | Custom script path to generate template run file |
| `files.include` | array | No | Files/directories to keep. Supports glob: `*`, `?`, `**` |
| `files.exclude` | array | No | Files to remove. Only excludes from what's being included |
| `procedures.include` | object | No | `{ "file.tcl": ["proc1", "proc2"] }` — procs to keep. `[]` = keep all procs in file |
| `procedures.exclude` | object | No | `{ "file.tcl": ["procN"] }` — procs to remove |
| `stages` | array | No | Ordered stage list (only if generating run/stack files) |
| `stage` | object | No | Per-stage step definitions |

### Key semantics

- **`files` and `procedures` are optional.** If not provided, pruning is based on `stages` section.
- **Empty proc list `[]` = keep all procs** in that file.
- **Unlisted procs are pruned** — default is remove (implicit exclude).
- **Unlisted files are removed** — "Any file not explicitly listed: Do not keep as source file."
- **Glob patterns supported:** `*` (any chars), `?` (one char), `**` (recursive directories).

### Observations

1. **Dual granularity** — `files` for whole-file ops, `procedures` for proc-level. Clean separation.
2. **File→proc mapping** — Procs are identified as `"filename": ["proc_name"]`, which is unambiguous but couples proc identity to file location.
3. **Implicit exclusion** — Anything not listed in `include` is excluded by default. This is **the opposite** of FlowBuilder (which includes everything by default and features add to it).
4. **`exclude` scoped to `include`** — You can only exclude from what's being included. Can't exclude something that wasn't included.

---

## 4. JSON Schema — Feature (`$feature.feature.json`)

```json
{
    "vendor": "snps",
    "tool": "my_flow",
    "name": "feature1",
    "description": "Enables the first feature",
    "related_ivars": "ivar(my_flow,enable_feature1)",
    "related_appvars": "",
    "files": {
        "include": [
            "feature1.tcl",
            "reports/feature1.tcl",
            "utils/**"
        ],
        "exclude": [
            "utils/x.tcl"
        ]
    },
    "procedures": {
        "include": {
            "feature_procs.tcl": [
                "proc_feature1",
                "proc_feature1a"
            ]
        },
        "exclude": {}
    },
    "step_*": {}
}
```

### Schema breakdown

| Field | Type | Required | Description |
|---|---|---|---|
| `vendor` | string | Yes | Vendor identifier |
| `tool` | string | Yes | Flow/tool name |
| `name` | string | Yes | Feature name |
| `description` | string | Yes | Human-readable description |
| `related_ivars` | string | No | Documentation: associated ivar(s) |
| `related_appvars` | string | No | Documentation: associated app variables |
| `files.include/exclude` | arrays | No | Same semantics as base JSON |
| `procedures.include/exclude` | objects | No | Same semantics as base JSON |
| `step_*` | object | No | Step insertion directives (only for run/stack generation) |

### Key rules

- **Features cannot exclude base flow files or procedures.** This is an enforced safety constraint.
- **Feature files/procs are ADDED to the base set** — union semantics.
- **`related_ivars` and `related_appvars` are informational only** — documentation metadata, not evaluated.

---

## 5. JSON Schema — Project Config

```json
{
    "project": "project_A",
    "owner": "me",
    "flowA": {
        "features": [
            "FeatureA",
            "FeatureD"
        ],
        "feature_priority": [
            "FeatureD",
            "FeatureA"
        ],
        "ivars": {
            "ivar_name": "value"
        }
    }
}
```

### Schema breakdown

| Field | Type | Required | Description |
|---|---|---|---|
| `project` | string | Yes | Project identifier |
| `owner` | string | Yes | Deployment owner |
| `<flow_name>` | object | Per flow | Per-flow configuration |
| `<flow>.features` | array | Yes | Selected features for this flow |
| `<flow>.feature_priority` | array | No | Ordering for run/stack generation |
| `<flow>.ivars` | object | No | Ivar overrides — appended/updated in vars.tcl |

---

## 6. Tool Behavior ("File Trimming & Procedure Pruning Tool")

From slide 12, the tool operates in this sequence:

```
1. Read $flow.json
   ├── Build include_files list
   ├── Build exclude_files list
   ├── Build include_procs list (per file)
   └── Build exclude_procs list (per file)

2. For each selected feature, read $feature.feature.json
   ├── Update include/exclude lists (union)
   └── Enforce: features cannot exclude base files/procs

3. Generate reports
   ├── Source files to keep vs not keep
   └── Procedures to keep vs not keep

4. File operations
   ├── Excluded files → p4 delete commands
   ├── Pruned proc files → p4 edit + rewrite file without pruned procs
   └── Run/stack files (optional) → p4 edit + overwrite with generated content

5. Output
   ├── p4 commands script (user reviews before running)
   ├── Modified procedure files
   └── Updated run files (optional)
```

### Three options for handling missing files/procs after pruning (slide 13)

| Option | Approach | Pros | Cons |
|---|---|---|---|
| **1** | Generate new run files based on stages/steps | Clean — run files match trimmed code | Requires stage/step structure |
| **2** | Each flow provides a custom template script | Flexible — domain owner controls output | Per-domain effort; no standardization |
| **3** | Modify existing code to check existence | `iproc_source -optional`, `if {[info command] ne ""}` | Adds defensive code; doesn't actually remove code |

---

## 7. Strengths

| # | Strength | Impact |
|---|---|---|
| S1 | **Proc-level extraction** — `procedures.include/exclude` with file→proc mapping | Core differentiator from FlowBuilder |
| S2 | **File + proc dual granularity** — clean separation of concerns | Domain owners can choose their level of precision |
| S3 | **`file: []` = keep all procs** convention | Simple, low-effort for files where all procs are needed |
| S4 | **Glob patterns** (`*`, `?`, `**`) for directory matching | Handles `onepower/**`, `Zstat/**` elegantly |
| S5 | **Replaces 4 tools** (FlowBuilder, SNORT, p4 template, ward gen) | Major simplification of the workflow |
| S6 | **Optional run/stack generation** | Domains without stage/step structure can skip it |
| S7 | **`template_script`** hook for custom run-file generation | Each domain can customize its own output format |
| S8 | **Feature metadata** (`related_ivars`, `related_appvars`) | Helps deployment owners understand what features control |
| S9 | **Project config per flow** with features + priority + ivar overrides | Single file captures complete project configuration |
| S10 | **Feature safety** — features cannot exclude base files/procs | Prevents features from breaking the core flow |
| S11 | **P4 command script** with user review step | Safe workflow — human in the loop before destructive ops |
| S12 | **Implicit exclusion** — unlisted = removed | Forces explicit declaration of what's needed (tighter trimming) |

---

## 8. Gaps & Concerns

| # | Gap | Severity | Detail |
|---|---|---|---|
| G1 | **No transitive dependency tracing** | **HIGH** | Domain owners must manually enumerate every proc in the call chain. If `proc A → proc B → proc C` and you list only `proc A`, procs B and C are pruned — breaking the flow. This is the biggest gap. |
| G2 | **No backup/re-trim lifecycle** | **HIGH** | Direct p4 delete/edit with no backup folder. Once submitted, you need p4 revert to undo. No built-in re-trim capability. |
| G3 | **No audit trail** | **MEDIUM** | No mention of preserving input JSONs, generating dependency graphs, or tracking what was trimmed and why. Makes debugging trimmed flows difficult. |
| G4 | **Missing proc handling undecided** | **MEDIUM** | Three options listed (slide 13) but no decision. Option 1 (generate run files) is the right answer for stage-based domains; option 2 (custom script) for others. Option 3 (defensive code) should be rejected — it doesn't remove code. |
| G5 | **`step_*` syntax underspecified** | **MEDIUM** | Feature JSON shows `"step_*": {}` for step insertion but doesn't define the action vocabulary. No `add_step_before/after`, `add_stage_before/after`, `remove_step/stage`, or `load_from` actions specified. |
| G6 | **No `@n` instance targeting** | **LOW** | No mechanism for targeting specific instances when a step appears multiple times in a stage (e.g., `step_load_post_compile_constraints.tcl` appears 3x in `compile_initial_opto`). |
| G7 | **No `#if/#else` conditionals** | **LOW** | No conditional code injection in generated run scripts. FlowBuilder supports this. |
| G8 | **No `!feature` negation** | **LOW** | No mechanism for user-level feature disabling (overriding design_class/project config). |
| G9 | **Proc ID = file+name coupling** | **LOW** | If a proc moves between files, JSON must be updated. Acceptable tradeoff for unambiguity. |
| G10 | **No schema version** | **LOW** | No `"$schema"` or version key. Makes forward compatibility harder. |
| G11 | **No include-wins-over-exclude rule** | **MEDIUM** | What happens when base includes `procN` and feature excludes `procN`? The proposal says "features cannot exclude base" — but what about two features conflicting? |
| G12 | **No validation** | **MEDIUM** | "Validate the flows" shown as a box in diagram but undefined. No post-trim check for dangling references. |

---

## 9. Implementation Cost (from proposal)

| Flow | Flow Changes | FTE | Validation | FTE |
|---|---|---|---|---|
| STA | 3 weeks | 2 | 2 weeks | 1 |
| FEV | 4 weeks | 3 | 4 weeks | 2 |

Deployment cost (building feature lists per project) is TBD.

---

## 10. What Chopper Should Adopt from This Proposal

| Proposal Element | Chopper Action |
|---|---|
| `files.include/exclude` with globs | **Adopt directly** — clean, proven pattern |
| `procedures.include/exclude` with `file: [procs]` | **Adopt with enhancement** — add auto transitive tracing |
| `file: []` = keep all procs | **Adopt** — simple convention |
| `generate_stack` / `template_script` | **Adopt** — optional run/stack generation |
| `related_ivars` / `related_appvars` | **Adopt** — feature documentation metadata |
| Project config with features + priority + ivars | **Adopt** — single project config file |
| P4 command script generation | **Add to Chopper** — practical need for Intel p4 workflow |
| Feature cannot exclude base | **Adopt** — enforced safety rule |

---

## 11. What Chopper Should Add Beyond This Proposal

| Enhancement | Why |
|---|---|
| **Automatic transitive proc tracing** | Don't force manual enumeration of entire call chain. Parse proc bodies, trace `A → B → C` automatically. |
| **Backup/re-trim lifecycle** | `domain_backup/` folder approach. Safe re-trim from original, cleanup at end. |
| **Audit trail** (`.chopper/` directory) | Preserve inputs, compiled manifest, dependency graph, trim report. Full reproducibility. |
| **Include-wins-over-exclude resolution** | Explicit conflict resolution rule across base + features. |
| **Post-trim validation** | Check for dangling proc references, missing files. Run `tclsh` syntax check on modified files. |
| **Step action vocabulary** | Adopt FlowBuilder's 7-action set for domains that generate run/stack files. |
| **Schema versioning** | `"$schema": "chopper/v1"` for forward compatibility. |
| **Dry-run mode** | Preview trimming without modifying anything. |

---

## 12. Comparison Matrix — FlowBuilder vs Proposal vs Chopper (Target)

| Capability | FlowBuilder | This Proposal | Chopper (Target) |
|---|---|---|---|
| File-level include/exclude | Implicit (via stages/steps) | Explicit (`files.include/exclude`) | Explicit + globs |
| Proc-level extraction | No | Yes (manual listing) | Yes + auto tracing |
| Glob patterns | No | Yes (`*`, `?`, `**`) | Yes |
| Stage/step generation | Required | Optional | Optional |
| Run-script output | Always (iproc_source lines) | Optional (3 strategies) | Optional |
| Transitive proc tracing | No | No | **Yes** |
| Backup/re-trim | No | No | **Yes** |
| Audit trail | No | No | **Yes** |
| Validation | No | Undefined | **Yes** |
| Feature safety | N/A | Features can't exclude base | Features can't exclude base + include-wins |
| P4 integration | Via SNORT + template | P4 command script | **P4 command script** |
| Feature metadata | No | `related_ivars`, `related_appvars` | Adopted |
| Schema versioning | No | No | **Yes** |
| Domains covered | apr_fc only | All signoff | **All ~30** |
| Replaces | Nothing | FB + SNORT + p4 template + ward gen | Same |

---

## 13. Open Discussion Points

1. **Should `procedures` section be required or optional?** — If optional and no `stages` provided either, what does the tool trim? Just files?

2. **How should FlowBuilder's action vocabulary map into `step_*`?** — The proposal leaves `step_*` undefined. Should Chopper adopt FB's 7 actions or define new ones?

3. **Implicit exclude vs explicit exclude** — The proposal defaults to "remove unlisted." This is safe but verbose — domain owners must list every file/proc they need. Is this acceptable? Or should there be a "keep unlisted files" mode for incremental adoption?

4. **P4 vs git** — The proposal assumes Perforce. Chopper should also support git workflows (the project repo may migrate).

5. **Cost of JSON creation** — FEV estimates 4 weeks / 3 FTE just for flow changes. Can auto-discovery (scanning domain files and generating draft JSONs) reduce this?
