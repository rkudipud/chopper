"""GeneratorService -- Phase 5b run-file emitter.

For each :class:`StageSpec` in ``manifest.stages``:

* If ``stage.standalone_stack`` is ``False``, emits ``<stage>.tcl``.
* If ``stage.standalone_stack`` is ``True``, emits ``<stage>.stack``
  (verbatim ``steps`` + Intel header) **instead of** ``<stage>.tcl`` --
  the standalone stack becomes the stage's sole driver.
The Intel header is injected at the top of a per-stage file only when
its steps do not already own a header (line-1 ``#!`` shebang or a
leading copyright notice) -- see :func:`chopper.core.header.needs_header`.
Additionally, when ``manifest.options.generate_stack`` is ``True`` and
``manifest.stages`` is non-empty, emits exactly one aggregate
``<domain>.stack`` (where ``<domain>`` is ``ctx.config.domain_root.name``)
containing one record per stage. Record order is
``manifest.stack_order`` (topological per the compiler's
:func:`compute_stack_order`), or ``manifest.stages`` order when
``stack_order`` is empty. The aggregate is appended *after* the
per-stage loop so its artifact slot is last and predictable for audit
consumers. On a v2 run the ``<domain>_feature_vars.tcl`` and
``<domain>_feature_procs.tcl`` sourcing files (ARCHITECTURE.md Sec.3.12)
are emitted after the per-stage files and before the aggregate stack,
and every aggregate record lists them as ``I`` inputs.

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
from chopper.generators.vars_emitter import emit_feature_vars

__all__ = ["GeneratorService"]


@dataclass(frozen=True)
class GeneratorService:
    """P5b stage run-file emitter."""

    def run(self, ctx: ChopperContext, manifest: CompiledManifest) -> tuple[GeneratedArtifact, ...]:
        """Build (and under live runs, write) the F3 artifact set."""

        artifacts: list[GeneratedArtifact] = []
        for stage in manifest.stages:
            if stage.standalone_stack:
                artifact = emit_standalone_stack(stage)
            else:
                artifact = emit_stage_tcl(stage)
            self._write(ctx, artifact)
            artifacts.append(artifact)

        sourcing: list[GeneratedArtifact] = []
        if manifest.feature_vars is not None:
            sourcing.append(emit_feature_vars(ctx.config.domain_root.name, manifest.feature_vars))

        if manifest.feature_procs is not None:
            sourcing.append(emit_feature_vars(ctx.config.domain_root.name, manifest.feature_procs, procs=True))

        for artifact in sourcing:
            self._write(ctx, artifact)
            artifacts.append(artifact)

        if manifest.options.generate_stack and manifest.stages:
            aggregate = emit_flow_stack(
                manifest.stages,
                ctx.config.domain_root.name,
                manifest.stack_order,
                extra_inputs=tuple(a.path.as_posix() for a in sourcing),
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
