"""Unit tests for :mod:`chopper.cli.loc_report` — pure-function math.

End-to-end behaviour (writes nothing, table renders, exit codes) is
covered by :mod:`tests.integration.test_cli_loc`. This module isolates
the percent-reduction math, the proc-drop span calculator, and the
PROC_TRIM after-line accounting.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from chopper.adapters import InMemoryFS
from chopper.cli.loc_report import (
    LocReport,
    TreatmentBucket,
    _proc_drop_span,
    _proc_trim_after,
    build_loc_report,
    render_loc_report,
)
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest, FileProvenance
from chopper.core.models_config import LoadedConfig
from chopper.core.models_parser import ParseResult, ProcEntry
from chopper.core.models_trimmer import GeneratedArtifact


def _proc(
    *,
    qualified_name: str = "p1",
    start_line: int = 5,
    end_line: int = 10,
    body_start_line: int | None = None,
    body_end_line: int | None = None,
    dpa_start_line: int | None = None,
    dpa_end_line: int | None = None,
    comment_start_line: int | None = None,
    comment_end_line: int | None = None,
    source_file: Path = Path("a.tcl"),
) -> ProcEntry:
    return ProcEntry(
        canonical_name=f"{source_file.as_posix()}::{qualified_name}",
        short_name=qualified_name.split("::")[-1],
        qualified_name=qualified_name,
        source_file=source_file,
        start_line=start_line,
        end_line=end_line,
        body_start_line=body_start_line if body_start_line is not None else start_line,
        body_end_line=body_end_line if body_end_line is not None else end_line,
        namespace_path="::",
        dpa_start_line=dpa_start_line,
        dpa_end_line=dpa_end_line,
        comment_start_line=comment_start_line,
        comment_end_line=comment_end_line,
    )


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
# _proc_drop_span
# ---------------------------------------------------------------------------


class TestProcDropSpan:
    def test_basic_proc_no_dpa_no_comment(self) -> None:
        proc = _proc(start_line=10, end_line=20)
        assert _proc_drop_span(proc) == (10, 20)

    def test_with_dpa_extends_first(self) -> None:
        proc = _proc(start_line=10, end_line=20, dpa_start_line=8, dpa_end_line=9)
        assert _proc_drop_span(proc) == (8, 20)

    def test_with_comment_extends_first(self) -> None:
        proc = _proc(start_line=10, end_line=20, comment_start_line=7, comment_end_line=9)
        assert _proc_drop_span(proc) == (7, 20)

    def test_with_both_dpa_and_comment_takes_min(self) -> None:
        proc = _proc(
            start_line=10,
            end_line=20,
            dpa_start_line=8,
            dpa_end_line=9,
            comment_start_line=5,
            comment_end_line=7,
        )
        assert _proc_drop_span(proc) == (5, 20)


# ---------------------------------------------------------------------------
# _proc_trim_after — line masking
# ---------------------------------------------------------------------------


class TestProcTrimAfter:
    def test_no_dropped_procs_returns_full_count(self) -> None:
        text = "line1\nline2\nline3\n"
        lines, _sloc = _proc_trim_after(text, [], Path("a.tcl"))
        assert lines == 3

    def test_drops_proc_lines(self) -> None:
        # Lines: 1=keep, 2-4=proc body (drop), 5=keep
        text = "set a 1\nproc foo {} {\n  return 1\n}\nset b 2\n"
        proc = _proc(start_line=2, end_line=4, body_start_line=2, body_end_line=4)
        lines, _sloc = _proc_trim_after(text, [proc], Path("a.tcl"))
        assert lines == 2

    def test_drops_multiple_procs_with_overlapping_ranges_handled(self) -> None:
        # 6 lines, drop lines 2-3 and 5
        text = "L1\nL2\nL3\nL4\nL5\nL6\n"
        p1 = _proc(qualified_name="p1", start_line=2, end_line=3, body_start_line=2, body_end_line=3)
        p2 = _proc(qualified_name="p2", start_line=5, end_line=5, body_start_line=5, body_end_line=5)
        lines, _sloc = _proc_trim_after(text, [p1, p2], Path("a.tcl"))
        assert lines == 3  # L1, L4, L6


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
        loaded=cast(LoadedConfig, None),
        parsed=parsed,
        manifest=manifest,
        generated_artifacts=artifacts,
    )

    assert report.files_before == 1
    assert report.sloc_before > 0
    gen_bucket = next(bucket for bucket in report.buckets if bucket.treatment == "GENERATED")
    assert gen_bucket.sloc_before > 0
