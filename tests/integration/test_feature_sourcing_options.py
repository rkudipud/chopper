"""V1/v2 sourcing contracts across every base-option combination."""

from __future__ import annotations

import itertools
import json
import shutil
from pathlib import Path

import pytest

from chopper.cli.main import main
from chopper.core.models_common import FileTreatment

from .test_feature_vars import _domain as _vars_domain
from .test_feature_vars import _run, _write

_SWITCHES = ("cross_validate", "generate_stack", "indent", "insert_markers")
_OPTIONS = tuple(dict(zip(_SWITCHES, flags, strict=True)) for flags in itertools.product((False, True), repeat=4))


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("dry_run", [True, False], ids=["dry", "live"])
@pytest.mark.parametrize("standalone", [False, True], ids=["tcl", "standalone"])
@pytest.mark.parametrize("options", _OPTIONS, ids=lambda opts: ",".join(f"{k}={int(v)}" for k, v in opts.items()))
def test_sourcing_files_across_all_base_options(
    tmp_path: Path, version: int, dry_run: bool, standalone: bool, options: dict[str, bool]
) -> None:
    domain = _vars_domain(tmp_path)
    for path in (domain / "jsons").rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["$schema"] = data["$schema"].replace("v2", f"v{version}")
        if version == 1:
            data.pop("vars_file", None)
        if path.name == "apr_fc.json":
            data["options"] = options
            data["procedures"] = {"include": [{"file": "shared.tcl", "procs": ["keep"]}]}
            data["stages"] = [
                {
                    "name": "run",
                    "load_from": "",
                    "command": "tool -f run.tcl",
                    "steps": ["set stage 1"],
                    "standalone_stack": standalone,
                }
            ]
        elif path.name == "fdr.feature.json":
            data["flow_actions"] = [
                {
                    "action": "add_step_after",
                    "stage": "run",
                    "reference": "set stage 1",
                    "items": ["set feature 1"],
                }
            ]
        _write(path, json.dumps(data))
    project = domain / "project.json"
    data = json.loads(project.read_text(encoding="utf-8"))
    data["$schema"] = f"project-v{version}"
    _write(project, json.dumps(data))
    _write(domain / "shared.tcl", "proc keep {} {\nreturn 1\n}\nproc drop {} { return 0 }\n")

    sink, result = _run(domain, dry_run=dry_run)

    assert result.exit_code == 0, [(d.code, d.message) for d in sink.snapshot()]
    assert result.manifest is not None
    sourcing = {Path("apr_fc_feature_vars.tcl")}
    generated = {p for p, treatment in result.manifest.file_decisions.items() if treatment is FileTreatment.GENERATED}
    driver = Path("run.stack" if standalone else "run.tcl")
    expected = {driver}
    if version == 2:
        expected.update(sourcing)
    if options["generate_stack"]:
        expected.add(Path("apr_fc.stack"))
    assert generated == expected

    if dry_run:
        assert all(not (domain / p).exists() for p in expected)
        assert not domain.with_name("apr_fc_backup").exists()
        return

    driver_text = (domain / driver).read_text(encoding="utf-8")
    assert "set stage 1" in driver_text and "set feature 1" in driver_text
    assert ("## CHOPPER: BEGIN" in driver_text) is (options["insert_markers"] and not standalone)
    assert "iproc_source" not in driver_text
    trimmed = (domain / "shared.tcl").read_text(encoding="utf-8")
    assert "proc keep" in trimmed and "proc drop" not in trimmed
    assert ("## CHOPPER: BEGIN" in trimmed) is options["insert_markers"]
    if options["indent"]:
        assert "\n    return 1\n" in trimmed
    else:
        assert "\nreturn 1\n" in trimmed
    if options["generate_stack"]:
        stack = (domain / "apr_fc.stack").read_text(encoding="utf-8")
        path = Path("apr_fc_feature_vars.tcl")
        assert (f"I {path.as_posix()}\n" in stack) is (version == 2)
    else:
        assert not (domain / "apr_fc.stack").exists()
    assert (domain / "apr_fc_feature_vars.tcl").exists() is (version == 2)
    assert not (domain / "apr_fc_feature_procs.tcl").exists()


@pytest.mark.parametrize("features", [(), ("fdr",), ("dop",), ("fdr", "dop"), ("dop", "fdr")])
def test_only_selected_features_contribute_in_recipe_order(tmp_path: Path, features: tuple[str, ...]) -> None:
    domain = _vars_domain(tmp_path)
    project = domain / "project.json"
    data = json.loads(project.read_text(encoding="utf-8"))
    data["features"] = [f"jsons/features/{feature}.feature.json" for feature in features]
    if not features:
        del data["features"]
    _write(project, json.dumps(data))

    sink, result = _run(domain, dry_run=False)

    assert result.exit_code == 0, [d.code for d in sink.snapshot()]
    text = (domain / "apr_fc_feature_vars.tcl").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.startswith("iproc_source ")]
    expected = []
    for feature in features:
        directory = "dop/" if feature == "dop" else ""
        expected.extend(
            f"iproc_source -file {directory}{prefix}{feature}_vars.tcl -optional"
            for prefix in ("", "tech_", "project_")
        )
    assert lines == expected
    assert not (domain / "apr_fc_feature_procs.tcl").exists()


@pytest.mark.parametrize("strict", [False, True])
def test_missing_pointer_strict_changes_exit_policy_not_diagnostics(tmp_path: Path, strict: bool) -> None:
    domain = _vars_domain(tmp_path)
    (domain / "fdr_vars.tcl").unlink()

    sink, result = _run(domain, dry_run=True, strict=strict)

    matching = [d for d in sink.snapshot() if d.code == "VW-27"]
    assert len(matching) == 1
    assert matching[0].severity == "warning"
    assert result.exit_code == (1 if strict else 0)


@pytest.mark.parametrize("versions", list(itertools.product((1, 2), repeat=3)))
def test_every_project_base_feature_version_combination(tmp_path: Path, versions: tuple[int, int, int]) -> None:
    domain = _vars_domain(tmp_path)
    project_version, base_version, feature_version = versions
    paths = [(domain / "project.json", project_version), (domain / "jsons/apr_fc.json", base_version)]
    paths.extend((path, feature_version) for path in (domain / "jsons/features").glob("*.json"))
    for path, version in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["$schema"] = raw["$schema"].replace("v2", f"v{version}")
        if version == 1:
            raw.pop("vars_file", None)
        _write(path, json.dumps(raw))

    sink, result = _run(domain, dry_run=True)

    mixed = len(set(versions)) != 1
    assert result.exit_code == (1 if mixed else 0)
    assert ("VE-41" in [d.code for d in sink.snapshot()]) is mixed
    assert not (domain / "apr_fc_feature_vars.tcl").exists()
    assert not domain.with_name("apr_fc_backup").exists()


@pytest.mark.parametrize("version", [1, 2])
def test_generate_stack_without_stages_is_noop(tmp_path: Path, version: int) -> None:
    domain = _vars_domain(tmp_path)
    for path in [domain / "project.json", *(domain / "jsons").rglob("*.json")]:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["$schema"] = data["$schema"].replace("v2", f"v{version}")
        if version == 1:
            data.pop("vars_file", None)
        if path.name == "apr_fc.json":
            data["options"] = {"generate_stack": True}
        _write(path, json.dumps(data))

    sink, result = _run(domain, dry_run=False)

    assert result.exit_code == 0, [d.code for d in sink.snapshot()]
    assert not (domain / "apr_fc.stack").exists()
    assert (domain / "apr_fc_feature_vars.tcl").exists() is (version == 2)


def test_runnable_v2_example_through_all_four_cli_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    example = Path(__file__).resolve().parents[2] / "examples" / "16_feature_vars"
    domain = tmp_path / "apr_fc"
    shutil.copytree(example, domain)
    project = domain / "project.json"
    recipe = project.read_text(encoding="utf-8")
    selection = ["--domain", str(domain), "--project", str(project)]

    for command in ("validate", "loc"):
        assert main(["--strict", "--plain", command, *selection]) == 0, capsys.readouterr()
    assert not domain.with_name("apr_fc_backup").exists()

    assert main(["--strict", "--plain", "trim", *selection, "--dry-run"]) == 0, capsys.readouterr()
    assert not (domain / "apr_fc_feature_vars.tcl").exists()
    assert main(["--strict", "--plain", "trim", *selection]) == 0, capsys.readouterr()

    generated = ("apr_fc_feature_vars.tcl", "apr_fc.stack", "main.tcl")
    p4 = (domain / ".chopper/p4_commands.txt").read_text(encoding="utf-8")
    for name in generated:
        assert (domain / name).is_file()
        assert f"p4 add -t text+x {name}" in p4
    stack = (domain / "apr_fc.stack").read_text(encoding="utf-8")
    assert "I apr_fc_feature_vars.tcl\n" in stack
    assert "feature_procs" not in stack
    _write(project, recipe)
    assert main(["--strict", "--plain", "trim", *selection]) == 0, capsys.readouterr()
    assert main(["--plain", "cleanup", "--domain", str(domain), "--confirm"]) == 0, capsys.readouterr()
    assert not domain.with_name("apr_fc_backup").exists()


def test_literal_vars_file_pointer_survives_f1_and_generated_p6_checks(tmp_path: Path) -> None:
    domain = _vars_domain(tmp_path)
    pointer = "feature dir/$name;f{_vars.tcl"
    feature = domain / "jsons/features/fdr.feature.json"
    raw = json.loads(feature.read_text(encoding="utf-8"))
    raw["vars_file"] = pointer
    _write(feature, json.dumps(raw))
    _write(domain / pointer, "set example 1\n")

    sink, result = _run(domain, dry_run=False)

    assert result.exit_code == 0, [(d.code, d.message) for d in sink.snapshot()]
    assert (domain / pointer).read_text(encoding="utf-8") == "set example 1\n"
    text = (domain / "apr_fc_feature_vars.tcl").read_text(encoding="utf-8")
    assert "feature\\ dir/\\$name\\;f\\{_vars.tcl -optional" in text
