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
from chopper.core.models_trimmer import FileOutcome, TrimReport
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


class _StatFailFS(InMemoryFS):
    def __init__(self, files: dict[Path, str], failing_path: Path) -> None:
        super().__init__(files)
        self._failing_path = failing_path

    def stat(self, path: Path):  # type: ignore[no-untyped-def]
        if path == self._failing_path:
            raise OSError("metadata unavailable")
        return super().stat(path)


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


def test_validate_pre_accepts_literal_file_present_in_backup_for_rerun() -> None:
    fs = InMemoryFS()
    fs.mkdir(DOMAIN, parents=True, exist_ok=True)
    fs.write_text(BACKUP / "extra_utils.tcl", "proc extra {} {}\n")
    ctx = _ctx(fs=fs)
    loaded = LoadedConfig(base=_base(files=FilesSection(include=("extra_utils.tcl",))))

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


def test_validate_pre_glob_matches_backup_for_rerun() -> None:
    fs = InMemoryFS()
    fs.mkdir(DOMAIN, parents=True, exist_ok=True)
    fs.write_text(BACKUP / "lib/a.tcl", "proc x {} {}\n")
    ctx = _ctx(fs=fs)
    loaded = LoadedConfig(base=_base(files=FilesSection(include=("lib/*.tcl",))))

    validate_pre(ctx, loaded)

    assert "VW-03" not in _codes(ctx)


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


def test_validate_pre_ve17_uses_domain_root_basename_not_cwd(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """VE-17 compares against ``RunConfig.domain_root.name`` (per
    ``technical_docs/ARCHITECTURE.md`` §5.1), never against
    ``Path.cwd().name``.

    Construct a context whose ``domain_root.name == 'my_domain'`` and
    chdir the test process into an unrelated directory. The project
    JSON declaring ``domain == 'my_domain'`` must NOT trigger VE-17 —
    the cwd basename is irrelevant.
    """
    elsewhere = tmp_path / "not_the_domain"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    ctx = _ctx()  # domain_root is /work/my_domain, set above.
    project = ProjectJson(
        source_path=Path("/cfg/project.json"),
        project="p",
        domain="my_domain",
        base="base.json",
    )
    loaded = LoadedConfig(base=_base(), project=project)
    validate_pre(ctx, loaded)
    assert "VE-17" not in _codes(ctx), (
        f"VE-17 must not depend on cwd; only domain_root.name should matter. Codes: {_codes(ctx)}"
    )


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


def _make_trim_report(*outcomes: FileOutcome) -> TrimReport:
    ordered = tuple(sorted(outcomes, key=lambda outcome: outcome.path.as_posix()))
    return TrimReport(
        outcomes=ordered,
        files_copied=sum(1 for outcome in ordered if outcome.treatment is FileTreatment.FULL_COPY),
        files_trimmed=sum(1 for outcome in ordered if outcome.treatment is FileTreatment.PROC_TRIM),
        files_removed=sum(1 for outcome in ordered if outcome.treatment is FileTreatment.REMOVE),
        procs_kept_total=sum(len(outcome.procs_kept) for outcome in ordered),
        procs_removed_total=sum(len(outcome.procs_removed) for outcome in ordered),
    )


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


def test_validate_post_emits_vw10_when_live_output_missing() -> None:
    rel = Path("copied.tcl")
    outcome = FileOutcome(
        path=rel,
        treatment=FileTreatment.FULL_COPY,
        bytes_in=12,
        bytes_out=12,
        procs_kept=(),
        procs_removed=(),
    )
    ctx = _ctx()
    manifest = _make_manifest(files={rel: FileTreatment.FULL_COPY})

    validate_post(ctx, manifest, _empty_graph(), rewritten=(), trim_report=_make_trim_report(outcome))
    assert "VW-10" in _codes(ctx)


def test_validate_post_emits_vw10_when_live_output_size_mismatches() -> None:
    fs = InMemoryFS()
    rel = Path("trimmed.tcl")
    fs.write_text(DOMAIN / rel, "short\n")
    outcome = FileOutcome(
        path=rel,
        treatment=FileTreatment.PROC_TRIM,
        bytes_in=20,
        bytes_out=99,
        procs_kept=("trimmed.tcl::keep_me",),
        procs_removed=("trimmed.tcl::drop_me",),
    )
    ctx = _ctx(fs=fs)
    validate_post(
        ctx, _make_manifest(), _empty_graph(), rewritten=(DOMAIN / rel,), trim_report=_make_trim_report(outcome)
    )
    assert "VW-10" in _codes(ctx)


def test_validate_post_emits_vw10_when_rewritten_proc_set_mismatches() -> None:
    fs = InMemoryFS()
    rel = Path("trimmed.tcl")
    fs.write_text(
        DOMAIN / rel,
        "proc keep_me {} { return ok }\nproc stray {} { return nope }\n",
    )
    keep = "trimmed.tcl::keep_me"
    manifest = _make_manifest(
        files={rel: FileTreatment.PROC_TRIM},
        procs={keep: ProcDecision(canonical_name=keep, source_file=rel, selection_source="base:procedures.include")},
    )
    outcome = FileOutcome(
        path=rel,
        treatment=FileTreatment.PROC_TRIM,
        bytes_in=64,
        bytes_out=len(b"proc keep_me {} { return ok }\nproc stray {} { return nope }\n"),
        procs_kept=(keep,),
        procs_removed=("trimmed.tcl::drop_me",),
    )
    ctx = _ctx(fs=fs)
    validate_post(ctx, manifest, _empty_graph(), rewritten=(DOMAIN / rel,), trim_report=_make_trim_report(outcome))
    assert "VW-10" in _codes(ctx)


def test_validate_post_skips_vw10_when_rewritten_proc_set_matches() -> None:
    fs = InMemoryFS()
    rel = Path("trimmed_ok.tcl")
    text = "proc keep_me {} { return ok }\n"
    fs.write_text(DOMAIN / rel, text)
    keep = "trimmed_ok.tcl::keep_me"
    manifest = _make_manifest(
        files={rel: FileTreatment.PROC_TRIM},
        procs={keep: ProcDecision(canonical_name=keep, source_file=rel, selection_source="base:procedures.include")},
    )
    outcome = FileOutcome(
        path=rel,
        treatment=FileTreatment.PROC_TRIM,
        bytes_in=len(text.encode("utf-8")),
        bytes_out=len(text.encode("utf-8")),
        procs_kept=(keep,),
        procs_removed=("trimmed_ok.tcl::drop_me",),
    )
    ctx = _ctx(fs=fs)
    validate_post(ctx, manifest, _empty_graph(), rewritten=(DOMAIN / rel,), trim_report=_make_trim_report(outcome))
    assert "VW-10" not in _codes(ctx)


def test_validate_post_emits_vw10_when_manifest_outcome_missing() -> None:
    manifest = _make_manifest(files={Path("must_exist.tcl"): FileTreatment.FULL_COPY})
    ctx = _ctx()
    validate_post(ctx, manifest, _empty_graph(), rewritten=(), trim_report=_make_trim_report())
    assert "VW-10" in _codes(ctx)


def test_validate_post_emits_vw10_when_manifest_treatment_mismatches_trim_report() -> None:
    fs = InMemoryFS()
    rel = Path("mismatch.tcl")
    fs.write_text(DOMAIN / rel, "proc p {} { return 1 }\n")
    manifest = _make_manifest(files={rel: FileTreatment.REMOVE})
    outcome = FileOutcome(
        path=rel,
        treatment=FileTreatment.FULL_COPY,
        bytes_in=24,
        bytes_out=24,
        procs_kept=(),
        procs_removed=(),
    )
    ctx = _ctx(fs=fs)
    validate_post(ctx, manifest, _empty_graph(), rewritten=(), trim_report=_make_trim_report(outcome))
    assert "VW-10" in _codes(ctx)


def test_validate_post_emits_vw10_when_manifest_proc_set_mismatches_trim_report() -> None:
    rel = Path("proc_mismatch.tcl")
    keep = "proc_mismatch.tcl::keep_me"
    manifest = _make_manifest(
        files={rel: FileTreatment.PROC_TRIM},
        procs={keep: ProcDecision(canonical_name=keep, source_file=rel, selection_source="base:procedures.include")},
    )
    outcome = FileOutcome(
        path=rel,
        treatment=FileTreatment.PROC_TRIM,
        bytes_in=10,
        bytes_out=10,
        procs_kept=(),
        procs_removed=(),
    )
    ctx = _ctx()
    validate_post(ctx, manifest, _empty_graph(), rewritten=(), trim_report=_make_trim_report(outcome))
    assert "VW-10" in _codes(ctx)


def test_validate_post_emits_vw10_when_removed_file_still_present() -> None:
    fs = InMemoryFS()
    rel = Path("should_be_removed.tcl")
    fs.write_text(DOMAIN / rel, "proc keep {} { return ok }\n")
    outcome = FileOutcome(
        path=rel,
        treatment=FileTreatment.REMOVE,
        bytes_in=10,
        bytes_out=0,
        procs_kept=(),
        procs_removed=(),
    )
    ctx = _ctx(fs=fs)
    manifest = _make_manifest(files={rel: FileTreatment.REMOVE})

    validate_post(ctx, manifest, _empty_graph(), rewritten=(), trim_report=_make_trim_report(outcome))
    assert "VW-10" in _codes(ctx)


def test_validate_post_emits_vw10_when_live_output_stat_fails() -> None:
    rel = Path("copied.tcl")
    fs = _StatFailFS({DOMAIN / rel: "proc p {} {}\n"}, DOMAIN / rel)
    outcome = FileOutcome(
        path=rel,
        treatment=FileTreatment.FULL_COPY,
        bytes_in=13,
        bytes_out=13,
        procs_kept=(),
        procs_removed=(),
    )
    ctx = _ctx(fs=fs)
    manifest = _make_manifest(files={rel: FileTreatment.FULL_COPY})

    validate_post(ctx, manifest, _empty_graph(), rewritten=(), trim_report=_make_trim_report(outcome))

    vw10 = [d for d in ctx.diag.snapshot() if d.code == "VW-10"]
    assert vw10
    assert vw10[0].context["reason"] == "stat-failed"


def test_validate_post_emits_vw10_when_live_output_is_directory() -> None:
    rel = Path("copied.tcl")
    fs = InMemoryFS()
    fs.mkdir(DOMAIN / rel, parents=True, exist_ok=True)
    outcome = FileOutcome(
        path=rel,
        treatment=FileTreatment.FULL_COPY,
        bytes_in=13,
        bytes_out=13,
        procs_kept=(),
        procs_removed=(),
    )
    ctx = _ctx(fs=fs)
    manifest = _make_manifest(files={rel: FileTreatment.FULL_COPY})

    validate_post(ctx, manifest, _empty_graph(), rewritten=(), trim_report=_make_trim_report(outcome))

    vw10 = [d for d in ctx.diag.snapshot() if d.code == "VW-10"]
    assert vw10
    assert vw10[0].context["reason"] == "is-dir"


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


def test_validate_post_ignores_resolved_call_from_removed_caller() -> None:
    graph = DependencyGraph(
        pi_seeds=("removed.tcl::caller",),
        nodes=("removed.tcl::caller",),
        pt=(),
        edges=(
            Edge(
                caller="removed.tcl::caller",
                callee="removed.tcl::callee",
                kind="proc_call",
                status="resolved",
                token="callee",
                line=1,
            ),
        ),
        reachable_from_includes=frozenset({"removed.tcl::caller"}),
    )
    ctx = _ctx()

    validate_post(ctx, _make_manifest(), graph, rewritten=())

    assert "VW-05" not in _codes(ctx)


def test_validate_post_accepts_resolved_call_to_surviving_proc() -> None:
    caller = "a.tcl::caller"
    callee = "a.tcl::callee"
    manifest = _make_manifest(
        files={Path("a.tcl"): FileTreatment.FULL_COPY},
        procs={
            caller: ProcDecision(caller, Path("a.tcl"), "base:procedures.include"),
            callee: ProcDecision(callee, Path("a.tcl"), "base:procedures.include"),
        },
    )
    graph = DependencyGraph(
        pi_seeds=(caller,),
        nodes=(callee, caller),
        pt=(callee,),
        edges=(Edge(caller=caller, callee=callee, kind="proc_call", status="resolved", token="callee", line=3),),
        reachable_from_includes=frozenset({caller, callee}),
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


def test_validate_post_accepts_source_cmd_existing_target() -> None:
    manifest = _make_manifest(
        files={Path("lib/present.tcl"): FileTreatment.FULL_COPY},
        stages=(_stage(steps=("source lib/present.tcl",)),),
    )
    ctx = _ctx()

    validate_post(ctx, manifest, _empty_graph(), rewritten=())

    assert "VW-16" not in _codes(ctx)


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


def test_validate_post_vw17_triggers_for_drive_letter_path() -> None:
    manifest = _make_manifest(stages=(_stage(steps=("C:/eda/script.tcl",)),))
    ctx = _ctx()

    validate_post(ctx, manifest, _empty_graph(), rewritten=())

    assert "VW-17" in _codes(ctx)


def test_validate_post_ignores_blank_and_comment_stage_steps() -> None:
    manifest = _make_manifest(stages=(_stage(steps=("", "   ", "# comment")),))
    ctx = _ctx()

    validate_post(ctx, manifest, _empty_graph(), rewritten=())

    assert not any(code in _codes(ctx) for code in ("VW-14", "VW-15", "VW-16", "VW-17"))


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
