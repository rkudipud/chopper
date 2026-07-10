"""Trimmer and generator model records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from chopper.core.models_common import FileTreatment

__all__ = ["FileOutcome", "GeneratedArtifact", "P4CheckoutResult", "TrimReport"]


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
class P4CheckoutResult:
    """Outcome of the optional pre-P5 ``--p4`` checkout step.

    Constructed only when ``RunConfig.p4_checkout`` is True and the run is
    not a dry-run; :attr:`TrimReport.p4_checkout` is ``None`` otherwise
    (including whenever ``--p4`` was not passed at all).
    """

    attempted: bool
    """True once checkout actually ran (p4 was available and the domain
    was a working p4 client workspace). False when skipped entirely --
    in that case ``skip_reason`` explains why, and none of the other
    fields are meaningful (all left at their defaults)."""

    skip_reason: str | None = None
    """Human-readable reason checkout was skipped (e.g. "the 'p4'
    executable was not found on PATH"). ``None`` when ``attempted`` is
    True."""

    checked_out: tuple[Path, ...] = ()
    """Paths successfully opened for edit (``p4 edit -t text+x``), in the
    order they were opened (lex-sorted, matching the input file set)."""

    failed_path: Path | None = None
    """The path whose ``p4 edit`` call failed, if any. ``None`` on full
    success (or when skipped)."""

    failure_message: str | None = None
    """Captured stderr / exception text for ``failed_path``. ``None``
    unless ``failed_path`` is set."""

    reverted: tuple[Path, ...] = ()
    """Paths that were ``p4 revert``-ed during rollback after a failure.
    Empty unless a failure occurred after at least one successful
    checkout."""

    domain_restored: bool = False
    """True when rollback also restored ``domain/`` from
    ``domain_backup/`` immediately (a later-P5-stage failure after
    checkout had already succeeded). False for the common case where
    checkout itself failed before any rename/rewrite occurred (nothing
    to restore)."""

    @property
    def failed(self) -> bool:
        """True when a checkout attempt failed partway through the batch."""
        return self.failed_path is not None

    def __post_init__(self) -> None:
        if not self.attempted and self.skip_reason is None:
            raise ValueError("P4CheckoutResult: attempted=False requires a non-None skip_reason")
        if self.attempted and self.skip_reason is not None:
            raise ValueError("P4CheckoutResult: attempted=True must not carry a skip_reason")
        if self.failed_path is not None and self.failure_message is None:
            raise ValueError("P4CheckoutResult: failed_path set requires a non-None failure_message")
        if self.domain_restored and not self.reverted:
            raise ValueError("P4CheckoutResult: domain_restored=True requires at least one reverted path")


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
    inputs_preserved: int = 0
    p4_checkout: P4CheckoutResult | None = None

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
