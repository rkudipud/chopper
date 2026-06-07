"""Per-file coverage tests for src/chopper/adapters/fs_memory.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_fs_memory_rename_missing_source_raises() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError):
        fs.rename(Path("/nope"), Path("/somewhere"))


def test_fs_memory_rename_existing_destination_raises() -> None:
    fs = InMemoryFS()
    fs.write_text(Path("/a"), "1")
    fs.write_text(Path("/b"), "2")
    with pytest.raises(FileExistsError):
        fs.rename(Path("/a"), Path("/b"))


def test_fs_memory_mkdir_no_parents_raises_when_parent_missing() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError):
        fs.mkdir(Path("/x/y/z"))


def test_fs_memory_mkdir_existing_no_exist_ok_raises() -> None:
    fs = InMemoryFS()
    fs.mkdir(Path("/x"), parents=True)
    with pytest.raises(FileExistsError):
        fs.mkdir(Path("/x"))


def test_fs_memory_write_text_over_directory_raises() -> None:
    fs = InMemoryFS()
    fs.mkdir(Path("/d"), parents=True)
    with pytest.raises(IsADirectoryError):
        fs.write_text(Path("/d"), "x")


def test_fs_memory_copy_tree_missing_source_raises() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError):
        fs.copy_tree(Path("/nope"), Path("/dst"))


def test_fs_memory_copy_file_missing_source_raises() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError):
        fs.copy_file(Path("/nope"), Path("/dst"))


def test_fs_memory_copy_file_into_directory_raises() -> None:
    fs = InMemoryFS()
    fs.write_text(Path("/src"), "x")
    fs.mkdir(Path("/d"), parents=True)
    with pytest.raises(IsADirectoryError):
        fs.copy_file(Path("/src"), Path("/d"))


def test_fs_memory_remove_missing_path_raises() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError):
        fs.remove(Path("/missing"))


def test_fs_memory_remove_nonempty_dir_without_recursive_raises() -> None:
    fs = InMemoryFS()
    fs.write_text(Path("/d/a"), "x")
    with pytest.raises(OSError):
        fs.remove(Path("/d"))


def test_fs_memory_remove_existing_file_returns_silently() -> None:
    fs = InMemoryFS()
    fs.write_text(Path("/a"), "x")
    fs.remove(Path("/a"))
    assert not fs.exists(Path("/a"))


def test_fs_memory_copy_tree_skips_chopper_subtree() -> None:
    fs = InMemoryFS()
    fs.write_text(Path("/src/keep.tcl"), "x")
    fs.write_text(Path("/src/.chopper/audit.json"), "{}")
    fs.copy_tree(Path("/src"), Path("/dst"))
    assert fs.exists(Path("/dst/keep.tcl"))
    assert not fs.exists(Path("/dst/.chopper/audit.json"))


def test_fs_memory_copy_file_adds_parent_dirs() -> None:
    """copy_file must register all ancestor directories of the destination
    so subsequent exists/list calls see the correct tree structure."""
    fs = InMemoryFS()
    fs.write_text(Path("/src/file.tcl"), "x")
    fs.copy_file(Path("/src/file.tcl"), Path("/dst/sub/file.tcl"))
    assert fs.exists(Path("/dst/sub/file.tcl"))
    assert fs.exists(Path("/dst/sub"))
    assert fs.exists(Path("/dst"))


def test_fs_memory_mkdir_exist_ok_true_is_noop() -> None:
    """mkdir with exist_ok=True on an existing directory must not raise."""
    fs = InMemoryFS()
    fs.mkdir(Path("/d"), parents=True)
    fs.mkdir(Path("/d"), exist_ok=True)  # must not raise


def test_fs_memory_read_text_returns_content() -> None:
    """read_text must return the exact string written by write_text."""
    fs = InMemoryFS()
    fs.write_text(Path("/f.tcl"), "hello world\n")
    assert fs.read_text(Path("/f.tcl")) == "hello world\n"


def test_fs_memory_mkdir_raises_file_exists_without_exist_ok() -> None:
    """mkdir on an existing directory without exist_ok=True must raise FileExistsError."""
    fs = InMemoryFS()
    fs.mkdir(Path("/d"), parents=True)
    with pytest.raises(FileExistsError):
        fs.mkdir(Path("/d"), exist_ok=False)


def test_fs_memory_copy_file_raises_when_dst_is_directory() -> None:
    """copy_file must raise IsADirectoryError when the destination is an existing directory."""
    fs = InMemoryFS()
    fs.write_text(Path("/src.tcl"), "x")
    fs.mkdir(Path("/d/sub"), parents=True)
    with pytest.raises(IsADirectoryError):
        fs.copy_file(Path("/src.tcl"), Path("/d/sub"))


def test_fs_memory_copy_tree_nested_dirs_preserved() -> None:
    """copy_tree must replicate nested directories and files in the destination tree."""
    fs = InMemoryFS()
    fs.write_text(Path("/src/a/b/c.tcl"), "content")
    fs.copy_tree(Path("/src"), Path("/dst"))
    assert fs.exists(Path("/dst/a/b/c.tcl"))
    assert fs.read_text(Path("/dst/a/b/c.tcl")) == "content"
    assert fs.exists(Path("/dst/a/b"))
    assert fs.exists(Path("/dst/a"))


def test_fs_memory_rename_skips_unrelated_files() -> None:
    """rename iterates all _files entries; unrelated ones are skipped (121->120 branch)."""
    fs = InMemoryFS()
    fs.write_text(Path("/src/a.tcl"), "content_a")
    fs.write_text(Path("/other/b.tcl"), "content_b")  # unrelated -- not under /src
    fs.rename(Path("/src"), Path("/dst"))
    assert fs.exists(Path("/dst/a.tcl"))
    assert not fs.exists(Path("/src/a.tcl"))
    assert fs.read_text(Path("/other/b.tcl")) == "content_b"


def test_fs_memory_mkdir_root_anchor_parent_skips_inner_raise() -> None:
    """mkdir(parents=False) on /child -- parent is '/' anchor -> inner raise skipped (166->168)."""
    fs = InMemoryFS()
    # /child has parent '/', which is in ("/", ".", "") -> inner FileNotFoundError NOT raised
    fs.mkdir(Path("/child"), parents=False)
    assert fs.exists(Path("/child"))


def test_fs_memory_copy_tree_excludes_chopper_subtree() -> None:
    """copy_tree skips files inside .chopper/ at root of src (line 199 continue branch)."""
    fs = InMemoryFS()
    fs.write_text(Path("/src/lib.tcl"), "proc foo {} {}")
    fs.write_text(Path("/src/.chopper/audit.json"), "{}")
    fs.copy_tree(Path("/src"), Path("/dst"))
    assert fs.exists(Path("/dst/lib.tcl"))
    assert not fs.exists(Path("/dst/.chopper/audit.json"))


def test_fs_memory_copy_tree_skips_unrelated_files() -> None:
    """copy_tree iterates all _files; files not under src are skipped (line 197 continue)."""
    fs = InMemoryFS()
    fs.write_text(Path("/src/lib.tcl"), "proc foo {} {}")
    fs.write_text(Path("/other/unrelated.tcl"), "proc bar {} {}")  # NOT under /src
    fs.copy_tree(Path("/src"), Path("/dst"))
    assert fs.exists(Path("/dst/lib.tcl"))
    assert not fs.exists(Path("/dst/unrelated.tcl"))
    assert fs.exists(Path("/other/unrelated.tcl"))  # original preserved
