"""GeneratorService — Phase 5b (P5b) of the Chopper pipeline.

Emits one ``<stage>.tcl`` file per resolved
:class:`~chopper.core.models.StageSpec` in ``manifest.stages``.

Per ARCHITECTURE_PLAN.md §6 and §9.2, the canonical signature is::

    GeneratorService.run(ctx, manifest) -> tuple[GeneratedArtifact, ...]

The service is stateless and deterministic: given the same manifest,
it returns the same artifact tuple in the same order (stage order
from the manifest is preserved).

Dry-run handling
----------------
When ``ctx.config.dry_run`` is true the service still **builds** and
returns the full artifact tuple — the audit bundle must be able to
report "what would have been generated" — but performs no filesystem
writes. This mirrors the trimmer's dry-run contract.

Diagnostics
-----------
This service emits no diagnostics in v1. Any error path (I/O failure,
content-construction bug) raises :class:`~chopper.core.errors.ChopperError`
and is mapped to exit 3 by the runner.
"""

from __future__ import annotations

from dataclasses import dataclass

from chopper.core.context import ChopperContext
from chopper.core.errors import ChopperError
from chopper.core.models import CompiledManifest, GeneratedArtifact
from chopper.generators.stage_emitter import emit_stage_tcl

__all__ = ["GeneratorService"]


@dataclass(frozen=True)
class GeneratorService:
    """P5b stage run-file emitter (bible §§3.6, 5.3)."""

    def run(self, ctx: ChopperContext, manifest: CompiledManifest) -> tuple[GeneratedArtifact, ...]:
        """Build (and under live runs, write) one artifact per resolved stage."""

        artifacts: list[GeneratedArtifact] = []
        for stage in manifest.stages:
            artifact = emit_stage_tcl(stage)
            if not ctx.config.dry_run:
                target = ctx.config.domain_root / artifact.path
                try:
                    ctx.fs.write_text(target, artifact.content)
                except OSError as exc:
                    raise ChopperError(f"failed to write generated stage file {target.as_posix()!r}: {exc}") from exc
            artifacts.append(artifact)

        return tuple(artifacts)
