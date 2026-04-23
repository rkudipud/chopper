# Chopper JSON Kit — Agent Instructions

This repository is a **standalone JSON authoring kit** for Chopper, an EDA tool domain trimmer. It ships before the Chopper runtime and lets domain engineers author and validate all three Chopper JSON types independently.

## What This Repo Contains

| Path | Purpose |
|------|---------|
| `schemas/` | Authoritative JSON Schema files (Draft-07) for base, feature, and project JSONs |
| `docs/JSON_AUTHORING_GUIDE.md` | Complete field reference, stack-file semantics, authoring rules, decision guide |
| `examples/` | Working JSON files for every combination of base / feature / project |
| `agent/DOMAIN_ANALYZER.md` | Detailed domain analysis instructions for authoring Chopper JSONs from a codebase |

This folder is intended to be self-contained. It can be handed off before the Chopper runtime ships, and the Chopper runtime later consumes the schema files in `schemas/` directly.

## Your Primary Task

When a user asks for help authoring Chopper JSONs, follow the 8-phase protocol in [`agent/DOMAIN_ANALYZER.md`](agent/DOMAIN_ANALYZER.md):

1. **Discover** the domain directory structure — ask for a file listing before assuming anything
2. **Extract** stage definitions from scheduler stack files (N/J/L/D/I/O → JSON fields)
3. **Classify** procs as core, feature-specific, or deprecated
4. **Split** content between `base.json` (universal) and feature JSONs (optional/conditional)
5. **Author** valid JSON instances using the templates in `agent/DOMAIN_ANALYZER.md`
6. **Validate** each file against the schemas in `schemas/`

The expected workflow is: analyze the user-provided codebase, help the user generate `jsons/base.json` and any needed feature JSONs, then validate them with `validate_jsons.py`.

User collaboration quality is a primary requirement. Analysis and JSON authoring should be done hand-in-hand with the user rather than as a blind one-shot generation pass.

## Proc Call Tracing Requirement

When users need help deciding file/proc include and exclude settings, you must perform a proc-call tracing pass using the analyzer protocol:

- Build a call tree from discovered entry procs and their reachable callees
- Produce a generated trace log that shows roots, call edges, unresolved calls, and per-file proc coverage
- Use that log to recommend `procedures.include`, `procedures.exclude`, `files.include`, and `files.exclude`
- Keep guidance conservative: prefer include recommendations first, then propose excludes for debug/deprecated content

The trace log is a curation aid for JSON authoring speed and codebase understanding. It helps users review why each proc or file was included or excluded before finalizing JSONs.

## Interactive Feedback Requirement

The agent must pause at key checkpoints and ask for user feedback before final JSON authoring decisions:

- Ask for top-level domain file/directory listing before call-tree construction
- Ask the user where the domain boundary stops before analyzing; in most cases this is the current working directory / domain root
- Ask users which top-level files are authoritative entry points for call-tree roots
- If user points to a proc file, trace call trees from every proc in that file across other files
- After showing inventory and after showing the proc trace log, ask user to confirm or correct classification

Use the feedback to refine include/exclude recommendations before writing final `base.json`, feature JSONs, and `project.json`.

Do not go outside the user-confirmed domain boundary during analysis or recommendation generation.

## EDA Command vs Proc Disambiguation

During call tracing, distinguish EDA tool commands from domain proc calls:

- Treat tool-shell command invocations (for example Synopsys/Cadence shell commands and app commands) as commands, not proc edges
- Build call-tree edges only for user/domain proc-to-proc invocations
- Keep a separate "external command" note in the trace log when useful, but do not mix those with proc reachability

## The Three JSON Types

| Type | Schema `$id` | File | Purpose |
|------|-------------|------|---------|
| Base | `chopper/base/v1` | `jsons/base.json` | Minimal viable flow — files, procs, stages |
| Feature | `chopper/feature/v1` | `jsons/features/<feature_name>.feature.json` | Optional extension or override of the base |
| Project | `chopper/project/v1` | `project.json` | Selects and orders one base + zero or more features |

## Key Rules to Enforce

- JSON file naming scheme: `jsons/base.json` and `jsons/features/<feature_name>.feature.json`
- Assume the target runtime environment is Unix with `tcsh`/`csh` as the primary shell. If that analysis path fails or the domain clearly uses a different shell model, fall back to `bash`-style analysis, and only then to Windows-based analysis.
- `$schema` is always required (exact literal string)
- All arrays must have `minItems: 1` — never leave empty arrays; omit the field instead
- All paths: forward slashes, no `..`, no `//`, no absolute paths
- `depends_on` values are feature `name` strings, not file paths
- Project `features` list order must satisfy all `depends_on` declarations (prerequisites first)
- `load_from` ≠ `dependencies`: `load_from` = run-script data predecessor; `dependencies` = scheduler `D` line

## Quick Validation

Run the helper script from repo root:

```bash
python validate_jsons.py
```

Or validate only one folder:

```bash
python validate_jsons.py examples/08_base_plus_one_feature/
```

Manual fallback:

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
- **Validating existing JSONs?** → Run `python validate_jsons.py <path>` from the repo root
