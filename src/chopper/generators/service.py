"""GeneratorService — Phase 5b run-file emitter.

Emits one ``<stage>.tcl`` per :class:`StageSpec` in
``manifest.stages``. When ``manifest.generate_stack`` is ``True`` also
emits one ``<stage>.stack`` per stage. Stateless and deterministic:
same manifest, same artifact tuple in the same order — for each stage
the ``.tcl`` artifact appears immediately before its ``.stack``
artifact, so audit consumers can iterate pairs predictably.

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
from chopper.generators.stack_emitter import emit_stage_stack
from chopper.generators.stage_emitter import emit_stage_tcl

__all__ = ["GeneratorService"]


@dataclass(frozen=True)
class GeneratorService:
    """P5b stage run-file emitter."""

    def run(self, ctx: ChopperContext, manifest: CompiledManifest) -> tuple[GeneratedArtifact, ...]:
        """Build (and under live runs, write) one or two artifacts per stage."""

        artifacts: list[GeneratedArtifact] = []
        for stage in manifest.stages:
            tcl_artifact = emit_stage_tcl(stage)
            self._write(ctx, tcl_artifact)
            artifacts.append(tcl_artifact)

            if manifest.generate_stack:
                stack_artifact = emit_stage_stack(stage)
                self._write(ctx, stack_artifact)
                artifacts.append(stack_artifact)

        return tuple(artifacts)

    @staticmethod
    def _write(ctx: ChopperContext, artifact: GeneratedArtifact) -> None:
        """Persist ``artifact`` via ``ctx.fs`` unless we are in dry-run."""

        if ctx.config.dry_run:
            return
        target = ctx.config.domain_root / artifact.path
        try:
            ctx.fs.write_text(target, artifact.content)
        except OSError as exc:
            raise ChopperError(f"failed to write generated file {target.as_posix()!r}: {exc}") from exc
