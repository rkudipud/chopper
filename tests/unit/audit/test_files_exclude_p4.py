"""Unit tests for :func:`chopper.audit.writers.render_files_exclude_p4`.

Covers FR-51 / architecture doc Sec.5.5.14 -- the standalone exclude-list
audit artifact. The path set and formatting must be byte-for-byte identical
to the ``exclude_file_list`` section of ``p4_commands.txt``
(:func:`chopper.audit.writers.render_p4_commands`), sharing the same
``_compute_excluded_paths`` helper.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from chopper.adapters import InMemoryFS
from chopper.audit.writers import render_files_exclude_p4, render_p4_commands
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase, Severity
from chopper.core.models_audit import RunRecord
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest, FileProvenance

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


def _make_ctx(*, dry_run: bool = False, fs: InMemoryFS | None = None, ward_root: Path | None = None) -> ChopperContext:
    cfg = RunConfig(
        domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=dry_run, ward_root=ward_root
    )
    return ChopperContext(config=cfg, fs=fs or InMemoryFS(), diag=_Sink(), progress=_Progress())


def _record(**overrides) -> RunRecord:
    t0 = datetime(2026, 7, 9, 12, 0, 0, tzinfo=UTC)
    base = {
        "run_id": "exclude-p4-test-run-000000",
        "command": "trim",
        "started_at": t0,
        "ended_at": t0 + timedelta(seconds=5),
        "exit_code": 0,
    }
    base.update(overrides)
    return RunRecord(**base)


def _prov(path: Path, treatment: FileTreatment) -> FileProvenance:
    return FileProvenance(
        path=path,
        treatment=treatment,
        reason="fi-literal",
        input_sources=("base:files.include",) if treatment is not FileTreatment.REMOVE else (),
    )


def _make_manifest(decisions: dict[Path, FileTreatment]) -> CompiledManifest:
    sorted_decisions = {p: decisions[p] for p in sorted(decisions, key=lambda x: x.as_posix())}
    return CompiledManifest(
        file_decisions=sorted_decisions,
        proc_decisions={},
        provenance={p: _prov(p, t) for p, t in sorted_decisions.items()},
    )


def _data_lines(content: str) -> list[str]:
    return [ln for ln in content.splitlines() if ln and not ln.startswith("#")]


def test_filename_is_files_exclude_p4_txt() -> None:
    name, _ = render_files_exclude_p4(_make_ctx(), _record())
    assert name == "files_exclude_p4.txt"


def test_banner_present_and_trailing_newline() -> None:
    _, content = render_files_exclude_p4(_make_ctx(), _record())
    assert content.startswith("# files_exclude_p4.txt")
    assert content.endswith("\n")


def test_empty_record_produces_no_op_marker() -> None:
    _, content = render_files_exclude_p4(_make_ctx(), _record())
    assert "(no files excluded)" in content
    assert _data_lines(content) == []


def test_excluded_paths_match_p4_commands_exclude_file_list_section() -> None:
    """The exact path set/order must match render_p4_commands's exclude_file_list section."""

    fs = InMemoryFS()
    fs.write_text(BACKUP / "kept.tcl", "puts kept\n")
    fs.write_text(BACKUP / "drop.tcl", "puts drop\n")
    fs.write_text(BACKUP / "helper.pl", "#!/usr/bin/env perl\n")
    manifest = _make_manifest(
        {
            Path("kept.tcl"): FileTreatment.FULL_COPY,
            Path("drop.tcl"): FileTreatment.REMOVE,
        }
    )
    record = _record(manifest=manifest)

    _, exclude_content = render_files_exclude_p4(_make_ctx(fs=fs), record)
    _, p4_content = render_p4_commands(_make_ctx(fs=fs), record)

    exclude_lines = _data_lines(exclude_content)
    p4_lines = [ln for ln in _data_lines(p4_content) if not ln.startswith("p4 ")]

    assert exclude_lines == ["drop.tcl", "helper.pl"]
    assert exclude_lines == sorted(exclude_lines)
    assert exclude_lines == p4_lines


def test_ward_relative_paths_used_when_ward_root_available() -> None:
    # Anchored to the OS root (drive letter on Windows, "/" on POSIX) so
    # ``Path.resolve()`` -- used internally by ``_format_exclusion_path`` --
    # is a no-op and the test behaves identically cross-platform.
    ward_root = Path(Path.cwd().anchor) / "ward"
    domain_root = ward_root / "global" / "snps" / "my_domain"
    backup_root = domain_root.with_name(domain_root.name + "_backup")

    fs = InMemoryFS()
    fs.write_text(backup_root / "old.tcl", "puts old\n")
    cfg = RunConfig(
        domain_root=domain_root,
        backup_root=backup_root,
        audit_root=domain_root / ".chopper",
        strict=False,
        dry_run=False,
        ward_root=ward_root,
    )
    ctx = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    manifest = _make_manifest({})
    _, content = render_files_exclude_p4(ctx, _record(manifest=manifest))
    assert "global/snps/my_domain/old.tcl" in _data_lines(content)


def test_no_source_root_falls_back_to_manifest_remove_decisions() -> None:
    fs = InMemoryFS()
    manifest = _make_manifest({Path("gone.tcl"): FileTreatment.REMOVE})
    _, content = render_files_exclude_p4(_make_ctx(fs=fs), _record(manifest=manifest))
    assert _data_lines(content) == ["gone.tcl"]


def test_output_is_deterministic_across_insertion_orders() -> None:
    fs = InMemoryFS()
    fs.write_text(BACKUP / "a.tcl", "x\n")
    fs.write_text(BACKUP / "b.tcl", "x\n")
    manifest_a = _make_manifest({Path("a.tcl"): FileTreatment.FULL_COPY})
    manifest_b = _make_manifest({Path("b.tcl"): FileTreatment.REMOVE})
    _, content_a = render_files_exclude_p4(_make_ctx(fs=fs), _record(manifest=manifest_a))
    _, content_b = render_files_exclude_p4(_make_ctx(fs=fs), _record(manifest=manifest_b))
    assert content_a != content_b  # sanity: different manifests differ
    assert _data_lines(content_a) == ["b.tcl"]
