"""Call and ``source``-ref extractor.

Coupled to :mod:`chopper.parser.proc_extractor`: once proc body spans
are known, this module walks tokens inside each body to produce:

* ``calls``       — tuple of deduplicated, lex-sorted proc-call tokens.
* ``source_refs`` — tuple of literal paths from ``source`` /
  ``iproc_source`` commands (source order, no dedup).

Both tuples live on :class:`ProcEntry`.

Extraction rules:

1. **Scope.** Only command-position WORD tokens inside a proc body
   (tracked via :class:`NamespaceTracker`'s ``PROC_BODY`` frame) are
   candidates. Nested brackets, control-flow bodies, and embedded
   braces are traversed.
2. **First word only.** Never treat second-or-later tokens as calls
   (prevents the ``define_proc_attributes <name>`` false-positive trap).
3. **Suppression cascade.** A four-level filter rejects comment lines,
   log-proc string arguments, option-flag arguments, and variable
   references.
4. **File dependencies.** ``source <path>`` and
   ``iproc_source -file <path>`` yield :attr:`source_refs` entries.
   Literal paths only; computed paths are silently skipped.
5. **Bracketed sub-calls.** ``[<callable> ...]`` patterns embedded in
   WORD tokens yield the inner first word as an additional candidate.

Pure module: no I/O, no :class:`ChopperContext`. Driven from within
:func:`extract_procs`.
"""

from __future__ import annotations

import re

from .tokenizer import Token, TokenKind

__all__ = [
    "EDA_FLOW_COMMANDS",
    "LOG_PROC_NAMES",
    "TCL_BUILTINS",
    "extract_body_refs",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# §5.5 Level 3 — log-proc names. Candidate call tokens that appear ONLY
# inside the string arguments of these procs are suppressed.
LOG_PROC_NAMES: frozenset[str] = frozenset(
    {
        "iproc_msg",
        "puts",
        "echo",
        "print_info",
        "print_warning",
        "print_error",
        "print_fatal",
        "rdt_print_info",
        "rdt_print_warn",
        "rdt_print_error",
        "log_message",
        "printvar",
        "time_stamp",
    }
)


# §5.5 — Synopsys/Cadence EDA flow control commands. These are first-word
# commands that are NOT user procs; they are extracted as call candidates
# and produce ``TW-02`` at trace time by design (the domain owner is
# informed, trim proceeds). The extractor does not suppress them — it is
# the tracer's job to classify them.
EDA_FLOW_COMMANDS: frozenset[str] = frozenset(
    {
        "vpx",
        "vpxmode",
        "tclmode",
        "redirect",
        "tcl_set_command_name_echo",
        "annotate_trace",
        "current_design",
        "current_container",
        "set_top",
        "read_verilog",
        "read_sverilog",
        "read_db",
        "set_app_var",
        "get_app_var",
    }
)


# Tcl built-in commands — suppressed at extraction time. These never
# appear in a Chopper domain's user-proc index, so they would always
# produce ``TW-02`` and pollute every trace report. The SNORT approach
# filters them at parse time.
TCL_BUILTINS: frozenset[str] = frozenset(
    {
        # Flow control (also handled structurally by NamespaceTracker, but
        # listed here for completeness — control-flow tokens that escape
        # the tracker because of nesting shape must not surface as calls).
        "if",
        "elseif",
        "else",
        "for",
        "foreach",
        "foreach_in_collection",
        "while",
        "switch",
        "catch",
        "try",
        "eval",
        "return",
        "break",
        "continue",
        "error",
        # Core I/O / data.
        "set",
        "unset",
        "incr",
        "append",
        "lappend",
        "lset",
        "lindex",
        "llength",
        "lrange",
        "lreplace",
        "lsearch",
        "lsort",
        "list",
        "dict",
        "array",
        "string",
        "format",
        "scan",
        "regexp",
        "regsub",
        "split",
        "join",
        "expr",
        "concat",
        # Namespaces and procs.
        "proc",
        "namespace",
        "variable",
        "global",
        "upvar",
        "uplevel",
        "info",
        "rename",
        "interp",
        # Files and I/O.
        "open",
        "close",
        "read",
        "gets",
        "puts",
        "file",
        "glob",
        "pwd",
        "cd",
        "exec",
        # Misc.
        "source",  # handled via source_refs extraction; never a call edge
        "iproc_source",
        "define_proc_attributes",
        "define_proc_arguments",
        "package",
        "clock",
        "after",
        "trace",
    }
)


# A candidate proc name must match this regex (§5.3 step 3a/3b). Absolute
# ``::``-prefixed names are accepted — the leading ``::`` is stripped.
_BARE_NAME_RE = re.compile(r"^(?:::)?[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*$")

# Tokens containing any of these markers are "dynamic" (§5.2): `$cmd`,
# `${var}`, `[...]`. They are not extracted as calls (the service layer
# may emit ``PW-03`` / ``TW-03`` at resolution time).
_DYNAMIC_MARKERS_RE = re.compile(r"[\$]")

# Bracketed sub-call pattern: opens with ``[``, captures the first word.
# Used to recurse into embedded command substitutions inside WORD tokens
# that the tokenizer kept as a single literal (e.g. quoted strings).
_BRACKET_CALL_RE = re.compile(r"\[\s*((?:::)?[A-Za-z_][A-Za-z0-9_:]*)")

# ``source`` / ``iproc_source`` detection — first word of a command.
_SOURCE_KEYWORDS: frozenset[str] = frozenset({"source", "iproc_source"})

# ``iproc_source`` option flags that precede the file-path argument.
_IPROC_SOURCE_FLAGS: frozenset[str] = frozenset(
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

# ``source`` option flags.
_SOURCE_FLAGS: frozenset[str] = frozenset({"-echo", "-verbose", "-nocomplain", "-quiet"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def extract_body_refs(
    tokens: tuple[Token, ...],
    body_lbrace_idx: int,
    body_rbrace_idx: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extract ``(calls, source_refs)`` for one proc body.

    :param tokens: Full token stream from :func:`chopper.parser.tokenizer.tokenize`.
    :param body_lbrace_idx: Index of the body opening ``LBRACE`` (NOT included).
    :param body_rbrace_idx: Index of the body closing ``RBRACE`` (NOT included).
    :returns: ``(calls, source_refs)``. ``calls`` is deduplicated and
        lexicographically sorted (§6.1 invariant 5). ``source_refs`` is in
        source order without dedup (§6.1 invariant 6).

    The range scanned is ``tokens[body_lbrace_idx + 1 : body_rbrace_idx]``
    — the proc body content, excluding the opening and closing braces.
    If ``body_lbrace_idx + 1 >= body_rbrace_idx`` (empty body), returns
    ``((), ())``.

    Algorithm:

    1. Walk every token in the body range.
    2. For a command-position WORD token, classify the first word: add to
       ``calls`` if it is a real user-proc call. Apply §5.5 suppression.
       If the first word starts a ``source`` / ``iproc_source`` command,
       extract the literal path into ``source_refs`` and mark the command
       tokens so they are not double-scanned for bracket calls.
    3. For every WORD token (whether command-position or argument),
       scan its text value for embedded ``[<call> ...]`` patterns and add
       the first word inside the brackets as a call candidate. This
       handles §5.3 step 4 uniformly — including the §5.5 Level 3
       exception for bracket calls inside log-proc strings.
    4. Tokens consumed as part of a ``source`` / ``iproc_source`` argument
       are skipped to avoid double-counting the path token as a call.

    The tokenizer's :attr:`Token.at_command_position` flag already marks
    real first-of-command words — control-flow body openers re-establish
    it inside their braces — so the outer walk never needs to ``skip to
    command boundary''. Keeping the walk uniform avoids the off-by-one
    traps that come with depth-based command skipping.
    """
    if body_lbrace_idx + 1 >= body_rbrace_idx:
        return (), ()

    calls: set[str] = set()
    source_refs: list[str] = []
    # Indices consumed as args to a ``source`` / ``iproc_source`` command.
    consumed: set[int] = set()
    # Command starts at which the first word itself must be treated as
    # suppressed (so we do not classify it) — for source/iproc_source.
    source_cmd_starts: set[int] = set()

    # Pre-pass: mark token indices that must be skipped because they are
    # contents of an opaque braced argument (regex/exec/string-match
    # pattern, etc.) or a switch pattern label. See `_compute_skip_indices`.
    skip_indices = _compute_skip_indices(tokens, body_lbrace_idx, body_rbrace_idx)

    i = body_lbrace_idx + 1
    while i < body_rbrace_idx:
        if i in skip_indices:
            i += 1
            continue
        tok = tokens[i]
        if tok.kind is TokenKind.WORD and tok.at_command_position:
            first_word = tok.value
            if first_word in _SOURCE_KEYWORDS:
                # §5.4 — extract literal path; skip path token in the free
                # bracket scan below so `source a.tcl` does not leak `a.tcl`
                # into calls. `source` itself is in TCL_BUILTINS so
                # _classify would reject it anyway, but explicit here.
                path, consumed_indices = _extract_source_path_with_indices(tokens, i, body_rbrace_idx, first_word)
                if path is not None:
                    source_refs.append(path)
                consumed.update(consumed_indices)
                source_cmd_starts.add(i)
                i += 1
                continue

            if not _should_suppress_first_word(first_word):
                candidate = _classify_call_candidate(first_word)
                if candidate is not None:
                    calls.add(candidate)
            # Fall through: still bracket-scan this token's value below.
        # Free bracket scan: any WORD token (command-position or not) may
        # contain embedded [<call>...] substitutions. Skip tokens that
        # were consumed as a source/iproc_source path argument.
        if tok.kind is TokenKind.WORD and i not in consumed:
            for match in _BRACKET_CALL_RE.finditer(tok.value):
                candidate = _classify_call_candidate(match.group(1))
                if candidate is not None:
                    calls.add(candidate)
        i += 1

    return tuple(sorted(calls)), tuple(source_refs)


# ---------------------------------------------------------------------------
# First-word classification (§5.3 step 3)
# ---------------------------------------------------------------------------


def _classify_call_candidate(word: str) -> str | None:
    """Return the canonical call-token form, or ``None`` to reject.

    Accepts bare / ``::``-qualified identifiers. Strips a single leading
    ``::``. Rejects dynamic names (``$cmd``, ``${var}``, ``[cmd]``), Tcl
    built-ins, and anything not matching :data:`_BARE_NAME_RE`.
    """
    if "$" in word or word.startswith("["):
        return None
    normalized = word[2:] if word.startswith("::") else word
    if not _BARE_NAME_RE.match(word):
        return None
    if normalized in TCL_BUILTINS:
        return None
    return normalized


# ---------------------------------------------------------------------------
# Suppression cascade (§5.5 levels 2a–2g)
# ---------------------------------------------------------------------------


def _should_suppress_first_word(first_word: str) -> bool:
    """SNORT §5.5 — return True if this first-word candidate must be suppressed.

    Level 2a (comment lines) is eliminated structurally by the tokenizer
    — COMMENT tokens never appear at command position. The remaining
    levels are identifier-based and implemented here.

    Tcl builtins are handled separately by :func:`_classify_call_candidate`
    via the :data:`TCL_BUILTINS` set; the checks below cover EDA-specific
    commands that are NOT builtins but still must not surface as calls.
    """
    # Level 3: log procs — the log proc itself is not a user proc.
    if first_word in LOG_PROC_NAMES:
        return True
    # Level 2d: EDA app-var commands (not in TCL_BUILTINS, but not calls).
    if first_word in ("set_app_var", "get_app_var"):
        return True
    return False


# ---------------------------------------------------------------------------
# source / iproc_source path extraction (§5.4)
# ---------------------------------------------------------------------------


def _extract_source_path_with_indices(
    tokens: tuple[Token, ...],
    keyword_idx: int,
    limit_idx: int,
    keyword: str,
) -> tuple[str | None, set[int]]:
    """Return ``(path, consumed_indices)`` for a ``source`` / ``iproc_source`` command.

    ``path`` is ``None`` if the path argument is dynamic (``$var`` /
    ``[cmd]``) or the command is malformed. ``consumed_indices`` contains
    every token index from ``keyword_idx + 1`` up to and including the
    path argument — so the caller can skip them in its free bracket-scan
    pass. Tokens past the path are NOT consumed (the caller continues
    its walk from ``keyword_idx + 1`` normally).
    """
    flags = _IPROC_SOURCE_FLAGS if keyword == "iproc_source" else _SOURCE_FLAGS
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
            if _is_dynamic_path(value):
                consumed.add(i)
                return None, consumed
            consumed.add(i)
            return _strip_quotes(value), consumed
        i += 1
    return None, consumed


def _is_dynamic_path(value: str) -> bool:
    """True if the token cannot be resolved statically to a path."""
    if "$" in value:
        return True
    if value.startswith("[") or "[" in value:
        return True
    return False


def _strip_quotes(value: str) -> str:
    """Strip a single surrounding pair of double quotes or braces if present."""
    if len(value) >= 2:
        if value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        if value[0] == "{" and value[-1] == "}":
            return value[1:-1]
    return value


# ---------------------------------------------------------------------------
# Structural pre-pass — opaque braces and switch patterns
# ---------------------------------------------------------------------------


# Commands whose ``{...}`` arguments are LITERAL strings, not Tcl source.
# The contents of these braces must not be walked for proc-call extraction
# (they are typically regular expressions, glob patterns, or external
# command lines passed verbatim to a system program).
#
# References:
# * Tcl ``regexp`` / ``regsub`` (n) man pages — pattern argument is a
#   regular expression, not Tcl source.
# * ``string match`` (n) — pattern is a glob, not Tcl.
# * ``exec`` — argv tokens are passed to a child process; brace-quoted
#   arguments are commonly grep/awk/sed regex literals.
# * ``glob`` — pattern is a glob.
# * ``after``, ``binary scan`` — format strings, not Tcl.
_OPAQUE_BRACE_COMMANDS: frozenset[str] = frozenset(
    {
        "regexp",
        "regsub",
        "exec",
        "glob",
    }
)


# Commands whose ``{...}`` arguments contain Tcl code that must be
# recursively scanned by the structural pre-pass. Without this list, an
# opaque command nested inside (for example) ``if {[catch {exec grep -P
# {...}} ]}`` would never be discovered because its ``[exec`` reference
# lives inside a body brace whose contents are not at command position.
# Recursing the pre-pass into these bodies finds those nested commands.
_CODE_BRACE_COMMANDS: frozenset[str] = frozenset(
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


def _compute_skip_indices(
    tokens: tuple[Token, ...],
    body_lbrace_idx: int,
    body_rbrace_idx: int,
) -> set[int]:
    """Identify token indices the extractor must skip during the body walk.

    Three structural cases produce skips:

    1. **Opaque braced arguments** to commands in
       :data:`_OPAQUE_BRACE_COMMANDS` (regex/exec/glob/string-match).
       The full ``{ ... }`` range (LBRACE through matching RBRACE,
       inclusive) is marked skip so embedded ``|`` / ``[abc]`` regex
       characters do not leak into call extraction (bug
       ``TW-02_regex_literal_misparse.md``).

    2. **Recursive descent into Tcl code blocks** (:data:`_CODE_BRACE_COMMANDS`:
       ``if``, ``catch``, ``while``, ``foreach``, etc.). The body
       brace's contents ARE Tcl code, so we recursively pre-pass the
       inner range to discover any nested opaque/switch commands.
       Without this, an ``exec`` inside ``[catch {exec grep -P {...}}]``
       is never found because nothing in the inner range is at command
       position from the outer pre-pass's point of view.

    3. **switch pattern labels.** Inside ``switch <expr> { ... }``,
       the WORD tokens at the body brace's inner depth are pattern
       labels or the ``-`` fall-through marker, never proc invocations
       (bug ``TW-02_switch_pattern_label_misparse.md``).
    """
    skip: set[int] = set()
    _scan_command_range(tokens, body_lbrace_idx + 1, body_rbrace_idx, skip)
    return skip


def _scan_command_range(
    tokens: tuple[Token, ...],
    start: int,
    end: int,
    skip: set[int],
) -> None:
    """Pre-pass over a Tcl-code range, populating ``skip`` in-place.

    Discovers command-position WORD tokens, classifies them against
    the opaque/code/switch sets, and either marks brace ranges
    skipped, recurses into code-block bodies, or marks switch pattern
    labels — depending on classification.

    Also scans every WORD value for ``[<cmd>`` substitutions; if the
    inner ``<cmd>`` is opaque/code/switch, the next ``{...}`` at the
    surrounding depth receives the same treatment as a command-position
    invocation.

    Tcl semantics correction: when the pre-pass enters a code-block
    body brace (e.g. the body of ``catch {script}`` or ``if
    {condition}``), the contents START at command position regardless
    of the tokenizer's ``at_command_position`` flag (the tokenizer
    flips that flag off on every LBRACE because it cannot know whether
    a brace introduces a value or a script). The pre-pass therefore
    treats the FIRST WORD it encounters at the range's enclosing depth
    as cmd-position — and similarly for the first WORD after every
    NEWLINE / SEMICOLON at that depth.
    """
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
            cmd_end = _find_command_end(tokens, i + 1, end, base_depth)
            is_cmd_pos = (
                tok.at_command_position
                or (expecting_cmd and base_depth == enclosing_depth)
            )
            if is_cmd_pos and i not in skip:
                _classify_and_handle(tokens, tok.value, i + 1, cmd_end, base_depth, skip)
                expecting_cmd = False
            for m in _INNER_CMD_RE.finditer(tok.value):
                inner_cmd = m.group(1)
                _classify_and_handle(tokens, inner_cmd, i + 1, cmd_end, base_depth, skip)
        elif tok.kind is TokenKind.LBRACE or tok.kind is TokenKind.RBRACE:
            # Brace tokens never reset cmd expectation; they are
            # part of an argument or close the enclosing scope.
            pass
        i += 1


def _classify_and_handle(
    tokens: tuple[Token, ...],
    cmd: str,
    arg_start: int,
    arg_end: int,
    depth: int,
    skip: set[int],
) -> None:
    """Apply opaque/code/switch handling for one (possibly inner) command."""
    if cmd in _OPAQUE_BRACE_COMMANDS:
        _mark_opaque_arg_braces(tokens, arg_start, arg_end, depth, skip)
    elif cmd == "string":
        if _is_string_match(tokens, arg_start, arg_end):
            _mark_opaque_arg_braces(tokens, arg_start, arg_end, depth, skip)
    elif cmd == "switch":
        _mark_switch_pattern_words(tokens, arg_start, arg_end, depth, skip)
    elif cmd in _CODE_BRACE_COMMANDS:
        # Recurse into every ``{...}`` argument at this depth — those
        # contents are Tcl code that may contain further opaque / switch
        # / nested code-block commands.
        j = arg_start
        while j < arg_end:
            t = tokens[j]
            if t.kind is TokenKind.LBRACE and t.brace_depth == depth:
                rbrace = _matching_rbrace(tokens, j, arg_end)
                if rbrace is not None:
                    _scan_command_range(tokens, j + 1, rbrace, skip)
                    j = rbrace + 1
                    continue
            j += 1


# Match ``[<cmd>`` openings inside a WORD value. ``<cmd>`` is captured
# without ``::`` qualifiers; this is sufficient because all the
# classified commands (opaque + code-block + switch + ``string``) are
# global builtins. Quoting/escape cases (``\[``) are handled at the
# tokenizer layer; by the time we see a WORD value, the ``\[`` character
# pair is preserved verbatim and matches harmlessly (the inner cmd then
# fails classification).
_INNER_CMD_RE = re.compile(r"\[\s*([A-Za-z_][A-Za-z_0-9]*)")


def _find_command_end(
    tokens: tuple[Token, ...],
    start: int,
    limit: int,
    base_depth: int,
) -> int:
    """Return the exclusive index where this command ends.

    A command terminates at the first NEWLINE or SEMICOLON whose
    ``brace_depth`` equals ``base_depth`` (the depth at which the
    command's first word lives). Tokens deeper than ``base_depth`` are
    inside arguments and do not terminate the command.
    """
    j = start
    while j < limit:
        t = tokens[j]
        if (t.kind is TokenKind.NEWLINE or t.kind is TokenKind.SEMICOLON) and t.brace_depth == base_depth:
            return j
        j += 1
    return limit


def _mark_opaque_arg_braces(
    tokens: tuple[Token, ...],
    start: int,
    end: int,
    base_depth: int,
    skip: set[int],
) -> None:
    """Mark every ``{...}`` argument of the current command as opaque.

    A ``{...}`` argument's LBRACE has ``brace_depth == base_depth``
    (depth before the brace increments it). Walks the command range,
    finds each such LBRACE, locates the matching RBRACE by depth, and
    adds every token index in ``[lbrace, rbrace]`` (inclusive) to
    ``skip``.
    """
    j = start
    while j < end:
        t = tokens[j]
        if t.kind is TokenKind.LBRACE and t.brace_depth == base_depth:
            rbrace = _matching_rbrace(tokens, j, end)
            if rbrace is not None:
                for k in range(j, rbrace + 1):
                    skip.add(k)
                j = rbrace + 1
                continue
        j += 1


def _mark_switch_pattern_words(
    tokens: tuple[Token, ...],
    start: int,
    end: int,
    base_depth: int,
    skip: set[int],
) -> None:
    """Mark ``switch`` pattern-label WORDs inside the body brace as skip.

    The body brace is the LAST LBRACE at ``base_depth`` before
    ``end``. Inside it, WORD tokens at ``base_depth + 1`` are pattern
    labels or the ``-`` fall-through marker; bodies are nested
    ``{...}`` blocks whose code lives at ``base_depth + 2`` and is left
    walkable.
    """
    body_lbrace = _last_lbrace_at_depth(tokens, start, end, base_depth)
    if body_lbrace is None:
        return
    body_rbrace = _matching_rbrace(tokens, body_lbrace, end)
    if body_rbrace is None:
        return
    inner_depth = base_depth + 1
    for j in range(body_lbrace + 1, body_rbrace):
        t = tokens[j]
        if t.kind is TokenKind.WORD and t.brace_depth == inner_depth:
            skip.add(j)


def _matching_rbrace(tokens: tuple[Token, ...], lbrace_idx: int, limit: int) -> int | None:
    """Find the index of the RBRACE matching ``tokens[lbrace_idx]``."""
    depth_after_open = tokens[lbrace_idx].brace_depth + 1
    j = lbrace_idx + 1
    while j < limit:
        t = tokens[j]
        # Per Token docstring, RBRACE.brace_depth is the enclosing-scope
        # depth (depth AFTER the close), so the matching RBRACE has
        # ``brace_depth == depth_after_open - 1 == lbrace.brace_depth``.
        if t.kind is TokenKind.RBRACE and t.brace_depth == depth_after_open - 1:
            return j
        j += 1
    return None


def _last_lbrace_at_depth(
    tokens: tuple[Token, ...], start: int, end: int, depth: int
) -> int | None:
    """Return the index of the LAST LBRACE within [start, end) at ``depth``."""
    last: int | None = None
    j = start
    while j < end:
        t = tokens[j]
        if t.kind is TokenKind.LBRACE and t.brace_depth == depth:
            last = j
        j += 1
    return last


def _is_string_match(tokens: tuple[Token, ...], start: int, end: int) -> bool:
    """True iff this ``string`` command is ``string match ...``."""
    j = start
    while j < end:
        t = tokens[j]
        if t.kind is TokenKind.WORD:
            return t.value == "match"
        j += 1
    return False
