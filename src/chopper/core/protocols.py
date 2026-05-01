"""Effectful ports — the only engine-level abstractions Chopper uses.

Exactly three engine ports: :class:`FileSystemPort`,
:class:`DiagnosticSink`, :class:`ProgressSink`. Clock, serialization,
audit storage, and rendering are **not** ports — they are direct
helpers or CLI-local concerns.

All ports are :class:`typing.Protocol` definitions so test doubles
satisfy them structurally without importing Chopper internals.

The port surface is intentionally small. No ``LockPort``,
``SerializerPort``, ``AuditStore``, or ``TableRenderer`` — adding one
would be a scope-lock violation.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models_common import FileStat

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

    **Write constraint**: services may only write / remove / rename paths
    under :attr:`RunConfig.domain_root`, :attr:`RunConfig.backup_root`,
    or :attr:`RunConfig.audit_root`. Adapters enforce this at the port
    boundary; services rely on the guarantee and do not re-check.

    **``copy_tree`` contract**: must *never* copy a ``.chopper/``
    subdirectory from ``src`` into ``dst``. The recursive copy skips
    any child literally named ``.chopper`` at the top level of ``src``.
    Both adapters (``LocalFS`` and ``InMemoryFS``) enforce this
    identically.
    """

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str: ...

    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None: ...

    def exists(self, path: Path) -> bool: ...

    def list(self, path: Path, *, pattern: str | None = None) -> Sequence[Path]:
        """Return a **sorted** sequence of direct children of ``path``.

        The sort key is the POSIX string representation — the
        determinism contract for directory listings.
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
    """The single communication spine for user-visible outcomes.

    Services call :meth:`emit`; the CLI and ``AuditService`` consume
    :meth:`snapshot` (ordered emissions) and :meth:`finalize` (aggregated
    counts). The only in-tree implementation is ``CollectingSink``;
    tests use stub sinks that also satisfy this protocol.

    Sinks in v1 are **not thread-safe** and need not be. Chopper runs
    single-threaded; the sink never needs a lock. Deduplication is
    performed on :attr:`Diagnostic.dedupe_key`; within a bucket the
    last-written emission wins.
    """

    def emit(self, diagnostic: Diagnostic) -> None: ...

    def snapshot(self) -> Sequence[Diagnostic]:
        """Return emissions in insertion order.

        The returned view is read-only; the sink does not sort. Determinism
        of the user-visible order follows from single-threaded sequential
        phase execution.
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

    There is no dedicated ``PlainProgress`` class. The service layer
    never introspects the progress adapter; it only calls the methods
    below.
    """

    def phase_started(self, phase: Phase) -> None: ...

    def phase_done(self, phase: Phase) -> None: ...

    def step(self, message: str) -> None:
        """Emit a fine-grained progress message within the current phase.

        ``message`` is single-line (newlines stripped by the adapter if
        present). The CLI formatter may truncate for display.
        """
        ...
