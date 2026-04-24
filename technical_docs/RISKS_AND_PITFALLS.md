# Chopper — Technical Risks and Implementation Pitfalls

**Purpose:** Document the known technical risks (TC-01 through TC-10) and the concrete implementation pitfalls (P-01 through P-37) that prevent those risks from being realized.
**Audience:** Engineering team
**Replaces:** prior `TECHNICAL_CHALLENGES.md` and the former `technical_docs/IMPLEMENTATION_PITFALLS_GUIDE.md`.

---

## Overview

This guide merges two previously separate documents:

- **Technical Challenges (TC-01 – TC-10)** — High-level risk areas identified during architecture. Each TC names a category of failure that would compromise trim correctness, reproducibility, or safety.
- **Implementation Pitfalls (P-01 – P-37)** — Concrete coding traps, each with a "naïve vs correct" example, implementation requirements, and a mandatory test fixture.

The document is organized by module. Each module section opens with the relevant TC risk statements, followed by the detailed pitfalls that guard against them.

---

## PARSER MODULE — Highest Risk Area

**TC-01 — Tcl Proc Boundary Detection:** Chopper must correctly find proc boundaries even with nested braces and namespace constructs. Without a reliable parser, F2 (proc-level trimming) is not viable.

**TC-02 — Canonical Proc Naming:** Resolved to **file + proc name** with namespace-qualified synthesis. Canonical form: `file.tcl::proc_name`. Incorrect canonicalization breaks JSON stability and traceability. JSON authoring uses the short proc name; Chopper resolves the canonical form internally.

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
- If yes: log WARNING with code `PW-01` (see `technical_docs/DIAGNOSTIC_CODES.md`)
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
- Emit ERROR diagnostic (not warning) with code `PE-01` (see `technical_docs/DIAGNOSTIC_CODES.md`)
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

### Pitfall P-32: Proc Args with Nested Brace Defaults Trigger Premature Body Detection

**THE TRAP:**
```tcl
proc read_rtl_2stage { rtlfile root_module { container "r" } { ctech_type "ADD" } } {
    iproc_source -file rtl_setup.tcl
    ...
}
```

A parser that scans for the first `}` after the opening `{` of the args word will see `}` from `{ container "r" }` and conclude the args word is closed. The next `{` appears to open the proc body — but it is actually the start of `{ ctech_type "ADD" }`, the next default-value arg descriptor. The parser opens the proc body at the wrong `{` and corrupts all subsequent proc boundary detection in the file.

**Correct Behavior:** The args specification is a **single brace-balanced word**. The parser must track brace depth through the entire args word. The body `{` is only the `{` that arrives after all nested default-value braces have balanced back to the depth present before the args word opened.

**Implementation Requirement:**
- Implement Step b of the §4.2 detection algorithm in TCL_PARSER_SPEC.md: "scan forward to next unescaped `{` at the original depth (before args word opened)"
- Do NOT exit the args scan on the first `}` — track depth and continue until the args word closes completely
- Body `{` = first `{` encountered at the same brace depth as before the args word started

**Why It Matters:** This is the most common EDA proc signature. `default_fm_procs.tcl` uses nested default values throughout (`read_rtl_2stage`, `report_verify_results`). Every such proc will have a corrupted `body_start_line` if this is not handled correctly, breaking all subsequent proc boundaries in the file.

**Test:** Fixture `proc_args_nested_defaults` — proc with multiple default-value arg descriptors; assert `body_start_line` is on the correct line immediately after the `{` that follows the fully closed args specification.

---

### Pitfall P-33: DPA Block Not Dropped Atomically With Its Proc

**THE TRAP:**
```tcl
proc read_libs {} {
    read_db_files
}
define_proc_attributes read_libs \
   -info "Reads Synopsys .db technology libraries"
```

Parser records `ProcEntry(start_line=1, end_line=3, dpa_start_line=None, dpa_end_line=None)`. Trimmer drops lines 1–3 when `read_libs` is excluded but leaves lines 4–5 in the output. Downstream Synopsys tools encounter `define_proc_attributes read_libs` for a proc that does not exist and abort.

**Correct Behavior:** The DPA lookahead (§4.6 of TCL_PARSER_SPEC.md) must execute after every proc body closes. `dpa_start_line`/`dpa_end_line` must be set on the `ProcEntry`. The trimmer must treat these lines as part of the proc's atomic keep/drop unit.

**Implementation Requirement:**
- After recording `end_line` for a proc, peek forward through up to 3 blank lines (skip blank lines only — a comment line between `}` and the DPA line breaks the association)
- If the peeked line matches `^\s*define_proc_(attributes|arguments)\s+`, associate it and follow `\` continuation lines to find `dpa_end_line`
- In the trimmer: `drop_range = range(start_line, end_line + 1) ∪ range(dpa_start_line, dpa_end_line + 1)` when the proc is excluded; keep both ranges together when included
- Emit `PW-11` when DPA proc name does not match `qualified_name` and skip the association

**Why It Matters:** In `default_fm_procs.tcl` and every real-world Intel/Synopsys EDA file, 100% of procs have a DPA block. Dropping the proc without its DPA block leaves orphaned metadata in every trimmed file, causing Synopsys tool errors.

**Test:** Fixture `proc_with_dpa_dropped_atomically` — verify trimmed output contains neither `proc read_libs` lines nor `define_proc_attributes read_libs` lines when `read_libs` is excluded.

---

### Pitfall P-34: Structured Comment Banner Left as Orphan After Proc Drop

**THE TRAP:**
```tcl
########################################################################
#proc       : read_libs
#purpose    : Reads technology libraries for LP and Non-LP runs
#usage      : read_libs
########################################################################
proc read_libs {} {
    ...
}
define_proc_attributes read_libs \
   -info "..."
```

Parser records `ProcEntry(start_line=6, comment_start_line=None)`. Trimmer drops the proc (lines 6–8) and DPA block (lines 9–10) but leaves lines 1–5 (the `########` banner) in the output. The trimmed file now has floating banner blocks between kept procs, degrading readability and confusing documentation tools.

**Correct Behavior:** The backward comment scan (§4.7 of TCL_PARSER_SPEC.md) must execute when each `proc` keyword is detected. Scan backward through already-parsed lines, counting contiguous `^\s*#` lines (any comment content). Stop at the first blank line or non-comment line. Assign `comment_start_line`–`comment_end_line = start_line - 1` to the `ProcEntry`.

**Implementation Requirement:**
- On detecting `proc` at `start_line`, scan backward through the accumulated line buffer
- Count contiguous `^\s*#` lines regardless of comment content (`########`, `#field: value`, etc.)
- Stop at first blank line or non-comment line; set `comment_start_line` = earliest qualifying line
- In the trimmer: `drop_range = range(comment_start_line, dpa_end_line + 1)` covers the full unit: banner + proc + DPA
- The backward scan is purely textual — it must **not** alter the forward brace-tracking state machine; braces in comments are always inert (see P-07)

**Why It Matters:** In `default_fm_procs.tcl`, 100% of procs have a `########...########` banner. Leaving orphaned banners is the most visible cosmetic failure in trimmed output and degrades trustworthiness of the tool.

**Test:** Fixture `proc_with_comment_banner_dropped_atomically` — verify trimmed output contains none of the `####` lines, proc lines, or DPA lines when the proc is excluded. Verify all three components survive together when the proc is included.

---

### Pitfall P-35: DPA Proc Name Argument Extracted as False Call Dependency

**THE TRAP:**
```tcl
proc register_all_attrs {} {
    define_proc_attributes read_libs \
       -info "Reads technology libraries"
    define_proc_attributes read_rtl_2stage \
       -info "Reads RTL files in two stages"
}
```

During call extraction for `register_all_attrs`, the call extractor applies "first word of command = candidate call". It correctly extracts `define_proc_attributes` as the command (which produces `TW-02` at trace time — expected). A naïve extractor then also inspects `read_libs` and `read_rtl_2stage` as apparent "tokens on the same line" and traces them as proc dependencies of `register_all_attrs`. This injects false dependency edges that cause `read_libs` and `read_rtl_2stage` to be kept whenever `register_all_attrs` is kept, even if they were explicitly excluded.

**Correct Behavior:** Call extraction extracts **only the first word** of a command as the candidate call. Subsequent tokens are arguments — never extracted as call candidates. The Level 2c suppression rule in §5.5 of TCL_PARSER_SPEC.md provides a belt-and-suspenders guard: any token in the `define_proc_attributes <token>` second-argument position is explicitly suppressed even if a future code path scans later tokens.

**Implementation Requirement:**
- Call extractor emits exactly one candidate per command: the first word after command-position whitespace or semicolon
- Do NOT scan second or later tokens for call candidates under any condition
- Level 2c guard: suppress tokens matched by `define_proc_(attributes|arguments)\s+<token>` pattern

**Why It Matters:** Every proc in `default_fm_procs.tcl` has a DPA block. If DPA proc-name tokens are traced as dependencies, the entire call graph is falsely interconnected and surgical trimming becomes impossible.

**Test:** Fixture `call_extraction_dpa_no_false_dependency` — proc body containing two `define_proc_attributes` lines; assert neither `read_libs` nor `read_rtl_2stage` appear in the extracted call list for the outer proc.

---

### Pitfall P-36: `foreach_in_collection` Must Push CONTROL_FLOW Context

**THE TRAP:**
```tcl
proc get_hier_summary { design } {
    foreach_in_collection cell [get_cells *] {
        set name [get_attribute $cell full_name]
        puts $name
    }
}
```

If `foreach_in_collection` is not in the recognized control-flow keyword set, the parser does not push `CONTROL_FLOW` context when the iterator body `{` is entered. Depending on the current stack state:

- A `proc` keyword inside the body is incorrectly indexed as a top-level or namespace-level definition, or
- The brace tracking for the containing proc body is corrupted when the iterator's closing `}` is encountered.

**Correct Behavior:** `foreach_in_collection` is a Synopsys Formality/DC EDA iterator command. Handle it identically to `foreach`: push `CONTROL_FLOW` when its body `{` opens, pop when the matching `}` closes. Extract calls from its body normally. Do NOT index any `proc` definitions found inside the body (§5.5, §7.14 of TCL_PARSER_SPEC.md).

**Implementation Requirement:**
- Include `foreach_in_collection` in the control-flow keyword set:
  ```python
  CONTROL_FLOW_KEYWORDS: frozenset[str] = frozenset({
      'if', 'else', 'elseif', 'for', 'foreach', 'foreach_in_collection',
      'while', 'switch', 'catch', 'try',
  })
  ```
- The parser looks for the body `{` after `foreach_in_collection <varname> <collection-expr>`; the `[get_cells *]` bracketed expression before `{` is parsed transparently (brackets are irrelevant to brace depth tracking)
- Push `CONTROL_FLOW` on that `{`; pop on the matching `}`
- Any `proc` keyword encountered inside this context is skipped (debug-level log)

**Why It Matters:** `foreach_in_collection` appears throughout Synopsys DC and Formality flows (`get_hier_summary` in `default_fm_procs.tcl` is a concrete example). Missing this keyword causes context stack corruption or false proc indexing in every file that uses it.

**Test:** Fixture `foreach_in_collection_not_proc_context` — proc body containing `foreach_in_collection` with a `proc` keyword inside the iterator body; assert the inner `proc` is NOT indexed.

---

### Pitfall P-37: Adjacent Drop-Ranges Produce Blank-Line Artifacts When Not Coalesced

**THE TRAP:**

```python
# Two adjacent procs are both marked for drop.
# Naïve deletion applies each range independently (bottom-up):
# range A: lines 40–55  (proc + DPA)
# range B: lines 15–38  (proc + banner + DPA, ends at line 38; line 39 is blank)
# After dropping range A then range B, line 39 (the blank separator) survives
# because it was outside both ranges. Output file has an orphaned blank line
# at the deletion site.
```

This produces cosmetic clutter in the trimmed output file. With many adjacent dropped procs, entire swathes of blank lines accumulate at the deletion site.

**Correct Behavior:** Before writing the rewritten file, **coalesce** all collected drop-ranges:

1. Sort drop-ranges in ascending order by `start_line` (for coalescing; apply in descending order when deleting).
2. Merge adjacent or overlapping ranges: if `range_A.end + 1 >= range_B.start`, merge into a single span `(range_B.start, range_A.end)` — note: after sorting ascending, "range A" precedes "range B", so `range_A.end + 1 >= range_B.start` is the adjacency condition.
3. Apply the coalesced set, sorted descending by start line, as a single deletion pass.

```python
def coalesce_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge adjacent or overlapping (start, end) line ranges."""
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda r: r[0])
    merged = [sorted_ranges[0]]
    for start, end in sorted_ranges[1:]:
        if start <= merged[-1][1] + 1:  # adjacent or overlapping
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged  # return ascending; caller reverses for bottom-up deletion
```

**Implementation Requirement:** `TrimmerService` and `proc_dropper.py` must call a coalesce step before applying any deletions. Blank lines between adjacent dropped-proc regions are included in the coalesced span if they fall within the merged range.

**Test:** Create a two-proc test fixture where both procs are dropped. Assert that the output file contains no consecutive blank lines at the deletion site.

**Why It Matters:** In production EDA domains, feature selection often drops adjacent utility procs (e.g., all EDA-vendor-specific helpers in a file). Without coalescing, the trimmed file visually signals removed sections through blank-line patterns — a minor but reproducible quality defect. More importantly, it is a sign that the deletion loop may be applying overlapping or inconsistently-ordered range logic.

---

## COMPILER MODULE — Risk: Non-Determinism

**TC-03 — Transitive Proc Tracing:** The center of the product. Requires correct static call extraction, conservative behavior for dynamic Tcl, cross-file proc mapping within the domain boundary based on the per-run proc index, and clear warnings when trace cannot prove correctness. The proc index contract is defined in R3 and must exist before F2 trimming or trace expansion runs.

**TC-08 — Override and Ordering Semantics:** Multiple selected features may touch the same proc or stage. Selected input order governs last-wins behavior for explicit `replace_step`/`replace_stage` conflicts; R1 governs include/exclude survival. Within one feature, action order is top-to-bottom and later actions see results of earlier ones.

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
- If a candidate qualified name maps to multiple canonical procs, log WARNING `TW-01`
- If no candidate resolves inside the selected domain, log WARNING `TW-02`
- Dynamic or syntactically unresolvable call forms still log WARNING `TW-03`
- Do NOT auto-resolve ambiguous or cross-domain calls

**Why It Matters:** Non-deterministic trimming breaks reproducibility.

**Test:** Scenario: caller namespace `flow::setup` invokes `helper`; tracer must try `flow::setup::helper` before global `helper`. Scenario: two canonical procs match the same candidate qualified name; log `TW-01`.

---

### Pitfall P-09: Include Always Wins Over Exclude

**THE TRAP:**
```json
{
  "base": { "procedures": { "include": [{"file": "utils.tcl", "procs": ["helper"]}] } },
  "feature": { "procedures": { "exclude": [{"file": "utils.tcl", "procs": ["helper"]}] } }
}
```

**Correct Behavior:** `helper` is included because it was explicitly requested. `files.exclude` remains meaningful only for wildcard-expanded file candidates. `procedures.exclude` is a *same-file* proc-trimming instruction (`PROC_TRIM` keep-set = `all_procs(file) − PE`); it does **not** filter trace-expanded callees, because trace (P4) is reporting-only and never adds procs to the surviving set. Only procs explicitly listed in `procedures.include` survive trimming — traced callees are emitted in `dependency_graph.json` and `trim_report.json` for visibility but are not copied.

**Implementation Requirement:**
- Literal file paths in `files.include` are authoritative and always survive
- `files.exclude` applies only to files matched by wildcard `files.include` patterns
- Explicit `procedures.include` entries are authoritative and always survive
- `procedures.exclude` prunes procs inside `PROC_TRIM` files (same-source authoring rule L2); it cannot remove another source's explicit `procedures.include` (`VW-18`) and cannot remove a whole-file include (`VW-19`)
- PI+ (transitive trace set) is **reporting-only**: see [chopper_description.md](chopper_description.md) §5.4. A traced-only proc is never auto-included; if it is needed it must be named explicitly in `procedures.include`

**Why It Matters:** This keeps owner-requested content safe. Excludes remain useful for broad globs and for authoring conveniences inside a single source, but never for second-guessing another author's explicit include.

**Test:** Scenario: base includes proc X, feature excludes proc X. Final output must contain proc X and emit `VW-18`. Scenario: proc Y is only reachable via trace (called by an explicitly-included proc); feature excludes Y. Final output omits Y from the trimmed domain regardless — Y was never going to be copied — and the PE entry is recorded with no diagnostic suppression.

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

**TC-04 — Copy-and-Delete Correctness:** F2 depends on preserving top-level Tcl while deleting only unwanted proc definitions. Chopper deletes only recorded proc spans; text between surviving spans is preserved byte-for-byte. If a proc-trimmed file has no surviving procs and no non-comment top-level Tcl, it survives as a stub with `VW-08`. Malformed deletion breaks Tcl syntax or leaves dangling structure.

### Pitfall P-13: Backup-and-Rebuild Must Fail Cleanly and Recover Deterministically

**THE TRAP:**
```python
# WRONG: If crash between steps 1 and 2, domain is corrupted
os.rename(domain, domain_backup)  # Step 1
write_trimmed_output(domain)      # Step 2: CRASH here
# Result: domain/ doesn't exist, domain_backup/ exists, but trim is incomplete
```

**Correct Behavior:** Backup creation and direct rebuild transitions are simple, restartable, and deterministic.

**Implementation Requirement:**
- Backup creation: First trim creates sibling `domain_backup/` once and treats it as the recovery source on every later run.
- Rebuild: Write directly into the active `domain/` tree during P5. There is no staging tree and no final promotion step.
- Failure: If a write fails mid-run, leave the half-rebuilt `domain/` in place and keep `domain_backup/` untouched.
- Recovery: On re-run, detect the existing backup and rebuild from it cleanly without re-backing-up.

**Why It Matters:** Trim must be re-runnable without manual intervention.

**Test:** Scenario: Simulate crash during backup creation or mid-rebuild; verify re-run recovers cleanly from `domain_backup/`.

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

**TC-07 — Validation Quality:** Validation must catch broken Tcl syntax, missing files, unjustifiable proc references, and F3 output pointing to trimmed-away content. Diagnostics must use stable IDs, severities, and actionable hints so CI, text reports, and future UIs all consume the same signal.

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
- Log literal unresolved calls as WARNING `TW-02`
- Log dynamic or otherwise unmodelable call forms as WARNING `TW-03`
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

## BACKUP & RECOVERY — Risk: Lost Work or Incomplete Cleanup

### Pitfall P-20: Backup Detection and Manual Recovery

**THE TRAP:**
```python
# WRONG: Always create a backup, even if one already exists
os.rename(domain, domain_backup)  # Overwrites any existing _backup!

# CORRECT: Detect backup, decide action
if domain_backup_exists():
    rebuild_from_backup()  # Re-trim scenario
else:
    os.rename(domain, domain_backup)  # First trim
```

**Implementation Requirement:**
- Before trim, check if `domain_backup/` exists
- If it exists: rebuild the trimmed domain from the backup (re-trim scenario)
- If it doesn't exist: create the backup by renaming `domain/` to `domain_backup/`
- Users can manually restore a domain by renaming `domain_backup/` back to `domain/` if desired
- `cleanup` removes the `domain_backup/` directory when the trim window is complete (requires `--confirm`)

**Why It Matters:** Enables re-trim without loss of work, and supports manual recovery if needed.

**Test:** Scenario 1: First trim creates backup and builds trimmed domain. Scenario 2: Re-run detects backup and rebuilds from it without duplicating. Scenario 3: User can manually rename backup to restore domain.

---

## CONFIGURATION & PATHS — Risk: Platform-Specific Bugs

**TC-10 — Boundary Discipline:** Chopper must never accidentally reach and trim outside the domain trim scope. Path validation is the primary enforcement mechanism.

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

**Correct Behavior:** `base` and `features` paths inside a project JSON are resolved relative to the current working directory, which is the operational domain root, NOT relative to the project JSON file location.

**Implementation Requirement:**
- CLI layer assumes the current working directory is the domain root
- CLI layer loads project JSON, extracts `base` and `features` fields
- Resolves all paths relative to `Path.cwd()`
- Default expected curated JSON locations under the domain are `jsons/base.json` and `jsons/features/*.feature.json`
- The project JSON file itself can live anywhere (e.g., `configs/`, `projects/`, outside the repo)
- The project JSON `domain` field must match `Path.cwd().name`
- If `--domain` is accepted, verify that it resolves to the same path as `Path.cwd()`
- After resolution, passes fully resolved `Path` objects into the `RunConfig` bound by `ChopperContext`
- Phase 1 validation (`VE-13 project-path-unresolvable`) catches unresolvable paths

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
- Validation check `VE-11 conflicting-cli-options` (exit code 2) covers this case

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
- `VW-01 file-in-both-include-lists` (and related soft-mismatch warnings) is the primary case: normally WARNING, escalated to ERROR under `--strict`

**Why It Matters:** CI pipelines rely on exit codes to gate merges. `--strict` ensures warnings do not silently pass.

**Test:** Scenario: trim with a `VW-01` overlap warning. Without `--strict`: exit 0. With `--strict`: exit 1.

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

**TC-05 — File Dependency Detection:** Chopper must correctly capture `source` and `iproc_source` references, including flags and hooks. Required vs optional references and `-use_hooks` behavior must follow R3 exactly and be reflected in diagnostics and manifests.

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

**Why It Matters:** The old hook-auto behavior was removed by design (see [chopper_description.md](chopper_description.md) Q12). Restoring it silently would re-bloat trimmed domains.

**Test:**
- Scenario: Domain has `setup.tcl` + `pre_setup.tcl` + `post_setup.tcl`. Base JSON includes only `setup.tcl` in `files.include`. After trim: `pre_setup.tcl` and `post_setup.tcl` must NOT appear in the trimmed domain.
- Scenario: Same domain, but base JSON adds `pre_setup.tcl` to `files.include`. After trim: `pre_setup.tcl` survives, `post_setup.tcl` does not.

---

## PROJECT JSON — Risk: Metadata Loss in Audit Trail

### Pitfall P-30: Project Metadata Must Flow Through to Audit Artifacts

**THE TRAP:**
```python
# CLI loads project JSON, extracts base + features
# WRONG: discards project name, owner, notes before building RunConfig
config = RunConfig(
    domain_root=domain,
    backup_root=backup,
    audit_root=audit,
    # project_json, project_name, project_owner, release_branch, project_notes all missing!
)
# Result: audit artifacts have no record that --project was used
```

**Correct Behavior:** When `--project` is used, the CLI layer must populate ALL project-related fields on `RunConfig` (the engine-behavior record inside `ChopperContext`, per [`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6.1):
- `project_json` — path to the project JSON file
- `project_name` — from `project` field
- `project_owner` — from `owner` field
- `release_branch` — from `release_branch` field
- `project_notes` — from `notes` array

These fields flow through `ConfigService` → `CompiledManifest` and are written into `chopper_run.json` and `compiled_manifest.json` by `AuditService`.

**Implementation Requirement:**
- CLI layer: parse project JSON, populate all `RunConfig` project fields before constructing `ChopperContext`
- Service layer: pass project fields through to `LoadedConfig` and `CompiledManifest`
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

**Correct Behavior:** The current working directory is the domain root. The project JSON `domain` field is a consistency identifier and must match `Path.cwd().name`. If `--domain` is provided alongside `--project`, it must resolve to the same directory as `Path.cwd()`; otherwise Chopper exits with code 2.

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
Stage 1: Implement parser, defer edge-case fixtures to later stages
Stage 2 or later: Add edge case tests
Result: Major bugs discovered after the compiler is already built on top of an untested parser, forcing cross-stage rework
```

**Implementation Requirement:**
- Implement parser and all fixtures together within Stage 1 — the Parser module is not complete until every fixture passes
- All 15+ fixture categories must pass before Stage 2 (Compiler) begins
- Property-based tests for invariants (span consistency, no overlaps, etc.) are part of Stage 1 acceptance

**Why It Matters:** Parser is the critical path; every later stage consumes its typed output (`list[ProcEntry]`). Failures here cascade into the compiler, trimmer, and validator.

**Test:** All fixtures from [TCL_PARSER_SPEC.md](TCL_PARSER_SPEC.md) §9 must pass before Stage 1 is declared complete.

---

## Quick Reference: Common Mistakes by Module

| Module | Mistake | Prevention |
|--------|---------|-----------|
| **Parser** | Quotes inside braced bodies treated as structural shields | Follow Tcl Rule 6: quotes are literal inside braced words (P-01) |
| **Parser** | Line continuation corrupts line numbers | Don't physically join lines (P-02) |
| **Parser** | Namespace context resets incorrectly | LIFO stack management (P-03) |
| **Parser** | Computed proc names not skipped | Log `PW-01`, skip proc (P-04) |
| **Parser** | Duplicate proc not flagged | Log `PE-01`, use last span (P-05) |
| **Parser** | Args nested defaults cause premature body detection | Track full brace depth through args word; body `{` only at original depth (P-32) |
| **Parser** | DPA block left as orphan after proc drop | Record `dpa_start_line`/`dpa_end_line`; drop atomically with proc (P-33) |
| **Parser** | Comment banner orphaned after proc drop | Record `comment_start_line`/`comment_end_line`; drop atomically with proc (P-34) |
| **Parser** | DPA proc name extracted as false call dependency | Extract first word only; Level 2c suppression filter (P-35) |
| **Parser** | `foreach_in_collection` not in control-flow keywords | Add to `CONTROL_FLOW_KEYWORDS`; push `CONTROL_FLOW` context (P-36) |
| **Trimmer** | Adjacent drop-ranges leave blank-line artifacts | Coalesce adjacent/overlapping ranges before deletion pass (P-37) |
| **Compiler** | Trace expansion is non-deterministic | Require exact match, not ambiguous (P-08) |
| **Compiler** | Excludes override includes | Remember: include wins (P-09) |
| **Compiler** | Glob results include duplicates | Normalize + deduplicate (P-11) |
| **Trimmer** | Crash leaves domain corrupted | Atomic transitions or safe re-run (P-13) |
| **Trimmer** | Lost work on re-trim | Detect existing backup and rebuild from it (P-20) |
| **Validator** | Typos in JSON go unnoticed | Validate JSON references exist (P-16) |
| **Audit** | Diagnostics lack context | Include location in every diagnostic (P-18) |
| **Config** | Paths break on different OS | Always use forward slashes (P-21) |
| **CLI** | Dry-run modifies filesystem | Skip all writes when `--dry-run` (P-23) |
| **CLI** | Project JSON paths resolve wrong | Resolve relative to the current working directory / domain root, not the project file (P-25) |
| **CLI** | `--project` + `--base` both provided | Mutually exclusive — exit code 2 (P-26) |
| **CLI** | `--strict` not checked | Escalate warnings to errors, change exit code (P-27) |
| **CLI** | Cleanup runs without `--confirm` | Require `--confirm` — exit code 2 without it (P-28) |
| **Hooks** | Hook files auto-copied from `-use_hooks` | Discovery-only; must be in `files.include` (P-29) |
| **Project** | Project metadata lost in audit | Populate all `RunConfig` project fields (P-30) |
| **Project** | Domain mismatch with project JSON | Require current working directory consistency and reject mismatches (P-31) |

---

## STANDALONE RISK ITEMS

These technical challenges have no dedicated pitfall entries but remain important architectural constraints.

### TC-06: Non-Tcl Handling

Non-Tcl files are intentionally file-level only. Attempting to over-interpret non-Tcl files adds cost without strong product value.

### TC-09: Template Generation

Template-script generation is **not** a Chopper v1 feature and is not reserved in the schema. Previous drafts kept an `options.template_script` field with diagnostic `VE-18 template-script-path-escapes` as a reserved hook — that field and that diagnostic have been removed in line with the scope-lock policy (no reserved seams). If a future version wants template generation, it will be filed as `FD-12 template-script-generation` and re-introduced through the architecture-doc-first cascade. Domain-specific generation logic stays outside the Chopper core.

---

## PROCESS ANALYSIS AND OPERATIONAL ASSESSMENT

### Current Process Assessment

| Strength | Why It Matters |
|---|---|
| **Clear ownership** | Each domain owner owns one bounded slice of work |
| **Time-boxed trim window** | Creates delivery pressure and prioritization |
| **Per-domain isolation** | Keeps the product scope realistic |
| **Backup strategy** | Makes re-trim operationally safe |

| Risk | Why It Matters |
|---|---|
| **Authoring overhead** | JSON authoring requires domain knowledge; dry-run provides the iteration feedback loop |
| **Tracing correctness** | Incorrect tracing breaks F2 output |
| **Validation late discovery** | Runtime failures are expensive during deployment windows |
| **Branch drift** | Long-lived project branches may miss fixes from mainline |

---

**End of Risks and Pitfalls Guide**

This guide should be referenced during code review. Each pitfall has a corresponding test case or scenario that should be validated.
