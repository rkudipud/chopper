# Chopper — CLI Reference

> **Purpose:** Canonical reference for all CLI subcommands, flags, and help text. The `argparse` help strings in `src/chopper/cli/` are derived from this file; the two must stay in lockstep.

---

## Top-Level

```text
usage: chopper [-h] [--version] [-v] [-q] [--plain] [--strict]
               {validate,trim,loc,cleanup} ...

Chopper — EDA TFM domain trimming tool.

Trims EDA tool flow domains to project-specific subsets using JSON
configuration. Supports whole-file (F1), proc-level (F2), and run-file
generation (F3) capabilities.

positional arguments:
  {validate,trim,loc,cleanup}
    validate            Validate JSON inputs against domain structure
    trim                Execute the full trim pipeline
    loc                 Print a read-only LOC report (no `.chopper/` written)
    cleanup             Remove domain backup after the trim window

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
  --domain PATH        Domain root — accepts three forms (4.1.0+):
                       (1) Absolute path, used as-is.
                       (2) Existing relative directory, used as-is.
                       (3) Logical name (e.g. ``fev_formality`` or ``snps/fev_formality``)
                           resolved via ``$WARD/global/<vendor>/<name>``.
                       Also accepts a comma-separated list for multi-domain runs (§5.1.2).
                       If the resolved path ends in ``_backup`` and a stripped sibling exists,
                       redirects to that sibling and emits VI-03.
                       Default: current working directory. See ARCHITECTURE.md §5.1.0.
  --base PATH          Path to base JSON. Optional when ``--domain`` provides a named domain;
                       Chopper auto-discovers ``<domain>/jsons/base.json`` (VE-35 if not found).
                       Required when using a plain path domain and ``--project`` is not used.
  --features PATHS     Comma-separated ordered list of feature JSON paths or names (4.1.0+).
                       Names (e.g. ``dft,power``) are resolved from ``<domain>/jsons/features/*.feature.json``.
                       Tokens containing ``/`` or ending with ``.json`` pass through as file paths.
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
  --domain PATH        Domain root — same three forms as ``chopper validate`` (see above).
                       Also accepts CSV for multi-domain runs (§5.1.2).
                       Default: current working directory. See ARCHITECTURE.md §5.1.0.
  --base PATH          Path to base JSON. Optional when ``--domain`` provides a named domain;
                       Chopper auto-discovers ``<domain>/jsons/base.json`` (VE-35 if not found).
  --features PATHS     Comma-separated ordered list of feature JSON paths or names.
                       Names resolved from ``<domain>/jsons/features/*.feature.json``.
  --project PATH       Path to project JSON (mutually exclusive with --base/--features)
  --tool-commands PATH Path to a plain-text file of known external tool-command
                       names. Repeatable. Extends the built-in tool-command
                       pool so TW-02 unresolved-proc-call becomes TI-01
                       known-tool-command for listed names during P4 trace.
                       See architecture doc §3.10.
  --dry-run            Compile, trace, run synthetic post-trim validation, and emit reports without rebuilding domain content files
```

The `.chopper/` audit bundle written by `chopper trim` includes
`p4_commands.txt` — a sorted Perforce command list with `p4 edit -t text+x` /
`p4 add -t text+x` sections, and an `exclude_file_list` section of
`$WARD`-relative paths for files to remove from the depot (4.1.0+, replaces
former `p4 delete` commands). Chopper never invokes `p4` itself.
A P4 branch analysis summary is printed to stdout after every run. See
architecture doc §5.5.14, §5.5.15, and FR-47/FR-48.

---

## `chopper loc`

```text
usage: chopper loc [--domain PATH]
                   (--base PATH [--features PATHS] | --project PATH)
                   [--tool-commands PATH]... [global options]

Print a read-only LOC report comparing the source domain against the
rebuilt trimmed domain. Runs the same P0–P4 + dry-run-P6 pipeline as
`chopper trim --dry-run`, then **replays the real P5 trim phases**
(trim → generators → indentation → companion-sync) against an
in-memory copy of the source tree and counts the *actual* rebuilt
output, then emits a stdout table:

  - Files before / after / net change
  - Physical lines before / after / percent reduction
  - SLOC (non-blank, non-comment) before / after / percent reduction
  - Per-treatment breakdown (FULL_COPY / PROC_TRIM / REMOVE / GENERATED)

Writes nothing to the real filesystem — no domain modifications and no
`.chopper/` audit bundle (the trim replay happens entirely in memory).
Diagnostics emitted along the P0–P4 path are
still summarized to stderr. Exit codes match `validate`: 0 clean,
1 validation errors (or `--strict` with warnings), 2 CLI/environment
error, 3 internal programmer error.

options:
  --domain PATH        Domain root — same three forms as ``chopper validate``.
                       Also accepts CSV for multi-domain runs (§5.1.2).
                       Default: current working directory. See ARCHITECTURE.md §5.1.0.
  --base PATH          Path to base JSON. Optional when domain is a named domain (auto-discovery).
  --features PATHS     Comma-separated ordered list of feature JSON paths or names.
                       Names resolved from ``<domain>/jsons/features/*.feature.json``.
                       Any entry may also be a directory (validate-only expansion).
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
  a prior `chopper trim` left it behind), `loc` seeds the in-memory replay
  from the backup, not
  the already-trimmed `<domain>/`. This mirrors the parser and keeps the
  "before" numbers stable across re-runs.
- **PROC_TRIM after-count is the real trimmed file,** measured from the
  in-memory replay of the production `ProcDropper` — not a span-masking
  reconstruction.
- **P5c indentation and P5d companion-sync are modeled.** The replay runs
  the optional P5c whitespace-only indentation pass and the P5d companion
  sync, exactly as live trim does.
- **Default-exclude.** A counted-extension file under `<domain>/` that the
  merged manifest never names is reported under `treatment.REMOVE.*`.
- **`.chopper/` is excluded** from the enumeration.
- **Decode fallback.** Files that fail both UTF-8 and latin-1 decode are
  silently dropped from the report.
- **Byte-identical to a live trim.** Because `loc` reuses the production P5
  services against an in-memory filesystem, its totals match `chopper trim`
  and the audit bundle's `trim_stats.json` exactly — it is a real
  (in-memory) trim, not a separate projection that could drift.

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

## Phrasing Rules

1. **Subcommand descriptions** use imperative verb: "Validate JSON inputs...", "Execute the full trim pipeline...", "Remove domain_backup..."
2. **Option help text** is a short noun phrase or clause; no trailing period.
3. **Default values** shown in parentheses: `(default: current directory)`.
4. **Mutual exclusivity** described as: `(mutually exclusive with --base/--features)`.
5. **Required conditionals** described as: `(required unless --project is used)`.
6. **--confirm** never has a default; it is explicitly required for destructive operations.
