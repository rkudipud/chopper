"""End-to-end tests for the v2 feature vars sourcing file (ARCHITECTURE Sec.3.12, FR-57)."""

from __future__ import annotations

import json
from pathlib import Path

from chopper.adapters import CollectingSink, LocalFS, SilentProgress
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.models_audit import RunResult
from chopper.core.models_common import FileTreatment
from chopper.orchestrator import ChopperRunner


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _domain(tmp_path: Path) -> Path:
    domain = tmp_path / "apr_fc"
    _write(
        domain / "jsons/apr_fc.json",
        json.dumps({"$schema": "base-v2", "domain": "apr_fc", "vars": "vars.tcl", "files": {"include": ["main.tcl"]}}),
    )
    _write(
        domain / "jsons/features/fdr.feature.json",
        json.dumps({"$schema": "feature-v2", "name": "fdr", "vars": "fdr_vars.tcl"}),
    )
    _write(
        domain / "jsons/features/dop.feature.json",
        json.dumps({"$schema": "feature-v2", "name": "dop", "vars": "dop/dop_vars.tcl"}),
    )
    _write(
        domain / "project.json",
        json.dumps(
            {
                "$schema": "project-v2",
                "project": "P",
                "domain": "apr_fc",
                "base": "jsons/apr_fc.json",
                "features": ["jsons/features/fdr.feature.json", "jsons/features/dop.feature.json"],
            }
        ),
    )
    for name in ("main.tcl", "vars.tcl", "fdr_vars.tcl", "tech_fdr_vars.tcl", "dop/dop_vars.tcl", "unused.tcl"):
        _write(domain / name, "set x 1\n")
    return domain


def _run(domain: Path, *, dry_run: bool, strict: bool = False) -> tuple[CollectingSink, RunResult]:
    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=domain,
        backup_root=domain.with_name(domain.name + "_backup"),
        audit_root=domain / ".chopper",
        strict=strict,
        dry_run=dry_run,
        project_path=domain / "project.json",
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=sink, progress=SilentProgress())
    return sink, ChopperRunner().run(ctx, command="trim")


def test_dry_run_plans_file_without_writing(tmp_path: Path) -> None:
    domain = _domain(tmp_path)
    sink, result = _run(domain, dry_run=True)
    assert result.exit_code == 0, [d.code for d in sink.snapshot()]
    decisions = result.manifest.file_decisions
    assert decisions[Path("apr_fc_feature_vars.tcl")] is FileTreatment.GENERATED
    for kept in ("vars.tcl", "fdr_vars.tcl", "tech_fdr_vars.tcl", "dop/dop_vars.tcl"):
        assert decisions[Path(kept)] is FileTreatment.FULL_COPY
    assert not (domain / "apr_fc_feature_vars.tcl").exists()


def test_live_trim_writes_file_and_keeps_vars(tmp_path: Path) -> None:
    domain = _domain(tmp_path)
    sink, result = _run(domain, dry_run=False)
    assert result.exit_code == 0, [d.code for d in sink.snapshot()]

    text = (domain / "apr_fc_feature_vars.tcl").read_text(encoding="utf-8")
    assert text.endswith(
        "# Feature vars.tcl sourcing file for apr_fc\n\n"
        "iproc_source -file fdr_vars.tcl -optional\n"
        "iproc_source -file tech_fdr_vars.tcl -optional\n"
        "iproc_source -file project_fdr_vars.tcl -optional\n\n"
        "iproc_source -file dop/dop_vars.tcl -optional\n"
        "iproc_source -file dop/tech_dop_vars.tcl -optional\n"
        "iproc_source -file dop/project_dop_vars.tcl -optional\n"
    )
    assert "-file vars.tcl" not in text
    for kept in ("main.tcl", "vars.tcl", "fdr_vars.tcl", "tech_fdr_vars.tcl", "dop/dop_vars.tcl"):
        assert (domain / kept).is_file()
    assert not (domain / "unused.tcl").exists()
