# Chopper JSON Kit — Standalone Package

**Version:** 1.0.0  
**Date:** April 2026  
**Status:** Shippable before Chopper runtime

This package gives teams everything needed to author, validate, and organize Chopper JSON files — no Chopper installation required.

---

## What Is This?

Chopper trims EDA tool domain codebases via three JSON configuration files:

| File | Purpose |
|------|---------|
| **Base JSON** | Defines the minimal viable flow for a domain (files, procs, stages) |
| **Feature JSON** | Extends or overrides the base for optional or project-specific scenarios |
| **Project JSON** | Selects and orders one base + zero or more features for a specific trim run |

You author these JSONs now. When Chopper is released, you run `chopper trim --project project.json` and it does the rest.

---

## Package Contents

```
standalone_json_kit/
├── README.md                        ← You are here
├── VERSION.txt                      ← Schema version tracking
├── schemas/
│   ├── base-v1.schema.json          ← Base JSON schema (authoritative validator)
│   ├── feature-v1.schema.json       ← Feature JSON schema
│   └── project-v1.schema.json       ← Project JSON schema
├── docs/
│   └── JSON_AUTHORING_GUIDE.md      ← Complete field reference, rules, decision guide
├── examples/
│   ├── 01_base_files_only/          ← files.include + files.exclude only
│   ├── 02_base_procs_only/          ← procedures.include + procedures.exclude only
│   ├── 03_base_stages_only/         ← stages only (run-file generation)
│   ├── 04_base_files_and_procs/     ← files + procedures (no stages)
│   ├── 05_base_files_and_stages/    ← files + stages
│   ├── 06_base_procs_and_stages/    ← procedures + stages
│   ├── 07_base_full/                ← files + procedures + stages (maximum control)
│   ├── 08_base_plus_one_feature/    ← base + one feature + project
│   ├── 09_base_plus_multiple_features/ ← base + two independent features + project
│   ├── 10_chained_features_depends_on/ ← three-level depends_on chain + project
│   ├── 11_project_base_only/        ← base-only trim (no features)
│   └── 12_fev_formality_domain/     ← Real-world example: Synopsys Formality FEV
└── agent/
    └── DOMAIN_ANALYZER.md           ← Agent instructions for codebase analysis and JSON authoring
```

---

## 10-Minute Quick Start

### 1. Choose your starting example

| Your situation | Start with |
|---------------|-----------|
| Need to trim files only | `examples/01_base_files_only/` |
| Need proc-level surgical trimming | `examples/02_base_procs_only/` |
| Have stack files to translate | `examples/03_base_stages_only/` |
| Full control (files + procs + stages) | `examples/07_base_full/` |
| Single optional feature | `examples/08_base_plus_one_feature/` |
| Multiple independent features | `examples/09_base_plus_multiple_features/` |
| Features depend on each other | `examples/10_chained_features_depends_on/` |
| Real EDA domain (Formality-style) | `examples/12_fev_formality_domain/` |

### 2. Copy and adapt

```bash
cp -r examples/07_base_full/ my_domain/chopper/
cd my_domain/chopper/
# Edit base.json: change domain, owner, file lists, stage definitions
```

### 3. Validate against schemas

```bash
pip install jsonschema
python - <<'EOF'
import json, jsonschema, pathlib

schema_dir = pathlib.Path("standalone_json_kit/schemas")
schemas = {
    "chopper/base/v1":    json.load(open(schema_dir / "base-v1.schema.json")),
    "chopper/feature/v1": json.load(open(schema_dir / "feature-v1.schema.json")),
    "chopper/project/v1": json.load(open(schema_dir / "project-v1.schema.json")),
}

for f in pathlib.Path("my_domain").rglob("*.json"):
    data = json.load(open(f))
    sid = data.get("$schema")
    if sid in schemas:
        try:
            jsonschema.validate(data, schemas[sid])
            print(f"OK  {f}")
        except jsonschema.ValidationError as e:
            print(f"ERR {f}: {e.message}")
EOF
```

### 4. Use the domain analyzer agent

Open `agent/DOMAIN_ANALYZER.md` in your AI assistant (Copilot, Claude, etc.) as a system prompt or instruction file. Then ask:

> "Analyze my domain directory at `my_domain/` and help me author the base, feature, and project JSONs."

The agent follows an 8-phase process: inventory → stack extraction → proc extraction → base/feature split → authoring → validation.

---

## Adapting from `fev_formality` to Your Domain

The `examples/12_fev_formality_domain/` example directly reflects the `fev_formality` codebase. Here is how the method generalizes:

| fev_formality pattern | Your domain equivalent |
|----------------------|----------------------|
| `default_fm_procs.tcl` | Your domain's core proc library |
| `*.stack` files with `N/J/L/D/I/O` | Your tool's job scheduler stack format |
| `prepare_fev_formality.tcl` | Your domain's environment setup script |
| `fev_fm_eco.stack` (optional flow) | Any optional flow → goes in a feature |
| `fev_fm_lite.stack` (lightweight variant) | Any variant flow → goes in a feature |
| `promote.tcl` (post-run artifact push) | Your domain's artifact promotion script |
| `utils/targ_synth/` (optional helper) | Any optional utility → `files.exclude` in base or omit |

---

## Where to Put Your JSON Files

Convention (following the `fev_formality` model):

```
<domain_root>/
└── chopper/
    ├── base.json
    └── features/
        ├── feature_a.json
        ├── feature_b.json
        └── project_abc.json
```

Or at the project level:

```
projects/<PROJECT_ID>/
└── chopper/
    ├── project.json         ← points to domain base + selected features
```

Paths in `project.json` are relative to the domain root (where Chopper will be invoked).

---

## Key Rules (Quick Reference)

1. **`$schema` is always required** and must be the exact literal string (e.g., `"chopper/base/v1"`).
2. **Base needs at least one of:** `files`, `procedures`, `stages`.
3. **Arrays must never be empty** when present — `minItems: 1` is enforced by schema.
4. **Paths:** forward slashes only, no `..`, no `//`, no absolute paths.
5. **`depends_on`** uses feature `name` values, not file paths.
6. **Project feature order** must satisfy all `depends_on` declarations (prerequisites first).
7. **`load_from` ≠ `dependencies`:** `load_from` = data predecessor for run script; `dependencies` = stack `D` line (scheduler order).

---

## Getting Help

- `docs/JSON_AUTHORING_GUIDE.md` — full field reference, all rules, decision flowchart
- `agent/DOMAIN_ANALYZER.md` — step-by-step domain analysis instructions for AI assistants
- `examples/` — working JSON files for every combination
- Schema files in `schemas/` are the authoritative validators — when in doubt, validate
