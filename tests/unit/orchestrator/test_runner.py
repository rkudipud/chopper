"""Unit tests for :class:`chopper.orchestrator.runner.ChopperRunner`."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.adapters import CollectingSink, InMemoryFS, SilentProgress
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, Phase, Severity
from chopper.orchestrator import ChopperRunner, has_errors

DOMAIN = Path("/work/my_domain")
BACKUP = Path("/work/my_domain_backup")


def _ctx(fs: InMemoryFS, *, dry_run: bool = False) -> tuple[ChopperContext, CollectingSink]:
    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=DOMAIN,
        backup_root=BACKUP,
        audit_root=DOMAIN / ".chopper",
        strict=False,
        dry_run=dry_run,
    )
    ctx = ChopperContext(config=cfg, fs=fs, diag=sink, progress=SilentProgress())
    return ctx, sink


def test_runner_case4_exits_with_code_2() -> None:
    """Neither domain nor backup exists → VE-21 → exit 2."""

    fs = InMemoryFS()
    ctx, sink = _ctx(fs)
    result = ChopperRunner().run(ctx)
    assert result.exit_code == 2
    codes = [d.code for d in sink.snapshot()]
    assert "VE-21" in codes
    assert result.state is not None
    assert result.state.case == 4


def test_runner_returns_run_result_with_summary() -> None:
    fs = InMemoryFS()
    ctx, _ = _ctx(fs)
    result = ChopperRunner().run(ctx)
    assert result.summary.errors >= 1
    assert result.exit_code == 2


def test_has_errors_filters_by_phase() -> None:
    fs = InMemoryFS()
    ctx, _ = _ctx(fs)
    d = Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="x", path=Path("a"))
    ctx.diag.emit(d)
    assert has_errors(ctx, Phase.P1_CONFIG) is True
    assert has_errors(ctx, Phase.P2_PARSE) is False


def test_has_errors_ignores_warnings() -> None:
    fs = InMemoryFS()
    ctx, _ = _ctx(fs)
    d = Diagnostic.build("VW-03", phase=Phase.P1_CONFIG, message="warn")
    ctx.diag.emit(d)
    assert has_errors(ctx, Phase.P1_CONFIG) is False
    # Severity accessor sanity.
    assert d.severity is Severity.WARNING


@pytest.mark.parametrize("command", ["validate", "trim"])
def test_runner_accepts_command_label(command: str) -> None:
    fs = InMemoryFS()
    ctx, _ = _ctx(fs)
    result = ChopperRunner().run(ctx, command=command)  # type: ignore[arg-type]
    # Case-4 short-circuit regardless of command label.
    assert result.exit_code == 2
