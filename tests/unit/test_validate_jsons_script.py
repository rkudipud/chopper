"""The documented schema-check command works without a schema-dir override."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "schemas" / "scripts" / "validate_jsons.py"


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("kind", ["base", "feature", "project"])
def test_validator_finds_bundled_schemas_from_another_working_directory(
    tmp_path: Path, version: int, kind: str
) -> None:
    raw: dict[str, object] = {"$schema": f"{kind}-v{version}"}
    if kind == "base":
        raw.update(domain="d", files={"include": ["main.tcl"]})
    elif kind == "feature":
        raw["name"] = "f"
    else:
        raw.update(project="p", domain="d", base="jsons/base.json")
    path = tmp_path / "input.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), str(path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK " in result.stdout
