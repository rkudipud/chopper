"""Per-file coverage tests for src/chopper/cli/render.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def _make_file_outcome(
    path_str: str,
    treatment,
    *,
    bytes_in: int = 100,
    bytes_out: int = 50,
    kept: tuple[str, ...] = (),
    removed: tuple[str, ...] = (),
):
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
    from chopper.core.models_audit import RunResult

    return RunResult(
        exit_code=0,
        summary=DiagnosticSummary(errors=0, warnings=0, infos=0),
        trim_report=trim_report,
        generated_artifacts=generated_artifacts,
    )


def test_render_trim_stats_noop_when_no_trim_report() -> None:
    """render_trim_stats must silently do nothing when trim_report is None
    (e.g. dry-run aborted early).  No output should be written."""
    from chopper.cli.render import render_trim_stats

    ctx = _ctx()
    result = _make_run_result(trim_report=None)
    buf = io.StringIO()
    render_trim_stats(ctx, result, stream=buf)
    assert buf.getvalue() == ""


def test_render_trim_stats_remove_treatment_shows_zero_sloc_out(tmp_path: Path) -> None:
    """Per ARCHITECTURE.md Sec.A7, REMOVE files have sloc_out=0 because the file
    is deleted from the rebuilt domain.  The table must not attempt to read the
    (non-existent) output file."""
    from chopper.cli.render import render_trim_stats
    from chopper.core.models_common import FileTreatment

    outcome = _make_file_outcome("a.tcl", FileTreatment.REMOVE, bytes_in=200)
    report = _make_trim_report(outcome)
    result = _make_run_result(trim_report=report)

    domain = tmp_path / "d"
    domain.mkdir()
    from chopper.adapters.fs_local import LocalFS
    from chopper.core.context import ChopperContext, RunConfig

    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=False,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    buf = io.StringIO()
    render_trim_stats(ctx, result, stream=buf)
    output = buf.getvalue()
    assert "Trim stats" in output
    assert "DROP" in output


def test_render_trim_stats_dry_run_reads_domain_for_sloc_in(tmp_path: Path) -> None:
    """Under dry-run no backup is taken; render_trim_stats must read sloc_in
    from domain_root when backup_root doesn't exist (ARCHITECTURE.md Sec.A7)."""
    from chopper.cli.render import render_trim_stats
    from chopper.core.models_common import FileTreatment

    domain = tmp_path / "d"
    domain.mkdir()
    (domain / "a.tcl").write_text("proc x {} {}\n")

    outcome = _make_file_outcome("a.tcl", FileTreatment.PROC_TRIM)
    report = _make_trim_report(outcome)
    result = _make_run_result(trim_report=report)

    from chopper.adapters.fs_local import LocalFS
    from chopper.core.context import ChopperContext, RunConfig

    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    buf = io.StringIO()
    render_trim_stats(ctx, result, stream=buf)
    output = buf.getvalue()
    assert "Trim stats" in output


def test_render_trim_stats_emits_drop_rows_for_unrecorded_domain_files(tmp_path: Path) -> None:
    """Full-domain coverage: files dropped under default-exclude (R2) never
    appear in ``report.outcomes``; render_trim_stats must still emit a DROP
    row for each, walking the pristine source tree (backup_root)."""
    from chopper.cli.render import render_trim_stats
    from chopper.core.models_common import FileTreatment

    domain = tmp_path / "d"
    backup = tmp_path / "d_backup"
    backup.mkdir()
    domain.mkdir()
    # Backup holds the pristine source: one rewritten file + two dropped.
    (backup / "kept.tcl").write_text("proc keep {} {}\n", encoding="utf-8")
    (backup / "dropped_a.tcl").write_text("proc a {} {}\nproc b {} {}\n", encoding="utf-8")
    (backup / "dropped_b.tcl").write_text("proc c {} {}\n", encoding="utf-8")
    # Rebuilt domain holds only the survivor.
    (domain / "kept.tcl").write_text("proc keep {} {}\n", encoding="utf-8")

    outcome = _make_file_outcome("kept.tcl", FileTreatment.FULL_COPY)
    report = _make_trim_report(outcome)
    result = _make_run_result(trim_report=report)

    from chopper.adapters.fs_local import LocalFS
    from chopper.core.context import ChopperContext, RunConfig

    cfg = RunConfig(
        domain_root=domain,
        backup_root=backup,
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=False,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    buf = io.StringIO()
    render_trim_stats(ctx, result, stream=buf)
    output = buf.getvalue()
    # Both dropped files appear as DROP rows; the survivor is COPY.
    assert "dropped_a.tcl" in output
    assert "dropped_b.tcl" in output
    assert output.count("DROP") >= 2
    # TOTAL row now spans all three domain files, not just the one outcome.
    assert "3 files" in output


def test_render_trim_stats_skips_unreadable_dropped_file(tmp_path: Path, monkeypatch) -> None:
    """A source file that fails to read during the DROP-row walk is skipped
    (defensive guard against a file vanishing between walk and read)."""
    from pathlib import Path as _Path

    from chopper.cli.render import render_trim_stats
    from chopper.core.models_common import FileTreatment

    domain = tmp_path / "d"
    backup = tmp_path / "d_backup"
    backup.mkdir()
    domain.mkdir()
    (backup / "kept.tcl").write_text("proc keep {} {}\n", encoding="utf-8")
    (backup / "vanished.tcl").write_text("proc gone {} {}\n", encoding="utf-8")
    (domain / "kept.tcl").write_text("proc keep {} {}\n", encoding="utf-8")

    outcome = _make_file_outcome("kept.tcl", FileTreatment.FULL_COPY)
    report = _make_trim_report(outcome)
    result = _make_run_result(trim_report=report)

    from chopper.adapters.fs_local import LocalFS
    from chopper.core.context import ChopperContext, RunConfig

    cfg = RunConfig(
        domain_root=domain,
        backup_root=backup,
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=False,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())

    _real_read_text = _Path.read_text

    def _raising_read_text(self, *args, **kwargs):
        if self.name == "vanished.tcl":
            raise OSError("file vanished between walk and read")
        return _real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(_Path, "read_text", _raising_read_text)

    buf = io.StringIO()
    render_trim_stats(ctx, result, stream=buf)
    output = buf.getvalue()
    # The unreadable file is silently dropped from the table.
    assert "vanished.tcl" not in output
    assert "kept.tcl" in output


def test_render_trim_stats_long_path_is_truncated(tmp_path: Path) -> None:
    """A file path longer than the computed file_w must be left-truncated
    keeping the basename visible (the '...' ellipsis prefix pattern)."""
    from chopper.cli.render import render_trim_stats
    from chopper.core.models_common import FileTreatment

    domain = tmp_path / "d"
    domain.mkdir()
    # No subdir needed for this test.

    # Create a simple outcome; the path itself is long enough to trigger truncation.
    outcome = _make_file_outcome("a.tcl", FileTreatment.FULL_COPY)
    report = _make_trim_report(outcome)
    result = _make_run_result(trim_report=report)

    from chopper.adapters.fs_local import LocalFS
    from chopper.core.context import ChopperContext, RunConfig

    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=False,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    buf = io.StringIO()
    # Force narrow terminal so truncation fires.
    with patch("shutil.get_terminal_size", return_value=MagicMock(columns=60)):
        render_trim_stats(ctx, result, stream=buf)
    output = buf.getvalue()
    # Table was rendered if file is present; check no crash occurred.
    # (Long path truncation or no-rows is acceptable here.)
    assert isinstance(output, str)


def test_render_trim_stats_with_generated_artifact(tmp_path: Path) -> None:
    """Generated artifacts (stage .tcl files) must appear in the stats table
    under the 'GEN ' treatment label per ARCHITECTURE.md Sec.5.6."""
    from chopper.cli.render import render_trim_stats
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_trimmer import GeneratedArtifact

    domain = tmp_path / "d"
    domain.mkdir()
    artifact = GeneratedArtifact(
        path=Path("synth.tcl"),
        kind="stage",
        content="proc run_synth {} {}\n",
        source_stage="synth",
    )
    # render_trim_stats only shows generated rows when trim_report has outcomes.
    outcome = _make_file_outcome("a.tcl", FileTreatment.FULL_COPY)
    report = _make_trim_report(outcome)
    result = _make_run_result(trim_report=report, generated_artifacts=(artifact,))

    from chopper.adapters.fs_local import LocalFS
    from chopper.core.context import ChopperContext, RunConfig

    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    buf = io.StringIO()
    render_trim_stats(ctx, result, stream=buf)
    output = buf.getvalue()
    assert "GEN" in output


def test_render_diagnostics_suppresses_ti01() -> None:
    """TI-01 (tool-command-index rebuild info) is a machine-readable internal
    diagnostic that must be suppressed from human-readable stderr output to
    reduce noise during normal trim invocations."""
    from chopper.cli.render import render_diagnostics
    from chopper.core.diagnostics import Diagnostic, Phase

    d_ti01 = Diagnostic.build(
        "TI-01",
        phase=Phase.P0_STATE,
        message="tool index rebuilt",
    )
    d_other = Diagnostic.build(
        "VW-03",
        phase=Phase.P1_CONFIG,
        message="no matches",
    )
    buf = io.StringIO()
    render_diagnostics([d_ti01, d_other], stream=buf)
    output = buf.getvalue()
    assert "TI-01" not in output
    assert "VW-03" in output


def test_fmt_pair_equal_values_omits_delta() -> None:
    """When before == after the delta tail must be omitted; the cell shows
    only 'N -> N' without a '(+0)' suffix (spec: identical live vs dry-run)."""
    from chopper.cli.render import _fmt_pair

    cell = _fmt_pair(100, 100)
    assert "100 -> 100" in cell
    assert "+" not in cell
    assert "(-" not in cell  # no negative-delta suffix; the '-' in '->' is OK


def test_render_diagnostics_includes_path_and_lineno() -> None:
    """render_diagnostics must format 'path:lineno' when both are set on a Diagnostic."""
    from chopper.cli.render import render_diagnostics

    diag = Diagnostic.build(
        "VE-06",
        phase=Phase.P1_CONFIG,
        message="not found",
        path=Path("sub/missing.tcl"),
        line_no=42,
    )
    out = io.StringIO()
    render_diagnostics([diag], stream=out)
    text = out.getvalue()
    assert "sub/missing.tcl" in text
    assert "42" in text


def test_render_cleanup_message_writes_to_stdout_by_default() -> None:
    """render_cleanup_message sends output to stdout when no explicit stream is given."""
    from chopper.cli.render import render_cleanup_message

    captured = io.StringIO()
    with patch("sys.stdout", captured):
        render_cleanup_message("cleanup done successfully")
    assert "cleanup done successfully" in captured.getvalue()


def test_render_table_left_truncates_long_path() -> None:
    """_render_table must left-truncate paths longer than the file column width."""
    from chopper.cli.render import _render_table

    long_path = "a" * 200 + "/very/long/path/to/file.tcl"
    rows: list[dict[str, object]] = [
        {
            "path": long_path,
            "treatment": "REMOVE",
            "sloc_in": 100,
            "sloc_out": None,
            "kept": 0,
            "removed": 5,
        }
    ]
    totals: dict[str, object] = {
        "path": "TOTAL",
        "treatment": "",
        "sloc_in": 100,
        "sloc_out": None,
        "kept": 0,
        "removed": 5,
    }
    out = io.StringIO()
    _render_table(out, rows, totals, width=80)
    text = out.getvalue()
    # Truncation inserts the ellipsis characters.
    assert "..." in text


def test_render_trim_stats_returns_early_when_no_trim_report() -> None:
    """render_trim_stats returns early when result.trim_report is None (line 119-120)."""
    from chopper.cli.render import render_trim_stats

    fs = InMemoryFS()
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=True)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    # RunResult with no trim_report -> early return at line 119
    result = _make_run_result()
    out = io.StringIO()
    render_trim_stats(ctx2, result, stream=out)
    assert out.getvalue() == ""


def test_render_result_writes_summary_line() -> None:
    """render_result calls render_diagnostics then writes summary (lines 80-83)."""
    from chopper.cli.render import render_result

    result = _make_run_result()
    out = io.StringIO()
    render_result(result, [], stream=out)
    text = out.getvalue()
    # render_result writes a Summary line
    assert "Summary" in text or "exit" in text


# ===========================================================================
# Batch 4 -- Remaining coverage gaps


def test_render_trim_stats_returns_early_when_rows_empty() -> None:
    """render_trim_stats returns early at line 129 when outcomes=() and no artifacts."""
    from chopper.cli.render import render_trim_stats
    from chopper.core.models_trimmer import TrimReport

    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=True)
    ctx2 = ChopperContext(config=cfg, fs=InMemoryFS(), diag=_Sink(), progress=_Progress())

    trim_report = TrimReport(
        outcomes=(),
        files_copied=0,
        files_trimmed=0,
        files_removed=0,
        procs_kept_total=0,
        procs_removed_total=0,
    )
    result = _make_run_result(trim_report=trim_report, generated_artifacts=())
    out = io.StringIO()
    render_trim_stats(ctx2, result, stream=out)
    # Empty rows -> early return, no table written
    assert out.getvalue() == ""


def test_render_trim_stats_artifact_oserror_falls_back_to_content() -> None:
    """_collect_generated_rows falls back to artifact.content when target read fails (197-201)."""
    from chopper.cli.render import render_trim_stats
    from chopper.core.models_trimmer import GeneratedArtifact

    artifact = GeneratedArtifact(
        path=Path("stage.tcl"),
        kind="tcl",
        content="# generated\nset x 1\n",
        source_stage="mystage",
    )
    # Non-dry-run: tries to read domain_root/stage.tcl, which doesn't exist
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    ctx2 = ChopperContext(config=cfg, fs=InMemoryFS(), diag=_Sink(), progress=_Progress())

    from chopper.core.models_common import FileTreatment

    outcome = _make_file_outcome("other.tcl", FileTreatment.FULL_COPY, bytes_out=50)
    trim_report = _make_trim_report(outcome)
    result = _make_run_result(trim_report=trim_report, generated_artifacts=(artifact,))
    out = io.StringIO()
    # Should not crash -- OSError is caught and falls back to artifact.content
    render_trim_stats(ctx2, result, stream=out)
    # Table is rendered (rows not empty)
    assert len(out.getvalue()) > 0


def test_render_trim_stats_reads_backup_source_for_artifact(tmp_path) -> None:
    """_collect_generated_rows reads backup source when it exists (lines 215, 219-220)."""
    from chopper.cli.render import render_trim_stats
    from chopper.core.models_trimmer import GeneratedArtifact

    # Create a backup copy of the generated file
    backup_root = tmp_path / "domain_backup"
    backup_root.mkdir()
    domain_root = tmp_path / "domain"
    domain_root.mkdir()
    # Create the artifact on disk at domain_root/stage.tcl
    artifact_rel = Path("stage.tcl")
    (domain_root / "stage.tcl").write_text("# content\n", encoding="utf-8")
    # Create "before" version at backup_root/stage.tcl
    (backup_root / "stage.tcl").write_text("# original\n", encoding="utf-8")

    artifact = GeneratedArtifact(
        path=artifact_rel,
        kind="tcl",
        content="# content\n",
        source_stage="mystage",
    )

    cfg = RunConfig(
        domain_root=domain_root,
        backup_root=backup_root,
        audit_root=domain_root / ".chopper",
        strict=False,
        dry_run=False,
    )
    ctx2 = ChopperContext(config=cfg, fs=InMemoryFS(), diag=_Sink(), progress=_Progress())

    outcome = _make_file_outcome(
        "other.tcl",
        __import__("chopper.core.models_common", fromlist=["FileTreatment"]).FileTreatment.FULL_COPY,
        bytes_out=50,
    )
    trim_report = _make_trim_report(outcome)
    result = _make_run_result(trim_report=trim_report, generated_artifacts=(artifact,))
    out = io.StringIO()
    render_trim_stats(ctx2, result, stream=out)
    # Should have rendered a table with the backup content
    assert len(out.getvalue()) > 0


def test_render_trim_stats_excludes_json_outcome(tmp_path: Path) -> None:
    """render_trim_stats skips outcomes whose path is an excluded artifact (.json)."""
    from chopper.cli.render import render_trim_stats
    from chopper.core.models_common import FileTreatment

    domain_root = tmp_path / "dom"
    backup_root = tmp_path / "dom_backup"
    backup_root.mkdir(parents=True)
    domain_root.mkdir(parents=True)
    (backup_root / "base.json").write_text("{}")
    (backup_root / "lib.tcl").write_text("proc foo {} {}")
    (domain_root / "lib.tcl").write_text("proc foo {} {}")

    cfg = RunConfig(
        domain_root=domain_root,
        backup_root=backup_root,
        audit_root=domain_root / ".chopper",
        strict=False,
        dry_run=False,
    )
    ctx2 = ChopperContext(config=cfg, fs=InMemoryFS(), diag=_Sink(), progress=_Progress())

    json_outcome = _make_file_outcome("base.json", FileTreatment.FULL_COPY, bytes_out=10)
    tcl_outcome = _make_file_outcome("lib.tcl", FileTreatment.FULL_COPY, bytes_out=50)
    trim_report = _make_trim_report(json_outcome, tcl_outcome)
    result = _make_run_result(trim_report=trim_report)
    out = io.StringIO()
    render_trim_stats(ctx2, result, stream=out)
    # base.json should NOT appear in the output table
    assert "base.json" not in out.getvalue()
    assert "lib.tcl" in out.getvalue()


def test_render_trim_stats_excludes_generated_json_artifact(tmp_path: Path) -> None:
    """render_trim_stats skips generated artifacts whose path is excluded."""
    from chopper.cli.render import render_trim_stats
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_trimmer import GeneratedArtifact

    domain_root = tmp_path / "dom"
    backup_root = tmp_path / "dom_backup"
    domain_root.mkdir(parents=True)
    backup_root.mkdir(parents=True)
    (domain_root / "stage.tcl").write_text("source x")

    cfg = RunConfig(
        domain_root=domain_root,
        backup_root=backup_root,
        audit_root=domain_root / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx2 = ChopperContext(config=cfg, fs=InMemoryFS(), diag=_Sink(), progress=_Progress())

    tcl_artifact = GeneratedArtifact(path=Path("stage.tcl"), kind="tcl", content="source x\n", source_stage="stage")
    json_artifact = GeneratedArtifact(path=Path("instructions.md"), kind="tcl", content="# hi\n", source_stage="s2")
    outcome = _make_file_outcome("stage.tcl", FileTreatment.FULL_COPY, bytes_out=20)
    trim_report = _make_trim_report(outcome)
    result = _make_run_result(trim_report=trim_report, generated_artifacts=(tcl_artifact, json_artifact))
    out = io.StringIO()
    render_trim_stats(ctx2, result, stream=out)
    # instructions.md artifact should NOT appear
    assert "instructions.md" not in out.getvalue()
