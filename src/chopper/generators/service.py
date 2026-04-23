"""GeneratorService — Phase 5b run-file emitter.

Emits one ``<stage>.tcl`` per :class:`StageSpec` in
``manifest.stages``. Stateless and deterministic: same manifest, same
artifact tuple in the same order (manifest stage order preserved).

Signature::

    GeneratorService.run(ctx, manifest) -> tuple[GeneratedArtifact, ...]

Dry-run: the service still builds and returns the full artifact tuple
(the audit bundle needs to report what *would* have been generated)
but performs no filesystem writes.

Emits no diagnostics in v1. Any error path (I/O failure,
content-construction bug) raises :class:`ChopperError` — mapped to
exit 3 by the runner.
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
    """P5b stage run-file emitter."""

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
