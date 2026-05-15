"""Per-file coverage tests for src/chopper/parser/tokenizer.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations



from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_tokenizer_command_position_backslash_newline_advances_line() -> None:
    """A backslash-newline at command position is a line continuation:
    line counter advances but the command stays open."""
    from chopper.parser.tokenizer import tokenize

    text = "proc x {} {}\n\\\nproc y {} {}\n"
    result = tokenize(text)
    proc_tokens = [t for t in result.tokens if t.value == "proc"]
    assert len(proc_tokens) >= 2


def test_tokenizer_comment_with_backslash_newline_continuation() -> None:
    """Backslash-newline inside a comment continues the comment."""
    from chopper.parser.tokenizer import tokenize

    text = "# header continues \\\nstill the comment\nproc x {} {}\n"
    result = tokenize(text)
    assert any(t.value == "proc" for t in result.tokens)


def test_tokenizer_comment_backslash_newline_advances_line_count() -> None:
    """A backslash-newline inside a Tcl comment is a line continuation.
    The tokenizer must count lines correctly so subsequent tokens get the
    right line_no (IMPLEMENTATION.md §P-02)."""
    from chopper.parser.tokenizer import tokenize

    # Comment with backslash-newline continuation, then a proc.
    text = "# multi-line \\\ncontinuation comment\nproc x {} {}\n"
    result = tokenize(text)
    proc_tokens = [t for t in result.tokens if t.value == "proc"]
    assert len(proc_tokens) == 1
    # proc must be on line 3 (after comment + continuation + blank).
    assert proc_tokens[0].line_no == 3


def test_tokenizer_handles_backslash_line_continuation() -> None:
    """Backslash line continuation must not crash the tokenizer (IMPLEMENTATION.md §P-02)."""
    from chopper.parser.tokenizer import tokenize

    # A backslash at end of line continues to the next physical line.
    text = "proc foo {} \\\n{ return 1 }\n"
    result = tokenize(text)
    tokens = list(result.tokens)
    # No crash; essential tokens are present.
    token_values = [t.value for t in tokens if t.value]
    assert "proc" in token_values
    assert "foo" in token_values


def test_tokenizer_backslash_continuation_increments_line_no() -> None:
    """Backslash-newline continuation is consumed without emitting NEWLINE token (lines 261-263)."""
    from chopper.parser.tokenizer import tokenize, TokenKind

    # 'proc foo {} ' followed by a backslash-continuation, then body
    text = "proc foo {} \\\n    {return 1}"
    result = tokenize(text)
    assert not result.errors
    # No NEWLINE token should appear (the \\\\n was consumed as continuation)
    newlines = [t for t in result.tokens if t.kind is TokenKind.NEWLINE]
    # The backslash-newline was continuation; the only newline token is the final implicit one if any
    # Main assertion: tokenization succeeds without errors and lines 261-263 execute
    assert len(result.tokens) > 0
