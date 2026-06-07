"""Public body-walk entry point for Tcl call extraction."""

from __future__ import annotations

from chopper.parser.call_extractor_classify import (
    BRACKET_CALL_RE,
    classify_call_candidate,
    should_suppress_first_word,
)
from chopper.parser.call_extractor_sources import SOURCE_KEYWORDS, extract_source_path_with_indices
from chopper.parser.call_extractor_structural import compute_skip_indices
from chopper.parser.tokenizer import Token, TokenKind

__all__ = ["extract_body_refs"]


def _bracket_is_escaped(text: str, bracket_pos: int) -> bool:
    """Return True if the ``[`` at *bracket_pos* in *text* is backslash-escaped.

    A ``[`` is escaped when it is preceded by an **odd** count of backslashes.
    An even count (including zero) means the backslashes cancel out and the
    bracket is a real command-substitution opener.

    Examples::

        \\[H      -> odd (1)  -> escaped  -> literal bracket, NOT a proc call
        \\\\[H   -> even (2) -> not escaped -> real command substitution
        [H        -> zero     -> not escaped -> real command substitution
    """
    count = 0
    j = bracket_pos - 1
    while j >= 0 and text[j] == "\\":
        count += 1
        j -= 1
    return count % 2 == 1


def extract_body_refs(
    tokens: tuple[Token, ...],
    body_lbrace_idx: int,
    body_rbrace_idx: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extract ``(calls, source_refs)`` for one proc body."""
    if body_lbrace_idx + 1 >= body_rbrace_idx:
        return (), ()

    calls: set[str] = set()
    source_refs: list[str] = []
    consumed: set[int] = set()
    skip_indices = compute_skip_indices(tokens, body_lbrace_idx, body_rbrace_idx)

    i = body_lbrace_idx + 1
    while i < body_rbrace_idx:
        if i in skip_indices:
            i += 1
            continue
        token = tokens[i]
        if token.kind is TokenKind.WORD and token.at_command_position:
            first_word = token.value
            if first_word in SOURCE_KEYWORDS:
                path, consumed_indices = extract_source_path_with_indices(tokens, i, body_rbrace_idx, first_word)
                if path is not None:
                    source_refs.append(path)
                consumed.update(consumed_indices)
                i += 1
                continue

            if not should_suppress_first_word(first_word):
                candidate = classify_call_candidate(first_word)
                if candidate is not None:
                    calls.add(candidate)
        if token.kind is TokenKind.WORD and i not in consumed:
            for match in BRACKET_CALL_RE.finditer(token.value):
                # P-46: skip escaped brackets -- \[ is a literal character in a
                # Tcl string, not a command-substitution opener.
                if _bracket_is_escaped(token.value, match.start()):
                    continue
                candidate = classify_call_candidate(match.group(1))
                if candidate is not None:
                    calls.add(candidate)
        i += 1

    return tuple(sorted(calls)), tuple(source_refs)
