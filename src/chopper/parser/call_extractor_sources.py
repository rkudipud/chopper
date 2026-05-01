"""Literal ``source`` / ``iproc_source`` extraction helpers."""

from __future__ import annotations

from chopper.parser.tokenizer import Token, TokenKind

__all__ = ["SOURCE_KEYWORDS", "extract_source_path_with_indices"]


SOURCE_KEYWORDS: frozenset[str] = frozenset({"source", "iproc_source"})

IPROC_SOURCE_FLAGS: frozenset[str] = frozenset(
    {
        "-file",
        "-optional",
        "-required",
        "-use_hooks",
        "-quiet",
        "-echo",
        "-verbose",
    }
)
SOURCE_FLAGS: frozenset[str] = frozenset({"-echo", "-verbose", "-nocomplain", "-quiet"})


def extract_source_path_with_indices(
    tokens: tuple[Token, ...],
    keyword_idx: int,
    limit_idx: int,
    keyword: str,
) -> tuple[str | None, set[int]]:
    """Return ``(path, consumed_indices)`` for a ``source`` / ``iproc_source`` command."""
    flags = IPROC_SOURCE_FLAGS if keyword == "iproc_source" else SOURCE_FLAGS
    consumed: set[int] = set()
    n = limit_idx
    i = keyword_idx + 1
    base_depth = tokens[keyword_idx].brace_depth
    while i < n:
        tok = tokens[i]
        if tok.kind is TokenKind.NEWLINE and tok.brace_depth == base_depth:
            return None, consumed
        if tok.kind is TokenKind.SEMICOLON and tok.brace_depth == base_depth:
            return None, consumed
        if tok.kind is TokenKind.WORD:
            value = tok.value
            if value in flags:
                consumed.add(i)
                i += 1
                continue
            if is_dynamic_path(value):
                consumed.add(i)
                return None, consumed
            consumed.add(i)
            return strip_quotes(value), consumed
        i += 1
    return None, consumed


def is_dynamic_path(value: str) -> bool:
    """True if the token cannot be resolved statically to a path."""
    if "$" in value:
        return True
    if value.startswith("[") or "[" in value:
        return True
    return False


def strip_quotes(value: str) -> str:
    """Strip a single surrounding pair of double quotes or braces if present."""
    if len(value) >= 2:
        if value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        if value[0] == "{" and value[-1] == "}":
            return value[1:-1]
    return value
