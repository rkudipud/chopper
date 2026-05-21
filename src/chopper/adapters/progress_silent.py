"""No-op :class:`~chopper.core.protocols.ProgressSink` adapter.

Selected by ``-q / --quiet`` and by all test harnesses. Every method
is a no-op; the sink allocates nothing at runtime.
"""

from __future__ import annotations

from chopper.core.diagnostics import Phase

__all__ = ["SilentProgress"]


class SilentProgress:
    """Drop-on-the-floor progress sink."""

    def phase_started(self, phase: Phase) -> None:  # pragma: no cover - trivial
        return None

    def phase_done(self, phase: Phase) -> None:  # pragma: no cover - trivial
        return None

    def step(self, message: str) -> None:  # pragma: no cover - trivial
        return None
