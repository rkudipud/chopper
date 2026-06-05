"""Unit tests for :mod:`chopper.cli.loc_report` — report math + builder.

End-to-end behaviour (writes nothing, table renders, exit codes) is
covered by :mod:`tests.integration.test_cli_loc`. This module isolates
the percent-reduction math and the per-treatment bucket attribution of
:func:`build_loc_report`, which replays the real trim in memory (see
:mod:`chopper.trimmer.simulate`).
"""

from __future__ import annotations

from pathlib import Path

from chopper.adapters import InMemoryFS
from chopper.cli.loc_report import (
    LocReport,
    TreatmentBucket,
    build_loc_report,
    render_loc_report,
)
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest, FileProvenance
from chopper.core.models_config import BaseJson, LoadedConfig
from chopper.core.models_parser import ParseResult
from chopper.core.models_trimmer import GeneratedArtifact


def _minimal_loaded() -> LoadedConfig:
    """Smallest valid config the in-memory trim replay needs."""
    return LoadedConfig(base=BaseJson(source_path=Path("base.json"), domain="d"))


# ---------------------------------------------------------------------------
# LocReport percent-reduction math
# ---------------------------------------------------------------------------


def _empty_buckets() -> tuple[TreatmentBucket, ...]:
    return (
        TreatmentBucket("FULL_COPY", 0, 0, 0, 0, 0),
        TreatmentBucket("PROC_TRIM", 0, 0, 0, 0, 0),
        TreatmentBucket("REMOVE", 0, 0, 0, 0, 0),
        TreatmentBucket("GENERATED", 0, 0, 0, 0, 0),
    )


class TestLocReportPercents:
    def test_zero_before_returns_zero_percent(self) -> None:
        report = LocReport(0, 0, 0, 0, 0, 0, _empty_buckets())
        assert report.files_pct_reduction == 0.0
        assert report.lines_pct_reduction == 0.0
        assert report.sloc_pct_reduction == 0.0

    def test_50_percent_reduction(self) -> None:
        report = LocReport(
            files_before=10,
            files_after=5,
            lines_before=200,
            lines_after=100,
            sloc_before=150,
            sloc_after=75,
            buckets=_empty_buckets(),
        )
        assert report.files_pct_reduction == 50.0
        assert report.lines_pct_reduction == 50.0
        assert report.sloc_pct_reduction == 50.0

    def test_no_reduction(self) -> None:
        report = LocReport(5, 5, 100, 100, 80, 80, _empty_buckets())
        assert report.files_pct_reduction == 0.0
        assert report.lines_pct_reduction == 0.0
        assert report.sloc_pct_reduction == 0.0


# ---------------------------------------------------------------------------
# render_loc_report — smoke test (renders without crash, contains markers)
# ---------------------------------------------------------------------------


class TestRenderLocReport:
    def test_renders_all_required_markers(self, capsys) -> None:
        report = LocReport(
            files_before=10,
            files_after=4,
            lines_before=500,
            lines_after=120,
            sloc_before=400,
            sloc_after=90,
            buckets=(
                TreatmentBucket("FULL_COPY", 2, 100, 100, 80, 80),
                TreatmentBucket("PROC_TRIM", 2, 300, 100, 250, 80),
                TreatmentBucket("REMOVE", 6, 100, 0, 70, 0),
                TreatmentBucket("GENERATED", 0, 0, 20, 0, 10),
            ),
        )
        render_loc_report(report)
        out = capsys.readouterr().out
        assert "chopper loc:" in out
        assert "files.before: 10" in out
        assert "files.after: 4" in out
        assert "lines.before: 500" in out
        assert "sloc.after: 90" in out
        assert "treatment.FULL_COPY.files: 2" in out
        assert "treatment.PROC_TRIM.files: 2" in out
        assert "treatment.REMOVE.files: 6" in out
        assert "treatment.GENERATED.files: 0" in out
        # 60% reduction on files (10 → 4).
        assert "files.reduction_pct: 60.00%" in out

    def test_render_empty_report_notes_no_files(self, capsys) -> None:
        report = LocReport(0, 0, 0, 0, 0, 0, _empty_buckets())
        render_loc_report(report)
        out = capsys.readouterr().out
        assert "no countable source files" in out


class _Sink:
    def emit(self, _d: Diagnostic) -> None:
        return None

    def snapshot(self) -> tuple[Diagnostic, ...]:
        return ()

    def finalize(self) -> DiagnosticSummary:
        return DiagnosticSummary(errors=0, warnings=0, infos=0)


class _Progress:
    def phase_started(self, _phase: Phase) -> None:
        return None

    def phase_done(self, _phase: Phase) -> None:
        return None

    def step(self, _message: str) -> None:
        return None


def test_build_loc_report_generated_preexisting_contributes_before_sloc() -> None:
    fs = InMemoryFS()
    domain = Path("/tmp/domain")
    backup = Path("/tmp/domain_backup")
    audit = domain / ".chopper"
    fs.write_text(domain / "gen.tcl", "# old\nproc old {} { return 1 }\n", encoding="utf-8")

    ctx = ChopperContext(
        config=RunConfig(domain_root=domain, backup_root=backup, audit_root=audit, strict=False, dry_run=True),
        fs=fs,
        diag=_Sink(),
        progress=_Progress(),
    )

    rel = Path("gen.tcl")
    manifest = CompiledManifest(
        file_decisions={rel: FileTreatment.GENERATED},
        proc_decisions={},
        provenance={
            rel: FileProvenance(
                path=rel,
                treatment=FileTreatment.GENERATED,
                reason="generated-stage",
            )
        },
    )
    parsed = ParseResult(files={}, index={})
    artifacts = (
        GeneratedArtifact(path=rel, kind="tcl", content="# new\nproc new {} { return 2 }\n", source_stage="synth"),
    )

    report = build_loc_report(
        ctx=ctx,
        loaded=_minimal_loaded(),
        parsed=parsed,
        manifest=manifest,
        generated_artifacts=artifacts,
    )

    assert report.files_before == 1
    assert report.sloc_before > 0
    gen_bucket = next(bucket for bucket in report.buckets if bucket.treatment == "GENERATED")
    assert gen_bucket.sloc_before > 0
