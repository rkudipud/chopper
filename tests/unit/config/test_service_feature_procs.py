"""V2 procs pointers use the same resolution and F1 rules as vars."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from chopper.compiler.merge_service import CompilerService
from chopper.config.schema import validate_json
from chopper.config.service import ConfigService
from chopper.core.diagnostics import Diagnostic
from chopper.core.header import intel_header_lines
from chopper.core.models_common import FileTreatment
from chopper.core.models_parser import ParseResult
from chopper.generators.vars_emitter import emit_feature_vars
from tests.unit.compiler._helpers import files_section, make_base, make_ctx, make_feature, make_loaded

from .test_service import _BACKUP, _DOMAIN, _default_state, _make_ctx
from .test_service_feature_vars import _BASE, _base, _feature, _fpath


@pytest.mark.parametrize("version", [1, 2])
def test_absent_procs_pointer_preserves_version_behavior(version: int) -> None:
    ctx, sink = _make_ctx({_BASE: _base(version=version)}, base_path=_BASE)
    result = ConfigService().run(ctx, _default_state())
    assert result.feature_procs == (() if version == 2 else None)
    assert result.base.procs_keep == ()
    assert sink.emissions == []
    artifact = emit_feature_vars("my_domain", (), procs=True)
    assert artifact.content == (
        "\n".join(intel_header_lines()) + "\n\n# Feature procs.tcl sourcing file for my_domain\n"
    )


def test_procs_resolved_order_partial_duplicates_and_independent_vars() -> None:
    files = {
        _BASE: _base(procs="missing.tcl"),
        _fpath("b"): _feature("b", depends_on=["a"], procs="x.tcl", vars="x.tcl"),
        _fpath("a"): _feature("a", procs="tech_x.tcl"),
        _fpath("plain"): _feature("plain"),
        _DOMAIN / "x.tcl": "",
        _DOMAIN / "tech_x.tcl": "",
        _DOMAIN / "project_x.tcl": "",
    }
    ctx, sink = _make_ctx(files, base_path=_BASE, feature_paths=(_fpath("b"), _fpath("plain"), _fpath("a")))
    result = ConfigService().run(ctx, _default_state())
    assert result.feature_procs == (
        ("tech_x.tcl", "tech_tech_x.tcl", "project_tech_x.tcl"),
        ("x.tcl", "project_x.tcl"),
    )
    assert result.feature_vars == (("x.tcl", "tech_x.tcl", "project_x.tcl"),)
    assert [d.code for d in sink.emissions] == ["VW-30", "VW-31"]
    by_name = {f.name: f for f in result.features}
    assert by_name["b"].procs_keep == (Path("x.tcl"), Path("tech_x.tcl"), Path("project_x.tcl"))
    assert by_name["plain"].procs_keep == ()
    assert {Path("x.tcl"), Path("tech_x.tcl"), Path("project_x.tcl")} <= set(result.surface_files)


def test_procs_existence_uses_backup_on_retrim() -> None:
    files = {
        _BASE: _base(procs="procs.tcl"),
        _fpath("f"): _feature("f", procs="f_procs.tcl"),
        _BACKUP / "procs.tcl": "",
        _BACKUP / "f_procs.tcl": "",
        _BACKUP / "tech_f_procs.tcl": "",
    }
    ctx, sink = _make_ctx(files, base_path=_BASE, feature_paths=(_fpath("f"),))
    result = ConfigService().run(ctx, replace(_default_state(), case=2, backup_exists=True))
    assert sink.emissions == []
    assert result.base.procs_keep == (Path("procs.tcl"),)
    assert result.features[0].procs_keep == (Path("f_procs.tcl"), Path("tech_f_procs.tcl"))


def test_later_exclude_overrides_procs_f1_keep() -> None:
    ctx, sink = make_ctx()
    base = replace(make_base(), procs="procs.tcl", procs_keep=(Path("procs.tcl"),))
    dropper = make_feature("dropper", files=files_section(exclude=("procs.tcl",)))
    loaded = replace(make_loaded(base, dropper, surface_files=(Path("procs.tcl"),)), feature_procs=())
    result = CompilerService().run(ctx, loaded, ParseResult(files={}, index={}))
    assert result.file_decisions[Path("procs.tcl")] is FileTreatment.REMOVE
    assert "VW-21" in sink.codes()


@pytest.mark.parametrize("kind", ["base", "feature"])
@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("entry", ["f_procs.tcl", "dir/f_procs.tcl", "", "*.tcl", "../x.tcl", "/x.tcl", "a\\b.tcl"])
def test_procs_schema_path_and_version_contract(kind: str, version: int, entry: str) -> None:
    raw: dict[str, object] = {"$schema": f"{kind}-v{version}", "procs": entry}
    if kind == "base":
        raw.update(domain="d", files={"include": ["main.tcl"]})
    else:
        raw["name"] = "f"
    diagnostics: list[Diagnostic] = []
    valid = validate_json(raw, Path("input.json"), diagnostics.append)
    expected = version == 2 and entry in ("f_procs.tcl", "dir/f_procs.tcl")
    assert valid is expected
    assert [d.code for d in diagnostics] == ([] if expected else ["VE-02"])
