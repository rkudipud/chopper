"""Selected-JSON-input preservation in the rebuilt domain (P5a tail).

Per ``technical_docs/ARCHITECTURE.md`` §5.6, after the per-file dispatch
loop has succeeded and only on a live (non-dry-run) trim, every JSON
input the run consumed is copied into the rebuilt ``<domain>/jsons/``:

* In-tree inputs (absolute path under the domain root) are preserved at
  their original domain-relative path.
* Out-of-tree inputs land in ``<domain>/jsons/_external/<NN>_<basename>``
  with a two-digit zero-padded sequence number derived from the input
  ordering. The numeric prefix mirrors the audit-bundle convention
  under ``.chopper/inputs/`` and prevents name collisions when two
  external inputs share a basename.

I/O failures during the copy step emit ``VW-20 audit-write-failed``
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
    """Copy every selected JSON input into the rebuilt ``<domain>/jsons/``.

    Returns the number of inputs successfully preserved. Caller is
    expected to gate on ``not ctx.config.dry_run`` and on a successful
    P5a dispatch loop.

    In-tree inputs (paths originally under ``domain_root``) are read
    from the backup tree, since the live trim has already torn down
    and rebuilt the domain root and the original ``<domain>/jsons/``
    contents are no longer present on disk. Out-of-tree inputs are
    read from their declared location.
    """

    domain_root = ctx.config.domain_root.resolve()
    backup_root = ctx.config.backup_root.resolve()
    jsons_root = domain_root / "jsons"
    external_root = jsons_root / "_external"

    # Ordered: project (if any) → base → features (in selection order).
    sources: list[Path] = []
    if loaded.project is not None:
        sources.append(loaded.project.source_path)
    sources.append(loaded.base.source_path)
    for feature in loaded.features:
        sources.append(feature.source_path)

    preserved = 0
    for index, src in enumerate(sources):
        try:
            resolution = _resolve_target(domain_root, backup_root, jsons_root, external_root, src, index)
            if resolution is None:
                continue
            read_from, target = resolution
            ctx.fs.mkdir(target.parent, parents=True, exist_ok=True)
            ctx.fs.copy_file(read_from, target)
            preserved += 1
        except OSError as exc:
            ctx.diag.emit(
                Diagnostic.build(
                    "VW-20",
                    phase=Phase.P5_TRIM,
                    message=f"Failed to preserve input JSON {src.as_posix()!r}: {exc}",
                    path=src,
                    hint="Preservation is best-effort; the rebuilt domain is unaffected",
                )
            )
    return preserved


def _resolve_target(
    domain_root: Path,
    backup_root: Path,
    jsons_root: Path,
    external_root: Path,
    src: Path,
    index: int,
) -> tuple[Path, Path] | None:
    """Compute ``(read_from, write_to)`` for a single input source.

    Returns ``None`` when the source should be skipped (e.g. it points
    into ``<domain>/.chopper/``, which is owned by the audit bundle).
    """

    src_resolved = src.resolve()
    try:
        rel = src_resolved.relative_to(domain_root)
    except ValueError:
        # Out-of-tree: source is still on disk at its declared path;
        # destination is <domain>/jsons/_external/NN_<basename>.
        return src_resolved, external_root / f"{index:02d}_{src_resolved.name}"

    # In-tree: the live trim has already wiped <domain>/, so the
    # original is now in the backup. Read from backup, write to the
    # rebuilt domain at the same relative path.
    if rel.parts and rel.parts[0] == ".chopper":
        return None
    return backup_root / rel, domain_root / rel
