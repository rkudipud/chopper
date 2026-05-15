"""Per-file coverage tests for src/chopper/cli/loc_report.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_loc_report_source_root_uses_backup_when_it_exists(tmp_path: Path) -> None:
    """_source_root must return backup_root when it exists, so 'before'
    reflects what the parser actually saw (case 2/3 re-run)."""
    from chopper.adapters.fs_local import LocalFS
    from chopper.cli.loc_report import _source_root
    from chopper.core.context import ChopperContext, RunConfig

    domain = tmp_path / "d"
    domain.mkdir()
    backup = tmp_path / "d_backup"
    backup.mkdir()

    cfg = RunConfig(
        domain_root=domain,
        backup_root=backup,
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    assert _source_root(ctx) == backup


def test_loc_report_read_with_latin1_fallback(tmp_path: Path) -> None:
    """_read must fall back to latin-1 when UTF-8 decoding fails.
    EDA scripts often contain non-ASCII vendor comments in ISO-8859-1."""
    from chopper.adapters.fs_local import LocalFS
    from chopper.cli.loc_report import _read
    from chopper.core.context import ChopperContext, RunConfig

    domain = tmp_path / "d"
    domain.mkdir()
    bad_utf8 = b"proc x {} {}\n# caf\xe9 comment\n"
    (domain / "f.tcl").write_bytes(bad_utf8)

    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    text = _read(ctx, Path("f.tcl"))
    assert text is not None
    assert "proc x" in text


def test_loc_report_read_returns_none_on_oserror(tmp_path: Path) -> None:
    """_read returns None (not raises) when the file doesn't exist,
    so build_loc_report can skip missing files gracefully."""
    from chopper.adapters.fs_local import LocalFS
    from chopper.cli.loc_report import _read
    from chopper.core.context import ChopperContext, RunConfig

    domain = tmp_path / "d"
    domain.mkdir()
    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    result = _read(ctx, Path("nonexistent.tcl"))
    assert result is None


def test_build_loc_report_baseline_only_returns_full_copy_bucket(
    tmp_path: Path,
) -> None:
    """build_loc_report_baseline_only must return a report with all source
    files in the FULL_COPY bucket (before==after for all metrics) because
    the manifest was unavailable and no trim was computed."""
    from chopper.adapters.fs_local import LocalFS
    from chopper.cli.loc_report import build_loc_report_baseline_only
    from chopper.core.context import ChopperContext, RunConfig

    domain = tmp_path / "d"
    domain.mkdir()
    (domain / "a.tcl").write_text("proc x {} {}\nproc y {} {}\n")
    (domain / "b.tcl").write_text("proc z {} {}\n")

    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    report = build_loc_report_baseline_only(ctx)

    # All files in FULL_COPY bucket; no trim occurred.
    fc = next(b for b in report.buckets if b.treatment == "FULL_COPY")
    assert fc.files >= 2
    assert fc.sloc_before == fc.sloc_after
    assert fc.lines_before == fc.lines_after


def test_render_loc_report_outputs_one_line_per_metric(tmp_path: Path) -> None:
    """render_loc_report must print one ``key: value`` line per metric to
    stdout (ARCHITECTURE.md §5.7).  Spot-check key names."""
    from chopper.adapters.fs_local import LocalFS
    from chopper.cli.loc_report import build_loc_report_baseline_only, render_loc_report
    from chopper.core.context import ChopperContext, RunConfig

    domain = tmp_path / "d"
    domain.mkdir()
    (domain / "x.tcl").write_text("proc a {} {}\n")

    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    report = build_loc_report_baseline_only(ctx)

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        render_loc_report(report)
    output = buf.getvalue()
    # render_loc_report uses 'files.before' dot-notation keys.
    assert "files.before" in output
    assert "sloc.before" in output
    assert "sloc.after" in output


def test_loc_report_read_with_latin1_fallback_in_proc_body(tmp_path: Path) -> None:
    """_read falls back to latin-1 encoding when UTF-8 decode fails (non-ASCII in proc body)."""
    from chopper.adapters.fs_local import LocalFS
    from chopper.cli.loc_report import _read

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    # Write a file with a latin-1 byte that is not valid UTF-8.
    latin_file = src_dir / "latin.tcl"
    latin_file.write_bytes(b"proc foo {} { return \xe9 }\n")

    ctx_cfg = RunConfig(
        domain_root=src_dir,
        backup_root=tmp_path / "src_backup",
        audit_root=src_dir / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=ctx_cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    text = _read(ctx, Path("latin.tcl"))
    assert text is not None
    assert "foo" in text


def test_loc_report_read_unicode_error_then_oserror_returns_none() -> None:
    """_read returns None when UnicodeDecodeError on first read and OSError on latin-1 fallback (142-143)."""
    from chopper.cli.loc_report import _read  # type: ignore[attr-defined]

    fs = InMemoryFS()
    abs_path = DOMAIN / "x.tcl"
    fs.write_text(abs_path, "proc foo {} {}\n")

    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=True)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    call_count = [0]

    def _mock_read_text(self, path, encoding="utf-8", errors="strict"):  # type: ignore[misc]
        call_count[0] += 1
        if call_count[0] == 1:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid byte")
        raise OSError("second read also fails")

    with patch.object(type(fs), "read_text", _mock_read_text):
        result = _read(ctx2, Path("x.tcl"))

    assert result is None


def test_build_loc_report_baseline_only_empty_domain() -> None:
    """build_loc_report_baseline_only returns LocReport with 0 counts for empty domain."""
    from chopper.cli.loc_report import build_loc_report_baseline_only

    fs = InMemoryFS()
    fs.mkdir(DOMAIN, parents=True, exist_ok=True)

    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=True)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    report = build_loc_report_baseline_only(ctx2)
    assert report.files_before == 0
    assert report.sloc_before == 0


def test_render_loc_report_writes_note_when_no_lines(capsys: pytest.CaptureFixture) -> None:
    """render_loc_report writes 'note: no countable source files' when lines_before==0 (line 363)."""
    from chopper.cli.loc_report import LocReport, TreatmentBucket, render_loc_report

    report = LocReport(
        files_before=0,
        files_after=0,
        lines_before=0,
        lines_after=0,
        sloc_before=0,
        sloc_after=0,
        buckets=(
            TreatmentBucket("FULL_COPY", 0, 0, 0, 0, 0),
            TreatmentBucket("PROC_TRIM", 0, 0, 0, 0, 0),
            TreatmentBucket("REMOVE", 0, 0, 0, 0, 0),
            TreatmentBucket("GENERATED", 0, 0, 0, 0, 0),
        ),
    )
    render_loc_report(report)
    captured = capsys.readouterr()
    assert "note: no countable source files" in captured.out


# ===========================================================================
# build_loc_report end-to-end (covers lines 212-285: FULL_COPY, PROC_TRIM,
# REMOVE, GENERATED bucket attribution + SLOC batch path).
# ===========================================================================


def test_build_loc_report_covers_all_treatment_buckets(tmp_path: Path) -> None:
    """build_loc_report exercises every treatment-bucket branch when the
    manifest names FULL_COPY + PROC_TRIM + REMOVE + GENERATED files."""
    from typing import cast as _cast

    from chopper.adapters.fs_local import LocalFS
    from chopper.cli.loc_report import build_loc_report
    from chopper.core.context import ChopperContext, RunConfig
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_compiler import CompiledManifest, FileProvenance, ProcDecision
    from chopper.core.models_config import LoadedConfig
    from chopper.core.models_parser import ParsedFile, ParseResult, ProcEntry
    from chopper.core.models_trimmer import GeneratedArtifact

    domain = tmp_path / "d"
    domain.mkdir()
    (domain / "keep.tcl").write_text("# header\nproc keep {} { return 1 }\n", encoding="utf-8")
    (domain / "trim.tcl").write_text(
        "proc stay {} {\n    return 1\n}\nproc drop {} {\n    return 2\n}\n",
        encoding="utf-8",
    )
    (domain / "gone.tcl").write_text("proc x {} {}\n", encoding="utf-8")
    (domain / "gen.tcl").write_text("# old gen\nproc oldgen {} {}\n", encoding="utf-8")

    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())

    keep_rel = Path("keep.tcl")
    trim_rel = Path("trim.tcl")
    gone_rel = Path("gone.tcl")
    gen_rel = Path("gen.tcl")

    stay_proc = ProcEntry(
        canonical_name=f"{trim_rel.as_posix()}::stay",
        short_name="stay",
        qualified_name="stay",
        source_file=trim_rel,
        start_line=1,
        end_line=3,
        body_start_line=1,
        body_end_line=3,
        namespace_path="::",
    )
    drop_proc = ProcEntry(
        canonical_name=f"{trim_rel.as_posix()}::drop",
        short_name="drop",
        qualified_name="drop",
        source_file=trim_rel,
        start_line=4,
        end_line=6,
        body_start_line=4,
        body_end_line=6,
        namespace_path="::",
    )
    parsed = ParseResult(
        files={trim_rel: ParsedFile(path=trim_rel, procs=(stay_proc, drop_proc), encoding="utf-8")},
        index=dict(
            sorted(
                {
                    stay_proc.canonical_name: stay_proc,
                    drop_proc.canonical_name: drop_proc,
                }.items()
            )
        ),
    )
    manifest = CompiledManifest(
        file_decisions={
            gen_rel: FileTreatment.GENERATED,
            gone_rel: FileTreatment.REMOVE,
            keep_rel: FileTreatment.FULL_COPY,
            trim_rel: FileTreatment.PROC_TRIM,
        },
        proc_decisions={
            stay_proc.canonical_name: ProcDecision(
                canonical_name=stay_proc.canonical_name,
                source_file=trim_rel,
                selection_source="base:procedures.include",
            ),
        },
        provenance={
            gen_rel: FileProvenance(path=gen_rel, treatment=FileTreatment.GENERATED, reason="generated"),
            gone_rel: FileProvenance(path=gone_rel, treatment=FileTreatment.REMOVE, reason="excluded"),
            keep_rel: FileProvenance(path=keep_rel, treatment=FileTreatment.FULL_COPY, reason="included"),
            trim_rel: FileProvenance(path=trim_rel, treatment=FileTreatment.PROC_TRIM, reason="proc-trim"),
        },
    )
    artifacts = (
        GeneratedArtifact(
            path=gen_rel,
            kind="tcl",
            content="# new gen\nproc newgen {} { return 99 }\n",
            source_stage="synth",
        ),
    )

    report = build_loc_report(
        ctx=ctx,
        loaded=_cast(LoadedConfig, None),
        parsed=parsed,
        manifest=manifest,
        generated_artifacts=artifacts,
    )

    bucket_by_name = {b.treatment: b for b in report.buckets}
    assert bucket_by_name["FULL_COPY"].files == 1
    assert bucket_by_name["PROC_TRIM"].files == 1
    assert bucket_by_name["REMOVE"].files == 1
    assert bucket_by_name["GENERATED"].files == 1
    assert bucket_by_name["PROC_TRIM"].lines_after < bucket_by_name["PROC_TRIM"].lines_before
    assert bucket_by_name["GENERATED"].sloc_before > 0


def test_build_loc_report_skips_unreadable_files_and_external_generated(tmp_path: Path) -> None:
    """Covers: _read returning None for sloc_files batch (212, 254), GENERATED
    artifact for a path not in source (regenerate-in-place absent → 284), and
    a non-.tcl generated artifact (270->273 false branch)."""
    from typing import cast as _cast

    from chopper.adapters.fs_local import LocalFS
    from chopper.cli import loc_report as lr
    from chopper.core.context import ChopperContext, RunConfig
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_compiler import CompiledManifest, FileProvenance
    from chopper.core.models_config import LoadedConfig
    from chopper.core.models_parser import ParseResult
    from chopper.core.models_trimmer import GeneratedArtifact

    domain = tmp_path / "d"
    domain.mkdir()
    (domain / "unreadable.tcl").write_text("proc x {} {}\n", encoding="utf-8")
    (domain / "trim.tcl").write_text("proc y {} {}\n", encoding="utf-8")

    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())

    unreadable = Path("unreadable.tcl")
    trim_rel = Path("trim.tcl")
    external_gen = Path("not_in_source.txt")  # non-.tcl, not on disk

    manifest = CompiledManifest(
        file_decisions={
            trim_rel: FileTreatment.PROC_TRIM,
            unreadable: FileTreatment.REMOVE,
        },
        proc_decisions={},
        provenance={
            trim_rel: FileProvenance(path=trim_rel, treatment=FileTreatment.PROC_TRIM, reason="proc-trim"),
            unreadable: FileProvenance(path=unreadable, treatment=FileTreatment.REMOVE, reason="excluded"),
        },
    )
    artifacts = (
        GeneratedArtifact(
            path=external_gen,
            kind="other",
            content="not tcl",
            source_stage="synth",
        ),
    )

    # Force _read → None everywhere; that exercises both the sloc_files skip
    # (lines 212-220, 363) and the PROC_TRIM text=None branch (line 254) and
    # the GENERATED regenerate-in-place fallback _read None (line 284-285).
    with patch.object(lr, "_read", return_value=None):
        report = lr.build_loc_report(
            ctx=ctx,
            loaded=_cast(LoadedConfig, None),
            parsed=ParseResult(files={}, index={}),
            manifest=manifest,
            generated_artifacts=artifacts,
        )

    bucket_by_name = {b.treatment: b for b in report.buckets}
    # PROC_TRIM had text=None → lines_after == 0
    assert bucket_by_name["PROC_TRIM"].lines_after == 0
    # GENERATED bucket exists; regenerate-in-place could not read source
    assert bucket_by_name["GENERATED"].files == 1


def test_build_loc_report_baseline_only_skips_unreadable_file(tmp_path: Path) -> None:
    """Covers line 363: build_loc_report_baseline_only continues past _read=None."""
    from chopper.adapters.fs_local import LocalFS
    from chopper.cli import loc_report as lr
    from chopper.core.context import ChopperContext, RunConfig

    domain = tmp_path / "d"
    domain.mkdir()
    (domain / "f.tcl").write_text("proc x {} {}\n", encoding="utf-8")
    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())

    with patch.object(lr, "_read", return_value=None):
        report = lr.build_loc_report_baseline_only(ctx)

    assert report.sloc_before == 0


# ===========================================================================
# BATCH-6: Fix remaining coverage gaps
