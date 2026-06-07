"""Unit tests for :mod:`chopper.generators`."""

from __future__ import annotations

from pathlib import Path

from chopper.adapters import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.header import intel_header_text
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest, FileProvenance, StageSpec
from chopper.generators import GeneratorService
from chopper.generators.stage_emitter import emit_stage_tcl, stage_output_path

DOMAIN = Path("/work/my_domain")


class _Sink:
    def __init__(self) -> None:
        self.emissions: list[Diagnostic] = []

    def emit(self, d: Diagnostic) -> None:  # pragma: no cover - not used
        self.emissions.append(d)

    def snapshot(self) -> tuple[Diagnostic, ...]:  # pragma: no cover
        return tuple(self.emissions)

    def finalize(self) -> DiagnosticSummary:  # pragma: no cover
        return DiagnosticSummary(errors=0, warnings=0, infos=0)


class _Progress:
    def phase_started(self, phase: Phase) -> None: ...  # pragma: no cover
    def phase_done(self, phase: Phase) -> None: ...  # pragma: no cover
    def step(self, message: str) -> None: ...  # pragma: no cover


def _make_ctx(*, dry_run: bool = False) -> tuple[ChopperContext, InMemoryFS]:
    fs = InMemoryFS()
    cfg = RunConfig(
        domain_root=DOMAIN,
        backup_root=Path("/work/my_domain_backup"),
        audit_root=DOMAIN / ".chopper",
        strict=False,
        dry_run=dry_run,
    )
    ctx = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())
    return ctx, fs


def _manifest_with_stages(stages: tuple[StageSpec, ...]) -> CompiledManifest:
    """Build a manifest whose ``file_decisions`` covers only the stage files."""

    file_decisions: dict[Path, FileTreatment] = {}
    provenance: dict[Path, FileProvenance] = {}
    for stage in stages:
        path = stage_output_path(stage)
        file_decisions[path] = FileTreatment.GENERATED
        provenance[path] = FileProvenance(
            path=path,
            treatment=FileTreatment.GENERATED,
            reason="fi-literal",
            input_sources=("base:stages",),
        )
    # manifests must be lex-sorted
    file_decisions = {k: file_decisions[k] for k in sorted(file_decisions, key=lambda p: p.as_posix())}
    provenance = {k: provenance[k] for k in sorted(provenance, key=lambda p: p.as_posix())}
    return CompiledManifest(
        file_decisions=file_decisions,
        proc_decisions={},
        provenance=provenance,
        stages=stages,
    )


def _manifest_with_stages_and_stack(stages: tuple[StageSpec, ...]) -> CompiledManifest:
    """Manifest mirroring compiler output when ``generate_stack`` is on."""

    file_decisions: dict[Path, FileTreatment] = {}
    provenance: dict[Path, FileProvenance] = {}
    for stage in stages:
        for path in (Path(f"{stage.name}.tcl"), Path(f"{stage.name}.stack")):
            file_decisions[path] = FileTreatment.GENERATED
            provenance[path] = FileProvenance(
                path=path,
                treatment=FileTreatment.GENERATED,
                reason="fi-literal",
                input_sources=("base:stages",),
            )
    file_decisions = {k: file_decisions[k] for k in sorted(file_decisions, key=lambda p: p.as_posix())}
    provenance = {k: provenance[k] for k in sorted(provenance, key=lambda p: p.as_posix())}
    return CompiledManifest(
        file_decisions=file_decisions,
        proc_decisions={},
        provenance=provenance,
        stages=stages,
        generate_stack=True,
    )


# ---------------------------------------------------------------------------
# stage_emitter
# ---------------------------------------------------------------------------


def test_emit_stage_tcl_preserves_steps_verbatim() -> None:
    stage = StageSpec(name="setup", steps=("puts hi", "puts {world}"))
    art = emit_stage_tcl(stage)
    assert art.path == Path("setup.tcl")
    assert art.kind == "tcl"
    assert art.source_stage == "setup"
    # Intel header, banner, then steps, trailing newline.
    assert art.content.startswith(intel_header_text())
    lines = art.content.splitlines()
    assert any(line.startswith("# Chopper-generated") for line in lines)
    assert lines[-2:] == ["puts hi", "puts {world}"]
    assert art.content.endswith("\n")


def test_emit_stage_tcl_includes_load_from_when_set() -> None:
    stage = StageSpec(name="run", steps=("do_it",), load_from="setup")
    art = emit_stage_tcl(stage)
    assert "# load_from: setup" in art.content


def test_stage_output_path_defaults_to_stage_name_tcl() -> None:
    stage = StageSpec(name="verify", steps=("x",))
    assert stage_output_path(stage) == Path("verify.tcl")


# ---------------------------------------------------------------------------
# GeneratorService
# ---------------------------------------------------------------------------


def test_service_writes_one_file_per_stage() -> None:
    ctx, fs = _make_ctx()
    stages = (
        StageSpec(name="setup", steps=("a", "b")),
        StageSpec(name="run", steps=("x",)),
    )
    manifest = _manifest_with_stages(stages)

    arts = GeneratorService().run(ctx, manifest)
    assert tuple(a.source_stage for a in arts) == ("setup", "run")
    assert fs.exists(DOMAIN / "setup.tcl")
    assert fs.exists(DOMAIN / "run.tcl")
    assert fs.read_text(DOMAIN / "setup.tcl") == arts[0].content
    assert fs.read_text(DOMAIN / "run.tcl") == arts[1].content


def test_service_dry_run_builds_artifacts_but_writes_nothing() -> None:
    ctx, fs = _make_ctx(dry_run=True)
    stages = (StageSpec(name="setup", steps=("a",)),)
    manifest = _manifest_with_stages(stages)

    arts = GeneratorService().run(ctx, manifest)
    assert len(arts) == 1
    assert not fs.exists(DOMAIN / "setup.tcl")


def test_service_returns_stages_in_manifest_order() -> None:
    ctx, _fs = _make_ctx()
    stages = (
        StageSpec(name="first", steps=("a",)),
        StageSpec(name="middle", steps=("b",)),
        StageSpec(name="last", steps=("c",)),
    )
    manifest = _manifest_with_stages(stages)
    arts = GeneratorService().run(ctx, manifest)
    assert tuple(a.source_stage for a in arts) == ("first", "middle", "last")


def test_service_no_stages_returns_empty_tuple() -> None:
    ctx, fs = _make_ctx()
    manifest = CompiledManifest(file_decisions={}, proc_decisions={}, provenance={}, stages=())
    assert GeneratorService().run(ctx, manifest) == ()
    # No writes.
    assert not fs.exists(DOMAIN)


# ---------------------------------------------------------------------------
# options.generate_stack -> .stack emission
# ---------------------------------------------------------------------------


def test_service_does_not_emit_stack_files_when_flag_off() -> None:
    ctx, fs = _make_ctx()
    stages = (StageSpec(name="setup", steps=("a",)),)
    manifest = _manifest_with_stages(stages)
    arts = GeneratorService().run(ctx, manifest)
    assert tuple(a.kind for a in arts) == ("tcl",)
    assert not fs.exists(DOMAIN / "setup.stack")


def test_service_emits_aggregate_stack_when_flag_on() -> None:
    """``options.generate_stack: true`` -> one aggregate ``<domain>.stack``,
    appended after all per-stage ``.tcl`` files."""

    ctx, fs = _make_ctx()
    stages = (
        StageSpec(name="setup", steps=("a",), command="-tool x"),
        StageSpec(name="run", steps=("b",), command="-tool y", load_from="setup"),
    )
    manifest = _manifest_with_stages_and_stack(stages)

    arts = GeneratorService().run(ctx, manifest)
    # Aggregate (kind="stack", source_stage=<domain>) is the final element.
    assert tuple((a.source_stage, a.kind) for a in arts) == (
        ("setup", "tcl"),
        ("run", "tcl"),
        (DOMAIN.name, "stack"),
    )
    # No per-stage ``.stack`` files when standalone_stack is not set.
    assert not fs.exists(DOMAIN / "setup.stack")
    assert not fs.exists(DOMAIN / "run.stack")
    # The aggregate file is written at ``<domain>/<domain-basename>.stack``.
    aggregate_path = DOMAIN / f"{DOMAIN.name}.stack"
    assert fs.exists(aggregate_path)
    aggregate_text = fs.read_text(aggregate_path)
    # Single header at the top, both stage records present.
    assert aggregate_text.count("#Intel Legal compliant copyright header") == 1
    assert "# Chopper-generated stack: setup\n" in aggregate_text
    assert "# Chopper-generated stack: run\n" in aggregate_text


def test_service_emits_standalone_stack_per_stage_when_flag_set() -> None:
    """``stage.standalone_stack: true`` -> per-stage ``<stage>.stack`` is
    emitted **instead of** the ``.tcl`` (3.4.0: standalone stack is the
    stage's sole driver). Regardless of ``options.generate_stack``."""

    ctx, fs = _make_ctx()
    stages = (
        StageSpec(name="setup", steps=("a",)),
        StageSpec(name="eco_apply_patch", steps=("rm -rf x", "cp y z"), standalone_stack=True),
    )
    manifest = _manifest_with_stages(stages)

    arts = GeneratorService().run(ctx, manifest)
    assert tuple((a.source_stage, a.kind) for a in arts) == (
        ("setup", "tcl"),
        ("eco_apply_patch", "stack"),
    )
    assert not fs.exists(DOMAIN / "setup.stack")
    assert fs.exists(DOMAIN / "eco_apply_patch.stack")
    # 3.4.0: standalone stage does NOT emit a .tcl.
    assert not fs.exists(DOMAIN / "eco_apply_patch.tcl")
    standalone_text = fs.read_text(DOMAIN / "eco_apply_patch.stack")
    # Verbatim steps body -- Intel header + blank line + steps.
    assert standalone_text == intel_header_text() + "\n" + "rm -rf x\ncp y z\n"


def test_service_emits_aggregate_and_standalone_together() -> None:
    """Mixed flow: ``options.generate_stack: true`` + one stage with
    ``standalone_stack: true``. The non-standalone stage emits ``.tcl``;
    the standalone stage emits ``.stack`` instead; the aggregate is
    appended last."""

    ctx, fs = _make_ctx()
    stages = (
        StageSpec(name="setup", steps=("a",), command="-tool x"),
        StageSpec(
            name="eco_apply_patch",
            steps=("rm -rf x",),
            command="-tool patch",
            standalone_stack=True,
        ),
    )
    manifest = _manifest_with_stages_and_stack(stages)

    arts = GeneratorService().run(ctx, manifest)
    assert tuple((a.source_stage, a.kind) for a in arts) == (
        ("setup", "tcl"),
        ("eco_apply_patch", "stack"),
        (DOMAIN.name, "stack"),
    )
    assert fs.exists(DOMAIN / "eco_apply_patch.stack")
    assert not fs.exists(DOMAIN / "eco_apply_patch.tcl")
    assert fs.exists(DOMAIN / f"{DOMAIN.name}.stack")
    # ``setup`` (no standalone_stack) has no per-stage stack.
    assert not fs.exists(DOMAIN / "setup.stack")


def test_service_dry_run_builds_stack_artifacts_but_writes_nothing() -> None:
    ctx, fs = _make_ctx(dry_run=True)
    stages = (StageSpec(name="setup", steps=("a",), command="-tool x", standalone_stack=True),)
    manifest = _manifest_with_stages_and_stack(stages)

    arts = GeneratorService().run(ctx, manifest)
    # 3.4.0: standalone stage emits only its .stack; the aggregate is
    # still appended because generate_stack is on.
    assert tuple(a.kind for a in arts) == ("stack", "stack")
    assert not fs.exists(DOMAIN / "setup.tcl")
    assert not fs.exists(DOMAIN / "setup.stack")
    assert not fs.exists(DOMAIN / f"{DOMAIN.name}.stack")


# ------------------------------------------------------------------
# Extracted from test_small_modules_torture.py (module-aligned consolidation).
# ------------------------------------------------------------------
