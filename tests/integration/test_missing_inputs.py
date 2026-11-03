"""Missing user inputs must stop before parsing or destructive output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chopper.cli.main import main


@pytest.mark.parametrize("layer", ["base", "feature"])
@pytest.mark.parametrize("direction", ["include", "exclude"])
@pytest.mark.parametrize("backup", [False, True])
def test_missing_proc_file_is_a_p1_error(tmp_path: Path, layer: str, direction: str, backup: bool) -> None:
    domain = tmp_path / "domain"
    domain.mkdir()
    source = tmp_path / "domain_backup" if backup else domain
    source.mkdir(exist_ok=True)
    (source / "core.tcl").write_text("proc core {} { return 1 }\n", encoding="utf-8")
    base = tmp_path / "base.json"
    base_data = {"$schema": "base-v1", "domain": "domain", "files": {"include": ["core.tcl"]}}
    procedures = {direction: [{"file": "missing[procs].tcl", "procs": ["keep"]}]}
    args = ["--plain", "validate", "--domain", str(domain), "--base", str(base)]
    if layer == "base":
        base_data["procedures"] = procedures
    else:
        feature = tmp_path / "extra.feature.json"
        feature.write_text(
            json.dumps({"$schema": "feature-v1", "name": "extra", "procedures": procedures}), encoding="utf-8"
        )
        args.extend(["--features", str(feature)])
    base.write_text(json.dumps(base_data), encoding="utf-8")

    assert main(args) == 1
    diagnostics = json.loads((domain / ".chopper" / "diagnostics.json").read_text(encoding="utf-8"))["diagnostics"]
    missing = [diag for diag in diagnostics if diag["code"] == "VE-06"]
    assert len(missing) == 1
    assert f"procedures.{direction}" in missing[0]["message"]
    assert missing[0]["file"] == "missing[procs].tcl"
    assert missing[0]["phase"] == "P1"
    assert not (domain / ".chopper" / "internal-error.log").exists()


@pytest.mark.parametrize("backup", [False, True])
def test_proc_paths_are_literal_and_use_pristine_source(tmp_path: Path, backup: bool) -> None:
    domain = tmp_path / "domain"
    domain.mkdir()
    source = tmp_path / "domain_backup" if backup else domain
    source.mkdir(exist_ok=True)
    (source / "lib[1].tcl").write_text("proc keep {} { return 1 }\n", encoding="utf-8")
    base = tmp_path / "base.json"
    base.write_text(
        json.dumps(
            {
                "$schema": "base-v1",
                "domain": "domain",
                "procedures": {"include": [{"file": "lib[1].tcl", "procs": ["keep"]}]},
            }
        ),
        encoding="utf-8",
    )
    assert main(["--plain", "--strict", "validate", "--domain", str(domain), "--base", str(base)]) == 0


@pytest.mark.parametrize("command", ["validate", "trim", "loc"])
@pytest.mark.parametrize("directory", [False, True])
def test_invalid_tool_command_path_is_a_user_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str, directory: bool
) -> None:
    domain = tmp_path / "domain"
    domain.mkdir()
    (domain / "core.tcl").write_text("proc core {} { return 1 }\n", encoding="utf-8")
    base = tmp_path / "base.json"
    base.write_text(
        json.dumps({"$schema": "base-v1", "domain": "domain", "files": {"include": ["core.tcl"]}}), encoding="utf-8"
    )
    commands = tmp_path / "tools.commands"
    if directory:
        commands.mkdir()

    rc = main(["--plain", command, "--domain", str(domain), "--base", str(base), "--tool-commands", str(commands)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "VE-43" in captured.err
    assert "tools.commands" in captured.err
    assert "Traceback" not in captured.err
    assert not (domain / ".chopper" / "internal-error.log").exists()
    assert not (tmp_path / "domain_backup").exists()
    assert (domain / "core.tcl").read_text(encoding="utf-8") == "proc core {} { return 1 }\n"


@pytest.mark.parametrize("example", ["02_base_procs_only", "06_base_procs_and_stages"])
def test_json_only_examples_report_missing_domain_files(tmp_path: Path, example: str) -> None:
    template = Path(__file__).resolve().parents[2] / "examples" / example / "jsons" / "base.json"
    base = tmp_path / "base.json"
    base.write_bytes(template.read_bytes())
    domain = tmp_path / example
    domain.mkdir()

    assert main(["--plain", "validate", "--domain", str(domain), "--base", str(base)]) == 1
    diagnostics = json.loads((domain / ".chopper" / "diagnostics.json").read_text(encoding="utf-8"))["diagnostics"]
    assert any(diag["code"] == "VE-06" for diag in diagnostics)
    assert not (domain / ".chopper" / "internal-error.log").exists()


def test_existing_tool_command_files_extend_the_pool(tmp_path: Path) -> None:
    domain = tmp_path / "domain"
    domain.mkdir()
    (domain / "core.tcl").write_text(
        "proc core {} {\n site_custom_tool_alpha\n site_custom_tool_beta\n return 1\n}\n", encoding="utf-8"
    )
    base = tmp_path / "base.json"
    base.write_text(
        json.dumps({"$schema": "base-v1", "domain": "domain", "files": {"include": ["core.tcl"]}}), encoding="utf-8"
    )
    first = tmp_path / "first.commands"
    second = tmp_path / "second.commands"
    first.write_text("site_custom_tool_alpha\n", encoding="utf-8")
    second.write_text("site_custom_tool_beta\n", encoding="utf-8")

    assert (
        main(
            [
                "--plain",
                "--strict",
                "validate",
                "--domain",
                str(domain),
                "--base",
                str(base),
                "--tool-commands",
                str(first),
                "--tool-commands",
                str(second),
            ]
        )
        == 0
    )
    diagnostics = json.loads((domain / ".chopper" / "diagnostics.json").read_text(encoding="utf-8"))["diagnostics"]
    assert [diag["code"] for diag in diagnostics].count("TI-01") == 2
