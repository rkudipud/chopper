"""End-to-end tests for :class:`chopper.trimmer.TrimmerService`.

These tests run the trimmer against the :class:`InMemoryFS` adapter and
assert both the :class:`TrimReport` shape and the resulting filesystem
state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.adapters import InMemoryFS
from chopper.core.models import (
    CompiledManifest,
    DomainState,
    FileProvenance,
    FileTreatment,
    ParsedFile,
    ParseResult,
    ProcDecision,
    ProcEntry,
)
from chopper.trimmer import TrimmerService
from tests.unit.trimmer._helpers import BACKUP, DOMAIN, make_ctx

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _proc(file: str, name: str, *, start: int, end: int) -> ProcEntry:
    path = Path(file)
    return ProcEntry(
        canonical_name=f"{path.as_posix()}::{name}",
        short_name=name,
        qualified_name=name,
        source_file=path,
        start_line=start,
        end_line=end,
        body_start_line=start + 1 if start + 1 <= end else start,
        body_end_line=end - 1 if end - 1 >= start else end,
        namespace_path="",
        calls=(),
        source_refs=(),
    )


def _parsed(files: dict[str, list[ProcEntry]]) -> ParseResult:
    out_files: dict[Path, ParsedFile] = {}
    index: dict[str, ProcEntry] = {}
    for file_str, procs in sorted(files.items()):
        path = Path(file_str)
        sorted_procs = tuple(sorted(procs, key=lambda p: p.start_line))
        out_files[path] = ParsedFile(path=path, procs=sorted_procs, encoding="utf-8")
        for p in sorted_procs:
            index[p.canonical_name] = p
    sorted_index = {k: index[k] for k in sorted(index)}
    return ParseResult(files=out_files, index=sorted_index)


def _manifest(
    file_decisions: dict[str, FileTreatment],
    proc_survivors: dict[str, str],
) -> CompiledManifest:
    """Build a CompiledManifest.

    ``proc_survivors`` maps canonical_name -> reason tag (e.g. "fi-literal").
    """
    fd: dict[Path, FileTreatment] = {}
    pv: dict[Path, FileProvenance] = {}
    for file_str, treatment in sorted(file_decisions.items()):
        path = Path(file_str)
        fd[path] = treatment
        reason = {
            FileTreatment.FULL_COPY: "fi-literal",
            FileTreatment.PROC_TRIM: "pi-additive",
            FileTreatment.REMOVE: "default-exclude",
            FileTreatment.GENERATED: "fi-literal",
        }[treatment]
        pv[path] = FileProvenance(
            path=path,
            treatment=treatment,
            reason=reason,
            input_sources=("base:files.include",) if treatment is not FileTreatment.REMOVE else (),
            proc_model=("additive" if treatment is FileTreatment.PROC_TRIM else None),
        )
    pd: dict[str, ProcDecision] = {}
    for cn, field in sorted(proc_survivors.items()):
        file_part = cn.split("::")[0]
        pd[cn] = ProcDecision(
            canonical_name=cn,
            source_file=Path(file_part),
            selection_source=f"base:{field}",
        )
    return CompiledManifest(file_decisions=fd, proc_decisions=pd, provenance=pv)


def _state(case: int, *, domain_exists: bool, backup_exists: bool) -> DomainState:
    return DomainState(
        case=case,  # type: ignore[arg-type]
        domain_exists=domain_exists,
        backup_exists=backup_exists,
        hand_edited=False,
    )


# ---------------------------------------------------------------------------
# Case-1 tests — first trim
# ---------------------------------------------------------------------------


def test_case_1_full_copy_rebuilds_domain() -> None:
    fs = InMemoryFS(
        {
            DOMAIN / "a.tcl": "proc foo {} {}\n",
            DOMAIN / "b.tcl": "proc bar {} {}\n",
        }
    )
    ctx, sink = make_ctx(fs=fs)

    manifest = _manifest(
        {"a.tcl": FileTreatment.FULL_COPY, "b.tcl": FileTreatment.FULL_COPY},
        {"a.tcl::foo": "files.include", "b.tcl::bar": "files.include"},
    )
    parsed = _parsed(
        {
            "a.tcl": [_proc("a.tcl", "foo", start=1, end=1)],
            "b.tcl": [_proc("b.tcl", "bar", start=1, end=1)],
        }
    )
    state = _state(1, domain_exists=True, backup_exists=False)

    report = TrimmerService().run(ctx, manifest, parsed, state)

    # Backup exists and still has the originals.
    assert fs.read_text(BACKUP / "a.tcl") == "proc foo {} {}\n"
    assert fs.read_text(BACKUP / "b.tcl") == "proc bar {} {}\n"
    # Rebuilt domain has verbatim copies.
    assert fs.read_text(DOMAIN / "a.tcl") == "proc foo {} {}\n"
    assert fs.read_text(DOMAIN / "b.tcl") == "proc bar {} {}\n"
    # Report shape.
    assert report.files_copied == 2
    assert report.files_trimmed == 0
    assert report.files_removed == 0
    assert report.procs_kept_total == 2
    assert report.procs_removed_total == 0
    assert report.rebuild_interrupted is False
    assert [o.path.as_posix() for o in report.outcomes] == ["a.tcl", "b.tcl"]
    assert sink.codes() == []


def test_case_1_preexisting_dot_chopper_is_not_backed_up() -> None:
    fs = InMemoryFS(
        {
            DOMAIN / "a.tcl": "x",
            DOMAIN / ".chopper" / "prev_run.json": "{}",
        }
    )
    ctx, _ = make_ctx(fs=fs)

    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY}, {"a.tcl::x": "files.include"})
    parsed = _parsed({"a.tcl": [_proc("a.tcl", "x", start=1, end=1)]})
    state = _state(1, domain_exists=True, backup_exists=False)

    TrimmerService().run(ctx, manifest, parsed, state)

    # Backup does not contain .chopper/ (it was removed before rename).
    assert not fs.exists(BACKUP / ".chopper")
    assert fs.read_text(BACKUP / "a.tcl") == "x"


# ---------------------------------------------------------------------------
# Case-2 tests — re-trim
# ---------------------------------------------------------------------------


def test_case_2_discards_domain_rebuilds_from_backup() -> None:
    fs = InMemoryFS(
        {
            DOMAIN / "stale.tcl": "STALE",
            BACKUP / "a.tcl": "proc foo {} {}\n",
        }
    )
    ctx, _ = make_ctx(fs=fs)

    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY}, {"a.tcl::foo": "files.include"})
    parsed = _parsed({"a.tcl": [_proc("a.tcl", "foo", start=1, end=1)]})
    state = _state(2, domain_exists=True, backup_exists=True)

    TrimmerService().run(ctx, manifest, parsed, state)

    # Stale file is gone; rebuilt domain has only backup contents.
    assert not fs.exists(DOMAIN / "stale.tcl")
    assert fs.read_text(DOMAIN / "a.tcl") == "proc foo {} {}\n"
    assert fs.read_text(BACKUP / "a.tcl") == "proc foo {} {}\n"


# ---------------------------------------------------------------------------
# Case-3 tests — recovery re-trim
# ---------------------------------------------------------------------------


def test_case_3_rebuilds_from_backup() -> None:
    fs = InMemoryFS({BACKUP / "a.tcl": "proc foo {} {}\n"})
    ctx, _ = make_ctx(fs=fs)

    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY}, {"a.tcl::foo": "files.include"})
    parsed = _parsed({"a.tcl": [_proc("a.tcl", "foo", start=1, end=1)]})
    state = _state(3, domain_exists=False, backup_exists=True)

    TrimmerService().run(ctx, manifest, parsed, state)

    assert fs.read_text(DOMAIN / "a.tcl") == "proc foo {} {}\n"
    assert fs.read_text(BACKUP / "a.tcl") == "proc foo {} {}\n"


# ---------------------------------------------------------------------------
# Case-4 is a bug to call run()
# ---------------------------------------------------------------------------


def test_case_4_raises_valueerror() -> None:
    fs = InMemoryFS()
    ctx, _ = make_ctx(fs=fs)
    manifest = _manifest({}, {})
    parsed = _parsed({})
    state = _state(4, domain_exists=False, backup_exists=False)
    with pytest.raises(ValueError):
        TrimmerService().run(ctx, manifest, parsed, state)


# ---------------------------------------------------------------------------
# PROC_TRIM execution
# ---------------------------------------------------------------------------


def test_proc_trim_drops_non_surviving_procs() -> None:
    content = "proc a {} {}\nproc b {} {}\nproc c {} {}\n"
    fs = InMemoryFS({DOMAIN / "m.tcl": content})
    ctx, _ = make_ctx(fs=fs)

    manifest = _manifest(
        {"m.tcl": FileTreatment.PROC_TRIM},
        {"m.tcl::a": "procedures.include", "m.tcl::c": "procedures.include"},
    )
    parsed = _parsed(
        {
            "m.tcl": [
                _proc("m.tcl", "a", start=1, end=1),
                _proc("m.tcl", "b", start=2, end=2),
                _proc("m.tcl", "c", start=3, end=3),
            ],
        }
    )
    state = _state(1, domain_exists=True, backup_exists=False)

    report = TrimmerService().run(ctx, manifest, parsed, state)

    assert fs.read_text(DOMAIN / "m.tcl") == "proc a {} {}\nproc c {} {}\n"
    assert report.files_trimmed == 1
    assert report.procs_kept_total == 2
    assert report.procs_removed_total == 1
    outcome = report.outcomes[0]
    assert outcome.procs_kept == ("m.tcl::a", "m.tcl::c")
    assert outcome.procs_removed == ("m.tcl::b",)


def test_proc_trim_out_of_range_emits_ve26_and_halts() -> None:
    fs = InMemoryFS({DOMAIN / "m.tcl": "one\ntwo\n"})
    ctx, sink = make_ctx(fs=fs)

    manifest = _manifest({"m.tcl": FileTreatment.PROC_TRIM}, {})
    # Declare a proc at lines 5-7 but the backup only has 2 lines.
    parsed = _parsed({"m.tcl": [_proc("m.tcl", "fake", start=5, end=7)]})
    state = _state(1, domain_exists=True, backup_exists=False)

    report = TrimmerService().run(ctx, manifest, parsed, state)

    assert sink.codes() == ["VE-26"]
    assert report.rebuild_interrupted is True


def test_proc_trim_missing_in_parsed_emits_ve24() -> None:
    fs = InMemoryFS({DOMAIN / "m.tcl": "body\n"})
    ctx, sink = make_ctx(fs=fs)
    manifest = _manifest({"m.tcl": FileTreatment.PROC_TRIM}, {})
    parsed = _parsed({})  # m.tcl absent — no ParsedFile
    state = _state(1, domain_exists=True, backup_exists=False)

    report = TrimmerService().run(ctx, manifest, parsed, state)

    assert sink.codes() == ["VE-24"]
    assert report.rebuild_interrupted is True


# ---------------------------------------------------------------------------
# REMOVE treatment
# ---------------------------------------------------------------------------


def test_remove_does_not_write_file_but_records_outcome() -> None:
    fs = InMemoryFS({DOMAIN / "extra.tcl": "hello\n"})
    ctx, _ = make_ctx(fs=fs)

    manifest = _manifest({"extra.tcl": FileTreatment.REMOVE}, {})
    parsed = _parsed({})
    state = _state(1, domain_exists=True, backup_exists=False)

    report = TrimmerService().run(ctx, manifest, parsed, state)

    assert not fs.exists(DOMAIN / "extra.tcl")
    assert fs.read_text(BACKUP / "extra.tcl") == "hello\n"
    assert report.files_removed == 1
    assert report.outcomes[0].bytes_in == len(b"hello\n")
    assert report.outcomes[0].bytes_out == 0


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


def test_dry_run_performs_no_writes_but_produces_report() -> None:
    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n"})
    ctx, _ = make_ctx(fs=fs, dry_run=True)

    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY}, {"a.tcl::foo": "files.include"})
    parsed = _parsed({"a.tcl": [_proc("a.tcl", "foo", start=1, end=1)]})
    state = _state(1, domain_exists=True, backup_exists=False)

    report = TrimmerService().run(ctx, manifest, parsed, state)

    # No backup was created, no rebuild happened.
    assert not fs.exists(BACKUP)
    assert fs.read_text(DOMAIN / "a.tcl") == "proc foo {} {}\n"  # unchanged
    # Report still faithfully describes the planned outcome.
    assert report.files_copied == 1
    assert report.procs_kept_total == 1


# ---------------------------------------------------------------------------
# GENERATED — owned by GeneratorService (P5b); trimmer skips
# ---------------------------------------------------------------------------


def test_generated_treatment_is_skipped_by_trimmer() -> None:
    """GENERATED files are owned by :class:`GeneratorService`; the trimmer
    must not attempt to copy or trim them, and they must not appear in
    :attr:`TrimReport.outcomes`."""

    fs = InMemoryFS({DOMAIN / "x": ""})
    ctx, _ = make_ctx(fs=fs)
    manifest = _manifest({"stages/s1.tcl": FileTreatment.GENERATED}, {})
    parsed = _parsed({})
    state = _state(1, domain_exists=True, backup_exists=False)
    report = TrimmerService().run(ctx, manifest, parsed, state)
    assert report.outcomes == ()
    assert report.files_copied == 0
    assert report.files_trimmed == 0
    assert report.files_removed == 0


def test_generated_treatment_skipped_in_dry_run() -> None:
    fs = InMemoryFS()
    ctx, _ = make_ctx(fs=fs, dry_run=True)
    manifest = _manifest({"stages/s1.tcl": FileTreatment.GENERATED}, {})
    parsed = _parsed({})
    state = _state(1, domain_exists=True, backup_exists=False)
    report = TrimmerService().run(ctx, manifest, parsed, state)
    assert report.outcomes == ()


# ---------------------------------------------------------------------------
# Report invariants
# ---------------------------------------------------------------------------


def test_report_outcomes_are_lex_sorted_by_path() -> None:
    fs = InMemoryFS(
        {
            DOMAIN / "zzz.tcl": "proc z {} {}\n",
            DOMAIN / "aaa.tcl": "proc a {} {}\n",
            DOMAIN / "mmm.tcl": "proc m {} {}\n",
        }
    )
    ctx, _ = make_ctx(fs=fs)
    manifest = _manifest(
        {
            "zzz.tcl": FileTreatment.FULL_COPY,
            "aaa.tcl": FileTreatment.FULL_COPY,
            "mmm.tcl": FileTreatment.FULL_COPY,
        },
        {
            "aaa.tcl::a": "files.include",
            "mmm.tcl::m": "files.include",
            "zzz.tcl::z": "files.include",
        },
    )
    parsed = _parsed(
        {
            "aaa.tcl": [_proc("aaa.tcl", "a", start=1, end=1)],
            "mmm.tcl": [_proc("mmm.tcl", "m", start=1, end=1)],
            "zzz.tcl": [_proc("zzz.tcl", "z", start=1, end=1)],
        }
    )
    state = _state(1, domain_exists=True, backup_exists=False)
    report = TrimmerService().run(ctx, manifest, parsed, state)
    paths = [o.path.as_posix() for o in report.outcomes]
    assert paths == ["aaa.tcl", "mmm.tcl", "zzz.tcl"]
