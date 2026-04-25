"""Proc extractor — recognises ``proc`` definitions in the token stream.

Walks the output of :func:`chopper.parser.tokenizer.tokenize`, drives a
:class:`NamespaceTracker`, and emits one :class:`ProcEntry` per
recognised proc.

Handled:

* ``proc NAME ARGS BODY`` recognition at command position in
  :attr:`ContextKind.FILE_ROOT` / :attr:`ContextKind.NAMESPACE_EVAL`.
* Canonical-name resolution (short + qualified).
* Body span (``start_line``, ``end_line``, ``body_start_line``,
  ``body_end_line``).
* Doc-comment banner backward scan (``comment_start_line`` /
  ``comment_end_line``).
* ``define_proc_attributes`` forward scan (``dpa_start_line`` /
  ``dpa_end_line``), ``PW-11`` name-mismatch, ``PI-04`` orphan.
* Diagnostics: ``PE-01``, ``PW-01``, ``PW-03``, ``PW-04`` (pass-through),
  ``PW-11``, ``PI-04``.

Call and source-ref extraction is delegated to
:mod:`chopper.parser.call_extractor`; the returned ``calls`` /
``source_refs`` tuples on :class:`ProcEntry` are populated by that module.

Pure module: no I/O, no :class:`ChopperContext` knowledge. The service
layer translates :class:`ExtractorDiagnostic` instances into registered
:class:`Diagnostic` codes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from chopper.core.models import ProcEntry

from .call_extractor import extract_body_refs
from .namespace_tracker import NamespaceTracker
from .tokenizer import Token, TokenizerResult, TokenKind, tokenize

__all__ = [
    "ExtractorDiagnostic",
    "ExtractorResult",
    "extract_procs",
]


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


ExtractorDiagnosticKind = Literal[
    "computed-proc-name",  # PW-01 — $var / ${...} / [...] in proc name
    "non-brace-body",  # PW-03 — proc body is not brace-delimited
    "computed-namespace-name",  # PW-04 — pass-through from NamespaceTracker
    "duplicate-proc-definition",  # PE-01 — two procs with same short_name in one file
    "dpa-name-mismatch",  # PW-11 — define_proc_attributes name != preceding qualified_name
    "dpa-orphan",  # PI-04 — define_proc_attributes with no preceding proc in file
]


@dataclass(frozen=True)
class ExtractorDiagnostic:
    """One observation from the proc extractor awaiting service-layer translation."""

    kind: ExtractorDiagnosticKind
    line_no: int
    detail: str


@dataclass(frozen=True)
class ExtractorResult:
    """Pure return value of :func:`extract_procs`.

    The service layer (Stage 1f) owns: reading the file, mapping
    :class:`ExtractorDiagnostic` into registered
    :class:`~chopper.core.diagnostics.Diagnostic` codes, and assembling
    :class:`~chopper.core.models.ParsedFile` + :class:`~chopper.core.models.ParseResult`.
    """

    procs: tuple[ProcEntry, ...]
    diagnostics: tuple[ExtractorDiagnostic, ...]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# §4.6: lookahead window of up to 3 blank lines after the proc close.
_DPA_BLANK_LOOKAHEAD = 3

# §4.6 DPA line recogniser.
_DPA_LINE_RE = re.compile(r"^\s*define_proc_(attributes|arguments)\s+")

# §4.6: boolean flags to strip before extracting the proc name.
_DPA_BOOL_FLAGS = (
    "-permanent",
    "-hide_body",
    "-hidden",
    "-dont_abbrev",
    "-obsolete",
    "-deprecated",
)

# §4.6: arg flags with values to strip before extracting the proc name.
_DPA_VALUE_FLAGS = (
    "-info",
    "-define_args",
    "-define_arg_groups",
    "-command_group",
    "-return",
)

# §4.7: comment-banner line test.
_COMMENT_LINE_RE = re.compile(r"^\s*#")

# §4.3: a proc name is "computed" if it contains any of these substitution markers.
_COMPUTED_NAME_MARKERS = ("$", "[")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def extract_procs(source_file: Path, text: str) -> ExtractorResult:
    """Extract proc definitions from Tcl source text.

    :param source_file: Domain-relative POSIX path recorded verbatim on each
        :class:`~chopper.core.models.ProcEntry` (also feeds canonical-name
        construction).
    :param text: UTF-8 decoded source text with ``\\n`` line endings
        (normalization is the service layer's responsibility — §Line endings).
    :returns: :class:`ExtractorResult` with the recognised procs (sorted by
        ``start_line``) and accumulated diagnostics in source order.

    The function is pure and deterministic: given the same ``source_file``
    and ``text`` it produces the same result. It never raises for malformed
    Tcl — structural tokenizer errors (``negative_depth`` / ``unclosed_braces``)
    short-circuit extraction and return an empty proc list, leaving the
    translation of those errors to ``PE-02`` for the service layer.
    """
    tok_result: TokenizerResult = tokenize(text)
    if tok_result.errors:
        # §3.0 state table: structural brace errors → PE-02, parse_file returns [].
        # The service layer inspects the tokenizer errors separately; the
        # extractor simply produces no procs.
        return ExtractorResult(procs=(), diagnostics=())

    tokens = tok_result.tokens
    # 0-indexed; source line N → lines[N-1].  Strip trailing ``\r`` so CRLF
    # inputs do not leak ``\r`` into downstream continuation / DPA analyzers
    # (P-02 backslash continuation must match regardless of line-ending style).
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    tracker = NamespaceTracker()
    procs: list[ProcEntry] = []
    diagnostics: list[ExtractorDiagnostic] = []
    # Track which source lines are covered by a DPA span so we can emit PI-04
    # for orphan define_proc_attributes lines at end of file.
    dpa_covered_lines: set[int] = set()

    pending_body_lbrace_idx: int | None = None

    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]

        # Proc detection must happen BEFORE feeding the ``proc`` token, so
        # ``tracker.can_define_proc()`` reflects the context at the keyword
        # position rather than after it.
        if tok.kind is TokenKind.WORD and tok.value == "proc" and tok.at_command_position and tracker.can_define_proc():
            # PW-01 guard: peek the name token and reject computed names
            # BEFORE attempting full layout scan (computed names break the
            # args/body element model; the scan would misclassify the next
            # non-brace word as a non-brace body).
            name_tok = _peek_name_token(tokens, i)
            if name_tok is not None and _is_computed_name(name_tok.value):
                diagnostics.append(
                    ExtractorDiagnostic(
                        kind="computed-proc-name",
                        line_no=name_tok.line_no,
                        detail=name_tok.value,
                    )
                )
                tracker.feed(tok)
                i += 1
                continue
            layout = _scan_proc_layout(tokens, i, base_depth=tracker.depth)
            if layout is not None:
                entry, entry_diags = _build_entry(
                    layout=layout,
                    tokens=tokens,
                    lines=lines,
                    source_file=source_file,
                    namespace_path=tracker.namespace_path,
                )
                diagnostics.extend(entry_diags)
                if entry is not None:
                    procs.append(entry)
                    # §4.6 forward DPA scan.
                    dpa_start, dpa_end, dpa_diags = _scan_dpa(
                        lines=lines,
                        proc_end_line=entry.end_line,
                        qualified_name=entry.qualified_name,
                    )
                    diagnostics.extend(dpa_diags)
                    if dpa_start is not None and dpa_end is not None:
                        # Replace the entry with DPA-enriched copy.
                        procs[-1] = _with_dpa(procs[-1], dpa_start, dpa_end)
                        dpa_covered_lines.update(range(dpa_start, dpa_end + 1))
                    pending_body_lbrace_idx = layout.body_lbrace_idx
            else:
                # Malformed proc — distinguish PW-03 (non-brace body) from
                # other failure modes by re-inspecting the post-args token.
                pw03 = _detect_non_brace_body(tokens, i, base_depth=tracker.depth)
                if pw03 is not None:
                    diagnostics.append(pw03)

        # Mark the body LBRACE immediately before it is fed to the tracker
        # so the resulting frame is :attr:`ContextKind.PROC_BODY`.
        if pending_body_lbrace_idx == i:
            tracker.mark_proc_body_opening()
            pending_body_lbrace_idx = None

        tracker.feed(tok)
        i += 1

    # Pass-through: tracker's PW-04 diagnostics surface through the extractor.
    for d in tracker.diagnostics:
        diagnostics.append(
            ExtractorDiagnostic(
                kind="computed-namespace-name",
                line_no=d.line_no,
                detail=d.detail,
            )
        )

    # §6.3: per-file duplicate short_name check. Emit PE-01 and drop earlier
    # duplicates so only the last definition survives in the returned list
    # (Invariant 4).
    procs, dup_diags = _deduplicate_short_names(procs)
    diagnostics.extend(dup_diags)

    # §4.6: orphan DPA lines — define_proc_attributes lines not covered by
    # any proc's dpa span → PI-04.
    for lineno_0, line in enumerate(lines):
        if _DPA_LINE_RE.match(line) and (lineno_0 + 1) not in dpa_covered_lines:
            # Strip a trailing line-continuation backslash so the user-facing
            # message does not carry the raw ``\`` (bug:
            # ``PW-11_PI-04_dpa_line_continuation_misparse.md``).
            detail = line.rstrip("\r\n").rstrip("\\").rstrip()
            diagnostics.append(
                ExtractorDiagnostic(
                    kind="dpa-orphan",
                    line_no=lineno_0 + 1,
                    detail=detail,
                )
            )

    # Deterministic output: sort procs by start_line (spec invariant on ParsedFile)
    # and diagnostics by (line_no, kind) so retokenization yields stable order.
    procs.sort(key=lambda p: p.start_line)
    diagnostics.sort(key=lambda d: (d.line_no, d.kind, d.detail))

    return ExtractorResult(procs=tuple(procs), diagnostics=tuple(diagnostics))


# ---------------------------------------------------------------------------
# Proc layout scanning
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ProcLayout:
    """Token-index layout of one proc definition."""

    proc_idx: int
    """Index of the ``proc`` keyword WORD token."""

    name_idx: int
    """Index of the WORD token carrying the proc name."""

    body_lbrace_idx: int
    """Index of the body opening ``LBRACE`` token."""

    body_rbrace_idx: int
    """Index of the body closing ``RBRACE`` token."""


def _peek_name_token(tokens: tuple[Token, ...], start_idx: int) -> Token | None:
    """Return the name WORD token following ``proc`` at ``start_idx`` or ``None``.

    Used for the PW-01 computed-name guard so the extractor can reject a
    malformed proc definition without triggering :func:`_scan_proc_layout`'s
    non-brace-body fallback.
    """
    j = start_idx + 1
    n = len(tokens)
    while j < n and tokens[j].kind is TokenKind.NEWLINE:
        j += 1
    if j < n and tokens[j].kind is TokenKind.WORD:
        return tokens[j]
    return None


def _scan_proc_layout(tokens: tuple[Token, ...], start_idx: int, base_depth: int) -> _ProcLayout | None:
    """Return the token-index layout of the proc starting at ``start_idx``.

    Returns ``None`` if the proc is malformed (no name, no args, no brace
    body). Callers still report the failure through diagnostics constructed
    in :func:`_build_entry`.
    """
    n = len(tokens)

    # Step 1: find the name — skip NEWLINE (continuation permitted per §7.2).
    i = start_idx + 1
    while i < n and tokens[i].kind is TokenKind.NEWLINE:
        i += 1
    if i >= n or tokens[i].kind is not TokenKind.WORD:
        return None
    name_idx = i
    i += 1

    # Step 2: consume args element (WORD or LBRACE-delimited block).
    while i < n and tokens[i].kind is TokenKind.NEWLINE:
        i += 1
    if i >= n:
        return None
    args_end = _consume_element(tokens, i, base_depth)
    if args_end is None:
        return None
    i = args_end

    # Step 3: the body MUST be brace-delimited (§4.1, §7.4 / PW-03).
    while i < n and tokens[i].kind is TokenKind.NEWLINE:
        i += 1
    if i >= n or tokens[i].kind is not TokenKind.LBRACE:
        return None
    body_lbrace_idx = i
    body_close = _consume_brace_block(tokens, i, base_depth)
    if body_close is None:
        # Tokenizer would have already flagged this; defensive.
        return None
    body_rbrace_idx = body_close - 1

    return _ProcLayout(
        proc_idx=start_idx,
        name_idx=name_idx,
        body_lbrace_idx=body_lbrace_idx,
        body_rbrace_idx=body_rbrace_idx,
    )


def _consume_element(tokens: tuple[Token, ...], i: int, base_depth: int) -> int | None:
    """Consume one element (a WORD or a balanced ``{...}`` block). Return index past it."""
    tok = tokens[i]
    if tok.kind is TokenKind.WORD:
        return i + 1
    if tok.kind is TokenKind.LBRACE:
        return _consume_brace_block(tokens, i, base_depth)
    return None


def _consume_brace_block(tokens: tuple[Token, ...], i: int, base_depth: int) -> int | None:
    """Consume a brace block starting at LBRACE index ``i``. Return index past RBRACE."""
    if tokens[i].kind is not TokenKind.LBRACE:
        return None
    depth = base_depth + 1
    j = i + 1
    n = len(tokens)
    while j < n:
        kind = tokens[j].kind
        if kind is TokenKind.LBRACE:
            depth += 1
        elif kind is TokenKind.RBRACE:
            depth -= 1
            if depth == base_depth:
                return j + 1
        j += 1
    return None


def _detect_non_brace_body(tokens: tuple[Token, ...], start_idx: int, base_depth: int) -> ExtractorDiagnostic | None:
    """Diagnose a ``proc NAME ARGS WORD`` form where the body is not braced.

    §7.4 / ``PW-03``: ``proc foo args "return hello"`` — the third element
    is a quoted WORD, not an ``LBRACE``. Return the diagnostic; the proc
    itself is skipped (no :class:`ProcEntry`).
    """
    n = len(tokens)
    i = start_idx + 1  # past `proc`
    while i < n and tokens[i].kind is TokenKind.NEWLINE:
        i += 1
    if i >= n or tokens[i].kind is not TokenKind.WORD:
        return None
    name_tok = tokens[i]
    i += 1
    while i < n and tokens[i].kind is TokenKind.NEWLINE:
        i += 1
    if i >= n:
        return None
    args_end = _consume_element(tokens, i, base_depth)
    if args_end is None:
        return None
    i = args_end
    while i < n and tokens[i].kind is TokenKind.NEWLINE:
        i += 1
    if i >= n:
        return None
    if tokens[i].kind is TokenKind.WORD:
        # Third element is a word, not a brace — non-brace body.
        return ExtractorDiagnostic(
            kind="non-brace-body",
            line_no=name_tok.line_no,
            detail=name_tok.value,
        )
    return None


# ---------------------------------------------------------------------------
# Entry construction
# ---------------------------------------------------------------------------


def _build_entry(
    layout: _ProcLayout,
    tokens: tuple[Token, ...],
    lines: list[str],
    source_file: Path,
    namespace_path: str,
) -> tuple[ProcEntry | None, list[ExtractorDiagnostic]]:
    """Turn a :class:`_ProcLayout` into a :class:`ProcEntry` plus any diagnostics.

    Returns ``(None, [...])`` for a computed proc name (``PW-01``). The proc
    is dropped from the index per §4.3 row 6.
    """
    diagnostics: list[ExtractorDiagnostic] = []

    name_tok = tokens[layout.name_idx]
    if _is_computed_name(name_tok.value):
        diagnostics.append(
            ExtractorDiagnostic(
                kind="computed-proc-name",
                line_no=name_tok.line_no,
                detail=name_tok.value,
            )
        )
        return None, diagnostics

    short_name, qualified_name = _resolve_qualified_name(name_tok.value, namespace_path)

    proc_tok = tokens[layout.proc_idx]
    start_line = proc_tok.line_no
    body_lbrace = tokens[layout.body_lbrace_idx]
    body_rbrace = tokens[layout.body_rbrace_idx]
    end_line = body_rbrace.line_no
    body_start_line = body_lbrace.line_no + 1
    body_end_line = body_rbrace.line_no - 1

    # §6.2 edge case for one-line procs: `proc foo {} { return 1 }` — all on
    # the same line. The table mandates body_start_line == body_end_line ==
    # start_line. Clamp the derived window back into the proc span.
    if body_lbrace.line_no == body_rbrace.line_no:
        body_start_line = body_lbrace.line_no
        body_end_line = body_rbrace.line_no

    # §4.7 backward comment-banner scan.
    comment_start, comment_end = _scan_comment_banner(lines, start_line)

    canonical_name = f"{source_file.as_posix()}::{qualified_name}"

    # Stage 1e: extract body references (calls + source_refs) now that the
    # body span is known. Per §5.1, the extractor operates on the already-
    # tokenized stream scoped to the body.
    calls, source_refs = extract_body_refs(
        tokens=tokens,
        body_lbrace_idx=layout.body_lbrace_idx,
        body_rbrace_idx=layout.body_rbrace_idx,
    )

    entry = ProcEntry(
        canonical_name=canonical_name,
        short_name=short_name,
        qualified_name=qualified_name,
        source_file=source_file,
        start_line=start_line,
        end_line=end_line,
        body_start_line=body_start_line,
        body_end_line=body_end_line,
        namespace_path=namespace_path,
        calls=calls,
        source_refs=source_refs,
        dpa_start_line=None,
        dpa_end_line=None,
        comment_start_line=comment_start,
        comment_end_line=comment_end,
    )
    return entry, diagnostics


def _with_dpa(entry: ProcEntry, dpa_start: int, dpa_end: int) -> ProcEntry:
    """Return a copy of ``entry`` with DPA span set.

    :class:`ProcEntry` is frozen, so we reconstruct via keyword args rather
    than mutate.
    """
    return ProcEntry(
        canonical_name=entry.canonical_name,
        short_name=entry.short_name,
        qualified_name=entry.qualified_name,
        source_file=entry.source_file,
        start_line=entry.start_line,
        end_line=entry.end_line,
        body_start_line=entry.body_start_line,
        body_end_line=entry.body_end_line,
        namespace_path=entry.namespace_path,
        calls=entry.calls,
        source_refs=entry.source_refs,
        dpa_start_line=dpa_start,
        dpa_end_line=dpa_end,
        comment_start_line=entry.comment_start_line,
        comment_end_line=entry.comment_end_line,
    )


# ---------------------------------------------------------------------------
# Name resolution (§4.3 / §4.3.1)
# ---------------------------------------------------------------------------


def _is_computed_name(raw_name: str) -> bool:
    """True iff the proc name contains an unresolvable substitution marker."""
    return any(m in raw_name for m in _COMPUTED_NAME_MARKERS)


def _resolve_qualified_name(raw_name: str, namespace_path: str) -> tuple[str, str]:
    """Resolve a proc name per §4.3 rules. Return ``(short_name, qualified_name)``.

    * Leading ``::`` → absolute name, namespace context is overridden.
    * Otherwise the active ``namespace_path`` is prefixed if non-empty.

    ``short_name`` is the rightmost ``::``-separated segment of the resolved
    qualified name. This matches the JSON ``procs`` matching contract:
    ``common/helpers.tcl`` with
    namespace ``["ns"]`` and name ``foo`` → ``short_name="foo"``,
    ``qualified_name="ns::foo"``.
    """
    if raw_name.startswith("::"):
        qualified = raw_name[2:]
    elif namespace_path:
        qualified = f"{namespace_path}::{raw_name}"
    else:
        qualified = raw_name
    short = qualified.rsplit("::", 1)[-1]
    return short, qualified


# ---------------------------------------------------------------------------
# Comment banner backward scan (§4.7)
# ---------------------------------------------------------------------------


def _scan_comment_banner(lines: list[str], start_line: int) -> tuple[int | None, int | None]:
    """Return (comment_start_line, comment_end_line) or (None, None).

    §4.7: contiguous ``^\\s*#`` lines immediately preceding ``start_line`` form
    the banner. A blank line or non-comment line breaks the banner.
    """
    end_line_0 = start_line - 2  # 0-indexed: the line immediately above the proc
    if end_line_0 < 0:
        return (None, None)
    if not _COMMENT_LINE_RE.match(lines[end_line_0]):
        return (None, None)
    start_line_0 = end_line_0
    while start_line_0 - 1 >= 0 and _COMMENT_LINE_RE.match(lines[start_line_0 - 1]):
        start_line_0 -= 1
    return (start_line_0 + 1, end_line_0 + 1)


# ---------------------------------------------------------------------------
# DPA forward scan (§4.6)
# ---------------------------------------------------------------------------


def _scan_dpa(
    lines: list[str],
    proc_end_line: int,
    qualified_name: str,
) -> tuple[int | None, int | None, list[ExtractorDiagnostic]]:
    """Return (dpa_start_line, dpa_end_line, diagnostics).

    Returns ``(None, None, [])`` when no DPA block is associated. Emits
    ``PW-11`` with ``(None, None, [...])`` when a DPA block is found but its
    proc name does not match ``qualified_name``.
    """
    diagnostics: list[ExtractorDiagnostic] = []
    n = len(lines)
    i = proc_end_line  # 0-indexed index of the line AFTER the proc close
    blanks = 0
    while i < n and lines[i].strip() == "" and blanks < _DPA_BLANK_LOOKAHEAD:
        blanks += 1
        i += 1
    if i >= n:
        return (None, None, diagnostics)
    if not _DPA_LINE_RE.match(lines[i]):
        return (None, None, diagnostics)

    dpa_start_0 = i
    dpa_end_0 = i
    # §4.6 step 3c: collect continuation lines while current ends with ``\``.
    while dpa_end_0 < n and _line_ends_with_continuation(lines[dpa_end_0]):
        dpa_end_0 += 1
        if dpa_end_0 >= n:
            break

    # Assemble the logical DPA command (continuation-joined for name extraction).
    joined = " ".join(line.rstrip("\\").rstrip() for line in lines[dpa_start_0 : dpa_end_0 + 1])
    dpa_name = _extract_dpa_proc_name(joined)
    if dpa_name != qualified_name:
        diagnostics.append(
            ExtractorDiagnostic(
                kind="dpa-name-mismatch",
                line_no=dpa_start_0 + 1,
                detail=f"DPA name '{dpa_name}' does not match preceding proc '{qualified_name}'",
            )
        )
        return (None, None, diagnostics)

    return (dpa_start_0 + 1, dpa_end_0 + 1, diagnostics)


def _line_ends_with_continuation(line: str) -> bool:
    """True iff ``line`` ends with an unescaped ``\\`` (continuation marker)."""
    stripped = line.rstrip("\r")
    if not stripped.endswith("\\"):
        return False
    # Count trailing backslashes — odd count means the final one is a continuation.
    k = 0
    while k < len(stripped) and stripped[-1 - k] == "\\":
        k += 1
    return k % 2 == 1


def _extract_dpa_proc_name(line: str) -> str:
    """Extract the proc name from a joined ``define_proc_attributes`` line.

    Tcl semantics: ``define_proc_attributes <proc_name> <option>...`` —
    the target proc name is the **first whitespace-delimited word**
    after the keyword. Anything after that (option flags, brace-quoted
    argument descriptors, possibly with nested ``{...}`` such as
    ``-define_args { {-clock ...} {-rptname ...} }``) is descriptor
    content and must NOT bleed into the name.

    The previous implementation tried to strip flags via regex, but
    ``\\{[^}]*\\}`` does not balance nested braces, so multi-line DPA
    blocks with nested arg descriptors absorbed the whole tail into
    the "name" and produced spurious PW-11 / PI-04 (see bug report
    ``PW-11_PI-04_dpa_line_continuation_misparse.md``).
    """
    # Strip CR / continuation backslash / leading whitespace.
    line = line.rstrip("\\\r\n").strip()
    # Strip the keyword prefix (everything up to and including
    # ``define_proc_(attributes|arguments)`` plus its trailing
    # whitespace).
    m = re.match(r"^.*?define_proc_(?:attributes|arguments)\s+", line)
    if m:
        line = line[m.end() :]
    # The proc name is the first whitespace-delimited token. Strip a
    # leading ``::`` per §4.3.1 absolute-name rule.
    name = line.split(None, 1)[0] if line else ""
    if name.startswith("::"):
        name = name[2:]
    return name


# ---------------------------------------------------------------------------
# Duplicate short-name dedup (§6.3)
# ---------------------------------------------------------------------------


def _deduplicate_short_names(
    procs: list[ProcEntry],
) -> tuple[list[ProcEntry], list[ExtractorDiagnostic]]:
    """Per-file duplicate detection. Last definition wins (Invariant 4).

    Walks ``procs`` in source order (caller guarantees this), identifies
    duplicate ``short_name`` groups, emits one ``PE-01`` per duplicate (at the
    *last* definition's ``start_line`` so the diagnostic points at the entry
    that survived), and returns only the surviving entries.
    """
    diagnostics: list[ExtractorDiagnostic] = []
    by_short: dict[str, list[ProcEntry]] = {}
    for p in procs:
        by_short.setdefault(p.short_name, []).append(p)

    survivors: list[ProcEntry] = []
    for short, group in by_short.items():
        if len(group) > 1:
            # Keep the last definition; emit one PE-01 carrying both line refs.
            last = group[-1]
            first = group[0]
            diagnostics.append(
                ExtractorDiagnostic(
                    kind="duplicate-proc-definition",
                    line_no=last.start_line,
                    detail=(
                        f"Duplicate proc '{short}' — first definition at line "
                        f"{first.start_line}, last definition at line {last.start_line} "
                        f"(used for index)"
                    ),
                )
            )
            survivors.append(last)
        else:
            survivors.append(group[0])
    return survivors, diagnostics
