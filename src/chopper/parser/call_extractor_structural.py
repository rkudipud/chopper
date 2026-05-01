"""Structural skip pre-pass for Tcl body call extraction.

This module owns opaque braced arguments (regex/exec/glob), recursive Tcl
code-body descent, and ``switch`` pattern-label suppression.
"""

from __future__ import annotations

import re

from chopper.parser.tokenizer import Token, TokenKind

__all__ = ["compute_skip_indices"]


OPAQUE_BRACE_COMMANDS: frozenset[str] = frozenset({"regexp", "regsub", "exec", "glob"})
CODE_BRACE_COMMANDS: frozenset[str] = frozenset(
    {
        "if",
        "elseif",
        "else",
        "while",
        "for",
        "foreach",
        "foreach_in_collection",
        "catch",
        "try",
        "eval",
        "uplevel",
        "namespace",
        "expr",
    }
)
INNER_CMD_RE = re.compile(r"\[\s*([A-Za-z_][A-Za-z_0-9]*)")


def compute_skip_indices(tokens: tuple[Token, ...], body_lbrace_idx: int, body_rbrace_idx: int) -> set[int]:
    """Identify token indices the extractor must skip during the body walk."""
    skip: set[int] = set()
    scan_command_range(tokens, body_lbrace_idx + 1, body_rbrace_idx, skip)
    return skip


def scan_command_range(tokens: tuple[Token, ...], start: int, end: int, skip: set[int]) -> None:
    """Pre-pass over a Tcl-code range, populating ``skip`` in-place."""
    if start >= end:
        return
    enclosing_depth = tokens[start].brace_depth if start < end else 0
    expecting_cmd = True
    i = start
    while i < end:
        tok = tokens[i]
        if tok.kind is TokenKind.NEWLINE or tok.kind is TokenKind.SEMICOLON:
            if tok.brace_depth == enclosing_depth:
                expecting_cmd = True
            i += 1
            continue
        if tok.kind is TokenKind.WORD:
            base_depth = tok.brace_depth
            cmd_end = find_command_end(tokens, i + 1, end, base_depth)
            is_cmd_pos = tok.at_command_position or (expecting_cmd and base_depth == enclosing_depth)
            if is_cmd_pos and i not in skip:
                classify_and_handle(tokens, tok.value, i + 1, cmd_end, base_depth, skip)
                expecting_cmd = False
            for match in INNER_CMD_RE.finditer(tok.value):
                inner_cmd = match.group(1)
                classify_and_handle(tokens, inner_cmd, i + 1, cmd_end, base_depth, skip)
        elif tok.kind is TokenKind.LBRACE or tok.kind is TokenKind.RBRACE:
            pass
        i += 1


def classify_and_handle(
    tokens: tuple[Token, ...], cmd: str, arg_start: int, arg_end: int, depth: int, skip: set[int]
) -> None:
    """Apply opaque/code/switch handling for one command."""
    if cmd in OPAQUE_BRACE_COMMANDS:
        mark_opaque_arg_braces(tokens, arg_start, arg_end, depth, skip)
    elif cmd == "string":
        if is_string_match(tokens, arg_start, arg_end):
            mark_opaque_arg_braces(tokens, arg_start, arg_end, depth, skip)
    elif cmd == "switch":
        mark_switch_pattern_words(tokens, arg_start, arg_end, depth, skip)
    elif cmd in CODE_BRACE_COMMANDS:
        j = arg_start
        while j < arg_end:
            token = tokens[j]
            if token.kind is TokenKind.LBRACE and token.brace_depth == depth:
                rbrace = matching_rbrace(tokens, j, arg_end)
                if rbrace is not None:
                    scan_command_range(tokens, j + 1, rbrace, skip)
                    j = rbrace + 1
                    continue
            j += 1


def find_command_end(tokens: tuple[Token, ...], start: int, limit: int, base_depth: int) -> int:
    """Return the exclusive index where this command ends."""
    j = start
    while j < limit:
        token = tokens[j]
        if (token.kind is TokenKind.NEWLINE or token.kind is TokenKind.SEMICOLON) and token.brace_depth == base_depth:
            return j
        j += 1
    return limit


def mark_opaque_arg_braces(tokens: tuple[Token, ...], start: int, end: int, base_depth: int, skip: set[int]) -> None:
    """Mark every ``{...}`` argument of the current command as opaque."""
    j = start
    while j < end:
        token = tokens[j]
        if token.kind is TokenKind.LBRACE and token.brace_depth == base_depth:
            rbrace = matching_rbrace(tokens, j, end)
            if rbrace is not None:
                for k in range(j, rbrace + 1):
                    skip.add(k)
                j = rbrace + 1
                continue
        j += 1


def mark_switch_pattern_words(tokens: tuple[Token, ...], start: int, end: int, base_depth: int, skip: set[int]) -> None:
    """Mark ``switch`` pattern-label WORDs inside the body brace as skip."""
    body_lbrace = last_lbrace_at_depth(tokens, start, end, base_depth)
    if body_lbrace is None:
        return
    body_rbrace = matching_rbrace(tokens, body_lbrace, end)
    if body_rbrace is None:
        return
    inner_depth = base_depth + 1
    for j in range(body_lbrace + 1, body_rbrace):
        token = tokens[j]
        if token.kind is TokenKind.WORD and token.brace_depth == inner_depth:
            skip.add(j)


def matching_rbrace(tokens: tuple[Token, ...], lbrace_idx: int, limit: int) -> int | None:
    """Find the index of the RBRACE matching ``tokens[lbrace_idx]``."""
    depth_after_open = tokens[lbrace_idx].brace_depth + 1
    j = lbrace_idx + 1
    while j < limit:
        token = tokens[j]
        if token.kind is TokenKind.RBRACE and token.brace_depth == depth_after_open - 1:
            return j
        j += 1
    return None


def last_lbrace_at_depth(tokens: tuple[Token, ...], start: int, end: int, depth: int) -> int | None:
    """Return the index of the last LBRACE within ``[start, end)`` at ``depth``."""
    last: int | None = None
    j = start
    while j < end:
        token = tokens[j]
        if token.kind is TokenKind.LBRACE and token.brace_depth == depth:
            last = j
        j += 1
    return last


def is_string_match(tokens: tuple[Token, ...], start: int, end: int) -> bool:
    """True iff this ``string`` command is ``string match ...``."""
    j = start
    while j < end:
        token = tokens[j]
        if token.kind is TokenKind.WORD:
            return token.value == "match"
        j += 1
    return False
