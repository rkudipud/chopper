"""Typed per-file before/after rows for the post-trim statistics table.

Covers the whole domain so the totals match ``chopper loc`` and the audit
bundle's ``trim_stats.json``: rewritten or copied files (from the trim
report), generated artifacts, and source files the trim dropped entirely.
Authoring artifacts are excluded exactly as :mod:`chopper.core.fs_walk`
excludes them (ARCHITECTURE.md Sec.5.5.13).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from chopper.audit.sloc import count_sloc
from chopper.core.context import ChopperContext
from chopper.core.fs_walk import EXCLUDED_FILENAMES, EXCLUDED_SUFFIXES, TEXT_LIKE_EXTENSIONS, walk_files
from chopper.core.layout import source_root
from chopper.core.models_audit import RunResult
from chopper.core.models_common import FileTreatment
from chopper.core.models_trimmer import GeneratedArtifact, TrimReport

__all__ = ["TrimStatRow", "TrimStats", "build_trim_stats"]


@dataclass(frozen=True)
class TrimStatRow:
    """One file's before/after counts. ``None`` SLOC means unreadable."""

    path: str
    treatment: FileTreatment
    bytes_in: int
    bytes_out: int
    sloc_in: int | None
    sloc_out: int | None
    kept: int
    removed: int


@dataclass(frozen=True)
class TrimStats:
    """All rows, sorted by path, plus totals (unreadable SLOC counts as 0)."""

    rows: tuple[TrimStatRow, ...]
    bytes_in: int
    bytes_out: int
    sloc_in: int
    sloc_out: int
    kept: int
    removed: int


def build_trim_stats(ctx: ChopperContext, result: RunResult) -> TrimStats | None:
    """Build the table, or ``None`` when the run produced no trim outcomes.

    ``None`` covers dry-run, validate-only, and early aborts. SLOC is read
    from the backup (before) and the domain (after) on the local
    filesystem.
    """
    report = result.trim_report
    if report is None or not report.outcomes:
        return None
    rows = _outcome_rows(ctx, report)
    rows.extend(_generated_rows(ctx, result.generated_artifacts))
    rows.extend(_dropped_rows(ctx, report, result.generated_artifacts))
    rows.sort(key=lambda r: r.path)
    return TrimStats(
        rows=tuple(rows),
        bytes_in=sum(r.bytes_in for r in rows),
        bytes_out=sum(r.bytes_out for r in rows),
        sloc_in=sum(r.sloc_in or 0 for r in rows),
        sloc_out=sum(r.sloc_out or 0 for r in rows),
        kept=sum(r.kept for r in rows),
        removed=sum(r.removed for r in rows),
    )


def _is_excluded_artifact(rel: Path) -> bool:
    return rel.name in EXCLUDED_FILENAMES or rel.suffix.lower() in EXCLUDED_SUFFIXES


def _safe_sloc(path: Path, rel: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return count_sloc(rel, text)


def _outcome_rows(ctx: ChopperContext, report: TrimReport) -> list[TrimStatRow]:
    backup_root = ctx.config.backup_root
    domain_root = ctx.config.domain_root
    rows: list[TrimStatRow] = []
    for outcome in report.outcomes:
        if _is_excluded_artifact(outcome.path):
            continue
        # Dry-run takes no backup; the pre-trim source is still at
        # ``domain_root``. Prefer the backup so both modes report the same
        # baseline (A7).
        sloc_in = _safe_sloc(backup_root / outcome.path, outcome.path)
        if sloc_in is None and ctx.config.dry_run:
            sloc_in = _safe_sloc(domain_root / outcome.path, outcome.path)
        if outcome.treatment is FileTreatment.REMOVE:
            sloc_out: int | None = 0
        else:
            sloc_out = _safe_sloc(domain_root / outcome.path, outcome.path)
        rows.append(
            TrimStatRow(
                path=outcome.path.as_posix(),
                treatment=outcome.treatment,
                bytes_in=outcome.bytes_in,
                bytes_out=outcome.bytes_out,
                sloc_in=sloc_in,
                sloc_out=sloc_out,
                kept=len(outcome.procs_kept),
                removed=len(outcome.procs_removed),
            )
        )
    return rows


def _generated_rows(ctx: ChopperContext, artifacts: Sequence[GeneratedArtifact]) -> list[TrimStatRow]:
    """GENERATED artifacts (stage tcl / stack / csv / feature sourcing files).

    Under dry-run the rebuilt domain is not on disk, so ``out`` comes from
    :attr:`GeneratedArtifact.content`. Under live trim the on-disk file is
    read (it has passed the optional P5c indentation pass). A same-path
    source file (under ``backup_root``; under dry-run still at
    ``domain_root``) supplies the ``in`` baseline for regenerate-in-place.
    """
    domain_root = ctx.config.domain_root
    backup_root = ctx.config.backup_root
    dry_run = ctx.config.dry_run
    rows: list[TrimStatRow] = []
    for artifact in artifacts:
        rel = artifact.path
        if _is_excluded_artifact(rel):
            continue
        if dry_run:
            text = artifact.content
        else:
            try:
                text = (domain_root / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = artifact.content

        bytes_in = 0
        sloc_in: int | None = 0
        src_text: str | None = None
        for candidate in (backup_root / rel, domain_root / rel) if dry_run else (backup_root / rel,):
            try:
                src_text = candidate.read_text(encoding="utf-8", errors="replace")
                break
            except OSError:
                continue
        if src_text is not None:
            bytes_in = len(src_text.encode("utf-8"))
            sloc_in = count_sloc(rel, src_text)

        rows.append(
            TrimStatRow(
                path=rel.as_posix(),
                treatment=FileTreatment.GENERATED,
                bytes_in=bytes_in,
                bytes_out=len(text.encode("utf-8")),
                sloc_in=sloc_in,
                sloc_out=count_sloc(rel, text),
                kept=0,
                removed=0,
            )
        )
    return rows


def _dropped_rows(
    ctx: ChopperContext,
    report: TrimReport,
    artifacts: Sequence[GeneratedArtifact],
) -> list[TrimStatRow]:
    """DROP rows for source files the trim removed entirely.

    Files dropped under default-exclude (R2) never appear in
    ``report.outcomes``; walk the pristine source tree and add every file
    not already accounted for as a rewrite, copy, or generated artifact.
    ``walk_files`` already hard-excludes authoring artifacts and ``.chopper/``.
    """
    root = source_root(ctx)
    accounted = {o.path.as_posix() for o in report.outcomes}
    accounted |= {a.path.as_posix() for a in artifacts}
    rows: list[TrimStatRow] = []
    for rel in walk_files(ctx.fs, root):
        if rel.as_posix() in accounted:
            continue
        try:
            raw = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rows.append(
            TrimStatRow(
                path=rel.as_posix(),
                treatment=FileTreatment.REMOVE,
                bytes_in=len(raw.encode("utf-8")),
                bytes_out=0,
                sloc_in=count_sloc(rel, raw) if rel.suffix.lower() in TEXT_LIKE_EXTENSIONS else 0,
                sloc_out=0,
                kept=0,
                removed=0,
            )
        )
    return rows
