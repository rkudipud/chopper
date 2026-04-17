# Chopper — CLI Help Text Reference

> **Status:** Implementation Reference
> **Last Updated:** 2026-04-05
> **Resolves:** E-10 (FINAL_PRODUCTION_REVIEW.md)
> **Purpose:** Canonical help text phrasing for all CLI subcommands. Implement `argparse` help strings from this file for consistency.

---

## Top-Level

```
usage: chopper [-h] [-v] [--debug] [--plain] [--no-color] [--json] [--strict]
               {scan,validate,trim,cleanup} ...

Chopper — EDA TFM domain trimming tool.

Trims EDA tool flow domains to project-specific subsets using JSON
configuration. Supports whole-file (F1), proc-level (F2), and run-file
generation (F3) capabilities.

positional arguments:
  {scan,validate,trim,cleanup}
    scan                Scan a domain and generate draft JSONs for owner curation
    validate            Validate JSON inputs against domain structure (Phase 1 only)
    trim                Execute the full trim pipeline
    cleanup             Remove domain backup after the trim window

options:
  -h, --help            show this help message and exit
  -v, --verbose         Increase verbosity (-v=INFO, -vv=DEBUG)
  --debug               Maximum verbosity with full stack traces
  --plain               Disable Rich rendering; use plain text output
  --no-color            Disable ANSI color codes
  --json                Emit machine-readable JSON to stdout
  --strict              Treat warnings as errors
```

---

## `chopper scan`

```
usage: chopper scan [--domain PATH] [--output DIR] [global options]

Scan a domain to discover files, procs, and dependencies. Produces draft
base JSON, inventories, and dependency graphs for domain owner curation.
Does not modify domain files.

options:
  --domain PATH   Domain root path (default: current directory)
  --output DIR    Output directory for scan artifacts (default: scan_output/)
```

---

## `chopper validate`

```
usage: chopper validate [--domain PATH]
                        (--base PATH [--features PATHS] | --project PATH)
                        [global options]

Run Phase 1 structural validation against JSON inputs. Checks schema
compliance, required fields, file/proc existence, and action targets.
Does not build a proc index, run tracing, or modify files.

options:
  --domain PATH       Domain root path (default: current directory)
  --base PATH         Path to base JSON (required unless --project is used)
  --features PATHS    Comma-separated ordered list of feature JSON paths
  --project PATH      Path to project JSON (mutually exclusive with --base/--features)
```

---

## `chopper trim`

```
usage: chopper trim [--domain PATH]
                    (--base PATH [--features PATHS] | --project PATH)
                    [--dry-run] [--force] [global options]

Execute the full trim pipeline: compile selections, trace proc dependencies,
build trimmed output, validate results, and emit audit trail.

First trim:  renames domain/ to domain_backup/, builds trimmed domain/.
Re-trim:     rebuilds domain/ from existing domain_backup/.
On failure:  restores pre-run state automatically.

options:
  --domain PATH       Domain root path (default: current directory)
  --base PATH         Path to base JSON (required unless --project is used)
  --features PATHS    Comma-separated ordered list of feature JSON paths
  --project PATH      Path to project JSON (mutually exclusive with --base/--features)
  --dry-run           Simulate the full pipeline without writing files
  --force             Clean up abandoned lock metadata (never breaks active locks)
```

---

## `chopper cleanup`

```
usage: chopper cleanup [--domain PATH] --confirm [--force] [global options]

Remove domain_backup/ permanently after the trim window is complete.
This operation is irreversible. Requires --confirm flag.

options:
  --domain PATH   Domain root path (default: current directory)
  --confirm       Required confirmation flag (cleanup refuses to run without it)
  --force         Clean up abandoned lock metadata (never breaks active locks)
```

---

## Phrasing Rules

1. **Subcommand descriptions** use imperative verb: "Scan a domain...", "Validate JSON inputs...", "Execute the full trim pipeline...", "Remove domain_backup..."
2. **Option help text** is a short noun phrase or clause; no trailing period.
3. **Default values** shown in parentheses: `(default: current directory)`.
4. **Mutual exclusivity** described as: `(mutually exclusive with --base/--features)`.
5. **Required conditionals** described as: `(required unless --project is used)`.
6. **--confirm** never has a default; it is explicitly required for destructive operations.
