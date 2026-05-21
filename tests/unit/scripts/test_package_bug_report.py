from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "schemas" / "scripts" / "package_bug_report.py"


def test_package_bug_report_bundles_directory_and_report(tmp_path: Path) -> None:
    audit_dir = tmp_path / ".chopper"
    audit_dir.mkdir()
    (audit_dir / "diagnostics.json").write_text('{"diagnostics": []}\n', encoding="utf-8")
    (audit_dir / "trim_report.txt").write_text("trim ok\n", encoding="utf-8")
    report = tmp_path / "parser_bug.md"
    report.write_text("# parser bug\n", encoding="utf-8")
    output = tmp_path / "bundle.zip"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(audit_dir), str(report), "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert output.exists()
    with ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "bundle_manifest.txt" in names
        assert "inputs/00_.chopper/diagnostics.json" in names
        assert "inputs/00_.chopper/trim_report.txt" in names
        assert "inputs/01_parser_bug.md" in names


def test_package_bug_report_rejects_missing_input(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    output = tmp_path / "bundle.zip"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(missing), "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert not output.exists()
    assert "does not exist" in result.stdout
