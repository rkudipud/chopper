"""Unit tests for :func:`chopper.audit.writers.render_p4_commands`.

Covers FR-47 / architecture doc Sec.5.5.14 -- the deterministic Perforce
command-list audit artifact. Each treatment in
``CompiledManifest.file_decisions`` maps to a specific ``p4`` command:

* ``PROC_TRIM`` -> ``p4 edit -t text+x``
* ``GENERATED`` where the path exists in the pre-trim source root ->
  ``p4 edit -t text+x`` (regenerate-in-place)
* ``GENERATED`` where the path does **not** exist pre-trim ->
  ``p4 add -t text+x``
* Physically removed (walk(source_root) - kept_set) -> ``exclude_file_list`` section
  (bare domain-relative paths; no ``p4`` command prefix).
* ``FULL_COPY`` -> no command (rebuilt byte-identical to depot).

Sections are alphabetically sorted within and ordered edits -> adds ->
deletes between. ``-t text+x`` matches the cross-phase
``ensure_executable()`` contract (every rebuilt file carries ``a+x``;
see ``core/file_perms.py``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from chopper.adapters import InMemoryFS
from chopper.audit.writers import render_p4_commands
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


def _make_ctx(*, dry_run: bool = False, fs: InMemoryFS | None = None) -> ChopperContext:
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=dry_run)
    return ChopperContext(config=cfg, fs=fs or InMemoryFS(), diag=_Sink(), progress=_Progress())


def _record(**overrides) -> RunRecord:
    t0 = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
    base = {
        "run_id": "p4-test-run-id-000000000",
        "command": "trim",
        "started_at": t0,
        "ended_at": t0 + timedelta(seconds=5),
        "exit_code": 0,
    }
    base.update(overrides)
    return RunRecord(**base)


def _prov(path: Path, treatment: FileTreatment, *, reason: str = "fi-literal") -> FileProvenance:
    return FileProvenance(
        path=path,
        treatment=treatment,
        reason=reason,
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


# ---------------------------------------------------------------------------
# Filename + banner
# ---------------------------------------------------------------------------


def test_filename_is_p4_commands_txt() -> None:
    name, _ = render_p4_commands(_make_ctx(), _record())
    assert name == "p4_commands.txt"


def test_banner_comments_are_present_and_trailing_newline() -> None:
    _, content = render_p4_commands(_make_ctx(), _record())
    assert content.startswith("# p4_commands.txt"), "must lead with banner comment"
    assert "p4 submit" in content, "banner must mention manual submit"
    assert "text+x" in content, "banner must document the filetype flag"
    assert content.endswith("\n"), "must end with a single trailing newline"


# ---------------------------------------------------------------------------
# Empty record (aborted run / no manifest)
# ---------------------------------------------------------------------------


def test_empty_record_produces_header_plus_no_op_marker() -> None:
    _, content = render_p4_commands(_make_ctx(), _record())
    assert "(no Perforce commands" in content
    assert _data_lines(content) == []


def test_empty_record_with_filesystem_still_no_op() -> None:
    fs = InMemoryFS()
    # No source files staged; manifest is None.
    _, content = render_p4_commands(_make_ctx(fs=fs), _record())
    assert "(no Perforce commands" in content
    assert _data_lines(content) == []


# ---------------------------------------------------------------------------
# PROC_TRIM -> p4 edit
# ---------------------------------------------------------------------------


def test_proc_trim_emits_p4_edit_with_text_plus_x() -> None:
    fs = InMemoryFS()
    p = Path("lib/foo.tcl")
    fs.write_text(BACKUP / p, "proc foo {} {}\n")
    manifest = _make_manifest({p: FileTreatment.PROC_TRIM})
    _, content = render_p4_commands(_make_ctx(fs=fs), _record(manifest=manifest))
    assert _data_lines(content) == ["p4 edit -t text+x lib/foo.tcl"]


def test_multiple_proc_trim_files_are_alphabetically_sorted() -> None:
    fs = InMemoryFS()
    for rel in ("z.tcl", "a.tcl", "m/lib.tcl"):
        fs.write_text(BACKUP / rel, "proc x {} {}\n")
    decisions = {Path(rel): FileTreatment.PROC_TRIM for rel in ("z.tcl", "a.tcl", "m/lib.tcl")}
    manifest = _make_manifest(decisions)
    _, content = render_p4_commands(_make_ctx(fs=fs), _record(manifest=manifest))
    assert _data_lines(content) == [
        "p4 edit -t text+x a.tcl",
        "p4 edit -t text+x m/lib.tcl",
        "p4 edit -t text+x z.tcl",
    ]


# ---------------------------------------------------------------------------
# GENERATED -- regenerate-in-place vs newly-added
# ---------------------------------------------------------------------------


def test_generated_with_pre_existing_source_is_p4_edit() -> None:
    """Regenerate-in-place: depot file already exists, the generator overwrites it."""

    fs = InMemoryFS()
    p = Path("fev_fm_rtl2gate.tcl")
    fs.write_text(BACKUP / p, "# existing\n")  # exists pre-trim
    manifest = _make_manifest({p: FileTreatment.GENERATED})
    _, content = render_p4_commands(_make_ctx(fs=fs), _record(manifest=manifest))
    assert _data_lines(content) == ["p4 edit -t text+x fev_fm_rtl2gate.tcl"]


def test_generated_without_pre_existing_source_is_p4_add() -> None:
    """Fresh stage file with no prior depot entry."""

    fs = InMemoryFS()
    # Backup directory exists so source_root resolves, but the generated
    # file itself was never on disk pre-trim.
    fs.write_text(BACKUP / "other.tcl", "# unrelated\n")
    p = Path("setup.tcl")
    manifest = _make_manifest({p: FileTreatment.GENERATED})
    _, content = render_p4_commands(_make_ctx(fs=fs), _record(manifest=manifest))
    assert "p4 add -t text+x setup.tcl" in _data_lines(content)
    assert "p4 edit -t text+x setup.tcl" not in content


def test_generated_dry_run_checks_domain_root_for_source() -> None:
    """Dry-run: no backup, original files still under domain_root."""

    fs = InMemoryFS()
    fs.write_text(DOMAIN / "fev_fm_rtl2gate.tcl", "# existing\n")
    manifest = _make_manifest({Path("fev_fm_rtl2gate.tcl"): FileTreatment.GENERATED})
    _, content = render_p4_commands(_make_ctx(dry_run=True, fs=fs), _record(manifest=manifest))
    # Pre-trim domain holds the file -> regenerate-in-place -> p4 edit.
    assert _data_lines(content) == ["p4 edit -t text+x fev_fm_rtl2gate.tcl"]


# ---------------------------------------------------------------------------
# REMOVE / files_removed parity -> exclude_file_list
# ---------------------------------------------------------------------------


def test_remove_files_emit_exclude_file_list_section() -> None:
    fs = InMemoryFS()
    fs.write_text(BACKUP / "kept.tcl", "puts kept\n")
    fs.write_text(BACKUP / "drop.tcl", "puts drop\n")
    manifest = _make_manifest(
        {
            Path("kept.tcl"): FileTreatment.FULL_COPY,
            Path("drop.tcl"): FileTreatment.REMOVE,
        }
    )
    _, content = render_p4_commands(_make_ctx(fs=fs), _record(manifest=manifest))
    assert "drop.tcl" in _data_lines(content)
    assert "p4 delete" not in content, "exclude_file_list section must not use p4 delete command"
    assert "exclude_file_list" in content


def test_exclude_file_list_parity_with_files_removed_includes_default_excluded() -> None:
    """exclude_file_list set equals ``walk(source_root) - kept_set`` -- matching files_removed.txt."""

    fs = InMemoryFS()
    fs.write_text(BACKUP / "kept.tcl", "puts kept\n")
    # Two files physically on disk but never named by any JSON layer.
    fs.write_text(BACKUP / "helper.pl", "#!/usr/bin/env perl\n")
    fs.write_text(BACKUP / "scripts" / "run.csh", "#!/bin/csh\n")
    p_kept = Path("kept.tcl")
    manifest = CompiledManifest(
        file_decisions={p_kept: FileTreatment.FULL_COPY},
        proc_decisions={},
        provenance={p_kept: _prov(p_kept, FileTreatment.FULL_COPY)},
    )
    _, content = render_p4_commands(_make_ctx(fs=fs), _record(manifest=manifest))
    data = _data_lines(content)
    # Default-excluded files appear in the exclude_file_list section even
    # though they never entered the manifest's REMOVE set.
    assert "helper.pl" in data
    assert "scripts/run.csh" in data
    assert "p4 delete" not in content
    # And they're sorted within the section.
    delete_lines = [ln for ln in data if not ln.startswith("p4 ")]
    assert delete_lines == sorted(delete_lines)


def test_p4_delete_skips_top_level_chopper_dir() -> None:
    fs = InMemoryFS()
    fs.write_text(BACKUP / "real.tcl", "puts hi\n")
    fs.write_text(BACKUP / ".chopper" / "leftover.json", "{}\n")
    p = Path("real.tcl")
    manifest = _make_manifest({p: FileTreatment.FULL_COPY})
    _, content = render_p4_commands(_make_ctx(fs=fs), _record(manifest=manifest))
    assert ".chopper" not in content


# ---------------------------------------------------------------------------
# FULL_COPY -- no command
# ---------------------------------------------------------------------------


def test_full_copy_emits_no_command() -> None:
    fs = InMemoryFS()
    p = Path("verbatim.tcl")
    fs.write_text(BACKUP / p, "verbatim\n")
    manifest = _make_manifest({p: FileTreatment.FULL_COPY})
    _, content = render_p4_commands(_make_ctx(fs=fs), _record(manifest=manifest))
    # No p4 command for FULL_COPY; only the no-op marker comment.
    assert "(no Perforce commands" in content
    assert _data_lines(content) == []


# ---------------------------------------------------------------------------
# Mixed scenario -- section ordering + sort determinism
# ---------------------------------------------------------------------------


def test_mixed_scenario_section_order_is_edit_add_delete() -> None:
    fs = InMemoryFS()
    # Pre-trim source: depot baseline.
    fs.write_text(BACKUP / "lib/foo.tcl", "proc foo {} {}\n")  # PROC_TRIM
    fs.write_text(BACKUP / "fev_fm_rtl2gate.tcl", "# old\n")  # GENERATED regen
    fs.write_text(BACKUP / "stale.pl", "#!/usr/bin/env perl\n")  # default-exclude (delete)
    fs.write_text(BACKUP / "verbatim.tcl", "verbatim\n")  # FULL_COPY

    manifest = _make_manifest(
        {
            Path("lib/foo.tcl"): FileTreatment.PROC_TRIM,
            Path("verbatim.tcl"): FileTreatment.FULL_COPY,
            Path("fev_fm_rtl2gate.tcl"): FileTreatment.GENERATED,  # exists in backup -> edit
            Path("setup.tcl"): FileTreatment.GENERATED,  # new -> add
            Path("run_flow.tcl"): FileTreatment.GENERATED,  # new -> add
        }
    )
    _, content = render_p4_commands(_make_ctx(fs=fs), _record(manifest=manifest))
    data = _data_lines(content)

    # Section order is fixed: edits, adds, exclude_file_list.
    edit_idx = next(i for i, ln in enumerate(data) if ln.startswith("p4 edit"))
    add_idx = next(i for i, ln in enumerate(data) if ln.startswith("p4 add"))
    # exclude_file_list entries are bare paths (no "p4 " prefix).
    delete_idx = next(i for i, ln in enumerate(data) if not ln.startswith("p4 "))
    assert edit_idx < add_idx < delete_idx, f"sections out of order: {data}"

    # Edit section contents -- sorted.
    edits = [ln for ln in data if ln.startswith("p4 edit")]
    assert edits == [
        "p4 edit -t text+x fev_fm_rtl2gate.tcl",
        "p4 edit -t text+x lib/foo.tcl",
    ]
    # Add section contents -- sorted.
    adds = [ln for ln in data if ln.startswith("p4 add")]
    assert adds == [
        "p4 add -t text+x run_flow.tcl",
        "p4 add -t text+x setup.tcl",
    ]
    # exclude_file_list section -- only the default-excluded helper.
    deletes = [ln for ln in data if not ln.startswith("p4 ")]
    assert deletes == ["stale.pl"]


def test_text_plus_x_appears_on_every_edit_and_add_line() -> None:
    fs = InMemoryFS()
    fs.write_text(BACKUP / "a.tcl", "x\n")  # PROC_TRIM
    fs.write_text(BACKUP / "b.tcl", "x\n")  # GENERATED regen
    manifest = _make_manifest(
        {
            Path("a.tcl"): FileTreatment.PROC_TRIM,
            Path("b.tcl"): FileTreatment.GENERATED,
            Path("c.tcl"): FileTreatment.GENERATED,  # new -> add
        }
    )
    _, content = render_p4_commands(_make_ctx(fs=fs), _record(manifest=manifest))
    for line in _data_lines(content):
        if line.startswith("p4 edit") or line.startswith("p4 add"):
            assert "-t text+x" in line, f"missing -t text+x on {line!r}"


def test_output_is_deterministic_across_insertion_orders() -> None:
    fs = InMemoryFS()
    fs.write_text(BACKUP / "a.tcl", "x\n")
    fs.write_text(BACKUP / "b.tcl", "x\n")
    decisions_a = {
        Path("a.tcl"): FileTreatment.PROC_TRIM,
        Path("b.tcl"): FileTreatment.PROC_TRIM,
    }
    decisions_b = {
        Path("b.tcl"): FileTreatment.PROC_TRIM,
        Path("a.tcl"): FileTreatment.PROC_TRIM,
    }
    _, content_a = render_p4_commands(_make_ctx(fs=fs), _record(manifest=_make_manifest(decisions_a)))
    _, content_b = render_p4_commands(_make_ctx(fs=fs), _record(manifest=_make_manifest(decisions_b)))
    assert content_a == content_b


# ---------------------------------------------------------------------------
# Source-root fallback (no fs available)
# ---------------------------------------------------------------------------


def test_no_source_root_falls_back_to_manifest_only_view() -> None:
    """When neither backup_root nor domain_root exist on disk, the writer
    falls back to a manifest-only view: REMOVE -> delete, GENERATED -> add."""

    # Empty fs -- neither domain_root nor backup_root exist.
    fs = InMemoryFS()
    manifest = _make_manifest(
        {
            Path("foo.tcl"): FileTreatment.PROC_TRIM,
            Path("gone.tcl"): FileTreatment.REMOVE,
            Path("new.tcl"): FileTreatment.GENERATED,
        }
    )
    _, content = render_p4_commands(_make_ctx(fs=fs), _record(manifest=manifest))
    data = _data_lines(content)
    assert "p4 edit -t text+x foo.tcl" in data
    # No source root -> cannot tell if GENERATED file pre-existed -> treat as add.
    assert "p4 add -t text+x new.tcl" in data
    # No source root -> manifest-only exclude_file_list entry.
    assert "gone.tcl" in data
    assert "p4 delete" not in content


# ---------------------------------------------------------------------------
# Dry-run / live byte-identical parity
# ---------------------------------------------------------------------------


def test_dry_run_and_live_produce_byte_identical_output_for_same_state() -> None:
    """Non-interactive scripts diff dry-run plan vs live trim -- must match."""

    # Dry-run state: original files still under domain_root.
    fs_dry = InMemoryFS()
    fs_dry.write_text(DOMAIN / "foo.tcl", "proc foo {} {}\n")
    fs_dry.write_text(DOMAIN / "drop.tcl", "stale\n")
    # Live state: same originals but moved to backup_root by P5.
    fs_live = InMemoryFS()
    fs_live.write_text(BACKUP / "foo.tcl", "proc foo {} {}\n")
    fs_live.write_text(BACKUP / "drop.tcl", "stale\n")

    decisions = {
        Path("foo.tcl"): FileTreatment.PROC_TRIM,
        Path("drop.tcl"): FileTreatment.REMOVE,
    }
    manifest = _make_manifest(decisions)

    _, dry = render_p4_commands(_make_ctx(dry_run=True, fs=fs_dry), _record(manifest=manifest))
    _, live = render_p4_commands(_make_ctx(dry_run=False, fs=fs_live), _record(manifest=manifest))
    assert dry == live
