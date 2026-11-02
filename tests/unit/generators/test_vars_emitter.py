"""Unit tests for the v2 feature vars sourcing file (ARCHITECTURE Sec.3.12).

Covers :func:`chopper.generators.vars_emitter.emit_feature_vars`, its
:class:`GeneratorService` wiring, the P3 registration / ``VE-40`` collision
in :class:`CompilerService`, implicit F1 keep via ``vars_keep``, and the v2
schema surface.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from chopper.compiler.merge_service import CompilerService
from chopper.config.schema import validate_json
from chopper.core.diagnostics import Diagnostic
from chopper.core.errors import ChopperError
from chopper.core.header import intel_header_lines
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest
from chopper.core.models_parser import ParseResult
from chopper.generators import GeneratorService
from chopper.generators.vars_emitter import emit_feature_vars
from tests.unit.compiler._helpers import files_section, make_base, make_ctx, make_feature, make_loaded

from .test_service import _make_ctx as _gen_ctx

_HEADER = "\n".join(intel_header_lines())


class TestEmitFeatureVars:
    def test_two_feature_blocks(self) -> None:
        artifact = emit_feature_vars(
            "apr_fc",
            (
                ("fdr_vars.tcl", "tech_fdr_vars.tcl", "project_fdr_vars.tcl"),
                ("dop_vars.tcl", "tech_dop_vars.tcl", "project_dop_vars.tcl"),
            ),
        )
        assert artifact.path == Path("apr_fc_feature_vars.tcl")
        assert artifact.kind == "tcl"
        assert artifact.content == (
            f"{_HEADER}\n\n"
            "# Feature vars.tcl sourcing file for apr_fc\n\n"
            "iproc_source -file fdr_vars.tcl -optional\n"
            "iproc_source -file tech_fdr_vars.tcl -optional\n"
            "iproc_source -file project_fdr_vars.tcl -optional\n\n"
            "iproc_source -file dop_vars.tcl -optional\n"
            "iproc_source -file tech_dop_vars.tcl -optional\n"
            "iproc_source -file project_dop_vars.tcl -optional\n"
        )

    def test_no_blocks_is_header_and_title_only(self) -> None:
        artifact = emit_feature_vars("apr_fc", ())
        assert artifact.content == f"{_HEADER}\n\n# Feature vars.tcl sourcing file for apr_fc\n"


class TestGeneratorWiring:
    def test_v2_manifest_writes_vars_file(self) -> None:
        ctx, fs = _gen_ctx()
        artifacts = GeneratorService().run(ctx, CompiledManifest(feature_vars=(("a_vars.tcl",),)))
        assert [a.path for a in artifacts] == [Path("my_domain_feature_vars.tcl")]
        assert "iproc_source -file a_vars.tcl -optional" in fs.read_text(ctx.config.domain_root / artifacts[0].path)

    def test_v1_manifest_emits_nothing(self) -> None:
        ctx, _fs = _gen_ctx()
        assert GeneratorService().run(ctx, CompiledManifest()) == ()


def _empty_parsed() -> ParseResult:
    return ParseResult(files={}, index={})


class TestCompilerRegistration:
    def test_registers_generated_with_provenance(self) -> None:
        ctx, sink = make_ctx()
        feat = replace(make_feature("fdr"), vars="fdr_vars.tcl", vars_keep=(Path("fdr_vars.tcl"),))
        loaded = replace(make_loaded(make_base(), make_feature("plain"), feat), feature_vars=(("fdr_vars.tcl",),))
        manifest = CompilerService().run(ctx, loaded, _empty_parsed())

        path = Path("my_domain_feature_vars.tcl")
        assert manifest.file_decisions[path] is FileTreatment.GENERATED
        assert manifest.provenance[path].input_sources == ("base", "feature:fdr:vars")
        assert manifest.provenance[path].contributed_by == "feature:fdr:vars"
        assert manifest.feature_vars == (("fdr_vars.tcl",),)
        assert manifest.file_decisions[Path("fdr_vars.tcl")] is FileTreatment.FULL_COPY
        assert sink.codes() == []

    def test_v1_registers_nothing(self) -> None:
        ctx, _sink = make_ctx()
        manifest = CompilerService().run(ctx, make_loaded(make_base()), _empty_parsed())
        assert manifest.file_decisions == {}
        assert manifest.feature_vars is None

    def test_base_vars_keep_is_full_copy_and_later_exclude_wins(self) -> None:
        ctx, sink = make_ctx()
        base = replace(make_base(), vars="vars.tcl", vars_keep=(Path("vars.tcl"),))
        dropper = make_feature("dropper", files=files_section(exclude=("vars.tcl",)))
        kept = CompilerService().run(ctx, replace(make_loaded(base), feature_vars=()), _empty_parsed())
        assert kept.file_decisions[Path("vars.tcl")] is FileTreatment.FULL_COPY

        loaded = replace(make_loaded(base, dropper, surface_files=(Path("vars.tcl"),)), feature_vars=())
        dropped = CompilerService().run(ctx, loaded, _empty_parsed())
        assert dropped.file_decisions[Path("vars.tcl")] is FileTreatment.REMOVE
        assert "VW-21" in sink.codes()

    def test_collision_emits_ve40_and_raises(self) -> None:
        ctx, sink = make_ctx()
        base = make_base(files=files_section(include=("my_domain_feature_vars.tcl",)))
        with pytest.raises(ChopperError, match="collides"):
            CompilerService().run(ctx, replace(make_loaded(base), feature_vars=()), _empty_parsed())
        assert sink.codes() == ["VE-40"]


def _codes(raw: dict) -> list[str]:
    out: list[Diagnostic] = []
    validate_json(raw, Path("x.json"), out.append)
    return [d.code for d in out]


class TestV2Schemas:
    def test_base_and_feature_v2_accept_vars(self) -> None:
        base = {"$schema": "base-v2", "domain": "d", "vars": "vars.tcl", "files": {"include": ["a.tcl"]}}
        assert _codes(base) == []
        assert _codes({"$schema": "feature-v2", "name": "f", "vars": "sub/f_vars.tcl"}) == []

    def test_v1_rejects_vars(self) -> None:
        assert _codes({"$schema": "feature-v1", "name": "f", "vars": "f_vars.tcl"}) == ["VE-02"]

    @pytest.mark.parametrize("bad", ["*.tcl", "a?.tcl", "[ab].tcl", "../x.tcl", "/abs.tcl", "a\\b.tcl", ""])
    def test_vars_rejects_globs_and_unsafe_paths(self, bad: str) -> None:
        assert _codes({"$schema": "feature-v2", "name": "f", "vars": bad}) == ["VE-02"]

    def test_project_v2_schema_errors_use_ve12(self) -> None:
        assert _codes({"$schema": "project-v2", "project": "p", "domain": "d", "base": "b.json"}) == []
        assert _codes({"$schema": "project-v2", "project": "p"}) == ["VE-12"]

    def test_non_string_schema_is_ve01(self) -> None:
        assert _codes({"$schema": ["base-v2"]}) == ["VE-01"]


@pytest.mark.parametrize("procs", [False, True])
@pytest.mark.parametrize(
    "entry",
    [
        "feature dir/fdr.tcl",
        "a;set flag 1.tcl",
        "$env(ROOT)/f.tcl",
        'quote"name.tcl',
        "brace{name.tcl",
        "[not_a_command].tcl",
        "brace}name.tcl",
        "a\tb\r\n\v\f.tcl",
        r"back\slash.tcl",
    ],
)
def test_source_paths_are_one_literal_tcl_argument(entry: str, procs: bool) -> None:
    tkinter = pytest.importorskip("tkinter", reason="Tcl runtime unavailable")
    tcl = tkinter.Tcl()
    tcl.eval("set seen {}; proc iproc_source {args} {lappend ::seen $args}")
    artifact = emit_feature_vars("flow", ((entry,),), procs=procs)

    tcl.eval(artifact.content)

    calls = tcl.splitlist(tcl.eval("set seen"))
    assert len(calls) == 1
    assert tcl.splitlist(calls[0]) == ("-file", entry, "-optional")
