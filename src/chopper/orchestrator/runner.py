"""The single composer (architecture doc Sec.5.2).

This module is the only owner of phase order, gates, the exception
boundary, and run bookkeeping:

* :class:`Providers` -- frozen bundle of typed callables, one per phase
  implementation. :func:`default_providers` is the single composition root.
* :class:`RunLedger` -- private, mutable record of each phase result as it
  lands, projected to the frozen :class:`RunResult` / :class:`RunRecord`.
* :func:`execute_output` -- the one P5 sequence (trim -> generate ->
  indentation -> companion sync), shared by live trim and the
  ``chopper loc`` in-memory projection.
* :class:`ChopperRunner` -- sequences P0 -> P7 for a single invocation.

Every gate decision routes through :func:`chopper.orchestrator.gates.has_errors`.
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from chopper.audit.internal_error import write_internal_error_log
from chopper.audit.service import AuditService
from chopper.compiler.merge_service import CompilerService
from chopper.compiler.trace_service import TracerService
from chopper.config.service import ConfigService
from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Phase
from chopper.core.models_audit import AuditManifest, InternalError, RunRecord, RunResult
from chopper.core.models_common import DomainState
from chopper.core.models_compiler import CompiledManifest, DependencyGraph
from chopper.core.models_config import LoadedConfig
from chopper.core.models_parser import ParseResult
from chopper.core.models_trimmer import GeneratedArtifact, TrimReport
from chopper.generators.service import GeneratorService
from chopper.orchestrator.domain_state import DomainStateService
from chopper.orchestrator.gates import has_errors
from chopper.parser.service import ParserService
from chopper.trimmer.companion_sync import CompanionSyncService
from chopper.trimmer.indentation import TclIndentationService
from chopper.trimmer.service import TrimmerService
from chopper.validator import validate_post, validate_pre

__all__ = ["ChopperRunner", "Providers", "RunLedger", "default_providers", "execute_output"]

Artifacts = tuple[GeneratedArtifact, ...]


@dataclass(frozen=True)
class Providers:
    """One typed callable per phase implementation.

    Swap one implementation with
    ``ChopperRunner(providers=replace(default_providers(), trim=my_trim))``.
    """

    domain_state: Callable[[ChopperContext], DomainState]
    load_config: Callable[[ChopperContext, DomainState], LoadedConfig]
    validate_pre: Callable[[ChopperContext, LoadedConfig], None]
    parse: Callable[..., ParseResult]
    compile: Callable[[ChopperContext, LoadedConfig, ParseResult], CompiledManifest]
    trace: Callable[[ChopperContext, CompiledManifest, ParseResult, LoadedConfig], DependencyGraph]
    trim: Callable[[ChopperContext, CompiledManifest, ParseResult, DomainState], TrimReport]
    generate: Callable[[ChopperContext, CompiledManifest], Artifacts]
    indent: Callable[
        [ChopperContext, CompiledManifest, TrimReport, Artifacts],
        tuple[TrimReport, Artifacts, tuple[Path, ...]],
    ]
    sync_companions: Callable[[ChopperContext, CompiledManifest, TrimReport], TrimReport]
    preserve_inputs: Callable[[ChopperContext, LoadedConfig], int]
    validate_post: Callable[..., None]
    audit: Callable[[ChopperContext, RunRecord], AuditManifest]


def _preserve_inputs(ctx: ChopperContext, loaded: LoadedConfig) -> int:
    # Imported at call time so the function stays patchable at its home module.
    from chopper.trimmer.input_preserver import preserve_input_sources

    return preserve_input_sources(ctx, loaded)


def default_providers() -> Providers:
    """The single composition root.

    Each callable resolves its service from this module at call time and
    constructs it exactly when its phase runs.
    """

    return Providers(
        domain_state=lambda ctx: DomainStateService().run(ctx),
        load_config=lambda ctx, state: ConfigService().run(ctx, state),
        validate_pre=lambda ctx, loaded: validate_pre(ctx, loaded),
        parse=lambda ctx, files, *, loaded=None: ParserService().run(ctx, files, loaded=loaded),
        compile=lambda ctx, loaded, parsed: CompilerService().run(ctx, loaded, parsed),
        trace=lambda ctx, manifest, parsed, loaded: TracerService().run(ctx, manifest, parsed, loaded),
        trim=lambda ctx, manifest, parsed, state: TrimmerService().run(ctx, manifest, parsed, state),
        generate=lambda ctx, manifest: GeneratorService().run(ctx, manifest),
        indent=lambda ctx, manifest, report, arts: TclIndentationService().run(ctx, manifest, report, arts),
        sync_companions=lambda ctx, manifest, report: CompanionSyncService().run(ctx, manifest, report),
        preserve_inputs=_preserve_inputs,
        validate_post=lambda *args, **kwargs: validate_post(*args, **kwargs),
        audit=lambda ctx, record: AuditService().run(ctx, record),
    )


@dataclass
class RunLedger:
    """Mutable per-run bookkeeping; services never receive it."""

    state: DomainState | None = None
    loaded: LoadedConfig | None = None
    parsed: ParseResult | None = None
    manifest: CompiledManifest | None = None
    graph: DependencyGraph | None = None
    trim_report: TrimReport | None = None
    artifacts: Artifacts = ()
    rewritten: tuple[Path, ...] = ()
    exit_code: int = 0
    internal_error: InternalError | None = None

    def result(self, ctx: ChopperContext, exit_code: int) -> RunResult:
        self.exit_code = exit_code
        return RunResult(
            exit_code=exit_code,
            summary=ctx.diag.finalize(),
            state=self.state,
            loaded=self.loaded,
            parsed=self.parsed,
            manifest=self.manifest,
            graph=self.graph,
            trim_report=self.trim_report,
            generated_artifacts=self.artifacts,
            internal_error=self.internal_error,
        )

    def record(
        self,
        *,
        run_id: str,
        command: Literal["validate", "trim", "cleanup", "loc"],
        started_at: datetime,
    ) -> RunRecord:
        ended_at = datetime.now(UTC)
        return RunRecord(
            run_id=run_id,
            command=command,
            started_at=started_at,
            ended_at=ended_at if ended_at >= started_at else started_at,
            exit_code=self.exit_code,
            state=self.state,
            loaded=self.loaded,
            parsed=self.parsed,
            manifest=self.manifest,
            graph=self.graph,
            trim_report=self.trim_report,
            generated_artifacts=self.artifacts,
            internal_error=self.internal_error,
        )


def execute_output(
    ctx: ChopperContext,
    providers: Providers,
    ledger: RunLedger,
    *,
    manifest: CompiledManifest,
    parsed: ParseResult,
    state: DomainState,
    gated: bool,
) -> TrimReport | None:
    """Run P5a trim -> P5b generate -> P5c indentation -> P5d companion sync.

    Each result lands in ``ledger`` as soon as it is produced, so a failure
    mid-sequence still audits the partial run. Returns the final
    :class:`TrimReport`, or ``None`` when ``gated`` and a P5 error stopped
    the sequence. Emits no progress events; the caller brackets P5.
    """

    ledger.trim_report = providers.trim(ctx, manifest, parsed, state)
    if gated and has_errors(ctx, Phase.P5_TRIM):
        return None
    ledger.artifacts = providers.generate(ctx, manifest)
    # P5c is a pass-through unless ``options.indent`` is set, but it always
    # returns the rewritten-path set so P6 brace-checks every final .tcl.
    ledger.trim_report, ledger.artifacts, ledger.rewritten = providers.indent(
        ctx, manifest, ledger.trim_report, ledger.artifacts
    )
    if gated and has_errors(ctx, Phase.P5_TRIM):
        return None
    ledger.trim_report = providers.sync_companions(ctx, manifest, ledger.trim_report)
    return ledger.trim_report


class ChopperRunner:
    """Sequence P0 -> P7 for a single invocation."""

    def __init__(self, providers: Providers | None = None) -> None:
        self._providers = providers

    def run(
        self,
        ctx: ChopperContext,
        *,
        command: Literal["validate", "trim", "loc"] = "trim",
    ) -> RunResult:
        started_at = datetime.now(UTC)
        run_id = uuid.uuid4().hex
        p = self._providers or default_providers()
        ledger = RunLedger()

        try:
            ctx.progress.phase_started(Phase.P0_STATE)
            state = ledger.state = p.domain_state(ctx)
            ctx.progress.phase_done(Phase.P0_STATE)
            if state.case == 4:
                return ledger.result(ctx, 2)

            ctx.progress.phase_started(Phase.P1_CONFIG)
            loaded = ledger.loaded = p.load_config(ctx, state)
            p.validate_pre(ctx, loaded)
            ctx.progress.phase_done(Phase.P1_CONFIG)
            if has_errors(ctx, Phase.P1_CONFIG):
                return ledger.result(ctx, 1)

            ctx.progress.phase_started(Phase.P2_PARSE)
            # Paths stay domain-relative; ``loaded`` enables the domain-file cache.
            parsed = ledger.parsed = p.parse(ctx, loaded.surface_files, loaded=loaded)
            ctx.progress.phase_done(Phase.P2_PARSE)
            if has_errors(ctx, Phase.P2_PARSE):
                return ledger.result(ctx, 1)

            ctx.progress.phase_started(Phase.P3_COMPILE)
            manifest = ledger.manifest = p.compile(ctx, loaded, parsed)
            ctx.progress.phase_done(Phase.P3_COMPILE)
            if has_errors(ctx, Phase.P3_COMPILE):
                return ledger.result(ctx, 1)

            # P4 is reporting-only: no gate.
            ctx.progress.phase_started(Phase.P4_TRACE)
            graph = ledger.graph = p.trace(ctx, manifest, parsed, loaded)
            ctx.progress.phase_done(Phase.P4_TRACE)

            if not ctx.config.dry_run:
                ctx.progress.phase_started(Phase.P5_TRIM)
                trim_report = execute_output(ctx, p, ledger, manifest=manifest, parsed=parsed, state=state, gated=True)
                if trim_report is None:
                    ctx.progress.phase_done(Phase.P5_TRIM)
                    return ledger.result(ctx, 1)
                # P5a tail: mirror jsons/ into the rebuilt domain (Sec.5.6).
                preserved = p.preserve_inputs(ctx, loaded)
                if preserved:
                    trim_report = ledger.trim_report = replace(trim_report, inputs_preserved=preserved)
                ctx.progress.phase_done(Phase.P5_TRIM)

                ctx.progress.phase_started(Phase.P6_POSTVALIDATE)
                p.validate_post(
                    ctx,
                    manifest,
                    graph,
                    ledger.rewritten,
                    trim_report=trim_report,
                    tool_command_pool=loaded.tool_command_pool,
                )
            else:
                # Dry run: generators respect ``dry_run`` and write nothing;
                # P6 validates the in-memory artifacts.
                ledger.artifacts = p.generate(ctx, manifest)
                ctx.progress.phase_started(Phase.P6_POSTVALIDATE)
                p.validate_post(
                    ctx,
                    manifest,
                    graph,
                    rewritten=(),
                    generated_artifacts=ledger.artifacts,
                    trim_report=None,
                    tool_command_pool=loaded.tool_command_pool,
                )
            ctx.progress.phase_done(Phase.P6_POSTVALIDATE)
            if has_errors(ctx, Phase.P6_POSTVALIDATE):
                return ledger.result(ctx, 1)

            # --strict is exit-code policy only; severities are never rewritten.
            summary = ctx.diag.finalize()
            return ledger.result(ctx, 1 if ctx.config.strict and summary.has_warning else 0)
        except Exception as exc:
            # ChopperError and any other escaping exception are programmer
            # errors (Sec.5.12.5): exit 3 plus a deterministic internal-error.log.
            ledger.exit_code = 3
            ledger.internal_error = write_internal_error_log(ctx, run_id=run_id, exc=exc)
            return ledger.result(ctx, 3)
        finally:
            # P7 audit always runs from whatever the ledger holds -- except for
            # read-only ``chopper loc`` (Sec.5.7). No ``return`` here: it would
            # clobber the result produced above.
            if command != "loc":
                try:
                    p.audit(ctx, ledger.record(run_id=run_id, command=command, started_at=started_at))
                except Exception as audit_exc:
                    # Audit must never mask the primary failure.
                    sys.stderr.write(
                        f"[chopper] internal: audit bundle failed to write: {type(audit_exc).__name__}: {audit_exc}\n"
                    )
