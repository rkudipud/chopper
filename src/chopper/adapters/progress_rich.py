"""Rich-based :class:`~chopper.core.protocols.ProgressSink` adapter.

Per ARCHITECTURE_PLAN.md §5: a single class, reconfigured for the
``--plain`` flag. Styled mode uses a default :class:`rich.console.Console`;
plain mode uses ``Console(no_color=True, force_terminal=False,
legacy_windows=False)`` and disables the live progress bar so only
ASCII single-line status is emitted.

``rich`` is an optional dependency; the module imports it lazily and
raises :class:`RichUnavailableError` if not installed.  The CLI catches
this and falls back to :class:`~chopper.adapters.progress_silent.SilentProgress`.
"""

from __future__ import annotations

from chopper.core.diagnostics import Phase

__all__ = ["RichProgress", "RichUnavailableError"]


class RichUnavailableError(RuntimeError):
    """Raised when :mod:`rich` is not importable.

    The CLI catches this and downgrades to silent progress so Chopper
    still runs on a minimal install.
    """


class RichProgress:
    """Progress sink backed by :mod:`rich`.

    ``plain=True`` forces ASCII / no-color output; otherwise Rich's
    default console styling is used. Both configurations write to
    ``stderr`` so stdout stays available for structured data in a
    future machine-readable mode (see `FD-10`).
    """

    def __init__(self, *, plain: bool = False) -> None:
        try:
            from rich.console import Console
        except ImportError as exc:  # pragma: no cover - optional dep
            raise RichUnavailableError(
                "rich is not installed; install the 'rich' extra or use --plain / --quiet"
            ) from exc

        if plain:
            self._console = Console(
                no_color=True,
                force_terminal=False,
                legacy_windows=False,
                stderr=True,
            )
        else:
            self._console = Console(stderr=True)
        self._plain = plain

    def phase_started(self, phase: Phase) -> None:
        self._console.print(f"[{phase.name}] started")

    def phase_done(self, phase: Phase) -> None:
        self._console.print(f"[{phase.name}] done")

    def step(self, message: str) -> None:
        self._console.print(f"  {message}")
