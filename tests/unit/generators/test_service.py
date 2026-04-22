"""Unit tests for :mod:`chopper.generators`."""

from __future__ import annotations

from pathlib import Path

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models import CompiledManifest, FileProvenance, FileTreatment, StageSpec
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


# ---------------------------------------------------------------------------
# stage_emitter
# ---------------------------------------------------------------------------


def test_emit_stage_tcl_preserves_steps_verbatim() -> None:
    stage = StageSpec(name="setup", steps=("puts hi", "puts {world}"))
    art = emit_stage_tcl(stage)
    assert art.path == Path("setup.tcl")
    assert art.kind == "tcl"
    assert art.source_stage == "setup"
    # Banner then steps, trailing newline.
    lines = art.content.splitlines()
    assert lines[0].startswith("# Chopper-generated")
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
