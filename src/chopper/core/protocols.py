"""Effectful ports — the only engine-level abstractions Chopper uses.

Per bible §5.12.1 and ARCHITECTURE_PLAN.md §5, Chopper exposes exactly
**three** engine ports: :class:`FileSystemPort`, :class:`DiagnosticSink`,
and :class:`ProgressSink`. Clock, serialization, audit storage, and
rendering are **not** ports — they are direct helpers or CLI-local
concerns (ARCHITECTURE_PLAN.md §5, closed decisions A2–A5).

All ports are :class:`typing.Protocol` definitions so test doubles satisfy
them structurally without importing Chopper internals (bible §5.12.3).

The port surface is **intentionally small**. No ``LockPort``, no
``SerializerPort``, no ``AuditStore``, no ``TableRenderer`` — adding one
would be a scope-lock violation. See ARCHITECTURE_PLAN.md §7 and
`.github/instructions/project.instructions.md` Scope Lock §1.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models import FileStat

__all__ = [
    "DiagnosticSink",
    "FileSystemPort",
    "ProgressSink",
]


@runtime_checkable
class FileSystemPort(Protocol):
    """Complete filesystem surface used by Chopper services.

    Implemented by :class:`~chopper.adapters.fs_local.LocalFS` in production
    and :class:`~chopper.adapters.fs_memory.InMemoryFS` in tests. The full
    set of methods — beyond plain read/write — is required by the trimmer
    (:meth:`rename`, :meth:`remove`, :meth:`copy_tree`), by domain-state
    detection (:meth:`exists`, :meth:`stat`), and by audit writing
    (:meth:`mkdir`).

    **Write constraint** (ARCHITECTURE_PLAN.md §5): services may only
    write / remove / rename paths under
    :attr:`RunConfig.domain_root`, :attr:`RunConfig.backup_root`, or
    :attr:`RunConfig.audit_root`. Adapters enforce this at the port
    boundary; services rely on the guarantee and do not re-check.

    **``copy_tree`` contract** (ARCHITECTURE_PLAN.md §5): must *never*
    copy a ``.chopper/`` subdirectory from ``src`` into ``dst``. The
    recursive copy skips any child literally named ``.chopper`` at the
    top level of ``src``. Both adapters (``LocalFS`` and ``InMemoryFS``)
    enforce this identically.
    """

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str: ...

    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None: ...

    def exists(self, path: Path) -> bool: ...

    def list(self, path: Path, *, pattern: str | None = None) -> Sequence[Path]:
        """Return a **sorted** sequence of direct children of ``path``.

        The sort key is the POSIX string representation — matching the
        determinism rule in ARCHITECTURE_PLAN.md §9.3 rule 6.
        """
        ...

    def stat(self, path: Path) -> FileStat: ...

    def rename(self, src: Path, dst: Path) -> None:
        """Rename ``src`` to ``dst`` (e.g. ``domain/`` → ``domain_backup/``)."""
        ...

    def remove(self, path: Path, *, recursive: bool = False) -> None: ...

    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None: ...

    def copy_tree(self, src: Path, dst: Path) -> None:
        """Recursively copy ``src`` to ``dst``, excluding any top-level ``.chopper/``.

        See class docstring for the exclusion contract.
        """
        ...


@runtime_checkable
class DiagnosticSink(Protocol):
    """The single communication spine for user-visible outcomes (bible §8.2).

    Services call :meth:`emit`; the CLI and ``AuditService`` consume
    :meth:`snapshot` (ordered emissions) and :meth:`finalize` (aggregated
    counts). The only in-tree implementation in Stage 0 is the default
    ``CollectingSink`` (added by the adapter stage that ships it); tests
    use stub sinks that also satisfy this protocol.

    Sinks in v1 are **not thread-safe** and need not be. Chopper runs
    single-threaded (ARCHITECTURE_PLAN.md §11); the sink never needs a
    lock. Deduplication is performed on
    :attr:`Diagnostic.dedupe_key`; within a bucket the last-written
    emission wins (bible §8.2 rule 2).
    """

    def emit(self, diagnostic: Diagnostic) -> None: ...

    def snapshot(self) -> Sequence[Diagnostic]:
        """Return emissions in insertion order.

        The returned view is read-only; the sink does not sort. Determinism
        of the user-visible order follows from single-threaded sequential
        phase execution (bible §8.2 rule 3).
        """
        ...

    def finalize(self) -> DiagnosticSummary: ...


@runtime_checkable
class ProgressSink(Protocol):
    """Coarse progress signal emitted by services at phase boundaries.

    Three concrete adapters exist:

    * ``RichProgress`` (default) — interactive TTY rendering via Rich.
    * ``RichProgress`` reconfigured for ``--plain`` — same class with
      ``Console(no_color=True, force_terminal=False)`` and the live bar
      disabled.
    * ``SilentProgress`` — no-op; selected by ``-q / --quiet`` and by all
      test harnesses.

    Per ARCHITECTURE_PLAN.md §5, there is **no dedicated** ``PlainProgress``
    class. The service layer never introspects the progress adapter; it
    only calls the methods below.
    """

    def phase_started(self, phase: Phase) -> None: ...

    def phase_done(self, phase: Phase) -> None: ...

    def step(self, message: str) -> None:
        """Emit a fine-grained progress message within the current phase.

        ``message`` is single-line (newlines stripped by the adapter if
        present). The CLI formatter may truncate for display.
        """
        ...
