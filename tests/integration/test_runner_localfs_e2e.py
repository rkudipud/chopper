"""LocalFS-backed end-to-end runner test.

Complements ``tests/unit/orchestrator/test_runner_e2e.py`` (which uses
:class:`InMemoryFS`) by exercising the real-disk adapter against the
``mini_domain`` fixture. The ``mini_domain`` tree is copied into a
temporary directory so the rebuilt/backup roots can live alongside it
without polluting the committed fixture.

Only dry-run is exercised here — a live trim would shell out to the
real filesystem and is covered by Stage 3 integration suites. The
purpose of this test is to prove the parser's I/O boundary (relative
path → absolute resolution against ``domain_root``) works on real disk,
which unit tests on :class:`InMemoryFS` cannot demonstrate.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from chopper.adapters import CollectingSink, LocalFS, SilentProgress
from chopper.core.context import ChopperContext, RunConfig
from chopper.orchestrator import ChopperRunner

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mini_domain"


def _make_ctx(domain: Path) -> tuple[ChopperContext, CollectingSink]:
    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=domain,
        backup_root=domain.with_name(domain.name + "_backup"),
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
        base_path=domain / "jsons" / "base.json",
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=sink, progress=SilentProgress())
    return ctx, sink


def test_runner_localfs_dry_run_mini_domain(tmp_path: Path) -> None:
    """Full P0→P7 dry-run succeeds on the real-disk ``mini_domain`` fixture."""

    domain = tmp_path / "mini_domain"
    shutil.copytree(FIXTURE, domain)

    ctx, sink = _make_ctx(domain)
    result = ChopperRunner().run(ctx, command="validate")

    codes = [d.code for d in sink.snapshot()]
    assert result.exit_code == 0, f"non-zero exit; diagnostics: {codes}"
    assert result.state is not None
    assert result.state.case == 1
    assert result.loaded is not None
    assert result.parsed is not None
    assert result.manifest is not None
    assert result.graph is not None
    # Dry-run: no trim_report.
    assert result.trim_report is None
    # Audit bundle written to the real domain.
    assert (domain / ".chopper" / "chopper_run.json").exists()
