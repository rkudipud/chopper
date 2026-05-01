"""Audit and run-result model records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from chopper.core.diagnostics import DiagnosticSummary
from chopper.core.models_common import DomainState
from chopper.core.models_compiler import CompiledManifest, DependencyGraph
from chopper.core.models_config import LoadedConfig
from chopper.core.models_parser import ParseResult
from chopper.core.models_trimmer import GeneratedArtifact, TrimReport

__all__ = ["AuditArtifact", "AuditManifest", "InternalError", "RunRecord", "RunResult"]


@dataclass(frozen=True)
class InternalError:
    """Programmer-error summary attached to :class:`RunResult` on exit code 3."""

    kind: str
    message: str
    log_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("InternalError.kind must be non-empty")


@dataclass(frozen=True)
class AuditArtifact:
    """One file written under ``.chopper/`` by :class:`AuditService`."""

    name: str
    path: Path
    size: int
    sha256: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("AuditArtifact.name must be non-empty")
        if self.size < 0:
            raise ValueError(f"AuditArtifact.size must be non-negative, got {self.size}")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError(f"AuditArtifact.sha256 must be a 64-char hex string, got {self.sha256!r}")


@dataclass(frozen=True)
class AuditManifest:
    """Inventory of every file :class:`AuditService` wrote under ``.chopper/``."""

    run_id: str
    started_at: datetime
    ended_at: datetime
    exit_code: int
    artifacts: tuple[AuditArtifact, ...]
    diagnostic_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("AuditManifest.run_id must be non-empty")
        if self.exit_code not in (0, 1, 2, 3, 4):
            raise ValueError(f"AuditManifest.exit_code must be 0/1/2/3/4, got {self.exit_code}")
        if self.ended_at < self.started_at:
            raise ValueError("AuditManifest.ended_at must be >= started_at")
        names = [a.name for a in self.artifacts]
        if names != sorted(names):
            raise ValueError("AuditManifest.artifacts must be lex-sorted by name")
        if len(set(names)) != len(names):
            raise ValueError("AuditManifest.artifacts must have unique names")


@dataclass(frozen=True)
class RunRecord:
    """Runtime snapshot handed to :class:`AuditService` at P7."""

    run_id: str
    command: Literal["validate", "trim", "cleanup"]
    started_at: datetime
    ended_at: datetime
    exit_code: int
    state: DomainState | None = None
    loaded: LoadedConfig | None = None
    parsed: ParseResult | None = None
    manifest: CompiledManifest | None = None
    graph: DependencyGraph | None = None
    trim_report: TrimReport | None = None
    generated_artifacts: tuple[GeneratedArtifact, ...] = ()
    internal_error: InternalError | None = None

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("RunRecord.run_id must be non-empty")
        if self.exit_code not in (0, 1, 2, 3, 4):
            raise ValueError(f"RunRecord.exit_code must be 0/1/2/3/4, got {self.exit_code}")
        if self.ended_at < self.started_at:
            raise ValueError("RunRecord.ended_at must be >= started_at")


@dataclass(frozen=True)
class RunResult:
    """Typed result returned by :meth:`ChopperRunner.run`."""

    exit_code: int
    summary: DiagnosticSummary
    state: DomainState | None = None
    loaded: LoadedConfig | None = None
    parsed: ParseResult | None = None
    manifest: CompiledManifest | None = None
    graph: DependencyGraph | None = None
    trim_report: TrimReport | None = None
    generated_artifacts: tuple[GeneratedArtifact, ...] = ()
    internal_error: InternalError | None = None

    def __post_init__(self) -> None:
        if self.exit_code not in (0, 1, 2, 3, 4):
            raise ValueError(f"RunResult.exit_code must be 0/1/2/3/4, got {self.exit_code}")
