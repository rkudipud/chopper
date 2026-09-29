"""Uniform provenance comment markers for F2 (procs) and F3 (steps/stages).

See ``technical_docs/ARCHITECTURE.md`` Sec.3.11 for the authoritative
spec. Both callers (``trimmer/proc_dropper.py`` for F2,
``compiler/flow_resolver.py`` for F3) render markers through
:func:`marker_pair` so the grammar has exactly one implementation.
"""

from __future__ import annotations

from typing import Literal

__all__ = ["Action", "Kind", "marker_pair"]

Action = Literal["kept", "removed", "added", "replaced"]
Kind = Literal["proc", "step", "stage"]

# Backslash first so the escapes added after it are not doubled. Braces matter
# even in a comment: Tcl counts them when matching an enclosing body's close.
_ESCAPES = (("\\", "\\\\"), ('"', '\\"'), ("{", "\\{"), ("}", "\\}"), ("\r", "\\r"), ("\n", "\\n"))


def _escape(text: str) -> str:
    for raw, escaped in _ESCAPES:
        text = text.replace(raw, escaped)
    return text


def marker_pair(*, action: Action, kind: Kind, name: str, source: str) -> tuple[str, str]:
    """Return the ``(begin, end)`` marker line pair for one wrapped unit."""

    body = f'{action} {kind} "{_escape(name)}" source={_escape(source)}'
    return f"## CHOPPER: BEGIN {body}", f"## CHOPPER: END {body}"
