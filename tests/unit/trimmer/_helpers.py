"""Shared fixtures for trimmer + orchestrator unit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chopper.adapters import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase


class CollectingSink:
    def __init__(self) -> None:
        self.emissions: list[Diagnostic] = []

    def emit(self, d: Diagnostic) -> None:
        self.emissions.append(d)

    def snapshot(self) -> tuple[Diagnostic, ...]:
        return tuple(self.emissions)

    def finalize(self) -> DiagnosticSummary:  # pragma: no cover
        return DiagnosticSummary(errors=0, warnings=0, infos=0)

    def codes(self) -> list[str]:
        return [d.code for d in self.emissions]


class _NullProgress:
    def phase_started(self, phase: Phase) -> None: ...  # pragma: no cover
    def phase_done(self, phase: Phase) -> None: ...  # pragma: no cover
    def step(self, message: str) -> None: ...  # pragma: no cover


DOMAIN = Path("/work/my_domain")
BACKUP = Path("/work/my_domain_backup")


def make_ctx(
    fs: Any | None = None,
    *,
    dry_run: bool = False,
    domain_root: Path = DOMAIN,
    backup_root: Path = BACKUP,
) -> tuple[ChopperContext, CollectingSink]:
    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=domain_root,
        backup_root=backup_root,
        audit_root=domain_root / ".chopper",
        strict=False,
        dry_run=dry_run,
    )
    ctx = ChopperContext(
        config=cfg,
        fs=fs if fs is not None else InMemoryFS(),
        diag=sink,
        progress=_NullProgress(),
    )
    return ctx, sink
