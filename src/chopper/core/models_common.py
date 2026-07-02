"""Common model primitives shared across Chopper phases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

__all__ = ["DomainRunResult", "DomainState", "FileStat", "FileTreatment"]


class FileTreatment(StrEnum):
    """Per-file disposition emitted by the compiler."""

    FULL_COPY = "FULL_COPY"
    PROC_TRIM = "PROC_TRIM"
    GENERATED = "GENERATED"
    REMOVE = "REMOVE"


@dataclass(frozen=True)
class DomainState:
    """Result of the Phase 0 domain-state classification."""

    case: Literal[1, 2, 3, 4]
    domain_exists: bool
    backup_exists: bool
    hand_edited: bool


@dataclass(frozen=True)
class FileStat:
    """Lightweight stat record returned by :meth:`FileSystemPort.stat`."""

    size: int
    mtime: float
    is_dir: bool


@dataclass(frozen=True)
class DomainRunResult:
    """Per-domain result from a multi-domain sequential trim run.

    Produced by ``cmd_trim``, ``cmd_validate``, and ``cmd_loc`` when
    ``--domain`` receives a CSV list of domain names. The multi-domain
    loop collects one instance per domain and passes them to
    :func:`~chopper.cli.render.render_p4_branch_analysis`.
    """

    domain_logical_name: str
    """Label for this domain -- the ``vendor/name`` string or basename of the
    domain root when name-mode was not used."""

    exit_code: int
    """The exit code produced by this domain's run."""

    branch_needed: bool
    """True if any ``PROC_TRIM`` or ``GENERATED`` treatment was applied,
    meaning a Perforce branch is required to record the changes."""

    edits_count: int
    """Number of ``PROC_TRIM`` + in-place-``GENERATED`` file treatments."""

    adds_count: int
    """Number of new (not-previously-existing) ``GENERATED`` file treatments."""

    removes_count: int
    """Number of files that will be removed (``REMOVE`` treatments or
    physical-walk entries not in the kept set)."""
