# Chopper JSON Kit — Agent Instructions

This repository is a **standalone JSON authoring kit** for Chopper, an EDA tool domain trimmer. It ships before the Chopper runtime and lets domain engineers author and validate all three Chopper JSON types independently.

## What This Repo Contains

| Path | Purpose |
|------|---------|
| `schemas/` | Authoritative JSON Schema files (Draft-07) for base, feature, and project JSONs |
| `docs/JSON_AUTHORING_GUIDE.md` | Complete field reference, stack-file semantics, authoring rules, decision guide |
| `examples/` | Working JSON files for every combination of base / feature / project |
| `agent/DOMAIN_ANALYZER.md` | Detailed domain analysis instructions for authoring Chopper JSONs from a codebase |

## Your Primary Task

When a user asks for help authoring Chopper JSONs, follow the 8-phase protocol in [`agent/DOMAIN_ANALYZER.md`](agent/DOMAIN_ANALYZER.md):

1. **Discover** the domain directory structure — ask for a file listing before assuming anything
2. **Extract** stage definitions from scheduler stack files (N/J/L/D/I/O → JSON fields)
3. **Classify** procs as core, feature-specific, or deprecated
4. **Split** content between `base.json` (universal) and feature JSONs (optional/conditional)
5. **Author** valid JSON instances using the templates in `agent/DOMAIN_ANALYZER.md`
6. **Validate** each file against the schemas in `schemas/`

## The Three JSON Types

| Type | Schema `$id` | File | Purpose |
|------|-------------|------|---------|
| Base | `chopper/base/v1` | `base.json` | Minimal viable flow — files, procs, stages |
| Feature | `chopper/feature/v1` | `feature_<name>.json` | Optional extension or override of the base |
| Project | `chopper/project/v1` | `project.json` | Selects and orders one base + zero or more features |

## Key Rules to Enforce

- `$schema` is always required (exact literal string)
- All arrays must have `minItems: 1` — never leave empty arrays; omit the field instead
- All paths: forward slashes, no `..`, no `//`, no absolute paths
- `depends_on` values are feature `name` strings, not file paths
- Project `features` list order must satisfy all `depends_on` declarations (prerequisites first)
- `load_from` ≠ `dependencies`: `load_from` = run-script data predecessor; `dependencies` = scheduler `D` line

## Quick Validation

```python
import json, jsonschema, pathlib

schema_dir = pathlib.Path("schemas")
schemas = {
    "chopper/base/v1":    json.load(open(schema_dir / "base-v1.schema.json")),
    "chopper/feature/v1": json.load(open(schema_dir / "feature-v1.schema.json")),
    "chopper/project/v1": json.load(open(schema_dir / "project-v1.schema.json")),
}
for f in pathlib.Path(".").rglob("*.json"):
    data = json.load(open(f))
    sid = data.get("$schema")
    if sid in schemas:
        try:
            jsonschema.validate(data, schemas[sid])
            print(f"OK  {f}")
        except jsonschema.ValidationError as e:
            print(f"ERR {f}: {e.message}")
```

## Where to Start

- **Reading docs?** → [`docs/JSON_AUTHORING_GUIDE.md`](docs/JSON_AUTHORING_GUIDE.md)
- **Copying an example?** → [`examples/`](examples/) — pick the folder matching your scenario
- **Analyzing a domain codebase?** → Open [`agent/DOMAIN_ANALYZER.md`](agent/DOMAIN_ANALYZER.md) and follow Phase 1
- **Validating existing JSONs?** → Run the validation snippet above from the repo root
