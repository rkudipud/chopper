"""First-word classification and suppression for Tcl body call extraction."""

from __future__ import annotations

import re

from chopper.parser.call_extractor_constants import LOG_PROC_NAMES, TCL_BUILTINS

__all__ = ["BRACKET_CALL_RE", "classify_call_candidate", "should_suppress_first_word"]


BARE_NAME_RE = re.compile(r"^(?:::)?[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*$")
BRACKET_CALL_RE = re.compile(r"\[\s*((?:::)?[A-Za-z_][A-Za-z0-9_:]*)")


def classify_call_candidate(word: str) -> str | None:
    """Return the canonical call-token form, or ``None`` to reject."""
    if "$" in word or word.startswith("["):
        return None
    normalized = word[2:] if word.startswith("::") else word
    if not BARE_NAME_RE.match(word):
        return None
    if normalized in TCL_BUILTINS:
        return None
    return normalized


def should_suppress_first_word(first_word: str) -> bool:
    """Return True if this first-word candidate must be suppressed."""
    if first_word in LOG_PROC_NAMES:
        return True
    if first_word in ("set_app_var", "get_app_var"):
        return True
    return False
