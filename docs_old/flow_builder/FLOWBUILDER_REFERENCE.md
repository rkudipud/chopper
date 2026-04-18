# FlowBuilder Reference — Insights for Chopper

> **Purpose:** Extract patterns from FlowBuilder (FB) that inform Chopper's JSON schema and run-script generation.  
> **Scope:** apr_fc domain only — FB is currently limited to apr_fc (SNPS). Chopper must work for ALL ~30 domains.  
> **Status:** Analysis complete  
> **Date:** 2026-04-04

---

## 1. What FlowBuilder Is

FlowBuilder is a **run-script generator** for the apr_fc (Fusion Compiler) domain. Given:
- A **base flow JSON** (`apr_fc.json`) — ordered list of stages, each with ordered steps
- Zero or more **feature JSONs** (`*.feature.json`) — directives to inject/remove/reorder steps and stages
- **Config files** — which features to enable, in what priority order

It produces:
- **`run_<stage>.tcl`** — one generated Tcl script per stage, fully resolved, with `iproc_source` calls
- **Stack file** — orchestration file defining stage ordering and dependencies
- **Final JSON** — the merged flow after all features applied

### Key limitations
- **apr_fc only** (since 2025.09; rtlfp added later). Not used by sta_pt, power, fev_formality, etc.
- **File-level only** — it organizes which *files* (steps) run in which order. No proc-level awareness.
- **No trimming** — it builds UP (adds features to a base), never removes unused code from the domain.

### The fundamental flaw: run scripts are just file-source calls
FlowBuilder's generated `run_<stage>.tcl` files contain **zero logic** — they are nothing more than an ordered sequence of `iproc_source -file X -use_hooks` lines with comment headers. The tool is a **file sequencer**: it knows *which files* to source in *what order*, but has absolutely no awareness of what's inside those files — no procs, no call graphs, no code structure. All intelligence lives in the sourced files themselves, which ship unmodified and in full. This means:
- Unused procs inside sourced files still exist and execute.
- Dead code paths guarded by `ivar` flags still ship.
- The "simplification" is cosmetic (cleaner ordering) rather than structural (actual code reduction).

Chopper's core value proposition is operating **below** the file level — understanding proc boundaries, tracing call dependencies, and producing output that contains only the code that's actually needed.

---

## 2. Base Flow JSON Schema (Real: `apr_fc.json`)

```json
{
    "owner": "johndoe",
    "description": "This Default APR_FC Flow",
    "vendor": "snps",
    "tool": "fusioncompiler",
    "command": "Ifc_shell -B $ivar(build_name) ...",

    "stages": [
        "import_design",
        "read_upf",
        "redefine",
        "init_floorplan",
        "setup_timing",
        "initial_map",
        "floorplan",
        "logic_opto",
        "insert_dft",
        "compile_initial_opto",
        "compile_final_opto",
        "cts",
        "clock_route_opt",
        "route_auto",
        "route_opt",
        "fill",
        "finish"
    ],

    "<stage_name>": {
        "load_from": "<parent_stage>",
        "steps": [
            "source $ward/global/snps/$env(flow)/setup.tcl",
            "step_load.tcl",
            "fc.app_options.tcl",
            "<domain_specific_steps>.tcl",
            "$ivar(key) -optional",
            "step_close.tcl"
        ]
    }
}
```

### Structural patterns

| Element | Description |
|---|---|
| `stages` (array) | Ordered list of stage names — defines execution sequence |
| `<stage>.load_from` | Data dependency — which stage's output to load. Translates to `set ivar(src_task)` |
| `<stage>.steps` (array) | Ordered list of step references within one stage |
| Step = filename | `step_cts.tcl` — resolved via search path, wrapped as `iproc_source -file <fullpath> -use_hooks` |
| Step = ivar ref | `$ivar(cts,setup_file)` — resolved at build time to actual file |
| Step = raw source | `source $ward/global/snps/$env(flow)/setup.tcl` — used verbatim |
| Step + `-optional` | `step_clock_ft.tcl -optional` — not an error if missing |

### What Chopper should adopt
- **Ordered stage list + per-stage step list** is a natural way to describe a flow.
- **`load_from` as data dependency** is useful for stack/task file generation.
- **Steps as file references** (not proc names) works for the file-oriented domains.

### What Chopper does differently
- Chopper needs **proc-level granularity** (not just file-level).
- Chopper needs to **describe what to KEEP** (trimming), not just what to RUN (building).
- Chopper operates on **all domains**, most of which don't have stage/step structure.

---

## 3. Feature JSON Schema (Real Examples)

### 3.1 Action Vocabulary

FlowBuilder features use exactly **7 actions**:

| Action | Target | Effect |
|---|---|---|
| `add_step_before` | Step in a stage | Insert step(s) before reference step |
| `add_step_after` | Step in a stage | Insert step(s) after reference step |
| `add_stage_before` | Stage in flow | Insert new stage before reference stage |
| `add_stage_after` | Stage in flow | Insert new stage after reference stage |
| `remove_step` | Step in a stage | Remove a step from a stage |
| `remove_stage` | Stage in flow | Remove entire stage |
| `load_from` | Stage property | Change a stage's data dependency |

### 3.2 Feature JSON Structure

```json
{
    "name": ["<item_id_1>", "<item_id_2>", ...],
    "description": "Short description of the feature",
    "wiki": "http://...",

    "<item_id>": {
        "action": "add_step_after|add_step_before|add_stage_after|...",
        "stage": "<target_stage>",
        "reference": "<reference_step_or_stage>",
        "items": ["step1.tcl", "step2.tcl", ...],
        "flow": "<optional_flow_filter>",
        "command": "<optional_stage_command_override>",
        "exit_codes": "<optional>",
        "outputs": "<optional>",
        "inputs": "<optional>",
        "load_from": "<required_for_new_stages>"
    }
}
```

### 3.3 Real Examples (from cbox_pipep/global/snps/apr_fc/features/)

**Simple — single step injection (`early_cts.feature.json`):**
```json
{
    "name": ["step_early_cts.tcl"],
    "description": "Performs CTS during compile_final_opto. Not compatible with ctmesh",
    "step_early_cts.tcl": {
        "action": "add_step_before",
        "stage": "compile_final_opto",
        "reference": "step_compile_final_place.tcl"
    }
}
```

**Multi-step injection (`dop.feature.json`):**
```json
{
    "name": [
        "step_capture_mapped_instance.tcl",
        "step_create_dops.tcl",
        "step_dop_checks.tcl",
        "step_compile_dop_cts.tcl"
    ],
    "description": "Inserts DOPs into the design",
    "step_capture_mapped_instance.tcl": {
        "action": "add_step_after",
        "stage": "redefine",
        "reference": "fc.app_options.tcl"
    },
    "step_create_dops.tcl": {
        "action": "add_step_after",
        "stage": "initial_map",
        "reference": "$ivar(ndr_file) -optional"
    }
}
```

**New stage + bundled steps (`csi.feature.json`):**
```json
{
    "name": ["step_csi_load_spec.tcl", "csi", "csi_stage_bundle"],
    "csi": {
        "action": "add_stage_after",
        "reference": "compile_initial_opto"
    },
    "csi_stage_bundle": {
        "action": "add_step_after",
        "stage": "csi",
        "reference": "",
        "items": [
            "source $ward/global/snps/$env(flow)/setup.tcl",
            "step_load.tcl",
            "step_csi_load_spec.tcl",
            "step_csi_checks.tcl",
            "step_close.tcl"
        ]
    }
}
```

**Flow reordering (`rtl_based_flow.feature.json`):**
```json
{
    "name": ["redefine", "setup_timing", "initial_map", "step_load_io_constraints.tcl"],
    "redefine":      { "action": "load_from", "reference": "setup_timing" },
    "setup_timing":  { "action": "load_from", "reference": "read_upf" },
    "initial_map":   { "action": "load_from", "reference": "init_floorplan" }
}
```

**If/else in steps (from tech.feature.json — PDF example):**
```json
"items": [
    "step_starrc_indesign_setup.tcl",
    "#if {[info exists ivar(csi,extraction_dir)] && $ivar(csi,extraction_dir) != \"\"}",
    "step_csi_recreate.tcl",
    "#else",
    "step_csi_load_spec.tcl",
    "step_csi_checks.tcl",
    "#endif",
    "step_close.tcl"
]
```
Steps prefixed with `#` are control flow directives (`#if`, `#else`, `#endif`) inserted verbatim into the run script with proper indentation.

### 3.4 Instance References (`@n`)

When a step appears multiple times in one stage, features can target a specific instance:
```json
"reference": "step_load_post_compile_constraints.tcl@2"
```
`@1` = first occurrence (same as no `@`), `@2` = second, etc. Error if `n > count`.

---

## 4. Feature Selection & Priority

### Config files (3 tiers, merged in order):

| File | Scope | Location |
|---|---|---|
| `design_class.features.config` | Design class | `design_class/<class>/snps/apr_fc/` |
| `project.features.config` | Project | `project/<proj>/snps/apr_fc/` |
| `features.config` | User/design | local |

**Content format (since 2025.12):**
```
features_apr_fc = rtla array_fdr fdr dop visa csi \
                  ser idpp seq_clustering mlmp
```

**User negation:** `!csi` in user config removes `csi` added by design_class.

### Priority ordering (`feature_priority.config`):
```
priority_apr_fc = tech rtl_based_flow mlmp mlvr tep \
                  ir_em_analysis add_redundant_vias custom_htree
```
- Features are applied in priority order.
- **Tech feature is always first.**
- Lower-priority features have steps **closer** to the reference point.
- Features not in priority file are applied after those that are (in config file order).

### Real apr_fc inventory: 40 feature JSONs, ~24 features enabled for server_ip design class.

---

## 5. Run Script Generation — The Output

### Per-stage file: `run_<stage>.tcl`

```tcl
# ** AUTOGENERATED FILE ** DO NOT MODIFY **

set ward           "$env(ward)"
set ivar(task)     "<stage_name>"
set ivar(src_task) "<load_from_stage>"

#-----------------------------------------------------------------------------
# Step:     step_create_lib.tcl
#-----------------------------------------------------------------------------
iproc_source -file step_create_lib.tcl -use_hooks

#-----------------------------------------------------------------------------
# Step:     step_setup_rtla_flow.tcl
# Feature:  rtla
#-----------------------------------------------------------------------------
iproc_source -file step_setup_rtla_flow.tcl -use_hooks
```

### Key observations about generated scripts:
1. **Every step** becomes `iproc_source -file <filename> -use_hooks` (full path in non-project mode)
2. **Feature origin is annotated** as a comment (`# Feature: rtla`)
3. **`-optional` flag preserved** — `iproc_source -file step_clock_ft.tcl -optional -use_hooks`
4. **If/else blocks** from feature `items` are inserted verbatim with proper indentation
5. **Raw source commands** (`source $ward/...`) are kept as-is (not wrapped in `iproc_source`)
6. **ivar references** resolved to actual files in non-project mode, kept as ivar refs in project mode
7. **Header boilerplate** (copyright, AUTOGENERATED notice) is standard per file

### Stack file
Defines stage execution order and dependencies. Translates `load_from` → `D <parent>`, `exit_codes` → `L <value>`, etc.

---

## 6. Insights for Chopper JSON Design

### 6.1 What to ADOPT from FlowBuilder

| FB Pattern | Chopper Adaptation | Why |
|---|---|---|
| **Ordered stages/steps** | Base JSON describes execution order | Natural for run-script generation |
| **7-action vocabulary** | Feature JSONs use same/similar actions to modify flow | Proven, well-understood by domain owners |
| **Step = file reference** | Files are the primary unit; procs are secondary | Matches existing codebase structure |
| **`-optional` flag** | Support optional file references | Already used throughout CTH |
| **`items` for bundled steps** | Allow multi-step operations in one directive | Reduces JSON verbosity |
| **`@n` instance targeting** | Support when same step appears multiple times | Real need (e.g., `step_load_post_compile_constraints.tcl` appears 3x in `compile_initial_opto`) |
| **`#if/#else/#endif` in items** | Conditional code injection in generated scripts | avoids massive if/else in flow code |
| **Feature priority config** | Chopper should respect ordering for deterministic output | Non-determinism caused real issues |
| **`!feature` negation** | Allow user-level feature disabling | Already established convention |
| **Feature annotation in output** | `.chopper/` audit trail tracks which feature contributed what | Debugging/traceability |

### 6.2 What to EXTEND beyond FlowBuilder

| Chopper Need | Why FB doesn't cover it |
|---|---|
| **Proc-level extraction** | FB operates at file level only. Chopper must parse Tcl files and extract individual procs |
| **Code removal/trimming** | FB only builds up; Chopper must also remove unused code from the domain |
| **All 30 domains** | FB only works for apr_fc. Chopper must handle sta_pt, power, fev_formality, etc. — each with different structure |
| **Non-Tcl files** | FB only generates Tcl. Chopper must handle Perl, Python, csh at file-level |
| **Proc dependency tracing** | FB doesn't trace call graphs. Chopper must follow `proc A calls proc B calls proc C` |
| **Backup/re-trim lifecycle** | FB runs every time tool starts. Chopper operates once during 2-week trim window |
| **ivar-conditional file sourcing** | FB resolves ivars at build time. Chopper uses JSON declarations to decide what to keep |

### 6.3 What to AVOID from FlowBuilder

| FB Pattern | Why not for Chopper |
|---|---|
| **Stage-centric structure as the only model** | Not all domains have clean stage/step decomposition (e.g., sta_pt is one long script, power has deeply nested onepower/) |
| **`name` array as item registry** | Conflates item IDs with step names; leads to suffixes like `step_csi_load_spec.tcl_0` to disambiguate |
| **Feature JSON = item IDs are also step names** | Makes the JSON fragile — changing a filename means updating the JSON ID |
| **No explicit version/schema** | FB JSONs have no `"version"` key — makes forward compatibility harder |
| **Tight coupling to `iproc_source` command format** | Chopper's output format should be more abstract — the generated script format can vary per domain |

---

## 7. Proposed Chopper JSON Vocabulary

Based on FB analysis plus Chopper's broader requirements, here is a starting point for discussion.

### 7.1 Base JSON — Strawman

```jsonc
{
    "$schema": "chopper/base-flow/v1",
    "domain": "fev_formality",
    "description": "Bare-minimum formality equivalence checking flow",

    // Files always needed (file-level include)
    "files": [
        "vars.tcl",
        "prepare_fev_formality.tcl",
        "default_fm_procs.tcl",
        "default_rules.fm.tcl",
        "promote.tcl"
    ],

    // Procs from the above files that are the actual entry points
    "procs": [
        "read_libs",
        "read_gate",
        "report_match_results",
        "report_verify_results"
    ],

    // For domains with stage/step structure (like apr_fc)
    "stages": [
        {
            "name": "rtl2gate",
            "file": "fev_fm_rtl2gate.tcl",
            "load_from": ""
        }
    ],

    // Files that are always present (not trimming targets)
    "infrastructure": [
        "common/*"
    ]
}
```

### 7.2 Feature JSON — Strawman

```jsonc
{
    "$schema": "chopper/feature/v1",
    "name": "dft",
    "description": "DFT scan-related verification",
    "depends": ["base"],

    // Additional files this feature needs
    "include_files": [
        "addon_fm_procs.tcl"
    ],

    // Additional procs (from any file) this feature needs
    "include_procs": [
        "add_fm_scan_constraints",
        "check_metaflop_settings",
        "check_metaflop",
        "MetaflopErrgen"
    ],

    // Procs to remove (overridden by include from other features)
    "exclude_procs": [],

    // For stage-based domains: flow modifications (FB-style actions)
    "flow_actions": [
        {
            "action": "add_step_after",
            "stage": "rtl2gate",
            "reference": "step_read_constraints.tcl",
            "items": ["step_scan_constraints.tcl"]
        }
    ]
}
```

### 7.3 Key Differences from FlowBuilder JSON

| Aspect | FlowBuilder | Chopper (proposed) |
|---|---|---|
| **Schema version** | None | `"$schema": "chopper/base-flow/v1"` |
| **Primary unit** | Steps (files) in stages | Files + Procs (dual granularity) |
| **Item identification** | Name = step filename (fragile) | Separate `include_files` and `include_procs` arrays |
| **Actions** | 7 actions overloaded into `name` array | `flow_actions` array with explicit objects |
| **Proc awareness** | None | First-class `procs` and `include_procs` keys |
| **Dependency declaration** | None (implicit via priority) | `"depends": [...]` key |
| **Trimming semantics** | N/A (only builds) | `exclude_procs`, `exclude_files` for removal |
| **Infrastructure exclusion** | N/A | `"infrastructure": ["common/*"]` |

---

## 8. Run-Script Generation for Chopper

Chopper's "build on the fly" aspect (FR-19) should learn from FlowBuilder's output model:

### What to generate

| Output | When | Template |
|---|---|---|
| `run_<stage>.tcl` | Domain has stage/step structure defined in JSON | Same pattern as FB: header → `set ivar(task)` → sequence of `iproc_source` calls |
| Stack file | Domain uses TFM stack orchestration | Stage ordering + `load_from` → `D`, `L`, `I`, `O` fields |
| Domain setup script | Always | Bootstrap that sources `common/setup.tcl` and domain `vars.tcl` |

### Template pattern (adapted from FB)

```tcl
# ** AUTOGENERATED by Chopper ** DO NOT MODIFY **
# Domain:   {domain}
# Stage:    {stage}
# Features: {feature_list}
# Generated: {timestamp}

set ward           "$env(ward)"
set ivar(task)     "{stage}"
set ivar(src_task) "{load_from}"

{for each step in resolved_stage.steps}
#-----------------------------------------------------------------------------
# Step:     {step.file}
{if step.feature}# Feature:  {step.feature}{endif}
#-----------------------------------------------------------------------------
{if step.is_source}
source {step.file}
{elif step.optional}
iproc_source -file {step.file} -optional -use_hooks
{else}
iproc_source -file {step.file} -use_hooks
{endif}
{endfor}
```

### Key design decision
FlowBuilder generates run scripts **every time the tool starts** (dynamic). Chopper generates them **once during trim** (static). This means Chopper's output must be complete and self-contained — no runtime resolution of features.

---

## 9. Scale Comparison

| Metric | FlowBuilder (apr_fc) | Chopper (all domains) |
|---|---|---|
| Domains covered | 1 (+ rtlfp) | ~30 |
| Base flow stages | 17 | Varies: 1 (fev) to 17+ (apr_fc) |
| Feature JSONs | 40 | TBD per domain — likely 5-20 each |
| Steps per stage | 5-15 | N/A for non-stage domains |
| Proc awareness | None | Required — proc-level extraction |
| Output files | `run_*.tcl` + stack | Trimmed domain + `run_*.tcl` + `.chopper/` audit |
| Config mechanism | `*.features.config` + priority | CLI args + project JSON |
| Execution frequency | Every tool launch | Once per 2-week trim window |

---

## 10. Summary — What Chopper Takes from FlowBuilder

1. **Stage/step JSON model** — adopt for domains that have clear stage structure
2. **7-action vocabulary** — proven set of flow modification operations
3. **Feature priority ordering** — essential for deterministic output
4. **`items` bundling and `@n` instance targeting** — practical necessities
5. **Generated run-script format** — `iproc_source -file X -use_hooks` with feature annotations
6. **Config file tiers** (design_class → project → user) — established convention; Chopper should respect this layering
7. **`!feature` negation** — user override pattern

But Chopper extends into:
- **Proc-level extraction** (the core differentiator)
- **Code trimming** (removal, not just assembly)
- **All-domain coverage** (not just apr_fc)
- **Dependency graph tracing** (proc call chains)
- **Backup/re-trim lifecycle management**
