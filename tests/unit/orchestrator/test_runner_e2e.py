"""End-to-end orchestrator test using :class:`InMemoryFS`.

This exercises P0 → P7 in dry-run mode against a synthetic domain
built entirely in memory. It validates the runner's phase sequencing
and gate policy without depending on real filesystem behaviour.

The LocalFS adapter has a known limitation: parser :mod:`service` stores
domain-relative paths internally and reads via ``ctx.fs`` with those
relative keys, which :class:`LocalFS` cannot resolve without cwd being
the domain root. That path (and a full LocalFS E2E) is revisited when
the parser is retrofitted to use absolute reads; here we pin the
orchestrator contract using :class:`InMemoryFS`, the in-tree FS adapter
that keys directly on relative paths.
"""

from __future__ import annotations

import json
from pathlib import Path

from chopper.adapters import CollectingSink, InMemoryFS, SilentProgress
from chopper.core.context import ChopperContext, RunConfig
from chopper.orchestrator import ChopperRunner

DOMAIN = Path("mini_domain")
BACKUP = Path("mini_domain_backup")
BASE_JSON = DOMAIN / "jsons" / "base.json"


def _seed_domain(fs: InMemoryFS) -> None:
    fs.mkdir(DOMAIN, parents=True, exist_ok=True)
    fs.write_text(DOMAIN / "vars.tcl", "# vars\nset PI 3.14\n")
    fs.write_text(DOMAIN / "helper_procs.tcl", "proc helper_a {} { return 1 }\n")
    fs.write_text(
        BASE_JSON,
        json.dumps(
            {
                "$schema": "chopper/base/v1",
                "domain": "mini_domain",
                "files": {"include": ["vars.tcl", "helper_procs.tcl"]},
            }
        ),
    )


def _make_ctx(fs: InMemoryFS) -> tuple[ChopperContext, CollectingSink]:
    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=DOMAIN,
        backup_root=BACKUP,
        audit_root=DOMAIN / ".chopper",
        strict=False,
        dry_run=True,
        base_path=BASE_JSON,
    )
    ctx = ChopperContext(config=cfg, fs=fs, diag=sink, progress=SilentProgress())
    return ctx, sink


def test_runner_full_dry_run_happy_path() -> None:
    fs = InMemoryFS()
    _seed_domain(fs)
    ctx, sink = _make_ctx(fs)
    result = ChopperRunner().run(ctx, command="validate")

    codes = [d.code for d in sink.snapshot()]
    assert result.exit_code == 0, f"non-zero exit; diagnostics: {codes}"
    # All phases reached manifest + graph construction.
    assert result.state is not None
    assert result.state.case == 1
    assert result.loaded is not None
    assert result.parsed is not None
    assert result.manifest is not None
    assert result.graph is not None
    # Dry-run: trim was NOT executed; trim_report must stay None.
    assert result.trim_report is None
    # Summary exposes the final counts.
    assert result.summary.errors == 0


def test_runner_writes_audit_bundle_in_dry_run() -> None:
    fs = InMemoryFS()
    _seed_domain(fs)
    ctx, _ = _make_ctx(fs)
    ChopperRunner().run(ctx, command="validate")
    # Audit service always runs — chopper_run.json is written.
    assert fs.exists(DOMAIN / ".chopper" / "chopper_run.json")
