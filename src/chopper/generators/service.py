"""GeneratorService -- Phase 5b run-file emitter.

For each :class:`StageSpec` in ``manifest.stages``:

* If ``stage.standalone_stack`` is ``False``, emits ``<stage>.tcl``.
* If ``stage.standalone_stack`` is ``True``, emits ``<stage>.stack``
  (verbatim ``steps`` + Intel header) **instead of** ``<stage>.tcl`` --
  the standalone stack becomes the stage's sole driver.

Additionally, when ``manifest.generate_stack`` is ``True`` and
``manifest.stages`` is non-empty, emits exactly one aggregate
``<domain>.stack`` (where ``<domain>`` is ``ctx.config.domain_root.name``)
containing one record per stage. Record order is
``manifest.stack_order`` (topological per the compiler's
:func:`compute_stack_order`), or ``manifest.stages`` order when
``stack_order`` is empty. The aggregate is appended *after* the
per-stage loop so its artifact slot is last and predictable for audit
consumers.

Stateless and deterministic: same manifest, same artifact tuple in the
same order.

Signature::

    GeneratorService.run(ctx, manifest) -> tuple[GeneratedArtifact, ...]

Dry-run: the service still builds and returns the full artifact tuple
(the audit bundle needs to report what *would* have been generated)
but performs no filesystem writes.

Emits no diagnostics in v1. Any error path (I/O failure,
content-construction bug) raises :class:`ChopperError` -- mapped to
exit 3 by the runner.
"""

from __future__ import annotations

from dataclasses import dataclass

from chopper.core.context import ChopperContext
from chopper.core.errors import ChopperError
from chopper.core.file_perms import ensure_executable, mirror_perms_plus_exec
from chopper.core.models_compiler import CompiledManifest
from chopper.core.models_trimmer import GeneratedArtifact
from chopper.generators.stack_emitter import emit_flow_stack, emit_standalone_stack
from chopper.generators.stage_emitter import emit_stage_tcl

__all__ = ["GeneratorService"]


@dataclass(frozen=True)
class GeneratorService:
    """P5b stage run-file emitter."""

    def run(self, ctx: ChopperContext, manifest: CompiledManifest) -> tuple[GeneratedArtifact, ...]:
        """Build (and under live runs, write) the F3 artifact set."""

        artifacts: list[GeneratedArtifact] = []
        for stage in manifest.stages:
            if not stage.standalone_stack:
                tcl_artifact = emit_stage_tcl(stage)
                self._write(ctx, tcl_artifact)
                artifacts.append(tcl_artifact)

            if stage.standalone_stack:
                standalone_artifact = emit_standalone_stack(stage)
                self._write(ctx, standalone_artifact)
                artifacts.append(standalone_artifact)

        if manifest.generate_stack and manifest.stages:
            aggregate = emit_flow_stack(
                manifest.stages,
                ctx.config.domain_root.name,
                manifest.stack_order,
            )
            self._write(ctx, aggregate)
            artifacts.append(aggregate)

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

        # Match the trimmer's policy: every final file in the rebuilt
        # domain gets ``a+x``. For the regenerate-in-place case (a
        # generated artifact whose path also existed in the source
        # domain) we additionally mirror the source mode bits, so the
        # rebuilt file carries the same read/write/setuid/sticky
        # permissions as the original on top of guaranteed exec.
        backup_src = ctx.config.backup_root / artifact.path
        if backup_src.is_file():
            mirror_perms_plus_exec(backup_src, target)
        else:
            ensure_executable(target)
