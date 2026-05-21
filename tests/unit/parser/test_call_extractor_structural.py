"""Direct branch tests for :mod:`chopper.parser.call_extractor_structural`."""

from __future__ import annotations

from chopper.parser.call_extractor_structural import (
    classify_and_handle,
    is_string_match,
    mark_opaque_arg_braces,
    mark_switch_pattern_words,
    scan_command_range,
)
from chopper.parser.tokenizer import Token, TokenKind, tokenize


def _tok(kind: TokenKind, value: str, *, depth: int = 0, cmd: bool = False) -> Token:
    return Token(kind=kind, value=value, line_no=1, brace_depth=depth, at_command_position=cmd)


def test_scan_command_range_accepts_empty_range() -> None:
    skip: set[int] = set()

    scan_command_range((), 0, 0, skip)

    assert skip == set()


def test_string_match_marks_pattern_braces_opaque() -> None:
    tokens = tokenize("string match {helper_*} $value\n").tokens
    skip: set[int] = set()

    classify_and_handle(tokens, "string", 1, len(tokens), 0, skip)

    assert skip
    assert any(tokens[i].value == "helper_*" for i in skip)


def test_code_brace_command_ignores_unmatched_body_brace() -> None:
    tokens = (
        _tok(TokenKind.WORD, "if", cmd=True),
        _tok(TokenKind.LBRACE, "{", depth=0),
        _tok(TokenKind.WORD, "helper", depth=1, cmd=True),
    )
    skip: set[int] = set()

    classify_and_handle(tokens, "if", 1, len(tokens), 0, skip)

    assert skip == set()


def test_opaque_arg_with_unmatched_brace_advances_without_marking() -> None:
    tokens = (_tok(TokenKind.WORD, "regexp", cmd=True), _tok(TokenKind.LBRACE, "{", depth=0))
    skip: set[int] = set()

    mark_opaque_arg_braces(tokens, 1, len(tokens), 0, skip)

    assert skip == set()


def test_switch_without_body_brace_and_unclosed_body_are_ignored() -> None:
    no_body = tokenize("switch $mode default run_default\n").tokens
    unclosed_body = (
        _tok(TokenKind.WORD, "switch", cmd=True),
        _tok(TokenKind.WORD, "$mode"),
        _tok(TokenKind.LBRACE, "{", depth=0),
        _tok(TokenKind.WORD, "default", depth=1, cmd=True),
    )

    skip: set[int] = set()
    mark_switch_pattern_words(no_body, 1, len(no_body), 0, skip)
    mark_switch_pattern_words(unclosed_body, 1, len(unclosed_body), 0, skip)

    assert skip == set()


def test_is_string_match_returns_false_without_words() -> None:
    tokens = (_tok(TokenKind.NEWLINE, "\n"),)

    assert is_string_match(tokens, 0, len(tokens)) is False
