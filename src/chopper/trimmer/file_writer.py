"""Per-file write helpers for :class:`TrimmerService`.

Each helper returns the :class:`FileOutcome` that will flow into the
:class:`TrimReport`. Under ``--dry-run`` no filesystem mutations are
performed, but the same :class:`FileOutcome` is produced so the audit
bundle at P7 describes the planned result identically.

The helpers never emit diagnostics themselves — the owning
:class:`TrimmerService` emits ``VE-23`` / ``VE-24`` / ``VE-25`` /
``VE-26`` in the dispatch loop.
"""

from __future__ import annotations

from pathlib import Path

from chopper.core.context import ChopperContext
from chopper.core.models import FileOutcome, FileTreatment, ParsedFile, ProcEntry
from chopper.trimmer.proc_dropper import drop_procs

__all__ = ["full_copy_file", "proc_trim_file", "remove_file"]


def _backup_path(ctx: ChopperContext, rel: Path) -> Path:
    return ctx.config.backup_root / rel


def _domain_path(ctx: ChopperContext, rel: Path) -> Path:
    return ctx.config.domain_root / rel


def full_copy_file(ctx: ChopperContext, rel: Path, *, procs_in_file: tuple[str, ...]) -> FileOutcome:
    """Copy ``rel`` verbatim from backup to the rebuilt domain."""

    src = _backup_path(ctx, rel)
    dst = _domain_path(ctx, rel)
    content = ctx.fs.read_text(src)
    bytes_in = len(content.encode("utf-8"))
    if not ctx.config.dry_run:
        ctx.fs.write_text(dst, content)
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
