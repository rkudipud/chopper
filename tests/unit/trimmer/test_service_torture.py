"""Torture tests for :class:`TrimmerService` — every error + dry-run branch.

Complements :mod:`tests.unit.trimmer.test_service` by covering:

* ``_prepare_workspace`` failing with :class:`OSError` → ``VE-23`` path.
* ``_dispatch`` receiving :class:`FileTreatment.GENERATED` directly (bug
  path; the loop normally filters this out but the defensive check must
  still fire).
* ``_dispatch`` receiving an unknown treatment (drift guard).
* ``full_copy_file`` failing with :class:`OSError` → ``VE-25`` path.
* Dry-run plan reporting for PROC_TRIM and REMOVE treatments.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.adapters import InMemoryFS
from chopper.core.models import (
    CompiledManifest,
    DomainState,
    FileProvenance,
    FileTreatment,
    ParseResult,
    ProcEntry,
)
from chopper.trimmer.service import TrimmerService
from tests.unit.trimmer._helpers import BACKUP, DOMAIN, make_ctx

# ---------------------------------------------------------------------------
# Builders copied (minimal) from test_service.py to keep this file isolated.
# ---------------------------------------------------------------------------


def _proc(file: str, name: str, *, start: int, end: int) -> ProcEntry:
    path = Path(file)
    return ProcEntry(
        canonical_name=f"{path.as_posix()}::{name}",
        short_name=name,
        qualified_name=name,
        source_file=path,
        start_line=start,
        end_line=end,
        body_start_line=start + 1 if start + 1 <= end else start,
        body_end_line=end - 1 if end - 1 >= start else end,
        namespace_path="",
    )


def _manifest_full_copy_then_proc_trim_then_remove() -> CompiledManifest:
    """Manifest exercising all three writable treatments + GENERATED."""

    fd: dict[Path, FileTreatment] = {
        Path("a.tcl"): FileTreatment.FULL_COPY,
        Path("m.tcl"): FileTreatment.PROC_TRIM,
        Path("stages/s1.tcl"): FileTreatment.GENERATED,
        Path("z.tcl"): FileTreatment.REMOVE,
    }
    pv: dict[Path, FileProvenance] = {
        Path("a.tcl"): FileProvenance(path=Path("a.tcl"), treatment=FileTreatment.FULL_COPY, reason="fi-literal"),
        Path("m.tcl"): FileProvenance(
            path=Path("m.tcl"),
            treatment=FileTreatment.PROC_TRIM,
            reason="pi-additive",
            proc_model="additive",
        ),
        Path("stages/s1.tcl"): FileProvenance(
            path=Path("stages/s1.tcl"), treatment=FileTreatment.GENERATED, reason="fi-literal"
        ),
        Path("z.tcl"): FileProvenance(path=Path("z.tcl"), treatment=FileTreatment.REMOVE, reason="default-exclude"),
    }
    return CompiledManifest(file_decisions=fd, provenance=pv)


def _state(case: int, *, domain: bool = True, backup: bool = False) -> DomainState:
    return DomainState(
        case=case,  # type: ignore[arg-type]
        domain_exists=domain,
        backup_exists=backup,
        hand_edited=False,
    )


# ---------------------------------------------------------------------------
# Dry-run: every treatment kind should be represented in the plan-only report
# ---------------------------------------------------------------------------


def test_dry_run_plan_reports_all_non_generated_treatments() -> None:
    """Covers the dry-run PROC_TRIM + REMOVE outcome-emission branches."""
    fs = InMemoryFS()
    ctx, _ = make_ctx(fs=fs, dry_run=True)
    manifest = _manifest_full_copy_then_proc_trim_then_remove()
    parsed = ParseResult(files={}, index={})
    state = _state(1)
    report = TrimmerService().run(ctx, manifest, parsed, state)
    paths = {o.path.as_posix(): o.treatment for o in report.outcomes}
    # GENERATED is filtered out; the other three all emit an outcome.
    assert Path("stages/s1.tcl").as_posix() not in paths
    assert paths[Path("a.tcl").as_posix()] is FileTreatment.FULL_COPY
    assert paths[Path("m.tcl").as_posix()] is FileTreatment.PROC_TRIM
    assert paths[Path("z.tcl").as_posix()] is FileTreatment.REMOVE


# ---------------------------------------------------------------------------
# _prepare_workspace OSError → VE-23 (interrupted, no dispatch)
# ---------------------------------------------------------------------------


class _ExplodingFS(InMemoryFS):
    """FS adapter whose mkdir/rename/remove all raise ``PermissionError``."""

    def rename(self, src: Path, dst: Path) -> None:  # type: ignore[override]
        raise PermissionError(f"deny rename {src} → {dst}")


def test_prepare_workspace_oserror_emits_ve23_and_returns_interrupted() -> None:
    # Case 1 prep renames domain → backup; force a PermissionError on that.
    fs = _ExplodingFS({DOMAIN / "a.tcl": "x"})
    ctx, sink = make_ctx(fs=fs)
    manifest = CompiledManifest(
        file_decisions={Path("a.tcl"): FileTreatment.FULL_COPY},
        provenance={
            Path("a.tcl"): FileProvenance(path=Path("a.tcl"), treatment=FileTreatment.FULL_COPY, reason="fi-literal")
        },
    )
    parsed = ParseResult(files={}, index={})
    state = _state(1)
    report = TrimmerService().run(ctx, manifest, parsed, state)
    assert sink.codes() == ["VE-23"]
    assert report.rebuild_interrupted is True
    assert report.outcomes == ()


# ---------------------------------------------------------------------------
# _dispatch OSError during FULL_COPY → VE-25 interrupted
# ---------------------------------------------------------------------------


class _WriteFailingFS(InMemoryFS):
    """FS adapter that allows read but fails on write_text with OSError."""

    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:  # type: ignore[override]
        raise OSError("disk full")


def test_dispatch_oserror_emits_ve25_and_halts() -> None:
    # Case 3 (backup exists; no domain) — avoids the prep rename that
    # _WriteFailingFS doesn't override.
    fs = _WriteFailingFS({BACKUP / "a.tcl": "hi\n"})
    ctx, sink = make_ctx(fs=fs)
    manifest = CompiledManifest(
        file_decisions={Path("a.tcl"): FileTreatment.FULL_COPY},
        provenance={
            Path("a.tcl"): FileProvenance(path=Path("a.tcl"), treatment=FileTreatment.FULL_COPY, reason="fi-literal")
        },
    )
    parsed = ParseResult(files={}, index={})
    state = _state(3, domain=False, backup=True)
    report = TrimmerService().run(ctx, manifest, parsed, state)
    assert sink.codes() == ["VE-25"]
    assert report.rebuild_interrupted is True


# ---------------------------------------------------------------------------
# _dispatch direct call with GENERATED → ValueError (defensive guard)
# ---------------------------------------------------------------------------


def test_dispatch_receives_generated_raises_valueerror() -> None:
    """The dispatch loop filters GENERATED, but the defensive check in
    ``_dispatch`` must still raise if called directly (drift guard)."""
    fs = InMemoryFS()
    ctx, _ = make_ctx(fs=fs)
    trimmer = TrimmerService()
    with pytest.raises(ValueError, match="GENERATED"):
        trimmer._dispatch(
            ctx,
            Path("s.tcl"),
            FileTreatment.GENERATED,
            ParseResult(files={}, index={}),
            {},
        )


def test_dispatch_unknown_treatment_raises_valueerror() -> None:
    """If a fifth FileTreatment ever sneaks in, ``_dispatch`` refuses it."""

    class _FakeTreatment:
        """A sentinel that is not a valid :class:`FileTreatment` member."""

        def __repr__(self) -> str:
            return "<FAKE_TREATMENT>"

    fs = InMemoryFS()
    ctx, _ = make_ctx(fs=fs)
    trimmer = TrimmerService()
    with pytest.raises(ValueError, match="unknown FileTreatment"):
        trimmer._dispatch(
            ctx,
            Path("s.tcl"),
            _FakeTreatment(),  # type: ignore[arg-type]
            ParseResult(files={}, index={}),
            {},
        )


# ---------------------------------------------------------------------------
# _plan_only_report with unknown treatment (drift guard)
# ---------------------------------------------------------------------------


def test_plan_only_report_unknown_treatment_raises_valueerror() -> None:
    """Drift guard in the dry-run path: unknown treatment is a bug."""
    from chopper.trimmer.service import _plan_only_report

    # Fabricate a CompiledManifest with one file claiming a fake treatment.
    # CompiledManifest's __post_init__ only checks sort/uniqueness, not
    # enum membership, so we can smuggle a non-member in here.
    class _FakeTreatment:
        def __repr__(self) -> str:
            return "<FAKE>"

    fake = _FakeTreatment()
    path = Path("weird.tcl")
    fd = {path: fake}  # type: ignore[dict-item]
    pv = {
        path: FileProvenance(
            path=path,
            treatment=FileTreatment.FULL_COPY,  # placeholder — won't be checked
            reason="fi-literal",
        )
    }

    # Build manifest bypassing treatment parity — construct with matching
    # shape first then swap file_decisions under the hood isn't possible
    # because dataclass is frozen. Instead call the helper directly with
    # a manifest-like shim:
    class _ManifestShim:
        file_decisions = fd
        proc_decisions: dict[str, object] = {}
        provenance = pv

    with pytest.raises(ValueError, match="unknown FileTreatment"):
        _plan_only_report(_ManifestShim())  # type: ignore[arg-type]
