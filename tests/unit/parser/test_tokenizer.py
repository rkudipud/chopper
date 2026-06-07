"""Unit tests for :mod:`chopper.parser.tokenizer`."""

from __future__ import annotations

import pytest

from chopper.parser.tokenizer import Token, TokenKind, tokenize


def _kinds(tokens: tuple[Token, ...]) -> list[TokenKind]:
    return [t.kind for t in tokens]


def _words(tokens: tuple[Token, ...]) -> list[tuple[str, int, bool]]:
    """Return (value, line_no, at_cmd_pos) triples for WORD tokens only."""
    return [(t.value, t.line_no, t.at_command_position) for t in tokens if t.kind == TokenKind.WORD]


class TestEmpty:
    def test_empty_string(self) -> None:
        r = tokenize("")
        assert r.tokens == ()
        assert r.errors == ()
        assert r.final_brace_depth == 0

    def test_whitespace_only(self) -> None:
        r = tokenize("   \t  ")
        assert r.tokens == ()
        assert r.final_brace_depth == 0

    def test_single_newline(self) -> None:
        r = tokenize("\n")
        assert _kinds(r.tokens) == [TokenKind.NEWLINE]


class TestWords:
    def test_single_word(self) -> None:
        r = tokenize("hello")
        assert _words(r.tokens) == [("hello", 1, True)]

    def test_two_words_same_line(self) -> None:
        r = tokenize("set x")
        assert _words(r.tokens) == [("set", 1, True), ("x", 1, False)]

    def test_words_across_lines(self) -> None:
        r = tokenize("set x\nputs $x")
        assert _words(r.tokens) == [
            ("set", 1, True),
            ("x", 1, False),
            ("puts", 2, True),
            ("$x", 2, False),
        ]

    def test_semicolon_resets_command_position(self) -> None:
        r = tokenize("a b; c d")
        words = _words(r.tokens)
        assert words == [("a", 1, True), ("b", 1, False), ("c", 1, True), ("d", 1, False)]


class TestBraces:
    def test_empty_braces(self) -> None:
        r = tokenize("{}")
        assert _kinds(r.tokens) == [TokenKind.LBRACE, TokenKind.RBRACE]
        # LBRACE depth shown is depth BEFORE open; RBRACE depth shown is after close.
        assert r.tokens[0].brace_depth == 0
        assert r.tokens[1].brace_depth == 0
        assert r.final_brace_depth == 0

    def test_nested_braces(self) -> None:
        r = tokenize("{ { } }")
        depths = [t.brace_depth for t in r.tokens if t.kind in (TokenKind.LBRACE, TokenKind.RBRACE)]
        # outer{, inner{, inner}, outer}  ->  0, 1, 1, 0
        assert depths == [0, 1, 1, 0]

    def test_proc_skeleton(self) -> None:
        r = tokenize("proc foo {} { return 1 }")
        kinds = _kinds(r.tokens)
        assert TokenKind.LBRACE in kinds
        assert TokenKind.RBRACE in kinds
        assert r.final_brace_depth == 0

    def test_escaped_open_brace_not_structural(self) -> None:
        # `\{` must be part of a word, not a structural open-brace.
        r = tokenize("a\\{b")
        assert _kinds(r.tokens) == [TokenKind.WORD]
        assert r.tokens[0].value == "a\\{b"

    def test_escaped_close_brace_not_structural(self) -> None:
        r = tokenize("a\\}b")
        assert _kinds(r.tokens) == [TokenKind.WORD]

    def test_double_backslash_brace_is_structural(self) -> None:
        # `\\{` -- even backslash count -> brace is NOT escaped.
        r = tokenize("\\\\{}")
        kinds = _kinds(r.tokens)
        assert TokenKind.LBRACE in kinds
        assert TokenKind.RBRACE in kinds


class TestBraceErrors:
    def test_unbalanced_close_reports_negative_depth(self) -> None:
        r = tokenize("}")
        assert any(e.kind == "negative_depth" for e in r.errors)

    def test_unclosed_open_reports_unclosed(self) -> None:
        r = tokenize("{")
        assert any(e.kind == "unclosed_braces" for e in r.errors)
        assert r.final_brace_depth == 1

    def test_balanced_no_errors(self) -> None:
        r = tokenize("proc foo {} { set x 1 }")
        assert r.errors == ()


class TestQuotedWords:
    def test_simple_quoted_word(self) -> None:
        r = tokenize('set x "hello world"')
        assert _words(r.tokens) == [("set", 1, True), ("x", 1, False), ('"hello world"', 1, False)]

    def test_brace_inside_quoted_word_is_inert(self) -> None:
        # Sec.3.3.1: pre-body quoted word with braces inside does NOT change depth.
        r = tokenize('proc foo "arg {arg2}" { body }')
        # Must see the quoted arg as ONE word, and the body braces as structural.
        word_values = [t.value for t in r.tokens if t.kind == TokenKind.WORD]
        assert '"arg {arg2}"' in word_values
        # brace depth returns to zero after body.
        assert r.final_brace_depth == 0

    def test_escaped_quote_inside_quoted_word(self) -> None:
        r = tokenize('set x "a \\" b"')
        word_values = [t.value for t in r.tokens if t.kind == TokenKind.WORD]
        assert '"a \\" b"' in word_values

    def test_quote_inside_braces_opens_quoted_word(self) -> None:
        # Tcl Endekas/Dodekalogue rule 5: a ``"`` at a word boundary opens
        # a quoted word at ANY brace depth. The contents of the quoted
        # word -- including unmatched ``{`` -- are LITERAL until the
        # matching ``"``. The example below is a well-formed proc whose
        # body contains a string literal carrying an unbalanced ``{``.
        # The outer braces remain balanced.
        # Bug repro anchor: ``TW-02_quoted_string_semicolon_misparse.md``.
        r = tokenize('proc foo {} { set x "text { more" }')
        assert r.final_brace_depth == 0
        assert r.errors == ()
        # The string literal is a single WORD token at depth 1.
        word_values = [t.value for t in r.tokens if t.kind == TokenKind.WORD]
        assert '"text { more"' in word_values

    def test_literal_quote_in_braced_data_word_self_recovers(self) -> None:
        # Real-world idiom from Synopsys Formality default_fm_procs.tcl:
        # ``set q {"}`` is a single-character data word containing the
        # literal ``"``. Tcl Endekas rule 6: contents of ``{...}`` are
        # literal bytes. The opening ``"`` must NOT be treated as a
        # quoted-word opener; otherwise the matching ``}`` is consumed
        # as part of the phantom quote and the brace counter desyncs.
        # Mechanism: the ``"`` is suppressed at open time because its
        # immediately preceding byte is an unescaped structural ``{``
        # (literal-data-word exception), so no quoted word is ever
        # entered and the ``}`` is processed structurally.
        r = tokenize('set q {"}')
        assert r.final_brace_depth == 0
        assert r.errors == ()

    def test_literal_quote_in_braced_word_inside_proc_body(self) -> None:
        # Same idiom embedded in a proc body (depth 1 enclosing scope).
        # The fix must work at every depth, not just at depth 0.
        src = 'proc foo {} {\n    set q {"}\n    set x ""\n}'
        r = tokenize(src)
        assert r.final_brace_depth == 0
        assert r.errors == ()

    def test_braced_regex_with_balanced_quotes(self) -> None:
        # ``{".*"}`` is a literal data word containing the bytes ``".*"``.
        # The opening ``"`` is the first byte inside ``{`` so the
        # quoted-word opener is suppressed (literal-data-word exception).
        # The matching ``"`` then accumulates as part of a regular WORD
        # and the ``}`` closes the brace structurally. Brace count stays
        # balanced.
        r = tokenize('regexp {".*"} $line')
        assert r.final_brace_depth == 0
        assert r.errors == ()

    def test_braced_word_with_multiple_quote_pairs(self) -> None:
        # Tcl LRM rule 5: a ``"`` opens a quoted word only at a true word
        # boundary. After the closing ``"`` of a prior quoted pair, a
        # following ``"`` cannot open a new quoted word -- the prior
        # implementation did, swallowing the closing ``}`` of the
        # enclosing braced data word.
        # Real-world repro: ``string map {" " ""}`` from Intel Caliber
        # ``run_caliber.tcl:418``. Validated with ``tclsh info complete``.
        r = tokenize('set k [string map {" " ""} $x]')
        assert r.final_brace_depth == 0
        assert r.errors == ()

    def test_braced_word_with_two_quoted_regex_fragments(self) -> None:
        # ``{".*" ".*"}`` -- two adjacent quoted regex fragments inside
        # one braced data word. The internal whitespace doesn't matter;
        # the closing ``}`` must be reached without phantom quote state.
        r = tokenize('regexp {".*" ".*"} $line')
        assert r.final_brace_depth == 0
        assert r.errors == ()

    def test_string_map_newline_to_space_idiom(self) -> None:
        # Normalization idiom: ``string map {"\n" " "}``. The escaped
        # newline inside the quoted word and the multi-pair brace
        # structure together exercised the old opener bug.
        r = tokenize(r'set t [string map {"\n" " "} $s]')
        assert r.final_brace_depth == 0
        assert r.errors == ()

    def test_list_literal_of_quoted_elements(self) -> None:
        # Four adjacent quoted elements as a braced list literal.
        r = tokenize('set xs {"a" "b" "c" "d"}')
        assert r.final_brace_depth == 0
        assert r.errors == ()

    def test_close_quote_then_open_quote_without_separator_is_literal(self) -> None:
        # LRM rule 5 invariant: ``""""`` (no separators) cannot be two
        # back-to-back quoted words. The first pair opens & closes; the
        # next ``"`` has a ``"`` immediately before it and therefore
        # cannot open a new quoted word. The remaining bytes accumulate
        # as a literal WORD. This is the precise condition that fixed
        # the multi-quote-pair brace bug.
        r = tokenize('set x ""extra')
        # Tokenizer must not desync; no errors, depth unchanged.
        assert r.final_brace_depth == 0
        assert r.errors == ()

    def test_real_world_fixture_intel_caliber_patterns(self) -> None:
        # Bulk fixture lifted verbatim from intel_caliber/run_caliber.tcl.
        # Captures the production patterns that triggered PE-02 before
        # the LRM rule-5 fix landed. New tokenizer scenarios from real
        # domains should be appended to this fixture as they are found.
        from pathlib import Path

        fixture = (
            Path(__file__).resolve().parents[2] / "fixtures" / "edge_cases" / "parser_braced_word_multi_quote_pairs.tcl"
        )
        text = fixture.read_text(encoding="utf-8")
        r = tokenize(text)
        assert r.final_brace_depth == 0, f"final_brace_depth={r.final_brace_depth} (expected 0); errors={r.errors}"
        assert r.errors == ()

    def test_braced_word_quote_space_quote_is_literal(self) -> None:
        # Bug repro: brace data word ``{" "}`` (quote, space, quote). The
        # second ``"`` is preceded by a space (a word-boundary byte) but
        # must stay literal because the whole brace word is literal data.
        # Before the level-scoped literal-data-word fix this opened a
        # phantom quoted word that swallowed the closing ``}`` and raised
        # a false PE-02 unbalanced-braces. Real-world shape:
        # ``regsub -all { \s+} $x {" "} y``.
        src = 'proc p {} {\n    regsub -all { \\s+} $x {" "} y\n}\n'
        r = tokenize(src)
        assert r.final_brace_depth == 0, f"final_brace_depth={r.final_brace_depth}; errors={r.errors}"
        assert r.errors == ()

    def test_braced_word_quote_space_quote_minimal(self) -> None:
        # Minimal standalone shapes that must all self-balance with no errors.
        for src in ('set y {" "}\n', 'set y {""}\n', 'set q {"x"}\n', 'set y {a "b" c}\n'):
            r = tokenize(src)
            assert r.final_brace_depth == 0, f"{src!r}: depth={r.final_brace_depth}"
            assert r.errors == (), f"{src!r}: errors={r.errors}"

    def test_lone_close_brace_in_quoted_word_stays_literal(self) -> None:
        # Regression guard for the {" "} fix: a lone ``}`` INSIDE a real
        # quoted word (opened at a script-context word boundary) is
        # literal and must NOT be treated as a structural close. Holds at
        # depth 0 and inside a proc body (depth 1).
        for src in ('puts "}"\n', 'proc p {} {\n    puts "end: }"\n}\n'):
            r = tokenize(src)
            assert r.final_brace_depth == 0, f"{src!r}: depth={r.final_brace_depth}"
            assert r.errors == (), f"{src!r}: errors={r.errors}"

    def test_quoted_semicolon_stays_literal_in_proc_body(self) -> None:
        # TW-02 pin: ``;`` inside a quoted word in a proc body is literal,
        # not a command separator. The {" "} fix must not regress this.
        r = tokenize('proc p {} {\n    puts "a; b"\n}\n')
        assert r.final_brace_depth == 0
        assert r.errors == ()
        word_values = [t.value for t in r.tokens if t.kind == TokenKind.WORD]
        assert '"a; b"' in word_values

    def test_real_world_fixture_quote_space_quote(self) -> None:
        # Fixture covering the ``{" "}`` family plus the lone-``}``-in-quote
        # and TW-02 regression guards. New real-domain tokenizer scenarios
        # for this family should be appended to this fixture.
        from pathlib import Path

        fixture = (
            Path(__file__).resolve().parents[2] / "fixtures" / "edge_cases" / "parser_braced_word_quote_space_quote.tcl"
        )
        text = fixture.read_text(encoding="utf-8")
        r = tokenize(text)
        assert r.final_brace_depth == 0, f"final_brace_depth={r.final_brace_depth} (expected 0); errors={r.errors}"
        assert r.errors == ()


class TestComments:
    def test_simple_comment(self) -> None:
        r = tokenize("# this is a comment\n")
        assert _kinds(r.tokens) == [TokenKind.COMMENT, TokenKind.NEWLINE]

    def test_leading_whitespace_comment(self) -> None:
        r = tokenize("    # indented\n")
        assert TokenKind.COMMENT in _kinds(r.tokens)

    def test_braces_in_comment_are_inert(self) -> None:
        # Sec.3.4 rule 7: braces inside comments do not change depth.
        r = tokenize("# { unbalanced {\nset x 1")
        assert r.final_brace_depth == 0
        assert r.errors == ()

    def test_hash_after_word_is_part_of_word(self) -> None:
        # `#` is only a comment at command position. `set x #hash` -- the
        # `#hash` is the third word, NOT a comment.
        r = tokenize("set x #hash")
        word_values = [t.value for t in r.tokens if t.kind == TokenKind.WORD]
        assert "#hash" in word_values
        assert TokenKind.COMMENT not in _kinds(r.tokens)

    def test_hash_after_semicolon_is_comment(self) -> None:
        r = tokenize("set x 1 ; # trailing comment")
        assert TokenKind.COMMENT in _kinds(r.tokens)

    def test_comment_inside_proc_body(self) -> None:
        r = tokenize("proc foo {} {\n    # body comment\n    set x 1\n}")
        comments = [t for t in r.tokens if t.kind == TokenKind.COMMENT]
        assert len(comments) == 1
        assert "body comment" in comments[0].value
        assert r.final_brace_depth == 0


class TestBackslashContinuation:
    def test_continuation_preserves_command(self) -> None:
        # Sec.3.2: `\<newline>` is a line continuation -- does NOT reset cmd pos.
        r = tokenize("proc \\\nfoo {} {}")
        words = _words(r.tokens)
        assert ("proc", 1, True) in words
        # `foo` is on line 2 but is NOT at command position (continuation).
        assert ("foo", 2, False) in words

    def test_continuation_line_numbers_advance(self) -> None:
        r = tokenize("a \\\nb")
        word_lines = [(t.value, t.line_no) for t in r.tokens if t.kind == TokenKind.WORD]
        assert ("a", 1) in word_lines
        assert ("b", 2) in word_lines

    def test_continuation_brace_depth_unchanged(self) -> None:
        # Continuation must not affect depth tracking.
        r = tokenize("{ \\\n}")
        assert r.final_brace_depth == 0
        assert r.errors == ()

    def test_double_backslash_newline_is_not_continuation(self) -> None:
        # Even count -> not an escape -> regular newline ends the command.
        r = tokenize("a \\\\\nb")
        words = _words(r.tokens)
        # `b` must be at command position -- newline was real.
        assert ("b", 2, True) in words


class TestCommandPosition:
    def test_first_word_on_each_line(self) -> None:
        r = tokenize("a b c\nd e\nf")
        words = _words(r.tokens)
        # First word of each line is at command position.
        first_on_each_line = {(value, line): at_cmd for value, line, at_cmd in words}
        assert first_on_each_line[("a", 1)] is True
        assert first_on_each_line[("b", 1)] is False
        assert first_on_each_line[("d", 2)] is True
        assert first_on_each_line[("f", 3)] is True

    def test_lbrace_at_command_position_flag(self) -> None:
        # `{` on a line of its own is at command position (first token).
        r = tokenize("{\n}")
        lbrace = next(t for t in r.tokens if t.kind == TokenKind.LBRACE)
        assert lbrace.at_command_position is True


class TestEdgeCases:
    def test_unclosed_quote_reports_error(self) -> None:
        # An unclosed `"` is a structural failure; surface as unclosed_braces
        # so the service can map it to PE-02.
        r = tokenize('set x "unterminated')
        assert any(e.kind == "unclosed_braces" for e in r.errors)

    def test_multiline_quoted_word(self) -> None:
        # A quoted word may span lines; line numbers advance inside.
        r = tokenize('set x "line1\nline2"')
        word_values = [t.value for t in r.tokens if t.kind == TokenKind.WORD]
        assert '"line1\nline2"' in word_values

    def test_continuation_at_cmd_pos_preserved(self) -> None:
        # Continuation between `;` and next command preserves cmd-pos.
        r = tokenize("a ; \\\nb")
        # `b` is the first non-whitespace after `;` + continuation -> cmd pos.
        words = _words(r.tokens)
        assert ("b", 2, True) in words

    def test_escaped_backslash_before_newline_not_continuation(self) -> None:
        # `\\\n` means escaped-backslash followed by real newline.
        r = tokenize("a\\\\\nb")
        words = _words(r.tokens)
        # Two separate commands; `b` is cmd pos on line 2.
        assert ("b", 2, True) in words

    def test_semicolon_inside_braces_still_emits_token(self) -> None:
        # IMPLEMENTATION.md (parser section) Sec.1.3.0 + Sec.1.3.4 rule 3: brace-delimited blocks are
        # treated as scripts. `;` inside braces is a command terminator
        # and `#` at the resulting cmd-pos activates a comment.
        r = tokenize("proc f {} { a ; b }")
        # Semicolon appears at brace_depth == 2 (inside the proc body).
        semis = [t for t in r.tokens if t.kind == TokenKind.SEMICOLON]
        assert len(semis) == 1
        assert semis[0].brace_depth == 1

    def test_comment_after_semicolon_inside_braces_activates(self) -> None:
        # Sec.3.4 rule 3: `#` at cmd-pos inside braces is a comment.
        r = tokenize("proc f {} { a ; # c\nb }")
        comments = [t for t in r.tokens if t.kind == TokenKind.COMMENT]
        assert len(comments) == 1
        assert comments[0].brace_depth == 1

    def test_dangling_backslash_at_eof(self) -> None:
        # A lone `\` at EOF (no following char) must not crash and must
        # not emit a continuation. It is accumulated as part of the word.
        r = tokenize("abc\\")
        # No errors expected for this structural non-issue.
        assert r.errors == ()

    def test_escaped_open_brace_in_word_stays_word(self) -> None:
        # `abc\{def` -- the `{` is escaped; the whole thing is one word.
        r = tokenize("abc\\{def")
        words = _words(r.tokens)
        assert words == [("abc\\{def", 1, True)]
        assert r.final_brace_depth == 0


class TestDeterminism:
    @pytest.mark.parametrize(
        "source",
        [
            "",
            "proc foo {} { return 1 }",
            "namespace eval ns {\n  proc p {} {}\n}",
            "set x 1; set y 2",
            "# only a comment\n",
        ],
    )
    def test_same_input_same_output(self, source: str) -> None:
        a = tokenize(source)
        b = tokenize(source)
        assert a == b
