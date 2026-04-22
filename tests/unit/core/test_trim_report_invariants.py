"""Direct invariant tests for :class:`TrimReport` and :class:`FileOutcome`."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.core.models import FileOutcome, FileTreatment, TrimReport


def _outcome(
    path: str,
    treatment: FileTreatment,
    *,
    kept: tuple[str, ...] = (),
    removed: tuple[str, ...] = (),
    bytes_in: int = 0,
    bytes_out: int = 0,
) -> FileOutcome:
    return FileOutcome(
        path=Path(path),
        treatment=treatment,
        bytes_in=bytes_in,
        bytes_out=bytes_out,
        procs_kept=kept,
        procs_removed=removed,
    )


def test_file_outcome_rejects_unsorted_procs() -> None:
    with pytest.raises(ValueError, match="procs_kept must be lex-sorted"):
        _outcome("a.tcl", FileTreatment.PROC_TRIM, kept=("b", "a"))


def test_file_outcome_rejects_remove_with_bytes_out() -> None:
    with pytest.raises(ValueError, match="REMOVE treatment requires bytes_out == 0"):
        _outcome("a.tcl", FileTreatment.REMOVE, bytes_in=10, bytes_out=5)


def test_file_outcome_rejects_full_copy_with_procs_removed() -> None:
    with pytest.raises(ValueError, match="must not list procs_removed"):
        _outcome("a.tcl", FileTreatment.FULL_COPY, removed=("x",))


def test_file_outcome_rejects_negative_bytes() -> None:
    with pytest.raises(ValueError, match="byte counts must be non-negative"):
        _outcome("a.tcl", FileTreatment.FULL_COPY, bytes_in=-1)


def test_trim_report_rejects_unsorted_outcomes() -> None:
    outcomes = (
        _outcome("z.tcl", FileTreatment.FULL_COPY),
        _outcome("a.tcl", FileTreatment.FULL_COPY),
    )
    with pytest.raises(ValueError, match="lex-sorted by POSIX path"):
        TrimReport(
            outcomes=outcomes,
            files_copied=2,
            files_trimmed=0,
            files_removed=0,
            procs_kept_total=0,
            procs_removed_total=0,
        )


def test_trim_report_rejects_derived_count_drift() -> None:
    outcomes = (_outcome("a.tcl", FileTreatment.FULL_COPY),)
    with pytest.raises(ValueError, match="files_copied mismatch"):
        TrimReport(
            outcomes=outcomes,
            files_copied=99,
            files_trimmed=0,
            files_removed=0,
            procs_kept_total=0,
            procs_removed_total=0,
        )


def test_trim_report_rejects_proc_count_drift() -> None:
    outcomes = (_outcome("a.tcl", FileTreatment.PROC_TRIM, kept=("a::x",), removed=("a::y",)),)
    with pytest.raises(ValueError, match="procs_kept_total mismatch"):
        TrimReport(
            outcomes=outcomes,
            files_copied=0,
            files_trimmed=1,
            files_removed=0,
            procs_kept_total=5,
            procs_removed_total=1,
        )


def test_trim_report_accepts_consistent_totals() -> None:
    outcomes = (
        _outcome("a.tcl", FileTreatment.PROC_TRIM, kept=("a::x",), removed=("a::y",), bytes_in=10, bytes_out=5),
        _outcome("b.tcl", FileTreatment.FULL_COPY, kept=("b::z",), bytes_in=3, bytes_out=3),
        _outcome("c.tcl", FileTreatment.REMOVE, bytes_in=7),
    )
    report = TrimReport(
        outcomes=outcomes,
        files_copied=1,
        files_trimmed=1,
        files_removed=1,
        procs_kept_total=2,
        procs_removed_total=1,
    )
    assert report.rebuild_interrupted is False
    assert len(report.outcomes) == 3
