# Chopper — CLI Help Text Reference

> **Status:** Implementation Reference
> **Resolves:** E-10 (FINAL_PRODUCTION_REVIEW.md)
> **Purpose:** Canonical help text phrasing for all CLI subcommands. Implement `argparse` help strings from this file for consistency.

---

## Top-Level

```
usage: chopper [-h] [-v] [--debug] [--plain] [--no-color] [--json] [--strict]
               {validate,trim,cleanup} ...

Chopper — EDA TFM domain trimming tool.

Trims EDA tool flow domains to project-specific subsets using JSON
configuration. Supports whole-file (F1), proc-level (F2), and run-file
generation (F3) capabilities.

positional arguments:
  {validate,trim,cleanup}
    validate            Validate JSON inputs against domain structure
    trim                Execute the full trim pipeline
    cleanup             Remove domain backup after the trim window

options:
  -h, --help            show this help message and exit
  -v, --verbose         Increase verbosity (-v=INFO, -vv=DEBUG)
  --debug               Maximum verbosity with full stack traces
  --plain               Disable Rich rendering; use plain text output
  --no-color            Disable ANSI color codes
  --json                Emit machine-readable JSON to stdout
  --strict              Exit non-zero if any warning is present (does not rewrite severity)
```

---


## `chopper validate`

```
usage: chopper validate [--domain PATH]
                        (--base PATH [--features PATHS] | --project PATH)
                        [global options]

Run structural validation against JSON inputs. Checks schema
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
                    [--dry-run] [global options]

Execute the full trim pipeline: compile selections, trace proc dependencies,
build trimmed output, validate results, and emit audit trail.

First trim:  renames domain/ to domain_backup/, builds trimmed domain/.
Re-trim:     rebuilds domain/ from existing domain_backup/.
On failure:  remove half cooked domain/ and replace domain_backup/ as domain/.

options:
  --domain PATH       Domain root path (default: current directory)
  --base PATH         Path to base JSON (required unless --project is used)
  --features PATHS    Comma-separated ordered list of feature JSON paths
  --project PATH      Path to project JSON (mutually exclusive with --base/--features)
  --dry-run           Simulate the full pipeline without writing files
```

---

## `chopper cleanup`

```
usage: chopper cleanup [--domain PATH] --confirm [global options]

Remove domain_backup/ permanently after the trim window is complete.
This operation is irreversible. Requires --confirm flag.

options:
  --domain PATH   Domain root path (default: current directory)
  --confirm       Required confirmation flag (cleanup refuses to run without it)
```

---

## Phrasing Rules

1. **Subcommand descriptions** use imperative verb: "Validate JSON inputs...", "Execute the full trim pipeline...", "Remove domain_backup..."
2. **Option help text** is a short noun phrase or clause; no trailing period.
3. **Default values** shown in parentheses: `(default: current directory)`.
4. **Mutual exclusivity** described as: `(mutually exclusive with --base/--features)`.
5. **Required conditionals** described as: `(required unless --project is used)`.
6. **--confirm** never has a default; it is explicitly required for destructive operations.
