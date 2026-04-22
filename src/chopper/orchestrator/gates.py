"""Phase-boundary gating helper.

A single entry point used by :class:`ChopperRunner` to decide whether
to abort the pipeline after a given phase. Gate semantics are defined
in ARCHITECTURE_PLAN.md §6.2: inspect the diagnostic snapshot and
return ``True`` iff any diagnostic with ``severity == ERROR`` and
``phase == <phase>`` is present. Severity is never rewritten by the
gate — :attr:`RunConfig.strict` is exit-code policy only.
"""

from __future__ import annotations

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Phase, Severity

__all__ = ["has_errors"]


def has_errors(ctx: ChopperContext, phase: Phase) -> bool:
    """Return ``True`` iff ``ctx.diag`` holds an ERROR for ``phase``."""

    for diagnostic in ctx.diag.snapshot():
        if diagnostic.severity is Severity.ERROR and diagnostic.phase == phase:
            return True
    return False
