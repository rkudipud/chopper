# Chopper — Technical Implementation Pitfalls Guide
**Created:** April 5, 2026  
**Purpose:** Identify common mistakes to avoid during implementation  
**Audience:** Engineering team  

---

## Overview

This guide documents architectural decisions, subtle requirements, and common pitfalls derived from the documentation. Every item here represents either a decision boundary or a likely source of bugs if overlooked.

---

## PARSER MODULE — Highest Risk Area

### Pitfall P-01: Brace Tracking Invents Quote Context Inside Braced Bodies

**THE TRAP:**
```tcl
proc bad_tracking {args} {
    set text "this has { an unmatched brace without closing"
    set x 1
}
```

**Naïve Parser:** Treats `"` as opening a quoted-string context inside the brace-delimited proc body, ignores the `{` inside it, and incorrectly accepts the proc as balanced.

**Correct Behavior:** In a brace-delimited proc body, quotes are literal characters under Tcl Rule 6. The unescaped `{` in the example above still affects brace depth, so this input is syntactically invalid and must produce a parse error. Quote tracking is still needed for quote-delimited words outside braced bodies, such as unusual quoted proc-argument words before the body opens.

**Implementation Requirement:** State machine must track:
- `brace_depth` (current nesting level)
- whether the current word is brace-delimited or quote-delimited
- `in_quote` only while parsing quote-delimited words outside brace-delimited bodies
    - *Mitigation Note:* When quote tracking is active, explicitly check for escaped quotes `\"` to avoid falsely exiting the quoted context.
- `in_comment` (boolean: rest of line is comment?)

**Why It Matters:** Inventing quote context inside braced bodies makes the parser accept invalid Tcl and corrupts proc boundaries later in the file.

**Test:** Fixture `brace_in_string_literal` must fail with an unbalanced-brace parse diagnostic. Separate quoted-word handling before the body brace should be tested independently if implemented.

---

### Pitfall P-02: Backslash Continuation Breaks Line Counting

**THE TRAP:**
```tcl
proc split_def \
    {args} \
    {
    return 42
}
```

The parser must preserve the original line numbers for diagnostic reporting. If physical lines are joined, line numbers become incorrect.

**Correct Behavior:** Do NOT physically join lines. Track and count them separately.

**Implementation Requirement:**
- Read file as array of lines (preserving original line breaks)
- When encountering `\` at end of line, recognize it as a continuation signal
- Continue parsing the next line in the same logical command context
- Report line numbers as they appear in the source file (1-indexed, continuous)

**Why It Matters:** Error diagnostics must point to the exact line in the source file so domain owners can fix it.

**Test:** Fixture `backslash_line_continuation` must preserve original line numbers in proc spans.

---

### Pitfall P-03: Namespace Stack Must Persist Across Blocks

**THE TRAP:**
```tcl
namespace eval a {
    proc proc_a {} { return "a" }
}

proc top_level {} { return "top" }
```

After exiting `namespace eval a`, the parser must reset the namespace context back to empty (file root).

**Correct Behavior:** Namespace stack is LIFO. When exiting a `namespace eval` block, pop the stack.

**Implementation Requirement:**
- `namespace_stack` is a list/deque
- On `namespace eval <name> {`: push `<name>`
- On closing `}` for that block: pop
- Canonical name = `file.tcl::` + `"::".join(namespace_stack)` + `qualified_name`

**Why It Matters:** Incorrect namespace resolution makes proc names ambiguous; tracing fails.

**Test:** Fixture `nested_namespace_accumulates` + `namespace_reset_after_block` must pass.

---

### Pitfall P-04: Computed Proc Names Are Not Extracted

**THE TRAP:**
```tcl
proc ${prefix}_helper {args} { return "dynamic" }
```

Chopper CANNOT statically determine the proc name. It must log a WARNING and skip this proc.

**Correct Behavior:** Only extract procs with literal names (matching pattern `[a-zA-Z_][a-zA-Z0-9_:]*`).

**Implementation Requirement:**
- Check if proc name contains `$`, `[`, or other substitution markers
- If yes: log WARNING with code "PARSE-DYNA-01"
- Skip proc definition (do not add to index)

**Why It Matters:** Attempting to index dynamic names causes non-deterministic output.

**Test:** Fixture `computed_proc_name_skipped` must produce WARNING diagnostic.

---

### Pitfall P-05: Duplicate Procs in Same File Are Semantic Errors

**THE TRAP:**
```tcl
proc read_data {} { return "v1" }
proc read_data {} { return "v2" }
```

**Correct Behavior:** Both definitions are detected. The LAST definition wins for indexing (matching Tcl runtime). But Chopper emits an ERROR diagnostic. The file is invalid for trim/trace until the duplicate is fixed.

**Implementation Requirement:**
- Detect duplicate `short_name` within the same source file
- Use LAST definition's span for the proc index entry (matches Tcl)
- Emit ERROR diagnostic (not warning) with code "PARSER-DUP-01"
- Mark file as having errors; parser should still complete but report failure

**Why It Matters:** Duplicates indicate authoring mistakes. Silently accepting them hides bugs.

**Test:** Fixture `duplicate_proc_definition_error` must emit ERROR, use last span.

---

### Pitfall P-06: Empty Files and Files with No Procs Are Valid

**THE TRAP:**
```tcl
# This file has no proc definitions
set x 1
```

**Correct Behavior:** Return empty proc index for this file. This is NOT an error.

**Implementation Requirement:**
- Proc index for a file may be empty
- This is valid; do not emit error or warning
- Aggregate proc index across domain treats empty files naturally (they contribute nothing)

**Why It Matters:** Many domains have utility files with only `set` statements, comments, etc.

**Test:** Fixture `empty_file_returns_empty_index` must pass with no errors.

---

### Pitfall P-07: Comment Braces Don't Affect Depth

**THE TRAP:**
```tcl
proc tricky {args} {
    # This line has a { that should be ignored
    set x 1
}
```

**Correct Behavior:** The `{` inside the comment on line 2 does NOT increment brace depth.

**Implementation Requirement:**
- State machine must track `in_comment` separately from `brace_depth`
- When in comment mode: skip all characters until end of line (except `\` continuation)
- Braces inside comments are completely inert

**Why It Matters:** Without this, comments with braces corrupt the proc boundaries.

**Test:** Fixture `comment_with_braces_ignored` must parse correctly.

---

## COMPILER MODULE — Risk: Non-Determinism

### Pitfall P-08: Trace Expansion Must Be Deterministic

**THE TRAP:**
```python
# If proc index lookup returns multiple candidates:
candidates = [proc_a, proc_b]  # Which one do we trace?
# Result: non-deterministic output
```

**Correct Behavior:** Trace expansion resolves a proc call only when the deterministic namespace lookup contract produces exactly one canonical proc in the selected domain.

**Implementation Requirement:**
- Bare token `helper`: try `caller_namespace::helper`, then global `helper`
- Relative qualified token `pkg::helper`: try `caller_namespace::pkg::helper`, then global `pkg::helper`
- Absolute token `::pkg::helper`: try only `pkg::helper`
- If a candidate qualified name maps to multiple canonical procs, log WARNING `TRACE-AMBIG-01`
- If no candidate resolves inside the selected domain, log WARNING `TRACE-CROSS-DOMAIN-01`
- Dynamic or syntactically unresolvable call forms still log WARNING `TRACE-UNRESOLV-01`
- Do NOT auto-resolve ambiguous or cross-domain calls

**Why It Matters:** Non-deterministic trimming breaks reproducibility.

**Test:** Scenario: caller namespace `flow::setup` invokes `helper`; tracer must try `flow::setup::helper` before global `helper`. Scenario: two canonical procs match the same candidate qualified name; log `TRACE-AMBIG-01`.

---

### Pitfall P-09: Include Always Wins Over Exclude

**THE TRAP:**
```json
{
  "base": { "procedures": { "include": [{"file": "utils.tcl", "procs": ["helper"]}] } },
  "feature": { "procedures": { "exclude": [{"file": "utils.tcl", "procs": ["helper"]}] } }
}
```

**Correct Behavior:** `helper` is included because it was explicitly requested. Excludes remain meaningful only for wildcard-expanded file candidates and trace-derived proc candidates.

**Implementation Requirement:**
- Literal file paths in `files.include` are authoritative and always survive
- `files.exclude` applies only to files matched by wildcard `files.include` patterns
- Explicit `procedures.include` entries are authoritative and always survive
- `procedures.exclude` applies only to procs added by trace expansion beyond the explicit seed set

**Why It Matters:** This keeps owner-requested content safe while making exclude fields useful for broad globs and conservative tracing.

**Test:** Scenario: base includes proc X, feature excludes proc X. Final output must contain proc X. Scenario: traced-only proc Y appears via conservative trace and feature excludes Y. Final output omits Y.

---

### Pitfall P-10: Feature Order Is Authoritative for Flow Actions

**THE TRAP:**
```python
features_cli = ["feature_b", "feature_a"]  # User specified
features_base = ["feature_a", "feature_b"]  # Base JSON reference order
# Which order do we apply?
```

**Correct Behavior:** CLI order (or project JSON order if no CLI override) is authoritative. Features are applied left-to-right in the specified order.

**Implementation Requirement:**
- CLI feature order completely replaces project JSON feature list
- Do NOT try to merge or re-sort
- Apply features in order: for each feature in order, apply all rules from that feature

**Why It Matters:** Determinism + reproducibility. Flow actions can be order-dependent.

**Test:** Scenario: Feature A creates stage X, Feature B modifies stage X with order ["A", "B"]. Reverse order to ["B", "A"] and verify different output (if flow actions can be order-dependent).

---

### Pitfall P-11: Glob Expansion Must Normalize Paths

**THE TRAP:**
```python
patterns = ["**/*.tcl", "sub/../file.tcl"]  # Unnormalized
# Result: file listed twice with different paths
```

**Correct Behavior:** Glob expansion results are normalized to a canonical form, deduplicated, and sorted.

**Implementation Requirement:**
- Use `pathlib.Path.glob()` for pattern expansion
- Normalize all results with `Path.resolve()` or similar
- Deduplicate results (set conversion)
- Sort results lexicographically before outputting

**Why It Matters:** Manifest must have canonical file lists for reproducibility.

**Test:** Fixture: `glob_normalizes_and_deduplicates` must produce sorted unique list.

---

### Pitfall P-12: Reject Absolute Paths and `..` Traversal

**THE TRAP:**
```json
{ "files": { "include": ["/absolute/path", "sub/../../../outside"] } }
```

**Correct Behavior:** Validation error. Paths must be relative, within domain, no `..` traversal.

**Implementation Requirement:**
- Check each path in JSON:
  - No leading `/`
  - No `..` segments (or reject if `..` would escape domain root)
  - Validate by resolving path and checking it stays within domain root

**Why It Matters:** Prevents accidental (or malicious) inclusion of files outside the domain.

**Test:** Schema validation must reject these patterns.

---

## TRIMMER MODULE — Risk: Incomplete Writes

### Pitfall P-13: State Machine Transitions Must Be Atomic or Fail Cleanly

**THE TRAP:**
```python
# WRONG: If crash between steps 1 and 2, domain is corrupted
os.rename(domain, domain_backup)  # Step 1
write_trimmed_output(domain)      # Step 2: CRASH here
# Result: domain/ doesn't exist, domain_backup/ exists, but trim is incomplete
```

**Correct Behavior:** All state transitions happen in atomic operation or re-run is safe.

**Implementation Requirement:**
- VIRGIN → BACKUP_CREATED: Atomic rename or use tempfile + atomic move
- BACKUP_CREATED → STAGING: Write to temp directory, not final location
- STAGING → TRIMMED: Atomic move/rename from staging to domain/
- If crash: domain/ and domain_backup/ must always be recoverable to a consistent state

**Why It Matters:** Trim must be re-runnable without manual intervention.

**Test:** Scenario: Simulate crash at each transition; verify re-run recovers cleanly.

---

### Pitfall P-14: Advisory Lock Must Not Block on Stale Locks

**THE TRAP:**
```python
lock_path = "domain.chopper.lock"
# If lock file exists from crashed process 1 hour ago:
# WRONG: wait indefinitely
with open(lock_path, 'r+') as lock_file:
    fcntl.flock(lock_file, fcntl.LOCK_EX)  # Waits forever if stale
```

**Correct Behavior:** Acquire `flock()` in non-blocking mode. If acquisition fails, treat the lock as active and fail fast. Stale-age handling applies only to recovered abandoned metadata after Chopper has already proven no active advisory lock is held.

**Implementation Requirement:**
- Open lock file with `O_CREAT` (create if doesn't exist)
- Try to acquire `flock(..., fcntl.LOCK_EX | fcntl.LOCK_NB)` (non-blocking)
- *Mitigation Note (Stale Locks):* The developer does *not* need to check the lock file's modification timestamp to see if it is "stale." Because `fcntl.flock` is released directly by the OS on process death (even `SIGKILL`), just attempt the `flock` call. If it succeeds, the previous owner is gone; rewrite over the abandoned metadata and proceed. 
- If lock acquisition fails with `EACCES` or `EAGAIN`: another process holds the advisory lock; fail fast with a diagnostic
- Never bypass a live advisory lock, including with `--force`
- If lock acquisition succeeds on a pre-existing lock path: treat it as abandoned metadata/orphaned file, rewrite metadata, and continue
- Apply `stale_timeout_seconds` only to recovered abandoned metadata after successful lock acquisition
- Keep the file descriptor open for the command lifetime; release lock and remove lock file in `finally`

**Why It Matters:** Crashes leave stale lock files; tool must recover without manual cleanup.

**Test:**
- Active lock held by another process: command fails fast and does not wait indefinitely
- Abandoned/orphaned lock path with no active lock: command acquires lock, rewrites metadata, and proceeds

---

### Pitfall P-15: Proc Trimming Must Preserve Surrounding Context

**THE TRAP:**
```tcl
# Original file:
set x 1
proc remove_me {args} { return 42 }
set y 2

# WRONG trimmed output:
set x 1
set y 2
# (removes entire proc but leaves surrounding code)
```

**Correct Behavior:** Extract just the proc definition, preserve surrounding lines as-is.

**Implementation Requirement:**
- Source file is a list of lines
- For each proc to keep: extract lines `[start_line, end_line]` from source
- For each proc to remove: skip those lines
- Reassemble: lines not part of any proc + lines from kept procs (in source order)

**Why It Matters:** Top-level code, variable assignments, and comments outside procs must remain untouched.

**Test:** Fixture: `trim_procs_preserves_context` must produce valid output with surrounding code intact.

---

## VALIDATOR MODULE — Risk: Silent Failures

### Pitfall P-16: Cross-Validation of Proc References

**THE TRAP:**
```python
# Proc included in JSON but file doesn't exist:
{"file": "nonexistent.tcl", "procs": ["my_proc"]}
# WRONG: silently ignore
# CORRECT: emit ERROR diagnostic
```

**Correct Behavior:** Validate that every proc entry in JSON actually exists in the domain.

**Implementation Requirement:**
- For each proc in procedures.include:
  - Verify the source file exists in domain
  - Verify the proc is defined in that file
  - If not: emit ERROR with code "VAL-PROC-01"
- For procedures.exclude: same validation

**Why It Matters:** Typos in JSON go unnoticed otherwise; leads to silent logic errors.

**Test:** Scenario: JSON references `nonexistent.tcl::helper`. Validator must emit ERROR.

---

### Pitfall P-17: Trace Expansion Must Validate Proc Existence

**THE TRAP:**
```python
# Proc A calls Proc B, but Proc B doesn't exist:
# Tracer should emit WARNING, not crash
```

**Correct Behavior:** When tracing discovers a proc call that doesn't resolve:
- Log literal unresolved calls as WARNING `TRACE-CROSS-DOMAIN-01`
- Log dynamic or otherwise unmodelable call forms as WARNING `TRACE-UNRESOLV-01`
- Include location (file + line) in diagnostic
- Suggest owner review

**Implementation Requirement:**
- Trace expansion must surviv unresolved references gracefully
- Emit diagnostics, not exceptions
- Continue tracing other procs

**Why It Matters:** Dynamic code or external-domain references are expected; must not crash.

**Test:** Scenario: Proc calls external proc. Tracer logs WARNING, continues.

---

## AUDIT & DIAGNOSTICS — Risk: Incomplete Context

### Pitfall P-18: All Diagnostics Must Include Location

**THE TRAP:**
```python
# WRONG:
diagnostic = Diagnostic(message="File not found")
# CORRECT:
diagnostic = Diagnostic(
    message="File not found",
    location="jsons/base.json:files.include[2]",  # or "fev_formality/utils.tcl:42"
    code="CONFIG-FILE-01"
)
```

**Implementation Requirement:**
- Every diagnostic must have a `location` field
- For JSON errors: `filename:path.to.field[index]`
- For parser errors: `filename:line_number:column` (1-indexed)
- For compiler errors: `canonical_name` + context

**Why It Matters:** Owner must be able to find and fix each error in source.

**Test:** All diagnostic types must carry location context.

---

### Pitfall P-19: Audit Artifacts Must Be Deterministic

**THE TRAP:**
```python
# WRONG: iterate over dict/set (order undefined in Python <3.7)
for key in diagnostics_dict.keys():  # Non-deterministic order
    output.write(json.dumps(key))
# Result: same input produces different output

# CORRECT: deterministic ordering
sorted_keys = sorted(diagnostics_dict.keys())
for key in sorted_keys:
    output.write(json.dumps(key))
```

**Implementation Requirement:**
- All serialized output (manifest.json, trace_report.json, etc.) must use sorted keys
- Use `json.dumps(..., sort_keys=True)`
- Preserve user-authored ordered collections in authored order (selected features, stages, stage steps, flow actions)
- Sort only inherently unordered or discovery-derived collections (inventories, normalized sets, diagnostics when no authored order exists)
- Same input always produces byte-for-byte identical output

**Why It Matters:** Reproducibility; allows comparison of two trim runs via checksums.

**Test:** Run trim twice with identical inputs; verify bit-identical audit artifacts.

---

## STATE MACHINE — Risk: Illegal Transitions

### Pitfall P-20: State Validation on Entry

**THE TRAP:**
```python
# Use case: `chopper cleanup` on a domain that's already CLEANED
# WRONG: silently do nothing
# CORRECT: emit error or warning

if domain_state == DomainState.CLEANED:
        # Already cleaned; emit an informational diagnostic and leave files untouched
        log.info("Domain already cleaned, nothing to do")
    return ExitCode.SUCCESS
```

**Implementation Requirement:**
- Each command validates domain state before proceeding:
  - `trim`: expects VIRGIN or TRIMMED; rejects CLEANED
  - `validate`: read-only, any state OK
    - `cleanup`: succeeds for TRIMMED, no-ops with INFO for CLEANED, rejects VIRGIN / BACKUP_CREATED / STAGING
- Emit appropriate diagnostic (INFO or ERROR) based on expected state

**Why It Matters:** Prevents user error (trimming an already-cleaned domain).

**Test:** Scenario: Try `cleanup` on already-CLEANED domain. Should emit diagnostic + skip.

---

## CONFIGURATION & PATHS — Risk: Platform-Specific Bugs

### Pitfall P-21: Always Normalize Paths to POSIX Forward Slashes

**THE TRAP:**
```python
# Windows:
path = "sub\\file.tcl"  # Backslashes
manifest = {"file": "sub\\file.tcl"}  # Manifest has backslashes
# When comparing later on Windows: OK
# When checking out on Linux: manifest won't match; broken

# CORRECT:
path = PurePosixPath(path).as_posix()  # Always "sub/file.tcl"
manifest = {"file": "sub/file.tcl"}  # Portable
```

**Implementation Requirement:**
- All paths stored in JSON use forward slashes
- Internally use `pathlib.PurePosixPath` for domain-relative paths
- Use `pathlib.Path` for filesystem operations (OS-native)
- Convert between them explicitly at boundaries

**Why It Matters:** Artifacts must be portable across Windows/Linux/macOS.

**Test:** Cross-platform test: trim on Windows, verify JSON on Linux.

---

### Pitfall P-22: Config File Path Resolution

**THE TRAP:**
```python
# User supplies relative path in .chopper.config:
common_path = "global/snps/common"
# WRONG: resolve relative to current working directory (unstable)
# CORRECT: resolve relative to config file location
config_dir = Path(".chopper.config").parent
common_path = (config_dir / common_path).resolve()
```

**Implementation Requirement:**
- Relative paths in `.chopper.config` are resolved relative to the config file location
- Absolute paths are used as-is
- After resolution, path must exist or emit error

**Why It Matters:** Config file is more portable if paths are relative to config location.

**Test:** Config file in subdirectory; verify path resolution is correct.

---

## CLI & PRESENTATION — Risk: User Confusion

### Pitfall P-23: Dry-Run Must Not Modify Filesystem

**THE TRAP:**
```python
if args.dry_run:
    # WRONG: still create domain_backup
    os.rename(domain, domain_backup)
    # Then fail partway through
    # Result: domain is corrupt

# CORRECT: skip all filesystem writes
if args.dry_run:
    return compiled_manifest  # Return results without writing
```

**Implementation Requirement:**
- `--dry-run` must produce full compilation + manifest + diagnostics
- Must NOT create domain_backup or write any files to domain/
- Must output manifest.json to stdout or `--output` file instead

**Why It Matters:** Dry-run allows domain owners to preview trim without risk.

**Test:** Scenario: `trim --dry-run` on live domain. Verify no filesystem changes.

---

### Pitfall P-25: Project JSON Paths Resolve Relative to the Current Working Directory

**THE TRAP:**
```python
# User runs Chopper from the domain root fev_formality/
# project.json lives at ../configs/project_abc.json
# contains: "base": "jsons/base.json"
#
# WRONG: resolve relative to project JSON file location
base_path = Path("../configs/") / "jsons/base.json"
# Result: ../configs/jsons/base.json (doesn't exist there)
#
# CORRECT: resolve relative to the current working directory / domain root
base_path = Path.cwd() / "jsons/base.json"
# Result: fev_formality/jsons/base.json (correct)
```

**Correct Behavior:** `base` and `features` paths inside a project JSON are resolved relative to the current working directory, which is the operational domain root in v1, NOT relative to the project JSON file location.

**Implementation Requirement:**
- CLI layer assumes the current working directory is the domain root
- CLI layer loads project JSON, extracts `base` and `features` fields
- Resolves all paths relative to `Path.cwd()`
- Default expected curated JSON locations under the domain are `jsons/base.json` and `jsons/features/*.json`
- The project JSON file itself can live anywhere (e.g., `configs/`, `projects/`, outside the repo)
- The project JSON `domain` field must match `Path.cwd().name`
- If `--domain` is accepted, verify that it resolves to the same path as `Path.cwd()`
- After resolution, passes fully resolved `Path` objects into the service layer `TrimRequest`
- Phase 1 validation (V-15) catches unresolvable paths

**Why It Matters:** This is the #1 probable mistake for project JSON implementers. The path resolution convention is intentional — it keeps project JSONs portable.

**Test:** Run from `fev_formality/` with a project JSON in `../configs/` referencing `jsons/base.json`. Verify the path resolves to `fev_formality/jsons/base.json`.

---

### Pitfall P-26: `--project` Is Mutually Exclusive with `--base`/`--features`

**THE TRAP:**
```bash
# WRONG: user provides both
chopper trim --project p.json --base jsons/base.json
# What happens? Which base wins?
```

**Correct Behavior:** Reject immediately with exit code 2 and an actionable error message. Do not attempt to merge or guess.

**Implementation Requirement:**
- In argparse setup, create a mutually exclusive group for `--project` vs `--base`/`--features`
- If both are provided: fail with exit code 2 and a clear message like: `"--project is mutually exclusive with --base and --features. Use one mode or the other."`
- Validation check V-13 covers this case

**Why It Matters:** Ambiguous input modes produce unpredictable behavior and break reproducibility.

**Test:** Scenario: `chopper trim --project p.json --base b.json` → exit code 2.

---

### Pitfall P-27: `--strict` Changes Exit Behavior

**THE TRAP:**
```python
# Without --strict: warnings are exit 0
# With --strict: warnings become errors → exit 1
# If implementer doesn't check strict flag: warnings silently pass in CI
```

**Correct Behavior:** When `--strict` is enabled (via CLI flag or `validation.strict = true` in `.chopper.config`), all WARNING-severity diagnostics are escalated to ERROR. This changes the final exit code from 0 to 1 if any warnings were emitted.

**Implementation Requirement:**
- After collecting all diagnostics, if `--strict` is active, re-classify any WARNING as ERROR
- Recalculate the exit code based on the escalated diagnostics
- V-04 (duplicate file entries) is the primary case: normally WARNING, escalated to ERROR under `--strict`

**Why It Matters:** CI pipelines rely on exit codes to gate merges. `--strict` ensures warnings do not silently pass.

**Test:** Scenario: trim with a V-04 duplicate entry. Without `--strict`: exit 0. With `--strict`: exit 1.

---

### Pitfall P-28: `chopper cleanup` Requires `--confirm`

**THE TRAP:**
```bash
# WRONG: user forgets --confirm
chopper cleanup
# What happens? Silently deletes backup?
```

**Correct Behavior:** Refuse to run. Emit exit code 2 with message: `"cleanup requires --confirm to proceed. This action is irreversible."`

**Implementation Requirement:**
- `--confirm` is a required flag for cleanup (not optional with a default)
- Without `--confirm`: exit code 2, no filesystem changes
- With `--confirm`: proceed with backup removal
- The CLEANED state is terminal and irreversible

**Why It Matters:** Cleanup permanently deletes `domain_backup/`. There is no undo. The `--confirm` flag forces conscious intent.

**Test:** Scenario: `chopper cleanup` without `--confirm` → exit code 2, backup untouched.

---

## HOOK FILES — Risk: Silent Bloat or Missing Files

### Pitfall P-29: Hook Files from `-use_hooks` Are Discovery-Only

**THE TRAP:**
```tcl
# In main.tcl:
iproc_source -file setup.tcl -use_hooks
# Domain has pre_setup.tcl and post_setup.tcl

# WRONG assumption: Chopper will automatically include pre_setup.tcl and post_setup.tcl
# CORRECT: Chopper discovers them (reported in scan artifacts) but does NOT copy them
```

**Correct Behavior:** When Chopper encounters `iproc_source -file X -use_hooks`, it detects the corresponding `pre_X` and `post_X` hook files as candidates. These appear in `scan_report.json`, `file_inventory.json`, and `dependency_graph.json`. But they are **NOT** copied during trim unless the domain owner explicitly adds them to `files.include` in the selected JSON.

**Implementation Requirement:**
- During scan/analysis: record hook file candidates in the file dependency graph
- During trim compilation: hook files are treated like any other file — they survive only if they appear in `files.include`
- There is no `HOOK_AUTO` keep reason. Hook files use the normal `explicit-file` reason if included.
- Warn in scan output that discovered hook files require explicit inclusion

**Why It Matters:** The old hook-auto behavior was removed by design (ARCHITECTURE.md Rev 18, Decision 1). Restoring it silently would re-bloat trimmed domains.

**Test:**
- Scenario: Domain has `setup.tcl` + `pre_setup.tcl` + `post_setup.tcl`. Base JSON includes only `setup.tcl` in `files.include`. After trim: `pre_setup.tcl` and `post_setup.tcl` must NOT appear in the trimmed domain.
- Scenario: Same domain, but base JSON adds `pre_setup.tcl` to `files.include`. After trim: `pre_setup.tcl` survives, `post_setup.tcl` does not.

---

## PROJECT JSON — Risk: Metadata Loss in Audit Trail

### Pitfall P-30: Project Metadata Must Flow Through to Audit Artifacts

**THE TRAP:**
```python
# CLI loads project JSON, extracts base + features
# WRONG: discards project name, owner, notes before creating TrimRequest
request = TrimRequest(
    domain_path=domain,
    base_json=resolved_base,
    feature_jsons=resolved_features,
    # project_json, project_name, project_owner, project_notes all missing!
)
# Result: audit artifacts have no record that --project was used
```

**Correct Behavior:** When `--project` is used, the CLI layer must populate ALL project-related fields in `TrimRequest`:
- `project_json` — path to the project JSON file
- `project_name` — from `project` field
- `project_owner` — from `owner` field
- `release_branch` — from `release_branch` field
- `project_notes` — from `notes` array

These fields flow through to `chopper_run.json` and `compiled_manifest.json`.

**Implementation Requirement:**
- CLI layer: parse project JSON, populate all `TrimRequest` project fields
- Service layer: pass project fields through to `RunSelection` and `CompiledManifest`
- Audit writer: serialize project fields into `chopper_run.json` and `compiled_manifest.json`
- When `--project` is NOT used: these fields are empty strings / None / empty tuples

**Why It Matters:** The audit trail must capture WHY a particular selection was made. Without project metadata, the audit trail shows WHAT was selected but not the project-level context.

**Test:** Trim with `--project`. Verify `chopper_run.json` contains `project_json_path`, `project_name`, `project_owner`, `release_branch`. Trim with `--base`/`--features`. Verify those fields are absent or null.

---

### Pitfall P-31: Project JSON Domain Must Match the Current Working Directory

**THE TRAP:**
```bash
# User runs from sta_pt/
# Project JSON says: "domain": "fev_formality"
# CLI also passes --domain ./
# Which root wins?
```

**Correct Behavior:** The current working directory is the domain root in v1. The project JSON `domain` field is a consistency identifier and must match `Path.cwd().name`. If `--domain` is provided alongside `--project`, it must resolve to the same directory as `Path.cwd()`; otherwise Chopper exits with code 2.

**Implementation Requirement:**
- Use `Path.cwd()` as the verified domain root for project path resolution
- Require `project_json["domain"] == Path.cwd().name`
- If `--domain` is provided, resolve it and require it to equal `Path.cwd()`
- If any of those checks fail: exit code 2 with actionable message

**Why It Matters:** This freezes one path root for the whole run and avoids hidden path-resolution branches.

**Test:** 
- `cd fev_formality && chopper trim --project ../configs/p.json`: succeeds only if the project JSON says `"domain": "fev_formality"`
- `cd sta_pt && chopper trim --project ../configs/p.json`: exit code 2 if the project JSON says `"domain": "fev_formality"`
- `cd fev_formality && chopper trim --project ../configs/p.json --domain $(pwd)`: succeeds
- `cd fev_formality && chopper trim --project ../configs/p.json --domain ../sta_pt`: exit code 2 with a mismatch diagnostic

---

## TESTING STRATEGY — Risk: Late Discovery of Bugs

### Pitfall P-24: Edge Case Fixtures Must Be Tested Early

**THE TRAP:**
```
Week 1, 2, 3: Implement parser without testing edge cases
Week 4: Add edge case tests
Result: Major bugs discovered late in implementation
```

**Implementation Requirement:**
- Implement parser + fixtures in WEEK 1 (parallel or sequential)
- Test all 15 fixture categories before moving to compiler
- Property-based tests for invariants (span consistency, no overlaps, etc.)

**Why It Matters:** Parser is the critical path; failures here cascade.

**Test:** All fixtures from TCL_PARSER_SPEC.md §9 must pass by end of Week 1.

---

## Quick Reference: Common Mistakes by Module

| Module | Mistake | Prevention |
|--------|---------|-----------|
| **Parser** | Quotes inside braced bodies treated as structural shields | Follow Tcl Rule 6: quotes are literal inside braced words (P-01) |
| **Parser** | Line continuation corrupts line numbers | Don't physically join lines (P-02) |
| **Parser** | Namespace context resets incorrectly | LIFO stack management (P-03) |
| **Compiler** | Trace expansion is non-deterministic | Require exact match, not ambiguous (P-08) |
| **Compiler** | Excludes override includes | Remember: include wins (P-09) |
| **Compiler** | Glob results include duplicates | Normalize + deduplicate (P-11) |
| **Trimmer** | Crash leaves domain corrupted | Atomic transitions or safe re-run (P-13) |
| **Trimmer** | Stale locks block forever | Non-blocking advisory lock + abandoned-metadata recovery (P-14) |
| **Validator** | Typos in JSON go unnoticed | Validate JSON references exist (P-16) |
| **Audit** | Diagnostics lack context | Include location in every diagnostic (P-18) |
| **Config** | Paths break on different OS | Always use forward slashes (P-21) |
| **CLI** | Dry-run modifies filesystem | Skip all writes when `--dry-run` (P-23) |
| **CLI** | Project JSON paths resolve wrong | Resolve relative to the current working directory / domain root, not the project file (P-25) |
| **CLI** | `--project` + `--base` both provided | Mutually exclusive — exit code 2 (P-26) |
| **CLI** | `--strict` not checked | Escalate warnings to errors, change exit code (P-27) |
| **CLI** | Cleanup runs without `--confirm` | Require `--confirm` — exit code 2 without it (P-28) |
| **Hooks** | Hook files auto-copied from `-use_hooks` | Discovery-only; must be in `files.include` (P-29) |
| **Project** | Project metadata lost in audit | Populate all `TrimRequest` project fields (P-30) |
| **Project** | Domain mismatch with project JSON | Require current working directory consistency and reject mismatches (P-31) |

---

**End of Pitfalls Guide**

This guide should be referenced during code review. Each pitfall has a corresponding test case or scenario that should be validated.
