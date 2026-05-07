"""Unit tests for :mod:`chopper.parser.proc_extractor`."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.parser import proc_extractor as proc_extractor_module
from chopper.parser.proc_extractor import (
    ExtractorDiagnostic,
    extract_procs,
)
from chopper.parser.tokenizer import TokenKind, tokenize

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _procs_by_short(source: str, path: str = "u.tcl") -> dict[str, object]:
    """Extract procs and return a dict keyed by ``short_name`` for easy assertions."""
    r = extract_procs(Path(path), source)
    return {p.short_name: p for p in r.procs}


def _diag_kinds(source: str, path: str = "u.tcl") -> list[str]:
    return [d.kind for d in extract_procs(Path(path), source).diagnostics]


# ---------------------------------------------------------------------------
# Basic proc detection
# ---------------------------------------------------------------------------


class TestBasic:
    def test_single_proc_one_line(self) -> None:
        # §6.2 edge case 1: one-line proc → body spans same line.
        src = "proc foo {} { return 1 }\n"
        by = _procs_by_short(src)
        assert "foo" in by
        p = by["foo"]
        assert p.start_line == 1  # type: ignore[attr-defined]
        assert p.end_line == 1  # type: ignore[attr-defined]
        assert p.body_start_line == 1  # type: ignore[attr-defined]
        assert p.body_end_line == 1  # type: ignore[attr-defined]
        assert p.canonical_name == "u.tcl::foo"  # type: ignore[attr-defined]
        assert p.qualified_name == "foo"  # type: ignore[attr-defined]
        assert p.namespace_path == ""  # type: ignore[attr-defined]

    def test_multi_line_proc_body(self) -> None:
        src = "proc bar {a b} {\n    return $a\n}\n"
        by = _procs_by_short(src)
        p = by["bar"]
        assert p.start_line == 1  # type: ignore[attr-defined]
        assert p.end_line == 3  # type: ignore[attr-defined]
        assert p.body_start_line == 2  # type: ignore[attr-defined]
        assert p.body_end_line == 2  # type: ignore[attr-defined]

    def test_multiple_procs(self) -> None:
        src = "proc a {} {}\nproc b {} {}\nproc c {} {}\n"
        by = _procs_by_short(src)
        assert list(by.keys()) == ["a", "b", "c"]
        for name, line in zip(("a", "b", "c"), (1, 2, 3)):
            assert by[name].start_line == line  # type: ignore[attr-defined]

    def test_empty_file(self) -> None:
        r = extract_procs(Path("empty.tcl"), "")
        assert r.procs == ()
        assert r.diagnostics == ()

    def test_no_procs_just_code(self) -> None:
        r = extract_procs(Path("u.tcl"), "set x 1\nset y 2\n")
        assert r.procs == ()
        assert r.diagnostics == ()

    def test_proc_sorted_by_start_line(self) -> None:
        # Even if procs are found out of order, the returned tuple is sorted.
        src = "proc z {} {}\nproc a {} {}\nproc m {} {}\n"
        r = extract_procs(Path("u.tcl"), src)
        starts = [p.start_line for p in r.procs]
        assert starts == sorted(starts)


# ---------------------------------------------------------------------------
# §6.2 body-line edge cases
# ---------------------------------------------------------------------------


class TestBodyEdgeCases:
    def test_empty_multiline_body(self) -> None:
        # §6.2: `proc foo {} {` / `}` on separate lines → body_start > body_end.
        src = "proc foo {} {\n}\n"
        p = _procs_by_short(src)["foo"]
        assert p.start_line == 1  # type: ignore[attr-defined]
        assert p.end_line == 2  # type: ignore[attr-defined]
        assert p.body_start_line == 2  # type: ignore[attr-defined]
        assert p.body_end_line == 1  # type: ignore[attr-defined]
        # Empty-body signal: body_start_line > body_end_line.
        assert p.body_start_line > p.body_end_line  # type: ignore[attr-defined]

    def test_whitespace_only_body(self) -> None:
        # §6.2 edge case 3: body has only blank lines.
        src = "proc foo {} {\n\n\n}\n"
        p = _procs_by_short(src)["foo"]
        assert p.start_line == 1  # type: ignore[attr-defined]
        assert p.end_line == 4  # type: ignore[attr-defined]
        assert p.body_start_line == 2  # type: ignore[attr-defined]
        assert p.body_end_line == 3  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Namespace resolution (§4.3 / §4.3.1 test vectors)
# ---------------------------------------------------------------------------


class TestNamespaceResolution:
    def test_file_root_bare_name(self) -> None:
        p = _procs_by_short("proc helper {} {}\n", path="utils.tcl")["helper"]
        assert p.canonical_name == "utils.tcl::helper"  # type: ignore[attr-defined]
        assert p.qualified_name == "helper"  # type: ignore[attr-defined]

    def test_single_namespace(self) -> None:
        src = "namespace eval a {\nproc helper {} {}\n}\n"
        p = _procs_by_short(src, path="utils.tcl")["helper"]
        assert p.canonical_name == "utils.tcl::a::helper"  # type: ignore[attr-defined]
        assert p.qualified_name == "a::helper"  # type: ignore[attr-defined]
        assert p.namespace_path == "a"  # type: ignore[attr-defined]

    def test_nested_namespace(self) -> None:
        src = "namespace eval a {\n    namespace eval b {\n        proc helper {} {}\n    }\n}\n"
        p = _procs_by_short(src, path="utils.tcl")["helper"]
        assert p.canonical_name == "utils.tcl::a::b::helper"  # type: ignore[attr-defined]
        assert p.qualified_name == "a::b::helper"  # type: ignore[attr-defined]
        assert p.namespace_path == "a::b"  # type: ignore[attr-defined]

    def test_absolute_at_file_root(self) -> None:
        p = _procs_by_short("proc ::abs::x {} {}\n", path="utils.tcl")["x"]
        assert p.canonical_name == "utils.tcl::abs::x"  # type: ignore[attr-defined]

    def test_absolute_overrides_namespace(self) -> None:
        # §4.3.1 row 5: absolute name inside namespace.
        src = "namespace eval a {\nproc ::abs::x {} {}\n}\n"
        p = _procs_by_short(src, path="utils.tcl")["x"]
        assert p.canonical_name == "utils.tcl::abs::x"  # type: ignore[attr-defined]

    def test_absolute_overrides_nested_namespace(self) -> None:
        # §4.3.1 row 6.
        src = "namespace eval a {\n    namespace eval b {\nproc ::abs::c::x {} {}\n    }\n}\n"
        p = _procs_by_short(src, path="utils.tcl")["x"]
        assert p.canonical_name == "utils.tcl::abs::c::x"  # type: ignore[attr-defined]

    def test_subdirectory_path(self) -> None:
        p = _procs_by_short("proc foo {} {}\n", path="common/helpers.tcl")["foo"]
        assert p.canonical_name == "common/helpers.tcl::foo"  # type: ignore[attr-defined]

    def test_subdirectory_with_namespace(self) -> None:
        src = "namespace eval ns {\nproc foo {} {}\n}\n"
        p = _procs_by_short(src, path="common/helpers.tcl")["foo"]
        assert p.canonical_name == "common/helpers.tcl::ns::foo"  # type: ignore[attr-defined]

    def test_deep_path_and_nested_namespace(self) -> None:
        src = "namespace eval p {\n    namespace eval q {\nproc r {} {}\n    }\n}\n"
        p = _procs_by_short(src, path="sub/dir/f.tcl")["r"]
        assert p.canonical_name == "sub/dir/f.tcl::p::q::r"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Context suppression (§4.4)
# ---------------------------------------------------------------------------


class TestContextSuppression:
    def test_proc_inside_if_block_skipped(self) -> None:
        # §4.4: `proc` inside `if` body → not recognised.
        src = "if { $cond } {\n    proc skipped {} {}\n}\n"
        by = _procs_by_short(src)
        assert by == {}

    def test_proc_inside_namespace_eval_recognised(self) -> None:
        # §4.4: `proc` inside `namespace eval` → recognised.
        src = "namespace eval ns {\n    proc kept {} {}\n}\n"
        by = _procs_by_short(src)
        assert "kept" in by

    @pytest.mark.parametrize("keyword", ["for", "foreach", "while", "catch"])
    def test_proc_inside_control_flow_skipped(self, keyword: str) -> None:
        src = f"{keyword} {{x}} {{\n    proc inner {{}} {{}}\n}}\n"
        assert _procs_by_short(src) == {}

    def test_nested_proc_not_recognised(self) -> None:
        # §4.4: proc inside proc body → not recognised.
        src = "proc outer {} {\n    proc inner {} {}\n}\n"
        by = _procs_by_short(src)
        assert "outer" in by
        assert "inner" not in by


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


class TestDiagnostics:
    def test_computed_proc_name_pw01(self) -> None:
        # §4.3 row 7 / fixture 8.
        src = "proc ${prefix}_foo {} {}\n"
        r = extract_procs(Path("u.tcl"), src)
        assert r.procs == ()
        assert any(d.kind == "computed-proc-name" for d in r.diagnostics)

    def test_computed_proc_name_with_bracket(self) -> None:
        src = "proc [make_name] {} {}\n"
        r = extract_procs(Path("u.tcl"), src)
        assert r.procs == ()
        assert any(d.kind == "computed-proc-name" for d in r.diagnostics)

    def test_duplicate_proc_pe01(self) -> None:
        # §6.3: same short_name twice → PE-01 at last definition's line;
        # last definition survives.
        src = "proc dup {} { return 1 }\nproc dup {} { return 2 }\n"
        r = extract_procs(Path("u.tcl"), src)
        dup_diags = [d for d in r.diagnostics if d.kind == "duplicate-proc-definition"]
        assert len(dup_diags) == 1
        assert dup_diags[0].line_no == 2  # last definition's start line
        # Only one ProcEntry survives; it's the last.
        assert len(r.procs) == 1
        assert r.procs[0].start_line == 2

    def test_non_brace_body_pw03(self) -> None:
        # §7.4: body is a quoted word, not a brace block.
        src = 'proc foo args "return hello"\n'
        r = extract_procs(Path("u.tcl"), src)
        assert r.procs == ()
        assert any(d.kind == "non-brace-body" for d in r.diagnostics)

    def test_computed_namespace_pw04_passthrough(self) -> None:
        # §4.5 rule 7: computed namespace name surfaces as PW-04 diagnostic.
        src = "namespace eval $var {\n    proc inside {} {}\n}\n"
        r = extract_procs(Path("u.tcl"), src)
        assert any(d.kind == "computed-namespace-name" for d in r.diagnostics)
        # Procs inside the unresolved namespace are NOT indexed.
        assert not any(p.short_name == "inside" for p in r.procs)

    def test_tokenizer_errors_short_circuit(self) -> None:
        # §3.0: structural brace errors → parse_file returns []. The
        # extractor produces no procs and no diagnostics of its own; the
        # service layer maps the tokenizer errors to PE-02.
        src = "proc foo {} { { unclosed\n"
        r = extract_procs(Path("u.tcl"), src)
        assert r.procs == ()
        assert r.diagnostics == ()


# ---------------------------------------------------------------------------
# Comment banner (§4.7)
# ---------------------------------------------------------------------------


class TestCommentBanner:
    def test_banner_detected(self) -> None:
        src = (
            "########################################################################\n"
            "#proc       : foo\n"
            "#purpose    : demo\n"
            "########################################################################\n"
            "proc foo {} {}\n"
        )
        p = _procs_by_short(src)["foo"]
        assert p.comment_start_line == 1  # type: ignore[attr-defined]
        assert p.comment_end_line == 4  # type: ignore[attr-defined]

    def test_no_banner(self) -> None:
        p = _procs_by_short("proc foo {} {}\n")["foo"]
        assert p.comment_start_line is None  # type: ignore[attr-defined]
        assert p.comment_end_line is None  # type: ignore[attr-defined]

    def test_blank_line_breaks_banner(self) -> None:
        # Blank line above proc → no banner attached.
        src = "# a comment\n\nproc foo {} {}\n"
        p = _procs_by_short(src)["foo"]
        assert p.comment_start_line is None  # type: ignore[attr-defined]

    def test_non_comment_breaks_banner(self) -> None:
        # Code above proc → no banner.
        src = "set x 1\nproc foo {} {}\n"
        p = _procs_by_short(src)["foo"]
        assert p.comment_start_line is None  # type: ignore[attr-defined]

    def test_banner_stops_at_code(self) -> None:
        # Comment above, then code, then more comments, then proc. Only the
        # contiguous block immediately above proc is the banner.
        src = "# early header\nset x 1\n# proc: foo\nproc foo {} {}\n"
        p = _procs_by_short(src)["foo"]
        assert p.comment_start_line == 3  # type: ignore[attr-defined]
        assert p.comment_end_line == 3  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# DPA detection (§4.6)
# ---------------------------------------------------------------------------


class TestDPA:
    def test_dpa_attached(self) -> None:
        src = 'proc read_libs {} {\n    puts hello\n}\ndefine_proc_attributes read_libs -info "read libs"\n'
        p = _procs_by_short(src)["read_libs"]
        assert p.dpa_start_line == 4  # type: ignore[attr-defined]
        assert p.dpa_end_line == 4  # type: ignore[attr-defined]

    def test_dpa_multi_line_continuation(self) -> None:
        src = 'proc read_libs {} {\n    puts hi\n}\ndefine_proc_attributes read_libs \\\n   -info "multi line"\n'
        p = _procs_by_short(src)["read_libs"]
        assert p.dpa_start_line == 4  # type: ignore[attr-defined]
        assert p.dpa_end_line == 5  # type: ignore[attr-defined]

    def test_dpa_multiline_define_args_consumes_full_braced_block(self) -> None:
        fixture = (
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "edge_cases"
            / "parser_multi_procs_with_sequential_dpa.tcl"
        )
        source = fixture.read_text(encoding="utf-8")
        by = _procs_by_short(source, path=fixture.name)

        assert by["pc_eco_set_dont_touch_annotated_delay"].dpa_start_line == 14  # type: ignore[attr-defined]
        assert by["pc_eco_set_dont_touch_annotated_delay"].dpa_end_line == 19  # type: ignore[attr-defined]
        assert by["pc_eco_set_size_cell_restrictions"].dpa_start_line == 26  # type: ignore[attr-defined]
        assert by["pc_eco_set_size_cell_restrictions"].dpa_end_line == 31  # type: ignore[attr-defined]
        assert by["pc_eco_remove_attr_name_size_cell_restrictions"].dpa_start_line == 38  # type: ignore[attr-defined]
        assert by["pc_eco_remove_attr_name_size_cell_restrictions"].dpa_end_line == 43  # type: ignore[attr-defined]

    def test_dpa_with_blank_lines(self) -> None:
        # Up to 3 blank lines permitted between proc and DPA.
        src = 'proc foo {} {}\n\n\ndefine_proc_attributes foo -info "x"\n'
        p = _procs_by_short(src)["foo"]
        assert p.dpa_start_line == 4  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        ("blanks", "expected_dpa_line", "should_attach"),
        [
            (0, 2, True),  # immediate DPA on the next line
            (1, 3, True),  # one blank line between
            (2, 4, True),  # two blank lines between
            (3, 5, True),  # three blank lines (boundary; spec §1.4.6 rule 2)
            (4, None, False),  # four blank lines exceeds the window — no DPA
        ],
    )
    def test_dpa_blank_line_tolerance_boundary(
        self, blanks: int, expected_dpa_line: int | None, should_attach: bool
    ) -> None:
        """`technical_docs/IMPLEMENTATION.md` §1.4.6 rule 2: DPA association
        permits up to three blank lines between the proc close and the
        ``define_proc_attributes`` block. Four or more blank lines breaks
        the window and the DPA is not attached.
        """
        gap = "\n" * blanks
        src = f'proc foo {{}} {{}}\n{gap}define_proc_attributes foo -info "x"\n'
        p = _procs_by_short(src)["foo"]
        if should_attach:
            assert p.dpa_start_line == expected_dpa_line  # type: ignore[attr-defined]
        else:
            assert p.dpa_start_line is None  # type: ignore[attr-defined]

    def test_dpa_comment_line_breaks_association(self) -> None:
        # §4.6 rule 2: comment lines between proc and DPA break the link.
        src = 'proc foo {} {}\n# unrelated comment\ndefine_proc_attributes foo -info "x"\n'
        p = _procs_by_short(src)["foo"]
        # No DPA attached — the comment broke the link.
        assert p.dpa_start_line is None  # type: ignore[attr-defined]

    def test_dpa_name_mismatch_pw11(self) -> None:
        # §4.6: DPA name does not match preceding proc → PW-11.
        src = 'proc foo {} {}\ndefine_proc_attributes bar -info "wrong name"\n'
        r = extract_procs(Path("u.tcl"), src)
        assert any(d.kind == "dpa-name-mismatch" for d in r.diagnostics)
        p = {pp.short_name: pp for pp in r.procs}["foo"]
        assert p.dpa_start_line is None

    def test_dpa_orphan_pi04(self) -> None:
        # §4.6: define_proc_attributes with no preceding proc → PI-04.
        src = 'define_proc_attributes nothing -info "orphan"\n'
        r = extract_procs(Path("u.tcl"), src)
        orphans = [d for d in r.diagnostics if d.kind == "dpa-orphan"]
        assert len(orphans) == 1

    def test_dpa_matches_namespaced_proc(self) -> None:
        # §4.6 name-match uses qualified_name. DPA must immediately follow
        # the proc (no intervening namespace close), so place it inside the
        # namespace block.
        src = 'namespace eval ns {\nproc foo {} {}\ndefine_proc_attributes ns::foo -info "x"\n}\n'
        p = _procs_by_short(src)["foo"]
        assert p.dpa_start_line == 3  # type: ignore[attr-defined]

    def test_dpa_block_without_trailing_continuations_still_consumes_braces(self) -> None:
        src = "proc foo {} {}\ndefine_proc_attributes foo -define_args {\n  {-clock Clock name}\n}\nproc bar {} {}\n"
        p = _procs_by_short(src)["foo"]
        assert p.dpa_start_line == 2  # type: ignore[attr-defined]
        assert p.dpa_end_line == 4  # type: ignore[attr-defined]

    def test_define_proc_arguments_is_treated_like_define_proc_attributes(self) -> None:
        src = "proc foo {} {}\ndefine_proc_arguments ::foo -define_args {{-x value}}\n"
        p = _procs_by_short(src)["foo"]
        assert p.dpa_start_line == 2  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Continuation and quoted args (§7.2, §3.3.1)
# ---------------------------------------------------------------------------


class TestContinuation:
    def test_proc_split_by_continuation(self) -> None:
        src = "proc split \\\n    {a b} \\\n    {\n    return $a\n}\n"
        by = _procs_by_short(src)
        assert "split" in by
        # start_line is the `proc` keyword line.
        assert by["split"].start_line == 1  # type: ignore[attr-defined]

    def test_quoted_args_word(self) -> None:
        # §3.3.1: `proc foo "arg1 {arg2}" { body }` — quoted args are a
        # single word; body follows.
        src = 'proc foo "arg1 {arg2}" { return 1 }\n'
        by = _procs_by_short(src)
        assert "foo" in by


class TestPrivateHelperBranches:
    def test_peek_name_token_skips_newlines_and_handles_missing_word(self) -> None:
        tokens = tokenize("proc\nfoo {} {}\n").tokens
        proc_idx = next(i for i, token in enumerate(tokens) if token.kind is TokenKind.WORD and token.value == "proc")

        assert proc_extractor_module._peek_name_token(tokens, proc_idx).value == "foo"

        missing = tokenize("proc\n{} {}\n").tokens
        proc_idx = next(i for i, token in enumerate(missing) if token.kind is TokenKind.WORD and token.value == "proc")
        assert proc_extractor_module._peek_name_token(missing, proc_idx) is None

    def test_scan_proc_layout_returns_none_when_name_is_missing(self) -> None:
        tokens = tokenize("proc\n").tokens
        proc_idx = next(i for i, token in enumerate(tokens) if token.kind is TokenKind.WORD and token.value == "proc")

        assert proc_extractor_module._scan_proc_layout(tokens, proc_idx, base_depth=0) is None

    def test_scan_proc_layout_malformed_args_and_body_branches(self) -> None:
        cases = (
            "proc foo\n",
            "proc foo\n;\n",
            "proc foo {} body\n",
            "proc foo {} {\n",
        )
        for source in cases:
            tokens = tokenize(source).tokens
            proc_idx = next(
                i for i, token in enumerate(tokens) if token.kind is TokenKind.WORD and token.value == "proc"
            )
            assert proc_extractor_module._scan_proc_layout(tokens, proc_idx, base_depth=0) is None

    def test_consume_brace_block_rejects_non_lbrace_and_unclosed_block(self) -> None:
        word_tokens = tokenize("proc foo {} {}\n").tokens
        word_idx = next(i for i, token in enumerate(word_tokens) if token.kind is TokenKind.WORD)
        assert proc_extractor_module._consume_brace_block(word_tokens, word_idx, base_depth=0) is None

        unclosed = tokenize("{ still open").tokens
        lbrace_idx = next(i for i, token in enumerate(unclosed) if token.kind is TokenKind.LBRACE)
        assert proc_extractor_module._consume_brace_block(unclosed, lbrace_idx, base_depth=0) is None

    def test_detect_non_brace_body_defensive_branches(self) -> None:
        diagnostic = proc_extractor_module._detect_non_brace_body(
            tokenize("proc\nfoo {} body\n").tokens,
            0,
            base_depth=0,
        )
        assert diagnostic == ExtractorDiagnostic(kind="non-brace-body", line_no=2, detail="foo")

        for source in ("proc\n", "proc foo\n", "proc foo\n;\n", "proc foo {}\n"):
            tokens = tokenize(source).tokens
            proc_idx = next(
                i for i, token in enumerate(tokens) if token.kind is TokenKind.WORD and token.value == "proc"
            )
            assert proc_extractor_module._detect_non_brace_body(tokens, proc_idx, base_depth=0) is None

    def test_build_entry_reports_computed_name_when_called_directly(self) -> None:
        tokens = tokenize("proc $computed {} {}\n").tokens
        proc_idx = next(i for i, token in enumerate(tokens) if token.kind is TokenKind.WORD and token.value == "proc")
        layout = proc_extractor_module._scan_proc_layout(tokens, proc_idx, base_depth=0)
        assert layout is not None

        entry, diagnostics = proc_extractor_module._build_entry(
            layout=layout,
            tokens=tokens,
            lines=["proc $computed {} {}\n"],
            source_file=Path("u.tcl"),
            namespace_path="",
        )

        assert entry is None
        assert diagnostics == [ExtractorDiagnostic(kind="computed-proc-name", line_no=1, detail="$computed")]

    def test_scan_dpa_block_end_returns_last_line_for_unclosed_payload(self) -> None:
        lines = ["define_proc_attributes foo -define_args {\n", "    {-x value}\n"]

        assert proc_extractor_module._scan_dpa_block_end(lines, 0) == 1

    def test_line_continuation_helper_distinguishes_odd_and_even_backslashes(self) -> None:
        assert proc_extractor_module._line_ends_with_continuation("cmd \\") is True
        assert proc_extractor_module._line_ends_with_continuation("cmd \\\\") is False
        assert proc_extractor_module._line_ends_with_continuation("cmd") is False

    def test_update_tcl_brace_depth_ignores_quotes_and_escaped_braces(self) -> None:
        depth, in_quotes = proc_extractor_module._update_tcl_brace_depth('puts "{" \\{ {', 0, False)

        assert depth == 1
        assert in_quotes is False

    def test_extract_dpa_proc_name_handles_absolute_and_empty_lines(self) -> None:
        assert proc_extractor_module._extract_dpa_proc_name("define_proc_attributes ::ns::foo -info x") == "ns::foo"
        assert proc_extractor_module._extract_dpa_proc_name("::bare -info x") == "bare"
        assert proc_extractor_module._extract_dpa_proc_name("") == ""


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    @pytest.mark.parametrize(
        "source",
        [
            "proc foo {} {}\nproc bar {} {}\n",
            "namespace eval a {\n    proc p {} {}\n}\n",
            '# banner\nproc foo {} {}\ndefine_proc_attributes foo -info "x"\n',
        ],
    )
    def test_same_input_same_output(self, source: str) -> None:
        r1 = extract_procs(Path("u.tcl"), source)
        r2 = extract_procs(Path("u.tcl"), source)
        assert r1 == r2

    def test_diagnostics_sorted(self) -> None:
        # Diagnostics come out sorted by (line_no, kind, detail).
        src = 'proc dup {} {}\nproc dup {} {}\ndefine_proc_attributes orphan -info "x"\n'
        diags = extract_procs(Path("u.tcl"), src).diagnostics
        keys = [(d.line_no, d.kind) for d in diags]
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Invariant cross-checks — ensure ProcEntry round-trips through its __post_init__
# ---------------------------------------------------------------------------


class TestProcEntryInvariants:
    def test_calls_is_empty_in_stage_1d(self) -> None:
        # Stage 1e: calls is now populated. For a body with only builtin-
        # suppressed tokens (see TCL_BUILTINS in call_extractor), calls is
        # still empty. This test documents that suppression works end-to-end.
        src = "proc foo {} { set x 1; set y 2 }\n"
        p = _procs_by_short(src)["foo"]
        assert p.calls == ()  # type: ignore[attr-defined]
        assert p.source_refs == ()  # type: ignore[attr-defined]

    def test_dedupe_diag_unique_per_short(self) -> None:
        src = "proc dup {} {}\nproc dup {} {}\nproc dup {} {}\n"
        r = extract_procs(Path("u.tcl"), src)
        dup_diags = [d for d in r.diagnostics if d.kind == "duplicate-proc-definition"]
        # One PE-01 per duplicate group, not one per occurrence.
        assert len(dup_diags) == 1
        assert isinstance(dup_diags[0], ExtractorDiagnostic)
