"""Tests for the in-memory filesystem adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.adapters import InMemoryFS


def test_read_text_returns_stored_content() -> None:
    fs = InMemoryFS({Path("/d/a.tcl"): "proc foo {} {}"})
    assert fs.read_text(Path("/d/a.tcl")) == "proc foo {} {}"


def test_read_text_missing_raises() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError):
        fs.read_text(Path("/nope"))


def test_exists_reports_files_and_implicit_dirs() -> None:
    fs = InMemoryFS({Path("/d/sub/a.tcl"): ""})
    assert fs.exists(Path("/d/sub/a.tcl"))
    assert fs.exists(Path("/d/sub"))
    assert fs.exists(Path("/d"))
    assert not fs.exists(Path("/x"))


def test_write_text_creates_file_and_implicit_dirs() -> None:
    fs = InMemoryFS()
    fs.write_text(Path("/d/sub/b.tcl"), "body")
    assert fs.exists(Path("/d/sub/b.tcl"))
    assert fs.exists(Path("/d/sub"))
    assert fs.read_text(Path("/d/sub/b.tcl")) == "body"


def test_list_returns_sorted_children() -> None:
    fs = InMemoryFS(
        {
            Path("/d/b.tcl"): "",
            Path("/d/a.tcl"): "",
            Path("/d/sub/c.tcl"): "",
        }
    )
    result = [p.as_posix() for p in fs.list(Path("/d"))]
    assert result == ["/d/a.tcl", "/d/b.tcl", "/d/sub"]


def test_list_pattern_filters() -> None:
    fs = InMemoryFS({Path("/d/a.tcl"): "", Path("/d/b.json"): ""})
    result = [p.name for p in fs.list(Path("/d"), pattern="*.tcl")]
    assert result == ["a.tcl"]


def test_mkdir_and_remove_recursive() -> None:
    fs = InMemoryFS()
    fs.mkdir(Path("/d"), parents=True, exist_ok=False)
    fs.mkdir(Path("/d/sub"), parents=False, exist_ok=False)
    assert fs.exists(Path("/d/sub"))
    fs.remove(Path("/d"), recursive=True)
    assert not fs.exists(Path("/d"))


def test_mkdir_exist_ok() -> None:
    fs = InMemoryFS({Path("/d/a"): ""})
    fs.mkdir(Path("/d"), exist_ok=True)
    with pytest.raises(FileExistsError):
        fs.mkdir(Path("/d"), exist_ok=False)


def test_rename_moves_subtree() -> None:
    fs = InMemoryFS(
        {
            Path("/d/a.tcl"): "A",
            Path("/d/sub/b.tcl"): "B",
        }
    )
    fs.rename(Path("/d"), Path("/d_backup"))
    assert not fs.exists(Path("/d/a.tcl"))
    assert fs.exists(Path("/d_backup/a.tcl"))
    assert fs.read_text(Path("/d_backup/sub/b.tcl")) == "B"


def test_copy_tree_excludes_dot_chopper_at_top() -> None:
    fs = InMemoryFS(
        {
            Path("/d/a.tcl"): "A",
            Path("/d/.chopper/run.json"): "{}",
            Path("/d/sub/.chopper/kept.txt"): "kept",  # deeper .chopper is NOT excluded
            Path("/d/sub/b.tcl"): "B",
        }
    )
    fs.copy_tree(Path("/d"), Path("/backup"))
    assert fs.read_text(Path("/backup/a.tcl")) == "A"
    assert fs.read_text(Path("/backup/sub/b.tcl")) == "B"
    assert fs.read_text(Path("/backup/sub/.chopper/kept.txt")) == "kept"
    assert not fs.exists(Path("/backup/.chopper"))
    # Original still intact
    assert fs.exists(Path("/d/.chopper/run.json"))


def test_remove_non_empty_dir_requires_recursive() -> None:
    fs = InMemoryFS({Path("/d/a.tcl"): ""})
    with pytest.raises(OSError):
        fs.remove(Path("/d"), recursive=False)


def test_stat_reports_size_for_file_and_dir() -> None:
    fs = InMemoryFS({Path("/d/a.tcl"): "abcd"})
    assert fs.stat(Path("/d/a.tcl")).size == 4
    assert not fs.stat(Path("/d/a.tcl")).is_dir
    assert fs.stat(Path("/d")).is_dir


# ---------------------------------------------------------------------------
# Merged from test_fs_memory_torture.py (spec: module-aligned test file per source).
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
