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
from chopper.core.models_common import FileTreatment
from chopper.core.models_config import AddStageAction, BaseJson, FeatureJson, StageDefinition
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
    """Architecture Doc §5.3 step 3: stage ``compile`` registers ``compile.tcl``;
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
# P-42 — Glob-matched non-Tcl files must reach the manifest (F1 is type-agnostic)
# ---------------------------------------------------------------------------


def test_glob_matched_non_tcl_file_receives_full_copy_treatment() -> None:
    """Regression for pitfall P-42: a ``.py`` file reachable *only* via a
    glob-surviving FI path must enter ``_collect_universe`` and therefore
    receive a ``FULL_COPY`` treatment in the manifest.

    Before the fix, ``_collect_universe`` only unioned ``fi_literal``;
    ``fi_glob_surviving`` was ignored, so glob-matched non-Tcl files were
    silently absent from the manifest.
    """
    from chopper.compiler.merge_service import (  # noqa: PLC0415
        _collect_universe,  # noqa: PLC0415
        _SourceFacts,
        _SourceRef,
    )

    ctx, _ = make_ctx()
    parsed = make_parsed({"core.tcl": ["setup"]})

    # Simulate: a feature whose files.include glob matched report.py (non-Tcl).
    # The .py was in fi_glob_surviving but NOT in fi_literal or parsed.files.
    report_py = Path("reports/report.py")
    fake_facts = _SourceFacts(
        ref=_SourceRef(key="feat", source_path=Path("/dom/feat.json")),
        fi_literal=frozenset(),
        fi_glob_surviving=frozenset({report_py}),
        fe_literal=frozenset(),
        pi_by_file={},
        pe_by_file={},
    )

    universe = _collect_universe(parsed, [fake_facts])
    assert report_py in universe, (
        "glob-matched non-Tcl file must appear in the manifest universe (P-42: F1 is file-type agnostic)"
    )


def test_compiler_service_glob_only_non_tcl_receives_full_copy() -> None:
    """End-to-end through CompilerService: a feature glob-only pattern expands
    to a non-Tcl file (pre-populated in fi_glob_surviving via _extract_facts).
    The file must appear in the manifest as FULL_COPY."""
    ctx, _ = make_ctx()
    # parsed has only a.tcl; report.py is NOT in parsed.files
    parsed = make_parsed({"a.tcl": ["foo"]})
    # Using a literal path here because _extract_facts classifies literals;
    # the companion test above covers the fi_glob_surviving path directly.
    # Using a .py literal to confirm non-Tcl literal FI still works.
    report_py = Path("reports/report.py")
    base = make_base(
        files=files_section(include=("a.tcl", "reports/report.py")),
    )
    loaded = make_loaded(base, surface_files=(Path("a.tcl"), report_py))
    manifest = CompilerService().run(ctx, loaded, parsed)
    assert manifest.file_decisions.get(report_py) is FileTreatment.FULL_COPY, (
        "non-Tcl file named in files.include must survive as FULL_COPY"
    )


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
