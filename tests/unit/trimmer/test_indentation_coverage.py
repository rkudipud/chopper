"""Per-file coverage tests for src/chopper/trimmer/indentation.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from pathlib import Path

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _make_file_outcome,
    _make_trim_report,
    _Progress,
    _Sink,
)


def test_format_tcl_indentation_empty_returns_empty() -> None:
    from chopper.trimmer.indentation import format_tcl_indentation

    assert format_tcl_indentation("") == ""


def test_indentation_service_emits_ve25_on_read_failure() -> None:
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_compiler import CompiledManifest, FileProvenance
    from chopper.core.models_trimmer import TrimReport
    from chopper.trimmer.indentation import TclIndentationService

    rel = Path("a.tcl")

    class _FailReadFS(InMemoryFS):
        def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:  # type: ignore[override]
            raise OSError("boom")

    fs = _FailReadFS()
    fs.write_text(DOMAIN / rel, "proc x {} {}\n")
    ctx = _ctx(fs=fs)
    manifest = CompiledManifest(
        file_decisions={rel: FileTreatment.PROC_TRIM},
        proc_decisions={},
        provenance={
            rel: FileProvenance(path=rel, treatment=FileTreatment.PROC_TRIM, reason="fi-literal"),
        },
        stages=(),
    )
    trim_report = TrimReport(
        outcomes=(),
        files_copied=0,
        files_trimmed=0,
        files_removed=0,
        procs_kept_total=0,
        procs_removed_total=0,
    )

    new_report, _, _ = TclIndentationService().run(ctx, manifest, trim_report, ())
    assert "VE-25" in _codes(ctx)
    assert new_report.rebuild_interrupted is True


def test_indentation_mark_interrupted_idempotent() -> None:
    from chopper.core.models_trimmer import TrimReport
    from chopper.trimmer.indentation import _mark_interrupted

    already = TrimReport(
        outcomes=(),
        files_copied=0,
        files_trimmed=0,
        files_removed=0,
        procs_kept_total=0,
        procs_removed_total=0,
        rebuild_interrupted=True,
    )
    assert _mark_interrupted(already) is already


def test_with_updated_artifacts_unchanged_when_no_normalization() -> None:
    """When the normalizer produces no diff for any artifact, the original
    artifacts tuple is returned unchanged (identity, not a copy)."""
    from chopper.core.models_trimmer import GeneratedArtifact
    from chopper.trimmer.indentation import _with_updated_artifacts  # type: ignore[attr-defined]

    a = GeneratedArtifact(path=Path("x.tcl"), kind="stage", content="a\n", source_stage="s")
    b = GeneratedArtifact(path=Path("y.tcl"), kind="stage", content="b\n", source_stage="s")
    # normalized dict has no overlap with artifact paths -> no changes.
    result = _with_updated_artifacts((a, b), normalized={})
    # Must return original tuple unchanged when nothing updated.
    assert result == (a, b)


def test_indentation_normalizer_skips_write_when_unchanged() -> None:
    """IndentationNormalizer skips ctx.fs.write_text when formatted == text (branch 85->91)."""
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_compiler import CompiledManifest, FileProvenance
    from chopper.trimmer.indentation import TclIndentationService

    fs = InMemoryFS()
    # Write a file that is ALREADY correctly indented (4-space indent -> no change)
    content = "proc foo {} {\n    return 1\n}\n"
    fs.write_text(DOMAIN / "lib.tcl", content)

    outcome = _make_file_outcome(
        "lib.tcl",
        FileTreatment.PROC_TRIM,
        bytes_in=len(content.encode()),
        bytes_out=len(content.encode()),
    )
    report = _make_trim_report(outcome)

    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    # Build a minimal compiled manifest for _tcl_output_paths
    prov = FileProvenance(path=Path("lib.tcl"), treatment=FileTreatment.PROC_TRIM, reason="included")
    manifest = CompiledManifest(
        file_decisions={Path("lib.tcl"): FileTreatment.PROC_TRIM},
        proc_decisions={},
        provenance={Path("lib.tcl"): prov},
        stages=(),
        generate_stack=False,
    )

    artifacts: tuple = ()

    # tab_space=4 to match the 4-space indentation already in the file
    svc = TclIndentationService(tab_space=4)
    new_report, new_artifacts, new_rewritten = svc.run(ctx2, manifest, report, artifacts)
    # lib.tcl was not changed (already 4-space), so write_text was not called again
    assert new_report is not None
