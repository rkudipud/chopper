"""LocalFS-backed end-to-end runner test.

Complements ``tests/unit/orchestrator/test_runner_e2e.py`` (which uses
:class:`InMemoryFS`) by exercising the real-disk adapter against the
``mini_domain`` and ``stages_domain`` fixtures. Domain trees are copied
into temporary directories so the rebuilt/backup roots can live alongside
them without polluting the committed fixtures.

``mini_domain`` tests use dry-run to prove the parser's I/O boundary
(relative path → absolute resolution against ``domain_root``) works on
real disk.

``stages_domain`` tests exercise both dry-run (manifest shape) and live
trim (``options.generate_stack`` → ``.tcl`` + ``.stack`` on disk) of the
F3 stage generation path.  These are the authoritative integration tests
for ``options.generate_stack``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from chopper.adapters import CollectingSink, LocalFS, SilentProgress
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.models_common import FileTreatment
from chopper.orchestrator import ChopperRunner

FIXTURE_MINI = Path(__file__).resolve().parents[1] / "fixtures" / "mini_domain"
FIXTURE_STAGES = Path(__file__).resolve().parents[1] / "fixtures" / "stages_domain"


def _make_ctx(domain: Path, *, dry_run: bool = True) -> tuple[ChopperContext, CollectingSink]:
    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=domain,
        backup_root=domain.with_name(domain.name + "_backup"),
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=dry_run,
        base_path=domain / "jsons" / "base.json",
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=sink, progress=SilentProgress())
    return ctx, sink


# ---------------------------------------------------------------------------
# mini_domain — baseline F1/F2 dry-run
# ---------------------------------------------------------------------------


def test_runner_localfs_dry_run_mini_domain(tmp_path: Path) -> None:
    """Full P0→P7 dry-run succeeds on the real-disk ``mini_domain`` fixture."""

    domain = tmp_path / "mini_domain"
    shutil.copytree(FIXTURE_MINI, domain)

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


# ---------------------------------------------------------------------------
# stages_domain — F3 generate_stack dry-run (manifest shape)
# ---------------------------------------------------------------------------


def test_runner_localfs_dry_run_stages_domain(tmp_path: Path) -> None:
    """Dry-run on ``stages_domain`` (``options.generate_stack: true``):
    manifest includes GENERATED entries for every ``.tcl`` and ``.stack`` pair;
    no files are written to disk.
    """

    domain = tmp_path / "stages_domain"
    shutil.copytree(FIXTURE_STAGES, domain)

    ctx, sink = _make_ctx(domain, dry_run=True)
    result = ChopperRunner().run(ctx, command="validate")

    codes = [d.code for d in sink.snapshot()]
    assert result.exit_code == 0, f"non-zero exit; diagnostics: {codes}"
    assert result.manifest is not None

    manifest = result.manifest
    assert manifest.generate_stack is True

    # Three stages → three .tcl + three .stack GENERATED entries.
    generated = {p.as_posix() for p, t in manifest.file_decisions.items() if t is FileTreatment.GENERATED}
    assert "setup.tcl" in generated
    assert "setup.stack" in generated
    assert "run_flow.tcl" in generated
    assert "run_flow.stack" in generated
    assert "promote.tcl" in generated
    assert "promote.stack" in generated

    # Dry-run: no files written.
    assert result.trim_report is None
    assert result.generated_artifacts == ()
    assert not (domain / "setup.tcl").exists()
    assert not (domain / "setup.stack").exists()


# ---------------------------------------------------------------------------
# stages_domain — F3 generate_stack live trim (files on disk)
# ---------------------------------------------------------------------------


def test_runner_localfs_live_trim_stages_domain_generates_stack_files(tmp_path: Path) -> None:
    """Live trim on ``stages_domain`` writes one ``.tcl`` + one ``.stack`` per
    resolved stage when ``options.generate_stack`` is ``true``.

    This is the primary end-to-end validation that the F3 stack-file path
    (P5b ``GeneratorService``) works correctly on a real filesystem.
    """

    domain = tmp_path / "stages_domain"
    shutil.copytree(FIXTURE_STAGES, domain)

    ctx, sink = _make_ctx(domain, dry_run=False)
    result = ChopperRunner().run(ctx, command="trim")

    codes = [d.code for d in sink.snapshot()]
    assert result.exit_code == 0, f"non-zero exit; diagnostics: {codes}"
    assert result.manifest is not None
    assert result.trim_report is not None

    # GeneratorService emitted six artifacts: tcl+stack for each of 3 stages.
    assert len(result.generated_artifacts) == 6
    kinds = tuple(a.kind for a in result.generated_artifacts)
    # Ordering contract: per stage, .tcl immediately precedes .stack.
    assert kinds == ("tcl", "stack", "tcl", "stack", "tcl", "stack")

    # All six files exist on disk.
    for stage_name in ("setup", "run_flow", "promote"):
        tcl_path = domain / f"{stage_name}.tcl"
        stack_path = domain / f"{stage_name}.stack"
        assert tcl_path.exists(), f"missing {tcl_path}"
        assert stack_path.exists(), f"missing {stack_path}"

    # Spot-check setup.stack content — N/J/L/D/R lines.
    setup_stack = (domain / "setup.stack").read_text()
    assert setup_stack.startswith("# Chopper-generated stack: setup\n")
    assert "N setup\n" in setup_stack
    assert "J -xt vw my_shell -B BLOCK -T setup\n" in setup_stack
    assert "L 0\n" in setup_stack
    assert "D\n" in setup_stack  # first stage — no predecessor → bare D
    assert "R serial\n" in setup_stack

    # Spot-check run_flow.stack — dependencies → D line per dep.
    run_flow_stack = (domain / "run_flow.stack").read_text()
    assert "N run_flow\n" in run_flow_stack
    assert "D setup\n" in run_flow_stack
    assert "L 0 3\n" in run_flow_stack

    # Spot-check setup.tcl banner + steps.
    setup_tcl = (domain / "setup.tcl").read_text()
    assert "# Chopper-generated" in setup_tcl
    assert "source setup.tcl" in setup_tcl
    assert "load_design" in setup_tcl

    # Audit bundle written.
    assert (domain / ".chopper" / "chopper_run.json").exists()


def test_runner_localfs_live_trim_stages_domain_stack_files_in_audit(tmp_path: Path) -> None:
    """Generated ``.stack`` files appear in the audit bundle's compiled_manifest."""

    domain = tmp_path / "stages_domain"
    shutil.copytree(FIXTURE_STAGES, domain)

    ctx, sink = _make_ctx(domain, dry_run=False)
    result = ChopperRunner().run(ctx, command="trim")

    assert result.exit_code == 0
    # compiled_manifest.json must record all GENERATED entries.
    manifest_path = domain / ".chopper" / "compiled_manifest.json"
    assert manifest_path.exists(), "compiled_manifest.json not written"
    data = json.loads(manifest_path.read_text())
    files = data.get("files", [])
    by_path = {entry["path"]: entry for entry in files}
    for stage_name in ("setup", "run_flow", "promote"):
        tcl_path = f"{stage_name}.tcl"
        stack_path = f"{stage_name}.stack"
        assert tcl_path in by_path, f"{tcl_path} missing from manifest"
        assert stack_path in by_path, f"{stack_path} missing from manifest"
        assert by_path[tcl_path]["treatment"] == "generated"
        assert by_path[stack_path]["treatment"] == "generated"
