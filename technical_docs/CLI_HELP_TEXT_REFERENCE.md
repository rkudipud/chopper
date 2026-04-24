# Chopper — CLI Help Text Reference

> **Status:** Implementation Reference
> **Resolves:** E-10 (FINAL_PRODUCTION_REVIEW.md)
> **Purpose:** Canonical help text phrasing for all CLI subcommands. Implement `argparse` help strings from this file for consistency.

---

## Top-Level

```text
usage: chopper [-h] [-v] [-q] [--plain] [--strict]
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
  -q, --quiet           Suppress progress output (CI / grid)
  --plain               Disable Rich rendering and ANSI colors; use plain text output
  --strict              Exit non-zero if any warning is present (does not rewrite severity)
```

> **Flag scope.** `--debug`, `--no-color`, and `--json` were considered and cut per [`DAY0_REVIEW.md`](DAY0_REVIEW.md) A1. Rich honors `NO_COLOR` automatically; `diagnostics.json` in the audit bundle is the machine-readable surface. Machine-readable stdout is tracked as [`FD-10`](FUTURE_PLANNED_DEVELOPMENTS.md#fd-10-machine-readable-cli-output).

---

## `chopper validate`

```text
usage: chopper validate [--domain PATH]
                        (--base PATH [--features PATHS] | --project PATH)
                        [global options]

Run read-only validation against JSON inputs. Checks schema
compliance, required fields, file/proc existence, action targets,
parses Tcl, compiles selections, and runs the trace phase.
Does not modify domain content files.

options:
  --domain PATH       Domain root path (default: current directory)
  --base PATH         Path to base JSON (required unless --project is used)
  --features PATHS    Comma-separated ordered list of feature JSON paths
  --project PATH      Path to project JSON (mutually exclusive with --base/--features)
```

---

## `chopper trim`

```text
usage: chopper trim [--domain PATH]
                    (--base PATH [--features PATHS] | --project PATH)
                    [--dry-run] [global options]

Execute the full trim pipeline: compile selections, trace proc dependencies,
build trimmed output, validate results, and emit audit trail.

First trim:  renames domain/ to domain_backup/, builds trimmed domain/.
Re-trim:     rebuilds domain/ from existing domain_backup/.
On failure:  leave state as-is and exit non-zero; re-run to resume (the next
             run detects the leftover state and rebuilds from domain_backup/),
             or manually run `rm -rf domain && mv domain_backup domain` to reset.

options:
  --domain PATH       Domain root path (default: current directory)
  --base PATH         Path to base JSON (required unless --project is used)
  --features PATHS    Comma-separated ordered list of feature JSON paths
  --project PATH      Path to project JSON (mutually exclusive with --base/--features)
  --dry-run           Compile, trace, run synthetic post-trim validation, and emit reports without rebuilding domain content files
```

---

## `chopper cleanup`

```text
usage: chopper cleanup [--domain PATH] --confirm [global options]

Remove domain_backup/ permanently after the trim window is complete.
This operation is irreversible. Requires --confirm flag.

options:
  --domain PATH   Domain root path (default: current directory)
  --confirm       Required confirmation flag (cleanup refuses to run without it)
```

---

## `chopper mcp-serve`

```text
usage: chopper mcp-serve [global options]

Start a stdio-only Model Context Protocol server. Exposes exactly three
read-only tools: chopper.validate, chopper.explain_diagnostic, chopper.read_audit.
Never registers chopper.trim or chopper.cleanup. Reads JSON-RPC frames on
stdin, writes responses on stdout, logs to stderr. Exits 0 on clean shutdown
(stdin EOF / SIGINT), 3 on programmer error, 4 on MCP protocol error.

No options specific to this subcommand. See `technical_docs/chopper_description.md`
§3.9 for the authoritative contract and tool parameter schemas.
```

---

## Phrasing Rules

1. **Subcommand descriptions** use imperative verb: "Validate JSON inputs...", "Execute the full trim pipeline...", "Remove domain_backup..."
2. **Option help text** is a short noun phrase or clause; no trailing period.
3. **Default values** shown in parentheses: `(default: current directory)`.
4. **Mutual exclusivity** described as: `(mutually exclusive with --base/--features)`.
5. **Required conditionals** described as: `(required unless --project is used)`.
6. **--confirm** never has a default; it is explicitly required for destructive operations.
