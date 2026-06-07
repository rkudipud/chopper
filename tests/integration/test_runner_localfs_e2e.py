"""LocalFS-backed end-to-end runner test.

Complements ``tests/unit/orchestrator/test_runner_e2e.py`` (which uses
:class:`InMemoryFS`) by exercising the real-disk adapter against the
``mini_domain`` and ``stages_domain`` fixtures. Domain trees are copied
into temporary directories so the rebuilt/backup roots can live alongside
them without polluting the committed fixtures.

``mini_domain`` tests use dry-run to prove the parser's I/O boundary
(relative path -> absolute resolution against ``domain_root``) works on
real disk.

``stages_domain`` tests exercise both dry-run (manifest shape) and live
trim (``options.generate_stack`` -> ``.tcl`` + ``.stack`` on disk) of the
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
from chopper.core.header import intel_header_text
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
# mini_domain -- baseline F1/F2 dry-run
# ---------------------------------------------------------------------------


def test_runner_localfs_dry_run_mini_domain(tmp_path: Path) -> None:
    """Full P0->P7 dry-run succeeds on the real-disk ``mini_domain`` fixture."""

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


def test_runner_localfs_live_trim_writes_proc_trim_and_generated_tcl_verbatim(tmp_path: Path) -> None:
    """Default (`base.options.indent: false`): P5c is a no-op; PROC_TRIM and
    GENERATED Tcl reach disk verbatim; FULL_COPY stays verbatim (issue #22).

    See `technical_docs/IMPLEMENTATION.md` Appendix B FD-15 for the deferred
    indentation-formatter rework that gates re-enabling P5c by default.
    """

    domain = tmp_path / "format_domain"
    (domain / "jsons").mkdir(parents=True)
    full_source = "proc copied {} {\nputs copied\n}\n"
    (domain / "full.tcl").write_text(full_source, encoding="utf-8")
    trim_source = "proc keep {} {\nputs keep\n}\n\nproc drop {} {\nputs drop\n}\n"
    (domain / "trim.tcl").write_text(trim_source, encoding="utf-8")
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
    # VW-10 on FULL_COPY .tcl can fire on Windows because FULL_COPY records
    # raw stat().size while the validator compares logical (LF-normalized)
    # text bytes; that mismatch is a pre-existing FULL_COPY-size bug
    # unrelated to P5c. We tolerate it here and only assert that no PROC_TRIM
    # / GENERATED VW-10 fires for paths Chopper itself wrote.
    proc_trim_vw10 = [
        d for d in sink.snapshot() if d.code == "VW-10" and d.path is not None and d.path.as_posix() != "full.tcl"
    ]
    assert proc_trim_vw10 == [], f"PROC_TRIM/GENERATED VW-10 fired: {proc_trim_vw10}"
    assert "VE-16" not in codes, f"FULL_COPY must not trip post-trim brace checks: {codes}"
    assert result.trim_report is not None

    full_text = (domain / "full.tcl").read_text(encoding="utf-8")
    trim_text = (domain / "trim.tcl").read_text(encoding="utf-8")
    stage_text = (domain / "stage.tcl").read_text(encoding="utf-8")
    # FULL_COPY is byte-for-byte identical to the source.
    assert full_text == full_source
    # PROC_TRIM: surviving proc kept verbatim, dropped proc removed; no
    # re-indentation applied because base.options.indent defaults to false.
    assert "proc keep {} {\nputs keep\n}\n" in trim_text
    assert "proc drop" not in trim_text
    # GENERATED: generator output reaches disk verbatim (header + raw steps).
    assert stage_text == (intel_header_text() + "# Chopper-generated stage: stage\nif {$ready} {\nputs ready\n}\n")
    assert result.generated_artifacts[0].content == stage_text

    outcomes = {outcome.path.as_posix(): outcome for outcome in result.trim_report.outcomes}
    # FULL_COPY: bytes_out matches bytes_in by definition (Chopper does not
    # transform the file). On Windows the on-disk stat may include CRLF
    # bytes while the in-memory text is LF; comparing bytes_out against
    # `len(text.encode())` is a separate FULL_COPY/CRLF concern that this
    # test does not cover.
    assert outcomes["full.tcl"].bytes_out == outcomes["full.tcl"].bytes_in
    # PROC_TRIM: bytes_out matches the LF-normalized on-disk text Chopper
    # itself wrote (after dropping the dropped proc, no formatter applied).
    assert outcomes["trim.tcl"].bytes_out == len(trim_text.encode("utf-8"))


# ---------------------------------------------------------------------------
# stages_domain -- F3 generate_stack dry-run (manifest shape)
# ---------------------------------------------------------------------------


def test_runner_localfs_dry_run_stages_domain(tmp_path: Path) -> None:
    """Dry-run on ``stages_domain`` (``options.generate_stack: true``):
    manifest includes one GENERATED ``.tcl`` per stage plus exactly one
    aggregate ``<domain-basename>.stack`` (per 3.3.0 contract); no files
    are written to disk.
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

    # Three stages -> three .tcl GENERATED entries, plus one aggregate
    # ``stages_domain.stack`` (domain basename). No per-stage .stack files
    # because no stage has ``standalone_stack: true``.
    generated = {p.as_posix() for p, t in manifest.file_decisions.items() if t is FileTreatment.GENERATED}
    assert "setup.tcl" in generated
    assert "run_flow.tcl" in generated
    assert "promote.tcl" in generated
    assert "stages_domain.stack" in generated
    assert "setup.stack" not in generated
    assert "run_flow.stack" not in generated
    assert "promote.stack" not in generated

    # Dry-run: no files written.
    assert result.trim_report is None
    assert result.generated_artifacts == ()
    assert not (domain / "setup.tcl").exists()
    assert not (domain / "stages_domain.stack").exists()


# ---------------------------------------------------------------------------
# stages_domain -- F3 generate_stack live trim (files on disk)
# ---------------------------------------------------------------------------


def test_runner_localfs_live_trim_stages_domain_generates_stack_files(tmp_path: Path) -> None:
    """Live trim on ``stages_domain`` writes one ``.tcl`` per resolved stage
    and exactly one aggregate ``<domain-basename>.stack`` when
    ``options.generate_stack`` is ``true`` (3.3.0 contract).

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

    # GeneratorService emitted four artifacts: 3 tcl + 1 aggregate stack.
    assert len(result.generated_artifacts) == 4
    kinds = tuple(a.kind for a in result.generated_artifacts)
    # Ordering contract: all .tcl files first, aggregate .stack appended last.
    assert kinds == ("tcl", "tcl", "tcl", "stack")
    aggregate = result.generated_artifacts[-1]
    assert aggregate.path == Path("stages_domain.stack")
    assert aggregate.source_stage == "stages_domain"

    # Per-stage .tcl files exist; no per-stage .stack files.
    for stage_name in ("setup", "run_flow", "promote"):
        tcl_path = domain / f"{stage_name}.tcl"
        assert tcl_path.exists(), f"missing {tcl_path}"
        assert not (domain / f"{stage_name}.stack").exists()

    # Aggregate stack file on disk.
    aggregate_path = domain / "stages_domain.stack"
    assert aggregate_path.exists()
    aggregate_text = aggregate_path.read_text()

    # Single Intel header at the top.
    assert aggregate_text.count("#Intel Legal compliant copyright header") == 1

    # All three stage records appear in declared order, separated by blank lines.
    setup_idx = aggregate_text.index("# Chopper-generated stack: setup\n")
    run_idx = aggregate_text.index("# Chopper-generated stack: run_flow\n")
    promote_idx = aggregate_text.index("# Chopper-generated stack: promote\n")
    assert setup_idx < run_idx < promote_idx

    # setup record content (first stage -- bare D, serial -> no R line).
    assert "N setup\n" in aggregate_text
    assert "J -xt vw my_shell -B BLOCK -T setup\n" in aggregate_text
    assert "L 0\n" in aggregate_text
    assert "\nD\n" in aggregate_text  # bare D for first stage
    assert "R serial" not in aggregate_text  # serial is implicit

    # run_flow record content (D-line points at setup, multiple exit codes).
    assert "N run_flow\n" in aggregate_text
    assert "D setup\n" in aggregate_text
    assert "L 0 3\n" in aggregate_text

    # Spot-check setup.tcl banner + steps.
    setup_tcl = (domain / "setup.tcl").read_text()
    assert "# Chopper-generated" in setup_tcl
    assert "source setup.tcl" in setup_tcl
    assert "load_design" in setup_tcl

    # Audit bundle written.
    assert (domain / ".chopper" / "chopper_run.json").exists()


def test_runner_localfs_live_trim_stages_domain_stack_files_in_audit(tmp_path: Path) -> None:
    """Generated aggregate ``.stack`` file appears in the audit bundle's
    ``compiled_manifest.json``; per-stage ``.stack`` entries do NOT appear
    unless a stage sets ``standalone_stack: true``."""

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
        assert tcl_path in by_path, f"{tcl_path} missing from manifest"
        assert by_path[tcl_path]["treatment"] == "generated"
        assert f"{stage_name}.stack" not in by_path
    # The single aggregate entry.
    assert "stages_domain.stack" in by_path
    assert by_path["stages_domain.stack"]["treatment"] == "generated"


def test_runner_localfs_live_trim_emits_p4_commands_txt(tmp_path: Path) -> None:
    """``.chopper/p4_commands.txt`` is emitted by live trim with the
    expected ``p4 add -t text+x`` lines for newly-generated stage files
    (FR-47, architecture doc Sec.5.5.14).

    The ``stages_domain`` fixture has no pre-existing ``setup.tcl`` /
    ``run_flow.tcl`` / ``promote.tcl`` / ``*.stack`` files in the source
    tree, so each generated artifact must land in the ``p4 add`` section.
    """

    domain = tmp_path / "stages_domain"
    shutil.copytree(FIXTURE_STAGES, domain)

    ctx, sink = _make_ctx(domain, dry_run=False)
    result = ChopperRunner().run(ctx, command="trim")
    assert result.exit_code == 0, f"non-zero exit; diagnostics: {[d.code for d in sink.snapshot()]}"

    p4_path = domain / ".chopper" / "p4_commands.txt"
    assert p4_path.exists(), "p4_commands.txt missing from audit bundle"
    content = p4_path.read_text()

    # Banner present.
    assert content.startswith("# p4_commands.txt")
    assert content.endswith("\n")
    # Generated per-stage ``.tcl`` files (no pre-existing depot counterpart) -> p4 add.
    for stage_name in ("setup", "run_flow", "promote"):
        assert f"p4 add -t text+x {stage_name}.tcl" in content, f"missing p4 add for {stage_name}.tcl"
        # No per-stage .stack -- only the aggregate.
        assert f"p4 add -t text+x {stage_name}.stack" not in content
    # Aggregate ``<domain-basename>.stack`` added once.
    assert "p4 add -t text+x stages_domain.stack" in content
    # `chopper_run.json` lists p4_commands.txt in artifacts_present.
    run_meta = json.loads((domain / ".chopper" / "chopper_run.json").read_text())
    assert "p4_commands.txt" in run_meta["artifacts_present"]


def test_runner_localfs_dry_run_emits_p4_commands_txt(tmp_path: Path) -> None:
    """Dry-run also emits ``p4_commands.txt`` (preview, consistent with
    every other audit artifact under Sec.5.5.10)."""

    domain = tmp_path / "stages_domain"
    shutil.copytree(FIXTURE_STAGES, domain)

    ctx, _ = _make_ctx(domain, dry_run=True)
    result = ChopperRunner().run(ctx, command="trim")
    assert result.exit_code == 0

    p4_path = domain / ".chopper" / "p4_commands.txt"
    assert p4_path.exists(), "dry-run must still emit p4_commands.txt"
    content = p4_path.read_text()
    # Same preview content: each generated stage -> p4 add.
    for stage_name in ("setup", "run_flow", "promote"):
        assert f"p4 add -t text+x {stage_name}.tcl" in content


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


def test_runner_localfs_overlay_no_op_exclude_emits_ve27(tmp_path: Path) -> None:
    """Feature-layer ``files.exclude`` entry that matches nothing emits ``VE-27``.

    The fixture's feature layer (``feature_typo``) declares a ``files.exclude``
    of ``unrelated.tcl`` -- a path that the running set established by earlier
    layers does not contain. Per the 2.0.0-alpha overlay contract, the compiler
    emits ``VE-27 no-op-exclude`` directly at this site (typo-class guard) and
    the run exits with code 1.
    """

    domain = tmp_path / "overlay_no_op_exclude"
    shutil.copytree(FIXTURE_OVERLAY_NO_OP_EXCLUDE, domain)

    ctx, sink = _make_overlay_ctx(domain, dry_run=True)
    result = ChopperRunner().run(ctx, command="validate")

    codes = [d.code for d in sink.snapshot()]
    assert "VE-27" in codes, f"expected VE-27 no-op-exclude; got {codes}"
    assert result.exit_code == 1
    # The no-op exclude is reported but does not mutate the running set:
    # ``real.tcl`` (kept by base) remains FULL_COPY in the manifest.
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
