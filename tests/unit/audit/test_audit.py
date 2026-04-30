"""Unit tests for :mod:`chopper.audit`."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from chopper.adapters import InMemoryFS
from chopper.audit import AuditService
from chopper.audit.hashing import sha256_hex
from chopper.audit.sloc import count_raw, count_sloc
from chopper.audit.writers import (
    render_chopper_run,
    render_compiled_manifest,
    render_dependency_graph,
    render_diagnostics,
    render_files_kept,
    render_files_removed,
    render_trim_report_json,
    render_trim_report_txt,
    render_trim_stats,
)
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase, Severity
from chopper.core.models import (
    BaseJson,
    CompiledManifest,
    DependencyGraph,
    DomainState,
    Edge,
    FileOutcome,
    FileProvenance,
    FileTreatment,
    LoadedConfig,
    ParsedFile,
    ParseResult,
    ProcDecision,
    ProcEntry,
    RunRecord,
    StageSpec,
    TrimReport,
)

DOMAIN = Path("/work/my_domain")
BACKUP = Path("/work/my_domain_backup")
AUDIT = DOMAIN / ".chopper"


class _Sink:
    def __init__(self) -> None:
        self.emissions: list[Diagnostic] = []

    def emit(self, d: Diagnostic) -> None:
        self.emissions.append(d)

    def snapshot(self) -> tuple[Diagnostic, ...]:
        return tuple(self.emissions)

    def finalize(self) -> DiagnosticSummary:
        errors = sum(1 for d in self.emissions if d.severity is Severity.ERROR)
        warnings = sum(1 for d in self.emissions if d.severity is Severity.WARNING)
        infos = sum(1 for d in self.emissions if d.severity is Severity.INFO)
        return DiagnosticSummary(errors=errors, warnings=warnings, infos=infos)


class _Progress:
    def phase_started(self, phase: Phase) -> None: ...  # pragma: no cover
    def phase_done(self, phase: Phase) -> None: ...  # pragma: no cover
    def step(self, message: str) -> None: ...  # pragma: no cover


def _make_ctx(*, dry_run: bool = False, fs: InMemoryFS | None = None) -> ChopperContext:
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=dry_run)
    return ChopperContext(config=cfg, fs=fs or InMemoryFS(), diag=_Sink(), progress=_Progress())


def _record(**overrides) -> RunRecord:
    t0 = datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)
    base = {
        "run_id": "test-run-id-000000000000",
        "command": "trim",
        "started_at": t0,
        "ended_at": t0 + timedelta(seconds=5),
        "exit_code": 0,
    }
    base.update(overrides)
    return RunRecord(**base)


# ---------------------------------------------------------------------------
# hashing
# ---------------------------------------------------------------------------


def test_sha256_hex_is_64_char_hex() -> None:
    h = sha256_hex("hello\n")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# sloc
# ---------------------------------------------------------------------------


def test_count_sloc_tcl_skips_full_line_comments_and_blanks() -> None:
    text = "# header\n\nproc foo {} { return 1 }\n  # inline leading\nreturn 0\n"
    assert count_sloc(Path("a.tcl"), text) == 2


def test_count_sloc_shell_preserves_shebang() -> None:
    text = "#!/usr/bin/env bash\n# comment\necho hi\n"
    assert count_sloc(Path("s.sh"), text) == 2


def test_count_sloc_csv_ignores_comma_only_lines() -> None:
    text = "a,b,c\n,,,\nx,y,z\n\n"
    assert count_sloc(Path("d.csv"), text) == 2


def test_count_sloc_unknown_extension_counts_all_nonblank() -> None:
    text = "one\n\n# hash\nthree\n"
    assert count_sloc(Path("weird.xyz"), text) == 3


def test_count_raw_is_nonblank_count() -> None:
    assert count_raw("a\n\nb\n   \nc\n") == 3


# ---------------------------------------------------------------------------
# Writers — empty record (all phases aborted)
# ---------------------------------------------------------------------------


def test_render_compiled_manifest_empty_record_is_valid_json() -> None:
    name, content = render_compiled_manifest(_record())
    assert name == "compiled_manifest.json"
    payload = json.loads(content)
    assert payload["files"] == []
    assert payload["procedures"] == {"surviving": [], "excluded": [], "traced": []}


def test_render_dependency_graph_empty_record_is_valid_json() -> None:
    name, content = render_dependency_graph(_record())
    assert name == "dependency_graph.json"
    payload = json.loads(content)
    assert payload["pi_seeds"] == [] and payload["edges"] == []


def test_render_diagnostics_captures_sink_snapshot() -> None:
    ctx = _make_ctx()
    ctx.diag.emit(
        Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="file missing", path=Path("a.tcl"), line_no=1)
    )
    name, content = render_diagnostics(ctx, _record())
    assert name == "diagnostics.json"
    payload = json.loads(content)
    assert len(payload["diagnostics"]) == 1
    entry = payload["diagnostics"][0]
    assert entry["code"] == "VE-06"
    assert entry["slug"] == "file-not-in-domain"
    assert entry["severity"] == "error"
    assert entry["phase"] == "P1"


def test_render_trim_report_json_has_required_top_level_keys() -> None:
    ctx = _make_ctx()
    name, content = render_trim_report_json(ctx, _record())
    assert name == "trim_report.json"
    payload = json.loads(content)
    for key in ("chopper_version", "run_id", "mode", "summary", "file_report", "proc_report", "diagnostics"):
        assert key in payload


def test_render_trim_report_txt_is_human_readable() -> None:
    ctx = _make_ctx()
    name, content = render_trim_report_txt(ctx, _record())
    assert name == "trim_report.txt"
    assert "Chopper Trim Report" in content
    assert "test-run-id-000000000000" in content


def test_render_trim_stats_empty_record_has_zeros() -> None:
    ctx = _make_ctx()
    name, content = render_trim_stats(ctx, _record())
    assert name == "trim_stats.json"
    payload = json.loads(content)
    assert payload["files_before"] == 0
    assert payload["files_after"] == 0
    assert payload["trim_ratio_files"] == 0.0


def test_render_chopper_run_includes_mode_and_counts() -> None:
    ctx = _make_ctx(dry_run=True)
    name, content = render_chopper_run(ctx, _record(), ("diagnostics.json",))
    assert name == "chopper_run.json"
    payload = json.loads(content)
    assert payload["mode"] == "dry-run"
    assert payload["exit_code"] == 0
    assert "artifacts_present" in payload
    assert payload["diagnostics_summary"] == {"errors": 0, "warnings": 0, "info": 0}


def test_render_files_removed_empty_record_produces_header_only() -> None:
    name, content = render_files_removed(_record())
    assert name == "files_removed.txt"
    assert content.startswith("# files_removed.txt")
    # No paths present when manifest is absent.
    lines = [line for line in content.splitlines() if line and not line.startswith("#")]
    assert lines == []


def test_render_files_removed_lists_remove_paths_sorted() -> None:
    p_rem1 = Path("a_first.tcl")
    p_kept = Path("lib/keep.tcl")
    p_rem2 = Path("z_last.tcl")
    manifest = CompiledManifest(
        file_decisions={
            p_rem1: FileTreatment.REMOVE,
            p_kept: FileTreatment.FULL_COPY,
            p_rem2: FileTreatment.REMOVE,
        },
        proc_decisions={},
        provenance={
            p_rem1: FileProvenance(path=p_rem1, treatment=FileTreatment.REMOVE, reason="default-exclude"),
            p_kept: FileProvenance(
                path=p_kept,
                treatment=FileTreatment.FULL_COPY,
                reason="fi-literal",
                input_sources=("base:files.include",),
            ),
            p_rem2: FileProvenance(path=p_rem2, treatment=FileTreatment.REMOVE, reason="default-exclude"),
        },
    )
    _, content = render_files_removed(_record(manifest=manifest))
    data_lines = [line for line in content.splitlines() if line and not line.startswith("#")]
    assert data_lines == ["a_first.tcl", "z_last.tcl"]
    assert "lib/keep.tcl" not in content


def test_render_files_kept_empty_record_produces_header_only() -> None:
    name, content = render_files_kept(_record())
    assert name == "files_kept.txt"
    assert content.startswith("# files_kept.txt")
    lines = [line for line in content.splitlines() if line and not line.startswith("#")]
    assert lines == []


def test_render_files_kept_lists_surviving_paths_sorted() -> None:
    p_trim = Path("a_trim.tcl")
    p_rem = Path("drop.tcl")
    p_gen = Path("synth.tcl")
    p_copy = Path("z_copy.tcl")
    manifest = CompiledManifest(
        file_decisions={
            p_trim: FileTreatment.PROC_TRIM,
            p_rem: FileTreatment.REMOVE,
            p_gen: FileTreatment.GENERATED,
            p_copy: FileTreatment.FULL_COPY,
        },
        proc_decisions={},
        provenance={
            p_trim: FileProvenance(
                path=p_trim,
                treatment=FileTreatment.PROC_TRIM,
                reason="pi-additive",
                input_sources=("base:procedures.include",),
                proc_model="additive",
            ),
            p_rem: FileProvenance(path=p_rem, treatment=FileTreatment.REMOVE, reason="default-exclude"),
            p_gen: FileProvenance(
                path=p_gen,
                treatment=FileTreatment.GENERATED,
                reason="fi-literal",
                input_sources=("base:stages",),
            ),
            p_copy: FileProvenance(
                path=p_copy,
                treatment=FileTreatment.FULL_COPY,
                reason="fi-literal",
                input_sources=("base:files.include",),
            ),
        },
    )
    _, content = render_files_kept(_record(manifest=manifest))
    data_lines = [line for line in content.splitlines() if line and not line.startswith("#")]
    assert data_lines == ["a_trim.tcl", "synth.tcl", "z_copy.tcl"]
    assert "drop.tcl" not in content





def test_audit_service_writes_bundle_with_empty_record() -> None:
    fs = InMemoryFS()
    ctx = _make_ctx(fs=fs)
    manifest = AuditService().run(ctx, _record())

    names = [a.name for a in manifest.artifacts]
    assert "chopper_run.json" in names
    assert "diagnostics.json" in names
    assert "run_id" in names
    assert "files_removed.txt" in names
    assert "files_kept.txt" in names
    assert names == sorted(names)

    # Each artifact was actually written and hash matches file content.
    for artifact in manifest.artifacts:
        assert fs.exists(artifact.path)
        assert artifact.sha256 == sha256_hex(fs.read_text(artifact.path))
        assert artifact.size == len(fs.read_text(artifact.path).encode("utf-8"))


def test_audit_service_copies_inputs_when_loaded_present() -> None:
    base_path = Path("/src/jsons/base.json")
    fs = InMemoryFS()
    fs.write_text(base_path, '{"name": "base"}\n')

    ctx = _make_ctx(fs=fs)
    base = BaseJson(source_path=base_path, domain="my_domain")
    loaded = LoadedConfig(base=base, features=(), surface_files=())

    manifest = AuditService().run(ctx, _record(loaded=loaded))

    names = [a.name for a in manifest.artifacts]
    assert "input_base.json" in names
    assert fs.read_text(AUDIT / "input_base.json") == '{"name": "base"}\n'


def test_audit_service_tolerates_missing_input_file() -> None:
    base_path = Path("/src/jsons/missing.json")
    ctx = _make_ctx()
    base = BaseJson(source_path=base_path, domain="my_domain")
    loaded = LoadedConfig(base=base, features=(), surface_files=())

    manifest = AuditService().run(ctx, _record(loaded=loaded))
    names = [a.name for a in manifest.artifacts]
    # input_base.json skipped silently because the source file is absent.
    assert "input_base.json" not in names
    assert "chopper_run.json" in names


def test_audit_service_records_trim_state_first_vs_retrim() -> None:
    fs = InMemoryFS()
    ctx = _make_ctx(fs=fs)
    state_first = DomainState(case=1, domain_exists=True, backup_exists=False, hand_edited=False)
    AuditService().run(ctx, _record(state=state_first))
    payload_first = json.loads(fs.read_text(AUDIT / "chopper_run.json"))
    assert payload_first["trim_state"] == "first-trim"

    fs2 = InMemoryFS()
    ctx2 = _make_ctx(fs=fs2)
    state_retrim = DomainState(case=2, domain_exists=True, backup_exists=True, hand_edited=False)
    AuditService().run(ctx2, _record(state=state_retrim))
    payload_retrim = json.loads(fs2.read_text(AUDIT / "chopper_run.json"))
    assert payload_retrim["trim_state"] == "re-trim"


def test_audit_service_renders_manifest_files_section() -> None:
    fs = InMemoryFS()
    ctx = _make_ctx(fs=fs)
    path = Path("a.tcl")
    manifest_obj = CompiledManifest(
        file_decisions={path: FileTreatment.FULL_COPY},
        proc_decisions={},
        provenance={
            path: FileProvenance(
                path=path,
                treatment=FileTreatment.FULL_COPY,
                reason="fi-literal",
                input_sources=("base:files.include",),
            )
        },
    )
    AuditService().run(ctx, _record(manifest=manifest_obj))

    payload = json.loads(fs.read_text(AUDIT / "compiled_manifest.json"))
    assert payload["files"] == [
        {
            "path": "a.tcl",
            "treatment": "full-copy",
            "reason": "fi-literal",
            "input_sources": ["base:files.include"],
            "proc_model": None,
            "surviving_procs": None,
            "excluded_procs": None,
        }
    ]


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
    ctx = _make_ctx()
    record = _build_rich_record()
    _name, content = render_trim_report_json(ctx, record)
    payload = json.loads(content)
    assert payload["summary"]["total_domain_files"] == 2
    assert payload["summary"]["procs_removed"] == 1
    assert len(payload["file_report"]) == 4
    assert len(payload["proc_report"]) == 2


def test_trim_report_txt_emits_treatment_breakdown_and_dry_run_notice() -> None:
    fs = InMemoryFS()
    ctx = _make_ctx(dry_run=True, fs=fs)
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
    ctx = _make_ctx(fs=fs)
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
    ctx = _make_ctx(fs=fs)
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


# ------------------------------------------------------------------
# Extracted from test_small_modules_torture.py (module-aligned consolidation).
# ------------------------------------------------------------------
