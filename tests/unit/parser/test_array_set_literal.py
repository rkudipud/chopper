"""Braced ``array set`` data is literal and must not yield calls."""

from __future__ import annotations

from pathlib import Path

from chopper.parser.service import parse_file


def test_array_set_braced_keys_are_not_calls() -> None:
    src = 'proc example {} {\n    array set data {\n        alpha ""\n        beta ""\n    }\n    foo\n}\n'
    assert parse_file(Path("example.tcl"), src)[0].calls == ("foo",)
