# Chopper -- Test Fixture Catalog

The single index of every fixture under [`tests/fixtures/`](fixtures/): what each one feeds, which rule or diagnostic it pins, and which known gaps have no fixture yet. Section references of the form `Sec.N` in Sec.2 point at the Tcl parser rules in [`technical_docs/IMPLEMENTATION.md`](../technical_docs/IMPLEMENTATION.md) (parser section); pitfall IDs (`P-xx`) point at the same document. Integration scenarios that consume these fixtures are catalogued in [`TESTING_STRATEGY.md`](TESTING_STRATEGY.md) Sec.5.

---

## 1. Fixture Directories

| Directory | Role | Consumers |
|---|---|---|
| [`fixtures/edge_cases/`](fixtures/edge_cases/) | Adversarial single-file Tcl inputs (`parser_*.tcl`, `indent_*.tcl`), two degenerate domains, and one non-Tcl stray-brace file | `tests/unit/parser/`, `tests/unit/trimmer/` -- see Sec.2 |
| [`fixtures/tracing_domain/`](fixtures/tracing_domain/) | One file per P4 trace category | Trace unit and integration tests -- see Sec.3 |
| [`fixtures/mini_domain/`](fixtures/mini_domain/) | Minimal valid multi-file domain with one feature | Smoke, first-trim and re-trim integration scenarios |
| [`fixtures/namespace_domain/`](fixtures/namespace_domain/) | Namespace-heavy domain | Cross-file namespace resolution scenarios |
| [`fixtures/stages_domain/`](fixtures/stages_domain/) | F3 domain: `base.json` only, `options.generate_stack: true`, stages `setup` -> `run_flow` -> `promote` chained via `load_from` / `dependencies` | `tests/integration/test_runner_localfs_e2e.py`: dry-run manifest shape; live trim emits one `<stage>.tcl` and one `<stage>.stack` per stage; generated stacks appear in the audit bundle |
| [`fixtures/header_domain/`](fixtures/header_domain/) | Generated-file header vectors (issue #30, P-49): `sta_setup.tcl` (shebang bootstrap with its own Intel header) and `rtl2rtl.tcl` (Intel header, no shebang) regenerated in place via `reference_file`; header-less `scripts/plain.steps`; a `standalone_stack` stage; feature `post_check` adding a stage from shebang script `scripts/post_check.tcl` | `test_runner_localfs_header_domain_keeps_owned_headers_on_top`: owned headers stay verbatim, header-less bodies get the Intel header on line 1, a feature marker never displaces a shebang (`options.insert_markers: true`; ARCHITECTURE Sec.3.11, Sec.6.6.1), and a re-trim is byte-stable |
| [`fixtures/overlay_replace/`](fixtures/overlay_replace/) | R1 ordered overlay: a feature excludes base `legacy.tcl` and includes `new.tcl` (`VW-21`) | Overlay integration tests |
| [`fixtures/overlay_remove_only/`](fixtures/overlay_remove_only/) | R1 ordered overlay: a feature removes a base file with no replacement (`VW-21`) | Overlay integration tests |
| [`fixtures/overlay_two_features_same_file/`](fixtures/overlay_two_features_same_file/) | R1 ordered overlay: `feature_a` proc-excludes a base whole file (WHOLE -> PROC_TRIM), `feature_b` re-includes -- last layer wins | Overlay integration tests |
| [`fixtures/overlay_no_op_exclude/`](fixtures/overlay_no_op_exclude/) | R1 ordered overlay: typo-class exclude that matches nothing (`VE-27`) | Overlay integration tests |
| [`fixtures/bug_reports/`](fixtures/bug_reports/) | Verbatim production snippets that reproduced filed bugs (`dpa_multiline.tcl`, `quoted_semicolon.tcl`, `regex_literals.tcl`, `switch_patterns.tcl`, `python_braces.py`); see the directory [`README.md`](fixtures/bug_reports/README.md) | `tests/unit/parser/test_bug_report_regressions.py` |

Helpers at the root of `fixtures/`:

- [`create_latin1_fixture.py`](fixtures/create_latin1_fixture.py) -- generates the Latin-1 encoded input for `PW-02` (fixture 15).
- [`gen_large_domain.py`](fixtures/gen_large_domain.py) -- synthesizes a 10k-proc domain for performance observation (`FD-09`).

---

## 2. Edge-Case Fixtures (`fixtures/edge_cases/`)

### 2.1 Parser fixture index

Every `parser_*.tcl` file is round-tripped by [`unit/parser/test_edge_case_fixtures.py`](unit/parser/test_edge_case_fixtures.py) (no crash, no hang, sorted output); fixtures 1-17 also carry the detailed expectations in Sec.2.4.

| # | Fixture File | Pitfall | Spec Sec. | Expected Outcome |
|---|---|---|---|---|
| 1 | `parser_basic_single_proc.tcl` | -- | Sec.4.1 | One `ProcEntry` with correct name, `start_line`, `end_line` |
| 2 | `parser_basic_multiple_procs.tcl` | -- | Sec.4.1 | Two or more `ProcEntry` records; no overlapping spans |
| 3 | `parser_empty_file.tcl` | -- | Sec.7.3 | Empty list -- no error, no warning |
| 4 | `parser_brace_in_string_literal.tcl` | P-01 | Sec.3.1, Sec.7.1 | Parse error diagnostic -- unbalanced brace inside braced proc body |
| 5 | `parser_backslash_line_continuation.tcl` | P-02 | Sec.3.2, Sec.7.2 | `ProcEntry` spans correct; original source line numbers preserved |
| 6 | `parser_nested_namespace_accumulates.tcl` | P-03 | Sec.4.5 | `qualified_name` = `a::b::deep_proc`; `namespace_path` = `a::b` |
| 7 | `parser_namespace_reset_after_block.tcl` | P-03 | Sec.4.5 | `p1.qualified_name = a::p1`, `p2.qualified_name = b::p2` after sequential blocks |
| 8 | `parser_computed_proc_name_skipped.tcl` | P-04 | Sec.4.3 | No `ProcEntry` for dynamic name; WARNING `PW-01` |
| 9 | `parser_duplicate_proc_definition_error.tcl` | -- | Sec.6.1, Sec.7.10 | ERROR `PE-01`; proc index uses last definition's span |
| 10 | `parser_comment_with_braces_ignored.tcl` | -- | Sec.3.4 | `ProcEntry` parsed correctly; brace in comment does not affect depth |
| 11 | `parser_proc_inside_if_block.tcl` | -- | Sec.4.4, Sec.7.8 | Proc inside `if` NOT indexed; debug log emitted |
| 12 | `parser_namespace_absolute_override.tcl` | -- | Sec.4.3 | `proc ::abs::foo` inside `namespace eval ns` resolves as `abs::foo` |
| 13 | `parser_empty_proc_body_forms.tcl` | -- | Sec.6.1 | One-line, empty-multiline and whitespace-only bodies; correct `body_start_line`/`body_end_line` for each |
| 14 | `parser_call_extraction.tcl` | -- | Sec.5.1 | Call extraction returns direct, bracketed and namespace-qualified call tokens |
| 15 | `parser_encoding_latin1_fallback.tcl` | -- | Sec.2, Sec.7.7 | Parses successfully with WARNING `PW-02` for Latin-1 fallback |
| 16 | `parser_eda_complex_del_seq_rpt.tcl` | -- | Sec.3.1, Sec.3.2, Sec.4.4, Sec.4.6, Sec.4.7, Sec.7.14 | One `ProcEntry`; correct DPA + comment spans; no parse errors despite regexp `{pattern}` and multi-line `lappend` backslash continuation |
| 17 | `parser_eda_complex_get_hier_summary.tcl` | P-36 | Sec.4.6, Sec.4.7, Sec.5.2, Sec.5.5 | One `ProcEntry`; `puts`/`echo`/EDA commands suppressed; `redirect -variable` string content not extracted; no parse errors |
| 18 | `parser_literal_quote_in_braced_word.tcl` | P-01a | Sec.1.3.3 | Literal `"` inside a brace word (`set q {"}`) stays literal; no false `PE-02` |
| 19 | `parser_braced_word_multi_quote_pairs.tcl` | P-01a | Sec.1.3.3 | Brace word with several quote pairs (`string map {" " ""}`) stays literal |
| 20 | `parser_braced_word_quote_space_quote.tcl` | P-01a | Sec.1.3.3 | Brace data word `{" "}` stays literal; lone `}` in a quoted word and `;`-in-quote (`TW-02`) regression guards |
| 21 | `parser_escaped_bracket_in_string.tcl` | P-46 | Sec.3.2 | Escaped `\[` inside a double-quoted string is not a command substitution |
| 22 | `parser_switch_brace_pattern.tcl` | P-47 | Sec.5.3 | Brace-delimited `switch` pattern containing `[...]` is opaque; no call candidates |
| 23 | `parser_multi_procs_with_sequential_dpa.tcl` | -- | Sec.4.6 | Several procs each followed by its own `define_proc_attributes`; every DPA binds to the preceding proc |

### 2.2 Formatter and non-parser fixtures

| Fixture | Covers |
|---|---|
| `indent_backslash_continuation.tcl` | P5c formatter: backslash-continuation indent, multi-continuation runs, escaped `\\` not treated as continuation |
| `indent_comment_braces.tcl` | P5c formatter: `#` comment lines with unmatched `{` / `}` and trailing `\` must not shift indent or propagate continuation |
| `indent_quoted_braces.tcl` | P5c formatter: unmatched `{` inside `"..."` and nested braces in `set_vclp_setup_commands` arguments must not affect brace counting |
| `domain_empty/` | Zero-`.tcl` domain: statistics render `files_out=0` / `procs_out=0` without division by zero |
| `domain_single_empty_file/` | One comment-only `.tcl` file: P2 returns an empty `ProcEntry` list and `trim_stats` handles `procs_in=0` |
| `non_tcl_python_stray_braces.py` | Issue #2 regression guard: non-Tcl files named in `files.include` / `procedures.*` are skipped by P2 (OOS-01, ARCHITECTURE Sec.1.3). The bytes would trigger a tokenizer `negative_depth` error if parsed; no `PE-02` may be emitted |

### 2.3 Pitfall coverage

| Pitfall | Behavior | Fixture(s) |
|---|---|---|
| P-01 | Quote context inside a braced body | 4 |
| P-01a | Literal / adjacent quotes inside brace words | 18, 19, 20 |
| P-02 | Backslash line continuation keeps source line numbers | 5 |
| P-03 | Nested `namespace eval` composition and stack pop | 6, 7 |
| P-04 | Computed proc name skipped with a warning | 8 |
| P-36 | No proc indexed inside a `foreach_in_collection` body | 17 |
| P-46 | Escaped `\[` is not a command substitution | 21 |
| P-47 | Brace-delimited `switch` patterns with `[...]` | 22 |
| P-48 | Standard Tcl builtins never reported as unresolved calls | inline -- `TestMissingBuiltins` in `unit/parser/test_call_extractor.py` |
| P-49 | Generated files keep an owned shebang / header on top | `header_domain/` |

### 2.4 Fixture detail (1-17)

#### 1 -- `parser_basic_single_proc.tcl`

```tcl
proc setup_tool {} {
    set x 1
    return $x
}
```

**Expected:** `[ProcEntry(canonical_name="parser_basic_single_proc.tcl::setup_tool", start_line=1, end_line=4, body_start_line=2, body_end_line=3)]`

---

#### 2 -- `parser_basic_multiple_procs.tcl`

```tcl
proc proc_a {} { return "a" }

proc proc_b {x} {
    return $x
}
```

**Expected:** Two entries; `proc_a.start_line=1`, `proc_a.end_line=1`; `proc_b.start_line=3`, `proc_b.end_line=5`. No overlapping spans.

---

#### 3 -- `parser_empty_file.tcl`

```tcl
# This file has no proc definitions
set x 1
```

**Expected:** `[]` -- no diagnostics, no errors.

---

#### 4 -- `parser_brace_in_string_literal.tcl`

```tcl
proc tricky {args} {
    set data "this has { an open brace"
    return $data
}
```

**Expected:** Parse error diagnostic. The `{` inside the quoted string inside a braced proc body still increments brace depth under Tcl Rule 6, making the body unbalanced.

---

#### 5 -- `parser_backslash_line_continuation.tcl`

```tcl
proc split_def \
    {arg1 arg2} \
    {
    return [list $arg1 $arg2]
}
```

**Expected:** One `ProcEntry`; `start_line=1` (original source, not joined), `end_line=6`. `body_start_line=4`, `body_end_line=5`.

---

#### 6 -- `parser_nested_namespace_accumulates.tcl`

```tcl
namespace eval a {
    namespace eval b {
        proc deep_proc {} { return "deep" }
    }
}
```

**Expected:** `ProcEntry(qualified_name="a::b::deep_proc", namespace_path="a::b")`.

---

#### 7 -- `parser_namespace_reset_after_block.tcl`

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

#### 8 -- `parser_computed_proc_name_skipped.tcl`

```tcl
proc ${prefix}_handler {} {
    return "dynamic"
}
```

**Expected:** No `ProcEntry`. WARNING diagnostic with code `PW-01 computed-proc-name`.

---

#### 9 -- `parser_duplicate_proc_definition_error.tcl`

```tcl
proc read_data {} {
    return "version 1"
}

proc read_data {} {
    return "version 2"
}
```

**Expected:** ERROR diagnostic code `PE-01 duplicate-proc-definition`. Proc index contains only the second definition (lines 5-7). File flagged as invalid for trim/trace.

---

#### 10 -- `parser_comment_with_braces_ignored.tcl`

```tcl
proc tricky {args} {
    # This line has a { that should be ignored
    set x 1
}
```

**Expected:** One `ProcEntry`; `start_line=1`, `end_line=4`. The `{` on the comment line does NOT affect brace depth.

---

#### 11 -- `parser_proc_inside_if_block.tcl`

```tcl
if {$feature_enabled} {
    proc conditional_proc {} {
        return "maybe"
    }
}
```

**Expected:** Empty proc index. Debug-level log emitted noting skip. `conditional_proc` is inside a `CONTROL_FLOW` context.

---

#### 12 -- `parser_namespace_absolute_override.tcl`

```tcl
namespace eval ns {
    proc ::abs::foo {} { return "absolute" }
}
```

**Expected:** `ProcEntry(qualified_name="abs::foo", namespace_path="")`. Absolute proc name overrides namespace context.

---

#### 13 -- `parser_empty_proc_body_forms.tcl`

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

#### 14 -- `parser_call_extraction.tcl`

```tcl
proc caller {} {
    direct_call arg1
    set result [bracketed_call arg2]
    return $result
}
```

**Expected call tokens:** `["direct_call", "bracketed_call"]`. Dynamic `$result` is not extracted.

---

#### 15 -- `parser_encoding_latin1_fallback.tcl`

Binary file containing Latin-1 encoded content (create via `tests/fixtures/create_latin1_fixture.py`).

```
# -*- coding: latin-1 -*-
proc legacy_proc {} {
    # U o a
    return "done"
}
```

**Expected:** One `ProcEntry(qualified_name="legacy_proc")`; WARNING diagnostic for Latin-1 fallback encoding.

---

#### 16 -- `parser_eda_complex_del_seq_rpt.tcl`

Representative Intel/Synopsys FEV-domain proc exercising the most challenging real-world patterns. Anchored on the production `del_seq_rpt` proc; additional real-world pathologies (CRLF + DPA backslash continuation, column-0 proc bodies) are exercised inline in [`tests/unit/parser/test_service.py::TestRealWorldScenarios`](unit/parser/test_service.py) and [`tests/unit/trimmer/test_proc_dropper.py`](unit/trimmer/test_proc_dropper.py) (structural-fidelity guarantee).

**Patterns covered:**

| Pattern | Spec Section |
|---|---|
| 8-field comment banner (#proc, #purpose, #usage, #Owner, #BU, #CTH release, #HSD) | Sec.4.7 |
| `while { [gets ...] >= 0 }` body (CONTROL_FLOW context) | Sec.4.4 |
| `if { [regexp {\pattern} ...] }` -- `{pattern}` braces balanced, `\(` `\)` are escaped parens not braces | Sec.3.1, Sec.4.2 |
| `lappend` with backslash multi-line string continuation -- no `{`/`}` in string content, brace depth unaffected | Sec.3.2 |
| `foreach_in_collection inst_t $instances { ... }` -- Synopsys EDA iterator, CONTROL_FLOW | Sec.7.14 |
| `define_proc_attributes` DPA block with backslash continuation `\` | Sec.4.6 |

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

#### 17 -- `parser_eda_complex_get_hier_summary.tcl`

Representative proc for `puts`/`echo`-heavy result reporting with Synopsys/Cadence EDA commands.

**Patterns covered:**

| Pattern | Spec Section |
|---|---|
| 8-field comment banner | Sec.4.7 |
| `tcl_set_command_name_echo off/on` -- Synopsys EDA command, not a user proc | Sec.5.5 |
| `redirect -variable varname "command string"` -- string content NOT extracted as call | Sec.5.1, Sec.5.2 |
| Nested `if + foreach line [split $var "\n"]` -- CONTROL_FLOW contexts | Sec.4.4 |
| `vpxmode`, `vpx`, `tclmode` -- Cadence LEC EDA commands; `TW-02 unresolved-proc-call` at trace time | Sec.5.3.1 |
| `puts "..."`, `echo "..." >> fev_results.log` -- Sec.5.5 Level 3/4 suppression; `>>` is inert argument | Sec.5.5 |
| `define_proc_attributes` DPA block with backslash continuation | Sec.4.6 |

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

No parse error diagnostics. `vpx`, `vpxmode`, `tclmode` produce `TW-02 unresolved-proc-call` at trace-expansion time (not parse time -- brace structure is clean).

**`foreach_in_collection` assertion (P-36).** The `get_hier_summary` proc body uses `foreach_in_collection` as a Synopsys EDA iterator. If the real fixture does not contain a `proc` keyword inside the `foreach_in_collection` body, a companion synthetic fixture `parser_foreach_in_collection_no_inner_proc.tcl` must be added that explicitly places a `proc` keyword inside the iterator body. Both fixtures must carry the explicit assertion:

```python
inner_procs = [e for e in result if "inner" in e.canonical_name or e.source_file == fixture_path]
assert len([e for e in result if e.canonical_name != "...::get_hier_summary"]) == 0, (
    "proc keyword inside foreach_in_collection body must NOT be indexed as a ProcEntry"
)
```

No proc defined inside a `foreach_in_collection` body (or any CONTROL_FLOW context) may appear in `ParseResult.index`.

---

## 3. Tracing-Domain Fixtures (`fixtures/tracing_domain/`)

One file per P4 trace category, so each `TW-*` code has exactly one positive fixture:

| Fixture | Scenario | Expected |
|---|---|---|
| `direct_call.tcl` | Bare `callee` inside a proc body | Resolved edge; positive baseline |
| `bracketed_call.tcl` | `[callee ...]` command substitution | Resolved edge |
| `namespace_qualified.tcl` | Absolute, relative and bare lookups of namespaced procs | All forms resolve to the same proc |
| `diamond.tcl` | `a -> b; a -> c; b -> d; c -> d` | `d` reached twice; the BFS visited-set dedupes |
| `cross_file.tcl` | Callee defined in a different file | Cross-file edge in `dependency_graph.json` |
| `cycle.tcl` | Mutual and self recursion | Terminates via the visited-set; `TW-04` |
| `ambiguous.tcl` | Same short name in two namespaces | `TW-01` |
| `dynamic.tcl` | `$cmd`, `eval`, `uplevel` call forms | Not enqueued; `TW-03` |

`TW-02` (unresolved call) and `VW-06` (sourced file removed) are asserted inline in the trace and validator unit tests rather than by a dedicated fixture file.

---

## 4. Real-World Coverage (Inline)

Production Synopsys Formality patterns are also exercised by small verbatim byte-literal snippets inside the unit tests, co-located with the code that enforces them:

- [`unit/parser/test_service.py::TestRealWorldScenarios`](unit/parser/test_service.py) -- CRLF line endings plus the `define_proc_attributes` backslash-continuation regression (previously emitted spurious `PI-04` + `PW-11`); column-0 proc bodies.
- [`unit/trimmer/test_proc_dropper.py`](unit/trimmer/test_proc_dropper.py) -- structural fidelity: after dropping one proc from a real multi-proc file, every kept proc (banner comment, blank lines, tab-indented or column-0 body) is byte-identical in the output.

Tokenizer and parser structural regressions must **also** be added as a dedicated `edge_cases/parser_*.tcl` fixture (the real snippet as-is) and referenced by a unit test, so the shared corpus keeps every real-world pathology.

---

## 5. Diagnostic Coverage and Open Gaps

Parser and trace codes with an emitter and a test: `PE-01`, `PE-02`, `PW-01`, `PW-02`, `PW-03` (inline in `unit/parser/test_proc_extractor.py`), `PW-04`, `PW-11`, `PI-04`, `TW-01`..`TW-04`, `VW-06`.

**Open gap -- registered but never emitted.** `PE-03`, `PW-05`, `PW-06`, `PW-07`, `PW-08`, `PW-09`, `PW-10`, `PI-01`, `PI-02` and `PI-03` are registered in [`technical_docs/DIAGNOSTIC_CODES.md`](../technical_docs/DIAGNOSTIC_CODES.md) but no code path in `src/chopper/` emits them (the parser maps only the extractor kinds in `parser/service.py` `_DIAG_CODE_MAP`). A fixture for one of these codes is meaningful only after an architecture-backed emitter exists; until then, do not author fixtures that assert them.

---

## 6. Coverage Requirements

- Every `edge_cases/parser_*.tcl` file is parametrized by [`unit/parser/test_edge_case_fixtures.py`](unit/parser/test_edge_case_fixtures.py), which also guards the corpus size (`>= 23`, the Sec.2.1 index) so an accidental deletion fails loudly. Fixtures 1-17 carry dedicated expectation tests under `tests/unit/parser/`.
- Parser expectations are asserted directly in unit tests, not by golden files; golden files cover the `.chopper/` audit artifacts only (see [`TESTING_STRATEGY.md`](TESTING_STRATEGY.md) Sec.7).
- The binary Latin-1 fixture is regenerated into `edge_cases/` by `fixtures/create_latin1_fixture.py`.

### Adding a fixture

1. Put the file in the directory that matches Sec.1 (adversarial parser input -> `edge_cases/parser_<behavior>.tcl`; trace category -> `tracing_domain/`; multi-file pipeline scenario -> a new `<scenario>_domain/`).
2. Add a row to the matching table in this file, citing the pitfall (`P-xx`) or diagnostic code it pins.
3. Add the unit or integration test that asserts both the returned objects and the emitted diagnostic set.
4. If the fixture backs a named integration scenario, cross-reference it from [`TESTING_STRATEGY.md`](TESTING_STRATEGY.md) Sec.5.
