# Chopper — CLI Reference

> **Purpose:** Canonical reference for all CLI subcommands, flags, and help text. The `argparse` help strings in `src/chopper/cli/` are derived from this file; the two must stay in lockstep.

---

## Top-Level

```text
usage: chopper [-h] [--version] [-v] [-q] [--plain] [--strict]
               {validate,trim,loc,cleanup,mcp-serve} ...

Chopper — EDA TFM domain trimming tool.

Trims EDA tool flow domains to project-specific subsets using JSON
configuration. Supports whole-file (F1), proc-level (F2), and run-file
generation (F3) capabilities.

positional arguments:
  {validate,trim,loc,cleanup,mcp-serve}
    validate            Validate JSON inputs against domain structure
    trim                Execute the full trim pipeline
    loc                 Print a read-only LOC report (no `.chopper/` written)
    cleanup             Remove domain backup after the trim window
    mcp-serve           Start a stdio-only read-only MCP server

options:
  -h, --help            show this help message and exit
  --version             Show program version and exit
  -v, --verbose         Increase verbosity (-v=INFO, -vv=DEBUG)
  -q, --quiet           Suppress progress output (CI / grid)
  --plain               Disable Rich rendering and ANSI colors; use plain text output
  --strict              Exit non-zero if any warning is present (does not rewrite severity)
```

> **Flag scope.** `--debug`, `--no-color`, and `--json` were considered and cut per [`DAY0_REVIEW.md`](DAY0_REVIEW.md) A1. Rich honors `NO_COLOR` automatically; `diagnostics.json` in the audit bundle is the machine-readable surface. Machine-readable stdout is tracked as `FD-10` in [`IMPLEMENTATION.md`](IMPLEMENTATION.md) Future Considerations section. `--version` prints `chopper <version>` and exits 0; it is a top-level global flag and does not require a subcommand.

---

## `chopper validate`

```text
usage: chopper validate [--domain PATH]
                        (--base PATH [--features PATHS] | --project PATH)
                        [--tool-commands PATH]...
                        [global options]

Run read-only validation against JSON inputs. Checks schema
compliance, required fields, file/proc existence, action targets,
parses Tcl, compiles selections, and runs the trace phase.
Does not modify domain content files.

options:
  --domain PATH        Domain root path (default: current directory). If the path ends in `_backup` and the stripped sibling exists as a directory, redirects to that sibling and emits VI-03 (otherwise honored as-is). Takes precedence over cwd. See ARCHITECTURE.md §5.1.
  --base PATH          Path to base JSON (required unless --project is used)
  --features PATHS     Comma-separated ordered list of feature JSON paths.
                       Validate-only: any entry may also be a directory, which
                       expands in place to its sorted *.json children (non-recursive).
  --project PATH       Path to project JSON (mutually exclusive with --base/--features)
  --tool-commands PATH Path to a plain-text file of known external tool-command
                       names (whitespace-separated tokens, '#' comments, blank
                       lines ignored). Repeatable. Each file extends the pool
                       of names that silence TW-02 unresolved-proc-call in P4
                       trace and emit TI-01 known-tool-command instead. The
                       built-in lists under src/chopper/data/tool_commands/
                       (e.g. pt.commands) are always loaded; this flag only
                       adds to that set. No effect on F1/F2/F3 decisions.
                       See architecture doc §3.10.
```

---

## `chopper trim`

```text
usage: chopper trim [--domain PATH]
                    (--base PATH [--features PATHS] | --project PATH)
                    [--tool-commands PATH]... [--dry-run] [global options]

Execute the full trim pipeline: compile selections, trace proc dependencies,
build trimmed output, validate results, and emit audit trail.

First trim:  renames domain/ to domain_backup/, builds trimmed domain/.
Re-trim:     rebuilds domain/ from existing domain_backup/.
On failure:  leave state as-is and exit non-zero; re-run to resume (the next
             run detects the leftover state and rebuilds from domain_backup/),
             or manually run `rm -rf domain && mv domain_backup domain` to reset.

options:
  --domain PATH        Domain root path (default: current directory). If the path ends in `_backup` and the stripped sibling exists as a directory, redirects to that sibling and emits VI-03 (otherwise honored as-is). Takes precedence over cwd. See ARCHITECTURE.md §5.1.
  --base PATH          Path to base JSON (required unless --project is used)
  --features PATHS     Comma-separated ordered list of feature JSON paths
  --project PATH       Path to project JSON (mutually exclusive with --base/--features)
  --tool-commands PATH Path to a plain-text file of known external tool-command
                       names. Repeatable. Extends the built-in tool-command
                       pool so TW-02 unresolved-proc-call becomes TI-01
                       known-tool-command for listed names during P4 trace.
                       See architecture doc §3.10.
  --dry-run            Compile, trace, run synthetic post-trim validation, and emit reports without rebuilding domain content files
```

The `.chopper/` audit bundle written by `chopper trim` includes
`p4_commands.txt` — a sorted, ready-to-execute Perforce command list
(`p4 edit -t text+x` / `p4 add -t text+x` / `p4 delete`) correlating each
file-treatment decision to the command needed to record the change
against the depot. Chopper never invokes `p4` itself; review the file and
run `p4 submit` manually. See architecture doc §5.5.14 and FR-47.

---

## `chopper loc`

```text
usage: chopper loc [--domain PATH]
                   (--base PATH [--features PATHS] | --project PATH)
                   [--tool-commands PATH]... [global options]

Print a read-only LOC report comparing the source domain against the
planned trimmed domain. Runs the same P0–P4 + dry-run-P6 pipeline as
`chopper trim --dry-run`, additionally invokes the F3 generator in
no-write mode so generated stage `.tcl` content is countable, then
emits a stdout table:

  - Files before / after / net change
  - Physical lines before / after / percent reduction
  - SLOC (non-blank, non-comment) before / after / percent reduction
  - Per-treatment breakdown (FULL_COPY / PROC_TRIM / REMOVE / GENERATED)

Writes nothing to the filesystem — no domain modifications and no
`.chopper/` audit bundle. Diagnostics emitted along the P0–P4 path are
still summarized to stderr. Exit codes match `validate`: 0 clean,
1 validation errors (or `--strict` with warnings), 2 CLI/environment
error, 3 internal programmer error. `loc` cannot return 4.

options:
  --domain PATH        Domain root path (default: current directory).
  --base PATH          Path to base JSON (required unless --project is used)
  --features PATHS     Comma-separated ordered list of feature JSON paths
  --project PATH       Path to project JSON (mutually exclusive with --base/--features)
  --tool-commands PATH Path to a plain-text file of known external tool-command
                       names. Repeatable. Same semantics as `chopper trim`.
                       See architecture doc §3.10.
```

See [`technical_docs/ARCHITECTURE.md`](ARCHITECTURE.md) §5.7 for the per-treatment
line-accounting contract.

### Counted file types

The source-domain walk uses a fixed extension allow-list. Files whose
extension is **not** in this list are skipped — they neither contribute to
the "before" totals nor count as REMOVE candidates.

| Counted | Extensions | SLOC rule |
|---|---|---|
| yes | `.tcl`, `.py`, `.pl`, `.pm`, `.sh`, `.bash`, `.csh`, `.tcsh`, `.zsh`, `.ksh` | non-blank, non-full-`#`-line; shell `#!` shebang on line 1 counts |
| yes | `.json` | every non-blank line |
| yes | `.csv` | every line that contains a non-comma, non-whitespace token |
| no | everything else (`.v`, `.sv`, `.vhd`, `.lib`, `.def`, `.spef`, `.md`, `.txt`, binaries, …) | silently skipped |

Generated stage artifacts are language-detected the same way — a generated
`<stage>.tcl` follows the hash-comment SLOC rule.

### Caveats

- **Source-root resolution.** If `<domain>_backup/` exists on disk (because
  a prior `chopper trim` left it behind), `loc` enumerates the backup, not
  the already-trimmed `<domain>/`. This mirrors the parser and keeps the
  "before" numbers stable across re-runs.
- **PROC_TRIM after-count is reconstructed,** not measured: it masks the
  `ProcEntry` line spans (body + leading DPA + leading comment block when
  captured) from the source and recounts.
- **P5c indentation pass is not modeled.** It is whitespace-only and does
  not change SLOC; physical-line counts are unaffected in practice.
- **Default-exclude.** A counted-extension file under `<domain>/` that the
  merged manifest never names is reported under `treatment.REMOVE.*`.
- **`.chopper/` is excluded** from the enumeration.
- **Decode fallback.** Files that fail both UTF-8 and latin-1 decode are
  silently dropped from the report.
- **No audit cross-check.** `loc` skips P7, so there is no
  `trim_report.json` written to compare against; the numbers are a
  planner-side projection.

---

## `chopper cleanup`

```text
usage: chopper cleanup [--domain PATH] --confirm [global options]

Remove domain_backup/ permanently after the trim window is complete.
This operation is irreversible. Requires --confirm flag.

options:
  --domain PATH   Domain root path (default: current directory). If the path ends in `_backup` and the stripped sibling exists as a directory, redirects to that sibling and emits VI-03 (otherwise honored as-is). Takes precedence over cwd. See ARCHITECTURE.md §5.1.
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

No options specific to this subcommand. See `technical_docs/ARCHITECTURE.md`
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
