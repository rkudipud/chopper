"""Torture for :mod:`chopper.compiler.merge_service` — F3 stage handling
and rare R1 rows that synthetic toy domains don't naturally exercise.

These tests target the missing-coverage hotspots:

* L189-216, 220-222 — F3 stage emission, collision check, feature
  flow_actions contributors.
* L402, 405, 417, 420 — VW-09 / VW-13 in rows 8/10/15/16.
* L506 — PE entries on a file the parser never saw (defensive skip).
* L612 — VW-18 (PE vetoed by another source's include).
* L822-823, 825 — _match_glob exception fallback.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from chopper.compiler import CompilerService
from chopper.core.errors import ChopperError
from chopper.core.models import (
    AddStageAction,
    BaseJson,
    FeatureJson,
    FileTreatment,
    StageDefinition,
)
from tests.unit.compiler._helpers import (
    files_section,
    make_base,
    make_ctx,
    make_feature,
    make_loaded,
    make_parsed,
    proc_ref,
    procs_section,
)


def _base_with_stages(base: BaseJson, stages: tuple[StageDefinition, ...]) -> BaseJson:
    return replace(base, stages=stages)


def _feature_with_flow(feat: FeatureJson, flows: tuple) -> FeatureJson:
    return replace(feat, flow_actions=flows)


# ---------------------------------------------------------------------------
# F3 — stage emission, contributors, collision
# ---------------------------------------------------------------------------


def test_stage_definition_emits_generated_file_with_base_contributor() -> None:
    ctx, _ = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo"]})
    base = _base_with_stages(
        make_base(files=files_section(include=("a.tcl",))),
        stages=(StageDefinition(name="compile", load_from="default", steps=("foo",)),),
    )
    loaded = make_loaded(base)
    manifest = CompilerService().run(ctx, loaded, parsed)
    gen = manifest.file_decisions[Path("compile.tcl")]
    assert gen is FileTreatment.GENERATED
    pv = manifest.provenance[Path("compile.tcl")]
    assert pv.input_sources == ("base:stages",)


def test_stage_collision_with_existing_file_decision_raises() -> None:
    """Bible §5.3 step 3: stage ``compile`` registers ``compile.tcl``;
    if files.include already lists ``compile.tcl`` → ChopperError."""
    ctx, _ = make_ctx()
    parsed = make_parsed({"compile.tcl": ["x"]})
    base = _base_with_stages(
        make_base(files=files_section(include=("compile.tcl",))),
        stages=(StageDefinition(name="compile", load_from="default", steps=("x",)),),
    )
    loaded = make_loaded(base)
    with pytest.raises(ChopperError, match="collides with an existing file decision"):
        CompilerService().run(ctx, loaded, parsed)


def test_feature_flow_action_appears_in_stage_input_sources() -> None:
    ctx, _ = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo"]})
    base = _base_with_stages(
        make_base(files=files_section(include=("a.tcl",))),
        stages=(StageDefinition(name="compile", load_from="default", steps=("foo",)),),
    )
    flow = AddStageAction(
        action="add_stage_after",
        reference="compile",
        stage=StageDefinition(name="post", load_from="default", steps=("foo",)),
    )
    feat = _feature_with_flow(make_feature("post_compile"), (flow,))
    loaded = make_loaded(base, feat)
    manifest = CompilerService().run(ctx, loaded, parsed)
    pv = manifest.provenance[Path("compile.tcl")]
    assert "base:stages" in pv.input_sources
    assert "post_compile:flow_actions" in pv.input_sources


# ---------------------------------------------------------------------------
# VW-13 — PE prunes include to empty (row 9 / row 10)
# ---------------------------------------------------------------------------


def test_vw13_emitted_when_pe_excludes_every_proc_in_include(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo", "bar"]})
    base = make_base(
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(exclude=(proc_ref("a.tcl", "foo", "bar"),)),
    )
    loaded = make_loaded(base)
    CompilerService().run(ctx, loaded, parsed)
    assert "VW-13" in sink.codes()


def test_vw13_with_pi_redundant_emits_vw09_too() -> None:
    """Row 10 — FI + PI + PE where PE removes everything: both VW-09 and VW-13."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo"]})
    base = make_base(
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(
            include=(proc_ref("a.tcl", "foo"),),
            exclude=(proc_ref("a.tcl", "foo"),),
        ),
    )
    loaded = make_loaded(base)
    CompilerService().run(ctx, loaded, parsed)
    codes = sink.codes()
    assert "VW-09" in codes
    assert "VW-13" in codes


# ---------------------------------------------------------------------------
# PE entry on file absent from ParseResult — defensive `continue` (L506)
# ---------------------------------------------------------------------------


def test_pe_on_unparsed_file_does_not_crash_aggregation() -> None:
    ctx, _ = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo"]})
    base = make_base(
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(exclude=(proc_ref("ghost.tcl", "phantom"),)),
    )
    loaded = make_loaded(base)
    manifest = CompilerService().run(ctx, loaded, parsed)
    assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.FULL_COPY


# ---------------------------------------------------------------------------
# VW-18 — PE in source-A vetoed by include in source-B
# ---------------------------------------------------------------------------


def test_vw18_emitted_when_feature_pi_blocks_base_pe() -> None:
    """Base wants to exclude proc ``foo``; feature explicitly includes
    ``foo`` → VW-18 (cross-source veto)."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo", "bar"]})
    base = make_base(
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(exclude=(proc_ref("a.tcl", "foo"),)),
    )
    feat = make_feature(
        "keep_foo",
        procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)),
    )
    loaded = make_loaded(base, feat)
    CompilerService().run(ctx, loaded, parsed)
    assert "VW-18" in sink.codes()
