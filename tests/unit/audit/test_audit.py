"""Unit tests for :mod:`chopper.audit`."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from chopper.adapters.fs_memory import InMemoryFS
from chopper.audit import AuditService
from chopper.audit.hashing import sha256_hex
from chopper.audit.sloc import count_raw, count_sloc
from chopper.audit.writers import (
    render_chopper_run,
    render_compiled_manifest,
    render_dependency_graph,
    render_diagnostics,
    render_trim_report_json,
    render_trim_report_txt,
    render_trim_stats,
)
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase, Severity
from chopper.core.models import (
    BaseJson,
    CompiledManifest,
    DomainState,
    FileProvenance,
    FileTreatment,
    LoadedConfig,
    RunRecord,
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


# ---------------------------------------------------------------------------
# AuditService end-to-end
# ---------------------------------------------------------------------------


def test_audit_service_writes_bundle_with_empty_record() -> None:
    fs = InMemoryFS()
    ctx = _make_ctx(fs=fs)
    manifest = AuditService().run(ctx, _record())

    names = [a.name for a in manifest.artifacts]
    assert "chopper_run.json" in names
    assert "diagnostics.json" in names
    assert "run_id" in names
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
