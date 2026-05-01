"""Mode-bit preservation tests for the trimmer's per-file write helpers.

These tests exercise :func:`chopper.trimmer.file_writer.full_copy_file` and
:func:`chopper.trimmer.file_writer.proc_trim_file` against a *real*
``LocalFS`` adapter and ``tmp_path``, because the bug they cover is
specifically about ``Path.write_text`` not propagating source ``st_mode``.
The in-memory adapter used elsewhere in :mod:`chopper.trimmer` has no
notion of file modes, so this regression cannot be caught against it.

The bug was: every file rebuilt by ``chopper trim`` came out with default
umask permissions instead of the mode bits the source file had in
``<domain>_backup/``. Concretely, every executable script in the input
domain lost its ``+x`` bit on the rebuilt side.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from chopper.adapters import LocalFS
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models import ParsedFile, ProcEntry
from chopper.trimmer.file_writer import full_copy_file, proc_trim_file

# POSIX mode-bit semantics don't apply on Windows: ``os.chmod`` can only
# toggle the read-only flag, not the executable / group / world bits the
# trimmer's mode-preservation contract is about. The bug fixed by
# :func:`chopper.trimmer.file_writer._mirror_mode` is also a POSIX-only
# regression (Linux EDA grid nodes), so guarding the suite to POSIX is
# both correct and aligned with the production target.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX mode bits not honored by Windows os.chmod; bug is Linux-only",
)


class _NullSink:
    def emit(self, d: Diagnostic) -> None: ...  # pragma: no cover
    def snapshot(self) -> tuple[Diagnostic, ...]: ...  # pragma: no cover
    def finalize(self) -> DiagnosticSummary: ...  # pragma: no cover


class _NullProgress:
    def phase_started(self, phase: Phase) -> None: ...  # pragma: no cover
    def phase_done(self, phase: Phase) -> None: ...  # pragma: no cover
    def step(self, message: str) -> None: ...  # pragma: no cover


def _make_ctx(tmp_path: Path, *, dry_run: bool = False) -> ChopperContext:
    domain = tmp_path / "domain"
    backup = tmp_path / "domain_backup"
    audit = domain / ".chopper"
    domain.mkdir()
    backup.mkdir()
    cfg = RunConfig(
        domain_root=domain,
        backup_root=backup,
        audit_root=audit,
        strict=False,
        dry_run=dry_run,
    )
    return ChopperContext(config=cfg, fs=LocalFS(), diag=_NullSink(), progress=_NullProgress())


def _executable_mode(p: Path) -> bool:
    return bool(p.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def test_full_copy_file_preserves_executable_bit(tmp_path: Path) -> None:
    """Regression: a ``+x`` source file in backup must remain ``+x`` after FULL_COPY."""

    ctx = _make_ctx(tmp_path)
    rel = Path("run_me.tcl")
    src = ctx.config.backup_root / rel
    src.write_text("#!/usr/bin/env tclsh\nputs hi\n")
    os.chmod(src, 0o755)
    assert _executable_mode(src), "fixture sanity: src must be +x before trim"

    full_copy_file(ctx, rel, procs_in_file=())

    dst = ctx.config.domain_root / rel
    assert dst.is_file()
    src_mode = stat.S_IMODE(src.stat().st_mode)
    dst_mode = stat.S_IMODE(dst.stat().st_mode)
    assert dst_mode == src_mode, f"FULL_COPY did not preserve mode bits: src=0o{src_mode:o} dst=0o{dst_mode:o}"
    assert _executable_mode(dst)


def test_full_copy_file_preserves_non_executable_mode(tmp_path: Path) -> None:
    """A non-executable source must end up non-executable (and exact-mode-equal)."""

    ctx = _make_ctx(tmp_path)
    rel = Path("data/notes.txt")
    src = ctx.config.backup_root / rel
    src.parent.mkdir(parents=True)
    src.write_text("just text\n")
    os.chmod(src, 0o640)

    full_copy_file(ctx, rel, procs_in_file=())

    dst = ctx.config.domain_root / rel
    assert stat.S_IMODE(dst.stat().st_mode) == 0o640
    assert not _executable_mode(dst)


def test_proc_trim_file_preserves_executable_bit(tmp_path: Path) -> None:
    """Same regression for the PROC_TRIM rewrite path: rewriting content
    must not strip the source ``+x`` bit."""

    ctx = _make_ctx(tmp_path)
    rel = Path("trim_me.tcl")
    src = ctx.config.backup_root / rel
    src.write_text("proc keep {} { puts ok }\nproc drop {} { puts bye }\n")
    os.chmod(src, 0o755)
    assert _executable_mode(src)

    keep = ProcEntry(
        canonical_name=f"{rel.as_posix()}::keep",
        short_name="keep",
        qualified_name="keep",
        source_file=rel,
        start_line=1,
        end_line=1,
        body_start_line=1,
        body_end_line=1,
        namespace_path="::",
    )
    drop = ProcEntry(
        canonical_name=f"{rel.as_posix()}::drop",
        short_name="drop",
        qualified_name="drop",
        source_file=rel,
        start_line=2,
        end_line=2,
        body_start_line=2,
        body_end_line=2,
        namespace_path="::",
    )
    parsed = ParsedFile(path=rel, procs=(keep, drop), encoding="utf-8")

    proc_trim_file(ctx, rel, parsed=parsed, keep_canonical=frozenset({keep.canonical_name}))

    dst = ctx.config.domain_root / rel
    assert dst.is_file()
    assert stat.S_IMODE(dst.stat().st_mode) == stat.S_IMODE(src.stat().st_mode)
    assert _executable_mode(dst)


def test_dry_run_does_not_touch_destination(tmp_path: Path) -> None:
    """Dry-run must remain side-effect free; mode preservation has no opportunity to fire."""

    ctx = _make_ctx(tmp_path, dry_run=True)
    rel = Path("preview_me.tcl")
    src = ctx.config.backup_root / rel
    src.write_text("# hi\n")
    os.chmod(src, 0o755)

    outcome = full_copy_file(ctx, rel, procs_in_file=())

    dst = ctx.config.domain_root / rel
    assert not dst.exists(), "dry-run must not create the destination file"
    # Outcome is still produced so the audit bundle can describe the planned action.
    assert outcome.path == rel
