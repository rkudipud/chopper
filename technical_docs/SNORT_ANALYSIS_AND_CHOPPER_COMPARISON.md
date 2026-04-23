# SNORT Deep Analysis & Chopper Engine Comparison

**Date:** April 18, 2026
**Scope:** Technical analysis of Intel's SNORT Tcl static analysis tool, comparison with Chopper v2 parser/compiler/trimmer requirements, and strategic recommendations for Chopper's code analysis engine.

> **Status:** Historical comparison and design-analysis reference.
>
> This document is **not** an implementation handoff spec. If anything here conflicts with [`technical_docs/chopper_description.md`](chopper_description.md), [`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md), or [`technical_docs/IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md), the live handoff docs win.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [SNORT Architecture & Capabilities](#2-snort-architecture--capabilities)
3. [PROCDIFF Companion Tool](#3-procdiff-companion-tool)
4. [SNORT's Algorithm Deep-Dive](#4-snorts-algorithm-deep-dive)
5. [Chopper v2 Engine Requirements Recap](#5-chopper-v2-engine-requirements-recap)
6. [Feature-by-Feature Comparison Matrix](#6-feature-by-feature-comparison-matrix)
7. [SNORT's `define_proc_attributes` Handling vs Chopper Diagnostics](#7-snorts-define_proc_attributes-handling-vs-chopper-diagnostics)
8. [SNORT's Comment Line Handling for Proc Definitions](#8-snorts-comment-line-handling-for-proc-definitions)
9. [What SNORT Does Better](#9-what-snort-does-better)
10. [What Chopper Needs That SNORT Doesn't Provide](#10-what-chopper-needs-that-snort-doesnt-provide)
11. [Strategic Recommendation: Build, Borrow, or Hybrid](#11-strategic-recommendation-build-borrow-or-hybrid)
12. [Algorithms Worth Borrowing](#12-algorithms-worth-borrowing)
13. [Algorithms to Build New or Improve](#13-algorithms-to-build-new-or-improve)
14. [Implementation Roadmap](#14-implementation-roadmap)

---

## 1. Executive Summary

**SNORT** (Static aNalysis Of Routines in Tcl) is a ~7,850-line Perl tool built at Intel (authored by Michael McCurdy, PESG DDI) for analyzing, reporting on, and pruning VLSI EDA Tcl codebases. It has been **production-proven since 2009** across Intel's Design Compiler, IC Compiler, PrimeTime, Genus, and Innovus flows.

**Key findings:**

- SNORT is a **full-scope Tcl dead-code analysis engine** — far broader than Chopper's requirements
- SNORT's parsing is **regex-based and line-oriented** (not tokenizer-based), making it fast but fragile on edge cases
- SNORT has **battle-tested algorithms** for: brace counting, namespace extraction, proc detection, call graph construction, dead code identification, source tree tracing, and surgical proc pruning
- SNORT's scope includes vendor tool compatibility analysis, RDT flow integration, environment variable tracking, and project-specific code detection — **none of which Chopper needs**
- Chopper's spec demands **higher correctness guarantees** (formal state machine, diagnostic codes, deterministic BFS tracing, atomic operations) that SNORT doesn't provide

**Verdict:** Don't use SNORT directly. **Borrow its proven algorithms, re-implement them in Python with Chopper's correctness contracts**, and use SNORT as a validation oracle during testing.

---

## 2. SNORT Architecture & Capabilities

### 2.1 Overview

SNORT operates as a monolithic Perl script organized around a rich global state machine with three primary data structures:

| Data Structure | Purpose | Key Fields |
|---|---|---|
| `%procs` | Master procedure registry | `exists`, `definitions`, `file_usage`, `total_usage`, `pruned_usage`, `is_ven_proc`, `is_builtin`, `is_custom`, `callees`, `callers`, `sourcees`, `vars_set`, `description`, `dead`, `tool_cond`, `proj_cond`, `fubp_code`, `lib_hardcode`, `length`, `getenv`, `setenv`, `ven_abbrev`, `ven_ambigu`, `cus_abbrev`, `cus_ambigu`, `mislabel`, `embedded_proc`, `uneven_suppress`, `speculative` |
| `%files` | Per-file metadata | `length`, `sources`, `procs_sources`, `proc_callees`, `uneven_braces`, `proc_definitions`, `unix_script`, `executable` |
| `%other_code` | Non-proc code per file | Raw text of lines outside proc definitions |

### 2.2 Processing Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  1. Configuration           _GetOptionsAndReadConfigFile()  │
│     - Read config.pl                                        │
│     - Validate paths, extensions                            │
│     - Set tool flags (DC/ICC/PT/genus/innovus)              │
├─────────────────────────────────────────────────────────────┤
│  2. File Discovery          _GetAllFilesInPath()            │
│     - Enumerate all files matching extensions               │
│     - Handle top-of-tree files                              │
│     - Apply ignore list                                     │
├─────────────────────────────────────────────────────────────┤
│  3. Proc Discovery          _FindAllTclProcs()              │
│     - Grep-scan all .tcl for proc/namespace/define_proc_*   │
│     - Speculative namespace-qualified name generation       │
│     - Deep scan for proc calls inside code                  │
│     - Vendor proc + abbreviation matching                   │
├─────────────────────────────────────────────────────────────┤
│  4. Usage Calculation       _FindTclProcDefsAndCalcUsage()  │
│     - Load all file contents into memory                    │
│     - Count exact proc matches per file                     │
│     - Build definitions hash                                │
├─────────────────────────────────────────────────────────────┤
│  5. Full Parse              _ParseAllTclFilesInPath()       │
│     - _ParseTclSourceFile() for each file                   │
│     - Brace-counted state machine per file                  │
│     - Extract proc bodies, namespace context, other_code    │
│     - Track define_proc_attributes sections                 │
├─────────────────────────────────────────────────────────────┤
│  6. Analysis                                                │
│     - _AnalyzeNonProcTclCode() — call graph from non-proc   │
│     - _AnalyzeTclProcDefinitions() — callee/caller graphs   │
│     - Source file tree construction                         │
│     - Environment variable tracking                         │
│     - Vendor tool compatibility                             │
├─────────────────────────────────────────────────────────────┤
│  7. Dead Code Detection     _Initialize()                   │
│     - Iterative convergence loop (up to 10,000 iterations)  │
│     - _MarkDeadFiles() — recursive from orphan files        │
│     - _MarkDeadProcs() — recursive from orphan procs        │
├─────────────────────────────────────────────────────────────┤
│  8. Reporting / Pruning                                     │
│     - ReportCallTree()                                      │
│     - ReportSourceTree()                                    │
│     - ReportSourceFiles()                                   │
│     - ReportCustomProcs() / ReportVendorProcs()             │
│     - PruneCode() — surgical file/proc removal              │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Supported EDA Tools

| Flag | Tool | Vendor |
|---|---|---|
| `$DC` | Design Compiler | Synopsys |
| `$ICC` | IC Compiler | Synopsys |
| `$ICC2` | IC Compiler II | Synopsys |
| `$FC` | Fusion Compiler | Synopsys |
| `$PT` | PrimeTime | Synopsys |
| `$genus` | Genus | Cadence |
| `$innovus` | Innovus | Cadence |
| `$RDT` | RDT flow framework | Intel |
| `$CTH` | Cheetah/CTH flow | Intel |

### 2.4 Report Types Generated

1. **`report.call_tree`** — Full proc-to-proc call tree (recursive, circular-call detection)
2. **`report.source_tree`** — File-sources-file tree (recursive, circular-source detection)
3. **`report.source_files`** — Per-file analysis with 28+ warning categories
4. **`report.vendor_commands`** — Vendor proc usage, compatibility matrix
5. **`report.custom_procs`** — Custom proc analysis with 30+ warning categories
6. **`report.non_proc_code`** — Lines outside procs with violation categorization
7. **`report.prune_estimate`** — Dead code statistics before pruning
8. **`report.prune_actual`** — Results after pruning

---

## 3. PROCDIFF Companion Tool

**procdiff** (313 lines of Perl) is a targeted utility for comparing a **single Tcl procedure** across two files using `tkdiff`. Key capabilities:

- Extracts a named proc definition from each file using brace counting
- Also extracts the `define_proc_attributes` and `parseOpt::cmdSpec` sections for the proc
- Handles namespace prefixes (with and without leading `::`)
- Uses CurlyCount/QuoteCount for balanced extraction
- Supports `-w` (ignore whitespace) flag for tkdiff
- Creates temp files in `/tmp/procdiff.$USER/` for diff comparison
- Detects multiple definitions and reports errors

**Relevance to Chopper:** The proc extraction algorithm in procdiff is a clean, minimal implementation of the same brace-counting approach used in SNORT's `_ParseTclSourceFile()`. It could serve as a reference for Chopper's trimmer's proc boundary detection.

---

## 4. SNORT's Algorithm Deep-Dive

### 4.1 Brace Counting Algorithm (`_CurlyCount` / `_CurlyCount2`)

SNORT implements two variants:

**`_CurlyCount($line)`** — Returns delta count (opens minus closes):

```
Algorithm:
1. For opening braces:
   a. Strip escaped braces: {\\{ → {  (brace followed by escaped brace)
   b. Strip backslash-escaped braces: [^\\]\\{ → remove
   c. Count remaining { characters
2. For closing braces (on original line copy):
   a. Same escape stripping logic
   b. Count remaining } characters
3. Return (opens - closes)
```

**`_CurlyCount2($line)`** — Returns `(delta_count, braces_found)` tuple, used when we need to know if braces appeared at all (for single-line proc detection).

**Strengths:**

- Handles `\{` and `{\{` patterns correctly
- Separate logic for opening and closing braces (works on line copy)
- Battle-tested across Intel's codebase

**Weaknesses:**

- Does NOT handle braces inside quoted strings (Tcl Rule 4 vs Rule 6 ambiguity)
- Regex-based stripping can have edge cases with `\\\\{` (four backslashes before brace)
- No awareness of comment context — relies on caller to strip comments first

**Chopper comparison:** Chopper's spec requires comment-aware brace counting and explicit Rule 6 handling. SNORT's algorithm is a good starting point but needs enhancement.

### 4.2 Proc Detection Algorithm

SNORT detects procs in two phases:

**Phase A: Grep scan** (`_FindAllTclProcs()`)

```
For each .tcl file:
  For each line:
    If matches:  ^\s*proc\s
              OR ^namespace\s+eval\s.*\s\{
              OR ^[^#]*\si?define_proc_(attributes|arguments)\s+
              OR ^i?define_proc_(attributes|arguments)\s+
    → Record as hit with file:line
```

**Phase B: Deep call scan** (same function, second pass)

```
For each .tcl file:
  Track: open_count, namespace, namespace_level, quote_count
  For each line:
    Skip define_proc_attributes multi-line blocks
    Track namespace eval entries/exits
    Parse for proc calls using multi-level filtering:
      Level 1: proc name found as word in line
      Level 2: Not in comment, not a variable, not a definition
      Level 3: Not in a log/print statement
      Level 4: Not used as a print label
    Add discovered procs to registry
```

**Speculative namespace handling:**

When a namespace is open and a proc is defined without `::`, SNORT creates TWO entries:

- `namespace::proc` (speculative)
- `proc` (speculative)

Both are marked `speculative = 1`. The `_ProcGarbageCollector()` later deletes speculatives that were never confirmed by `_ParseTclSourceFile()`.

**Strengths:**

- 4-level filtering heuristic is remarkably effective at distinguishing proc calls from mentions
- Speculative dual-registration handles the common ambiguity of "is this proc in the namespace or not?"
- Handles abbreviated vendor command detection

**Weaknesses:**

- Line-oriented (not token-oriented) — can miss procs spanning multiple lines
- No formal grammar — relies on regex patterns that accumulate special cases
- Multi-line comment handling is a hack (`if multiline_comment: prepend #`)
- No formal state machine — brace/quote tracking is ad-hoc

### 4.3 Namespace Handling

```
Detection:   ^namespace\s+eval\s.*\s\{
Extraction:  Strip "namespace eval " prefix, strip trailing \s.*$, strip ::
Scope:       namespace_level = open_count at time of namespace eval
Reset:       When open_count drops to <= namespace_level
Nesting:     Only one level tracked (namespace resets if new namespace eval while already in one)
```

**Critical limitation:** SNORT only tracks ONE namespace level. Nested `namespace eval` blocks will lose the outer namespace. Chopper's spec requires a LIFO stack (unlimited nesting).

### 4.4 Dead Code Detection Algorithm

SNORT uses an **iterative convergence loop** — the most sophisticated algorithm in the tool:

```
Initialize():
  repeat (up to 10,000 iterations):
    dead_count = 0
    dead_count += _MarkDeadFiles()
    dead_count += _MarkDeadProcs()
  until dead_count == 0
```

**`_MarkDeadFiles()`:**

1. Find orphan files (not sourced by any other file, not top-of-tree)
2. For each orphan: recursively mark children dead if all parents are dead
3. A file is dead if: no living parents AND not top-of-tree AND not do-not-prune

**`_MarkDeadProcs()`:**

1. Find orphan procs (no callers, or only called by dead entities)
2. For each orphan: recursively mark callee procs dead
3. A proc is dead if:
   - (no living parents AND not defined in top-of-tree) OR (all definitions in dead files)
   - AND not on do-not-prune list
   - AND no definitions in do-not-prune files

**The convergence property:** Each iteration may mark new files/procs dead, which in turn may cause their dependents to become dead. This cascading effect converges when no new dead entities are found.

**Strengths:**

- Handles circular dependencies gracefully (convergence loop breaks cycles)
- Respects do-not-prune lists and top-of-tree designations
- Accurate dead code percentage calculations

**Relevance to Chopper:** This algorithm is conceptually similar to Chopper's BFS trace expansion run in reverse — finding unreachable code. Chopper doesn't need dead code detection (it uses forward selection), but the iterative convergence technique could inform future "what-if" analysis features.

### 4.5 Proc Pruning Algorithm (`_PruneProcDefsFromFile`)

The most directly relevant algorithm for Chopper's trimmer:

```
For each file with procs to remove:
  open_count = 0, namespace = "", proc = ""
  comment_cache = []

  For each line:
    If namespace eval at file level:
      Keep line, track namespace
    Elif proc definition start AND not already in proc:
      Full-qualify proc name with namespace
      Track proc_level = open_count
      Decision: keep or drop based on remove list
    Elif inside namespace or proc:
      Count braces
      If still inside proc/namespace body:
        Route to keep_lines or drop_lines via _KeepOrDropCodeLine()
      Else (exited):
        Route closing brace to keep/drop
        Reset proc state
        Look ahead for define_proc_attributes section
        If found: route entire DPA block to keep/drop based on DPA's proc name
    Else:
      Non-proc code: keep unless inside a removed proc
      Comments: buffer in comment_cache (sticky-bit logic)

  Write keep_lines back to original file
  Write drop_lines to OBSOLETE/ directory
```

**Comment association (sticky-bit mechanism):**

- Comments between proc definitions are buffered in `comment_cache`
- If the next non-comment code is "keep" → comments go to keep_lines
- If "drop" → comments go to drop_lines
- The `sticky_bit` flag handles the case where a commented-out proc definition (`#proc ...`) should be dropped along with its associated block

**Strengths:**

- Preserves file structure precisely — non-proc code, namespace blocks kept intact
- Comment association is bidirectional (comments attach to the entity they precede)
- Handles define_proc_attributes sections correctly
- Backup/trash directory mechanism for recovery

**Weaknesses:**

- No atomic operations — crash during write leaves partial files
- No blank line collapse logic
- SCM integration (SVN/P4) is hardcoded

### 4.6 Source Tree Construction

SNORT builds a complete `source`/`sourced_by` bidirectional graph:

```
For each file:
  Scan for: source, rdt_source_if_exists, source_pkg_file,
            iproc_source, iproc_source_distributed, Ifc_shell/Ipt_shell -f

  _ExtractSourcedFileFromLine():
    1. Strip command options (-echo, -verbose, -continue_on_error, etc.)
    2. Handle special constructs (namespace eval :: [list source ...])
    3. Strip directory paths, keeping filename only
    4. Handle quotes, brackets, backslashes
    5. Substitute known variables ($fub, $proj, etc.)
    6. Return clean filename
```

**Strengths:**

- Handles 10+ different source commands across Synopsys/Cadence/Intel tools
- Robust option stripping for each command variant
- Variable substitution for common patterns

### 4.7 Call Graph Construction (`_IsProcFoundInLine`)

This is SNORT's most complex function — a **4-level cascading filter** to determine if a proc name truly appears as a call in a code line:

```
Level 1 (grep -e):  Proc name found as word boundary match
Level 2 (grep -v):  NOT in: define_proc_attributes, get/set_app_var,
                     comments, substrings, variable refs, argument lists,
                     regexp patterns, redirect targets, switch cases
Level 3 (log filter): NOT in: print/echo/puts string arguments,
                       help commands, quoted descriptions
Level 4 (label filter): NOT used as: print label in echo/puts statements,
                         BUT catch embedded calls in print strings

Special: Handle multiple instances of proc name in same line
Special: Handle procs with namespaces (foo::bar vs bar)
Special: Handle single-character proc names
```

**Strengths:**

- Remarkably accurate for a regex-based approach
- Handles dozens of false-positive patterns
- Production-proven across massive codebases

**Weaknesses:**

- Extremely complex (the function is ~150 lines of nested regex)
- Fragile — each new false positive requires a new pattern
- Not compositional — understanding the interaction of all 4 levels is difficult

---

## 5. Chopper v2 Engine Requirements Recap

| Requirement | Chopper Spec | SNORT Capability |
|---|---|---|
| **Proc detection** | Formal state machine, `ProcEntry` frozen dataclass | Regex-based, hash of hashes |
| **Namespace handling** | LIFO stack (unlimited nesting) | Single level only |
| **Brace counting** | Rule 6 aware (quotes literal in braced bodies) | No Rule 6 awareness |
| **Comment handling** | Command-position only (Tcl Rule 10) | Partial (line-start heuristic) |
| **Backslash continuation** | Preserve original lines, track line numbers | Some support, not fully spec'd |
| **Computed proc names** | Skip with `PW-01 computed-proc-name` warning | Skip with `print` warning |
| **Duplicate procs** | Error `PE-01 duplicate-proc-definition`, last-wins | Warning, both kept |
| **Call extraction** | Deterministic namespace resolution contract | 4-level heuristic filter |
| **Trace algorithm** | BFS, lexicographically sorted frontier | Iterative convergence (reverse) |
| **Merge semantics** | Explicit include always wins | Not applicable (dead code model) |
| **Trimmer** | Atomic staging, blank line collapse, byte-perfect | Direct file edit, OBSOLETE dir |
| **Diagnostics** | 47+ structured codes with severity/location | Print warnings inline |
| **Determinism** | Mandatory (reproducible output) | Not guaranteed (hash ordering) |
| **JSON serialization** | All models serializable | No JSON output |
| **Encoding** | UTF-8 with Latin-1 fallback | Perl's default (usually Latin-1) |

---

## 6. Feature-by-Feature Comparison Matrix

| Feature | SNORT | Chopper Needed | Gap | Recommendation |
|---|---|---|---|---|
| **Brace counting** | Good (escape-aware) | Needs Rule 6 + comment-aware | Small | Borrow + extend |
| **Proc boundary detection** | Good (brace-counted) | Needs formal spans | Small | Borrow + formalize |
| **Namespace extraction** | Basic (single level) | Needs LIFO stack | Medium | Build new |
| **Proc-in-namespace dual registration** | Excellent (speculative) | Needs canonical names | Medium | Borrow concept |
| **define_proc_attributes parsing** | Excellent | Potentially useful | N/A | Borrow for future |
| **Comment-proc association** | Good (sticky-bit) | Needs bidirectional | Small | Borrow + adapt |
| **Call graph construction** | Excellent (4-level filter) | Needs deterministic resolver | Large | Build new |
| **Dead code detection** | Excellent (iterative convergence) | Not needed (forward selection) | N/A | Don't port |
| **Source tree tracing** | Excellent | Simpler version needed | Large | Build simpler |
| **Vendor tool compatibility** | Excellent | Not needed | N/A | Don't port |
| **Pruning/trimming** | Good (keep/drop split) | Needs atomic staging | Medium | Borrow + harden |
| **Environment variable tracking** | Good | Not needed | N/A | Don't port |
| **Abbreviated proc detection** | Excellent | Not needed | N/A | Don't port |
| **RDT flow integration** | Extensive | Not needed | N/A | Don't port |
| **Diagnostic codes** | Ad-hoc print statements | Needs structured system | Large | Build new |
| **Deterministic output** | Not guaranteed | Mandatory | Large | Build new |
| **JSON serialization** | None | Required | Large | Build new |

---

## 7. SNORT's `define_proc_attributes` Handling vs Chopper Diagnostics

### 7.1 SNORT's DPA Parsing

SNORT has dedicated handling for `define_proc_attributes` (DPA) — a Synopsys convention for annotating proc metadata:

```tcl
define_proc_attributes my_proc \
  -info "Description of my_proc" \
  -define_args {
    {-input "Input file" "" string required}
    {-output "Output file" "" string optional}
  }
```

**SNORT's `_GetDefineProcAttributesProcName($line)` algorithm:**

1. Strip `define_proc_(attributes|arguments)` prefix
2. Strip boolean switches: `-permanent`, `-hide_body`, `-hidden`, `-dont_abbrev`, `-obsolete`, `-deprecated`
3. Strip non-boolean args with values: `-info "..."`, `-define_args {...}`, `-command_group ...`, `-return ...`
4. Strip `\r`, trailing `\`, trailing whitespace
5. Return the remaining token as the proc name

**SNORT tracks from DPA:**

- `$procs{$proc}{description}` — extracted from `-info "..."` field
- Used for: "no define_proc_attribute description" warning
- DPA's proc name cross-referenced with preceding proc definition
- If DPA proc name differs from preceding proc → treated as non-proc code

### 7.2 Relevance to Chopper

Chopper's diagnostic codes system (`VE-*`, `VW-*`, `TW-*`, `PE-*`, `PW-*`, `PI-*`) is far more structured than SNORT's ad-hoc warnings. However, SNORT's DPA parsing reveals useful patterns:

| SNORT DPA Warning | Chopper Equivalent | Status |
|---|---|---|
| "No define_proc_attribute description" | `PI-01` (structured comment block) | Similar concept |
| "define_proc_attributes proc name != preceding proc" | `PW-06` (DPA mismatch) | **Consider adding** |
| Multiple DPA definitions for same proc | `PE-03` (DPA duplicate) | **Consider adding** |
| DPA with `-obsolete` flag | `PW-07` (deprecated proc) | **Consider adding** |

**Recommendation:** If Chopper ever needs to support Synopsys flows, the DPA parsing from SNORT is directly reusable. For now, capture the **comment-to-proc association** concept using Chopper's `PI-01` diagnostic and the parser's structured comment detection.

---

## 8. SNORT's Comment Line Handling for Proc Definitions

### 8.1 SNORT's Three Comment Handling Contexts

**Context 1: Comment caching during pruning** (`_PruneProcDefsFromFile`)

```perl
# Comments between procs are buffered in @comment_cache
# They attach to the NEXT entity encountered:
#   - If next entity is KEPT → comments go to keep_lines
#   - If next entity is DROPPED → comments go to drop_lines
# sticky_bit: If a commented-out proc (e.g., "# proc foo ...") is found,
#   set sticky_bit = 1 → all buffered comments also drop
```

**Context 2: Comment detection in code analysis** (`_IsNonBlankLine`)

```perl
sub _IsNonBlankLine($) {
    # A line is blank if ONLY comments or whitespace
    if (!($line =~ /^\s*\#/) && !($line =~ /^\s*$/)) {
        return 1;  # Has real code
    }
    return 0;       # Comment-only or empty
}
```

**Context 3: Multi-line comment tracking** (in `_FindAllTclProcs`)

```perl
if ($multiline_comment) {
    $line =~ s/^/#/;  # Force-comment continuation lines
} elsif ($line =~ /^#/ || ($line =~ /[^\\]#/ && !($line =~ /[{"].*#.*[{"]/))) {
    $multiline_comment = 1;
}
```

### 8.2 Comparison with Chopper's Spec

| Aspect | SNORT | Chopper Spec |
|---|---|---|
| Comment detection | `^\s*#` (line start) | Command position (after `;` or line start) per Tcl Rule 10 |
| Multi-line comments | Heuristic continuation | Backslash-newline continuation only |
| Braces in comments | NOT handled (counted normally in some paths) | Explicitly inert (spec P-07) |
| Comment-proc association | Sticky-bit forward attachment | Backward scan: contiguous comments before proc |
| Inline comments | Partial (`;\s*#` → strip) | Formal: `#` at command position after `;` |

### 8.3 Diagnostic Code Opportunities

For Chopper's comment handling in proc definitions:

| Situation | Proposed Diagnostic | Severity |
|---|---|---|
| Structured comment block found before proc | `PI-01` (already specified) | Info |
| Commented-out proc definition (`# proc foo`) | `PW-08` — Commented-out proc | Warning |
| Comment with unescaped braces inside proc body | Already handled by Rule 6 in brace counter | N/A |
| Multi-line comment with line continuation | `PI-03` — Comment continuation | Info |
| Orphan DPA without preceding proc | `PW-06` — Orphan DPA block | Warning |

---

## 9. What SNORT Does Better

### 9.1 Proc Call Detection Heuristics

SNORT's 4-level `_IsProcFoundInLine()` filter has been refined over 15+ years of production use. Its ability to distinguish genuine proc calls from:

- Variable names
- String contents in print/log statements
- Argument list positions
- Regexp pattern strings
- Switch case labels
- Abbreviations and ambiguous names

...is unmatched by any formal approach Chopper could build from scratch in comparable time.

### 9.2 define_proc_attributes Integration

SNORT treats DPA as a first-class construct: parsing the proc name, extracting descriptions, detecting mismatches, and associating DPA blocks with proc definitions during pruning. This is directly applicable to VLSI EDA codebases.

### 9.3 Iterative Dead Code Convergence

The cascading mark-dead algorithm (up to 10,000 iterations) handles complex dependency chains that a single-pass BFS would miss. The convergence guarantee is elegant.

### 9.4 Vendor Command Awareness

SNORT dynamically generates vendor command lists by invoking actual EDA tool shells (`dc_shell`, `icc2_shell`, `pt_shell`, etc.) and capturing `help *` output. This gives it perfect knowledge of vendor commands — something Chopper would need a static builtin list for.

### 9.5 Source Command Extraction

The `_ExtractSourcedFileFromLine()` function handles an extraordinary range of `source` command variants, options, and variable interpolations. This accumulated knowledge is valuable.

---

## 10. What Chopper Needs That SNORT Doesn't Provide

### 10.1 Formal Correctness

| Requirement | SNORT Gap |
|---|---|
| Deterministic output | Hash iteration order is non-deterministic in Perl |
| BFS with sorted frontier | SNORT uses forward grep, not BFS |
| Frozen immutable data models | Perl hashes are mutable global state |
| Structured diagnostic codes | Ad-hoc print/warn statements |
| JSON-serializable everything | No serialization support |
| Exit code contracts | `die` and `exit(1)` only |

### 10.2 Modern Architecture

| Requirement | SNORT Gap |
|---|---|
| Service layer (no `print`) | Extensive `print` throughout |
| Protocol-based interfaces | Monolithic Perl with globals |
| Testable in isolation | Everything depends on global state |
| Frozen dataclasses | Mutable hash-of-hashes |
| Type safety | Perl dynamic typing, no contracts |

### 10.3 Tcl Correctness

| Requirement | SNORT Gap |
|---|---|
| Tcl Rule 6 (quotes in braces) | Not handled |
| LIFO namespace stack (unlimited) | Single level only |
| Formal command position for `#` | Line-start heuristic |
| Backslash continuation line tracking | Partial (some paths join lines) |
| Encoding fallback (UTF-8 → Latin-1) | Perl default only |

### 10.4 Operational Safety

| Requirement | SNORT Gap |
|---|---|
| Atomic staging/promotion | Direct file edit |
| Backup/restore lifecycle | OBSOLETE directory (no restore) |
| Lock-based concurrency protection | None |
| State machine for trim lifecycle | None |

---

## 11. Strategic Recommendation: Build, Borrow, or Hybrid

### 11.1 The Three Options

**Option A: Use SNORT directly**

- Call SNORT as a subprocess, parse its reports
- **Rejected:** SNORT is Perl, requires EDA tool access for vendor commands, outputs unstructured text, can't meet Chopper's determinism/diagnostic/serialization requirements

**Option B: Port SNORT to Python**

- Translate SNORT line-by-line to Python
- **Rejected:** SNORT's architecture (global mutable state, regex spaghetti, 7850 lines of accumulated special cases) is fundamentally incompatible with Chopper's frozen-dataclass, service-layer, protocol-based design. A port would inherit all of SNORT's design debt.

**Option C: Hybrid — Borrow algorithms, build new architecture (RECOMMENDED)**

- Study SNORT's proven algorithms as reference implementations
- Re-implement the valuable algorithms in Python with Chopper's correctness contracts
- Build from scratch where SNORT's approach doesn't meet requirements
- Use SNORT as a test oracle: run both on test fixtures, compare results

### 11.2 Why Hybrid is Best

1. **SNORT has 15 years of edge-case knowledge baked into its regex patterns.** This is irreplaceable domain knowledge that should inform Chopper's parser, even if the implementation differs.

2. **SNORT's architecture won't scale to Chopper's requirements.** The global mutable state, non-deterministic hash ordering, and lack of structured output mean that even a perfect Python port wouldn't pass Chopper's CI.

3. **The algorithmic patterns are universally applicable.** Brace counting, namespace tracking, proc boundary detection, comment association — these algorithms can be cleanly re-implemented in a state-machine-based Python parser.

4. **SNORT's scope is 80% irrelevant to Chopper.** Vendor tool compatibility, RDT flow integration, environment variable tracking, project-specific code detection — all of this is dead weight for Chopper.

---

## 12. Algorithms Worth Borrowing

### 12.1 Brace Counting (High Value)

**From:** `_CurlyCount()` / `_CurlyCount2()`
**Adapt for Chopper:**

```python
def count_braces(line: str, in_comment: bool) -> tuple[int, bool]:
    """
    Returns (delta, braces_found).
    Enhancement over SNORT: skip braces in comments entirely.
    Enhancement over SNORT: Rule 6 awareness (don't count braces in
    quoted strings when NOT inside a braced body).
    """
```

**What to borrow:** The backslash-escape stripping logic (`\{` and `{\{` patterns).
**What to improve:** Add comment awareness, Rule 6 handling, and return typed result instead of raw int.

### 12.2 Proc Boundary Detection (High Value)

**From:** `_ParseTclSourceFile()` proc detection loop
**Adapt for Chopper:**

```python
# SNORT pattern (line ~4712):
# m/^\s*proc\s+([^\s^\(^\[]+)\s/i  → proc definition start
# Track proc_level = open_count at definition start
# Exit when open_count drops back to proc_level
```

**What to borrow:** The detection pattern, the brace-depth tracking for proc body boundaries, the 1-line proc detection (`curly_delta == 0 && !line ends with \`).
**What to improve:** Use named groups, emit `ProcEntry` dataclass, handle multi-line proc headers.

### 12.3 Namespace Extraction (Medium Value)

**From:** `_ExtractNamespaceFromLine()`, namespace tracking in `_ParseTclSourceFile()`
**Adapt for Chopper:**

```python
# SNORT pattern: ^namespace\s+eval\s.*\s\{
# SNORT extraction: strip prefix, strip trailing, strip ::
# SNORT limitation: single level
```

**What to borrow:** The extraction regex and the concept of tracking namespace_level.
**What to improve:** Replace single-level tracking with LIFO stack. Handle computed namespace names (emit `PW-04`).

### 12.4 Comment-Proc Association (High Value)

**From:** `_KeepOrDropCodeLine()` sticky-bit mechanism
**Adapt for Chopper:**

The sticky-bit concept — buffering comments and deciding their fate based on the next real code entity — is directly applicable to Chopper's trimmer. Chopper should:

1. Buffer comment lines while scanning
2. When proc-to-remove is found: check if buffered comments are contiguous (no blank line) → drop with proc
3. When kept code found: flush buffer to keep_lines

### 12.5 `define_proc_attributes` Proc Name Extraction (Medium Value)

**From:** `_GetDefineProcAttributesProcName()`
**Adapt for Chopper:**

Even if Chopper doesn't need DPA in v1, the extraction algorithm is valuable for future EDA tool integration. The logic for stripping boolean flags, non-boolean args with values, and handling multi-line DPA blocks is non-trivial and well-tested.

### 12.6 Proc Pruning Keep/Drop Logic (High Value)

**From:** `_PruneProcDefsFromFile()` and `_KeepOrDropCodeLine()`
**Adapt for Chopper:**

The line-by-line classification into keep/drop sets with comment buffering is the core of Chopper's trimmer. The SNORT implementation handles:

- Namespace boundaries (keep even if procs inside are removed)
- define_proc_attributes blocks (drop with associated proc)
- Commented-out proc definitions (drop via sticky_bit)
- Non-proc code (always keep)

### 12.7 Speculative Dual Registration (Medium Value)

**From:** `_FindAllTclProcs()` speculative namespace handling
**Concept for Chopper:**

When a proc is defined inside a namespace but without `::` qualification, register as both `ns::proc` and `proc`, mark both speculative, and confirm the correct one during full parsing. This technique handles a real ambiguity in Tcl codebases.

**Chopper adaptation:** Instead of speculative dual registration, use the namespace stack to always emit the fully-qualified canonical name, and store the short name as a separate field in `ProcEntry`. Resolution at trace time uses the deterministic resolution contract (try caller_ns::proc, then global proc).

---

## 13. Algorithms to Build New or Improve

### 13.1 State Machine Tokenizer (Build New)

SNORT's line-oriented regex scanning cannot meet Chopper's Tcl correctness requirements. Build a formal state machine:

```
States: NORMAL, IN_BRACE, IN_QUOTE, IN_COMMENT, CONTINUATION
Transitions driven by: character-by-character + lookahead
Track: brace_depth, namespace_stack, in_quote, in_comment, continuation
Output: Token stream → ProcEntry records
```

**Why new:** SNORT processes lines; Chopper needs character-level awareness for Rule 6 and Rule 10 compliance.

### 13.2 Deterministic BFS Trace Expansion (Build New)

SNORT's forward scan + iterative dead code detection is the opposite of Chopper's forward selection model. Build BFS from scratch per the Chopper spec:

```python
frontier = SortedList(explicit_pi_entries)
traced = set()
while frontier:
    proc = frontier.pop_min()  # Lexicographic ordering
    if proc in traced: continue
    traced.add(proc)
    for callee in extract_calls(proc.body):
        resolved = resolve_namespace(callee, proc.namespace)
        if resolved and resolved not in traced:
            frontier.add(resolved)
```

**Why new:** SNORT has no equivalent. Its dead code approach runs backward (mark unreachable); Chopper runs forward (expand reachable).

### 13.3 Structured Diagnostic System (Build New)

SNORT uses `print`, `warn`, and `die`. Chopper needs:

```python
@dataclass(frozen=True)
class Diagnostic:
    code: str           # "PE-01", "VW-03", etc.
    severity: Severity  # ERROR, WARNING, INFO
    message: str
    location: Location  # file:line:column or JSON path
    hint: str
    source: str         # Module that emitted it
```

**Why new:** Fundamental architectural difference. No SNORT analog.

### 13.4 Atomic Staging and Promotion (Build New)

SNORT writes directly to original files with OBSOLETE/ directory backup. Chopper needs:

```
domain/ → domain_backup/ (os.rename, atomic)
Build into domain_staging/
Validate domain_staging/
domain_staging/ → domain/ (os.replace, atomic)
```

**Why new:** SNORT's approach is unsafe for production use. No SNORT analog for atomic operations.

### 13.5 Quote-Aware Brace Counting (Improve SNORT's)

SNORT's brace counter ignores Tcl Rule 6. Chopper must:

```
If processing braced word (proc body):
    Quotes are LITERAL → do NOT suppress brace counting
If processing quoted word:
    Braces are LITERAL → do NOT count them
If in comment:
    All braces INERT
```

**Why improve:** SNORT's counter works on most real code but fails on adversarial inputs (see `tests/fixtures/edge_cases/`).

### 13.6 Multi-Level Namespace Stack (Improve SNORT's)

SNORT tracks one namespace level. Improve to:

```python
class NamespaceTracker:
    stack: list[tuple[str, int]]  # (name, entry_brace_depth)

    def push(self, name: str, brace_depth: int): ...
    def pop_if_exited(self, brace_depth: int): ...
    def current_path(self) -> str:
        return "::".join(name for name, _ in self.stack)
```

---

## 14. Implementation Roadmap

### Phase 1: Core Parser (Borrow + Build)

| Task | Source | Effort |
|---|---|---|
| Brace counter with Rule 6 + comment awareness | Borrow SNORT `_CurlyCount`, extend | Low |
| Proc boundary detector | Borrow SNORT `_ParseTclSourceFile` pattern, formalize | Medium |
| LIFO namespace stack | Improve SNORT's single-level to stack | Low |
| Backslash continuation tracker | Borrow SNORT's approach, add line number tracking | Low |
| State machine tokenizer | Build new | Medium |
| Computed proc name detection | Borrow SNORT's `$`, `[` check | Low |
| Structured comment extraction | Adapt SNORT's comment_cache concept | Low |

### Phase 2: Compiler (Build New)

| Task | Source | Effort |
|---|---|---|
| BFS trace expansion | Build new per spec | Medium |
| Deterministic namespace resolution | Build new per spec | Medium |
| Merge algorithm (include wins) | Build new per spec | Medium |
| Feature ordering | Build new | Low |

### Phase 3: Trimmer (Borrow + Build)

| Task | Source | Effort |
|---|---|---|
| Keep/drop line classification | Borrow SNORT `_PruneProcDefsFromFile` | Medium |
| Comment-proc association | Borrow SNORT sticky-bit concept | Low |
| DPA block association | Borrow SNORT DPA parsing | Low |
| Blank line collapse | Build new | Low |
| Atomic staging/promotion | Build new | Medium |

### Phase 4: Future-Ready Extensions (From SNORT)

| Task | Source | Priority |
|---|---|---|
| DPA parsing for vendor flows | Port SNORT's DPA extraction | Future |
| Source command extraction | Adapt SNORT's multi-variant handler | Future |
| Vendor builtin registry | Adapt SNORT's `tcl_builtins.txt` concept | Future |
| Call detection heuristics | Study SNORT's 4-level filter for edge cases | Future |

---

## Appendix A: SNORT File Statistics

| Metric | Value |
|---|---|
| Total lines | 7,850 |
| Language | Perl 5.40.1 |
| Subroutines (public) | 12 |
| Subroutines (private) | 55+ |
| Global variables | 40+ |
| Regex patterns | 500+ |
| Warning categories | 30+ per report |
| First copyright | 2009 |
| Supported EDA tools | 7 (DC, ICC, ICC2, FC, PT, genus, innovus) |

## Appendix B: PROCDIFF File Statistics

| Metric | Value |
|---|---|
| Total lines | 313 |
| Language | Perl 5.40.1 |
| Subroutines | 3 (`ProcDiff`, `CurlyCount`, `QuoteCount`) |
| Purpose | Visual diff of single proc across two files |
| External tool | tkdiff |

## Appendix C: Tcl Builtins Registry

SNORT ships with `tcl_builtins.txt` containing:

- **Core builtins:** 57 commands (after, append, array, ... while)
- **Math builtins:** 25 functions (acos, asin, ... wide)
- **Widget creation:** 18 commands (button, canvas, ... toplevel)
- **Widget manipulation:** 24 commands (bell, bind, ... wm)

Chopper should adopt this registry as a starting point for its builtin detection (useful for `TW-02` cross-domain resolution).

---

## Appendix D: Key SNORT Functions and Their Chopper Equivalents

| SNORT Function | Lines | Chopper Module | Chopper Equivalent |
|---|---|---|---|
| `_CurlyCount()` | ~25 | parser/tokenizer.py | `count_braces()` |
| `_CurlyCount2()` | ~25 | parser/tokenizer.py | `count_braces_with_presence()` |
| `_QuoteCount()` | ~20 | parser/tokenizer.py | `count_quotes()` |
| `_ExtractNamespaceFromLine()` | ~10 | parser/parse.py | `NamespaceTracker.push()` |
| `_ParseTclSourceFile()` | ~300 | parser/parse.py | `parse_file()` |
| `_FindAllTclProcs()` | ~250 | parser/parse.py | `build_proc_index()` |
| `_FindTclProcDefsAndCalcUsage()` | ~120 | compiler/trace.py | `trace_dependencies()` |
| `_AnalyzeTclProcDefinitions()` | ~180 | compiler/trace.py | `extract_calls()` |
| `_MarkDeadProcs()` / `_RecursiveFindDeadProcs()` | ~100 | N/A | Not needed (forward selection) |
| `_MarkDeadFiles()` / `_RecursiveFindDeadFiles()` | ~80 | N/A | Not needed (forward selection) |
| `_PruneProcDefsFromFile()` | ~150 | trimmer/trimmer.py | `trim_file()` |
| `_KeepOrDropCodeLine()` | ~50 | trimmer/trimmer.py | `classify_line()` |
| `_GetDefineProcAttributesProcName()` | ~30 | parser/parse.py | `extract_dpa_proc_name()` |
| `_IsProcFoundInLine()` | ~150 | compiler/trace.py | `is_proc_call()` |
| `_ExtractSourcedFileFromLine()` | ~200 | compiler/trace.py | `extract_source_target()` |
| `_GetFullProcName()` | ~10 | core/models.py | `ProcEntry.canonical_name` |
| `_IsNonBlankLine()` | ~10 | parser/tokenizer.py | `is_code_line()` |

---

*End of analysis.*
