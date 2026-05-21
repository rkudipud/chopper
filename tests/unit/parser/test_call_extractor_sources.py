"""Unit tests for :mod:`chopper.parser.call_extractor_sources`."""

from __future__ import annotations

from chopper.parser.call_extractor_sources import extract_source_path_with_indices, is_dynamic_path, strip_quotes
from chopper.parser.tokenizer import TokenKind, tokenize


def _extract(command: str, *, keyword: str = "source") -> tuple[str | None, set[int]]:
    result = tokenize(command)
    tokens = result.tokens
    keyword_idx = next(i for i, token in enumerate(tokens) if token.kind is TokenKind.WORD and token.value == keyword)
    return extract_source_path_with_indices(tokens, keyword_idx, len(tokens), keyword)


def test_source_flags_are_skipped_before_literal_path() -> None:
    path, consumed = _extract("source -echo -verbose common/helpers.tcl\n")

    assert path == "common/helpers.tcl"
    assert len(consumed) == 3


def test_iproc_source_flags_are_skipped_before_literal_path() -> None:
    path, consumed = _extract("iproc_source -file -optional hooks/setup.tcl\n", keyword="iproc_source")

    assert path == "hooks/setup.tcl"
    assert len(consumed) == 3


def test_newline_terminates_command_before_path() -> None:
    path, consumed = _extract("source -quiet\ncommon/helpers.tcl\n")

    assert path is None
    assert consumed == {1}


def test_semicolon_terminates_command_before_path() -> None:
    path, consumed = _extract("source -quiet; common/helpers.tcl\n")

    assert path is None
    assert consumed == {1}


def test_dynamic_source_path_is_consumed_but_not_returned() -> None:
    path, consumed = _extract("source $SCRIPT_ROOT/common.tcl\n")

    assert path is None
    assert consumed == {1}


def test_bracket_dynamic_source_path_is_consumed_but_not_returned() -> None:
    path, consumed = _extract("source [file join common helpers.tcl]\n")

    assert path is None
    assert consumed == {1}


def test_quoted_and_braced_literals_are_stripped() -> None:
    assert _extract('source "common/helpers.tcl"\n')[0] == "common/helpers.tcl"
    assert _extract("source {common/helpers.tcl}\n")[0] == "common/helpers.tcl"


def test_no_path_before_limit_returns_none() -> None:
    path, consumed = _extract("source -nocomplain")

    assert path is None
    assert consumed == {1}


def test_dynamic_path_helper_detects_variables_and_brackets() -> None:
    assert is_dynamic_path("$root/a.tcl") is True
    assert is_dynamic_path("[file join a.tcl]") is True
    assert is_dynamic_path("a[file join b].tcl") is True
    assert is_dynamic_path("literal/a.tcl") is False


def test_strip_quotes_leaves_unwrapped_values_unchanged() -> None:
    assert strip_quotes("literal.tcl") == "literal.tcl"
    assert strip_quotes("{not-closed") == "{not-closed"
