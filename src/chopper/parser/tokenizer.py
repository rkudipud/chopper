"""Structural tokenizer for Tcl source.

Character-level state machine over ``(brace_depth, in_quote, in_comment)``.
Reduces raw source into a stream of :class:`Token` records annotated with
brace depth, command-position flag, and 1-indexed line number.

The tokenizer does **not** execute Tcl, track namespaces, or recognise
``proc`` definitions — those layer on top (``namespace_tracker``,
``proc_extractor``, ``call_extractor``).

Structural errors (negative depth, unclosed braces) land in
:attr:`TokenizerResult.errors` as :class:`TokenizerError` records; the
service layer translates them into ``PE-02 unbalanced-braces``.

State precedence: ``in_comment`` > ``in_quote`` > brace tracking.
Backslash escape: a structural character preceded by an odd number of
backslashes is escaped; even (including zero) is not.

Quote behavior: pre-body (depth 0, word start) ``"`` opens a quoted
word until the next unescaped ``"``. Inside braces ``"`` is literal.

Comment behavior: ``#`` at command position runs to end of line;
braces inside comments are inert.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

__all__ = [
    "Token",
    "TokenKind",
    "TokenizerError",
    "TokenizerResult",
    "tokenize",
]


class TokenKind(StrEnum):
    """Structural token kinds emitted by :func:`tokenize`.

    The set is intentionally small. Downstream consumers (proc extractor,
    call extractor) filter this stream on ``kind`` + ``at_command_position``
    + ``brace_depth``; all semantic recognition happens there.
    """

    WORD = "WORD"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    SEMICOLON = "SEMICOLON"
    NEWLINE = "NEWLINE"
    COMMENT = "COMMENT"


@dataclass(frozen=True)
class Token:
    """One structural token.

    * ``kind`` — see :class:`TokenKind`.
    * ``value`` — the raw text of the token, verbatim from the source
      (including the surrounding ``"`` quotes of a quoted word, and
      including the leading ``#`` of a comment). Value is ``"{"`` /
      ``"}"`` / ``";"`` / ``"\\n"`` for the single-character kinds.
    * ``line_no`` — 1-indexed source line where the token **begins**. For
      a quoted word that spans multiple lines (rare but legal) this is
      the line of the opening ``"``.
    * ``brace_depth`` — the brace depth **active at the start** of the
      token. For :class:`TokenKind.LBRACE`, the depth shown is the depth
      before the brace increments it. For :class:`TokenKind.RBRACE`, the
      depth shown is the depth **after** the brace decrements it
      (i.e. the enclosing scope). This makes downstream depth checks
      (``token.brace_depth == 0``) read intuitively for both cases.
    * ``at_command_position`` — True iff this token is the first token of
      a new Tcl command. Set on WORD / LBRACE / COMMENT / SEMICOLON /
      NEWLINE depending on emission context; consumers should check it
      only on WORD / LBRACE tokens.
    """

    kind: TokenKind
    value: str
    line_no: int
    brace_depth: int
    at_command_position: bool


@dataclass(frozen=True)
class TokenizerError:
    """A structural error surfaced during tokenization.

    ``kind`` values:

    * ``"negative_depth"`` — a closing ``}`` drove ``brace_depth`` below
      zero. The tokenizer clamps depth back to zero and continues so the
      remainder of the file still produces a useful token stream, but the
      service layer treats any such error as ``PE-02`` and returns ``[]``.
    * ``"unclosed_braces"`` — EOF reached with ``brace_depth > 0``.
      ``line_no`` points at the last line of the file.
    """

    kind: Literal["negative_depth", "unclosed_braces"]
    line_no: int


@dataclass(frozen=True)
class TokenizerResult:
    """Return value of :func:`tokenize`.

    * ``tokens`` — structural token stream in source order.
    * ``errors`` — zero or more :class:`TokenizerError` records. If
      ``errors`` is non-empty, callers should assume the token stream is
      unreliable beyond the first error and return ``PE-02`` (§3.0 final
      two rows).
    * ``final_brace_depth`` — depth remaining after EOF. Zero for a
      well-formed file; otherwise equal to the number of unclosed braces.
    """

    tokens: tuple[Token, ...]
    errors: tuple[TokenizerError, ...]
    final_brace_depth: int


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


def _preceding_backslashes(text: str, idx: int) -> int:
    """Return the count of consecutive ``\\`` characters immediately before ``idx``.

    An odd count means the character at ``idx`` is backslash-escaped for the
    purpose of structural scanning.
    ``idx`` must be within bounds; callers pass it only for candidate
    structural characters.
    """
    count = 0
    while idx - 1 - count >= 0 and text[idx - 1 - count] == "\\":
        count += 1
    return count


def _is_escaped(text: str, idx: int) -> bool:
    """True iff the character at ``idx`` is preceded by an odd number of ``\\``."""
    return _preceding_backslashes(text, idx) % 2 == 1


def tokenize(text: str) -> TokenizerResult:
    """Tokenize a Tcl source string.

    The function is pure and deterministic: given the same input, it
    produces the same :class:`TokenizerResult`. It never raises for
    malformed input — structural errors surface on
    :attr:`TokenizerResult.errors`.
    """
    tokens: list[Token] = []
    errors: list[TokenizerError] = []

    i = 0
    n = len(text)
    line_no = 1
    brace_depth = 0
    at_cmd_pos = True  # start-of-file is command position

    # Pending-word state. ``word_start == -1`` means no word in progress.
    # ``word_at_cmd_pos`` captures ``at_cmd_pos`` at word start so flushing
    # the word emits the right flag even after at_cmd_pos has flipped.
    word_start = -1
    word_line = 0
    word_at_cmd_pos = False
    in_quoted_word = False  # True while scanning between matched ``"`` quotes
    quoted_bracket_depth = 0  # ``[...]`` nesting inside a quoted word

    def _flush_word(end_idx: int) -> None:
        nonlocal word_start, at_cmd_pos
        if word_start != -1:
            tokens.append(
                Token(
                    kind=TokenKind.WORD,
                    value=text[word_start:end_idx],
                    line_no=word_line,
                    brace_depth=brace_depth,
                    at_command_position=word_at_cmd_pos,
                )
            )
            word_start = -1
            at_cmd_pos = False

    while i < n:
        ch = text[i]

        # Backslash-newline continuation — handled uniformly before any
        # other dispatch so the pair is invisible to word accumulation
        # (§3.2: do not physically join lines, but the command continues
        # and the `\` must not become part of a word). Comments and
        # quoted-word scanning also honour this via their own loops;
        # this top-level check catches the continuation anywhere else
        # (e.g. between words, inside an unquoted word, at cmd-pos).
        if ch == "\\" and i + 1 < n and text[i + 1] == "\n" and not _is_escaped(text, i):
            # Flush any in-progress unquoted word that ended before the
            # backslash (quoted-word state is handled by its own branch).
            if not in_quoted_word:
                _flush_word(i)
            line_no += 1
            i += 2
            continue

        # Quoted-word in progress — track ``[...]`` bracket nesting
        # because in Tcl ``"..."`` words, ``[...]`` is command
        # substitution and any ``"`` inside it is part of the inner
        # command, not a closing quote of the outer word. Without this
        # nesting accounting, an inner ``[format "%.3f" ...]`` would
        # close the outer quote and leak the rest of the message text
        # back into the command stream — see bug
        # ``TW-02_quoted_string_semicolon_misparse.md``.
        if in_quoted_word:
            if ch == "[" and not _is_escaped(text, i):
                quoted_bracket_depth += 1
                i += 1
                continue
            if ch == "]" and not _is_escaped(text, i) and quoted_bracket_depth > 0:
                quoted_bracket_depth -= 1
                i += 1
                continue
            if ch == '"' and quoted_bracket_depth == 0 and not _is_escaped(text, i):
                # Close the quoted word; include the closing ``"`` in value.
                tokens.append(
                    Token(
                        kind=TokenKind.WORD,
                        value=text[word_start : i + 1],
                        line_no=word_line,
                        brace_depth=brace_depth,
                        at_command_position=word_at_cmd_pos,
                    )
                )
                word_start = -1
                in_quoted_word = False
                quoted_bracket_depth = 0
                at_cmd_pos = False
                i += 1
                continue
            if ch == "\n":
                line_no += 1
            i += 1
            continue

        # Newline — unless it is an odd-backslash continuation.
        if ch == "\n":
            if _is_escaped(text, i):
                # Line continuation: the command continues on the next line.
                # Line number advances; at_cmd_pos is preserved.
                line_no += 1
                i += 1
                continue
            _flush_word(i)
            tokens.append(
                Token(
                    kind=TokenKind.NEWLINE,
                    value="\n",
                    line_no=line_no,
                    brace_depth=brace_depth,
                    at_command_position=False,
                )
            )
            line_no += 1
            i += 1
            at_cmd_pos = True
            continue

        # Inter-token whitespace (space, tab).
        if ch in " \t":
            _flush_word(i)
            i += 1
            continue

        # Comment: `#` at command position, not already inside a word.
        if ch == "#" and at_cmd_pos and word_start == -1:
            comment_start = i
            comment_line = line_no
            # Scan to end of logical line (honouring backslash-newline continuation).
            while i < n:
                c = text[i]
                if c == "\n":
                    if _is_escaped(text, i):
                        line_no += 1
                        i += 1
                        continue
                    break
                i += 1
            tokens.append(
                Token(
                    kind=TokenKind.COMMENT,
                    value=text[comment_start:i],
                    line_no=comment_line,
                    brace_depth=brace_depth,
                    at_command_position=True,
                )
            )
            # Leave the newline (if any) for the main loop to handle — it will
            # reset at_cmd_pos and increment line_no via the newline branch.
            continue

        # Open-brace `{` — unescaped → structural.
        if ch == "{" and not _is_escaped(text, i):
            _flush_word(i)
            tokens.append(
                Token(
                    kind=TokenKind.LBRACE,
                    value="{",
                    line_no=line_no,
                    brace_depth=brace_depth,
                    at_command_position=at_cmd_pos,
                )
            )
            brace_depth += 1
            at_cmd_pos = False
            i += 1
            continue

        # Close-brace `}` — unescaped → structural.
        if ch == "}" and not _is_escaped(text, i):
            _flush_word(i)
            brace_depth -= 1
            if brace_depth < 0:
                errors.append(TokenizerError(kind="negative_depth", line_no=line_no))
                brace_depth = 0  # clamp for error recovery; caller aborts
            tokens.append(
                Token(
                    kind=TokenKind.RBRACE,
                    value="}",
                    line_no=line_no,
                    brace_depth=brace_depth,  # depth of the enclosing scope
                    at_command_position=False,
                )
            )
            at_cmd_pos = False
            i += 1
            continue

        # Semicolon — command terminator.
        if ch == ";":
            _flush_word(i)
            tokens.append(
                Token(
                    kind=TokenKind.SEMICOLON,
                    value=";",
                    line_no=line_no,
                    brace_depth=brace_depth,
                    at_command_position=False,
                )
            )
            at_cmd_pos = True
            i += 1
            continue

        # Double-quote — opens a quoted word at word-start position. Tcl's
        # rule (Endekas/Dodekalogue rule 5: "Double-quotes") is that an
        # unescaped ``"`` at a word boundary opens a quoted word that runs
        # until the matching unescaped ``"``; whitespace, ``;``, ``\n``,
        # and ``}`` inside the quoted word are LITERAL characters.
        # The previous implementation gated this on ``brace_depth == 0``,
        # which broke every proc body (depth ≥ 1) and was the root cause
        # of TW-02 false positives where ``;`` inside a quoted string was
        # treated as a command separator (bug report
        # ``TW-02_quoted_string_semicolon_misparse.md``). Quoting must
        # work at every depth — Chopper re-tokenizes proc bodies as Tcl
        # source and Tcl source honors ``"..."`` regardless of nesting.
        if ch == '"' and word_start == -1 and not _is_escaped(text, i):
            word_start = i  # include opening `"` in value
            word_line = line_no
            word_at_cmd_pos = at_cmd_pos
            in_quoted_word = True
            i += 1
            continue

        # Generic character — part of a word.
        if word_start == -1:
            word_start = i
            word_line = line_no
            word_at_cmd_pos = at_cmd_pos
        i += 1

    # EOF flush.
    _flush_word(n)
    if in_quoted_word:
        # An unclosed quoted word is reported as unclosed_braces-equivalent
        # (it also fails the brace-balance check once the enclosing scope
        # closes elsewhere). Still, surface it so the service can emit PE-02.
        errors.append(TokenizerError(kind="unclosed_braces", line_no=line_no))
    if brace_depth > 0:
        errors.append(TokenizerError(kind="unclosed_braces", line_no=line_no))

    return TokenizerResult(
        tokens=tuple(tokens),
        errors=tuple(errors),
        final_brace_depth=brace_depth,
    )
