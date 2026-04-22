"""Programmer-error exception hierarchy.

Per bible §5.12.5, user-visible conditions are **diagnostics**, not exceptions.
Services never raise :class:`ValueError` / :class:`FileNotFoundError` to signal
bad input. The classes below exist exclusively for internal-consistency
assertions and registry mismatches — programmer errors, not user errors.

An unhandled exception that escapes a service terminates the run with exit
code 3 (bible §5.10, ARCHITECTURE_PLAN.md §6.2).
"""

from __future__ import annotations


class ChopperError(Exception):
    """Base class for every programmer-error exception raised inside Chopper.

    User-facing outcomes must use :class:`~chopper.core.diagnostics.Diagnostic`
    and :meth:`DiagnosticSink.emit` — not this hierarchy. Catching
    ``ChopperError`` at the orchestrator boundary converts a programmer bug
    into exit code 3.
    """


class UnknownDiagnosticCodeError(ChopperError):
    """Raised when a :class:`Diagnostic` is constructed with a code that is
    not present in the registry shipped with
    :mod:`chopper.core.diagnostics`.

    Catches typos at construction time so no unregistered code can ever reach
    the sink. See bible §8.1 invariants.
    """


class ProgrammerError(ChopperError):
    """Internal-consistency assertion failure.

    Raised when an invariant that should hold by construction is violated —
    for example, when the runner observes a phase completing without emitting
    the artifact its contract requires. Always a bug in Chopper itself, never
    a user-input problem.
    """
