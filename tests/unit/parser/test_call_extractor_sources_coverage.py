"""Per-file coverage tests for src/chopper/parser/call_extractor_sources.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_call_extractor_strip_quotes_braces() -> None:
    from chopper.parser.call_extractor_sources import strip_quotes

    assert strip_quotes("{abc}") == "abc"
    assert strip_quotes('"abc"') == "abc"
    assert strip_quotes("plain") == "plain"


def test_strip_quotes_returns_value_unchanged_when_short() -> None:
    """strip_quotes returns the input unchanged when len < 2 (branch 70->75)."""
    from chopper.parser.call_extractor_sources import strip_quotes

    # Short strings -- condition len(value) >= 2 is False -> return value unchanged
    assert strip_quotes("") == ""
    assert strip_quotes("a") == "a"
    # Normal cases still work
    assert strip_quotes('"hello"') == "hello"
    assert strip_quotes("{hello}") == "hello"
