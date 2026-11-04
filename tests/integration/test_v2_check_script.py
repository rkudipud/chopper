"""The migrate-v1-to-v2 skill's ``check_v2.py`` grades real Chopper audit bundles.

Each scenario builds the same small ``apr_fc`` domain, writes one JSON set,
dry-runs Chopper in-process, and feeds the resulting ``.chopper/`` bundle to the
checker. The scenarios mirror what users hand the agent: an untouched v1 set, a
schema-only flip, a clean v2 migration, and a migration with the classic
mistakes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from chopper.cli.main import main

_SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "skills" / "migrate-v1-to-v2" / "scripts" / "check_v2.py"

_TCL = {
    "vars.tcl": "set core_mode 1\n",
    "procs/core_procs.tcl": (
        "proc core_setup {} {\n    core_helper\n    return 1\n}\n"
        "proc core_helper {} {\n    return 2\n}\n"
        "proc core_debug {} {\n    return 3\n}\n"
    ),
    "fdr_vars.tcl": "set fdr_mode 1\n",
    "tech_fdr_vars.tcl": "set fdr_mode 2\n",
    "project_fdr_vars.tcl": "set fdr_mode 3\n",
    "procs/fdr_procs.tcl": "proc fdr_run {} {\n    return 1\n}\nproc fdr_debug {} {\n    return 0\n}\n",
    "dop_vars.tcl": "set dop_mode 1\n",
    "procs/dop_procs.tcl": "proc dop_run {} {\n    return 1\n}\nproc dop_report {} {\n    return 2\n}\n",
    "utils/report.tcl": "set report_mode 1\n",
}

Layers = dict[str, dict[str, Any]]


def _v1_layers(version: str = "v1") -> Layers:
    return {
        "base": {
            "$schema": f"base-{version}",
            "domain": "apr_fc",
            "description": "core",
            "files": {"include": ["vars.tcl", "utils/*.tcl"], "exclude": ["utils/old_debug.tcl"]},
            "procedures": {"include": [{"file": "procs/core_procs.tcl", "procs": ["core_setup"]}]},
            "stages": [
                {
                    "name": "main",
                    "load_from": "",
                    "command": "tclsh main.tcl",
                    "steps": ["iproc_source -file vars.tcl", "core_setup"],
                }
            ],
        },
        "fdr": {
            "$schema": f"feature-{version}",
            "name": "fdr",
            "description": "fdr",
            "files": {"include": ["fdr_vars.tcl", "tech_fdr_vars.tcl"]},
            "procedures": {"include": [{"file": "procs/fdr_procs.tcl", "procs": ["fdr_run"]}]},
            "flow_actions": [
                {
                    "action": "add_step_after",
                    "stage": "main",
                    "reference": "core_setup",
                    "items": ["iproc_source -file fdr_vars.tcl -optional", "fdr_run"],
                }
            ],
        },
        "dop": {
            "$schema": f"feature-{version}",
            "name": "dop",
            "files": {"include": ["dop_vars.tcl"]},
            "procedures": {"include": [{"file": "procs/dop_procs.tcl", "procs": ["dop_run", "dop_report"]}]},
        },
        "legacy": {"$schema": "feature-v1", "name": "legacy", "description": "old", "files": {"include": ["x.tcl"]}},
        "project": {
            "$schema": f"project-{version}",
            "project": "P",
            "domain": "apr_fc",
            "base": "jsons/base.json",
            "features": ["jsons/features/fdr.feature.json", "jsons/features/dop.feature.json"],
        },
    }


def _good_layers() -> Layers:
    layers = _v1_layers("v2")
    base, fdr, dop = layers["base"], layers["fdr"], layers["dop"]
    base["vars_file"] = "vars.tcl"
    base["files"] = {"include": ["utils/*.tcl"]}
    base["procedures"]["include"][0]["procs"] = ["core_setup", "core_helper"]
    base["stages"][0]["steps"] = ["core_setup"]
    fdr["vars_file"] = "fdr_vars.tcl"
    del fdr["files"]
    fdr["flow_actions"][0]["items"] = ["fdr_run"]
    dop.update(description="dop", vars_file="dop_vars.tcl")
    del dop["files"]
    layers["legacy"]["$schema"] = "feature-v2"
    layers["project"]["base"] = "jsons/apr_fc.json"
    layers["project"]["features"].append("jsons/features/legacy.feature.json")
    layers["legacy"]["files"] = {"include": ["utils/report.tcl"]}
    return layers


def _flawed_layers() -> Layers:
    layers = _v1_layers("v2")
    layers["fdr"]["vars_file"] = "fdr_vars.tcl"
    layers["dop"]["vars_file"] = "dop_var.tcl"
    return layers


def _write_domain(root: Path, layers: Layers) -> Path:
    domain = root / "apr_fc"
    for rel, text in _TCL.items():
        (domain / rel).parent.mkdir(parents=True, exist_ok=True)
        (domain / rel).write_text(text, encoding="utf-8")
    base_rel = layers["project"]["base"]
    paths = {
        "base": base_rel,
        "fdr": "jsons/features/fdr.feature.json",
        "dop": "jsons/features/dop.feature.json",
        "legacy": "jsons/features/legacy.feature.json",
        "project": "jsons/project.json",
    }
    for key, rel in paths.items():
        (domain / rel).parent.mkdir(parents=True, exist_ok=True)
        (domain / rel).write_text(json.dumps(layers[key], indent=2) + "\n", encoding="utf-8")
    return domain


def _trim(domain: Path, *, dry_run: bool = True) -> int:
    args = ["--plain", "trim", "--domain", str(domain), "--project", str(domain / "jsons" / "project.json")]
    if dry_run:
        args.insert(2, "--dry-run")
    return main(args)


def _snapshot(root: Path, name: str, layers: Layers) -> Path:
    domain = _write_domain(root / name, layers)
    _trim(domain)
    snap = root / "snap" / name
    shutil.copytree(domain / ".chopper", snap)
    return snap


def _check(audit: Path, *extra: str) -> tuple[int, dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), str(audit), "--json", *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stderr == "", result.stderr
    return result.returncode, json.loads(result.stdout)


def _slugs(report: dict[str, Any]) -> set[tuple[str, str]]:
    return {(s["slug"], s["target"]) for s in report["suggestions"]}


def _gate(report: dict[str, Any]) -> dict[str, str]:
    return {g["check"]: g["status"] for g in report["gate"]}


@pytest.fixture(scope="module")
def snaps(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    root = tmp_path_factory.mktemp("v2check")
    built: dict[str, Path] = {}
    makers = {"v1": _v1_layers, "flip": lambda: _v1_layers("v2"), "good": _good_layers, "flawed": _flawed_layers}

    def get(name: str) -> Path:
        if name not in built:
            built[name] = _snapshot(root, name, makers[name]())
        return built[name]

    return get


def test_clean_v2_migration_passes_with_full_adoption(snaps: Callable[[str], Path]) -> None:
    rc, report = _check(snaps("good"), "--baseline", str(snaps("v1")), "--require-adoption")

    assert rc == 0, report
    assert report["result"] == "pass"
    assert report["schema"] == "v2"
    assert set(_gate(report).values()) <= {"pass", "skip"}
    assert report["adoption"]["level"] == "full"
    assert not [d for d in report["delta"] if d["class"] == "unexpected"]
    assert report["preview"]["apr_fc_feature_vars.tcl"] == [
        "iproc_source -file fdr_vars.tcl -optional",
        "iproc_source -file tech_fdr_vars.tcl -optional",
        "iproc_source -file project_fdr_vars.tcl -optional",
        "",
        "iproc_source -file dop_vars.tcl -optional",
        "iproc_source -file tech_dop_vars.tcl -optional",
        "iproc_source -file project_dop_vars.tcl -optional",
    ]
    assert set(report["preview"]) == {"apr_fc_feature_vars.tcl"}
    review = {d["line"] for d in report["delta"] if d["class"] == "review"}
    assert any("project_fdr_vars.tcl" in line for line in review)


def test_schema_only_flip_is_not_a_finished_migration(snaps: Callable[[str], Path]) -> None:
    rc, report = _check(snaps("flip"), "--baseline", str(snaps("v1")))

    assert rc == 0
    assert report["adoption"]["level"] == "schema-only"
    assert report["preview"] == {"apr_fc_feature_vars.tcl": []}
    assert {
        ("pointer-candidate", "feature:fdr"),
        ("pointer-candidate", "feature:dop"),
        ("pointer-candidate", "base"),
    } <= _slugs(report)

    rc, report = _check(snaps("flip"), "--require-adoption")
    assert rc == 1
    assert _gate(report)["adoption"] == "fail"


@pytest.mark.parametrize(
    ("version", "layer", "kind", "pointer", "level", "strict_rc"),
    [
        ("v1", None, None, None, "none", 1),
        ("v2", None, None, None, "not-applicable", 1),
        ("v2", "base", "vars_file", "vars.tcl", "full", 0),
        ("v2", "fdr", "vars_file", "fdr_vars.tcl", "full", 0),
    ],
)
def test_strict_adoption_requires_a_pointer_even_without_candidates(
    tmp_path: Path,
    version: str,
    layer: str | None,
    kind: str | None,
    pointer: str | None,
    level: str,
    strict_rc: int,
) -> None:
    layers = _v1_layers(version)
    for key in ("base", "fdr", "dop"):
        layers[key] = {
            "$schema": f"{'base' if key == 'base' else 'feature'}-{version}",
            **({"domain": "apr_fc"} if key == "base" else {"name": key}),
            "files": {"include": ["utils/report.tcl"]},
        }
    if layer is not None and kind is not None:
        layers[layer][kind] = pointer
    domain = _write_domain(tmp_path, layers)
    assert _trim(domain) == 0

    rc, report = _check(domain / ".chopper")
    assert rc == 0, report
    assert report["result"] == "pass"
    assert report["adoption"]["level"] == level
    assert report["adoption"]["candidates"] == []
    assert len(report["adoption"]["pointers"]) == (0 if layer is None else 1)
    assert _gate(report)["adoption"] == "skip"

    rc, report = _check(domain / ".chopper", "--require-adoption")
    assert rc == strict_rc, report
    assert report["result"] == ("fail" if strict_rc else "pass")
    assert _gate(report)["adoption"] == ("fail" if strict_rc else "pass")
    assert {status for name, status in _gate(report).items() if name != "adoption"} <= {"pass", "skip"}


def test_strict_adoption_accepts_a_pointer_with_remaining_candidates(tmp_path: Path) -> None:
    layers = _v1_layers("v2")
    layers["base"]["vars_file"] = "vars.tcl"
    domain = _write_domain(tmp_path, layers)
    assert _trim(domain) == 0

    rc, report = _check(domain / ".chopper", "--require-adoption")
    assert rc == 0, report
    assert report["result"] == "pass"
    assert report["adoption"]["level"] == "partial"
    assert report["adoption"]["pointers"] == ["base vars_file vars.tcl"]
    assert report["adoption"]["candidates"]
    assert _gate(report)["adoption"] == "pass"


def test_flawed_migration_fails_with_an_edit_for_every_mistake(snaps: Callable[[str], Path]) -> None:
    rc, report = _check(snaps("flawed"), "--baseline", str(snaps("v1")))

    assert rc == 1
    assert _gate(report)["pointer-targets"] == "fail"
    assert {
        ("missing-pointer", "feature:dop"),
        ("double-sourcing-step", "feature:fdr"),
        ("redundant-pointer-include", "feature:fdr"),
        ("manual-variant-include", "feature:fdr"),
        ("dormant-variant", "feature:fdr"),
        ("base-name", "base"),
        ("step-source-form", "base"),
        ("traced-callee-dropped", "base"),
        ("stale-exclude", "base"),
        ("missing-description", "feature:dop"),
        ("orphan-json", "jsons/features/legacy.feature.json"),
    } <= _slugs(report)
    typo = next(s for s in report["suggestions"] if s["slug"] == "missing-pointer")
    assert "dop_vars.tcl" in typo["edit"]
    unexpected = {d["line"] for d in report["delta"] if d["class"] == "unexpected"}
    assert any("VW-27" in line for line in unexpected)
    manifest = json.loads((snaps("flawed") / "compiled_manifest.json").read_text(encoding="utf-8"))
    fdr_file = next(f for f in manifest["files"] if f["path"] == "procs/fdr_procs.tcl")
    assert fdr_file["treatment"] == "proc-trim"
    assert fdr_file["surviving_procs"] == ["procs/fdr_procs.tcl::fdr_run"]


def test_v1_bundle_gets_a_migration_plan(snaps: Callable[[str], Path]) -> None:
    rc, report = _check(snaps("v1"))

    assert rc == 0
    assert report["schema"] == "v1"
    assert report["adoption"]["level"] == "none"
    assert {
        ("unflipped-json", "project"),
        ("pointer-candidate", "feature:fdr"),
        ("pointer-candidate", "feature:dop"),
        ("dormant-variant", "feature:fdr"),
        ("base-name", "base"),
        ("traced-callee-dropped", "base"),
        ("stale-exclude", "base"),
        ("missing-description", "feature:dop"),
    } <= _slugs(report)
    fdr = [s for s in report["suggestions"] if s == {**s, "slug": "pointer-candidate", "target": "feature:fdr"}]
    assert all("procs" not in s["edit"] for s in fdr), "fdr keeps only fdr_run; a procs pointer would revert that"


def test_vars_pointer_that_starts_loading_an_unreferenced_file_is_flagged(snaps: Callable[[str], Path]) -> None:
    # v1 keeps dop_vars.tcl but no step or kept Tcl file loads it; fdr_vars.tcl is sourced by an fdr step.
    _, v1 = _check(snaps("v1"))
    candidates = {s["target"]: s["message"] for s in v1["suggestions"] if s["slug"] == "pointer-candidate"}
    dop = [s["message"] for s in v1["suggestions"] if s["slug"] == "pointer-candidate" and s["target"] == "feature:dop"]
    assert len(dop) == 1
    assert all("Nothing references it today" in m for m in dop)
    assert "Nothing references it today" not in candidates["feature:fdr"]

    _, good = _check(snaps("good"), "--baseline", str(snaps("v1")))
    fresh = [s for s in good["suggestions"] if s["slug"] == "newly-sourced"]
    assert {(s["target"], s["level"]) for s in fresh} == {("feature:dop", "review")}
    assert len(fresh) == 1
    assert "dop_vars.tcl" in fresh[0]["message"]

    _, alone = _check(snaps("good"))
    assert not [s for s in alone["suggestions"] if s["slug"] == "newly-sourced"], "needs a baseline to know"


def test_preview_matches_the_files_a_live_trim_writes(tmp_path: Path) -> None:
    domain = _write_domain(tmp_path, _good_layers())
    assert _trim(domain, dry_run=False) == 0

    rc, report = _check(domain / ".chopper")

    assert rc == 0, report
    assert _gate(report)["generated-content"] == "pass"
    for name, lines in report["preview"].items():
        written = (domain / name).read_text(encoding="utf-8").split("# Feature ", 1)[1].splitlines()[2:]
        assert written == lines


def test_text_report_is_stable_across_runs(snaps: Callable[[str], Path]) -> None:
    args = [sys.executable, str(_SCRIPT), str(snaps("flawed")), "--baseline", str(snaps("v1"))]
    first = subprocess.run(args, capture_output=True, text=True, check=False)
    second = subprocess.run(args, capture_output=True, text=True, check=False)

    assert first.returncode == 1
    assert first.stdout == second.stdout
    assert first.stdout.rstrip().endswith("RESULT: FAIL")


def test_a_failed_run_fails_the_gate(tmp_path: Path) -> None:
    layers = _v1_layers("v2")
    layers["dop"]["$schema"] = "feature-v1"
    domain = _write_domain(tmp_path, layers)
    assert _trim(domain) == 1

    rc, report = _check(domain / ".chopper")

    assert rc == 1
    assert _gate(report)["run-ok"] == "fail"
