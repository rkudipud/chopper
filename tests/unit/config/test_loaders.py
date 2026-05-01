"""Unit tests for :mod:`chopper.config.loaders` — hydration + topo-sort."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.config.loaders import (
    load_base,
    load_feature,
    load_project,
    topo_sort_features,
)
from chopper.core.diagnostics import Diagnostic
from chopper.core.models_config import (
    AddStageAction,
    AddStepAction,
    BaseJson,
    FeatureJson,
    LoadFromAction,
    RemoveStageAction,
    RemoveStepAction,
    ReplaceStageAction,
    ReplaceStepAction,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_base(raw: dict, path: Path = Path("base.json")) -> tuple[BaseJson, list[Diagnostic]]:
    diags: list[Diagnostic] = []
    result = load_base(raw, path, diags.append)
    return result, diags


def _collect_feat(raw: dict, path: Path = Path("feat.json")) -> tuple[FeatureJson, list[Diagnostic]]:
    diags: list[Diagnostic] = []
    result = load_feature(raw, path, diags.append)
    return result, diags


# ---------------------------------------------------------------------------
# load_base
# ---------------------------------------------------------------------------


class TestLoadBase:
    def test_minimal(self) -> None:
        raw = {
            "$schema": "base-v1",
            "domain": "my_domain",
            "files": {"include": ["setup.tcl"]},
        }
        base, diags = _collect_base(raw)
        assert base.domain == "my_domain"
        assert "setup.tcl" in base.files.include
        assert diags == []

    def test_optional_fields_default(self) -> None:
        raw = {
            "$schema": "base-v1",
            "domain": "d",
            "files": {"include": ["a.tcl"]},
        }
        base, _ = _collect_base(raw)
        assert base.owner is None
        assert base.vendor is None
        assert base.tool is None
        assert base.description is None
        assert base.options.cross_validate is True  # default
        assert base.stages == ()

    def test_options_cross_validate_false(self) -> None:
        raw = {
            "$schema": "base-v1",
            "domain": "d",
            "files": {"include": ["a.tcl"]},
            "options": {"cross_validate": False},
        }
        base, _ = _collect_base(raw)
        assert base.options.cross_validate is False

    def test_procedures_include_hydrated(self) -> None:
        raw = {
            "$schema": "base-v1",
            "domain": "d",
            "procedures": {"include": [{"file": "a.tcl", "procs": ["foo", "bar"]}]},
        }
        base, diags = _collect_base(raw)
        assert diags == []
        assert len(base.procedures.include) == 1
        ref = base.procedures.include[0]
        assert ref.file == Path("a.tcl")
        assert "foo" in ref.procs
        assert "bar" in ref.procs

    def test_ve03_on_empty_procs_in_include(self) -> None:
        raw = {
            "$schema": "base-v1",
            "domain": "d",
            "procedures": {"include": [{"file": "a.tcl", "procs": []}]},
        }
        base, diags = _collect_base(raw)
        assert any(d.code == "VE-03" for d in diags)
        # Entry with empty procs is skipped
        assert base.procedures.include == ()

    def test_ve03_on_empty_procs_in_exclude(self) -> None:
        raw = {
            "$schema": "base-v1",
            "domain": "d",
            "files": {"include": ["a.tcl"]},
            "procedures": {"exclude": [{"file": "a.tcl", "procs": []}]},
        }
        _, diags = _collect_base(raw)
        assert any(d.code == "VE-03" for d in diags)

    def test_stage_def_hydrated(self) -> None:
        raw = {
            "$schema": "base-v1",
            "domain": "d",
            "stages": [
                {
                    "name": "setup",
                    "load_from": "prev",
                    "steps": ["source a.tcl"],
                    "exit_codes": [0, 3],
                    "command": "-xt vw Ishell",
                    "dependencies": ["init"],
                    "run_mode": "parallel",
                    "language": "python",
                }
            ],
        }
        base, _ = _collect_base(raw)
        assert len(base.stages) == 1
        s = base.stages[0]
        assert s.name == "setup"
        assert s.load_from == "prev"
        assert s.steps == ("source a.tcl",)
        assert s.exit_codes == (0, 3)
        assert s.command == "-xt vw Ishell"
        assert s.run_mode == "parallel"
        assert s.language == "python"

    def test_source_path_recorded(self) -> None:
        raw = {
            "$schema": "base-v1",
            "domain": "d",
            "files": {"include": ["a.tcl"]},
        }
        p = Path("jsons/base.json")
        base, _ = _collect_base(raw, path=p)
        assert base.source_path == p


# ---------------------------------------------------------------------------
# load_feature
# ---------------------------------------------------------------------------


class TestLoadFeature:
    def test_minimal(self) -> None:
        raw = {"$schema": "feature-v1", "name": "dft"}
        feat, diags = _collect_feat(raw)
        assert feat.name == "dft"
        assert diags == []

    def test_depends_on_hydrated(self) -> None:
        raw = {
            "$schema": "feature-v1",
            "name": "x",
            "depends_on": ["base_feat", "other"],
        }
        feat, _ = _collect_feat(raw)
        assert feat.depends_on == ("base_feat", "other")

    def test_metadata_hydrated(self) -> None:
        raw = {
            "$schema": "feature-v1",
            "name": "x",
            "metadata": {
                "owner": "team",
                "tags": ["dft", "scan"],
                "wiki": "https://wiki.example.com",
                "related_ivars": ["my_ivar"],
            },
        }
        feat, _ = _collect_feat(raw)
        assert feat.metadata.owner == "team"
        assert feat.metadata.tags == ("dft", "scan")
        assert feat.metadata.wiki == "https://wiki.example.com"
        assert feat.metadata.related_ivars == ("my_ivar",)

    def test_add_step_before_action(self) -> None:
        raw = {
            "$schema": "feature-v1",
            "name": "x",
            "flow_actions": [
                {
                    "action": "add_step_before",
                    "stage": "setup",
                    "reference": "step1.tcl",
                    "items": ["new_step.tcl"],
                }
            ],
        }
        feat, _ = _collect_feat(raw)
        action = feat.flow_actions[0]
        assert isinstance(action, AddStepAction)
        assert action.action == "add_step_before"
        assert action.items == ("new_step.tcl",)

    def test_add_step_after_action(self) -> None:
        raw = {
            "$schema": "feature-v1",
            "name": "x",
            "flow_actions": [
                {
                    "action": "add_step_after",
                    "stage": "setup",
                    "reference": "step1.tcl",
                    "items": ["step2.tcl", "step3.tcl"],
                }
            ],
        }
        feat, _ = _collect_feat(raw)
        action = feat.flow_actions[0]
        assert isinstance(action, AddStepAction)
        assert action.action == "add_step_after"

    def test_add_stage_after_action(self) -> None:
        raw = {
            "$schema": "feature-v1",
            "name": "x",
            "flow_actions": [
                {
                    "action": "add_stage_after",
                    "name": "dft_check",
                    "reference": "main",
                    "load_from": "main",
                    "steps": ["setup_scan"],
                }
            ],
        }
        feat, _ = _collect_feat(raw)
        action = feat.flow_actions[0]
        assert isinstance(action, AddStageAction)
        assert action.stage.name == "dft_check"
        assert action.reference == "main"

    def test_remove_step_action(self) -> None:
        raw = {
            "$schema": "feature-v1",
            "name": "x",
            "flow_actions": [{"action": "remove_step", "stage": "s", "reference": "old.tcl"}],
        }
        feat, _ = _collect_feat(raw)
        action = feat.flow_actions[0]
        assert isinstance(action, RemoveStepAction)

    def test_remove_stage_action(self) -> None:
        raw = {
            "$schema": "feature-v1",
            "name": "x",
            "flow_actions": [{"action": "remove_stage", "reference": "old_stage"}],
        }
        feat, _ = _collect_feat(raw)
        action = feat.flow_actions[0]
        assert isinstance(action, RemoveStageAction)
        assert action.reference == "old_stage"

    def test_load_from_action(self) -> None:
        raw = {
            "$schema": "feature-v1",
            "name": "x",
            "flow_actions": [{"action": "load_from", "stage": "s", "reference": "new_src"}],
        }
        feat, _ = _collect_feat(raw)
        action = feat.flow_actions[0]
        assert isinstance(action, LoadFromAction)
        assert action.reference == "new_src"

    def test_replace_step_action(self) -> None:
        raw = {
            "$schema": "feature-v1",
            "name": "x",
            "flow_actions": [{"action": "replace_step", "stage": "s", "reference": "old.tcl", "with": "new.tcl"}],
        }
        feat, _ = _collect_feat(raw)
        action = feat.flow_actions[0]
        assert isinstance(action, ReplaceStepAction)
        assert action.replacement == "new.tcl"

    def test_replace_stage_action(self) -> None:
        raw = {
            "$schema": "feature-v1",
            "name": "x",
            "flow_actions": [
                {
                    "action": "replace_stage",
                    "reference": "old_stage",
                    "with": {"name": "new_stage", "load_from": "", "steps": ["s1"]},
                }
            ],
        }
        feat, _ = _collect_feat(raw)
        action = feat.flow_actions[0]
        assert isinstance(action, ReplaceStageAction)
        assert action.replacement.name == "new_stage"


# ---------------------------------------------------------------------------
# load_project
# ---------------------------------------------------------------------------


class TestLoadProject:
    def test_minimal(self) -> None:
        raw = {
            "$schema": "project-v1",
            "project": "P",
            "domain": "d",
            "base": "jsons/base.json",
        }
        proj = load_project(raw, Path("project.json"))
        assert proj.project == "P"
        assert proj.domain == "d"
        assert proj.base == "jsons/base.json"
        assert proj.features == ()

    def test_features_preserved(self) -> None:
        raw = {
            "$schema": "project-v1",
            "project": "P",
            "domain": "d",
            "base": "jsons/base.json",
            "features": ["jsons/features/a.json", "jsons/features/b.json"],
        }
        proj = load_project(raw, Path("project.json"))
        assert proj.features == ("jsons/features/a.json", "jsons/features/b.json")

    def test_notes_preserved(self) -> None:
        raw = {
            "$schema": "project-v1",
            "project": "P",
            "domain": "d",
            "base": "b.json",
            "notes": ["note one", "note two"],
        }
        proj = load_project(raw, Path("p.json"))
        assert proj.notes == ("note one", "note two")


# ---------------------------------------------------------------------------
# topo_sort_features
# ---------------------------------------------------------------------------


def _make_feat(name: str, depends_on: list[str] = []) -> FeatureJson:  # noqa: B006
    return FeatureJson(source_path=Path(f"{name}.json"), name=name, depends_on=tuple(depends_on))


class TestTopoSort:
    def test_no_deps_preserves_order(self) -> None:
        feats = [_make_feat("c"), _make_feat("a"), _make_feat("b")]
        diags: list[Diagnostic] = []
        result = topo_sort_features(feats, Path("p.json"), diags.append)
        assert [f.name for f in result] == ["c", "a", "b"]
        assert diags == []

    def test_simple_chain(self) -> None:
        feats = [_make_feat("c", ["b"]), _make_feat("b", ["a"]), _make_feat("a")]
        diags: list[Diagnostic] = []
        result = topo_sort_features(feats, Path("p.json"), diags.append)
        names = [f.name for f in result]
        # a must come before b, b before c
        assert names.index("a") < names.index("b")
        assert names.index("b") < names.index("c")
        assert diags == []

    def test_diamond_dependency(self) -> None:
        # a → b, a → c, b → d, c → d  (d must be first)
        feats = [
            _make_feat("d"),
            _make_feat("b", ["d"]),
            _make_feat("c", ["d"]),
            _make_feat("a", ["b", "c"]),
        ]
        diags: list[Diagnostic] = []
        result = topo_sort_features(feats, Path("p.json"), diags.append)
        names = [f.name for f in result]
        assert names.index("d") < names.index("b")
        assert names.index("d") < names.index("c")
        assert names.index("b") < names.index("a")
        assert names.index("c") < names.index("a")

    def test_ve22_cycle_detected(self) -> None:
        feats = [_make_feat("a", ["b"]), _make_feat("b", ["a"])]
        diags: list[Diagnostic] = []
        result = topo_sort_features(feats, Path("p.json"), diags.append)
        assert any(d.code == "VE-22" for d in diags)
        # Returns original order on cycle
        assert len(result) == 2

    def test_ve14_duplicate_name(self) -> None:
        feats = [_make_feat("a"), _make_feat("a")]
        diags: list[Diagnostic] = []
        result = topo_sort_features(feats, Path("p.json"), diags.append)
        assert any(d.code == "VE-14" for d in diags)
        assert len(result) == 1  # duplicate dropped

    def test_ve15_missing_prerequisite(self) -> None:
        feats = [_make_feat("x", ["ghost"])]
        diags: list[Diagnostic] = []
        result = topo_sort_features(feats, Path("p.json"), diags.append)
        assert any(d.code == "VE-15" for d in diags)
        # Returns as-is when edges are dangling
        assert len(result) == 1

    def test_stable_sort_within_rank(self) -> None:
        # b and c both depend on a — their relative order should match input.
        feats = [_make_feat("a"), _make_feat("b", ["a"]), _make_feat("c", ["a"])]
        diags: list[Diagnostic] = []
        result = topo_sort_features(feats, Path("p.json"), diags.append)
        names = [f.name for f in result]
        assert names[0] == "a"
        assert names.index("b") < names.index("c")

    def test_empty_list(self) -> None:
        result = topo_sort_features([], Path("p.json"), lambda _: None)
        assert result == []


# ------------------------------------------------------------------
# Extracted from test_small_modules_torture.py (module-aligned consolidation).
# ------------------------------------------------------------------


def test_load_base_emits_ve03_for_empty_procs_array_in_exclude() -> None:
    from chopper.config.loaders import load_base

    diagnostics: list[Diagnostic] = []

    def _emit(d: Diagnostic) -> None:
        diagnostics.append(d)

    raw = {
        "$schema": "base-v1",
        "domain": "d",
        "procedures": {
            "exclude": [
                {"file": "lib/empty.tcl", "procs": []},  # empty → VE-03
            ],
        },
    }
    load_base(raw, Path("/cfg/base.json"), _emit)
    assert any(d.code == "VE-03" for d in diagnostics)


def test_load_flow_action_unmapped_action_raises() -> None:
    from chopper.config.loaders import _load_flow_action

    with pytest.raises(AssertionError, match="unmapped flow action kind"):
        _load_flow_action({"action": "completely_made_up"})
