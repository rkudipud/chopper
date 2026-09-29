"""Unit tests for :mod:`chopper.core.globs` -- the ARCHITECTURE.md Sec.6.3.1 contract."""

from __future__ import annotations

import pytest

from chopper.core.globs import glob_match

# Every row of the Sec.6.3.1 "Examples" table, verbatim. The three rows marked
# "cross '/'" failed before 4.9.1: plain patterns fell back to fnmatch, whose
# ``*`` crosses directory boundaries.
SPEC_TABLE = [
    ("procs/*.tcl", "procs/core_procs.tcl", True),
    ("procs/*.tcl", "procs/rules.tcl", True),
    ("procs/*.tcl", "procs/sub/file.tcl", False),  # cross '/'
    ("procs/??.tcl", "procs/ab.tcl", True),
    ("procs/??.tcl", "procs/abc.tcl", False),
    ("reports/**", "reports/base.txt", True),
    ("reports/**", "reports/sub/detail.txt", True),
    ("reports/**", "reports/a/b/c/file.txt", True),
    ("rules/**/*.fm.tcl", "rules/r1.fm.tcl", True),
    ("rules/**/*.fm.tcl", "rules/sub/r2.fm.tcl", True),
    ("rules/**/*.fm.tcl", "rules/r1.tcl", False),
    ("*_procs.tcl", "core_procs.tcl", True),
    ("*_procs.tcl", "dft_procs.tcl", True),
    ("*_procs.tcl", "procs/core_procs.tcl", False),  # cross '/'
    ("*.tcl", "lib/top.tcl", False),  # cross '/'
]


@pytest.mark.parametrize(("pattern", "path", "expected"), SPEC_TABLE)
def test_architecture_glob_examples(pattern: str, path: str, expected: bool) -> None:
    assert glob_match(pattern, path) is expected


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("**/*.tcl", "top.tcl", True),  # ** matches zero segments
        ("**/*.tcl", "lib/nested/top.tcl", True),
        ("src/**/?.tcl", "src/lib/long.tcl", False),  # ? stays inside one segment
        ("**/[!b]lock.tcl", "flow/clock.tcl", True),
        ("**/[!b]lock.tcl", "flow/block.tcl", False),
        ("Procs/*.tcl", "procs/a.tcl", False),  # case-sensitive
        ("**/[abc.tcl", "[abc.tcl", True),  # an unclosed class is a literal, never an error
        ("**/[abc.tcl", "a.tcl", False),
    ],
)
def test_segment_and_class_semantics(pattern: str, path: str, expected: bool) -> None:
    assert glob_match(pattern, path) is expected
