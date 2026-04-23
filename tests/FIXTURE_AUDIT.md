# Chopper — Fixture Audit

> **Status:** Gap tracker for Stage 0 → Stage 1 handoff.
> **Purpose:** Map every named fixture under [`tests/fixtures/`](./fixtures/) to the pitfall, corner-case scenario, parser-spec rule, or tracing sub-category it covers. Identify gaps that must be filled before Stage 1 begins.

**Authority.** Subordinate to:

- [`docs/RISKS_AND_PITFALLS.md`](../docs/RISKS_AND_PITFALLS.md) — `P-01` through `P-36` pitfalls and `TC-01` through `TC-10` technical risks.
- [`docs/TCL_PARSER_SPEC.md`](../docs/TCL_PARSER_SPEC.md) — tokenization rules, proc detection algorithm, canonical-name vectors.
- [`tests/TESTING_STRATEGY.md`](TESTING_STRATEGY.md) — 30-row named integration-scenario catalog (§5).
- [`tests/FIXTURE_CATALOG.md`](FIXTURE_CATALOG.md) — canonical fixture index.

---

## 1. Fixture Directories

| Directory | Role | Status |
|---|---|---|
| [`fixtures/edge_cases/`](fixtures/edge_cases/) | Adversarial single-file Tcl inputs for parser unit tests | **Populated** — 17 fixtures (`parser_*.tcl`). See [§2](#2-edge-cases-parser-fixtures). |
| [`fixtures/mini_domain/`](fixtures/mini_domain/) | Minimal valid multi-file domain (3 procs, 2 files, 1 feature) for end-to-end integration | **Populated** (see `FIXTURE_CATALOG.md`). |
| [`fixtures/namespace_domain/`](fixtures/namespace_domain/) | Namespace resolution test cases across files | **Populated** (see `FIXTURE_CATALOG.md`). |
| [`fixtures/tracing_domain/`](fixtures/tracing_domain/) | BFS trace fixtures (direct, cycle, ambiguous, dynamic) | **Populated** — 6 fixtures (see [§3](#3-tracing-domain-fixtures)). |

Real-world Tcl pathologies from production Synopsys Formality flows (CRLF line endings, ``define_proc_attributes`` backslash continuation, column-0 proc bodies, banner-comment preservation through trimming) are embedded inline in [`unit/parser/test_service.py::TestRealWorldScenarios`](unit/parser/test_service.py) and [`unit/trimmer/test_proc_dropper.py`](unit/trimmer/test_proc_dropper.py) rather than kept as a bulk corpus fixture — this keeps the regression guards co-located with the code that enforces them.

Helpers at the root of `fixtures/`:

- [`create_latin1_fixture.py`](fixtures/create_latin1_fixture.py) — generates the Latin-1 encoded input for `PW-02`.
- [`gen_large_domain.py`](fixtures/gen_large_domain.py) — synthesizes the 10k-proc large-domain fixture for performance observation (`FD-09`).

---

## 2. Edge-Case Parser Fixtures

Each `.tcl` under `fixtures/edge_cases/` targets a pitfall (`P-xx`) or parser-spec rule. Canonical mapping:

| Fixture | Covers | Diagnostic | Spec § |
|---|---|---|---|
| `parser_basic_single_proc.tcl` | Baseline — `proc foo {} {}` | — | §4 |
| `parser_basic_multiple_procs.tcl` | Multi-proc file, index stability | — | §4 |
| `parser_empty_file.tcl` | Zero procs | — | §2.1.1 row 1 |
| `parser_empty_proc_body_forms.tcl` | `proc foo {} {}` vs `proc foo {args} {}` | — | §4.1 |
| `parser_brace_in_string_literal.tcl` | P-01: quote context inside braced body | — | §3.3.1, §3.3.2 |
| `parser_backslash_line_continuation.tcl` | P-02: `\\\n` continuation, line-count integrity | `PW-05` | §3.2 |
| `parser_comment_with_braces_ignored.tcl` | P-34: `#` comments with `{` / `}` inside | — | §3.4 |
| `parser_nested_namespace_accumulates.tcl` | P-03: nested `namespace eval` composition | — | §4.5 |
| `parser_namespace_reset_after_block.tcl` | P-03 corollary: namespace stack pops on `}` | — | §4.5.1 |
| `parser_namespace_absolute_override.tcl` | `::abs::name` overrides active namespace | — | §4.3 (rows 4–6) |
| `parser_proc_inside_if_block.tcl` | P-04: proc inside `if` body is NOT indexed | — | §4.4 |
| `parser_computed_proc_name_skipped.tcl` | P-04: `proc $name {...}` skip + warn | `PW-01` | §4.3 (row 6) |
| `parser_duplicate_proc_definition_error.tcl` | P-05: last-wins + `PE-01` | `PE-01` | §2.1.1 row 3 |
| `parser_encoding_latin1_fallback.tcl` | P-09: UTF-8 fail → Latin-1 retry | `PW-02` | §2 |
| `parser_call_extraction.tcl` | Call tokens extracted (bracketed, bare, namespace-qualified) | — | §5 |
| `parser_eda_complex_del_seq_rpt.tcl` | Real EDA-style proc with DPA + structured comments | `PI-01`, `PI-04` | §4.6, §4.7 |
| `parser_eda_complex_get_hier_summary.tcl` | Real EDA-style proc, complex body | — | §4.6 |

### 2.1 Pitfall coverage matrix

| Pitfall | Description | Fixture |
|---|---|---|
| P-01 | Quote context inside braced body | `parser_brace_in_string_literal.tcl` |
| P-02 | Backslash line continuation | `parser_backslash_line_continuation.tcl` |
| P-03 | Nested namespace resolution | `parser_nested_namespace_accumulates.tcl`, `parser_namespace_reset_after_block.tcl`, `parser_namespace_absolute_override.tcl` |
| P-04 | Computed / dynamic proc name | `parser_computed_proc_name_skipped.tcl`, `parser_proc_inside_if_block.tcl` |
| P-05 | Duplicate proc definition | `parser_duplicate_proc_definition_error.tcl` |
| P-09 | Non-UTF-8 encoding | `parser_encoding_latin1_fallback.tcl` |
| P-34 | Comment with embedded braces | `parser_comment_with_braces_ignored.tcl` |

### 2.2 Gaps to fill before Stage 1 freeze

The following pitfalls from [`RISKS_AND_PITFALLS.md`](../docs/RISKS_AND_PITFALLS.md) do not yet have a dedicated `edge_cases/` fixture. They are **Stage 1 prerequisites** — author them as part of Stage 1 kickoff:

| Pitfall | Gap | Suggested fixture filename |
|---|---|---|
| P-06 | Non-brace body (`proc foo "quoted body"`) | `parser_non_brace_body_skipped.tcl` (`PW-03`) |
| P-07 | Ambiguous short name across files | `parser_ambiguous_short_name_error.tcl` (`PE-03`) |
| P-08 | Deep nesting (>8 levels) | `parser_deep_nesting_warning.tcl` (`PW-08`) |
| P-10 | DPA block orphan (no preceding proc) | `parser_dpa_orphan.tcl` (`PI-04`) |
| P-11 | DPA name mismatch | `parser_dpa_name_mismatch.tcl` (`PW-11`) |
| P-12 | Multi-value `set` statement | `parser_multi_value_set.tcl` (`PW-06`) |
| P-13 | Dynamic array index | `parser_dynamic_array_index.tcl` (`PW-07`) |
| P-14 | Structured comment block extraction | `parser_structured_comment_block.tcl` (`PI-01`, `PI-03`) |
| P-15 | Proc call in string context | `parser_proc_call_in_string.tcl` (`PW-10`) |
| P-16 | Unbalanced braces | `parser_unbalanced_braces.tcl` (`PE-02`) |
| P-17 | Dynamic variable reference in call | `parser_dynamic_variable_ref.tcl` (`PW-09`) |
| P-18 | `namespace eval` with computed name | `parser_computed_namespace.tcl` (`PW-04`) |

**Acceptance criterion for Stage 1:** every row above has a fixture and a matching unit test asserting both the returned `ProcEntry` set and the emitted diagnostic set. Rows not listed here are covered by existing fixtures in §2 or are pure control-flow variants that the parser's state-machine tests already exercise.

---

## 3. Tracing-Domain Fixtures

`fixtures/tracing_domain/` drives the P4 BFS trace tests. Current coverage:

| Fixture | Scenario | BFS outcome | Diagnostic |
|---|---|---|---|
| `chain.tcl` | `a → b → c → d` linear | All four in PI+ when `a` is PI | — |
| `diamond.tcl` | `a → b; a → c; b → d; c → d` | `d` reached twice; BFS visited-set dedupes | — |
| `cycle.tcl` | `a → b → a` (and self-recursion) | Cycle terminator via visited-set | `TW-04 cycle-in-call-graph` |
| `dynamic.tcl` | `$cmd`, `eval`, `uplevel` call tokens | Unresolvable; not enqueued | `TW-03 dynamic-call-form` |
| `ns_calls.tcl` | Namespace-qualified calls (`ns::p`, bare `p`, `::abs::p`) | All three resolve to the same proc | — |
| `cross_file.tcl` | Call resolves to a proc in a different file | Cross-file edge in graph | — |

### 3.1 Gaps to fill before Stage 2 freeze

| Sub-scenario (review E3) | Gap | Suggested fixture |
|---|---|---|
| Ambiguous match — same short name in two namespaces | Not yet a dedicated fixture | `tracing_domain/ambiguous.tcl` + `utils_a.tcl` / `utils_b.tcl` with homonymous procs; expected `TW-01` |
| Unresolved — callee not in any parsed file | Covered partially by `dynamic.tcl`; add a pure-unresolved case | `tracing_domain/unresolved.tcl`; expected `TW-02` |
| `source` / `iproc_source` edge (reporting-only survival) | No fixture yet | `tracing_domain/source_edge.tcl` — a proc that `source`s a file not in `files.include`; assert the edge appears in `dependency_graph.json` with `kind: "source"` **and** the sourced file is NOT in the trimmed tree, **and** `VW-06 source-file-removed` fires at P6 |

These three fixtures plus an expected `dependency_graph.json` per-fixture are Stage 2 prerequisites.

---

## 4. Real-World Coverage (Inline)

Real production Synopsys Formality patterns are exercised via inline byte-literal snippets in the unit tests rather than a bulk fixture directory:

- [`unit/parser/test_service.py::TestRealWorldScenarios`](unit/parser/test_service.py) — CRLF line endings + ``define_proc_attributes`` backslash-continuation regression (was spuriously emitting `PI-04` + `PW-11`); column-0 proc bodies (as seen in the ``dangle_dont_verify_par`` production proc).
- [`unit/trimmer/test_proc_dropper.py`](unit/trimmer/test_proc_dropper.py) — structural-fidelity guarantee: after dropping one proc from a real multi-proc file, every kept proc (including its banner comment, blank lines, tab-indented or column-0 body) must appear byte-identical in the output.

Snippets are copied verbatim from production scripts and kept small and representative. When a new real-world pathology surfaces, add it as an inline constant next to an existing scenario — do not reintroduce a bulk corpus directory.

---

## 5. Tracking

This document is a living tracker. When a gap in §2.2 or §3.1 is filled:

1. Add the new fixture file under `fixtures/edge_cases/` or `fixtures/tracing_domain/`.
2. Move the row from the gap table into the populated table above.
3. Add the corresponding unit-test / integration-test reference.
4. Update [`tests/FIXTURE_CATALOG.md`](FIXTURE_CATALOG.md) if the fixture carries a canonical ID.

When every row in §2.2 is filled, Stage 1 is cleared for freeze. When every row in §3.1 is filled, Stage 2 is cleared for freeze.
