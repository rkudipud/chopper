"""Trimmer and generator model records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from chopper.core.models_common import FileTreatment

__all__ = ["FileOutcome", "GeneratedArtifact", "TrimReport"]


@dataclass(frozen=True)
class FileOutcome:
    """Per-file audit record produced by :class:`TrimmerService` (P5a)."""

    path: Path
    treatment: FileTreatment
    bytes_in: int
    bytes_out: int
    procs_kept: tuple[str, ...]
    procs_removed: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.bytes_in < 0 or self.bytes_out < 0:
            raise ValueError(
                "FileOutcome byte counts must be non-negative, "
                f"got bytes_in={self.bytes_in}, bytes_out={self.bytes_out}"
            )
        if list(self.procs_kept) != sorted(self.procs_kept):
            raise ValueError("FileOutcome.procs_kept must be lex-sorted")
        if list(self.procs_removed) != sorted(self.procs_removed):
            raise ValueError("FileOutcome.procs_removed must be lex-sorted")
        if self.treatment is FileTreatment.REMOVE and self.bytes_out != 0:
            raise ValueError("FileOutcome: REMOVE treatment requires bytes_out == 0")
        if self.treatment in (FileTreatment.FULL_COPY, FileTreatment.REMOVE) and self.procs_removed:
            raise ValueError(f"FileOutcome: treatment {self.treatment} must not list procs_removed")


@dataclass(frozen=True)
class TrimReport:
    """Frozen output of :class:`~chopper.trimmer.TrimmerService` (P5a)."""

    outcomes: tuple[FileOutcome, ...]
    files_copied: int
    files_trimmed: int
    files_removed: int
    procs_kept_total: int
    procs_removed_total: int
    rebuild_interrupted: bool = False

    def __post_init__(self) -> None:
        paths = [o.path.as_posix() for o in self.outcomes]
        if paths != sorted(paths):
            raise ValueError("TrimReport.outcomes must be lex-sorted by POSIX path")

        expected_copied = sum(1 for o in self.outcomes if o.treatment is FileTreatment.FULL_COPY)
        expected_trimmed = sum(1 for o in self.outcomes if o.treatment is FileTreatment.PROC_TRIM)
        expected_removed = sum(1 for o in self.outcomes if o.treatment is FileTreatment.REMOVE)
        expected_kept = sum(len(o.procs_kept) for o in self.outcomes)
        expected_removed_procs = sum(len(o.procs_removed) for o in self.outcomes)

        if self.files_copied != expected_copied:
            raise ValueError(f"TrimReport.files_copied mismatch: got {self.files_copied}, derived {expected_copied}")
        if self.files_trimmed != expected_trimmed:
            raise ValueError(f"TrimReport.files_trimmed mismatch: got {self.files_trimmed}, derived {expected_trimmed}")
        if self.files_removed != expected_removed:
            raise ValueError(f"TrimReport.files_removed mismatch: got {self.files_removed}, derived {expected_removed}")
        if self.procs_kept_total != expected_kept:
            raise ValueError(
                f"TrimReport.procs_kept_total mismatch: got {self.procs_kept_total}, derived {expected_kept}"
            )
        if self.procs_removed_total != expected_removed_procs:
            raise ValueError(
                f"TrimReport.procs_removed_total mismatch: got {self.procs_removed_total}, "
                f"derived {expected_removed_procs}"
            )


@dataclass(frozen=True)
class GeneratedArtifact:
    """One file emitted by :class:`~chopper.generators.GeneratorService` (P5b)."""

    path: Path
    kind: Literal["stack", "tcl", "csv"]
    content: str
    source_stage: str

    def __post_init__(self) -> None:
        if not self.source_stage:
            raise ValueError("GeneratedArtifact.source_stage must be non-empty")
