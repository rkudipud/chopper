"""Unit tests for :mod:`chopper.core.globs`."""

from __future__ import annotations

from chopper.core.globs import glob_to_regex


def test_pattern_without_double_star_returns_none() -> None:
    assert glob_to_regex("lib/*.tcl") is None


def test_double_star_slash_matches_zero_or_more_segments() -> None:
    regex = glob_to_regex("**/*.tcl")
    assert regex is not None
    assert regex.fullmatch("top.tcl")
    assert regex.fullmatch("lib/nested/top.tcl")
    assert not regex.fullmatch("top.txt")


def test_double_star_without_slash_matches_any_tail() -> None:
    regex = glob_to_regex("generated/**")
    assert regex is not None
    assert regex.fullmatch("generated/")
    assert regex.fullmatch("generated/deep/path/file.tcl")


def test_question_mark_and_star_do_not_cross_slashes() -> None:
    regex = glob_to_regex("src/**/?.tcl")
    assert regex is not None
    assert regex.fullmatch("src/a.tcl")
    assert regex.fullmatch("src/lib/b.tcl")
    assert not regex.fullmatch("src/lib/long.tcl")


def test_character_class_and_negation_are_preserved() -> None:
    regex = glob_to_regex("**/[!b]lock[.]tcl")
    assert regex is not None
    assert regex.fullmatch("flow/clock.tcl")
    assert not regex.fullmatch("flow/block.tcl")


def test_character_class_can_start_with_closing_bracket() -> None:
    regex = glob_to_regex("**/[]a].tcl")
    assert regex is not None
    assert regex.fullmatch("].tcl")
    assert regex.fullmatch("a.tcl")
    assert not regex.fullmatch("b.tcl")


def test_unclosed_character_class_is_escaped_literally() -> None:
    regex = glob_to_regex("**/[abc.tcl")
    assert regex is not None
    assert regex.fullmatch("[abc.tcl")
    assert not regex.fullmatch("a.tcl")
