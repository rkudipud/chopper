"""The single phase-sequencing driver.

:class:`ChopperRunner` is the only place Chopper phases are ordered.
Every service runs through its ``run()`` method; every gate decision
routes through :func:`chopper.orchestrator.gates.has_errors`.
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from typing import Literal

from chopper.audit.internal_error import write_internal_error_log
from chopper.audit.service import AuditService
from chopper.compiler.merge_service import CompilerService
from chopper.compiler.trace_service import TracerService
from chopper.config.service import ConfigService
from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Phase
from chopper.core.errors import ChopperError
from chopper.core.models_audit import InternalError, RunRecord, RunResult
from chopper.core.models_common import DomainState, FileTreatment
from chopper.core.models_compiler import CompiledManifest, DependencyGraph
from chopper.core.models_config import LoadedConfig
from chopper.core.models_parser import ParseResult
from chopper.core.models_trimmer import GeneratedArtifact, TrimReport
from chopper.generators.service import GeneratorService
from chopper.orchestrator.domain_state import DomainStateService
from chopper.orchestrator.gates import has_errors
from chopper.parser.service import ParserService
from chopper.trimmer.service import TrimmerService
from chopper.validator import validate_post, validate_pre

__all__ = ["ChopperRunner"]


class ChopperRunner:
    """Sequence P0 → P7 for a single invocation.

    The runner constructs no state of its own beyond what lives inside
    ``ctx``; every per-phase value is a local, so gate aborts are plain
    early returns.
    """

    def run(
        self,
        ctx: ChopperContext,
        *,
        command: Literal["validate", "trim"] = "trim",
    ) -> RunResult:
        started_at = datetime.now(UTC)
        run_id = uuid.uuid4().hex

        state: DomainState | None = None
        loaded: LoadedConfig | None = None
        parsed: ParseResult | None = None
        manifest: CompiledManifest | None = None
        graph: DependencyGraph | None = None
        trim_report: TrimReport | None = None
        artifacts: tuple[GeneratedArtifact, ...] = ()
        exit_code = 0
        internal_error: InternalError | None = None

        try:
            # P0 — Domain state.
            ctx.progress.phase_started(Phase.P0_STATE)
            state = DomainStateService().run(ctx)
            ctx.progress.phase_done(Phase.P0_STATE)
            if state.case == 4:
                exit_code = 2
                return self._build(ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts)

            # P1a — Config load.
            ctx.progress.phase_started(Phase.P1_CONFIG)
            loaded = ConfigService().run(ctx, state)
            # P1b — Pre-validation.
            validate_pre(ctx, loaded)
            ctx.progress.phase_done(Phase.P1_CONFIG)
            if has_errors(ctx, Phase.P1_CONFIG):
                exit_code = 1
                return self._build(ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts)

            # P2 — Parse.
            ctx.progress.phase_started(Phase.P2_PARSE)
            # Paths are domain-relative throughout the pipeline; the
            # parser resolves against ``domain_root`` at the I/O
            # boundary (see ``ParserService._resolve_for_read``).
            # Pass ``loaded`` for O1 domain-file-cache optimization.
            parsed = ParserService().run(ctx, loaded.surface_files, loaded=loaded)
            ctx.progress.phase_done(Phase.P2_PARSE)
            if has_errors(ctx, Phase.P2_PARSE):
                exit_code = 1
                return self._build(ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts)

            # P3 — Compile.
            ctx.progress.phase_started(Phase.P3_COMPILE)
            manifest = CompilerService().run(ctx, loaded, parsed)
            ctx.progress.phase_done(Phase.P3_COMPILE)
            if has_errors(ctx, Phase.P3_COMPILE):
                exit_code = 1
                return self._build(ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts)

            # P4 — Trace (reporting-only; no gate).
            ctx.progress.phase_started(Phase.P4_TRACE)
            graph = TracerService().run(ctx, manifest, parsed, loaded)
            ctx.progress.phase_done(Phase.P4_TRACE)

            if not ctx.config.dry_run:
                # P5a — Trim.
                ctx.progress.phase_started(Phase.P5_TRIM)
                trim_report = TrimmerService().run(ctx, manifest, parsed, state)
                if has_errors(ctx, Phase.P5_TRIM):
                    ctx.progress.phase_done(Phase.P5_TRIM)
                    exit_code = 1
                    return self._build(ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts)
                # P5b — Generators.
                artifacts = GeneratorService().run(ctx, manifest)
                ctx.progress.phase_done(Phase.P5_TRIM)

                # P6 — Post-validate over rewritten files.
                # "Rewritten" = files the trimmer re-tokenised and wrote
                # (PROC_TRIM). FULL_COPY files are verbatim copies — they
                # were validated at P2 and don't need re-checking.
                rewritten = tuple(
                    ctx.config.domain_root / outcome.path
                    for outcome in trim_report.outcomes
                    if outcome.treatment is FileTreatment.PROC_TRIM
                )
                ctx.progress.phase_started(Phase.P6_POSTVALIDATE)
                validate_post(ctx, manifest, graph, rewritten)
                ctx.progress.phase_done(Phase.P6_POSTVALIDATE)
                if has_errors(ctx, Phase.P6_POSTVALIDATE):
                    exit_code = 1
                    return self._build(ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts)
            else:
                # Dry-run P6: manifest-derivable checks only.
                ctx.progress.phase_started(Phase.P6_POSTVALIDATE)
                validate_post(ctx, manifest, graph, rewritten=())
                ctx.progress.phase_done(Phase.P6_POSTVALIDATE)
                if has_errors(ctx, Phase.P6_POSTVALIDATE):
                    exit_code = 1
                    return self._build(ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts)

            # Strict-mode warning escalation (exit policy only).
            summary = ctx.diag.finalize()
            if ctx.config.strict and summary.has_warning:
                exit_code = 1

            return self._build(
                ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts, internal_error
            )
        except ChopperError as exc:
            # Internal programmer error explicitly raised by a service — exit 3.
            exit_code = 3
            internal_error = write_internal_error_log(ctx, run_id=run_id, exc=exc)
            return self._build(
                ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts, internal_error
            )
        except Exception as exc:
            # Any other unhandled exception escaping a service is also a
            # programmer error per architecture doc §5.12.5 — exit 3 +
            # internal-error.log so users have a deterministic recovery
            # artifact instead of a raw Python traceback.
            exit_code = 3
            internal_error = write_internal_error_log(ctx, run_id=run_id, exc=exc)
            return self._build(
                ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts, internal_error
            )
        finally:
            # Audit always runs, even on failure.
            try:
                ended_at = datetime.now(UTC)
                record = RunRecord(
                    run_id=run_id,
                    command=command,
                    started_at=started_at,
                    ended_at=ended_at if ended_at >= started_at else started_at,
                    exit_code=exit_code,
                    state=state,
                    loaded=loaded,
                    parsed=parsed,
                    manifest=manifest,
                    graph=graph,
                    trim_report=trim_report,
                    generated_artifacts=artifacts,
                    internal_error=internal_error,
                )
                AuditService().run(ctx, record)
            except Exception as audit_exc:
                # Audit must never mask the primary failure. Best-effort:
                # surface the bug to stderr so test harnesses see it
                # instead of a silent swallow.
                sys.stderr.write(
                    f"[chopper] internal: audit bundle failed to write: {type(audit_exc).__name__}: {audit_exc}\n"
                )

    def _build(
        self,
        ctx: ChopperContext,
        exit_code: int,
        state: DomainState | None,
        loaded: LoadedConfig | None,
        parsed: ParseResult | None,
        manifest: CompiledManifest | None,
        graph: DependencyGraph | None,
        trim_report: TrimReport | None,
        artifacts: tuple[GeneratedArtifact, ...],
        internal_error: InternalError | None = None,
    ) -> RunResult:
        summary = ctx.diag.finalize()
        return RunResult(
            exit_code=exit_code,
            summary=summary,
            state=state,
            loaded=loaded,
            parsed=parsed,
            manifest=manifest,
            graph=graph,
            trim_report=trim_report,
            generated_artifacts=artifacts,
            internal_error=internal_error,
        )
