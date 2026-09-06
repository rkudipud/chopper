"""Cross-platform unit tests for :mod:`chopper.trimmer.file_writer`."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.adapters import InMemoryFS
from chopper.core.models_common import FileTreatment
from chopper.core.models_parser import ParsedFile, ProcEntry
from chopper.trimmer.file_writer import full_copy_file, proc_trim_file, remove_file
from tests.unit.trimmer._helpers import BACKUP, DOMAIN, make_ctx


def _proc(file: str, name: str, *, start: int, end: int) -> ProcEntry:
    path = Path(file)
    return ProcEntry(
        canonical_name=f"{path.as_posix()}::{name}",
        short_name=name,
        qualified_name=name,
        source_file=path,
        start_line=start,
        end_line=end,
        body_start_line=start,
        body_end_line=end,
        namespace_path="",
    )


def test_remove_file_records_zero_bytes_when_backup_is_missing() -> None:
    ctx, _ = make_ctx(fs=InMemoryFS())

    outcome = remove_file(ctx, Path("missing.tcl"))

    assert outcome.path == Path("missing.tcl")
    assert outcome.treatment is FileTreatment.REMOVE
    assert outcome.bytes_in == 0
    assert outcome.bytes_out == 0


def test_full_copy_file_dry_run_reports_without_writing() -> None:
    rel = Path("copied.tcl")
    fs = InMemoryFS({BACKUP / rel: "proc copied {} {}\n"})
    ctx, _ = make_ctx(fs=fs, dry_run=True)

    outcome = full_copy_file(ctx, rel, procs_in_file=("copied.tcl::copied",))

    assert not fs.exists(DOMAIN / rel)
    assert outcome.bytes_in == len(b"proc copied {} {}\n")
    assert outcome.procs_kept == ("copied.tcl::copied",)


def test_proc_trim_file_sorts_kept_and_removed_proc_names() -> None:
    rel = Path("trimmed.tcl")
    text = "proc z_keep {} {}\nproc a_drop {} {}\nproc b_keep {} {}\n"
    fs = InMemoryFS({BACKUP / rel: text})
    ctx, _ = make_ctx(fs=fs)
    z_keep = _proc("trimmed.tcl", "z_keep", start=1, end=1)
    a_drop = _proc("trimmed.tcl", "a_drop", start=2, end=2)
    b_keep = _proc("trimmed.tcl", "b_keep", start=3, end=3)
    parsed = ParsedFile(path=rel, procs=(z_keep, a_drop, b_keep), encoding="utf-8")

    outcome = proc_trim_file(
        ctx,
        rel,
        parsed=parsed,
        keep_canonical=frozenset({z_keep.canonical_name, b_keep.canonical_name}),
        source_of=lambda cn: "base",
    )

    assert "proc a_drop {} {}" not in fs.read_text(DOMAIN / rel)
    assert outcome.procs_kept == ("trimmed.tcl::b_keep", "trimmed.tcl::z_keep")
    assert outcome.procs_removed == ("trimmed.tcl::a_drop",)


def test_proc_trim_file_dry_run_reports_without_writing() -> None:
    rel = Path("trimmed.tcl")
    text = "proc keep {} {}\nproc drop {} {}\n"
    fs = InMemoryFS({BACKUP / rel: text})
    ctx, _ = make_ctx(fs=fs, dry_run=True)
    keep = _proc("trimmed.tcl", "keep", start=1, end=1)
    drop = _proc("trimmed.tcl", "drop", start=2, end=2)
    parsed = ParsedFile(path=rel, procs=(keep, drop), encoding="utf-8")

    outcome = proc_trim_file(
        ctx, rel, parsed=parsed, keep_canonical=frozenset({keep.canonical_name}), source_of=lambda cn: "base"
    )

    assert not fs.exists(DOMAIN / rel)
    assert outcome.treatment is FileTreatment.PROC_TRIM
    assert outcome.procs_kept == ("trimmed.tcl::keep",)
    assert outcome.procs_removed == ("trimmed.tcl::drop",)


def test_mirror_perms_plus_exec_swallows_chmod_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from chopper.core import file_perms

    src = tmp_path / "src.tcl"
    dst = tmp_path / "dst.tcl"
    src.write_text("src\n", encoding="utf-8")
    dst.write_text("dst\n", encoding="utf-8")

    def _raise_copymode(source: Path, target: Path) -> None:
        raise OSError("chmod rejected")

    monkeypatch.setattr(file_perms.shutil, "copymode", _raise_copymode)

    file_perms.mirror_perms_plus_exec(src, dst)
