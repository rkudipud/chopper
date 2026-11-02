"""V2 sourcing pointers must be literal file paths, not directories."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.config.schema import validate_json
from chopper.core.diagnostics import Diagnostic


@pytest.mark.parametrize("kind", ["base", "feature"])
@pytest.mark.parametrize("pointer", ["vars", "procs"])
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
def test_sourcing_pointers_reject_directory_and_drive_paths(kind: str, pointer: str, entry: str) -> None:
    raw: dict[str, object] = {"$schema": f"{kind}-v2", pointer: entry}
    if kind == "base":
        raw.update(domain="d", files={"include": ["main.tcl"]})
    else:
        raw["name"] = "f"
    diagnostics: list[Diagnostic] = []

    assert validate_json(raw, Path("input.json"), diagnostics.append) is False
    assert [d.code for d in diagnostics] == ["VE-02"]
