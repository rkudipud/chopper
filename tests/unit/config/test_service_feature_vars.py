"""Unit tests for v2 ``vars`` resolution in :mod:`chopper.config.service` (ARCHITECTURE Sec.3.12, FR-57).

Covers the three-entry expansion, F1 auto-keep (``vars_keep`` + surface
files), first-wins dedup (``VW-29``), missing authored entry (``VW-27``),
base JSON naming (``VW-28``), and the one-version-per-run rule (``VE-41``).
"""

from __future__ import annotations

import json
from pathlib import Path

from chopper.config.service import ConfigService, expand_vars_entry

from .test_service import _DOMAIN, _default_state, _make_ctx

_BASE = _DOMAIN / "jsons/my_domain.json"


def _base(version: int = 2, **extra: object) -> str:
    return json.dumps({"$schema": f"base-v{version}", "domain": "my_domain", "files": {"include": ["a.tcl"]}, **extra})


def _feature(name: str, version: int = 2, **extra: object) -> str:
    return json.dumps({"$schema": f"feature-v{version}", "name": name, **extra})


def _fpath(name: str) -> Path:
    return _DOMAIN / f"jsons/features/{name}.feature.json"


class TestExpandVarsEntry:
    def test_root_level_entry(self) -> None:
        assert expand_vars_entry("fdr_vars.tcl") == ("fdr_vars.tcl", "tech_fdr_vars.tcl", "project_fdr_vars.tcl")

    def test_nested_entry_prefixes_file_name_only(self) -> None:
        assert expand_vars_entry("vars/dop_vars.tcl") == (
            "vars/dop_vars.tcl",
            "vars/tech_dop_vars.tcl",
            "vars/project_dop_vars.tcl",
        )


class TestFeatureVarsResolution:
    def test_blocks_keep_and_surface(self) -> None:
        files = {
            _BASE: _base(vars="vars.tcl"),
            _DOMAIN / "vars.tcl": "",
            _fpath("fdr"): _feature("fdr", vars="fdr_vars.tcl"),
            _DOMAIN / "fdr_vars.tcl": "",
            _DOMAIN / "tech_fdr_vars.tcl": "",
            _fpath("dop"): _feature("dop", vars="v/dop_vars.tcl"),
            _DOMAIN / "v/dop_vars.tcl": "",
            _fpath("plain"): _feature("plain", files={"include": ["b.tcl"]}),
        }
        ctx, sink = _make_ctx(files, base_path=_BASE, feature_paths=(_fpath("fdr"), _fpath("dop"), _fpath("plain")))
        result = ConfigService().run(ctx, _default_state())

        assert sink.emissions == []
        assert result.feature_vars == (
            ("fdr_vars.tcl", "tech_fdr_vars.tcl", "project_fdr_vars.tcl"),
            ("v/dop_vars.tcl", "v/tech_dop_vars.tcl", "v/project_dop_vars.tcl"),
        )
        assert result.base.vars_keep == (Path("vars.tcl"),)
        by_name = {f.name: f for f in result.features}
        assert by_name["fdr"].vars_keep == (Path("fdr_vars.tcl"), Path("tech_fdr_vars.tcl"))
        assert by_name["dop"].vars_keep == (Path("v/dop_vars.tcl"),)
        assert by_name["plain"].vars_keep == ()
        for kept in ("vars.tcl", "fdr_vars.tcl", "tech_fdr_vars.tcl", "v/dop_vars.tcl"):
            assert Path(kept) in result.surface_files
        assert Path("project_fdr_vars.tcl") not in result.surface_files

    def test_v2_without_any_vars_yields_empty_blocks(self) -> None:
        ctx, sink = _make_ctx({_BASE: _base()}, base_path=_BASE)
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        assert result.feature_vars == ()
        assert result.base.schema_version == 2

    def test_v1_run_yields_none(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ctx, sink = _make_ctx({base_path: _base(version=1)}, base_path=base_path)
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        assert result.feature_vars is None

    def test_missing_entries_warn_vw27_and_still_emit_lines(self) -> None:
        files = {
            _BASE: _base(vars="vars.tcl"),
            _fpath("fdr"): _feature("fdr", vars="fdr_vars.tcl"),
        }
        ctx, sink = _make_ctx(files, base_path=_BASE, feature_paths=(_fpath("fdr"),))
        result = ConfigService().run(ctx, _default_state())

        assert [d.code for d in sink.emissions] == ["VW-27", "VW-27"]
        assert result.base.vars_keep == ()
        assert result.features[0].vars_keep == ()
        assert result.feature_vars == (("fdr_vars.tcl", "tech_fdr_vars.tcl", "project_fdr_vars.tcl"),)

    def test_duplicate_entries_warn_vw29_first_wins(self) -> None:
        files = {
            _BASE: _base(),
            _fpath("a"): _feature("a", vars="x_vars.tcl"),
            _fpath("b"): _feature("b", vars="x_vars.tcl"),
            _DOMAIN / "x_vars.tcl": "",
        }
        ctx, sink = _make_ctx(files, base_path=_BASE, feature_paths=(_fpath("a"), _fpath("b")))
        result = ConfigService().run(ctx, _default_state())

        assert [d.code for d in sink.emissions] == ["VW-29", "VW-29", "VW-29"]
        assert "feature 'a'" in sink.emissions[0].message
        assert result.feature_vars == (("x_vars.tcl", "tech_x_vars.tcl", "project_x_vars.tcl"),)

    def test_partial_duplicate_keeps_remaining_entries(self) -> None:
        # b's tech_/project_ variants collide with a's own entries only where the strings match.
        files = {
            _BASE: _base(),
            _fpath("a"): _feature("a", vars="tech_x.tcl"),
            _fpath("b"): _feature("b", vars="x.tcl"),
            _DOMAIN / "tech_x.tcl": "",
            _DOMAIN / "x.tcl": "",
        }
        ctx, sink = _make_ctx(files, base_path=_BASE, feature_paths=(_fpath("a"), _fpath("b")))
        result = ConfigService().run(ctx, _default_state())

        assert [d.code for d in sink.emissions] == ["VW-29"]
        assert result.feature_vars == (
            ("tech_x.tcl", "tech_tech_x.tcl", "project_tech_x.tcl"),
            ("x.tcl", "project_x.tcl"),
        )

    def test_base_json_name_mismatch_warns_vw28(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ctx, sink = _make_ctx({base_path: _base()}, base_path=base_path)
        result = ConfigService().run(ctx, _default_state())
        assert [d.code for d in sink.emissions] == ["VW-28"]
        assert result.feature_vars == ()

    def test_base_json_name_match_is_case_insensitive(self) -> None:
        base_path = _DOMAIN / "jsons/MY_DOMAIN.json"
        ctx, sink = _make_ctx({base_path: _base()}, base_path=base_path)
        ConfigService().run(ctx, _default_state())
        assert sink.emissions == []


class TestMixedSchemaVersions:
    def test_base_v2_feature_v1_fails_ve41(self) -> None:
        files = {_BASE: _base(vars="vars.tcl"), _fpath("f"): _feature("f", version=1)}
        ctx, sink = _make_ctx(files, base_path=_BASE, feature_paths=(_fpath("f"),))
        result = ConfigService().run(ctx, _default_state())
        assert [d.code for d in sink.emissions] == ["VE-41"]
        assert "(v1)" in sink.emissions[0].message and "(v2)" in sink.emissions[0].message
        assert result.feature_vars is None
        assert result.base.vars_keep == ()

    def test_project_v1_with_base_v2_fails_ve41(self) -> None:
        project_path = _DOMAIN / "project.json"
        project = json.dumps(
            {"$schema": "project-v1", "project": "P", "domain": "my_domain", "base": "jsons/my_domain.json"}
        )
        ctx, sink = _make_ctx({project_path: project, _BASE: _base()}, project_path=project_path)
        result = ConfigService().run(ctx, _default_state())
        assert [d.code for d in sink.emissions] == ["VE-41"]
        assert result.project is not None and result.project.schema_version == 1

    def test_project_v2_with_v2_inputs_passes(self) -> None:
        project_path = _DOMAIN / "project.json"
        project = json.dumps(
            {
                "$schema": "project-v2",
                "project": "P",
                "domain": "my_domain",
                "base": "jsons/my_domain.json",
                "features": ["jsons/features/f.feature.json"],
            }
        )
        files = {project_path: project, _BASE: _base(), _fpath("f"): _feature("f", vars="f_vars.tcl")}
        files[_DOMAIN / "f_vars.tcl"] = ""
        ctx, sink = _make_ctx(files, project_path=project_path)
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        assert result.project is not None and result.project.schema_version == 2
        assert result.feature_vars == (("f_vars.tcl", "tech_f_vars.tcl", "project_f_vars.tcl"),)
