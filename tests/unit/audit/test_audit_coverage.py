"""Coverage tests: exercise the rich-record paths through audit writers."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from chopper.adapters.fs_memory import InMemoryFS
from chopper.audit import AuditService
from chopper.audit.writers import (
    render_compiled_manifest,
    render_dependency_graph,
    render_trim_report_json,
    render_trim_report_txt,
    render_trim_stats,
)
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase, Severity
from chopper.core.models import (
    CompiledManifest,
    DependencyGraph,
    Edge,
    FileOutcome,
    FileProvenance,
    FileTreatment,
    ParsedFile,
    ParseResult,
    ProcDecision,
    ProcEntry,
    RunRecord,
    StageSpec,
    TrimReport,
)

DOMAIN = Path("/work/dd")
BACKUP = Path("/work/dd_backup")
AUDIT = DOMAIN / ".chopper"


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


def _ctx(*, dry_run: bool = False, fs: InMemoryFS | None = None) -> ChopperContext:
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=dry_run)
    return ChopperContext(config=cfg, fs=fs or InMemoryFS(), diag=_Sink(), progress=_Progress())


def _build_rich_record() -> RunRecord:
    """Full pipeline record with every optional field populated."""

    p_full = Path("lib/full.tcl")
    p_trim = Path("lib/trim.tcl")
    p_gen = Path("synth.tcl")

    # ParseResult: two files, one proc each.
    proc_full = ProcEntry(
        canonical_name=f"{p_full.as_posix()}::kept_a",
        short_name="kept_a",
        qualified_name="kept_a",
        source_file=p_full,
        start_line=1,
        end_line=3,
        body_start_line=2,
        body_end_line=3,
        namespace_path="::",
    )
    proc_trim_keep = ProcEntry(
        canonical_name=f"{p_trim.as_posix()}::kept_b",
        short_name="kept_b",
        qualified_name="kept_b",
        source_file=p_trim,
        start_line=1,
        end_line=3,
        body_start_line=2,
        body_end_line=3,
        namespace_path="::",
    )
    proc_trim_drop = ProcEntry(
        canonical_name=f"{p_trim.as_posix()}::drop_c",
        short_name="drop_c",
        qualified_name="drop_c",
        source_file=p_trim,
        start_line=5,
        end_line=7,
        body_start_line=6,
        body_end_line=7,
        namespace_path="::",
    )
    pf_full = ParsedFile(path=p_full, procs=(proc_full,), encoding="utf-8")
    pf_trim = ParsedFile(path=p_trim, procs=(proc_trim_keep, proc_trim_drop), encoding="utf-8")
    parsed = ParseResult(
        files={p_full: pf_full, p_trim: pf_trim},
        index={
            proc_full.canonical_name: proc_full,
            proc_trim_drop.canonical_name: proc_trim_drop,
            proc_trim_keep.canonical_name: proc_trim_keep,
        },
    )

    # Manifest with FULL_COPY + PROC_TRIM + GENERATED + REMOVE.
    p_rem = Path("obsolete.tcl")
    provenance = {
        p_full: FileProvenance(
            path=p_full,
            treatment=FileTreatment.FULL_COPY,
            reason="fi-literal",
            input_sources=("base:files.include",),
        ),
        p_trim: FileProvenance(
            path=p_trim,
            treatment=FileTreatment.PROC_TRIM,
            reason="pi-additive",
            input_sources=("base:procedures.include",),
            proc_model="additive",
        ),
        p_rem: FileProvenance(
            path=p_rem,
            treatment=FileTreatment.REMOVE,
            reason="default-exclude",
        ),
        p_gen: FileProvenance(
            path=p_gen,
            treatment=FileTreatment.GENERATED,
            reason="fi-literal",
            input_sources=("base:stages",),
        ),
    }
    manifest = CompiledManifest(
        file_decisions={
            p_full: FileTreatment.FULL_COPY,
            p_trim: FileTreatment.PROC_TRIM,
            p_rem: FileTreatment.REMOVE,
            p_gen: FileTreatment.GENERATED,
        },
        proc_decisions={
            proc_full.canonical_name: ProcDecision(
                canonical_name=proc_full.canonical_name,
                source_file=p_full,
                selection_source="base:files.include",
            ),
            proc_trim_keep.canonical_name: ProcDecision(
                canonical_name=proc_trim_keep.canonical_name,
                source_file=p_trim,
                selection_source="base:procedures.include",
            ),
        },
        provenance=provenance,
        stages=(
            StageSpec(
                name="synth",
                load_from="base",
                steps=("do_synth",),
                dependencies=(),
                exit_codes=(0,),
                command="tclsh",
                inputs=(),
                outputs=(),
                run_mode="serial",
                language="tcl",
            ),
        ),
    )

    # DependencyGraph: one resolved edge + one unresolved.
    edge_resolved = Edge(
        caller=proc_full.canonical_name,
        callee=proc_trim_keep.canonical_name,
        kind="proc_call",
        status="resolved",
        token="kept_b",
        line=2,
    )
    edge_unresolved = Edge(
        caller=proc_full.canonical_name,
        callee="",
        kind="proc_call",
        status="unresolved",
        token="mystery",
        line=3,
        diagnostic_code="TW-01",
    )
    seeds = (proc_full.canonical_name, proc_trim_keep.canonical_name)
    nodes_sorted = tuple(sorted(seeds))
    graph = DependencyGraph(
        pi_seeds=nodes_sorted,
        nodes=nodes_sorted,
        pt=(),
        edges=tuple(
            sorted(
                (edge_resolved, edge_unresolved),
                key=lambda e: (e.caller, e.kind, e.line, e.token, e.callee),
            )
        ),
        reachable_from_includes=frozenset(nodes_sorted),
        unresolved_tokens=((proc_full.canonical_name, "mystery", 3, "TW-01"),),
    )

    # TrimReport.
    outcome_full = FileOutcome(
        path=p_full,
        treatment=FileTreatment.FULL_COPY,
        bytes_in=100,
        bytes_out=100,
        procs_kept=(proc_full.canonical_name,),
        procs_removed=(),
    )
    outcome_trim = FileOutcome(
        path=p_trim,
        treatment=FileTreatment.PROC_TRIM,
        bytes_in=200,
        bytes_out=150,
        procs_kept=(proc_trim_keep.canonical_name,),
        procs_removed=(proc_trim_drop.canonical_name,),
    )
    outcome_rem = FileOutcome(
        path=p_rem,
        treatment=FileTreatment.REMOVE,
        bytes_in=50,
        bytes_out=0,
        procs_kept=(),
        procs_removed=(),
    )
    outcomes = tuple(sorted((outcome_full, outcome_trim, outcome_rem), key=lambda o: o.path.as_posix()))
    trim_report = TrimReport(
        outcomes=outcomes,
        files_copied=1,
        files_trimmed=1,
        files_removed=1,
        procs_kept_total=2,
        procs_removed_total=1,
    )

    t0 = datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)
    return RunRecord(
        run_id="rich-run-id-aaaabbbbccccd",
        command="trim",
        started_at=t0,
        ended_at=t0 + timedelta(seconds=12),
        exit_code=0,
        parsed=parsed,
        manifest=manifest,
        graph=graph,
        trim_report=trim_report,
    )


def test_compiled_manifest_includes_proc_trim_surviving_procs() -> None:
    record = _build_rich_record()
    _name, content = render_compiled_manifest(record)
    payload = json.loads(content)
    trim_entry = next(f for f in payload["files"] if f["path"] == "lib/trim.tcl")
    assert trim_entry["treatment"] == "proc-trim"
    assert trim_entry["surviving_procs"] == ["lib/trim.tcl::kept_b"]
    # full-copy has None surviving_procs
    full_entry = next(f for f in payload["files"] if f["path"] == "lib/full.tcl")
    assert full_entry["surviving_procs"] is None


def test_dependency_graph_renders_resolved_and_unresolved() -> None:
    record = _build_rich_record()
    _name, content = render_dependency_graph(record)
    payload = json.loads(content)
    assert len(payload["edges"]) == 2
    assert {e["status"] for e in payload["edges"]} == {"resolved", "unresolved"}
    assert payload["unresolved"] == [
        {
            "token": "mystery",
            "caller": "lib/full.tcl::kept_a",
            "line": 3,
            "reason": "no-in-domain-match",
            "diagnostic_code": "TW-01",
        }
    ]


def test_trim_report_json_populates_summary_and_reports() -> None:
    ctx = _ctx()
    record = _build_rich_record()
    _name, content = render_trim_report_json(ctx, record)
    payload = json.loads(content)
    assert payload["summary"]["total_domain_files"] == 2
    assert payload["summary"]["procs_removed"] == 1
    assert len(payload["file_report"]) == 4
    assert len(payload["proc_report"]) == 2


def test_trim_report_txt_emits_treatment_breakdown_and_dry_run_notice() -> None:
    fs = InMemoryFS()
    ctx = _ctx(dry_run=True, fs=fs)
    ctx.diag.emit(Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="bad thing", path=Path("x.tcl"), line_no=4))
    record = _build_rich_record()
    _name, content = render_trim_report_txt(ctx, record)
    assert "full-copy" in content and ": 1" in content
    assert "proc-trim" in content
    assert "Errors (1)" in content
    assert "(no files were modified)" in content


def test_trim_stats_reflects_rich_record_with_fs_reads() -> None:
    fs = InMemoryFS()
    # After-tree: write surviving files under domain_root.
    fs.write_text(DOMAIN / "lib/full.tcl", "proc kept_a {} { return 1 }\n")
    fs.write_text(DOMAIN / "lib/trim.tcl", "proc kept_b {} { return 2 }\n")
    fs.write_text(DOMAIN / "synth.tcl", "# generated\nsource lib/trim.tcl\n")
    # Before-tree: first-trim means parsed files read from domain too.
    # Both trim.tcl versions differ (before has drop_c too).
    # We reuse the same file tree for this test — the point is that the reader branch executes.
    ctx = _ctx(fs=fs)
    record = _build_rich_record()
    _name, content = render_trim_stats(ctx, record)
    payload = json.loads(content)
    assert payload["files_before"] == 2
    # full, proc-trim, generated all count (REMOVE excluded).
    assert payload["files_after"] == 3
    assert payload["procs_before"] == 3
    assert payload["procs_after"] == 2
    assert payload["trim_ratio_files"] > 0


def test_audit_service_end_to_end_writes_full_bundle() -> None:
    fs = InMemoryFS()
    fs.write_text(DOMAIN / "lib/full.tcl", "proc kept_a {} { return 1 }\n")
    fs.write_text(DOMAIN / "lib/trim.tcl", "proc kept_b {} { return 2 }\n")
    fs.write_text(DOMAIN / "synth.tcl", "# generated\n")
    ctx = _ctx(fs=fs)
    ctx.diag.emit(Diagnostic.build("VW-05", phase=Phase.P6_POSTVALIDATE, message="mild warning"))
    record = _build_rich_record()
    manifest = AuditService().run(ctx, record)

    names = [a.name for a in manifest.artifacts]
    for required in (
        "chopper_run.json",
        "compiled_manifest.json",
        "dependency_graph.json",
        "diagnostics.json",
        "run_id",
        "trim_report.json",
        "trim_report.txt",
        "trim_stats.json",
    ):
        assert required in names

    # diagnostic_counts reflects the sink.
    assert manifest.diagnostic_counts == {"error": 0, "warning": 1, "info": 0}

    # chopper_run.json records every other artifact.
    chopper_run = json.loads(fs.read_text(AUDIT / "chopper_run.json"))
    present = chopper_run["artifacts_present"]
    assert "chopper_run.json" in present
    assert present == sorted(present)
