"""Per-file coverage tests for src/chopper/core/file_perms.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations



from unittest.mock import patch


from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_mirror_perms_plus_exec_tolerates_oserror(tmp_path: Path) -> None:
    """mirror_perms_plus_exec must not raise even when chmod/copymode fail.
    This is essential for in-memory adapters and read-only EDA tool areas."""
    from chopper.core.file_perms import mirror_perms_plus_exec

    src = tmp_path / "src.tcl"
    dst = tmp_path / "dst.tcl"
    src.write_text("x")
    dst.write_text("x")

    with patch("shutil.copymode", side_effect=OSError("read-only")):
        # Must not raise; OSError is silently swallowed per spec.
        mirror_perms_plus_exec(src, dst)


def test_mirror_perms_plus_exec_noop_on_nonexistent_paths(tmp_path: Path) -> None:
    """mirror_perms_plus_exec is a no-op (no error) when paths do not exist on disk."""
    from chopper.core.file_perms import mirror_perms_plus_exec

    # Neither path exists — must not raise.
    mirror_perms_plus_exec(tmp_path / "ghost_src.tcl", tmp_path / "ghost_dst.tcl")


def test_mirror_perms_plus_exec_calls_copymode_and_ensure_executable(tmp_path: Path) -> None:
    """mirror_perms_plus_exec calls shutil.copymode then ensure_executable (lines 48-49)."""
    from chopper.core.file_perms import mirror_perms_plus_exec

    src = tmp_path / "src.tcl"
    dst = tmp_path / "dst.tcl"
    src.write_text("proc foo {} {}")
    dst.write_text("proc foo {} {}")

    with patch("shutil.copymode") as mock_cm:
        with patch("chopper.core.file_perms.ensure_executable") as mock_ea:
            mirror_perms_plus_exec(src, dst)

    mock_cm.assert_called_once()
    mock_ea.assert_called_once_with(dst)


def test_ensure_executable_oserror_swallowed(tmp_path: Path) -> None:
    """ensure_executable swallows OSError from chmod (lines 48-49)."""
    from chopper.core.file_perms import ensure_executable

    dst = tmp_path / "dst.tcl"
    dst.write_text("proc foo {} {}")
    # Patch chmod to raise OSError → except block at lines 48-49 is hit
    with patch("pathlib.Path.chmod", side_effect=OSError("permission denied")):
        ensure_executable(dst)  # must not raise


# ================================================================
# BATCH 3 — targeted tests for remaining < 99% files
