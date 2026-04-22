"""Unit tests for :mod:`chopper.compiler.flow_resolver`.

Covers the full action vocabulary (bible §6.7) plus the three explicit
diagnostics the resolver owns:

* ``VE-10`` — ``@n`` index overflow.
* ``VE-19`` — ``@0`` occurrence suffix.
* ``VE-20`` — ambiguous step target without ``@n``.
"""

from __future__ import annotations

import pytest

from chopper.compiler.flow_resolver import resolve_stages
from chopper.core.errors import ChopperError
from chopper.core.models import (
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
# Feature + action ordering (bible §6.7)
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
# Programmer-error paths
# ---------------------------------------------------------------------------


def test_missing_stage_reference_raises() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a"),)
    feat = _make_feature("feat", RemoveStepAction(action="remove_step", stage="nope", reference="a"))
    with pytest.raises(ChopperError, match="missing stage"):
        resolve_stages(ctx, base, (feat,))


def test_missing_step_reference_raises() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a"),)
    feat = _make_feature("feat", RemoveStepAction(action="remove_step", stage="setup", reference="nope"))
    with pytest.raises(ChopperError, match="not found"):
        resolve_stages(ctx, base, (feat,))


def test_duplicate_stage_names_in_base_raises() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a"), _sd("setup", "b"))
    with pytest.raises(ChopperError, match="duplicate names"):
        resolve_stages(ctx, base, ())


def test_add_stage_that_already_exists_raises() -> None:
    ctx, _ = make_ctx()
    base = (_sd("setup", "a"), _sd("run", "r"))
    dup = _sd("setup", "zzz")
    feat = _make_feature("feat", AddStageAction(action="add_stage_after", reference="run", stage=dup))
    with pytest.raises(ChopperError, match="duplicate stage"):
        resolve_stages(ctx, base, (feat,))
