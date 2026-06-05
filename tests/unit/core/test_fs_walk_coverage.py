"""Per-file coverage tests for src/chopper/core/fs_walk.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from chopper.adapters.fs_memory import InMemoryFS
from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_walk_files_nonexistent_root_returns_empty() -> None:
    """Per ARCHITECTURE.md §5.3, walk_files on a missing root must return []
    so callers can treat an empty domain as a valid (trivially empty) result
    without special-casing the absence of the directory."""
    from chopper.core.fs_walk import walk_files

    fs = InMemoryFS()
    result = walk_files(fs, Path("/no/such/dir"))
    assert result == []


def test_walk_files_with_extension_filter() -> None:
    """walk_files honours the ``extensions`` parameter: only files whose
    suffix (lowercased) matches are returned.  This is used by the SLOC
    pipeline to restrict counting to text-like files."""
    from chopper.core.fs_walk import walk_files

    fs = InMemoryFS()
    fs.write_text(DOMAIN / "a.tcl", "x")
    fs.write_text(DOMAIN / "b.txt", "x")
    fs.write_text(DOMAIN / "c.tcl", "x")

    result = walk_files(fs, DOMAIN, extensions=[".tcl"])
    posix = {p.as_posix() for p in result}
    assert "a.tcl" in posix
    assert "c.tcl" in posix
    assert "b.txt" not in posix


def test_walk_files_oserror_on_list_skips_directory() -> None:
    """walk_files must continue walking other directories when fs.list()
    raises OSError for one directory.  This tolerates NFS permission errors
    without aborting the full domain enumeration."""

    class _BadList(InMemoryFS):
        def list(self, path: Path, *, pattern: str | None = None) -> tuple[Path, ...]:  # type: ignore[override]
            if path == DOMAIN / "blocked":
                raise OSError("permission denied")
            return super().list(path, pattern=pattern)

    fs = _BadList()
    fs.write_text(DOMAIN / "ok.tcl", "x")
    fs.mkdir(DOMAIN / "blocked", parents=True, exist_ok=True)
    fs.write_text(DOMAIN / "blocked" / "secret.tcl", "y")

    from chopper.core.fs_walk import walk_files

    result = walk_files(fs, DOMAIN)
    posix = {p.as_posix() for p in result}
    assert "ok.tcl" in posix
    assert "blocked/secret.tcl" not in posix


def test_walk_files_oserror_on_stat_skips_entry() -> None:
    """walk_files skips entries whose fs.stat() raises OSError.  This
    handles transient NFS failures on individual inodes."""

    class _StatFail(InMemoryFS):
        def stat(self, path: Path):  # type: ignore[override]
            if path == DOMAIN / "unstable.tcl":
                raise OSError("inode vanished")
            return super().stat(path)

    fs = _StatFail()
    fs.write_text(DOMAIN / "stable.tcl", "x")
    fs.write_text(DOMAIN / "unstable.tcl", "y")

    from chopper.core.fs_walk import walk_files

    result = walk_files(fs, DOMAIN)
    posix = {p.as_posix() for p in result}
    assert "stable.tcl" in posix
    assert "unstable.tcl" not in posix


def test_walk_files_skips_deeply_nested_excluded_dirs() -> None:
    """Excluded dir names are checked at any depth, not just the top level.
    A .chopper/ directory nested inside a feature subdirectory must also be
    excluded (ARCHITECTURE.md §5.3 exclusion contract)."""
    from chopper.core.fs_walk import walk_files

    fs = InMemoryFS()
    fs.write_text(DOMAIN / "sub" / "ok.tcl", "x")
    fs.write_text(DOMAIN / "sub" / ".chopper" / "audit.json", "{}")

    result = walk_files(fs, DOMAIN, exclude_dirs=(".chopper",))
    posix = {p.as_posix() for p in result}
    assert "sub/ok.tcl" in posix
    assert "sub/.chopper/audit.json" not in posix


def test_walk_files_skips_nested_excluded_dir_by_name() -> None:
    """walk_files must skip any directory whose NAME is in exclude_dirs, even when nested."""
    from chopper.core.fs_walk import walk_files

    fs = InMemoryFS()
    # root/sub/visible.tcl  → should be found
    # root/sub/.chopper/hidden.tcl → .chopper dir at depth > 1, must be excluded
    fs.write_text(Path("/root/sub/.chopper/hidden.tcl"), "secret")
    fs.write_text(Path("/root/sub/visible.tcl"), "public")

    result = walk_files(fs, Path("/root"))
    posix_paths = [p.as_posix() for p in result]

    assert "sub/visible.tcl" in posix_paths
    assert not any(".chopper" in p for p in posix_paths)


def test_walk_files_relative_to_valueerror_skips_child() -> None:
    """walk_files skips a child where relative_to raises ValueError (lines 118-119)."""
    from chopper.core.fs_walk import walk_files

    mock_fs = MagicMock()
    # Root is DOMAIN; child is /alien (NOT under DOMAIN) → relative_to raises ValueError
    alien = Path("/alien/outside.tcl")
    alien_stat = MagicMock()
    alien_stat.is_dir = False

    def fake_list(p: Path) -> list[Path]:
        if p == DOMAIN:
            return [alien]
        return []

    mock_fs.list.side_effect = fake_list
    mock_fs.stat.return_value = alien_stat

    result = walk_files(mock_fs, DOMAIN)
    assert result == []


def test_walk_files_excludes_json_and_instructions_md() -> None:
    """walk_files excludes .json files and instructions.md per ARCHITECTURE.md §5.5.13."""
    from chopper.core.fs_walk import walk_files

    fs = InMemoryFS()
    fs.write_text(DOMAIN / "base.json", "{}")
    fs.write_text(DOMAIN / "sub" / "feature.json", "{}")
    fs.write_text(DOMAIN / "instructions.md", "# howto")
    fs.write_text(DOMAIN / "lib.tcl", "proc foo {} {}")

    result = walk_files(fs, DOMAIN)
    posix = [p.as_posix() for p in result]
    assert "lib.tcl" in posix
    assert "base.json" not in posix
    assert "sub/feature.json" not in posix
    assert "instructions.md" not in posix


def test_walk_files_chopper_direct_child_of_root_skipped() -> None:
    """walk_files skips .chopper/ when it is a DIRECT child of root (parts[0] check, line 126)."""
    from chopper.core.fs_walk import walk_files

    fs = InMemoryFS()
    fs.write_text(DOMAIN / ".chopper" / "audit.json", "{}")
    fs.write_text(DOMAIN / "lib.tcl", "proc foo {} {}")

    result = walk_files(fs, DOMAIN)
    posix = [p.as_posix() for p in result]
    assert "lib.tcl" in posix
    assert not any(".chopper" in p for p in posix)
