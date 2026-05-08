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

import hashlib
import json
import shutil
from pathlib import Path

from chopper.adapters import CollectingSink, LocalFS, SilentProgress
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.models_common import FileTreatment
from chopper.orchestrator import ChopperRunner
from chopper.parser.service import parse_file

FIXTURE_MINI = Path(__file__).resolve().parents[1] / "fixtures" / "mini_domain"
FIXTURE_STAGES = Path(__file__).resolve().parents[1] / "fixtures" / "stages_domain"
FIXTURE_OVERLAY_REPLACE = Path(__file__).resolve().parents[1] / "fixtures" / "overlay_replace"
FIXTURE_OVERLAY_REMOVE_ONLY = Path(__file__).resolve().parents[1] / "fixtures" / "overlay_remove_only"
FIXTURE_OVERLAY_NO_OP_EXCLUDE = Path(__file__).resolve().parents[1] / "fixtures" / "overlay_no_op_exclude"
FIXTURE_OVERLAY_TWO_FEATURES_SAME_FILE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "overlay_two_features_same_file"
)


def _make_ctx(
    domain: Path,
    *,
    dry_run: bool = True,
    base_path: Path | None = None,
    feature_paths: tuple[Path, ...] = (),
) -> tuple[ChopperContext, CollectingSink]:
    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=domain,
        backup_root=domain.with_name(domain.name + "_backup"),
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=dry_run,
        base_path=base_path or domain / "jsons" / "base.json",
        feature_paths=feature_paths,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=sink, progress=SilentProgress())
    return ctx, sink


def _domain_payload_hashes(domain: Path) -> dict[str, str]:
    """Return file payload hashes under ``domain``, excluding Chopper audit output."""

    out: dict[str, str] = {}
    for file_path in sorted(domain.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(domain)
        if rel.parts and rel.parts[0] == ".chopper":
            continue
        out[rel.as_posix()] = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return out


def _copy_fixture_jsons(domain: Path, target: Path) -> Path:
    config_root = target / "jsons"
    shutil.copytree(domain / "jsons", config_root)
    return config_root


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


def test_runner_localfs_dry_run_manifest_matches_live_trim_outputs_1_to_1(tmp_path: Path) -> None:
    """Dry-run manifest expectations must match live trim outputs 1:1.

    The same fixture is first run in dry-run mode (to get the expected
    manifest), then run in live mode. The rebuilt domain files and proc
    sets must match the dry-run manifest exactly.
    """

    domain = tmp_path / "mini_domain"
    shutil.copytree(FIXTURE_MINI, domain)

    dry_ctx, dry_sink = _make_ctx(domain, dry_run=True)
    dry_result = ChopperRunner().run(dry_ctx, command="validate")
    dry_codes = [d.code for d in dry_sink.snapshot()]
    assert dry_result.exit_code == 0, f"dry-run failed; diagnostics: {dry_codes}"
    assert dry_result.manifest is not None

    expected_manifest = dry_result.manifest
    expected_keep_by_file: dict[Path, set[str]] = {}
    for canonical_name, decision in expected_manifest.proc_decisions.items():
        expected_keep_by_file.setdefault(decision.source_file, set()).add(canonical_name)

    live_ctx, live_sink = _make_ctx(domain, dry_run=False)
    live_result = ChopperRunner().run(live_ctx, command="trim")
    live_codes = [d.code for d in live_sink.snapshot()]
    assert live_result.exit_code == 0, f"live trim failed; diagnostics: {live_codes}"
    assert "VW-10" not in live_codes, f"live trim reported output mismatch: {live_codes}"

    for rel_path, treatment in expected_manifest.file_decisions.items():
        if treatment is FileTreatment.GENERATED:
            continue

        target = domain / rel_path
        if treatment is FileTreatment.REMOVE:
            assert not target.exists(), f"expected removed file still present: {target}"
            continue

        assert target.exists(), f"expected surviving file missing: {target}"
        assert target.is_file(), f"expected file, found directory: {target}"

        text = target.read_text(encoding="utf-8")
        actual_proc_set = {proc.canonical_name for proc in parse_file(rel_path, text)}
        expected_proc_set = expected_keep_by_file.get(rel_path, set())
        assert actual_proc_set == expected_proc_set, (
            f"proc-set mismatch for {rel_path.as_posix()!r}: "
            f"expected={sorted(expected_proc_set)!r}, actual={sorted(actual_proc_set)!r}"
        )


def test_runner_localfs_live_rerun_same_selection_is_byte_stable(tmp_path: Path) -> None:
    """A Case-2 rerun with the same selection discards stale domain edits and rebuilds byte-stably."""

    domain = tmp_path / "mini_domain"
    shutil.copytree(FIXTURE_MINI, domain)
    config_root = _copy_fixture_jsons(domain, tmp_path / "config_same_selection")

    first_ctx, first_sink = _make_ctx(domain, dry_run=False, base_path=config_root / "base.json")
    first_result = ChopperRunner().run(first_ctx, command="trim")
    first_codes = [d.code for d in first_sink.snapshot()]
    assert first_result.exit_code == 0, f"first trim failed; diagnostics: {first_codes}"
    assert first_result.state is not None
    assert first_result.state.case == 1
    first_hashes = _domain_payload_hashes(domain)

    stale = domain / "stale_after_first_trim.tcl"
    stale.write_text("proc stale {} { return stale }\n", encoding="utf-8")

    second_ctx, second_sink = _make_ctx(domain, dry_run=False, base_path=config_root / "base.json")
    second_result = ChopperRunner().run(second_ctx, command="trim")
    second_codes = [d.code for d in second_sink.snapshot()]
    assert second_result.exit_code == 0, f"rerun failed; diagnostics: {second_codes}"
    assert second_result.state is not None
    assert second_result.state.case == 2

    assert not stale.exists(), "Case-2 rerun must discard stale rebuilt-domain edits"
    assert _domain_payload_hashes(domain) == first_hashes


def test_runner_localfs_live_rerun_with_feature_changes_selection(tmp_path: Path) -> None:
    """A Case-2 rerun can rebuild from backup with an expanded feature selection."""

    domain = tmp_path / "mini_domain"
    shutil.copytree(FIXTURE_MINI, domain)
    config_root = _copy_fixture_jsons(domain, tmp_path / "config_feature_rerun")

    base_ctx, base_sink = _make_ctx(domain, dry_run=False, base_path=config_root / "base.json")
    base_result = ChopperRunner().run(base_ctx, command="trim")
    base_codes = [d.code for d in base_sink.snapshot()]
    assert base_result.exit_code == 0, f"base trim failed; diagnostics: {base_codes}"
    assert not (domain / "extra_utils.tcl").exists()
    assert "proc cleanup_flow" not in (domain / "main_flow.tcl").read_text(encoding="utf-8")

    feature_ctx, feature_sink = _make_ctx(
        domain,
        dry_run=False,
        base_path=config_root / "base.json",
        feature_paths=(config_root / "features" / "feature_a.json",),
    )
    feature_result = ChopperRunner().run(feature_ctx, command="trim")
    feature_codes = [d.code for d in feature_sink.snapshot()]
    assert feature_result.exit_code == 0, f"feature rerun failed; diagnostics: {feature_codes}"
    assert feature_result.state is not None
    assert feature_result.state.case == 2

    assert (domain / "extra_utils.tcl").exists()
    assert "proc cleanup_flow" in (domain / "main_flow.tcl").read_text(encoding="utf-8")


def test_runner_localfs_dry_live_dry_sequence_keeps_domain_payload_stable(tmp_path: Path) -> None:
    """Dry-run before and after a live trim must not mutate rebuilt domain payloads."""

    domain = tmp_path / "mini_domain"
    shutil.copytree(FIXTURE_MINI, domain)
    config_root = _copy_fixture_jsons(domain, tmp_path / "config_dry_live_dry")

    dry_ctx, dry_sink = _make_ctx(domain, dry_run=True, base_path=config_root / "base.json")
    dry_result = ChopperRunner().run(dry_ctx, command="validate")
    dry_codes = [d.code for d in dry_sink.snapshot()]
    assert dry_result.exit_code == 0, f"initial dry-run failed; diagnostics: {dry_codes}"
    before_live_hashes = _domain_payload_hashes(domain)

    live_ctx, live_sink = _make_ctx(domain, dry_run=False, base_path=config_root / "base.json")
    live_result = ChopperRunner().run(live_ctx, command="trim")
    live_codes = [d.code for d in live_sink.snapshot()]
    assert live_result.exit_code == 0, f"live trim failed; diagnostics: {live_codes}"
    after_live_hashes = _domain_payload_hashes(domain)
    assert after_live_hashes != before_live_hashes

    dry_again_ctx, dry_again_sink = _make_ctx(domain, dry_run=True, base_path=config_root / "base.json")
    dry_again_result = ChopperRunner().run(dry_again_ctx, command="validate")
    dry_again_codes = [d.code for d in dry_again_sink.snapshot()]
    assert dry_again_result.exit_code == 0, f"post-live dry-run failed; diagnostics: {dry_again_codes}"

    assert _domain_payload_hashes(domain) == after_live_hashes


def test_runner_localfs_live_trim_formats_full_copy_proc_trim_and_generated_tcl(tmp_path: Path) -> None:
    """P5c formats every emitted Tcl output before P6 validates byte counts."""

    domain = tmp_path / "format_domain"
    (domain / "jsons").mkdir(parents=True)
    (domain / "full.tcl").write_text("proc copied {} {\nputs copied\n}\n", encoding="utf-8")
    (domain / "trim.tcl").write_text(
        "proc keep {} {\nputs keep\n}\n\nproc drop {} {\nputs drop\n}\n",
        encoding="utf-8",
    )
    (domain / "jsons" / "base.json").write_text(
        json.dumps(
            {
                "$schema": "base-v1",
                "domain": "format_domain",
                "files": {"include": ["full.tcl"]},
                "procedures": {"include": [{"file": "trim.tcl", "procs": ["keep"]}]},
                "stages": [
                    {
                        "name": "stage",
                        "load_from": "",
                        "steps": ["if {$ready} {", "puts ready", "}"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    ctx, sink = _make_ctx(domain, dry_run=False)
    result = ChopperRunner().run(ctx, command="trim")

    codes = [d.code for d in sink.snapshot()]
    assert result.exit_code == 0, f"live trim failed; diagnostics: {codes}"
    assert "VW-10" not in codes, f"formatting byte counts drifted from P6 expectations: {codes}"
    assert result.trim_report is not None

    full_text = (domain / "full.tcl").read_text(encoding="utf-8")
    trim_text = (domain / "trim.tcl").read_text(encoding="utf-8")
    stage_text = (domain / "stage.tcl").read_text(encoding="utf-8")
    assert full_text == "proc copied {} {\n    puts copied\n}\n"
    assert "proc keep" in trim_text
    assert "    puts keep\n" in trim_text
    assert "proc drop" not in trim_text
    assert stage_text == "# Chopper-generated stage: stage\nif {$ready} {\n    puts ready\n}\n"
    assert result.generated_artifacts[0].content == stage_text

    outcomes = {outcome.path.as_posix(): outcome for outcome in result.trim_report.outcomes}
    assert outcomes["full.tcl"].bytes_out == len(full_text.encode("utf-8"))
    assert outcomes["trim.tcl"].bytes_out == len(trim_text.encode("utf-8"))


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




# ---------------------------------------------------------------------------
# overlay_* fixtures \u2014 R1 ordered-overlay end-to-end
# ---------------------------------------------------------------------------


def _make_overlay_ctx(domain: Path, *, dry_run: bool = True) -> tuple[ChopperContext, CollectingSink]:
    return _make_ctx(
        domain,
        dry_run=dry_run,
        base_path=domain / "jsons" / "base.json",
        feature_paths=tuple(sorted((domain / "jsons" / "features").glob("*.json"))),
    )


def test_runner_localfs_overlay_replace_emits_vw21_and_swaps_files(tmp_path: Path) -> None:
    """Feature-layer exclude of a base-included file replaces it with the feature's own file.

    Asserts the surviving manifest contains `new.tcl` (FULL_COPY) and `legacy.tcl`
    is REMOVE, and that `VW-21 layer-shadowed` fires for the feature's removal of
    the base contribution.
    """

    domain = tmp_path / "overlay_replace"
    shutil.copytree(FIXTURE_OVERLAY_REPLACE, domain)

    ctx, sink = _make_overlay_ctx(domain, dry_run=True)
    result = ChopperRunner().run(ctx, command="validate")

    codes = [d.code for d in sink.snapshot()]
    assert result.exit_code == 0, f"non-zero exit; diagnostics: {codes}"
    assert "VW-21" in codes, f"expected VW-21 layer-shadowed; got {codes}"

    assert result.manifest is not None
    decisions = result.manifest.file_decisions
    assert decisions[Path("new.tcl")] is FileTreatment.FULL_COPY
    assert decisions[Path("legacy.tcl")] is FileTreatment.REMOVE


def test_runner_localfs_overlay_remove_only_emits_vw21(tmp_path: Path) -> None:
    """Feature-layer exclude of a base-included file with no replacement still emits VW-21."""

    domain = tmp_path / "overlay_remove_only"
    shutil.copytree(FIXTURE_OVERLAY_REMOVE_ONLY, domain)

    ctx, sink = _make_overlay_ctx(domain, dry_run=True)
    result = ChopperRunner().run(ctx, command="validate")

    codes = [d.code for d in sink.snapshot()]
    assert result.exit_code == 0, f"non-zero exit; diagnostics: {codes}"
    assert "VW-21" in codes

    assert result.manifest is not None
    decisions = result.manifest.file_decisions
    assert decisions[Path("core.tcl")] is FileTreatment.REMOVE
    assert decisions[Path("keep.tcl")] is FileTreatment.FULL_COPY


def test_runner_localfs_overlay_no_op_exclude_loads_cleanly(tmp_path: Path) -> None:
    """Fixture loads and parses cleanly.

    ``VE-27 no-op-exclude`` is registered in the diagnostic catalog but the validator
    emission is not yet implemented (the compiler defers to the validator with
    ``# No-op exclude — VE-27 handled by validator.`` and the validator has no
    matching check). When the emission lands, this test should be tightened to assert
    ``VE-27`` in ``codes`` and ``exit_code == 1``. Tracked under SPEC_COVERAGE_AUDIT.md.
    """

    domain = tmp_path / "overlay_no_op_exclude"
    shutil.copytree(FIXTURE_OVERLAY_NO_OP_EXCLUDE, domain)

    ctx, _sink = _make_overlay_ctx(domain, dry_run=True)
    result = ChopperRunner().run(ctx, command="validate")

    # Pre-impl: run succeeds; the silently-no-op exclude leaves real.tcl intact.
    assert result.exit_code == 0
    assert result.manifest is not None
    assert result.manifest.file_decisions[Path("real.tcl")] is FileTreatment.FULL_COPY


def test_runner_localfs_overlay_two_features_last_layer_wins(tmp_path: Path) -> None:
    """feature_a PE drops proc foo; feature_b PI re-includes it; final keeps both foo and bar."""

    domain = tmp_path / "overlay_two_features_same_file"
    shutil.copytree(FIXTURE_OVERLAY_TWO_FEATURES_SAME_FILE, domain)

    ctx, sink = _make_overlay_ctx(domain, dry_run=True)
    result = ChopperRunner().run(ctx, command="validate")

    codes = [d.code for d in sink.snapshot()]
    assert result.exit_code == 0, f"non-zero exit; diagnostics: {codes}"

    assert result.manifest is not None
    proc_names = {d.canonical_name.split("::", 1)[1] for d in result.manifest.proc_decisions.values()}
    assert "foo" in proc_names, f"foo should survive feature_b PI; got {proc_names}"
    assert "bar" in proc_names, f"bar should survive base WHOLE; got {proc_names}"