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

    i = body_lbrace_idx + 1
    while i < body_rbrace_idx:
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
