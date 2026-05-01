"""Unit tests for :mod:`chopper.validator`."""

from __future__ import annotations

from pathlib import Path

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase, Severity
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import (
    CompiledManifest,
    DependencyGraph,
    Edge,
    FileProvenance,
    ProcDecision,
    StageSpec,
)
from chopper.core.models_config import BaseJson, BaseOptions, FeatureJson, FilesSection, LoadedConfig, ProjectJson
from chopper.validator import validate_post, validate_pre

DOMAIN = Path("/work/my_domain")
BACKUP = Path("/work/my_domain_backup")
AUDIT = DOMAIN / ".chopper"


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _Sink:
    def __init__(self) -> None:
        self._emissions: list[Diagnostic] = []

    def emit(self, d: Diagnostic) -> None:
        self._emissions.append(d)

    def snapshot(self) -> tuple[Diagnostic, ...]:
        return tuple(self._emissions)

    def finalize(self) -> DiagnosticSummary:
        e = sum(1 for d in self._emissions if d.severity is Severity.ERROR)
        w = sum(1 for d in self._emissions if d.severity is Severity.WARNING)
        i = sum(1 for d in self._emissions if d.severity is Severity.INFO)
        return DiagnosticSummary(errors=e, warnings=w, infos=i)


class _Progress:
    def phase_started(self, phase: Phase) -> None: ...
    def phase_done(self, phase: Phase) -> None: ...
    def step(self, message: str) -> None: ...


def _ctx(fs: InMemoryFS | None = None) -> ChopperContext:
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    return ChopperContext(config=cfg, fs=fs or InMemoryFS(), diag=_Sink(), progress=_Progress())


def _codes(ctx: ChopperContext) -> list[str]:
    return [d.code for d in ctx.diag.snapshot()]


def _base(
    *,
    path: Path = Path("/cfg/base.json"),
    domain: str = "my_domain",
    files: FilesSection | None = None,
    stages: tuple = (),
) -> BaseJson:
    return BaseJson(
        source_path=path,
        domain=domain,
        files=files or FilesSection(),
        stages=stages,
        options=BaseOptions(),
    )


# ---------------------------------------------------------------------------
# validate_pre — VI-01 empty base
# ---------------------------------------------------------------------------


def test_validate_pre_emits_vi01_for_empty_base() -> None:
    ctx = _ctx()
    loaded = LoadedConfig(base=_base())
    validate_pre(ctx, loaded)
    assert _codes(ctx) == ["VI-01"]


def test_validate_pre_skips_vi01_when_files_present() -> None:
    fs = InMemoryFS()
    fs.write_text(DOMAIN / "a.tcl", "proc x {} {}\n")
    ctx = _ctx(fs=fs)
    loaded = LoadedConfig(base=_base(files=FilesSection(include=("a.tcl",))))
    validate_pre(ctx, loaded)
    assert "VI-01" not in _codes(ctx)


# ---------------------------------------------------------------------------
# validate_pre — VE-06 literal path missing
# ---------------------------------------------------------------------------


def test_validate_pre_emits_ve06_when_literal_file_missing() -> None:
    ctx = _ctx()
    loaded = LoadedConfig(base=_base(files=FilesSection(include=("missing.tcl",))))
    validate_pre(ctx, loaded)
    assert "VE-06" in _codes(ctx)


def test_validate_pre_does_not_emit_ve06_when_file_present() -> None:
    fs = InMemoryFS()
    fs.write_text(DOMAIN / "lib/x.tcl", "proc x {} {}\n")
    ctx = _ctx(fs=fs)
    loaded = LoadedConfig(base=_base(files=FilesSection(include=("lib/x.tcl",))))
    validate_pre(ctx, loaded)
    assert "VE-06" not in _codes(ctx)


# ---------------------------------------------------------------------------
# validate_pre — VE-09 malformed glob
# ---------------------------------------------------------------------------


def test_validate_pre_emits_ve09_for_unbalanced_bracket() -> None:
    ctx = _ctx()
    loaded = LoadedConfig(base=_base(files=FilesSection(include=("lib/[abc.tcl",))))
    validate_pre(ctx, loaded)
    assert "VE-09" in _codes(ctx)


def test_validate_pre_accepts_wellformed_star_glob() -> None:
    fs = InMemoryFS()
    fs.write_text(DOMAIN / "lib/a.tcl", "proc x {} {}\n")
    ctx = _ctx(fs=fs)
    loaded = LoadedConfig(base=_base(files=FilesSection(include=("lib/*.tcl",))))
    validate_pre(ctx, loaded)
    assert "VE-09" not in _codes(ctx)


# ---------------------------------------------------------------------------
# validate_pre — VW-03 glob matches nothing
# ---------------------------------------------------------------------------


def test_validate_pre_emits_vw03_when_glob_has_no_matches() -> None:
    fs = InMemoryFS()
    # Domain exists but no *.tcl files.
    fs.mkdir(DOMAIN, parents=True, exist_ok=True)
    ctx = _ctx(fs=fs)
    loaded = LoadedConfig(base=_base(files=FilesSection(include=("*.tcl",))))
    validate_pre(ctx, loaded)
    assert "VW-03" in _codes(ctx)


def test_validate_pre_skips_vw03_when_exclude_has_no_matches() -> None:
    fs = InMemoryFS()
    fs.mkdir(DOMAIN, parents=True, exist_ok=True)
    ctx = _ctx(fs=fs)
    loaded = LoadedConfig(base=_base(files=FilesSection(exclude=("*.tcl",))))
    validate_pre(ctx, loaded)
    assert "VW-03" not in _codes(ctx)


# ---------------------------------------------------------------------------
# validate_pre — VW-04 feature domain mismatch
# ---------------------------------------------------------------------------


def test_validate_pre_emits_vw04_when_feature_domain_differs() -> None:
    ctx = _ctx()
    feature = FeatureJson(
        source_path=Path("/cfg/feat.json"),
        name="x",
        domain="other_domain",
    )
    loaded = LoadedConfig(base=_base(), features=(feature,))
    validate_pre(ctx, loaded)
    assert "VW-04" in _codes(ctx)


def test_validate_pre_skips_vw04_when_feature_domain_none() -> None:
    ctx = _ctx()
    feature = FeatureJson(
        source_path=Path("/cfg/feat.json"),
        name="x",
        domain=None,
    )
    loaded = LoadedConfig(base=_base(), features=(feature,))
    validate_pre(ctx, loaded)
    assert "VW-04" not in _codes(ctx)


# ---------------------------------------------------------------------------
# validate_pre — VE-17 / VE-18 project-level
# ---------------------------------------------------------------------------


def test_validate_pre_emits_ve17_when_project_domain_mismatch() -> None:
    ctx = _ctx()
    project = ProjectJson(
        source_path=Path("/cfg/project.json"),
        project="p",
        domain="OTHER",
        base="base.json",
    )
    loaded = LoadedConfig(base=_base(), project=project)
    validate_pre(ctx, loaded)
    assert "VE-17" in _codes(ctx)


def test_validate_pre_ve17_is_case_insensitive() -> None:
    ctx = _ctx()
    project = ProjectJson(
        source_path=Path("/cfg/project.json"),
        project="p",
        domain="MY_DOMAIN",
        base="base.json",
    )
    loaded = LoadedConfig(base=_base(), project=project)
    validate_pre(ctx, loaded)
    assert "VE-17" not in _codes(ctx)


def test_validate_pre_emits_ve18_for_duplicate_feature_path() -> None:
    ctx = _ctx()
    project = ProjectJson(
        source_path=Path("/cfg/project.json"),
        project="p",
        domain="my_domain",
        base="base.json",
        features=("features/a.json", "features/a.json"),
    )
    loaded = LoadedConfig(base=_base(), project=project)
    validate_pre(ctx, loaded)
    assert "VE-18" in _codes(ctx)


# ---------------------------------------------------------------------------
# validate_post — VE-16 brace imbalance
# ---------------------------------------------------------------------------


def _make_manifest(
    files: dict[Path, FileTreatment] | None = None,
    procs: dict[str, ProcDecision] | None = None,
    stages: tuple[StageSpec, ...] = (),
) -> CompiledManifest:
    files = files or {}
    procs = procs or {}
    provenance = {
        p: FileProvenance(path=p, treatment=t, reason="fi-literal")
        for p, t in sorted(files.items(), key=lambda kv: kv[0].as_posix())
    }
    return CompiledManifest(
        file_decisions={p: files[p] for p in sorted(files, key=lambda x: x.as_posix())},
        proc_decisions={k: procs[k] for k in sorted(procs)},
        provenance=provenance,
        stages=stages,
    )


def _empty_graph() -> DependencyGraph:
    return DependencyGraph(pi_seeds=(), nodes=(), pt=(), edges=(), reachable_from_includes=frozenset())


def test_validate_post_emits_ve16_on_brace_imbalance() -> None:
    fs = InMemoryFS()
    bad = DOMAIN / "bad.tcl"
    fs.write_text(bad, "proc x {} { set a 1 \n")  # unmatched `{`
    ctx = _ctx(fs=fs)
    validate_post(ctx, _make_manifest(), _empty_graph(), rewritten=(bad,))
    assert "VE-16" in _codes(ctx)


def test_validate_post_skips_ve16_when_balanced() -> None:
    fs = InMemoryFS()
    good = DOMAIN / "good.tcl"
    fs.write_text(good, "proc x {} { set a 1 }\n")
    ctx = _ctx(fs=fs)
    validate_post(ctx, _make_manifest(), _empty_graph(), rewritten=(good,))
    assert "VE-16" not in _codes(ctx)


def test_validate_post_ignores_escaped_braces() -> None:
    fs = InMemoryFS()
    good = DOMAIN / "esc.tcl"
    fs.write_text(good, "proc x {} { set a \\{ }\n")
    ctx = _ctx(fs=fs)
    validate_post(ctx, _make_manifest(), _empty_graph(), rewritten=(good,))
    assert "VE-16" not in _codes(ctx)


# ---------------------------------------------------------------------------
# validate_post — VW-05 / VW-06 dangling refs
# ---------------------------------------------------------------------------


def test_validate_post_emits_vw05_for_call_into_removed_proc() -> None:
    caller = "a.tcl::foo"
    removed = "a.tcl::gone"
    manifest = _make_manifest(
        files={Path("a.tcl"): FileTreatment.FULL_COPY},
        procs={
            caller: ProcDecision(
                canonical_name=caller,
                source_file=Path("a.tcl"),
                selection_source="base:files.include",
            )
        },
    )
    edge = Edge(
        caller=caller,
        callee=removed,
        kind="proc_call",
        status="resolved",
        token="gone",
        line=5,
    )
    graph = DependencyGraph(
        pi_seeds=(caller,),
        nodes=(caller,),
        pt=(),
        edges=(edge,),
        reachable_from_includes=frozenset({caller}),
    )
    ctx = _ctx()
    validate_post(ctx, manifest, graph, rewritten=())
    assert "VW-05" in _codes(ctx)


def test_validate_post_emits_vw06_for_source_into_removed_file() -> None:
    caller = "a.tcl::foo"
    manifest = _make_manifest(
        files={Path("a.tcl"): FileTreatment.FULL_COPY},
        procs={
            caller: ProcDecision(
                canonical_name=caller,
                source_file=Path("a.tcl"),
                selection_source="base:files.include",
            )
        },
    )
    edge = Edge(
        caller=caller,
        callee="lib/missing.tcl",
        kind="source",
        status="resolved",
        token="source lib/missing.tcl",
        line=3,
    )
    graph = DependencyGraph(
        pi_seeds=(caller,),
        nodes=(caller,),
        pt=(),
        edges=(edge,),
        reachable_from_includes=frozenset({caller}),
    )
    ctx = _ctx()
    validate_post(ctx, manifest, graph, rewritten=())
    assert "VW-06" in _codes(ctx)


def test_validate_post_vw05_carries_caller_path() -> None:
    """Bug ``diagnostics_file_null_for_p4_p6.md``: VW-05/VW-06 had ``file: null``.

    The fix populates ``Diagnostic.path`` from the caller's source file
    recovered from the canonical name. The audit JSON ``file`` field is
    now a real domain-relative POSIX path, not None.
    """
    caller = "a.tcl::foo"
    removed = "a.tcl::gone"
    manifest = _make_manifest(
        files={Path("a.tcl"): FileTreatment.FULL_COPY},
        procs={
            caller: ProcDecision(
                canonical_name=caller,
                source_file=Path("a.tcl"),
                selection_source="base:files.include",
            )
        },
    )
    edge = Edge(
        caller=caller,
        callee=removed,
        kind="proc_call",
        status="resolved",
        token="gone",
        line=5,
    )
    graph = DependencyGraph(
        pi_seeds=(caller,),
        nodes=(caller,),
        pt=(),
        edges=(edge,),
        reachable_from_includes=frozenset({caller}),
    )
    ctx = _ctx()
    validate_post(ctx, manifest, graph, rewritten=())
    vw05 = [d for d in ctx.diag.snapshot() if d.code == "VW-05"]
    assert vw05, "expected at least one VW-05 emission"
    assert vw05[0].path == Path("a.tcl"), f"VW-05 must carry caller's source file, got {vw05[0].path!r}"


def test_validate_post_ignores_unresolved_edges() -> None:
    caller = "a.tcl::foo"
    manifest = _make_manifest(
        files={Path("a.tcl"): FileTreatment.FULL_COPY},
        procs={
            caller: ProcDecision(
                canonical_name=caller,
                source_file=Path("a.tcl"),
                selection_source="base:files.include",
            )
        },
    )
    edge = Edge(
        caller=caller,
        callee="",
        kind="proc_call",
        status="unresolved",
        token="mystery",
        line=2,
        diagnostic_code="TW-02",
    )
    graph = DependencyGraph(
        pi_seeds=(caller,),
        nodes=(caller,),
        pt=(),
        edges=(edge,),
        reachable_from_includes=frozenset({caller}),
    )
    ctx = _ctx()
    validate_post(ctx, manifest, graph, rewritten=())
    assert "VW-05" not in _codes(ctx)


# ---------------------------------------------------------------------------
# validate_post — F3 cross-validate (VW-14/15/16/17)
# ---------------------------------------------------------------------------


def _stage(*, steps: tuple[str, ...]) -> StageSpec:
    return StageSpec(name="synth", load_from="base", steps=steps)


def test_validate_post_emits_vw14_for_missing_step_file() -> None:
    manifest = _make_manifest(stages=(_stage(steps=("missing.tcl",)),))
    ctx = _ctx()
    validate_post(ctx, manifest, _empty_graph(), rewritten=())
    assert "VW-14" in _codes(ctx)


def test_validate_post_accepts_present_step_file() -> None:
    step = Path("present.tcl")
    manifest = _make_manifest(
        files={step: FileTreatment.FULL_COPY},
        stages=(_stage(steps=("present.tcl",)),),
    )
    ctx = _ctx()
    validate_post(ctx, manifest, _empty_graph(), rewritten=())
    assert "VW-14" not in _codes(ctx)


def test_validate_post_emits_vw15_for_missing_proc_step() -> None:
    manifest = _make_manifest(stages=(_stage(steps=("run_flow",)),))
    ctx = _ctx()
    validate_post(ctx, manifest, _empty_graph(), rewritten=())
    assert "VW-15" in _codes(ctx)


def test_validate_post_accepts_present_proc_step() -> None:
    cn = "a.tcl::run_flow"
    manifest = _make_manifest(
        files={Path("a.tcl"): FileTreatment.FULL_COPY},
        procs={cn: ProcDecision(cn, Path("a.tcl"), "base:procedures.include")},
        stages=(_stage(steps=("run_flow",)),),
    )
    ctx = _ctx()
    validate_post(ctx, manifest, _empty_graph(), rewritten=())
    assert "VW-15" not in _codes(ctx)


def test_validate_post_emits_vw16_for_source_cmd_missing_target() -> None:
    manifest = _make_manifest(stages=(_stage(steps=("source lib/missing.tcl",)),))
    ctx = _ctx()
    validate_post(ctx, manifest, _empty_graph(), rewritten=())
    assert "VW-16" in _codes(ctx)


def test_validate_post_emits_vw17_for_external_path() -> None:
    manifest = _make_manifest(stages=(_stage(steps=("/abs/path/script.tcl",)),))
    ctx = _ctx()
    validate_post(ctx, manifest, _empty_graph(), rewritten=())
    assert "VW-17" in _codes(ctx)


def test_validate_post_vw17_triggers_for_dotdot_path() -> None:
    manifest = _make_manifest(stages=(_stage(steps=("../elsewhere/x.tcl",)),))
    ctx = _ctx()
    validate_post(ctx, manifest, _empty_graph(), rewritten=())
    assert "VW-17" in _codes(ctx)


# ---------------------------------------------------------------------------
# Issue #8 regression — VW-06 false positive for bare filenames in source
# ---------------------------------------------------------------------------


def _source_edge(caller: str, callee: str) -> Edge:
    return Edge(
        caller=caller,
        callee=callee,
        kind="source",
        status="resolved",
        token=f"source {callee}",
        line=10,
    )


def test_vw06_not_emitted_when_bare_filename_matches_surviving_subdir_file() -> None:
    """Regression for #8: ``source write_power_reports.tcl`` must not produce
    VW-06 when ``onepower/write_power_reports.tcl`` is in the active selection.

    The post-trim validator used to compare ``write_power_reports.tcl``
    literally against the set of domain-relative surviving paths and always
    missed the match.
    """
    caller = "onepower/run_quality.tcl::post_checker"
    manifest = _make_manifest(
        files={
            Path("onepower/run_quality.tcl"): FileTreatment.FULL_COPY,
            Path("onepower/write_power_reports.tcl"): FileTreatment.FULL_COPY,
        },
        procs={
            caller: ProcDecision(
                canonical_name=caller,
                source_file=Path("onepower/run_quality.tcl"),
                selection_source="base:files.include",
            )
        },
    )
    # The Tcl source token uses the bare filename, not the full path.
    edge = _source_edge(caller, "write_power_reports.tcl")
    graph = DependencyGraph(
        pi_seeds=(caller,),
        nodes=(caller,),
        pt=(),
        edges=(edge,),
        reachable_from_includes=frozenset({caller}),
    )
    ctx = _ctx()
    validate_post(ctx, manifest, graph, rewritten=())
    assert "VW-06" not in _codes(ctx), (
        "VW-06 must not fire when the bare filename suffix-matches a surviving domain-relative path"
    )


def test_vw06_not_emitted_when_bare_filename_matches_nested_subdir_file() -> None:
    """Bare filename ``default_report_list.tcl`` must match
    ``onepower/default_reports/default_report_list.tcl`` (two levels deep).
    """
    caller = "onepower/write_power_reports.tcl::get_list_of_reports"
    manifest = _make_manifest(
        files={
            Path("onepower/write_power_reports.tcl"): FileTreatment.FULL_COPY,
            Path("onepower/default_reports/default_report_list.tcl"): FileTreatment.FULL_COPY,
        },
        procs={
            caller: ProcDecision(
                canonical_name=caller,
                source_file=Path("onepower/write_power_reports.tcl"),
                selection_source="base:files.include",
            )
        },
    )
    edge = _source_edge(caller, "default_report_list.tcl")
    graph = DependencyGraph(
        pi_seeds=(caller,),
        nodes=(caller,),
        pt=(),
        edges=(edge,),
        reachable_from_includes=frozenset({caller}),
    )
    ctx = _ctx()
    validate_post(ctx, manifest, graph, rewritten=())
    assert "VW-06" not in _codes(ctx), "VW-06 must not fire when the bare filename matches a nested surviving path"


def test_vw06_still_emitted_when_bare_filename_is_genuinely_missing() -> None:
    """VW-06 must still fire when the sourced file is truly absent from the
    surviving set (not a false positive suppression regression).
    """
    caller = "a.tcl::foo"
    manifest = _make_manifest(
        files={Path("a.tcl"): FileTreatment.FULL_COPY},
        procs={
            caller: ProcDecision(
                canonical_name=caller,
                source_file=Path("a.tcl"),
                selection_source="base:files.include",
            )
        },
    )
    edge = _source_edge(caller, "genuinely_removed.tcl")
    graph = DependencyGraph(
        pi_seeds=(caller,),
        nodes=(caller,),
        pt=(),
        edges=(edge,),
        reachable_from_includes=frozenset({caller}),
    )
    ctx = _ctx()
    validate_post(ctx, manifest, graph, rewritten=())
    assert "VW-06" in _codes(ctx), "VW-06 must still fire for a file not in the surviving set"
