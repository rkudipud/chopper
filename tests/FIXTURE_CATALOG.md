# Chopper — Parser Test Fixture Catalog

> **Scope:** Stage 1 — Parser (module `src/chopper/parser/`)

This file enumerates all parser test fixtures required for Stage 1 acceptance. Each fixture maps to a pitfall reference and the TCL spec section it exercises. Every fixture must be implemented before the Parser module is declared complete and Stage 2 (Compiler) begins.

---

## Fixture Index

| # | Fixture File | Pitfall | TCL Spec Section | Expected Outcome |
|---|---|---|---|---|
| 1 | `parser_basic_single_proc.tcl` | — | §4.1 | One `ProcEntry` with correct name, `start_line`, `end_line` |
| 2 | `parser_basic_multiple_procs.tcl` | — | §4.1 | Two or more `ProcEntry` records; no overlapping spans |
| 3 | `parser_empty_file.tcl` | P-06 | §7.3 | Empty list — no error, no warning |
| 4 | `parser_brace_in_string_literal.tcl` | P-01 | §3.1, §7.1 | Parse error diagnostic — unbalanced brace inside braced proc body |
| 5 | `parser_backslash_line_continuation.tcl` | P-02 | §3.2, §7.2 | `ProcEntry` spans correct; original source line numbers preserved |
| 6 | `parser_nested_namespace_accumulates.tcl` | P-03 | §4.5 | `qualified_name` = `a::b::deep_proc`; `namespace_path` = `a::b` |
| 7 | `parser_namespace_reset_after_block.tcl` | P-03, B-04 | §4.5 | `p1.qualified_name = a::p1`, `p2.qualified_name = b::p2` after sequential blocks |
| 8 | `parser_computed_proc_name_skipped.tcl` | P-04 | §4.3 | No `ProcEntry` for dynamic name; WARNING diagnostic `PW-01 computed-proc-name` |
| 9 | `parser_duplicate_proc_definition_error.tcl` | P-05 | §6.1, §7.10 | ERROR diagnostic `PE-01 duplicate-proc-definition`; proc index uses last definition's span |
| 10 | `parser_comment_with_braces_ignored.tcl` | P-07 | §3.4 | `ProcEntry` parsed correctly; brace in comment does not affect depth |
| 11 | `parser_proc_inside_if_block.tcl` | — | §4.4, §7.8 | Proc inside `if` NOT indexed; debug log emitted |
| 12 | `parser_namespace_absolute_override.tcl` | — | §4.3 | `proc ::abs::foo` inside `namespace eval ns` resolves as `abs::foo` |
| 13 | `parser_empty_proc_body_forms.tcl` | B-02 | §6.1 | Three fixtures: one-line, empty-multiline, whitespace-only; correct `body_start_line`/`body_end_line` for each |
| 14 | `parser_call_extraction.tcl` | — | §5.1 | Call extraction returns both direct and bracketed proc call tokens |
| 15 | `parser_encoding_latin1_fallback.tcl` | — | §2, §7.7 | Parses successfully with WARNING for Latin-1 fallback |
| 16 | `parser_eda_complex_del_seq_rpt.tcl` | — | §3.1, §3.2, §4.4, §4.6, §4.7, §7.14 | One `ProcEntry`; correct DPA + comment spans; no parse errors despite regexp `{pattern}` and multi-line `lappend` backslash continuation |
| 17 | `parser_eda_complex_get_hier_summary.tcl` | — | §4.6, §4.7, §5.2, §5.5 | One `ProcEntry`; `puts`/`echo`/EDA commands suppressed; `redirect -variable` string content not extracted; no parse errors |

---

## Fixture Detail

### 1 — `parser_basic_single_proc.tcl`

```tcl
proc setup_tool {} {
    set x 1
    return $x
}
```

**Expected:** `[ProcEntry(canonical_name="parser_basic_single_proc.tcl::setup_tool", start_line=1, end_line=4, body_start_line=2, body_end_line=3)]`

---

### 2 — `parser_basic_multiple_procs.tcl`

```tcl
proc proc_a {} { return "a" }

proc proc_b {x} {
    return $x
}
```

**Expected:** Two entries; `proc_a.start_line=1`, `proc_a.end_line=1`; `proc_b.start_line=3`, `proc_b.end_line=5`. No overlapping spans.

---

### 3 — `parser_empty_file.tcl`

```tcl
# This file has no proc definitions
set x 1
```

**Expected:** `[]` — no diagnostics, no errors.

---

### 4 — `parser_brace_in_string_literal.tcl`

```tcl
proc tricky {args} {
    set data "this has { an open brace"
    return $data
}
```

**Expected:** Parse error diagnostic. The `{` inside the quoted string inside a braced proc body still increments brace depth under Tcl Rule 6, making the body unbalanced.

---

### 5 — `parser_backslash_line_continuation.tcl`

```tcl
proc split_def \
    {arg1 arg2} \
    {
    return [list $arg1 $arg2]
}
```

**Expected:** One `ProcEntry`; `start_line=1` (original source, not joined), `end_line=6`. `body_start_line=4`, `body_end_line=5`.

---

### 6 — `parser_nested_namespace_accumulates.tcl`

```tcl
namespace eval a {
    namespace eval b {
        proc deep_proc {} { return "deep" }
    }
}
```

**Expected:** `ProcEntry(qualified_name="a::b::deep_proc", namespace_path="a::b")`.

---

### 7 — `parser_namespace_reset_after_block.tcl`

```tcl
namespace eval a {
    proc p1 {} { return "a" }
}

namespace eval b {
    proc p2 {} { return "b" }
}
```

**Expected:** `p1.qualified_name = "a::p1"`, `p2.qualified_name = "b::p2"`. The namespace stack resets to empty after each block closes.

---

### 8 — `parser_computed_proc_name_skipped.tcl`

```tcl
proc ${prefix}_handler {} {
    return "dynamic"
}
```

**Expected:** No `ProcEntry`. WARNING diagnostic with code `PW-01 computed-proc-name`.

---

### 9 — `parser_duplicate_proc_definition_error.tcl`

```tcl
proc read_data {} {
    return "version 1"
}

proc read_data {} {
    return "version 2"
}
```

**Expected:** ERROR diagnostic code `PE-01 duplicate-proc-definition`. Proc index contains only the second definition (lines 5–7). File flagged as invalid for trim/trace.

---

### 10 — `parser_comment_with_braces_ignored.tcl`

```tcl
proc tricky {args} {
    # This line has a { that should be ignored
    set x 1
}
```

**Expected:** One `ProcEntry`; `start_line=1`, `end_line=4`. The `{` on the comment line does NOT affect brace depth.

---

### 11 — `parser_proc_inside_if_block.tcl`

```tcl
if {$feature_enabled} {
    proc conditional_proc {} {
        return "maybe"
    }
}
```

**Expected:** Empty proc index. Debug-level log emitted noting skip. `conditional_proc` is inside a `CONTROL_FLOW` context.

---

### 12 — `parser_namespace_absolute_override.tcl`

```tcl
namespace eval ns {
    proc ::abs::foo {} { return "absolute" }
}
```

**Expected:** `ProcEntry(qualified_name="abs::foo", namespace_path="")`. Absolute proc name overrides namespace context.

---

### 13 — `parser_empty_proc_body_forms.tcl`

Three proc forms in one file:
```tcl
proc empty_one_line {} { }

proc empty_multiline {} {
}

proc whitespace_body {} {

}
```

**Expected per B-02 operational definition:**
- `empty_one_line`: `body_start_line = body_end_line = start_line`
- `empty_multiline`: `start_line = 3`, `end_line = 4`; body is zero lines (implementation must not crash)
- `whitespace_body`: `start_line = 6`, `end_line = 9`; `body_start_line = 7`, `body_end_line = 8`

---

### 14 — `parser_call_extraction.tcl`

```tcl
proc caller {} {
    direct_call arg1
    set result [bracketed_call arg2]
    return $result
}
```

**Expected call tokens:** `["direct_call", "bracketed_call"]`. Dynamic `$result` is not extracted.

---

### 15 — `parser_encoding_latin1_fallback.tcl`

Binary file containing Latin-1 encoded content (create via `tests/fixtures/create_latin1_fixture.py`).

```
# -*- coding: latin-1 -*-
proc legacy_proc {} {
    # Ü ö ä
    return "done"
}
```

**Expected:** One `ProcEntry(qualified_name="legacy_proc")`; WARNING diagnostic for Latin-1 fallback encoding.

---

### 16 — `parser_eda_complex_del_seq_rpt.tcl`

Representative Intel/Synopsys FEV-domain proc exercising the most challenging real-world patterns. Anchored to `tests/fixtures/fev_formality_real/default_fm_procs.tcl` and the production `del_seq_rpt` proc.

**Patterns covered:**

| Pattern | Spec Section |
|---|---|
| 8-field comment banner (#proc, #purpose, #usage, #Owner, #BU, #CTH release, #HSD) | §4.7 |
| `while { [gets ...] >= 0 }` body (CONTROL_FLOW context) | §4.4 |
| `if { [regexp {\pattern} ...] }` — `{pattern}` braces balanced, `\(` `\)` are escaped parens not braces | §3.1, §4.2 |
| `lappend` with backslash multi-line string continuation — no `{`/`}` in string content, brace depth unaffected | §3.2 |
| `foreach_in_collection inst_t $instances { ... }` — Synopsys EDA iterator, CONTROL_FLOW | §7.14 |
| `define_proc_attributes` DPA block with backslash continuation `\` | §4.6 |

**Expected:**

```
ProcEntry(
    canonical_name  = "parser_eda_complex_del_seq_rpt.tcl::del_seq_rpt",
    qualified_name  = "del_seq_rpt",
    start_line      = 10,           # proc keyword line
    end_line        = 57,           # closing }
    body_start_line = 11,
    body_end_line   = 56,
    comment_start_line = 1,
    comment_end_line   = 9,
    dpa_start_line  = 58,
    dpa_end_line    = 59,
)
```

No diagnostics expected. `iproc_msg`, `find_cfm`, `get_attribute`, `foreach_in_collection` are EDA/log calls and are not traced as user procs.

---

### 17 — `parser_eda_complex_get_hier_summary.tcl`

Representative proc for `puts`/`echo`-heavy result reporting with Synopsys/Cadence EDA commands.

**Patterns covered:**

| Pattern | Spec Section |
|---|---|
| 8-field comment banner | §4.7 |
| `tcl_set_command_name_echo off/on` — Synopsys EDA command, not a user proc | §5.5 |
| `redirect -variable varname "command string"` — string content NOT extracted as call | §5.1, §5.2 |
| Nested `if + foreach line [split $var "\n"]` — CONTROL_FLOW contexts | §4.4 |
| `vpxmode`, `vpx`, `tclmode` — Cadence LEC EDA commands; `TW-02 unresolved-proc-call` at trace time | §5.3.1 |
| `puts "..."`, `echo "..." >> fev_results.log` — §5.5 Level 3/4 suppression; `>>` is inert argument | §5.5 |
| `define_proc_attributes` DPA block with backslash continuation | §4.6 |

**Expected:**

```
ProcEntry(
    canonical_name  = "parser_eda_complex_get_hier_summary.tcl::get_hier_summary",
    qualified_name  = "get_hier_summary",
    start_line      = 10,
    end_line        = 55,
    body_start_line = 11,
    body_end_line   = 54,
    comment_start_line = 1,
    comment_end_line   = 9,
    dpa_start_line  = 56,
    dpa_end_line    = 57,
)
```

​No parse error diagnostics. `vpx`, `vpxmode`, `tclmode` produce `TW-02 unresolved-proc-call` at trace-expansion time (not parse time — brace structure is clean).

---

## Coverage Requirements

All 17 fixtures must pass before the Parser module (Stage 1) is declared complete and Stage 2 (Compiler) begins. Each fixture must be implemented as a parametrized test in `tests/unit/test_parser.py`. Golden output files live in `tests/golden/` as `parser__<fixture_name_without_parser_prefix>.json`.

Parser fixture Tcl files live in `tests/fixtures/edge_cases/`. The binary Latin-1 fixture (fixture 15) is generated into that directory by `tests/fixtures/create_latin1_fixture.py`.

---

## Real-World Fixtures

Real-world Tcl sources are kept alongside the fabricated parser fixtures so the integration suite (Stage 3+) can exercise the full pipeline end-to-end against content that matches production EDA domains.

| Fixture Directory | Source | Purpose |
|---|---|---|
| `tests/fixtures/fev_formality_real/` | Production Intel/Synopsys Formality (FEV) domain — `default_fm_procs.tcl`, `default_rules.fm.tcl`, `fev_fm_rtl2gate.tcl`, `fev_fm_gate2gate.tcl`, `*.stack`, `vars.tcl`, `utils/`, etc. | End-to-end acceptance test for `chopper trim --project` against a real domain layout; parser fixture 16 (`parser_eda_complex_del_seq_rpt.tcl`) is anchored on one proc from this tree. Determinism gate (NFR-03) runs against this directory by invoking two successive trims and comparing outputs byte-for-byte. |
| `tests/fixtures/mini_domain/` | Fabricated minimal domain | Smoke + first-trim / re-trim integration scenarios. |
| `tests/fixtures/namespace_domain/` | Fabricated namespace-heavy domain | Namespace resolution integration scenarios. |
| `tests/fixtures/tracing_domain/` | Fabricated tracing-scenario domain covering the six canonical P4 categories — `direct_call.tcl`, `bracketed_call.tcl`, `namespace_qualified.tcl`, `cycle.tcl`, `ambiguous.tcl`, `dynamic.tcl` plus the multi-file extras `diamond.tcl` and `cross_file.tcl` | Trace (P4) integration scenarios: BFS termination, frontier determinism, and one-fixture-per-diagnostic coverage — `direct_call` is the positive baseline; `bracketed_call` exercises `[cmd ...]` substitution; `namespace_qualified` covers absolute / relative / bare lookup; `cycle` forces `TW-04`; `ambiguous` forces `TW-01`; `dynamic` forces `TW-03`. |
| `tests/fixtures/edge_cases/domain_empty/` | Zero-`.tcl` domain | Validates statistics rendering on `files_out=0` / `procs_out=0` without division-by-zero (HANDOFF_REVIEW S-7). |
| `tests/fixtures/edge_cases/domain_single_empty_file/` | One `.tcl` file containing only a comment | Validates P2 empty `ProcEntry` list return and downstream trim_stats handling when `procs_in=0` (HANDOFF_REVIEW S-7). |
