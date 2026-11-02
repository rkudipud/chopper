"""``chopper loc`` projection (architecture doc Sec.5.7).

``chopper loc`` reports the SLOC impact of a planned trim without mutating
the real domain. The projection copies the source tree into an
:class:`InMemoryFS`, replays the one P5 sequence
(:func:`chopper.orchestrator.runner.execute_output`, gates off) against it,
and counts the *actual* rebuilt files. Before/after totals therefore match a
live ``chopper trim`` byte-for-byte; there is no separate estimator.

Files present in the source domain but absent from
``manifest.file_decisions`` count as REMOVE (default-exclude under R2).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from chopper.adapters.fs_memory import InMemoryFS
from chopper.adapters.progress_silent import SilentProgress
from chopper.adapters.sink_collecting import CollectingSink
from chopper.audit.sloc import count_sloc_many
from chopper.core.context import ChopperContext
from chopper.core.fs_walk import TEXT_LIKE_EXTENSIONS, walk_files
from chopper.core.layout import source_root
from chopper.core.models_audit import LocReport, TreatmentBucket
from chopper.core.models_common import DomainState, FileTreatment
from chopper.core.models_compiler import CompiledManifest
from chopper.core.models_parser import ParseResult
from chopper.core.models_trimmer import GeneratedArtifact
from chopper.core.protocols import FileSystemPort
from chopper.orchestrator.runner import RunLedger, default_providers, execute_output

__all__ = [
    "SimulatedTrim",
    "build_loc_report",
    "build_loc_report_baseline_only",
    "simulate_trim_in_memory",
]


@dataclass(frozen=True)
class SimulatedTrim:
    """Result of an in-memory trim replay.

    * ``fs`` -- the in-memory filesystem after the trim completed.
    * ``domain_root`` -- holds the rebuilt, trimmed domain.
    * ``backup_root`` -- holds the pristine pre-trim source (moved aside
      by the trimmer's Case-1 prep, exactly as on real disk).
    """

    fs: InMemoryFS
    domain_root: Path
    backup_root: Path


def _read_text(ctx: ChopperContext, path: Path) -> str | None:
    """Read ``path`` with a latin-1 fallback; unreadable files yield ``None``."""

    try:
        return ctx.fs.read_text(path)
    except UnicodeDecodeError:
        try:
            return ctx.fs.read_text(path, encoding="latin-1")
        except OSError:
            return None
    except OSError:
        return None


def simulate_trim_in_memory(
    ctx: ChopperContext,
    *,
    parsed: ParseResult,
    manifest: CompiledManifest,
) -> SimulatedTrim:
    """Replay P5 against an in-memory Case-1 copy of the source tree.

    Diagnostics and progress are discarded -- the caller already rendered
    them from the dry-run pass. Gates are off and JSON inputs are not
    preserved, exactly like the previous standalone replay.
    """

    domain_root = ctx.config.domain_root
    backup_root = ctx.config.backup_root
    src_root = source_root(ctx)

    seed: dict[Path, str] = {}
    for rel in walk_files(ctx.fs, src_root):
        text = _read_text(ctx, src_root / rel)
        if text is None:
            continue
        seed[domain_root / rel] = text

    # walk_files skips ``.json``, but the trimmer copies surviving JSONs
    # (e.g. jsons/base.json). Without them its per-file loop stops early and
    # later files are never written, undercounting sloc_after.
    for rel in manifest.file_decisions:
        if rel.suffix.lower() != ".json":
            continue
        json_path = src_root / rel
        if not ctx.fs.exists(json_path):
            continue
        text = _read_text(ctx, json_path)
        if text is not None:
            seed.setdefault(domain_root / rel, text)

    memfs = InMemoryFS(seed)
    mem_ctx = ChopperContext(
        config=replace(ctx.config, dry_run=False),
        fs=memfs,
        diag=CollectingSink(),
        progress=SilentProgress(),
    )
    # Clean Case-1 layout: domain present, backup absent.
    state = DomainState(case=1, domain_exists=True, backup_exists=False)
    execute_output(
        mem_ctx,
        default_providers(),
        RunLedger(),
        manifest=manifest,
        parsed=parsed,
        state=state,
        gated=False,
    )
    return SimulatedTrim(fs=memfs, domain_root=domain_root, backup_root=backup_root)


def _count_tree(fs: FileSystemPort, root: Path) -> tuple[list[Path], dict[Path, int], dict[Path, int]]:
    """Return ``(rels, lines_by_rel, sloc_by_rel)`` for every file under ``root``.

    ``lines_by_rel`` maps each readable file to its physical line count;
    ``sloc_by_rel`` maps only text-like files, counted in one batched pass.
    """

    rels = walk_files(fs, root)
    lines_by_rel: dict[Path, int] = {}
    sloc_items: list[tuple[Path, str]] = []
    for rel in rels:
        try:
            text = fs.read_text(root / rel)
        except (OSError, UnicodeDecodeError):
            continue
        lines_by_rel[rel] = len(text.splitlines())
        if rel.suffix.lower() in TEXT_LIKE_EXTENSIONS:
            sloc_items.append((rel, text))
    sloc_by_rel: dict[Path, int] = {}
    if sloc_items:
        for (rel, _), n in zip(sloc_items, count_sloc_many(sloc_items), strict=True):
            sloc_by_rel[rel] = n
    return rels, lines_by_rel, sloc_by_rel


def build_loc_report(
    *,
    ctx: ChopperContext,
    parsed: ParseResult,
    manifest: CompiledManifest,
    generated_artifacts: tuple[GeneratedArtifact, ...],
) -> LocReport:
    """Bucket the replayed before/after trees by :class:`FileTreatment`."""

    sim = simulate_trim_in_memory(ctx, parsed=parsed, manifest=manifest)
    before_rels, before_lines, before_sloc = _count_tree(sim.fs, sim.backup_root)
    _after_rels, after_lines, after_sloc = _count_tree(sim.fs, sim.domain_root)

    gen_paths: set[Path] = {art.path for art in generated_artifacts}

    fc_files = fc_lb = fc_la = fc_sb = fc_sa = 0
    pt_files = pt_lb = pt_la = pt_sb = pt_sa = 0
    rm_files = rm_lb = rm_sb = 0

    for rel in before_rels:
        treatment = manifest.file_decisions.get(rel)
        if treatment is FileTreatment.GENERATED or rel in gen_paths:
            # Regenerate-in-place source -- counted in GENERATED below.
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
            # Only PROC_TRIM remains: the enum is exhausted above.
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
            # The source already had a file here: it is the GENERATED "before".
            regenerate_in_place += 1
            gen_lb += before_lines.get(art.path, 0)
            gen_sb += before_sloc.get(art.path, 0)

    return LocReport(
        files_before=fc_files + pt_files + rm_files + regenerate_in_place,
        files_after=fc_files + pt_files + gen_files,
        lines_before=fc_lb + pt_lb + rm_lb + gen_lb,
        lines_after=fc_la + pt_la + gen_la,
        sloc_before=fc_sb + pt_sb + rm_sb + gen_sb,
        sloc_after=fc_sa + pt_sa + gen_sa,
        buckets=(
            TreatmentBucket("FULL_COPY", fc_files, fc_lb, fc_la, fc_sb, fc_sa),
            TreatmentBucket("PROC_TRIM", pt_files, pt_lb, pt_la, pt_sb, pt_sa),
            TreatmentBucket("REMOVE", rm_files, rm_lb, 0, rm_sb, 0),
            TreatmentBucket("GENERATED", gen_files, gen_lb, gen_la, gen_sb, gen_sa),
        ),
    )


def build_loc_report_baseline_only(ctx: ChopperContext) -> LocReport:
    """Baseline-only report for when the pipeline aborted before a manifest.

    ``after == before`` for every metric, all files in one ``FULL_COPY``
    bucket; per-treatment accounting is unavailable without the manifest,
    so the caller relies on the rendered diagnostics to explain why.
    """

    root = source_root(ctx)
    items: list[tuple[Path, str]] = []
    total_lines = 0
    for rel in walk_files(ctx.fs, root, extensions=TEXT_LIKE_EXTENSIONS):
        text = _read_text(ctx, root / rel)
        if text is None:
            continue
        items.append((rel, text))
        total_lines += len(text.splitlines())
    total_sloc = sum(count_sloc_many(items)) if items else 0
    file_count = len(walk_files(ctx.fs, root))

    return LocReport(
        files_before=file_count,
        files_after=file_count,
        lines_before=total_lines,
        lines_after=total_lines,
        sloc_before=total_sloc,
        sloc_after=total_sloc,
        buckets=(
            TreatmentBucket("FULL_COPY", file_count, total_lines, total_lines, total_sloc, total_sloc),
            TreatmentBucket("PROC_TRIM", 0, 0, 0, 0, 0),
            TreatmentBucket("REMOVE", 0, 0, 0, 0, 0),
            TreatmentBucket("GENERATED", 0, 0, 0, 0, 0),
        ),
    )
