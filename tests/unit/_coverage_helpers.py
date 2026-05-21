"""Shared test helpers for redistributed coverage tests.

This module provides the ``_Sink`` / ``_Progress`` / ``_ctx`` / ``_codes``
fixtures and the ``DOMAIN`` / ``BACKUP`` / ``AUDIT`` path constants that
were originally defined at the top of ``tests/unit/test_coverage_98.py``
and ``tests/unit/test_coverage_99.py``.  Those two omnibus files were
dismantled in favour of fleet-local test files; each fleet test file
imports the helpers it needs from this module.
"""

from __future__ import annotations

from pathlib import Path

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase, Severity

__all__ = [
    "AUDIT",
    "BACKUP",
    "DOMAIN",
    "_Progress",
    "_Sink",
    "_codes",
    "_ctx",
    "_make_file_outcome",
    "_make_run_result",
    "_make_trim_report",
]

DOMAIN = Path("/work/d")
BACKUP = Path("/work/d_backup")
AUDIT = DOMAIN / ".chopper"


class _Sink:
    """Collecting :class:`DiagnosticSink` matching the protocol used in tests."""

    def __init__(self) -> None:
        self._emissions: list[Diagnostic] = []

    def emit(self, d: Diagnostic) -> None:
        self._emissions.append(d)

    def snapshot(self) -> tuple[Diagnostic, ...]:
        return tuple(self._emissions)

    def finalize(self) -> DiagnosticSummary:
        e = sum(1 for d in self._emissions if d.severity is Severity.ERROR)
        w = sum(1 for d in self._emissions if d.severity is Severity.WARNING)
        i = sum(1 for d in self._emissions if d.severity is Severity.INFO)
        return DiagnosticSummary(errors=e, warnings=w, infos=i)


class _Progress:
    """No-op :class:`ProgressSink`."""

    def phase_started(self, phase: Phase) -> None: ...

    def phase_done(self, phase: Phase) -> None: ...

    def step(self, message: str) -> None: ...


def _ctx(fs: InMemoryFS | None = None) -> ChopperContext:
    """Build a :class:`ChopperContext` for unit tests with sensible defaults."""

    cfg = RunConfig(
        domain_root=DOMAIN,
        backup_root=BACKUP,
        audit_root=AUDIT,
        strict=False,
        dry_run=False,
    )
    return ChopperContext(config=cfg, fs=fs or InMemoryFS(), diag=_Sink(), progress=_Progress())


def _codes(ctx: ChopperContext) -> list[str]:
    """Extract the diagnostic-code sequence from ``ctx.diag.snapshot()``."""

    return [d.code for d in ctx.diag.snapshot()]


def _make_file_outcome(
    path_str: str,
    treatment,
    *,
    bytes_in: int = 100,
    bytes_out: int = 50,
    kept: tuple[str, ...] = (),
    removed: tuple[str, ...] = (),
):
    """Build a :class:`FileOutcome` with sensible defaults.

    Mirrors the helper that used to live at the top of
    ``tests/unit/test_coverage_99.py``.  Sorts kept/removed proc
    tuples and zeroes ``bytes_out`` + ``procs_removed`` for REMOVE
    treatments so the resulting outcome satisfies
    :class:`TrimReport`'s post-init invariants.
    """
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_trimmer import FileOutcome

    sk = tuple(sorted(kept))
    sr = tuple(sorted(removed))
    if treatment is FileTreatment.REMOVE:
        bytes_out = 0
        sr = ()
    if treatment in (FileTreatment.FULL_COPY, FileTreatment.REMOVE):
        sr = ()
    return FileOutcome(
        path=Path(path_str),
        treatment=treatment,
        bytes_in=bytes_in,
        bytes_out=bytes_out,
        procs_kept=sk,
        procs_removed=sr,
    )


def _make_trim_report(*outcomes):
    """Aggregate outcomes into a :class:`TrimReport` with correct counts."""
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_trimmer import TrimReport

    sorted_outcomes = tuple(sorted(outcomes, key=lambda o: o.path.as_posix()))
    return TrimReport(
        outcomes=sorted_outcomes,
        files_copied=sum(1 for o in sorted_outcomes if o.treatment is FileTreatment.FULL_COPY),
        files_trimmed=sum(1 for o in sorted_outcomes if o.treatment is FileTreatment.PROC_TRIM),
        files_removed=sum(1 for o in sorted_outcomes if o.treatment is FileTreatment.REMOVE),
        procs_kept_total=sum(len(o.procs_kept) for o in sorted_outcomes),
        procs_removed_total=sum(len(o.procs_removed) for o in sorted_outcomes),
    )


def _make_run_result(trim_report=None, generated_artifacts=()):
    """Build a minimal :class:`RunResult` for renderer tests."""
    from chopper.core.diagnostics import DiagnosticSummary
    from chopper.core.models_audit import RunResult

    return RunResult(
        exit_code=0,
        summary=DiagnosticSummary(errors=0, warnings=0, infos=0),
        trim_report=trim_report,
        generated_artifacts=generated_artifacts,
    )
