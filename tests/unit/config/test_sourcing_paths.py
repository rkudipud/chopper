"""V2 sourcing pointers must be literal file paths, not directories."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.config.schema import validate_json
from chopper.core.diagnostics import Diagnostic


@pytest.mark.parametrize("kind", ["base", "feature"])
def test_vars_file_accepts_literal_file_path(kind: str) -> None:
    raw: dict[str, object] = {"$schema": f"{kind}-v2", "vars_file": "dir/vars.tcl"}
    if kind == "base":
        raw.update(domain="d", files={"include": ["main.tcl"]})
    else:
        raw["name"] = "f"

    assert validate_json(raw, Path("input.json"), lambda _: None) is True


@pytest.mark.parametrize("kind", ["base", "feature"])
@pytest.mark.parametrize(
    "entry",
    [
        ".",
        "./",
        "./vars.tcl",
        "dir/./vars.tcl",
        "dir/..",
        "dir/",
        "C:/vars.tcl",
        "C:vars.tcl",
        "feature\n/../vars.tcl",
        "feature\n//vars.tcl",
        "feature\n/./vars.tcl",
        "feature\n/",
    ],
)
def test_vars_file_rejects_directory_and_drive_paths(kind: str, entry: str) -> None:
    raw: dict[str, object] = {"$schema": f"{kind}-v2", "vars_file": entry}
    if kind == "base":
        raw.update(domain="d", files={"include": ["main.tcl"]})
    else:
        raw["name"] = "f"
    diagnostics: list[Diagnostic] = []

    assert validate_json(raw, Path("input.json"), diagnostics.append) is False
    assert [d.code for d in diagnostics] == ["VE-02"]
