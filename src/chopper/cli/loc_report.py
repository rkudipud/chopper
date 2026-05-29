"""LOC report builder and renderer for ``chopper loc`` (FR-46).

Per architecture doc §5.7: the LOC subcommand runs the same P0–P4 +
dry-run pipeline as ``chopper trim --dry-run``, then *replays the real
P5 trim phases against an in-memory copy of the source tree* (see
:mod:`chopper.orchestrator.simulate`) and prints a stdout table comparing
the source domain against the actually-rebuilt trimmed domain.

Because the replay reuses the production trimmer, generator,
indentation, and companion-sync services unchanged, ``chopper loc``
before/after totals are byte-for-byte identical to a live
``chopper trim`` — there is no separate "estimate" to drift.

This module owns:

* the per-treatment accounting that buckets each domain file by its
  :class:`~chopper.core.models_common.FileTreatment` and reads the
  actual before (backup tree) / after (rebuilt domain tree) counts
  from the in-memory filesystem;
* a baseline-only fallback for when the pipeline aborts before a
  manifest is available;
* the table renderer.

Files present in the source domain but absent from
``manifest.file_decisions`` are treated as REMOVE for after totals
(default-exclude under R2).
"""

from __future__ import annotations

import sys
from collections import deque  # noqa: F401  (kept for backward-compat import path)
from dataclasses import dataclass
from pathlib import Path

from chopper.audit.sloc import count_sloc_many
from chopper.core.context import ChopperContext
from chopper.core.fs_walk import TEXT_LIKE_EXTENSIONS, walk_files
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest
from chopper.core.models_config import LoadedConfig
from chopper.core.models_parser import ParseResult
from chopper.core.models_trimmer import GeneratedArtifact

__all__ = [
    "LocReport",
    "TreatmentBucket",
    "build_loc_report",
    "build_loc_report_baseline_only",
    "render_loc_report",
]


_SLOC_EXTENSIONS = TEXT_LIKE_EXTENSIONS


@dataclass(frozen=True)
class TreatmentBucket:
    """Per-treatment subtotal row in the LOC report."""

    treatment: str
    files: int
    lines_before: int
    lines_after: int
    sloc_before: int
    sloc_after: int


@dataclass(frozen=True)
class LocReport:
    """Aggregated LOC comparison for a planned trim."""

    files_before: int
    files_after: int
    lines_before: int
    lines_after: int
    sloc_before: int
    sloc_after: int
    buckets: tuple[TreatmentBucket, ...]

    @property
    def files_pct_reduction(self) -> float:
        if self.files_before == 0:
            return 0.0
        return (1.0 - self.files_after / self.files_before) * 100.0

    @property
    def lines_pct_reduction(self) -> float:
        if self.lines_before == 0:
            return 0.0
        return (1.0 - self.lines_after / self.lines_before) * 100.0

    @property
    def sloc_pct_reduction(self) -> float:
        if self.sloc_before == 0:
            return 0.0
        return (1.0 - self.sloc_after / self.sloc_before) * 100.0


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _source_root(ctx: ChopperContext) -> Path:
    """Mirror :func:`chopper.parser.service.ParserService._source_root`.

    P2 reads from ``backup_root`` when it exists (Case 2 / Case 3
    reruns) and from ``domain_root`` otherwise. The LOC reporter
    follows the same convention so "before" reflects what the parser
    actually saw.
    """
    if ctx.fs.exists(ctx.config.backup_root):
        return ctx.config.backup_root
    return ctx.config.domain_root


def _enumerate_source_files(ctx: ChopperContext) -> list[Path]:
    """Return all SLOC-eligible files under the source root, lex-sorted.

    Backed by :func:`chopper.core.fs_walk.walk_files` so the audit and
    LOC reporter agree on what counts as a file. Returns paths
    **relative** to the source root; ``.chopper/`` is excluded.
    """

    return walk_files(ctx.fs, _source_root(ctx), extensions=_SLOC_EXTENSIONS)


def _enumerate_all_source_files(ctx: ChopperContext) -> list[Path]:
    """Return every regular file under the source root, lex-sorted.

    Unlike :func:`_enumerate_source_files`, this walker does *not*
    filter by extension. The result drives ``files_before`` /
    ``files_after`` counts so the LOC report's file totals match the
    audit bundle's full-domain view (S3, production-readiness review).
    """

    return walk_files(ctx.fs, _source_root(ctx))


def _read(ctx: ChopperContext, rel: Path) -> str | None:
    """Read a file relative to the source root with a latin-1 fallback."""
    abs_path = _source_root(ctx) / rel
    try:
        return ctx.fs.read_text(abs_path)
    except UnicodeDecodeError:
        try:
            return ctx.fs.read_text(abs_path, encoding="latin-1")
        except OSError:
            return None
    except OSError:
        return None


def _count_tree(fs: object, root: Path) -> tuple[list[Path], dict[Path, int], dict[Path, int]]:
    """Return ``(rels, lines_by_rel, sloc_by_rel)`` for every file under ``root``.

    ``rels`` is the full lex-sorted file set (``walk_files`` already
    drops ``.chopper/`` and authoring artifacts). ``lines_by_rel`` maps
    each file to its physical line count; ``sloc_by_rel`` maps only
    text-like files to their logical-source-line count, computed in a
    single batched ``cloc`` pass.
    """

    rels = walk_files(fs, root)  # type: ignore[arg-type]
    lines_by_rel: dict[Path, int] = {}
    sloc_items: list[tuple[Path, str]] = []
    for rel in rels:
        try:
            text = fs.read_text(root / rel)  # type: ignore[attr-defined]
        except (OSError, UnicodeDecodeError):
            continue
        lines_by_rel[rel] = len(text.splitlines())
        if rel.suffix.lower() in _SLOC_EXTENSIONS:
            sloc_items.append((rel, text))
    sloc_by_rel: dict[Path, int] = {}
    if sloc_items:
        for (rel, _), n in zip(sloc_items, count_sloc_many(sloc_items), strict=True):
            sloc_by_rel[rel] = n
    return rels, lines_by_rel, sloc_by_rel


def build_loc_report(
    *,
    ctx: ChopperContext,
    loaded: LoadedConfig,
    parsed: ParseResult,
    manifest: CompiledManifest,
    generated_artifacts: tuple[GeneratedArtifact, ...],
) -> LocReport:
    """Compute the LOC report by replaying the real trim in memory.

    Per ARCHITECTURE.md §5.7, ``chopper loc`` reports the SLOC impact of
    a planned trim. Rather than *estimating* the trimmed output, this
    builder replays the production P5 phases (trim → generators →
    indentation → companion sync) against an in-memory copy of the
    source tree via :func:`chopper.orchestrator.simulate.simulate_trim_in_memory`,
    then counts the *actual* rebuilt files. The before/after totals are
    therefore byte-for-byte identical to a live ``chopper trim`` (the
    same services produce both), including companion-file sync (P5d)
    and optional indentation normalization (P5c).

    File counts walk the full domain; SLOC math is constrained to
    text-like extensions and routed through :func:`count_sloc_many` so
    each tree is counted with a single ``cloc`` invocation.
    """
    from chopper.orchestrator.simulate import simulate_trim_in_memory

    sim = simulate_trim_in_memory(ctx, loaded=loaded, parsed=parsed, manifest=manifest)
    before_rels, before_lines, before_sloc = _count_tree(sim.fs, sim.backup_root)
    _after_rels, after_lines, after_sloc = _count_tree(sim.fs, sim.domain_root)

    gen_paths: set[Path] = {art.path for art in generated_artifacts}

    fc_files = fc_lb = fc_la = fc_sb = fc_sa = 0
    pt_files = pt_lb = pt_la = pt_sb = pt_sa = 0
    rm_files = rm_lb = rm_sb = 0

    for rel in before_rels:
        treatment = manifest.file_decisions.get(rel)
        if treatment is FileTreatment.GENERATED or rel in gen_paths:
            # Regenerate-in-place source — accounted in the GENERATED
            # bucket below so it is not double-counted here.
            continue
        lb = before_lines.get(rel, 0)
        sb = before_sloc.get(rel, 0)
        if treatment is None or treatment is FileTreatment.REMOVE:
            rm_files += 1
            rm_lb += lb
            rm_sb += sb
        elif treatment is FileTreatment.FULL_COPY:
            fc_files += 1
            fc_lb += lb
            fc_sb += sb
            fc_la += after_lines.get(rel, 0)
            fc_sa += after_sloc.get(rel, 0)
        else:
            # The only remaining treatment is PROC_TRIM: GENERATED files
            # are skipped above and None/REMOVE/FULL_COPY are handled in
            # the branches before this one, so the enum is exhausted here.
            pt_files += 1
            pt_lb += lb
            pt_sb += sb
            pt_la += after_lines.get(rel, 0)
            pt_sa += after_sloc.get(rel, 0)

    gen_files = gen_lb = gen_la = gen_sb = gen_sa = 0
    regenerate_in_place = 0
    for art in generated_artifacts:
        gen_files += 1
        gen_la += after_lines.get(art.path, 0)
        gen_sa += after_sloc.get(art.path, 0)
        if art.path in before_lines:
            # The source domain already contained a file at this path;
            # capture its pre-trim size as the GENERATED "before".
            regenerate_in_place += 1
            gen_lb += before_lines.get(art.path, 0)
            gen_sb += before_sloc.get(art.path, 0)

    buckets = (
        TreatmentBucket("FULL_COPY", fc_files, fc_lb, fc_la, fc_sb, fc_sa),
        TreatmentBucket("PROC_TRIM", pt_files, pt_lb, pt_la, pt_sb, pt_sa),
        TreatmentBucket("REMOVE", rm_files, rm_lb, 0, rm_sb, 0),
        TreatmentBucket("GENERATED", gen_files, gen_lb, gen_la, gen_sb, gen_sa),
    )

    files_before = fc_files + pt_files + rm_files + regenerate_in_place
    files_after = fc_files + pt_files + gen_files
    lines_before = fc_lb + pt_lb + rm_lb + gen_lb
    lines_after = fc_la + pt_la + gen_la
    sloc_before = fc_sb + pt_sb + rm_sb + gen_sb
    sloc_after = fc_sa + pt_sa + gen_sa

    return LocReport(
        files_before=files_before,
        files_after=files_after,
        lines_before=lines_before,
        lines_after=lines_after,
        sloc_before=sloc_before,
        sloc_after=sloc_after,
        buckets=buckets,
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def build_loc_report_baseline_only(ctx: ChopperContext) -> LocReport:
    """Compute a *baseline-only* LOC report by walking the source root.

    Used by ``chopper loc`` as a fallback when the dry-run pipeline
    aborted before producing a :class:`CompiledManifest` (e.g. P2/P3
    surfaced ``PE-01`` duplicate procs or ``PE-02`` unbalanced braces).
    In that case we still want the caller to see the SLOC baseline of
    the domain — the LOC subcommand is purely read-only and the
    on-disk source is unaffected by the pipeline halt.

    The returned report has ``after == before`` for every metric and a
    single ``FULL_COPY`` bucket holding all source files. Per-treatment
    accounting is unavailable without the manifest, so we deliberately
    do not synthesize ``PROC_TRIM`` / ``REMOVE`` / ``GENERATED``
    counts; consumers must rely on diagnostics (rendered separately
    by ``cmd_loc``) to understand why downstream treatment buckets are
    empty.
    """
    source_files = _enumerate_source_files(ctx)
    all_files = _enumerate_all_source_files(ctx)

    items: list[tuple[Path, str]] = []
    total_lines = 0
    for rel in source_files:
        text = _read(ctx, rel)
        if text is None:
            continue
        items.append((rel, text))
        total_lines += len(text.splitlines())
    total_sloc = sum(count_sloc_many(items)) if items else 0
    file_count = len(all_files)

    buckets = (
        TreatmentBucket(
            "FULL_COPY",
            file_count,
            total_lines,
            total_lines,
            total_sloc,
            total_sloc,
        ),
        TreatmentBucket("PROC_TRIM", 0, 0, 0, 0, 0),
        TreatmentBucket("REMOVE", 0, 0, 0, 0, 0),
        TreatmentBucket("GENERATED", 0, 0, 0, 0, 0),
    )

    return LocReport(
        files_before=file_count,
        files_after=file_count,
        lines_before=total_lines,
        lines_after=total_lines,
        sloc_before=total_sloc,
        sloc_after=total_sloc,
        buckets=buckets,
    )


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def render_loc_report(report: LocReport) -> None:
    """Print the LOC report as one ``key: value`` line per metric.

    Output is intentionally line-oriented (no ASCII tables, no column
    alignment) so downstream consumers — pipes, ``grep``, harness
    captures, MCP clients — can parse it deterministically. Each line
    is a ``label: value`` pair; per-treatment subtotals are namespaced
    with ``treatment.<NAME>.<field>``.
    """
    out = sys.stdout
    write = out.write

    write("chopper loc: read-only LOC report\n")
    write(f"files.before: {report.files_before}\n")
    write(f"files.after: {report.files_after}\n")
    write(f"files.delta: {report.files_after - report.files_before:+d}\n")
    write(f"files.reduction_pct: {_fmt_pct(report.files_pct_reduction)}\n")
    write(f"lines.before: {report.lines_before}\n")
    write(f"lines.after: {report.lines_after}\n")
    write(f"lines.delta: {report.lines_after - report.lines_before:+d}\n")
    write(f"lines.reduction_pct: {_fmt_pct(report.lines_pct_reduction)}\n")
    write(f"sloc.before: {report.sloc_before}\n")
    write(f"sloc.after: {report.sloc_after}\n")
    write(f"sloc.delta: {report.sloc_after - report.sloc_before:+d}\n")
    write(f"sloc.reduction_pct: {_fmt_pct(report.sloc_pct_reduction)}\n")
    for bucket in report.buckets:
        prefix = f"treatment.{bucket.treatment}"
        write(f"{prefix}.files: {bucket.files}\n")
        write(f"{prefix}.lines_before: {bucket.lines_before}\n")
        write(f"{prefix}.lines_after: {bucket.lines_after}\n")
        write(f"{prefix}.sloc_before: {bucket.sloc_before}\n")
        write(f"{prefix}.sloc_after: {bucket.sloc_after}\n")
    if report.lines_before == 0:
        write("note: no countable source files in domain\n")
    out.flush()
