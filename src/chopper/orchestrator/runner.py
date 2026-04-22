"""The single phase-sequencing driver.

:class:`ChopperRunner` is the only place Chopper phases are ordered.
Every service runs through its ``run()`` method; every gate decision
routes through :func:`chopper.orchestrator.gates.has_errors`.

Sketch authoritative reference: ARCHITECTURE_PLAN.md §6.2.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from chopper.audit.service import AuditService
from chopper.compiler.merge_service import CompilerService
from chopper.compiler.trace_service import TracerService
from chopper.config.service import ConfigService
from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Phase
from chopper.core.errors import ChopperError
from chopper.core.models import (
    CompiledManifest,
    DependencyGraph,
    DomainState,
    FileTreatment,
    GeneratedArtifact,
    LoadedConfig,
    ParseResult,
    RunRecord,
    RunResult,
    TrimReport,
)
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
            parsed = ParserService().run(ctx, loaded.surface_files)
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
            graph = TracerService().run(ctx, manifest, parsed)
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

            return self._build(ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts)
        except ChopperError:
            # Internal programmer error — exit 3 per bible §8.2 rule 4.
            exit_code = 3
            return self._build(ctx, exit_code, state, loaded, parsed, manifest, graph, trim_report, artifacts)
        finally:
            # P7 always runs (bible §5.5.10).
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
                )
                AuditService().run(ctx, record)
            except Exception:
                # Never mask the primary failure (bible §5.5.10).
                pass

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
        )
