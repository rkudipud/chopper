"""Feature procs sourcing follows the v2 vars contract (ARCHITECTURE Sec.3.12)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chopper.core.models_common import FileTreatment

from .test_feature_vars import _domain, _run, _write


def _procs_domain(tmp_path: Path) -> Path:
    domain = _domain(tmp_path)
    for relative, pointer in (
        ("jsons/apr_fc.json", "procs.tcl"),
        ("jsons/features/fdr.feature.json", "fdr_procs.tcl"),
        ("jsons/features/dop.feature.json", "dop/dop_procs.tcl"),
    ):
        path = domain / relative
        data = json.loads(path.read_text(encoding="utf-8"))
        data["procs"] = pointer
        _write(path, json.dumps(data))
    for name in ("procs.tcl", "fdr_procs.tcl", "tech_fdr_procs.tcl", "dop/dop_procs.tcl"):
        _write(domain / name, "proc kept {} { return 1 }\n")
    return domain


@pytest.mark.parametrize("dry_run", [True, False])
def test_procs_generation_and_f1_preservation(tmp_path: Path, dry_run: bool) -> None:
    domain = _procs_domain(tmp_path)
    project = (domain / "project.json").read_text(encoding="utf-8")
    sink, result = _run(domain, dry_run=dry_run)
    assert result.exit_code == 0, [(d.code, d.message) for d in sink.snapshot()]
    path = Path("apr_fc_feature_procs.tcl")
    assert result.manifest.file_decisions[path] is FileTreatment.GENERATED
    assert result.manifest.provenance[path].input_sources == ("base", "feature:dop:procs", "feature:fdr:procs")
    for kept in ("procs.tcl", "fdr_procs.tcl", "tech_fdr_procs.tcl", "dop/dop_procs.tcl"):
        assert result.manifest.file_decisions[Path(kept)] is FileTreatment.FULL_COPY
        assert (domain / kept).read_text(encoding="utf-8") == "proc kept {} { return 1 }\n"
    if dry_run:
        assert not (domain / path).exists()
    else:
        text = (domain / path).read_text(encoding="utf-8")
        assert text.endswith(
            "# Feature procs.tcl sourcing file for apr_fc\n\n"
            "iproc_source -file fdr_procs.tcl -optional\n"
            "iproc_source -file tech_fdr_procs.tcl -optional\n"
            "iproc_source -file project_fdr_procs.tcl -optional\n\n"
            "iproc_source -file dop/dop_procs.tcl -optional\n"
            "iproc_source -file dop/tech_dop_procs.tcl -optional\n"
            "iproc_source -file dop/project_dop_procs.tcl -optional\n"
        )
        assert "-file procs.tcl" not in text
        assert (domain / "apr_fc_feature_vars.tcl").is_file()
        # Root-level project JSON is an input, not an implicitly retained domain file.
        _write(domain / "project.json", project)
        sink, repeated = _run(domain, dry_run=False)
        assert repeated.exit_code == 0, [d.code for d in sink.snapshot()]
        assert (domain / path).read_text(encoding="utf-8") == text


def test_generated_sourcing_files_flow_to_p4_audit_and_loc(tmp_path: Path) -> None:
    from chopper.adapters import CollectingSink, LocalFS, SilentProgress
    from chopper.core.context import ChopperContext, RunConfig
    from chopper.orchestrator import ChopperRunner
    from chopper.orchestrator.projection import build_loc_report

    domain = _procs_domain(tmp_path)
    # A previously submitted vars file is in the depot already; procs is new.
    _write(domain / "apr_fc_feature_vars.tcl", "# stale\n")
    generated = ("apr_fc_feature_vars.tcl", "apr_fc_feature_procs.tcl")

    # LoC replays the trim in memory; both files land in the GENERATED bucket.
    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=domain,
        backup_root=domain.with_name("apr_fc_backup"),
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
        project_path=domain / "project.json",
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=sink, progress=SilentProgress())
    loc = ChopperRunner().run(ctx, command="loc")
    assert loc.exit_code == 0, [d.code for d in sink.snapshot()]
    assert {a.path.as_posix() for a in loc.generated_artifacts} >= set(generated)
    report = build_loc_report(
        ctx=ctx, parsed=loc.parsed, manifest=loc.manifest, generated_artifacts=loc.generated_artifacts
    )
    bucket = next(b for b in report.buckets if b.treatment == "GENERATED")
    assert bucket.files == len(loc.generated_artifacts)
    assert bucket.sloc_after > 0

    # Live trim: pre-existing depot file -> `p4 edit`, new file -> `p4 add`.
    # Re-trims compare against the pristine backup, so the classification is stable.
    sink, result = _run(domain, dry_run=False)
    assert result.exit_code == 0, [d.code for d in sink.snapshot()]
    p4 = (domain / ".chopper/p4_commands.txt").read_text(encoding="utf-8")
    kept = (domain / ".chopper/files_kept.txt").read_text(encoding="utf-8")
    assert "p4 edit -t text+x apr_fc_feature_vars.tcl" in p4
    assert "p4 add -t text+x apr_fc_feature_procs.tcl" in p4
    for name in generated:
        assert name in kept
        assert name not in (domain / ".chopper/files_removed.txt").read_text(encoding="utf-8")


def test_generated_sourcing_files_are_aggregate_stack_inputs(tmp_path: Path) -> None:
    domain = _procs_domain(tmp_path)
    path = domain / "jsons/apr_fc.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["options"] = {"generate_stack": True}
    data["stages"] = [
        {"name": "setup", "load_from": "", "command": "run setup", "inputs": ["in.v"], "steps": ["set a 1"]},
        {"name": "route", "load_from": "setup", "command": "run route", "steps": ["set b 1"]},
    ]
    _write(path, json.dumps(data))
    sink, result = _run(domain, dry_run=False)
    assert result.exit_code == 0, [d.code for d in sink.snapshot()]
    stack = (domain / "apr_fc.stack").read_text(encoding="utf-8")
    sourcing = "I apr_fc_feature_vars.tcl\nI apr_fc_feature_procs.tcl\n"
    assert f"N setup\nJ run setup\nI in.v\n{sourcing}D\n" in stack
    assert f"N route\nJ run route\n{sourcing}D setup\n" in stack
    assert "iproc_source" not in (domain / "setup.tcl").read_text(encoding="utf-8")


def test_missing_and_duplicate_procs_warn(tmp_path: Path) -> None:
    domain = _procs_domain(tmp_path)
    path = domain / "jsons/features/dop.feature.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["procs"] = "fdr_procs.tcl"
    _write(path, json.dumps(data))
    (domain / "fdr_procs.tcl").unlink()
    sink, result = _run(domain, dry_run=False)
    assert result.exit_code == 0
    codes = [d.code for d in sink.snapshot()]
    assert codes.count("VW-30") == 2
    assert codes.count("VW-31") == 3
    text = (domain / "apr_fc_feature_procs.tcl").read_text(encoding="utf-8")
    assert text.count("iproc_source -file fdr_procs.tcl -optional") == 1
    assert (domain / "tech_fdr_procs.tcl").exists()


def test_v2_without_procs_writes_header_only_file(tmp_path: Path) -> None:
    domain = _domain(tmp_path)
    sink, result = _run(domain, dry_run=False)
    assert result.exit_code == 0, [d.code for d in sink.snapshot()]
    text = (domain / "apr_fc_feature_procs.tcl").read_text(encoding="utf-8")
    assert text.endswith("# Feature procs.tcl sourcing file for apr_fc\n")
    assert "iproc_source" not in text
    assert result.manifest.feature_procs == ()


@pytest.mark.parametrize("stage_collision", [False, True])
def test_procs_generated_path_collision(tmp_path: Path, stage_collision: bool) -> None:
    domain = _procs_domain(tmp_path)
    path = domain / "jsons/apr_fc.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if stage_collision:
        data["stages"] = [{"name": "apr_fc_feature_procs", "load_from": "", "steps": ["set x 1"]}]
    else:
        data["files"]["include"].append("apr_fc_feature_procs.tcl")
        _write(domain / "apr_fc_feature_procs.tcl", "set original 1\n")
    _write(path, json.dumps(data))
    sink, result = _run(domain, dry_run=True)
    assert result.exit_code != 0
    assert "VE-42" in [d.code for d in sink.snapshot()]
