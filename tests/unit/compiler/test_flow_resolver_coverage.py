"""Per-file coverage tests for src/chopper/compiler/flow_resolver.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_flow_resolver_find_stage_index_returns_none_for_unknown() -> None:
    from chopper.compiler.flow_resolver import _find_stage_index, _MutableStage  # type: ignore[attr-defined]
    from chopper.core.models_config import StageDefinition

    s = _MutableStage.from_definition(StageDefinition(name="a", load_from="base", steps=("step1",)))
    assert _find_stage_index([s], "nope") is None


def test_flow_resolver_find_stage_returns_none_for_unknown() -> None:
    from chopper.compiler.flow_resolver import _find_stage, _MutableStage  # type: ignore[attr-defined]
    from chopper.core.models_config import StageDefinition

    s = _MutableStage.from_definition(StageDefinition(name="a", load_from="base", steps=("step1",)))
    assert _find_stage([s], "nope") is None


def test_replace_stage_with_identical_name_skips_load_from_rewrite() -> None:
    """``_apply_replace_stage`` (branch 425→exit): when the replacement's
    ``name`` equals the old stage's name, the load_from-rewrite loop must
    be skipped entirely. The replacement is installed in place and no
    duplicate-stage error is raised even if another stage references the
    same name via ``load_from``.
    """
    from chopper.compiler.flow_resolver import _apply_replace_stage, _MutableStage  # type: ignore[attr-defined]
    from chopper.core.models_config import ReplaceStageAction, StageDefinition

    s_a = _MutableStage.from_definition(StageDefinition(name="alpha", load_from="base", steps=("old_step",)))
    s_b = _MutableStage.from_definition(StageDefinition(name="beta", load_from="alpha", steps=("b_step",)))
    working = [s_a, s_b]

    replacement_def = StageDefinition(name="alpha", load_from="base", steps=("new_step",))
    action = ReplaceStageAction(
        action="replace_stage",
        reference="alpha",
        replacement=replacement_def,
    )
    ctx = _ctx()
    _apply_replace_stage(ctx, working, action, feature_name="feat")

    # Replacement installed at the same index, same name.
    assert working[0].name == "alpha"
    assert list(working[0].steps) == ["new_step"]
    # ``beta`` still references "alpha" (the load_from-rewrite loop did
    # NOT run because replacement.name == old_name).
    assert working[1].load_from == "alpha"
