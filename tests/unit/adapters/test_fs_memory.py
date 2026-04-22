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
