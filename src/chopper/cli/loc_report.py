"""LOC report builder and renderer for ``chopper loc`` (FR-46).

Per architecture doc §5.7: the LOC subcommand runs the same P0–P4 +
dry-run-P6 pipeline as ``chopper trim --dry-run`` plus
``GeneratorService`` in no-write mode, then prints a stdout table
comparing the source domain against the planned trimmed domain.

This module owns:

* the "before" enumeration (walk the source root for SLOC-relevant
  source files, skipping ``.chopper/``);
* the per-treatment "after" math (FULL_COPY → unchanged; PROC_TRIM →
  source minus ``procs_removed`` line spans; REMOVE → 0; GENERATED →
  rendered artifact content);
* the table renderer.

Files present in the source domain but absent from
``manifest.file_decisions`` are treated as REMOVE for after totals
(default-exclude under R2).
"""

from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from chopper.audit.sloc import count_sloc
from chopper.core.context import ChopperContext
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest
from chopper.core.models_config import LoadedConfig
from chopper.core.models_parser import ParseResult, ProcEntry
from chopper.core.models_trimmer import GeneratedArtifact

__all__ = ["LocReport", "TreatmentBucket", "build_loc_report", "render_loc_report"]


_SLOC_EXTENSIONS = frozenset(
    {
        ".tcl",
        ".py",
        ".pl",
        ".pm",
        ".sh",
        ".csh",
        ".tcsh",
        ".bash",
        ".zsh",
        ".ksh",
        ".json",
        ".csv",
    }
)


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
    """Return all SLOC-relevant files under the source root, lex-sorted.

    Returns paths **relative** to the source root. ``.chopper/`` is
    excluded. Returns an empty list when the source root does not exist
    (covers in-memory unit-test fixtures with no real domain).
    """
    root = _source_root(ctx)
    if not ctx.fs.exists(root):
        return []

    results: list[Path] = []
    frontier: deque[Path] = deque([root])
    while frontier:
        current = frontier.popleft()
        try:
            children = ctx.fs.list(current)
        except OSError:
            continue
        for child in children:
            try:
                rel = child.relative_to(root)
            except ValueError:
                continue
            rel_posix = rel.as_posix()
            if rel_posix == ".chopper" or rel_posix.startswith(".chopper/"):
                continue
            try:
                st = ctx.fs.stat(child)
            except OSError:
                continue
            if st.is_dir:
                frontier.append(child)
            elif rel.suffix.lower() in _SLOC_EXTENSIONS:
                results.append(rel)
    results.sort(key=lambda p: p.as_posix())
    return results


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


def _proc_drop_span(proc: ProcEntry) -> tuple[int, int]:
    """Return inclusive ``[first, last]`` line range to mask out for a dropped proc.

    Mirrors the spans the trimmer would actually delete (proc body +
    leading DPA + leading comment block, when ``ProcEntry`` records them).
    """
    first = proc.start_line
    if proc.dpa_start_line is not None:
        first = min(first, proc.dpa_start_line)
    if proc.comment_start_line is not None:
        first = min(first, proc.comment_start_line)
    last = proc.end_line
    return first, last


def _proc_trim_after(text: str, dropped_procs: list[ProcEntry], path: Path) -> tuple[int, int]:
    """Return ``(physical_lines_after, sloc_after)`` for a PROC_TRIM file."""
    if not dropped_procs:
        return len(text.splitlines()), count_sloc(path, text)

    drop_set: set[int] = set()
    for proc in dropped_procs:
        first, last = _proc_drop_span(proc)
        drop_set.update(range(first, last + 1))

    kept_lines = [line for lineno, line in enumerate(text.splitlines(), start=1) if lineno not in drop_set]
    kept_text = "\n".join(kept_lines)
    return len(kept_lines), count_sloc(path, kept_text)


def build_loc_report(
    *,
    ctx: ChopperContext,
    loaded: LoadedConfig,
    parsed: ParseResult,
    manifest: CompiledManifest,
    generated_artifacts: tuple[GeneratedArtifact, ...],
) -> LocReport:
    """Compute the LOC report from a completed dry-run pipeline.

    See module docstring for the per-treatment accounting contract.
    """
    del loaded  # surface_files not needed; we walk the disk for "before".

    source_files = _enumerate_source_files(ctx)

    full_copy_files = full_copy_lines = full_copy_sloc = 0
    proc_trim_files = 0
    proc_trim_lines_b = proc_trim_lines_a = 0
    proc_trim_sloc_b = proc_trim_sloc_a = 0
    remove_files = remove_lines_b = remove_sloc_b = 0

    procs_kept_by_file: dict[Path, set[str]] = {}
    for decision in manifest.proc_decisions.values():
        procs_kept_by_file.setdefault(decision.source_file, set()).add(decision.canonical_name)

    for rel in source_files:
        text = _read(ctx, rel)
        if text is None:
            continue
        lines_b = len(text.splitlines())
        sloc_b = count_sloc(rel, text)

        treatment = manifest.file_decisions.get(rel)
        if treatment is None or treatment is FileTreatment.REMOVE:
            remove_files += 1
            remove_lines_b += lines_b
            remove_sloc_b += sloc_b
            continue
        if treatment is FileTreatment.FULL_COPY:
            full_copy_files += 1
            full_copy_lines += lines_b
            full_copy_sloc += sloc_b
        elif treatment is FileTreatment.PROC_TRIM:
            parsed_file = parsed.files.get(rel)
            kept = procs_kept_by_file.get(rel, set())
            dropped = [
                p for p in (parsed_file.procs if parsed_file is not None else ()) if p.canonical_name not in kept
            ]
            lines_a, sloc_a = _proc_trim_after(text, dropped, rel)
            proc_trim_files += 1
            proc_trim_lines_b += lines_b
            proc_trim_lines_a += lines_a
            proc_trim_sloc_b += sloc_b
            proc_trim_sloc_a += sloc_a
        # GENERATED: source-file-side has nothing to count; the artifact
        # contributes only to "after" via generated_artifacts below.

    gen_files = gen_lines_a = gen_sloc_a = 0
    for art in generated_artifacts:
        gen_files += 1
        gen_lines_a += len(art.content.splitlines())
        gen_sloc_a += count_sloc(art.path, art.content)

    buckets = (
        TreatmentBucket(
            "FULL_COPY",
            full_copy_files,
            full_copy_lines,
            full_copy_lines,
            full_copy_sloc,
            full_copy_sloc,
        ),
        TreatmentBucket(
            "PROC_TRIM",
            proc_trim_files,
            proc_trim_lines_b,
            proc_trim_lines_a,
            proc_trim_sloc_b,
            proc_trim_sloc_a,
        ),
        TreatmentBucket("REMOVE", remove_files, remove_lines_b, 0, remove_sloc_b, 0),
        TreatmentBucket("GENERATED", gen_files, 0, gen_lines_a, 0, gen_sloc_a),
    )

    files_before = full_copy_files + proc_trim_files + remove_files
    files_after = full_copy_files + proc_trim_files + gen_files
    lines_before = full_copy_lines + proc_trim_lines_b + remove_lines_b
    lines_after = full_copy_lines + proc_trim_lines_a + gen_lines_a
    sloc_before = full_copy_sloc + proc_trim_sloc_b + remove_sloc_b
    sloc_after = full_copy_sloc + proc_trim_sloc_a + gen_sloc_a

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
