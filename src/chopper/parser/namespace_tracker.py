"""Context + namespace tracker.

Consumes the tokenizer stream and maintains two stacks:

* **Context stack** — one :class:`ContextFrame` per open brace block plus
  an implicit :attr:`ContextKind.FILE_ROOT` bottom. Determines whether a
  ``proc`` keyword at command position is a real definition
  (only ``FILE_ROOT`` and ``NAMESPACE_EVAL`` allow it).
* **Namespace stack** — tracks active ``namespace eval`` nesting so the
  proc extractor can qualify proc names.

Stateful utility driven by a caller feeding tokens one at a time. Owns
**no** :class:`ChopperContext` knowledge — diagnostics are collected
into :attr:`diagnostics` for the service layer to translate into
``PW-04 computed-namespace-name``.

Interaction with the proc extractor:

1. The extractor calls :meth:`feed` for each token.
2. When it spots a ``proc`` keyword and :meth:`can_define_proc` is
   true, it consumes the name / args tokens and calls
   :meth:`mark_proc_body_opening` **before** feeding the body ``LBRACE``.
   The resulting frame is labelled :attr:`ContextKind.PROC_BODY`.

The tracker never emits ``PE-02`` — structural brace errors are the
tokenizer's responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from .tokenizer import Token, TokenKind

__all__ = [
    "ContextFrame",
    "ContextKind",
    "NamespaceTracker",
    "TrackerDiagnostic",
]


# Control-flow openers.
_CONTROL_FLOW_KEYWORDS: frozenset[str] = frozenset(
    {
        "if",
        "elseif",
        "else",
        "for",
        "foreach",
        "foreach_in_collection",  # Synopsys EDA iterator (§7.14, P-36)
        "while",
        "switch",
        "catch",
        "eval",
    }
)


class ContextKind(StrEnum):
    """The kind of brace-delimited block on the context stack.

    Only :attr:`FILE_ROOT` and :attr:`NAMESPACE_EVAL` permit top-level
    proc recognition. :attr:`CONTROL_FLOW`, :attr:`PROC_BODY`, and
    :attr:`OTHER` all suppress it.
    """

    FILE_ROOT = "FILE_ROOT"
    NAMESPACE_EVAL = "NAMESPACE_EVAL"
    CONTROL_FLOW = "CONTROL_FLOW"
    PROC_BODY = "PROC_BODY"
    OTHER = "OTHER"
    """Anonymous brace block — data literal, expression, args word, etc."""


@dataclass(frozen=True)
class ContextFrame:
    """One entry on the context stack."""

    kind: ContextKind
    entered_at_depth: int
    """Brace depth **before** this frame's opening ``LBRACE`` was consumed.

    The frame is popped when the tracker's depth returns to this value after
    the matching ``RBRACE`` is consumed.
    """

    namespace_name: str | None = None
    """Literal namespace name (``::`` stripped) for :attr:`ContextKind.NAMESPACE_EVAL`; ``None`` otherwise."""


@dataclass(frozen=True)
class TrackerDiagnostic:
    """A tracker-level observation the service layer maps to a registered code.

    Currently the tracker only emits ``computed-namespace-name`` (``PW-04``)
    when ``namespace eval`` is used with a substituted name that cannot be
    statically resolved.
    """

    kind: Literal["computed-namespace-name"]
    line_no: int
    detail: str


# The command-position words we track for opener detection. A short sliding
# window is sufficient: we only care about the first three words of the
# current command (``namespace eval <name>``) or the first word alone
# (control-flow keywords, ``proc``).
_MAX_TRACKED_WORDS = 3


@dataclass
class NamespaceTracker:
    """Stateful consumer of :class:`Token` that maintains context + namespace stacks.

    Feed tokens via :meth:`feed`. Query state via the read-only properties and
    :meth:`can_define_proc`. Emit :class:`TrackerDiagnostic` on observations
    requiring a service-layer diagnostic translation.
    """

    _stack: list[ContextFrame] = field(default_factory=list)
    _namespace_stack: list[str] = field(default_factory=list)
    _depth: int = 0
    _cmd_words: list[Token] = field(default_factory=list)
    _pending_kind: ContextKind | None = None
    _pending_namespace: str | None = None
    _in_control_flow_command: bool = False
    """Sticky flag: every ``LBRACE`` until command-terminator gets ``CONTROL_FLOW``.

    Control-flow commands routinely take multiple brace words
    (``if {cond} {body}``, ``foreach v {list} {body}``). Each of those braces
    must suppress proc recognition equally, so the opener classification
    persists across the command.
    """
    _diagnostics: list[TrackerDiagnostic] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self._stack:
            self._stack.append(ContextFrame(ContextKind.FILE_ROOT, 0))

    # -- Public query surface ------------------------------------------------

    @property
    def depth(self) -> int:
        """Current brace depth as observed from the token stream."""
        return self._depth

    @property
    def top(self) -> ContextFrame:
        """Top of the context stack. Always at least :attr:`ContextKind.FILE_ROOT`."""
        return self._stack[-1]

    @property
    def namespace_stack(self) -> tuple[str, ...]:
        """Current active ``namespace eval`` nesting (innermost last)."""
        return tuple(self._namespace_stack)

    @property
    def namespace_path(self) -> str:
        """``::``-joined namespace path, e.g. ``"a::b"`` or ``""`` at file root."""
        return "::".join(self._namespace_stack)

    @property
    def diagnostics(self) -> tuple[TrackerDiagnostic, ...]:
        """Diagnostics accumulated during feeding."""
        return tuple(self._diagnostics)

    def can_define_proc(self) -> bool:
        """True iff a ``proc`` keyword here would be a top-level definition.

        Only :attr:`ContextKind.FILE_ROOT` and
        :attr:`ContextKind.NAMESPACE_EVAL` contexts allow it.
        """
        return self.top.kind in (ContextKind.FILE_ROOT, ContextKind.NAMESPACE_EVAL)

    # -- Stage 1d cooperation ------------------------------------------------

    def mark_proc_body_opening(self) -> None:
        """Signal that the next :attr:`TokenKind.LBRACE` fed opens a proc body.

        Called by the proc extractor (Stage 1d) after it has confirmed a
        ``proc NAME ARGS`` sequence and located the body ``{``. The next
        ``LBRACE`` will produce a :attr:`ContextKind.PROC_BODY` frame.
        Cleared on the next frame push regardless.
        """
        self._pending_kind = ContextKind.PROC_BODY
        self._pending_namespace = None

    # -- Token feeding -------------------------------------------------------

    def feed(self, token: Token) -> None:
        """Consume one token and update state.

        Callers must feed tokens in source order. Feeding an ``LBRACE`` pushes
        a context frame; feeding the matching ``RBRACE`` pops it. ``WORD``
        tokens at command position seed the opener-detection state machine.

        :raises ValueError: if an ``RBRACE`` is fed when depth is already 0
            (which the tokenizer would have already flagged as a
            ``negative_depth`` error — callers are expected to abort on
            tokenizer errors rather than pass them through to the tracker).
        """
        kind = token.kind
        if kind is TokenKind.LBRACE:
            self._handle_lbrace()
            return
        if kind is TokenKind.RBRACE:
            self._handle_rbrace()
            return
        if kind is TokenKind.NEWLINE or kind is TokenKind.SEMICOLON:
            self._cmd_words = []
            self._pending_kind = None
            self._pending_namespace = None
            self._in_control_flow_command = False
            return
        if kind is TokenKind.COMMENT:
            # Comments appear at command position and terminate the current
            # command's word sequence.
            self._cmd_words = []
            self._pending_kind = None
            self._pending_namespace = None
            self._in_control_flow_command = False
            return
        if kind is TokenKind.WORD:
            self._handle_word(token)
            return

    # -- Internal handlers ---------------------------------------------------

    def _handle_word(self, token: Token) -> None:
        if token.at_command_position:
            # A new command has started; reset the sliding window to this word.
            self._cmd_words = [token]
            self._pending_namespace = None
            if token.value in _CONTROL_FLOW_KEYWORDS:
                self._pending_kind = ContextKind.CONTROL_FLOW
                self._in_control_flow_command = True
            else:
                self._pending_kind = None
                self._in_control_flow_command = False
            return
        # Continuation of the current command — extend the window.
        if self._cmd_words:
            self._cmd_words.append(token)
            if len(self._cmd_words) > _MAX_TRACKED_WORDS:
                # Drop the oldest to bound memory; only the first three matter
                # for ``namespace eval <name>`` detection.
                self._cmd_words = self._cmd_words[-_MAX_TRACKED_WORDS:]
            self._check_namespace_eval()

    def _check_namespace_eval(self) -> None:
        """Recognise the ``namespace eval <name>`` opener pattern."""
        if len(self._cmd_words) < 3:
            return
        first, second, third = self._cmd_words[0], self._cmd_words[1], self._cmd_words[2]
        if first.value != "namespace" or second.value != "eval":
            return
        raw_name = third.value
        if _looks_computed(raw_name):
            self._diagnostics.append(
                TrackerDiagnostic(
                    kind="computed-namespace-name",
                    line_no=third.line_no,
                    detail=raw_name,
                )
            )
            # Spec §4.5 rule 7: body is NOT parsed for procs. The next LBRACE
            # pushes :attr:`ContextKind.OTHER` so proc recognition is suppressed.
            self._pending_kind = ContextKind.OTHER
            self._pending_namespace = None
            return
        self._pending_kind = ContextKind.NAMESPACE_EVAL
        self._pending_namespace = _strip_leading_colons(raw_name)

    def _handle_lbrace(self) -> None:
        if self._pending_kind is not None:
            kind = self._pending_kind
        elif self._in_control_flow_command:
            kind = ContextKind.CONTROL_FLOW
        else:
            kind = ContextKind.OTHER
        namespace_name = self._pending_namespace if kind is ContextKind.NAMESPACE_EVAL else None
        frame = ContextFrame(kind=kind, entered_at_depth=self._depth, namespace_name=namespace_name)
        self._stack.append(frame)
        if kind is ContextKind.NAMESPACE_EVAL and namespace_name is not None:
            self._namespace_stack.append(namespace_name)
        self._depth += 1
        # Pending opener (if any) has been consumed; reset for the next brace.
        # The sticky control-flow flag persists until the command terminates
        # via NEWLINE / SEMICOLON / COMMENT.
        self._pending_kind = None
        self._pending_namespace = None
        # A new brace-delimited block starts a fresh command-position context
        # inside it; the parent command's sliding window is no longer relevant.
        self._cmd_words = []

    def _handle_rbrace(self) -> None:
        if self._depth <= 0:
            raise ValueError(
                "NamespaceTracker: RBRACE at depth 0. The tokenizer should have reported "
                "this as a 'negative_depth' error; callers must not pass through a token "
                "stream with tokenizer errors."
            )
        self._depth -= 1
        top = self._stack[-1]
        if self._depth == top.entered_at_depth and top.kind is not ContextKind.FILE_ROOT:
            self._stack.pop()
            if top.kind is ContextKind.NAMESPACE_EVAL:
                # The namespace stack always tracks NAMESPACE_EVAL frames 1:1
                # because `namespace eval` with a computed name does NOT push
                # NAMESPACE_EVAL (it pushes OTHER) and does NOT push the
                # namespace onto the namespace stack.
                if self._namespace_stack:
                    self._namespace_stack.pop()
        # RBRACE terminates the enclosing command's word sequence.
        self._cmd_words = []
        self._pending_kind = None
        self._pending_namespace = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _looks_computed(name: str) -> bool:
    """True if the namespace name contains a substitution marker.

    ``$`` and ``[`` are unambiguous; even if the tokenizer would leave them
    literal inside a brace, at command position they indicate an unresolvable
    computed name.
    """
    return "$" in name or "[" in name


def _strip_leading_colons(name: str) -> str:
    """Strip a single ``::`` prefix; leave other ``::`` segments intact."""
    if name.startswith("::"):
        return name[2:]
    return name
