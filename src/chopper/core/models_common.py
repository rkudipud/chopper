"""Common model primitives shared across Chopper phases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

__all__ = ["DomainState", "FileStat", "FileTreatment"]


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
