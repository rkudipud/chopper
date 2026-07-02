"""In-memory trim replay for ``chopper loc`` (ARCHITECTURE.md Sec.5.7).

``chopper loc`` reports the SLOC impact of a planned trim without
mutating the real domain. To make its before/after numbers match a
live ``chopper trim`` byte-for-byte, this module replays the real P5
trim phases (P5a trim -> P5b generators -> P5c indentation -> P5d
companion sync) against an in-memory copy of the source tree and
returns the resulting filesystem so the LOC reporter can count the
*actual* trimmed output rather than estimating it.

The replay reuses the production services unchanged -- there is no
parallel "estimator" to drift out of sync with the trimmer. The only
inputs are the manifest and parse result already computed by the
dry-run pipeline, so the heavy P0-P4 work is not repeated.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from chopper.adapters.fs_memory import InMemoryFS
from chopper.adapters.progress_silent import SilentProgress
from chopper.adapters.sink_collecting import CollectingSink
from chopper.core.context import ChopperContext
from chopper.core.fs_walk import walk_files
from chopper.core.models_common import DomainState
from chopper.core.models_compiler import CompiledManifest
from chopper.core.models_config import LoadedConfig
from chopper.core.models_parser import ParseResult
from chopper.generators.service import GeneratorService
from chopper.trimmer.companion_sync import CompanionSyncService
from chopper.trimmer.indentation import TclIndentationService
from chopper.trimmer.service import TrimmerService

__all__ = ["SimulatedTrim", "simulate_trim_in_memory"]


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


def _source_root(ctx: ChopperContext) -> Path:
    """Mirror :func:`chopper.cli.loc_report._source_root`."""

    if ctx.fs.exists(ctx.config.backup_root):
        return ctx.config.backup_root
    return ctx.config.domain_root


def _read_text(ctx: ChopperContext, path: Path) -> str | None:
    """Read ``path`` via the real filesystem with a latin-1 fallback."""

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
    loaded: LoadedConfig,
    parsed: ParseResult,
    manifest: CompiledManifest,
) -> SimulatedTrim:
    """Replay the P5 trim phases against an in-memory copy of the source.

    The real source tree (``backup_root`` when it exists, else
    ``domain_root``) is copied into a fresh :class:`InMemoryFS` laid out
    as a clean Case-1 domain (domain present, no backup). The real P5
    services then run with ``dry_run=False`` so the in-memory domain is
    rebuilt identically to a live trim. Diagnostics and progress are
    discarded -- the caller already rendered them from the dry-run pass.
    """

    domain_root = ctx.config.domain_root
    backup_root = ctx.config.backup_root
    src_root = _source_root(ctx)

    seed: dict[Path, str] = {}
    for rel in walk_files(ctx.fs, src_root):
        text = _read_text(ctx, src_root / rel)
        if text is None:
            continue
        seed[domain_root / rel] = text

    # walk_files excludes ``.json`` files via EXCLUDED_SUFFIXES so authoring
    # artifacts are never counted as domain SLOC.  However, the trimmer
    # copies surviving json files (e.g. jsons/base.json) from backup to the
    # rebuilt domain.  If those files are absent from the InMemoryFS seed the
    # trimmer gets FileNotFoundError, breaks its per-file dispatch loop, and
    # files sorted after jsons/ (kpi_metrics.tcl, procs.tcl, ...) are never
    # written -- producing a severely undercounted sloc_after in the loc report.
    # Seed them separately so the trimmer loop completes without interruption.
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
    # Reconstruct a clean Case-1 layout: domain present, backup absent.
    state = DomainState(case=1, domain_exists=True, backup_exists=False, hand_edited=False)

    trim_report = TrimmerService().run(mem_ctx, manifest, parsed, state)
    artifacts = GeneratorService().run(mem_ctx, manifest)
    trim_report, _artifacts, _rewritten = TclIndentationService().run(
        mem_ctx,
        manifest,
        trim_report,
        artifacts,
        enabled=loaded.base.options.indent,
    )
    CompanionSyncService().run(mem_ctx, manifest, trim_report)

    return SimulatedTrim(fs=memfs, domain_root=domain_root, backup_root=backup_root)
