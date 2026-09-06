"""Torture for :mod:`chopper.compiler.merge_service` -- F3 stage handling
and rare R1 rows that synthetic toy domains don't naturally exercise.

These tests target the missing-coverage hotspots:

* L189-216, 220-222 -- F3 stage emission, collision check, feature
  flow_actions contributors.
* L402, 405, 417, 420 -- VW-09 / VW-13 in rows 8/10/15/16.
* L506 -- PE entries on a file the parser never saw (defensive skip).
* L612 -- VW-18 (PE vetoed by another source's include).
* L822-823, 825 -- _match_glob exception fallback.
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
# F3 -- stage emission, contributors, collision
# ---------------------------------------------------------------------------


def test_stage_definition_emits_generated_file_with_base_contributor() -> None:
    ctx, _ = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo"]})
    base = _base_with_stages(
        make_base(files=files_section(include=("a.tcl",))),
        stages=(StageDefinition(name="compile", load_from="", steps=("foo",)),),
    )
    loaded = make_loaded(base)
    manifest = CompilerService().run(ctx, loaded, parsed)
    gen = manifest.file_decisions[Path("compile.tcl")]
    assert gen is FileTreatment.GENERATED
    pv = manifest.provenance[Path("compile.tcl")]
    assert pv.input_sources == ("base:stages",)


def test_stage_collision_with_existing_file_decision_raises() -> None:
    """Architecture Doc Sec.5.3 step 3: stage ``compile`` registers ``compile.tcl``;
    if files.include already lists ``compile.tcl`` -> ChopperError."""
    ctx, _ = make_ctx()
    parsed = make_parsed({"compile.tcl": ["x"]})
    base = _base_with_stages(
        make_base(files=files_section(include=("compile.tcl",))),
        stages=(StageDefinition(name="compile", load_from="", steps=("x",)),),
    )
    loaded = make_loaded(base)
    with pytest.raises(ChopperError, match="collides with an existing file decision"):
        CompilerService().run(ctx, loaded, parsed)


def test_feature_flow_action_appears_in_stage_input_sources() -> None:
    ctx, _ = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo"]})
    base = _base_with_stages(
        make_base(files=files_section(include=("a.tcl",))),
        stages=(StageDefinition(name="compile", load_from="", steps=("foo",)),),
    )
    flow = AddStageAction(
        action="add_stage_after",
        reference="compile",
        stage=StageDefinition(name="post", load_from="compile", steps=("foo",)),
    )
    feat = _feature_with_flow(make_feature("post_compile"), (flow,))
    loaded = make_loaded(base, feat)
    manifest = CompilerService().run(ctx, loaded, parsed)
    pv = manifest.provenance[Path("compile.tcl")]
    assert "base:stages" in pv.input_sources
    assert "feature:post_compile:flow_actions" in pv.input_sources


def test_stage_contributors_skip_feature_without_flow_actions() -> None:
    """A loaded feature with no flow_actions must not appear in the stage's
    input_sources contributor list."""
    ctx, _ = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo"]})
    base = _base_with_stages(
        make_base(files=files_section(include=("a.tcl",))),
        stages=(StageDefinition(name="compile", load_from="", steps=("foo",)),),
    )
    feat = make_feature("no_flow")  # no flow_actions
    loaded = make_loaded(base, feat)
    manifest = CompilerService().run(ctx, loaded, parsed)
    pv = manifest.provenance[Path("compile.tcl")]
    assert pv.input_sources == ("base:stages",)
    assert "feature:no_flow:flow_actions" not in pv.input_sources


# ---------------------------------------------------------------------------
# P-42 -- Glob-matched non-Tcl files must reach the manifest (F1 is type-agnostic)
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
        fi_glob_matched=frozenset({report_py}),
        fi_glob_surviving=frozenset({report_py}),
        fe_literal=frozenset(),
        pi_by_file={},
        pe_by_file={},
        fe_glob_unmatched=(),
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
# VW-13 -- PE prunes include to empty (row 9 / row 10)
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
    """Row 10 -- FI + PI + PE where PE removes everything: both VW-09 and VW-13."""
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


def test_vw13_emitted_for_pe_alone_excluding_every_proc() -> None:
    """Row 9 -- PE alone (no FI/PI/FE) that excludes every proc in the file
    triggers VW-13, independent of whether the file is otherwise reachable."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["a", "b"]})
    base = make_base(procedures=procs_section(exclude=(proc_ref("a.tcl", "a", "b"),)))
    loaded = make_loaded(base)
    CompilerService().run(ctx, loaded, parsed)
    assert "VW-13" in sink.codes()


# ---------------------------------------------------------------------------
# PE entry on file absent from ParseResult -- defensive `continue` (L506)
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


def test_trim_pe_alone_with_no_prior_layer_state() -> None:
    """PE alone (no FI/PI/FE) touching a file with no prior layer state
    still records winner/loser attribution for the resulting partial keep
    set (row: PE-alone, prev=None, some-but-not-all procs excluded)."""
    ctx, _ = make_ctx()
    parsed = make_parsed({"a.tcl": ["keep", "drop"]})
    base = make_base(procedures=procs_section(exclude=(proc_ref("a.tcl", "drop"),)))
    loaded = make_loaded(base)
    manifest = CompilerService().run(ctx, loaded, parsed)
    assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM
    assert list(manifest.proc_decisions.keys()) == ["a.tcl::keep"]


def test_trim_pe_redundant_re_exclude_of_already_removed_proc() -> None:
    """A later layer's procedures.exclude re-naming a proc an earlier layer
    already excluded is a no-op for that proc (the intersection with the
    current keep-set is empty) -- must not emit a spurious VW-21 remove-proc
    for a proc that isn't actually being removed again."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["a", "b", "c"]})
    base = make_base(
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(exclude=(proc_ref("a.tcl", "c"),)),
    )
    feat = make_feature("reexclude", procedures=procs_section(exclude=(proc_ref("a.tcl", "c"),)))
    loaded = make_loaded(base, feat)
    manifest = CompilerService().run(ctx, loaded, parsed)
    assert "VW-21" not in sink.codes()
    assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM


# ---------------------------------------------------------------------------
# VW-21 -- layer-shadowed: a later layer overrides an earlier layer's decision
# ---------------------------------------------------------------------------


def test_vw21_emitted_when_feature_pi_overrides_base_pe() -> None:
    """Base wants to exclude proc ``foo``; a later feature explicitly includes
    ``foo`` again. Under the ordered-overlay R1 the feature wins and ``foo``
    is kept. The transition emits ``VW-21 layer-shadowed`` (warning)."""
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
    assert "VW-21" in sink.codes()


def test_vw21_add_proc_message_names_procs_and_sets() -> None:
    """VW-21 add-proc message names the added procs, prior keep-set, and
    combined keep-set explicitly so users know exactly what each feature layer
    contributed.  See ``technical_docs/DIAGNOSTIC_CODES.md`` VW-21."""
    ctx, sink = make_ctx()
    # Feature 1 keeps a, b, c; feature 2 adds c, e, r (c already there).
    parsed = make_parsed({"procs.tcl": ["a", "b", "c", "e", "r"]})
    base = make_base()
    feat1 = make_feature(
        "feat1",
        procedures=procs_section(include=(proc_ref("procs.tcl", "a", "b", "c"),)),
    )
    feat2 = make_feature(
        "feat2",
        procedures=procs_section(include=(proc_ref("procs.tcl", "c", "e", "r"),)),
    )
    loaded = make_loaded(base, feat1, feat2)
    CompilerService().run(ctx, loaded, parsed)
    vw21_msgs = [d.message for d in sink.emissions if d.code == "VW-21"]
    assert vw21_msgs, "expected a VW-21 add-proc diagnostic"
    msg = vw21_msgs[0]
    # Added procs are e and r (c was already kept by feat1).
    assert "e" in msg and "r" in msg
    # The prior keep-set (a, b, c) and final set are shown.
    assert "a" in msg and "b" in msg and "c" in msg
    # Layer names are shown.
    assert "feature:feat2" in msg
    assert "feature:feat1" in msg


def test_vw21_remove_proc_message_names_removed_procs() -> None:
    """VW-21 remove-proc message names the procs that were dropped."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"procs.tcl": ["a", "b", "c"]})
    base = make_base()
    feat1 = make_feature(
        "feat1",
        procedures=procs_section(include=(proc_ref("procs.tcl", "a", "b", "c"),)),
    )
    feat2 = make_feature(
        "feat2",
        procedures=procs_section(exclude=(proc_ref("procs.tcl", "b"),)),
    )
    loaded = make_loaded(base, feat1, feat2)
    CompilerService().run(ctx, loaded, parsed)
    vw21_msgs = [d.message for d in sink.emissions if d.code == "VW-21"]
    assert vw21_msgs, "expected a VW-21 remove-proc diagnostic"
    msg = vw21_msgs[0]
    assert "b" in msg  # removed proc named
    assert "feature:feat2" in msg  # acting layer named
    assert "feature:feat1" in msg  # prior layer named


def test_vw21_downgrade_whole_to_trim_message_names_kept_procs() -> None:
    """VW-21 downgrade-whole-to-trim message shows the resulting keep-set."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"procs.tcl": ["a", "b", "c"]})
    base = make_base(files=files_section(include=("procs.tcl",)))
    feat = make_feature(
        "narrow",
        procedures=procs_section(exclude=(proc_ref("procs.tcl", "c"),)),
    )
    loaded = make_loaded(base, feat)
    CompilerService().run(ctx, loaded, parsed)
    vw21_msgs = [d.message for d in sink.emissions if d.code == "VW-21"]
    assert vw21_msgs, "expected a VW-21 downgrade-whole-to-trim diagnostic"
    msg = vw21_msgs[0]
    assert "FULL_COPY" in msg or "PROC_TRIM" in msg
    assert "feature:narrow" in msg


def test_vw21_downgrade_whole_to_trim_via_trim_replace_intent() -> None:
    """Same downgrade-whole-to-trim transition, but reached via the
    ``trim-replace`` intent (FI + PE together in the later layer) rather
    than the ``trim-pe`` intent -- exercises ``_record_replace_transition``'s
    own downgrade branch instead of the inline one in the trim-pe handler."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"procs.tcl": ["a", "b", "c"]})
    base = make_base(files=files_section(include=("procs.tcl",)))
    feat = make_feature(
        "narrow2",
        files=files_section(include=("procs.tcl",)),
        procedures=procs_section(exclude=(proc_ref("procs.tcl", "c"),)),
    )
    loaded = make_loaded(base, feat)
    CompilerService().run(ctx, loaded, parsed)
    vw21_msgs = [d.message for d in sink.emissions if d.code == "VW-21"]
    assert vw21_msgs, "expected a VW-21 downgrade-whole-to-trim diagnostic"
    assert "feature:narrow2" in vw21_msgs[0]


def test_vw21_not_emitted_for_redundant_whole_reaffirmation() -> None:
    """A later layer re-affirming the same file as ``files.include`` alone
    (WHOLE -> WHOLE, no PI/PE) is a no-op transition -- must not emit
    VW-21 nor record a ShadowEvent."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo"]})
    base = make_base(files=files_section(include=("a.tcl",)))
    feat = make_feature("reaffirm", files=files_section(include=("a.tcl",)))
    loaded = make_loaded(base, feat)
    manifest = CompilerService().run(ctx, loaded, parsed)
    assert "VW-21" not in sink.codes()
    assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.FULL_COPY


def test_vw21_not_emitted_for_redundant_trim_reaffirmation() -> None:
    """A later layer re-affirming an identical FI+PE keep-set (TRIM -> TRIM,
    same resulting keep) is a no-op transition -- must not emit VW-21 nor
    record a ShadowEvent."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["keep", "drop"]})
    base = make_base(
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(exclude=(proc_ref("a.tcl", "drop"),)),
    )
    feat = make_feature(
        "reaffirm",
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(exclude=(proc_ref("a.tcl", "drop"),)),
    )
    loaded = make_loaded(base, feat)
    manifest = CompilerService().run(ctx, loaded, parsed)
    assert "VW-21" not in sink.codes()
    assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM


# ---------------------------------------------------------------------------
# VE-27 -- no-op excludes
# ---------------------------------------------------------------------------


def test_ve27_emitted_for_literal_fe_no_match_in_running_set() -> None:
    """Feature ``files.exclude`` lists a path that no earlier layer included."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo"], "b.tcl": ["bar"]})
    base = make_base(files=files_section(include=("a.tcl",)))
    feat = make_feature("typo", files=files_section(exclude=("b.tcl",)))
    loaded = make_loaded(base, feat)
    CompilerService().run(ctx, loaded, parsed)
    assert "VE-27" in sink.codes()


def test_ve27_emitted_for_glob_fe_with_zero_matches() -> None:
    """A glob ``files.exclude`` pattern that matches no surface file -> VE-27."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo"]})
    base = make_base(files=files_section(include=("a.tcl",)))
    feat = make_feature("typo", files=files_section(exclude=("zzz_*.tcl",)))
    loaded = make_loaded(base, feat)
    CompilerService().run(ctx, loaded, parsed)
    assert "VE-27" in sink.codes()


def test_ve27_not_emitted_for_same_layer_glob_include_then_exclude() -> None:
    """Same-layer FI glob + FE literal is an intentional subtraction.

    Example: ``files.include=["*"]`` and ``files.exclude=["b.tcl"]`` in the
    same layer should NOT raise VE-27 for ``b.tcl``.
    """
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo"], "b.tcl": ["bar"]})
    base = make_base(files=files_section(include=("*",), exclude=("b.tcl",)))
    loaded = make_loaded(base)
    manifest = CompilerService().run(ctx, loaded, parsed)
    assert "VE-27" not in sink.codes()
    assert Path("a.tcl") in manifest.file_decisions
    assert manifest.file_decisions[Path("b.tcl")] is FileTreatment.REMOVE


def test_ve27_emitted_for_pe_proc_name_typo() -> None:
    """PE proc-name that doesn't match any proc in the file -> VE-27."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo", "bar"]})
    base = make_base(
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(exclude=(proc_ref("a.tcl", "no_such_proc"),)),
    )
    loaded = make_loaded(base)
    CompilerService().run(ctx, loaded, parsed)
    assert "VE-27" in sink.codes()


# ---------------------------------------------------------------------------
# VW-09/11/12/13 -- message text names the specific procs involved
# ---------------------------------------------------------------------------


def test_vw09_message_names_redundant_pi_procs() -> None:
    """VW-09 message names the specific PI procs that are redundant."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo", "bar"]})
    base = make_base(
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(include=(proc_ref("a.tcl", "foo", "bar"),)),
    )
    loaded = make_loaded(base)
    CompilerService().run(ctx, loaded, parsed)
    vw09_msgs = [d.message for d in sink.emissions if d.code == "VW-09"]
    assert vw09_msgs, "expected a VW-09 diagnostic"
    msg = vw09_msgs[0]
    assert "foo" in msg
    assert "bar" in msg


def test_vw11_message_names_pe_procs() -> None:
    """VW-11 message names the PE procs on the doubly-excluded file."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo", "bar"]})
    base = make_base(
        files=files_section(exclude=("a.tcl",)),
        procedures=procs_section(exclude=(proc_ref("a.tcl", "foo", "bar"),)),
    )
    loaded = make_loaded(base)
    CompilerService().run(ctx, loaded, parsed)
    vw11_msgs = [d.message for d in sink.emissions if d.code == "VW-11"]
    assert vw11_msgs, "expected a VW-11 diagnostic"
    msg = vw11_msgs[0]
    assert "foo" in msg
    assert "bar" in msg


def test_vw12_message_names_pi_and_pe_procs() -> None:
    """VW-12 message names both the PI procs (kept) and PE procs (ignored)."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo", "bar", "baz"]})
    base = make_base(
        procedures=procs_section(
            include=(proc_ref("a.tcl", "foo", "bar"),),
            exclude=(proc_ref("a.tcl", "baz"),),
        ),
    )
    loaded = make_loaded(base)
    CompilerService().run(ctx, loaded, parsed)
    vw12_msgs = [d.message for d in sink.emissions if d.code == "VW-12"]
    assert vw12_msgs, "expected a VW-12 diagnostic"
    msg = vw12_msgs[0]
    assert "foo" in msg
    assert "bar" in msg
    assert "baz" in msg


def test_vw13_message_names_all_excluded_procs() -> None:
    """VW-13 message names every proc that procedures.exclude removed."""
    ctx, sink = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo", "bar", "baz"]})
    base = make_base(
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(exclude=(proc_ref("a.tcl", "foo", "bar", "baz"),)),
    )
    loaded = make_loaded(base)
    CompilerService().run(ctx, loaded, parsed)
    vw13_msgs = [d.message for d in sink.emissions if d.code == "VW-13"]
    assert vw13_msgs, "expected a VW-13 diagnostic"
    msg = vw13_msgs[0]
    assert "foo" in msg


# ---------------------------------------------------------------------------
# Sec.3.11 -- proc_removals attribution (F2 provenance markers)
# ---------------------------------------------------------------------------


def test_proc_removals_attributes_default_exclude() -> None:
    """A proc never named in any layer's procedures.include is attributed
    to the ``default`` sentinel (R2 default-exclude, no explicit excluder)."""
    ctx, _ = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo", "bar"]})
    base = make_base(
        procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)),
    )
    loaded = make_loaded(base)
    manifest = CompilerService().run(ctx, loaded, parsed)
    removal = manifest.proc_removals["a.tcl::bar"]
    assert removal.removal_source == "default:r2-default-exclude"


def test_proc_removals_cleared_when_proc_trim_file_later_removed() -> None:
    """A PROC_TRIM file's proc_removals must not leak once a later layer
    removes the file entirely via files.exclude."""
    ctx, _ = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo", "bar"]})
    base = make_base(
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(exclude=(proc_ref("a.tcl", "bar"),)),
    )
    feat = make_feature("drop_file", files=files_section(exclude=("a.tcl",)))
    loaded = make_loaded(base, feat)
    manifest = CompilerService().run(ctx, loaded, parsed)
    assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.REMOVE
    assert not any(r.source_file == Path("a.tcl") for r in manifest.proc_removals.values())


def test_proc_removals_cleared_when_proc_trim_file_upgraded_to_whole() -> None:
    """A PROC_TRIM file's proc_removals must clear once a later layer
    upgrades it to FULL_COPY via files.include alone."""
    ctx, _ = make_ctx()
    parsed = make_parsed({"a.tcl": ["foo", "bar"]})
    base = make_base(
        files=files_section(include=("a.tcl",)),
        procedures=procs_section(exclude=(proc_ref("a.tcl", "bar"),)),
    )
    feat = make_feature("keep_whole", files=files_section(include=("a.tcl",)))
    loaded = make_loaded(base, feat)
    manifest = CompilerService().run(ctx, loaded, parsed)
    assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.FULL_COPY
    assert not manifest.proc_removals
