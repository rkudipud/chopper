"""Per-file write helpers for :class:`TrimmerService`.

Each helper returns the :class:`FileOutcome` that will flow into the
:class:`TrimReport`. Under ``--dry-run`` no filesystem mutations are
performed, but the same :class:`FileOutcome` is produced so the audit
bundle at P7 describes the planned result identically.

The helpers never emit diagnostics themselves — the owning
:class:`TrimmerService` emits ``VE-23`` / ``VE-24`` / ``VE-25`` /
``VE-26`` in the dispatch loop.

File-mode preservation
----------------------
After writing each rebuilt file (``FULL_COPY`` or ``PROC_TRIM``) we mirror
the source file's mode bits from ``<domain>_backup/`` onto the freshly
written destination via :func:`shutil.copymode`. ``Path.write_text`` (used
by :class:`~chopper.adapters.fs_local.LocalFS`) creates the destination
with the process umask, which silently drops the executable bit and
collapses group/world permissions; without this step every rebuilt
``.tcl`` / ``.pl`` / ``.csh`` / ``.py`` script that was executable in the
input domain comes out non-executable in the rebuilt domain. The copy is
gated on the destination actually existing on the real filesystem so it
is a no-op for in-memory filesystem adapters used by unit tests, and the
``OSError`` swallow keeps the trim resilient to unusual filesystems
(e.g. NFS exports that reject ``chmod``).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from chopper.core.context import ChopperContext
from chopper.core.models import FileOutcome, FileTreatment, ParsedFile, ProcEntry
from chopper.trimmer.proc_dropper import drop_procs

__all__ = ["full_copy_file", "proc_trim_file", "remove_file"]


def _backup_path(ctx: ChopperContext, rel: Path) -> Path:
    return ctx.config.backup_root / rel


def _domain_path(ctx: ChopperContext, rel: Path) -> Path:
    return ctx.config.domain_root / rel


def _mirror_mode(src: Path, dst: Path) -> None:
    """Copy ``src``'s mode bits onto ``dst`` if both are real on-disk paths.

    No-op when either path is absent from the real filesystem (the unit-test
    in-memory adapter never materializes paths on disk) or when the platform
    rejects ``chmod`` for any reason. Errors here must never break a trim:
    the destination content is already correct; only the perms are at risk.
    """

    try:
        if src.is_file() and dst.is_file():
            shutil.copymode(src, dst)
    except OSError:
        # Defensive: keep the trim alive on filesystems that reject chmod.
        pass


def full_copy_file(ctx: ChopperContext, rel: Path, *, procs_in_file: tuple[str, ...]) -> FileOutcome:
    """Copy ``rel`` verbatim from backup to the rebuilt domain."""

    src = _backup_path(ctx, rel)
    dst = _domain_path(ctx, rel)
    content = ctx.fs.read_text(src)
    bytes_in = len(content.encode("utf-8"))
    if not ctx.config.dry_run:
        ctx.fs.write_text(dst, content)
        _mirror_mode(src, dst)
    return FileOutcome(
        path=rel,
        treatment=FileTreatment.FULL_COPY,
        bytes_in=bytes_in,
        bytes_out=bytes_in,
        procs_kept=procs_in_file,
        procs_removed=(),
    )


def proc_trim_file(
    ctx: ChopperContext,
    rel: Path,
    *,
    parsed: ParsedFile,
    keep_canonical: frozenset[str],
) -> FileOutcome:
    """Rewrite ``rel`` with non-surviving procs deleted.

    Drop ranges are computed from the :class:`ProcEntry` records on
    ``parsed.procs``; the rewrite is performed by
    :func:`chopper.trimmer.proc_dropper.drop_procs`.
    """

    src = _backup_path(ctx, rel)
    dst = _domain_path(ctx, rel)
    content = ctx.fs.read_text(src)
    bytes_in = len(content.encode("utf-8"))

    to_drop: list[ProcEntry] = [p for p in parsed.procs if p.canonical_name not in keep_canonical]
    kept: list[ProcEntry] = [p for p in parsed.procs if p.canonical_name in keep_canonical]

    new_content = drop_procs(content, to_drop)
    bytes_out = len(new_content.encode("utf-8"))
    if not ctx.config.dry_run:
        ctx.fs.write_text(dst, new_content)
        _mirror_mode(src, dst)

    return FileOutcome(
        path=rel,
        treatment=FileTreatment.PROC_TRIM,
        bytes_in=bytes_in,
        bytes_out=bytes_out,
        procs_kept=tuple(sorted(p.canonical_name for p in kept)),
        procs_removed=tuple(sorted(p.canonical_name for p in to_drop)),
    )


def remove_file(ctx: ChopperContext, rel: Path) -> FileOutcome:
    """Record that ``rel`` is omitted from the rebuilt domain.

    REMOVE is the default "do nothing" path: because the rebuilt domain
    is constructed fresh from backup, omitting a write is sufficient.
    ``bytes_in`` is read from backup (if the backup still has the file)
    for audit completeness; a missing backup file surfaces an
    :class:`OSError` that the caller translates to ``VE-24``.
    """

    src = _backup_path(ctx, rel)
    try:
        content = ctx.fs.read_text(src)
        bytes_in = len(content.encode("utf-8"))
    except (OSError, FileNotFoundError):
        bytes_in = 0
    return FileOutcome(
        path=rel,
        treatment=FileTreatment.REMOVE,
        bytes_in=bytes_in,
        bytes_out=0,
        procs_kept=(),
        procs_removed=(),
    )
