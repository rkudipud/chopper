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
                candidate = classify_call_candidate(match.group(1))
                if candidate is not None:
                    calls.add(candidate)
        i += 1

    return tuple(sorted(calls)), tuple(source_refs)
