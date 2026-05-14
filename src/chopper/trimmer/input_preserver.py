"""Selected-JSON-input preservation in the rebuilt domain (P5a tail).

Per ``technical_docs/ARCHITECTURE.md`` §5.6, after the per-file dispatch
loop has succeeded and only on a live (non-dry-run) trim, the entire
``jsons/`` directory from the backup is mirrored into the rebuilt
``<domain>/jsons/``:

* The whole ``<domain_backup>/jsons/`` subtree is copied verbatim so
  every JSON that existed in the original domain — selected or not —
  is present in the rebuilt domain without ambiguity.
* Out-of-tree inputs (absolute paths outside the domain root) are
  additionally copied to ``<domain>/jsons/_external/<NN>_<basename>``
  with a two-digit zero-padded sequence number derived from the input
  ordering. The numeric prefix mirrors the audit-bundle convention
  under ``.chopper/inputs/`` and prevents name collisions when two
  external inputs share a basename.

I/O failures during either copy step emit ``VW-20 audit-write-failed``
(severity warning, exit 0) and the run continues — preservation is a
convenience, not a hard guarantee. The rebuilt domain remains the
primary deliverable.
"""

from __future__ import annotations

from pathlib import Path

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models_config import LoadedConfig

__all__ = ["preserve_input_sources"]


def preserve_input_sources(ctx: ChopperContext, loaded: LoadedConfig) -> int:
    """Mirror ``<domain_backup>/jsons/`` into the rebuilt domain and copy
    any out-of-tree inputs to ``<domain>/jsons/_external/``.

    Returns the total number of files preserved. Caller is expected to gate
    on ``not ctx.config.dry_run`` and on a successful P5a dispatch loop.

    The entire backup ``jsons/`` directory is copied verbatim so the rebuilt
    domain is unambiguous: every JSON that existed under the original
    ``<domain>/jsons/`` — selected or not — is present in the rebuilt
    domain. Out-of-tree inputs are additionally placed in
    ``<domain>/jsons/_external/`` with a two-digit sequence prefix so they
    are accessible without consulting external paths.
    """

    domain_root = ctx.config.domain_root.resolve()
    backup_root = ctx.config.backup_root.resolve()
    backup_jsons = backup_root / "jsons"
    domain_jsons = domain_root / "jsons"
    external_root = domain_jsons / "_external"

    preserved = 0

    # --- Step 1: mirror the entire jsons/ tree from backup ---
    if ctx.fs.exists(backup_jsons):
        try:
            ctx.fs.mkdir(domain_jsons, parents=True, exist_ok=True)
            preserved += _copy_dir(ctx, backup_jsons, domain_jsons)
        except OSError as exc:
            ctx.diag.emit(
                Diagnostic.build(
                    "VW-20",
                    phase=Phase.P5_TRIM,
                    message=f"Failed to copy jsons/ directory from backup: {exc}",
                    path=backup_jsons,
                    hint="Preservation is best-effort; the rebuilt domain is unaffected",
                )
            )

    # --- Step 2: out-of-tree inputs → _external/<NN>_<basename> ---
    sources: list[Path] = []
    if loaded.project is not None:
        sources.append(loaded.project.source_path)
    sources.append(loaded.base.source_path)
    for feature in loaded.features:
        sources.append(feature.source_path)

    for index, src in enumerate(sources):
        src_resolved = src.resolve()
        try:
            src_resolved.relative_to(domain_root)
            # In-tree: already covered by the jsons/ tree copy above; skip.
        except ValueError:
            # Out-of-tree: copy to _external/<NN>_<basename>.
            try:
                target = external_root / f"{index:02d}_{src_resolved.name}"
                ctx.fs.mkdir(external_root, parents=True, exist_ok=True)
                ctx.fs.copy_file(src_resolved, target)
                preserved += 1
            except OSError as exc:
                ctx.diag.emit(
                    Diagnostic.build(
                        "VW-20",
                        phase=Phase.P5_TRIM,
                        message=f"Failed to preserve external input JSON {src.as_posix()!r}: {exc}",
                        path=src,
                        hint="Preservation is best-effort; the rebuilt domain is unaffected",
                    )
                )

    return preserved


def _copy_dir(ctx: ChopperContext, src: Path, dst: Path) -> int:
    """Recursively copy all files under ``src`` into ``dst``.

    Creates intermediate directories as needed. Returns the count of
    regular files copied. ``dst`` must already exist before this is
    called (the caller creates it).
    """
    count = 0
    for child in ctx.fs.list(src):
        stat = ctx.fs.stat(child)
        rel = child.relative_to(src)
        dst_child = dst / rel
        if stat.is_dir:
            ctx.fs.mkdir(dst_child, parents=True, exist_ok=True)
            count += _copy_dir(ctx, child, dst_child)
        else:
            ctx.fs.mkdir(dst_child.parent, parents=True, exist_ok=True)
            ctx.fs.copy_file(child, dst_child)
            count += 1
    return count
