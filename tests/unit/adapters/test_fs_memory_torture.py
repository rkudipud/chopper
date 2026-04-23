"""Torture tests for :class:`InMemoryFS` — every error path + edge case.

The main trimmer/runner suites already exercise the happy paths, but
several defensive branches in :mod:`chopper.adapters.fs_memory` are not
hit by end-to-end flows (e.g. reading a non-existent file, listing a
missing directory, pattern-filtering, mkdir parent-missing). This file
explicitly drives each of them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.adapters import InMemoryFS

# ---------------------------------------------------------------------------
# Read / metadata surface
# ---------------------------------------------------------------------------


def test_read_text_missing_raises_filenotfound() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError, match="no such file"):
        fs.read_text(Path("/nowhere"))


def test_stat_returns_is_dir_for_directory() -> None:
    fs = InMemoryFS({Path("/a/b/c.tcl"): "x"})
    st = fs.stat(Path("/a/b"))
    assert st.is_dir is True
    assert st.size == 0


def test_stat_missing_raises_filenotfound() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError, match="no such path"):
        fs.stat(Path("/ghost"))


def test_list_missing_directory_raises_filenotfound() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError, match="no such directory"):
        fs.list(Path("/ghost"))


def test_list_pattern_filters_results() -> None:
    fs = InMemoryFS(
        {
            Path("/d/a.tcl"): "",
            Path("/d/b.tcl"): "",
            Path("/d/c.txt"): "",
        }
    )
    results = [p.name for p in fs.list(Path("/d"), pattern="*.tcl")]
    assert results == ["a.tcl", "b.tcl"]


# ---------------------------------------------------------------------------
# Mutating surface
# ---------------------------------------------------------------------------


def test_rename_missing_source_raises_filenotfound() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError, match="rename source"):
        fs.rename(Path("/ghost"), Path("/elsewhere"))


def test_rename_existing_target_raises_fileexists() -> None:
    fs = InMemoryFS({Path("/a.tcl"): "1", Path("/b.tcl"): "2"})
    with pytest.raises(FileExistsError, match="rename target"):
        fs.rename(Path("/a.tcl"), Path("/b.tcl"))


def test_remove_nonempty_directory_without_recursive_raises() -> None:
    fs = InMemoryFS({Path("/dir/a.tcl"): "x"})
    with pytest.raises(OSError, match="directory not empty"):
        fs.remove(Path("/dir"), recursive=False)


def test_remove_missing_path_raises_filenotfound() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError, match="no such path"):
        fs.remove(Path("/ghost"))


def test_remove_recursive_deletes_subtree() -> None:
    fs = InMemoryFS(
        {
            Path("/dir/a.tcl"): "1",
            Path("/dir/sub/b.tcl"): "2",
        }
    )
    fs.remove(Path("/dir"), recursive=True)
    assert not fs.exists(Path("/dir"))
    assert not fs.exists(Path("/dir/a.tcl"))
    assert not fs.exists(Path("/dir/sub/b.tcl"))


def test_mkdir_over_existing_file_raises_fileexists() -> None:
    fs = InMemoryFS({Path("/f"): "x"})
    with pytest.raises(FileExistsError, match="file at target"):
        fs.mkdir(Path("/f"))


def test_mkdir_existing_dir_without_exist_ok_raises() -> None:
    fs = InMemoryFS({Path("/dir/x"): ""})
    with pytest.raises(FileExistsError, match="already exists"):
        fs.mkdir(Path("/dir"))


def test_mkdir_missing_parent_without_parents_raises_filenotfound() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError, match="parent does not exist"):
        fs.mkdir(Path("/a/b/c"), parents=False)


def test_copy_tree_missing_source_raises_filenotfound() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError, match="copy_tree source"):
        fs.copy_tree(Path("/ghost"), Path("/dst"))


def test_copy_tree_excludes_dot_chopper_subtree() -> None:
    fs = InMemoryFS(
        {
            Path("/src/a.tcl"): "1",
            Path("/src/sub/b.tcl"): "2",
            Path("/src/.chopper/prev.json"): "{}",
            Path("/src/.chopper/sub/nested.json"): "{}",
        }
    )
    fs.copy_tree(Path("/src"), Path("/dst"))
    assert fs.read_text(Path("/dst/a.tcl")) == "1"
    assert fs.read_text(Path("/dst/sub/b.tcl")) == "2"
    assert not fs.exists(Path("/dst/.chopper"))
    assert not fs.exists(Path("/dst/.chopper/prev.json"))
