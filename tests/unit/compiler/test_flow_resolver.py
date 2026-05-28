"""Unit tests for :mod:`chopper.compiler.flow_resolver`.

Covers the full action vocabulary (architecture doc §6.7) plus the
resolver-owned diagnostics:

* ``VE-05`` — missing stage / step target on any flow_action.
* ``VE-08`` — duplicate stage name created by ``add_stage_*`` /
  ``replace_stage``.
* ``VE-10`` — ``@n`` index overflow.
* ``VE-19`` — ``@0`` occurrence suffix.
* ``VE-20`` — ambiguous step target without ``@n``.
"""

from __future__ import annotations

import pytest

from chopper.compiler.flow_resolver import resolve_stages
from chopper.core.errors import ChopperError
from chopper.core.models_config import (
    AddStageAction,
    AddStepAction,
    FeatureJson,
    LoadFromAction,
    RemoveStageAction,
    RemoveStepAction,
    ReplaceStageAction,
    ReplaceStepAction,
    StageDefinition,
)

from ._helpers import make_ctx, make_feature

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _sd(name: str, *steps: str, load_from: str = "") -> StageDefinition:
    return StageDefinition(name=name, load_from=load_from, steps=tuple(steps))


def _make_feature(name: str, *actions) -> FeatureJson:
    """Build a ``FeatureJson`` with the given ``flow_actions``."""

    from dataclasses import replace

    return replace(make_feature(name), flow_actions=tuple(actions))


# ---------------------------------------------------------------------------
# Happy paths — one action at a time
# ---------------------------------------------------------------------------


def test_base_only_returns_stages_unchanged() -> None:
    ctx, sink = make_ctx()
    base = (_sd("setup", "a", "b"), _sd("run", "x"))
    out = resolve_stages(ctx, base, ())
    assert tuple((s.name, s.steps) for s in out) == (("setup", ("a", "b")), ("run", ("x",)))
    assert sink.codes() == []


def test_add_step_before_and_after() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a", "b", "c"),)
    feat = _make_feature(
        "feat",
        AddStepAction(action="add_step_before", stage="setup", reference="b", items=("pre1", "pre2")),
        AddStepAction(action="add_step_after", stage="setup", reference="c", items=("post",)),
    )
    out = resolve_stages(ctx, base, (feat,))
    assert out[0].steps == ("a", "pre1", "pre2", "b", "c", "post")


def test_remove_step() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a", "b", "c"),)
    feat = _make_feature("feat", RemoveStepAction(action="remove_step", stage="setup", reference="b"))
    out = resolve_stages(ctx, base, (feat,))
    assert out[0].steps == ("a", "c")


def test_replace_step() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a", "b", "c"),)
    feat = _make_feature(
        "feat",
        ReplaceStepAction(action="replace_step", stage="setup", reference="b", replacement="B!"),
    )
    out = resolve_stages(ctx, base, (feat,))
    assert out[0].steps == ("a", "B!", "c")


def test_add_stage_before_and_after() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a"), _sd("run", "x"))
    new_stage = _sd("prep", "p")
    new_stage2 = _sd("verify", "v")
    feat = _make_feature(
        "feat",
        AddStageAction(action="add_stage_before", reference="run", stage=new_stage),
        AddStageAction(action="add_stage_after", reference="run", stage=new_stage2),
    )
    out = resolve_stages(ctx, base, (feat,))
    assert tuple(s.name for s in out) == ("setup", "prep", "run", "verify")


def test_remove_stage() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a"), _sd("drop_me", "x"), _sd("run", "r"))
    feat = _make_feature("feat", RemoveStageAction(action="remove_stage", reference="drop_me"))
    out = resolve_stages(ctx, base, (feat,))
    assert tuple(s.name for s in out) == ("setup", "run")


def test_replace_stage_rewrites_load_from() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a"), _sd("run", "r", load_from="setup"))
    replacement = _sd("setup2", "a2")
    feat = _make_feature("feat", ReplaceStageAction(action="replace_stage", reference="setup", replacement=replacement))
    out = resolve_stages(ctx, base, (feat,))
    assert tuple(s.name for s in out) == ("setup2", "run")
    assert out[1].load_from == "setup2"


def test_load_from_action() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a"), _sd("run", "r"))
    feat = _make_feature("feat", LoadFromAction(action="load_from", stage="run", reference="setup"))
    out = resolve_stages(ctx, base, (feat,))
    assert out[1].load_from == "setup"


# ---------------------------------------------------------------------------
# Feature + action ordering (architecture doc §6.7)
# ---------------------------------------------------------------------------


def test_features_applied_in_selection_order() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a"),)
    f1 = _make_feature("f1", AddStepAction(action="add_step_after", stage="setup", reference="a", items=("from_f1",)))
    f2 = _make_feature(
        "f2", AddStepAction(action="add_step_after", stage="setup", reference="from_f1", items=("from_f2",))
    )
    out = resolve_stages(ctx, base, (f1, f2))
    assert out[0].steps == ("a", "from_f1", "from_f2")


def test_actions_within_feature_applied_top_to_bottom() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a"),)
    feat = _make_feature(
        "feat",
        AddStepAction(action="add_step_after", stage="setup", reference="a", items=("b",)),
        AddStepAction(action="add_step_after", stage="setup", reference="b", items=("c",)),
    )
    out = resolve_stages(ctx, base, (feat,))
    assert out[0].steps == ("a", "b", "c")


def test_add_step_after_preserves_project_order_for_shared_anchor() -> None:
    """Three features sharing one anchor must emit in selected feature order.

    Per architecture doc §6.7 (Order Preservation for ``add_*_after`` actions),
    when N features each ``add_step_after`` on the same anchor, the resolver
    must preserve the **selected feature order** — i.e. the order in which
    ``LoadedConfig.features`` carries them, which is the same whether the
    selection comes from ``project.json`` ``features[]`` (``--project``) or
    from a comma-separated ``--features`` CLI list. ``f1`` items first, then
    ``f2``, then ``f3``. The naive implementation re-resolves the anchor each
    call and silently REVERSES that order — this test guards against the
    regression.
    """

    ctx, _ = make_ctx()
    base = (_sd("setup", "anchor"),)
    f1 = _make_feature("f1", AddStepAction(action="add_step_after", stage="setup", reference="anchor", items=("a1",)))
    f2 = _make_feature(
        "f2", AddStepAction(action="add_step_after", stage="setup", reference="anchor", items=("b1", "b2"))
    )
    f3 = _make_feature("f3", AddStepAction(action="add_step_after", stage="setup", reference="anchor", items=("c1",)))
    out = resolve_stages(ctx, base, (f1, f2, f3))
    assert out[0].steps == ("anchor", "a1", "b1", "b2", "c1")


def test_add_stage_after_preserves_project_order_for_shared_anchor() -> None:
    """Three features each adding a new stage after the same reference must
    emit in selected feature order (architecture doc §6.7). The selection
    source (``--project`` vs ``--features``) is irrelevant: both surfaces
    populate ``LoadedConfig.features`` with the same ordering contract."""

    ctx, _ = make_ctx()
    base = (_sd("setup", "s"), _sd("anchor", "x"), _sd("end", "z"))
    f1 = _make_feature("f1", AddStageAction(action="add_stage_after", reference="anchor", stage=_sd("st1", "s1")))
    f2 = _make_feature("f2", AddStageAction(action="add_stage_after", reference="anchor", stage=_sd("st2", "s2")))
    f3 = _make_feature("f3", AddStageAction(action="add_stage_after", reference="anchor", stage=_sd("st3", "s3")))
    out = resolve_stages(ctx, base, (f1, f2, f3))
    assert tuple(s.name for s in out) == ("setup", "anchor", "st1", "st2", "st3", "end")


# ---------------------------------------------------------------------------
# @n resolution + diagnostics
# ---------------------------------------------------------------------------


def test_at_one_equivalent_to_no_suffix() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a", "b"),)
    feat = _make_feature("feat", RemoveStepAction(action="remove_step", stage="setup", reference="a@1"))
    out = resolve_stages(ctx, base, (feat,))
    assert out[0].steps == ("b",)


def test_at_n_selects_nth_occurrence() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a", "dup", "b", "dup", "c"),)
    feat = _make_feature(
        "feat",
        ReplaceStepAction(action="replace_step", stage="setup", reference="dup@2", replacement="DUP!"),
    )
    out = resolve_stages(ctx, base, (feat,))
    assert out[0].steps == ("a", "dup", "b", "DUP!", "c")


def test_at_zero_emits_ve19_and_skips() -> None:
    ctx, sink = make_ctx()
    base = (_sd("setup", "a", "b"),)
    feat = _make_feature("feat", RemoveStepAction(action="remove_step", stage="setup", reference="a@0"))
    out = resolve_stages(ctx, base, (feat,))
    assert sink.codes() == ["VE-19"]
    # Action was skipped.
    assert out[0].steps == ("a", "b")


def test_at_overflow_emits_ve10_and_skips() -> None:
    ctx, sink = make_ctx()
    base = (_sd("setup", "a", "dup", "dup"),)
    feat = _make_feature(
        "feat",
        RemoveStepAction(action="remove_step", stage="setup", reference="dup@3"),
    )
    out = resolve_stages(ctx, base, (feat,))
    assert sink.codes() == ["VE-10"]
    assert out[0].steps == ("a", "dup", "dup")


def test_ambiguous_target_without_suffix_emits_ve20() -> None:
    ctx, sink = make_ctx()
    base = (_sd("setup", "a", "dup", "dup"),)
    feat = _make_feature(
        "feat",
        ReplaceStepAction(action="replace_step", stage="setup", reference="dup", replacement="NEW"),
    )
    out = resolve_stages(ctx, base, (feat,))
    assert sink.codes() == ["VE-20"]
    assert out[0].steps == ("a", "dup", "dup")


# ---------------------------------------------------------------------------
# User-input target-miss paths (emit diagnostics, do not raise)
# ---------------------------------------------------------------------------


def test_missing_stage_reference_emits_ve05() -> None:
    ctx, sink = make_ctx()
    base = (_sd("setup", "a"),)
    feat = _make_feature("feat", RemoveStepAction(action="remove_step", stage="nope", reference="a"))
    out = resolve_stages(ctx, base, (feat,))
    # Action is skipped; base stages pass through untouched.
    assert sink.codes() == ["VE-05"]
    assert tuple(s.name for s in out) == ("setup",)
    assert out[0].steps == ("a",)


def test_missing_step_reference_emits_ve05() -> None:
    ctx, sink = make_ctx()
    base = (_sd("setup", "a"),)
    feat = _make_feature("feat", RemoveStepAction(action="remove_step", stage="setup", reference="nope"))
    out = resolve_stages(ctx, base, (feat,))
    assert sink.codes() == ["VE-05"]
    assert out[0].steps == ("a",)


def test_duplicate_stage_names_in_base_raises() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a"), _sd("setup", "b"))
    with pytest.raises(ChopperError, match="duplicate names"):
        resolve_stages(ctx, base, ())


def test_add_stage_that_already_exists_emits_ve08() -> None:
    ctx, sink = make_ctx()
    base = (_sd("setup", "a"), _sd("run", "r"))
    dup = _sd("setup", "zzz")
    feat = _make_feature("feat", AddStageAction(action="add_stage_after", reference="run", stage=dup))
    out = resolve_stages(ctx, base, (feat,))
    # Action is skipped; base stage sequence is unchanged.
    assert sink.codes() == ["VE-08"]
    assert tuple(s.name for s in out) == ("setup", "run")


# ---------------------------------------------------------------------------
# skip_if_no_stage — architecture doc §6.7 'Optional Stage Targets'
# ---------------------------------------------------------------------------


def test_skip_if_no_stage_emits_vi05_and_skips_add_step() -> None:
    """An ``add_step_after`` whose target stage is absent and which
    declared ``skip_if_no_stage=true`` emits VI-05 and skips silently.
    """
    ctx, sink = make_ctx()
    base = (_sd("setup", "a"),)
    feat = _make_feature(
        "feat",
        AddStepAction(
            action="add_step_after",
            stage="missing_stage",
            reference="anchor",
            items=("new",),
            skip_if_no_stage=True,
        ),
    )
    out = resolve_stages(ctx, base, (feat,))
    assert sink.codes() == ["VI-05"]
    # Base sequence untouched.
    assert tuple((s.name, s.steps) for s in out) == (("setup", ("a",)),)


def test_skip_if_no_stage_default_false_still_emits_ve05() -> None:
    """Backward-compat: omitting ``skip_if_no_stage`` keeps the strict
    VE-05 behaviour. (Default value path.)"""
    ctx, sink = make_ctx()
    base = (_sd("setup", "a"),)
    feat = _make_feature(
        "feat",
        AddStepAction(action="add_step_after", stage="missing_stage", reference="a", items=("x",)),
    )
    resolve_stages(ctx, base, (feat,))
    assert sink.codes() == ["VE-05"]


def test_skip_if_no_stage_present_stage_step_miss_still_emits_ve05() -> None:
    """``skip_if_no_stage=true`` softens stage-not-found only. A step
    miss inside a present stage is still a hard VE-05 (per §6.7
    'step-level miss is unaffected')."""
    ctx, sink = make_ctx()
    base = (_sd("setup", "a"),)
    feat = _make_feature(
        "feat",
        RemoveStepAction(
            action="remove_step",
            stage="setup",
            reference="nope",
            skip_if_no_stage=True,
        ),
    )
    out = resolve_stages(ctx, base, (feat,))
    assert sink.codes() == ["VE-05"]
    assert out[0].steps == ("a",)


def test_skip_if_no_stage_present_stage_runs_normally() -> None:
    """When the target stage *is* present, ``skip_if_no_stage=true`` is
    a no-op: the action runs identically to the strict path."""
    ctx, sink = make_ctx()
    base = (_sd("setup", "a", "b"),)
    feat = _make_feature(
        "feat",
        AddStepAction(
            action="add_step_after",
            stage="setup",
            reference="a",
            items=("a2",),
            skip_if_no_stage=True,
        ),
    )
    out = resolve_stages(ctx, base, (feat,))
    assert sink.codes() == []
    assert out[0].steps == ("a", "a2", "b")


@pytest.mark.parametrize(
    "action_builder",
    [
        lambda: RemoveStepAction(action="remove_step", stage="absent", reference="x", skip_if_no_stage=True),
        lambda: ReplaceStepAction(
            action="replace_step", stage="absent", reference="x", replacement="y", skip_if_no_stage=True
        ),
        lambda: RemoveStageAction(action="remove_stage", reference="absent", skip_if_no_stage=True),
        lambda: ReplaceStageAction(
            action="replace_stage",
            reference="absent",
            replacement=_sd("new", "n"),
            skip_if_no_stage=True,
        ),
        lambda: AddStageAction(
            action="add_stage_after",
            reference="absent",
            stage=_sd("new", "n"),
            skip_if_no_stage=True,
        ),
        lambda: LoadFromAction(action="load_from", stage="absent", reference="setup", skip_if_no_stage=True),
    ],
    ids=["remove_step", "replace_step", "remove_stage", "replace_stage", "add_stage_after", "load_from"],
)
def test_skip_if_no_stage_applies_to_all_variants(action_builder) -> None:
    """Every flow_action variant honours ``skip_if_no_stage`` for the
    stage-not-found path."""
    ctx, sink = make_ctx()
    base = (_sd("setup", "a"),)
    feat = _make_feature("feat", action_builder())
    out = resolve_stages(ctx, base, (feat,))
    assert sink.codes() == ["VI-05"]
    # Working sequence unchanged.
    assert tuple((s.name, s.steps) for s in out) == (("setup", ("a",)),)


# ---------------------------------------------------------------------------
# VE-05 default (skip_if_no_stage=False) for each action variant that
# targets a stage. Covers the branches missed by the parametrized VI-05 test.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action_builder",
    [
        lambda: ReplaceStepAction(action="replace_step", stage="absent", reference="x", replacement="y"),
        lambda: RemoveStageAction(action="remove_stage", reference="absent"),
        lambda: ReplaceStageAction(action="replace_stage", reference="absent", replacement=_sd("new", "n")),
        lambda: AddStageAction(action="add_stage_after", reference="absent", stage=_sd("new", "n")),
        lambda: AddStageAction(action="add_stage_before", reference="absent", stage=_sd("new", "n")),
        lambda: LoadFromAction(action="load_from", stage="absent", reference="setup"),
    ],
    ids=["replace_step", "remove_stage", "replace_stage", "add_stage_after", "add_stage_before", "load_from"],
)
def test_ve05_default_for_all_stage_targeting_variants(action_builder) -> None:
    """Without ``skip_if_no_stage``, targeting an absent stage emits VE-05
    for every action variant that checks stage existence."""
    ctx, sink = make_ctx()
    base = (_sd("setup", "a"),)
    feat = _make_feature("feat", action_builder())
    out = resolve_stages(ctx, base, (feat,))
    assert sink.codes() == ["VE-05"]
    assert tuple((s.name, s.steps) for s in out) == (("setup", ("a",)),)
