"""Tests for P5c Tcl indentation normalization."""

from __future__ import annotations

from pathlib import Path

from chopper.adapters import InMemoryFS
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest, FileProvenance
from chopper.core.models_trimmer import FileOutcome, GeneratedArtifact, TrimReport
from chopper.trimmer.indentation import TclIndentationService, format_tcl_indentation
from tests.unit.trimmer._helpers import DOMAIN, make_ctx


def _manifest(decisions: dict[str, FileTreatment]) -> CompiledManifest:
    file_decisions: dict[Path, FileTreatment] = {}
    provenance: dict[Path, FileProvenance] = {}
    for raw_path, treatment in sorted(decisions.items()):
        path = Path(raw_path)
        file_decisions[path] = treatment
        provenance[path] = FileProvenance(
            path=path,
            treatment=treatment,
            reason="fi-literal" if treatment is not FileTreatment.REMOVE else "default-exclude",
            input_sources=("base:files.include",) if treatment is not FileTreatment.REMOVE else (),
            proc_model="overlay" if treatment is FileTreatment.PROC_TRIM else None,
        )
    return CompiledManifest(file_decisions=file_decisions, proc_decisions={}, provenance=provenance)


def _outcome(path: str, treatment: FileTreatment, *, bytes_out: int) -> FileOutcome:
    return FileOutcome(
        path=Path(path),
        treatment=treatment,
        bytes_in=bytes_out,
        bytes_out=bytes_out,
        procs_kept=(),
        procs_removed=(),
    )


def _report(*outcomes: FileOutcome) -> TrimReport:
    ordered = tuple(sorted(outcomes, key=lambda outcome: outcome.path.as_posix()))
    return TrimReport(
        outcomes=ordered,
        files_copied=sum(1 for outcome in ordered if outcome.treatment is FileTreatment.FULL_COPY),
        files_trimmed=sum(1 for outcome in ordered if outcome.treatment is FileTreatment.PROC_TRIM),
        files_removed=sum(1 for outcome in ordered if outcome.treatment is FileTreatment.REMOVE),
        procs_kept_total=0,
        procs_removed_total=0,
    )


def test_format_tcl_indentation_ports_legacy_brace_logic() -> None:
    text = "proc foo {} {\nputs ok\nif {$flag} {\nputs nested\n}\ntopology:\n}\n"

    assert format_tcl_indentation(text) == (
        "proc foo {} {\n    puts ok\n    if {$flag} {\n        puts nested\n    }\n  topology:\n}\n"
    )


def test_service_formats_all_surviving_tcl_outputs_and_updates_report() -> None:
    full_text = "proc copied {} {\nputs copied\n}\n"
    trim_text = "proc kept {} {\nputs kept\n}\n"
    generated_text = "# Chopper-generated stage: stage\nif {$ready} {\nputs ready\n}\n"
    note_text = "    not tcl\n"
    fs = InMemoryFS(
        {
            DOMAIN / "full.tcl": full_text,
            DOMAIN / "trim.tcl": trim_text,
            DOMAIN / "stage.tcl": generated_text,
            DOMAIN / "note.txt": note_text,
        }
    )
    ctx, sink = make_ctx(fs=fs)
    manifest = _manifest(
        {
            "full.tcl": FileTreatment.FULL_COPY,
            "note.txt": FileTreatment.FULL_COPY,
            "stage.tcl": FileTreatment.GENERATED,
            "trim.tcl": FileTreatment.PROC_TRIM,
        }
    )
    report = _report(
        _outcome("full.tcl", FileTreatment.FULL_COPY, bytes_out=len(full_text.encode("utf-8"))),
        _outcome("note.txt", FileTreatment.FULL_COPY, bytes_out=len(note_text.encode("utf-8"))),
        _outcome("trim.tcl", FileTreatment.PROC_TRIM, bytes_out=len(trim_text.encode("utf-8"))),
    )
    artifacts = (GeneratedArtifact(path=Path("stage.tcl"), kind="tcl", content=generated_text, source_stage="stage"),)

    updated_report, updated_artifacts, rewritten = TclIndentationService().run(ctx, manifest, report, artifacts)

    assert sink.codes() == []
    assert rewritten == (DOMAIN / "full.tcl", DOMAIN / "stage.tcl", DOMAIN / "trim.tcl")
    assert fs.read_text(DOMAIN / "full.tcl") == "proc copied {} {\n    puts copied\n}\n"
    assert fs.read_text(DOMAIN / "trim.tcl") == "proc kept {} {\n    puts kept\n}\n"
    assert fs.read_text(DOMAIN / "stage.tcl") == (
        "# Chopper-generated stage: stage\nif {$ready} {\n    puts ready\n}\n"
    )
    assert fs.read_text(DOMAIN / "note.txt") == note_text

    outcomes = {outcome.path.as_posix(): outcome for outcome in updated_report.outcomes}
    assert outcomes["full.tcl"].bytes_out == len(fs.read_text(DOMAIN / "full.tcl").encode("utf-8"))
    assert outcomes["trim.tcl"].bytes_out == len(fs.read_text(DOMAIN / "trim.tcl").encode("utf-8"))
    assert outcomes["note.txt"].bytes_out == len(note_text.encode("utf-8"))
    assert updated_artifacts[0].content == fs.read_text(DOMAIN / "stage.tcl")
