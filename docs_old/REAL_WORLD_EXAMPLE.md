# Real-World Example: Formality Domain Complete Setup

**Date:** April 2026  
**Purpose:** Comprehensive example showing all three authoring families with annotations  
**Scenario:** Setting up a formal verification flow with DFT, power, and stage orchestration

---

## File Structure

```
fev_formality/
├── jsons/
│   ├── base.json                    # Minimal viable flow
│   └── features/
│       ├── feature_dft.json         # DFT-specific additions
│       ├── feature_power.json       # Power analysis extensions
│       └── feature_pipeline.json    # Stage orchestration
├── *.tcl                            # Domain Tcl files
├── default_fm_procs.tcl             # Shared procedures
├── templates/
│   └── generate_release_manifest.py # Post-trim script
└── configs/
    └── project_rtl2gate.json        # Project-specific selection
```

---

## 1. BASE JSON: Minimal Viable Flow

**File:** `jsons/base.json`  
**Purpose:** Define files, procs, and stages that are always needed

```json
{
  "$schema": "chopper/base/v1",
  "domain": "fev_formality",
  "owner": "rkudipud",
  "vendor": "cdns/snps/intel",
  "tool": "formality",
  "description": "Minimal viable flow for RTL-to-Gate formal verification",
  "_draft": false,
  
  "options": {
    "cross_validate": true,
    "template_script": "templates/generate_release_manifest.py"
  },
  
  "files": {
    "include": [
      "vars.tcl",
      "promote.tcl",
      "fev_fm_rtl2gate.tcl",
      "hooks/common_postcheck.tcl"
    ]
  },
  
  "procedures": {
    "include": [
      {
        "file": "default_fm_procs.tcl",
        "procs": ["read_libs", "run_verify", "emit_reports"]
      }
    ],
    "exclude": [
      {
        "file": "default_fm_procs.tcl",
        "procs": ["legacy_compare"]
      }
    ]
  },
  
  "stages": [
    {
      "name": "setup",
      "load_from": "",
      "language": "tcl",
      "run_mode": "serial",
      "outputs": ["setup.done"],
      "steps": [
        "source $ward/global/snps/$env(flow)/setup.tcl",
        "step_load_env.tcl",
        "step_load_libs.tcl",
        "step_load_constraints.tcl"
      ]
    },
    {
      "name": "verify",
      "load_from": "setup",
      "dependencies": ["setup"],
      "command": "fm_shell -f run_verify.tcl",
      "language": "tcl",
      "run_mode": "serial",
      "exit_codes": [0, 1, 2],
      "inputs": ["setup.done"],
      "outputs": ["verify.done"],
      "steps": [
        "step_run_verify.tcl",
        "step_generate_reports.tcl"
      ]
    }
  ]
}
```

### Annotations for base.json:

| Section | Field | Value | Explanation |
|---|---|---|---|
| Metadata | owner | rkudipud | Who maintains this domain |
| Metadata | vendor | cdns/cnps/intel | Vendor classification for traceability |
| Metadata | tool | formality | Tool this domain supports |
| Files | include | vars.tcl, promote.tcl, ... | Essential files that must remain |
| Files | exclude | (not shown here, would prune glob results) | Uncommon; typically for wildcard pruning |
| Procedures | include | read_libs, run_verify, emit_reports | Entry-point procedures from shared library |
| Procedures | exclude | legacy_compare | Procedure kept conservatively by tracing; explicitly excluded here |
| Stages | setup | name: "setup" | Generates `N setup` in the stack file |
| Stages | setup | load_from: "" | First stage has no predecessor in the generated run script |
| Stages | verify | command: "fm_shell -f run_verify.tcl" | Generates the `J` execution line in the stack file |
| Stages | verify | load_from: "setup", dependencies: ["setup"] | `load_from` feeds the run script; `dependencies` generates the `D setup` graph line |
| Stages | verify | exit_codes: [0, 1, 2] | Generates the `L 0 1 2` legal-exit-code line |
| Stages | verify | run_mode: "serial" | Sequential execution (not parallel) |
| Stages | verify | language: "tcl" | Uses Tcl (default, can omit) |

---

## 2. FEATURE JSON #1: DFT Support

**File:** `jsons/features/feature_dft.json`  
**Purpose:** Add DFT-specific files, procs, and pipeline modifications

```json
{
  "$schema": "chopper/feature/v1",
  "name": "dft_support",
  "domain": "fev_formality",
  "description": "Add DFT mode and scan procedures to the baseline verify flow",
  
  "metadata": {
    "owner": "dft_team",
    "tags": ["dft", "scan", "signoff"],
    "wiki": "https://wiki.company.com/dft/formality_flow",
    "related_ivars": ["dft_mode", "scan_compression"]
  },
  
  "files": {
    "include": [
      "scan/**",
      "dft_lib/**",
      "hooks/dft_hook.tcl"
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
        "procs": ["obsolete_scan_proc"]
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
        "step_load_scan_libs.tcl"
      ]
    },
    {
      "action": "add_step_after",
      "stage": "verify",
      "reference": "step_run_verify.tcl",
      "items": [
        "step_verify_scan_integrity.tcl"
      ]
    },
    {
      "action": "add_stage_after",
      "name": "dft_analysis",
      "reference": "verify",
      "load_from": "verify",
      "dependencies": ["verify"],
      "language": "tcl",
      "command": "fm_shell -f run_dft_analysis.tcl",
      "exit_codes": [0, 1],
      "inputs": ["verify.done"],
      "outputs": ["dft_analysis.done"],
      "run_mode": "serial",
      "steps": [
        "step_analyze_scan_coverage.tcl",
        "step_emit_dft_report.tcl"
      ]
    }
  ]
}
```

### Annotations for DFT feature:

| Section | Field | Value | Explanation |
|---|---|---|---|
| Name | name | dft_support | Unique identifier within project |
| Metadata | tags | ["dft", "scan", "signoff"] | For catalog filtering and discovery |
| Files | include | scan/**, dft_lib/** | Add all DFT-related files and libraries |
| Files | exclude | scan/legacy/** | But exclude obsolete scan directories |
| Procedures | include | add_fm_scan_constraints, emit_scan_summary | DFT-specific procedures from shared lib |
| flow_actions | add_step_after (setup) | ... | Inject scan setup steps after constraints load |
| flow_actions | add_step_after (verify) | ... | Add scan integrity check after main verify |
| flow_actions | add_stage_after | dft_analysis | Create new post-verify stage for DFT analysis |
| New stage | language | tcl | DFT analysis is Tcl-based (could be Python) |
| New stage | dependencies | ["verify"] | Depends on verify stage completing |
| New stage | exit_codes | [0, 1] | Allow both success and "warnings found" codes |

---

## 3. FEATURE JSON #2: Power Analysis

**File:** `jsons/features/feature_power.json`  
**Purpose:** Add power-related analysis that builds on DFT setup

```json
{
  "$schema": "chopper/feature/v1",
  "name": "power_analysis",
  "depends_on": ["dft_support"],
  "domain": "fev_formality",
  "description": "Add power analysis and leakage verification",
  
  "metadata": {
    "owner": "power_team",
    "tags": ["power", "leakage"],
    "wiki": "https://wiki.company.com/power"
  },
  
  "files": {
    "include": [
      "power/**",
      "templates/power_*.py"
    ],
    "exclude": [
      "power/old_metrics/**"
    ]
  },
  
  "procedures": {
    "include": [
      {
        "file": "default_fm_procs.tcl",
        "procs": ["analyze_power_metrics", "check_leakage"]
      }
    ]
  },
  
  "flow_actions": [
    {
      "action": "add_stage_after",
      "name": "power_verification",
      "reference": "verify",
      "load_from": "verify",
      "dependencies": ["verify"],
      "language": "python",
      "command": "python3 run_power_analysis.py",
      "exit_codes": [0, 1, 2],
      "inputs": ["verify.done", "power.metrics"],
      "outputs": ["power_verified.done"],
      "run_mode": "serial",
      "steps": [
        "python3 scripts/extract_power_data.py",
        "python3 scripts/analyze_leakage.py",
        "python3 scripts/generate_power_report.py"
      ]
    }
  ]
}
```

### Annotations for Power feature:

| Section | Key Point | Value | Why |
|---|---|---|---|
| Name | Feature dependency | depends_on: ["dft_support"] | Power analysis assumes DFT setup and files are already present |
| New stage | language | "python" | Power analysis uses Python (2025.12+) |
| New stage | steps | Python scripts | Each step is a Python command |
| New stage | exit_codes | [0, 1, 2] | Allow multiple outcomes: pass, warning, fail |
| New stage | inputs | ["verify.done", "power.metrics"] | Requires verify completion + power data |

---

## 4. FEATURE JSON #3: Pipeline Optimization

**File:** `jsons/features/feature_pipeline.json`  
**Purpose:** Enable parallel execution and add reporting stage

```json
{
  "$schema": "chopper/feature/v1",
  "name": "optimized_pipeline",
  "depends_on": ["dft_support", "power_analysis"],
  "description": "Enable parallel execution and add comprehensive reporting",
  
  "metadata": {
    "owner": "infrastructure_team",
    "tags": ["performance", "optimization"]
  },
  
  "flow_actions": [
    {
      "action": "load_from",
      "stage": "verify",
      "reference": "parallel_checks"
    },
    {
      "action": "add_stage_before",
      "name": "parallel_checks",
      "reference": "verify",
      "load_from": "setup",
      "dependencies": ["setup"],
      "language": "tcl",
      "run_mode": "parallel",
      "outputs": ["checks.done"],
      "steps": [
        "step_structural_check.tcl",
        "step_connectivity_check.tcl",
        "step_interface_check.tcl"
      ]
    },
    {
      "action": "add_stage_after",
      "name": "final_reports",
      "reference": "verify",
      "load_from": "verify",
      "dependencies": ["verify"],
      "language": "tcl",
      "exit_codes": [0],
      "inputs": ["verify.done"],
      "outputs": ["final_reports.done"],
      "run_mode": "serial",
      "steps": [
        "step_consolidate_results.tcl",
        "step_generate_html_report.tcl",
        "step_upload_artifacts.tcl"
      ]
    }
  ]
}
```

### Annotations for Pipeline feature:

| Section | Key Point | Example | Impact |
|---|---|---|---|
| Name | Feature purpose | optimized_pipeline | Distinct from file/proc selection |
| Name | Feature chain | depends_on: ["dft_support", "power_analysis"] | Pipeline rewiring is applied only after those prerequisite features |
| flow_actions | load_from modification | Change verify to parallel_checks | Restructure pipeline dependencies |
| add_stage_before | parallel execution | run_mode: "parallel" | Checks run concurrently (2025.12+) |
| add_stage_after | reporting | final_reports stage | New post-verify aggregation stage |

---

## 5. PROJECT JSON: RTL-to-Gate Project

**File:** `configs/project_rtl2gate.json`  
**Purpose:** Capture exact project configuration for reproducible trims

```json
{
  "$schema": "chopper/project/v1",
  "project": "RTL2GATE_PROJECT",
  "domain": "fev_formality",
  "owner": "verification_team",
  "release_branch": "rtl2gate_main",
  
  "base": "jsons/base.json",
  
  "features": [
    "jsons/features/feature_dft.json",
    "jsons/features/feature_power.json",
    "jsons/features/feature_pipeline.json"
  ],
  
  "notes": [
    "feature_dft adds DFT-specific files and procedures. It is the root prerequisite for the later feature chain.",
    "feature_power declares depends_on: [dft_support], so it must appear after feature_dft.",
    "feature_pipeline declares depends_on: [dft_support, power_analysis], so it must run last after both prerequisites.",
    "Final pipeline: setup → parallel_checks (parallel) → verify → power_verification (Python) → dft_analysis (Tcl) → final_reports"
  ]
}
```

### Annotations for Project JSON:

| Section | Field | Value | Purpose |
|---|---|---|---|
| Metadata | project | RTL2GATE_PROJECT | Project identifier for audit |
| Metadata | release_branch | rtl2gate_main | Git branch for this trim |
| Config | base | jsons/base.json | Always required; points to minimal viable flow |
| Config | features | [dft, power, pipeline] | Ordered list; order is significant and must satisfy each feature's depends_on chain |
| Documentation | notes | Ordering explanations | Why features are in this dependency order |

---

## 6. Usage Workflow

### Step 1: Validate Base JSON

```bash
cd /path/to/fev_formality
chopper validate --base jsons/base.json
# Output: ✓ Base JSON is valid
```

### Step 2: Validate Features

```bash
chopper validate \
  --base jsons/base.json \
  --features jsons/features/feature_dft.json,jsons/features/feature_power.json
# Output: ✓ Base + 2 features valid
```

### Step 3: Validate Project

```bash
chopper validate --project configs/project_rtl2gate.json
# Output: ✓ Project configuration valid
```

### Step 4: Dry-Run Trim

```bash
chopper trim --dry-run --project configs/project_rtl2gate.json
# Output: Shows what would be trimmed (no actual changes)
```

### Step 5: Execute Live Trim

```bash
chopper trim --project configs/project_rtl2gate.json
# Output:
# ✓ Backup created: fev_formality_backup/
# ✓ Trimming: 150 files, 45 procs, 5 stages
# ✓ Template script executed: generate_release_manifest.py
# ✓ Trim complete. Audit artifacts in .chopper/audit/
```

---

## 7. Final Pipeline Visualization

```
After all features applied:

┌─────────────────────────────────────────────────────┐
│ setup                                               │
│ (source setup.tcl, load libs, load constraints)    │
│ Output: setup.done                                  │
└────────────┬────────────────────────────────────────┘
             │
    ┌────────┴──────────┐
    │                   │
┌───▼───┐    ┌─────────▼───────────────┐
│       │    │                         │
│step_1 │    │      step_2             │  (PARALLEL, run_mode: "parallel")
│       │    │                         │
└───┬───┘    └────────┬────────────────┘
    │                 │
    └────────┬────────┘
             │
    Output: checks.done
             │
    ┌────────▼─────────────────────────────────────────┐
    │ verify                                            │
    │ (fm_shell, verify RTL vs Gate)                   │
    │ Output: verify.done, exit_codes: [0,1,2]        │
    └────────┬─────────────────────────────────────────┘
             │
    ┌────────┴────────────────────────┐
    │                                 │
┌───▼──────────────────┐    ┌────────▼──────────────────┐
│ power_verification   │    │ dft_analysis              │
│ (Python, parallel OK)│    │ (Tcl)                     │
│ Input: verify.done   │    │ Input: verify.done        │
│ Output: verified.json│    │ Output: dft_analysis.done │
└──────┬───────────────┘    └───────┬──────────────────┘
       │                            │
       └───────────┬────────────────┘
                   │
    ┌──────────────▼──────────────────┐
    │ final_reports                    │
    │ (consolidate, HTML, upload)     │
    │ Output: final_reports.done       │
    └─────────────────────────────────┘
```

---

## 8. Key Takeaways

✓ **Modular design:** Each feature adds focused functionality with explicit prerequisites when needed  
✓ **Clear dependencies:** flow_actions manage stage relationships  
✓ **Feature chains:** `depends_on` documents cross-feature prerequisites  
✓ **Mixed languages:** Tcl and Python stages work together  
✓ **Parallel execution:** optimize_pipeline enables efficient runs  
✓ **Reproducibility:** Project JSON captures exact configuration  
✓ **Traceability:** owner, vendor, tool fields document responsibility  

---

## 9. Common Modifications

### To disable power analysis:
Remove from project.json features list, OR create new project without it

### To run DFT only:
Use only base.json + feature_dft.json

### To add sequential dependency:
Modify flow_actions to use dependencies array

### To change from serial to parallel:
Set `"run_mode": "parallel"` on any stage

### To add new tool:
Create new base.json with updated tool field

---

## Conclusion

This real-world example demonstrates:
1. How to structure base.json with all three families
2. How to build composable features
3. How to use flow_actions for stage orchestration
4. How to support multiple languages and execution modes
5. How to package everything in a project.json

Use this as a template for your own domains!

