"""Behavior tests for the standalone source-to-release P4 planner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "plan_p4_sync.py"


def test_planner_emits_edit_and_add_for_changed_and_new_source_files(tmp_path: Path) -> None:
    """A changed source file needs edit; a source-only file needs add."""

    source = tmp_path / "dist"
    target = tmp_path / "release"
    source.mkdir()
    target.mkdir()
    (source / "same.tcl").write_text("same\n")
    (target / "same.tcl").write_text("same\n")
    (source / "changed.tcl").write_text("new\n")
    (target / "changed.tcl").write_text("old\n")
    (source / "jsons").mkdir()
    (source / "jsons" / "added.json").write_text("{}\n")
    (target / "target-only.tcl").write_text("legacy\n")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), str(target)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert [line for line in result.stdout.splitlines() if line.startswith("p4 ")] == [
        f"p4 edit -t text+x {target / 'changed.tcl'}",
        f"p4 add -t text+x {target / 'jsons' / 'added.json'}",
    ]
    assert "# target-only.tcl" in result.stdout


def test_planner_filters_to_requested_file_glob_and_filetype(tmp_path: Path) -> None:
    """A JSON-only release plan must not include Tcl files or mark JSON executable."""

    source = tmp_path / "dist"
    target = tmp_path / "release"
    source.mkdir()
    target.mkdir()
    (source / "changed.tcl").write_text("new\n")
    (target / "changed.tcl").write_text("old\n")
    (source / "base.json").write_text("new\n")
    (target / "base.json").write_text("old\n")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(source),
            str(target),
            "--include",
            "*.json",
            "--filetype",
            "text",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert [line for line in result.stdout.splitlines() if line.startswith("p4 ")] == [
        f"p4 edit -t text {target / 'base.json'}"
    ]
