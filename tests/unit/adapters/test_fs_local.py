"""Smoke tests for :class:`chopper.adapters.LocalFS` against a real tmp dir."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.adapters import LocalFS


def test_write_read_roundtrip(tmp_path: Path) -> None:
    fs = LocalFS()
    target = tmp_path / "sub" / "a.tcl"
    target.parent.mkdir()
    fs.write_text(target, "body")
    assert fs.read_text(target) == "body"


def test_exists_and_stat(tmp_path: Path) -> None:
    fs = LocalFS()
    f = tmp_path / "x"
    f.write_text("abcd", encoding="utf-8")
    assert fs.exists(f)
    st = fs.stat(f)
    assert st.size == 4
    assert st.is_dir is False
    st_dir = fs.stat(tmp_path)
    assert st_dir.is_dir is True


def test_list_sorted_with_pattern(tmp_path: Path) -> None:
    fs = LocalFS()
    (tmp_path / "b.tcl").write_text("", encoding="utf-8")
    (tmp_path / "a.tcl").write_text("", encoding="utf-8")
    (tmp_path / "c.json").write_text("", encoding="utf-8")
    all_items = [p.name for p in fs.list(tmp_path)]
    assert all_items == sorted(all_items)
    tcl_only = [p.name for p in fs.list(tmp_path, pattern="*.tcl")]
    assert tcl_only == ["a.tcl", "b.tcl"]


def test_rename_and_remove(tmp_path: Path) -> None:
    fs = LocalFS()
    src = tmp_path / "old"
    src.mkdir()
    (src / "a").write_text("1", encoding="utf-8")
    dst = tmp_path / "new"
    fs.rename(src, dst)
    assert not src.exists()
    assert (dst / "a").read_text() == "1"
    fs.remove(dst, recursive=True)
    assert not dst.exists()


def test_remove_file(tmp_path: Path) -> None:
    fs = LocalFS()
    f = tmp_path / "x"
    f.write_text("", encoding="utf-8")
    fs.remove(f)
    assert not f.exists()


def test_mkdir_parents_exist_ok(tmp_path: Path) -> None:
    fs = LocalFS()
    target = tmp_path / "a" / "b" / "c"
    fs.mkdir(target, parents=True, exist_ok=False)
    assert target.is_dir()
    fs.mkdir(target, exist_ok=True)  # second call fine with exist_ok


def test_copy_tree_excludes_top_level_dot_chopper(tmp_path: Path) -> None:
    fs = LocalFS()
    src = tmp_path / "dom"
    src.mkdir()
    (src / "a.tcl").write_text("A", encoding="utf-8")
    chopper = src / ".chopper"
    chopper.mkdir()
    (chopper / "run.json").write_text("{}", encoding="utf-8")
    sub = src / "sub"
    sub.mkdir()
    (sub / "b.tcl").write_text("B", encoding="utf-8")

    dst = tmp_path / "bk"
    fs.copy_tree(src, dst)
    assert (dst / "a.tcl").read_text() == "A"
    assert (dst / "sub" / "b.tcl").read_text() == "B"
    assert not (dst / ".chopper").exists()
    # Original intact
    assert chopper.exists()


def test_remove_dir_nonrecursive_raises_if_nonempty(tmp_path: Path) -> None:
    fs = LocalFS()
    d = tmp_path / "d"
    d.mkdir()
    (d / "x").write_text("", encoding="utf-8")
    with pytest.raises(OSError):
        fs.remove(d, recursive=False)
