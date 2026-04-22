"""Unit tests for :mod:`chopper.parser.namespace_tracker`."""

from __future__ import annotations

import pytest

from chopper.parser.namespace_tracker import (
    ContextKind,
    NamespaceTracker,
    TrackerDiagnostic,
)
from chopper.parser.tokenizer import Token, TokenKind, tokenize


def _feed_all(source: str) -> NamespaceTracker:
    """Run ``tokenize`` and feed every token into a fresh tracker."""
    t = NamespaceTracker()
    for tok in tokenize(source).tokens:
        t.feed(tok)
    return t


class TestEmpty:
    def test_initial_state(self) -> None:
        t = NamespaceTracker()
        assert t.depth == 0
        assert t.top.kind is ContextKind.FILE_ROOT
        assert t.namespace_stack == ()
        assert t.namespace_path == ""
        assert t.can_define_proc() is True
        assert t.diagnostics == ()

    def test_empty_source(self) -> None:
        t = _feed_all("")
        assert t.top.kind is ContextKind.FILE_ROOT
        assert t.depth == 0


class TestNamespaceEval:
    def test_single_namespace_eval(self) -> None:
        src = "namespace eval a {\n}\n"
        t = NamespaceTracker()
        tokens = list(tokenize(src).tokens)
        # Feed up to (but not including) the closing RBRACE.
        rbrace_index = next(i for i, tok in enumerate(tokens) if tok.kind is TokenKind.RBRACE)
        for tok in tokens[:rbrace_index]:
            t.feed(tok)
        assert t.top.kind is ContextKind.NAMESPACE_EVAL
        assert t.namespace_stack == ("a",)
        assert t.namespace_path == "a"
        assert t.can_define_proc() is True
        # Now feed the RBRACE and the tail — namespace pops.
        for tok in tokens[rbrace_index:]:
            t.feed(tok)
        assert t.top.kind is ContextKind.FILE_ROOT
        assert t.namespace_stack == ()

    def test_nested_namespace_eval(self) -> None:
        # Newline between outer `{` and inner `namespace` is what establishes
        # command position for the inner keyword.
        src = "namespace eval a {\n    namespace eval b {\n"
        t = _feed_all(src)
        assert t.namespace_stack == ("a", "b")
        assert t.namespace_path == "a::b"
        assert t.top.kind is ContextKind.NAMESPACE_EVAL

    def test_sequential_namespace_blocks_reset(self) -> None:
        # §4.5.1 worked example: namespace must reset completely between blocks.
        src = "namespace eval a {\n    proc p1 {} { return 1 }\n}\nnamespace eval b {\n"
        t = _feed_all(src)
        # After closing `a`, opening `b` → stack should be just ["b"], not ["a", "b"].
        assert t.namespace_stack == ("b",)

    def test_absolute_namespace_stripped(self) -> None:
        t = _feed_all("namespace eval ::abs {\n")
        assert t.namespace_stack == ("abs",)

    def test_computed_namespace_name_emits_diagnostic(self) -> None:
        # §4.5 rule 7 — computed name is not parsed; PW-04 is emitted.
        t = _feed_all("namespace eval $prefix_ns {\n")
        diags = t.diagnostics
        assert len(diags) == 1
        assert diags[0] == TrackerDiagnostic(
            kind="computed-namespace-name",
            line_no=1,
            detail="$prefix_ns",
        )
        # Body context is OTHER, not NAMESPACE_EVAL — procs inside suppressed.
        assert t.top.kind is ContextKind.OTHER
        assert t.can_define_proc() is False
        # No namespace was pushed.
        assert t.namespace_stack == ()

    def test_computed_namespace_with_brackets(self) -> None:
        t = _feed_all("namespace eval [compute_name] {\n")
        assert t.top.kind is ContextKind.OTHER
        assert t.namespace_stack == ()
        assert any(d.kind == "computed-namespace-name" for d in t.diagnostics)


class TestControlFlow:
    @pytest.mark.parametrize(
        "keyword",
        ["if", "for", "foreach", "foreach_in_collection", "while", "switch", "catch", "eval"],
    )
    def test_control_flow_keyword_pushes_context(self, keyword: str) -> None:
        # Sticky behaviour: both the condition brace and the body brace are
        # labeled CONTROL_FLOW (the command persists until newline/semicolon).
        src = f"{keyword} {{cond}} {{\n"
        t = _feed_all(src)
        assert t.top.kind is ContextKind.CONTROL_FLOW
        assert t.can_define_proc() is False

    def test_control_flow_pops_after_close(self) -> None:
        src = "if { $x } { } \n"
        t = _feed_all(src)
        assert t.top.kind is ContextKind.FILE_ROOT
        assert t.depth == 0


class TestProcBodyMarking:
    def test_mark_proc_body_opening(self) -> None:
        # Simulate Stage 1d's cooperation: before the body LBRACE is fed,
        # the extractor calls mark_proc_body_opening(). The resulting frame
        # is PROC_BODY, not OTHER.
        t = NamespaceTracker()
        # Fabricate a minimal token stream: `proc foo {}` args-word first
        # (OTHER), then the body opener (PROC_BODY via mark).
        t.feed(Token(kind=TokenKind.WORD, value="proc", line_no=1, brace_depth=0, at_command_position=True))
        t.feed(Token(kind=TokenKind.WORD, value="foo", line_no=1, brace_depth=0, at_command_position=False))
        # Args word: `{}` — opens and closes at depth 0.
        t.feed(Token(kind=TokenKind.LBRACE, value="{", line_no=1, brace_depth=0, at_command_position=False))
        assert t.top.kind is ContextKind.OTHER  # args block
        t.feed(Token(kind=TokenKind.RBRACE, value="}", line_no=1, brace_depth=1, at_command_position=False))
        # Now the extractor marks the upcoming body LBRACE.
        t.mark_proc_body_opening()
        t.feed(Token(kind=TokenKind.LBRACE, value="{", line_no=1, brace_depth=0, at_command_position=False))
        assert t.top.kind is ContextKind.PROC_BODY
        assert t.can_define_proc() is False

    def test_mark_cleared_on_lbrace(self) -> None:
        t = NamespaceTracker()
        t.mark_proc_body_opening()
        t.feed(Token(kind=TokenKind.LBRACE, value="{", line_no=1, brace_depth=0, at_command_position=True))
        assert t.top.kind is ContextKind.PROC_BODY
        # Second LBRACE — without a new mark — is OTHER.
        t.feed(Token(kind=TokenKind.LBRACE, value="{", line_no=1, brace_depth=1, at_command_position=False))
        assert t.top.kind is ContextKind.OTHER


class TestOtherContext:
    def test_anonymous_brace_is_other(self) -> None:
        # `set x {...}` — the `{` opens an OTHER frame, procs inside not
        # recognised.
        t = _feed_all("set x {\n")
        assert t.top.kind is ContextKind.OTHER
        assert t.can_define_proc() is False

    def test_namespace_eval_inside_control_flow_still_pushes_ns(self) -> None:
        # Inside `if { ... }` body, a `namespace eval` pattern still triggers
        # detection — though whether that's semantically correct for Tcl is
        # academic; the spec §4.4 says procs inside CONTROL_FLOW are not
        # recognised, but the namespace stack itself tracks syntactic nesting.
        # This test documents current behaviour.
        src = "if { $x } {\n    namespace eval inner {\n"
        t = _feed_all(src)
        # Inside the `if` body, we see `namespace eval inner` → NS push.
        assert "inner" in t.namespace_stack


class TestCommandReset:
    def test_newline_resets_pending_opener(self) -> None:
        # `namespace eval a\n{` — newline between name and `{` breaks the
        # sliding window; the `{` is then OTHER, not NAMESPACE_EVAL.
        src = "namespace eval a\n{\n"
        t = _feed_all(src)
        assert t.top.kind is ContextKind.OTHER
        assert t.namespace_stack == ()

    def test_semicolon_resets_pending_opener(self) -> None:
        src = "namespace eval a ; {\n"
        t = _feed_all(src)
        assert t.top.kind is ContextKind.OTHER

    def test_comment_breaks_pending_opener(self) -> None:
        src = "namespace eval a\n# comment\n{\n"
        t = _feed_all(src)
        assert t.top.kind is ContextKind.OTHER


class TestDepthTracking:
    def test_depth_matches_tokenizer(self) -> None:
        src = "a { b { c } d }"
        t = _feed_all(src)
        assert t.depth == 0

    def test_intermediate_depth_queryable(self) -> None:
        t = NamespaceTracker()
        t.feed(Token(kind=TokenKind.LBRACE, value="{", line_no=1, brace_depth=0, at_command_position=True))
        assert t.depth == 1
        t.feed(Token(kind=TokenKind.LBRACE, value="{", line_no=1, brace_depth=1, at_command_position=False))
        assert t.depth == 2


class TestErrorHandling:
    def test_unbalanced_rbrace_raises(self) -> None:
        # An RBRACE at depth 0 must raise — callers are expected to abort
        # on tokenizer errors before feeding the tracker.
        t = NamespaceTracker()
        with pytest.raises(ValueError, match="negative_depth"):
            t.feed(Token(kind=TokenKind.RBRACE, value="}", line_no=1, brace_depth=0, at_command_position=False))

    def test_file_root_never_popped(self) -> None:
        # Feeding a balanced stream leaves FILE_ROOT intact.
        t = _feed_all("proc p {} {}\n")
        assert t.top.kind is ContextKind.FILE_ROOT
        assert len([f for f in t._stack if f.kind is ContextKind.FILE_ROOT]) == 1  # noqa: SLF001
