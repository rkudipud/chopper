from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "file_bug_report.py"


def _payload(tmp_path: Path, attachments: list[str]) -> Path:
    payload_path = tmp_path / "payload.json"
    payload = {
        "repo": "rkudipud/chopper",
        "title": "[Bug] Example automation path",
        "command": "chopper trim --dry-run",
        "platform": "Linux",
        "ec_site": "local",
        "python_version": "Python 3.11.9",
        "what_happened": "Expected a clean dry run. Got a parser error instead.",
        "reproduce": "1. Run chopper trim --dry-run\n2. Observe the parser error",
        "terminal_output": "ERROR PE-02: parser failure",
        "audit_bundle": "Attached diagnostics.json and chopper_run.json.",
        "json_files": "base.json: {\"domain\": \"demo\"}",
        "additional_context": "Triggered by the companion automation test.",
        "attachments": attachments,
    }
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload_path


def test_file_bug_report_dry_run_writes_body_and_bundle(tmp_path: Path) -> None:
    audit_dir = tmp_path / ".chopper"
    audit_dir.mkdir()
    (audit_dir / "diagnostics.json").write_text('{"diagnostics": []}\n', encoding="utf-8")
    report = tmp_path / "notes.md"
    report.write_text("report body\n", encoding="utf-8")
    payload = _payload(tmp_path, [str(audit_dir), str(report)])
    output_dir = tmp_path / "out"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--payload", str(payload), "--output-dir", str(output_dir), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    body_path = output_dir / "bug_report_issue.md"
    bundle_path = output_dir / "bug_report_bundle.zip"
    assert body_path.exists()
    assert bundle_path.exists()
    body = body_path.read_text(encoding="utf-8")
    assert "### Which command triggered the bug?" in body
    assert "Companion note: a local evidence bundle was prepared separately." in body
    assert "Simple fallback behavior active" in result.stdout


def test_file_bug_report_create_uses_gh_issue_create(tmp_path: Path) -> None:
    audit_dir = tmp_path / ".chopper"
    audit_dir.mkdir()
    (audit_dir / "diagnostics.json").write_text('{"diagnostics": []}\n', encoding="utf-8")
    payload = _payload(tmp_path, [str(audit_dir)])
    output_dir = tmp_path / "out"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    args_file = tmp_path / "gh_args.txt"
    gh_path = bin_dir / "gh"
    gh_path.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$@\" > \"$GH_ARGS_FILE\"\n"
        "printf '%s\\n' 'https://github.com/rkudipud/chopper/issues/999'\n",
        encoding="utf-8",
    )
    gh_path.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["GH_ARGS_FILE"] = str(args_file)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--payload", str(payload), "--output-dir", str(output_dir), "--create"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert "Created GitHub issue: https://github.com/rkudipud/chopper/issues/999" in result.stdout
    gh_args = args_file.read_text(encoding="utf-8")
    assert "issue" in gh_args
    assert "create" in gh_args
    assert "--repo" in gh_args
    assert "rkudipud/chopper" in gh_args
    assert "--label" in gh_args
    assert "bug" in gh_args


def test_file_bug_report_create_falls_back_when_gh_is_missing(tmp_path: Path) -> None:
    audit_dir = tmp_path / ".chopper"
    audit_dir.mkdir()
    (audit_dir / "diagnostics.json").write_text('{"diagnostics": []}\n', encoding="utf-8")
    payload = _payload(tmp_path, [str(audit_dir)])
    output_dir = tmp_path / "out"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--payload", str(payload), "--output-dir", str(output_dir), "--create"],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": ""},
    )

    assert result.returncode == 0
    assert "falling back to local output" in result.stdout
    assert "`gh` was not found on PATH" in result.stdout
    assert (output_dir / "bug_report_issue.md").exists()


def test_file_bug_report_create_falls_back_when_gh_returns_error(tmp_path: Path) -> None:
    audit_dir = tmp_path / ".chopper"
    audit_dir.mkdir()
    (audit_dir / "diagnostics.json").write_text('{"diagnostics": []}\n', encoding="utf-8")
    payload = _payload(tmp_path, [str(audit_dir)])
    output_dir = tmp_path / "out"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh_path = bin_dir / "gh"
    gh_path.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' 'authentication required' >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gh_path.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--payload", str(payload), "--output-dir", str(output_dir), "--create"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert "falling back to local output" in result.stdout
    assert "authentication required" in result.stdout
    assert (output_dir / "bug_report_issue.md").exists()


def test_file_bug_report_rejects_missing_required_fields(tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"title": "[Bug] Missing data"}), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--payload", str(payload), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "payload field 'command'" in result.stdout
