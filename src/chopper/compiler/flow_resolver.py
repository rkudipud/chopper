"""F3 flow-action resolver.

Consumes the base stage sequence and every selected feature's ordered
``flow_actions`` and returns the resolved tuple of :class:`StageSpec`.

Resolver is reporting-only for feature order, authoritative for F3
ordering:

* features are applied in selection order (:attr:`LoadedConfig.features`,
  already topo-sorted by the loader);
* within one feature, actions apply top-to-bottom;
* ``@n`` instance targeting on step-level actions follows 1-based
  indexing; ``@0`` is an error.

**Order-preservation contract (R1 ordered overlay for F3):**

When multiple features share the same anchor for an ``add_step_after``
or ``add_stage_after`` action, the **selected feature order** is
preserved verbatim in the emitted output. "Selected feature order"
is whatever order :attr:`LoadedConfig.features` carries — i.e. the
order declared in ``project.json`` ``features[]`` when invoked with
``--project``, or the order passed on the command line via
``--features f1.feature.json,f2.feature.json,...``. The two surfaces
are equivalent: the same overlay contract that R1 already enforces
for F1 (file decisions) and F2 (proc decisions) in
``merge_service.py`` is enforced here for F3 (stage / step
decisions).

Concretely, given anchor ``X`` in stage ``S`` and selected
``features = [F1, F2, F3]`` each with ``add_step_after S:X``, the
resolved step sequence around the anchor is::

    ..., X, <items from F1>, <items from F2>, <items from F3>, ...

The resolver tracks a cumulative insertion offset per ``(stage, anchor)``
pair so each subsequent same-anchor ``add_step_after`` lands *after* the
prior feature's items, not directly after the anchor. The same
contract holds for ``add_stage_after`` keyed on ``reference`` stage
name. ``add_step_before`` and ``add_stage_before`` already preserve
selected feature order naturally because each insertion sits
immediately before a shifted anchor, so no offset tracking is required
for them. Order-independent F3 actions (``replace_step``,
``replace_stage``, ``remove_step``, ``remove_stage``, ``load_from``)
follow last-layer-wins semantics, which is consistent with R1.

Diagnostics emitted:

* ``VE-10 occurrence-suffix-overflow`` — ``@n`` with *n* exceeding the
  number of matching steps in the stage.
* ``VE-19 occurrence-suffix-zero`` — ``@0``; indices are 1-based.
* ``VE-20 ambiguous-step-target`` — a step-level action with no ``@n``
  where the step string appears more than once in the stage.

Programmer-error conditions (missing stage target, unknown action kind)
raise :class:`ChopperError` and the runner maps that to exit 3.
"""

from __future__ import annotations

import re
from dataclasses import replace

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.errors import ChopperError
from chopper.core.models_compiler import StageSpec
from chopper.core.models_config import (
    AddStageAction,
    AddStepAction,
    FeatureJson,
    FlowAction,
    LoadFromAction,
    RemoveStageAction,
    RemoveStepAction,
    ReplaceStageAction,
    ReplaceStepAction,
    StageDefinition,
)

__all__ = ["resolve_stages"]


# ``step@n`` — ``@n`` applies to the trailing integer only; step strings
# themselves may contain ``@`` characters, so we only honor a suffix when
# it matches ``@<digits>`` at end-of-string.
_SUFFIX_RE = re.compile(r"@(\d+)$")


def _split_reference(ref: str) -> tuple[str, int | None]:
    """Split ``step@n`` into ``("step", n)``. ``n`` is ``None`` if absent."""

    match = _SUFFIX_RE.search(ref)
    if match is None:
        return ref, None
    suffix = int(match.group(1))
    return ref[: match.start()], suffix


def resolve_stages(
    ctx: ChopperContext,
    base_stages: tuple[StageDefinition, ...],
    features: tuple[FeatureJson, ...],
) -> tuple[StageSpec, ...]:
    """Return the resolved stage sequence.

    The input ``base_stages`` is never mutated; the resolver works on a
    list-of-lists copy internally.
    """

    # Working state: list of dicts so we can mutate steps in place.
    working: list[_MutableStage] = [_MutableStage.from_definition(s) for s in base_stages]

    _assert_unique_stage_names(working)

    # Per-resolve cumulative-offset trackers used to preserve
    # project-declared feature order for ``add_*_after`` actions when
    # multiple features share the same anchor. See module docstring.
    step_after_offsets: dict[tuple[str, str, int | None], int] = {}
    stage_after_offsets: dict[str, int] = {}

    for feature in features:
        for action in feature.flow_actions:
            _apply_action(
                ctx,
                working,
                action,
                feature_name=feature.name,
                step_after_offsets=step_after_offsets,
                stage_after_offsets=stage_after_offsets,
            )

    return tuple(ms.freeze() for ms in working)


# ---------------------------------------------------------------------------
# Mutable staging types (used only inside this module)
# ---------------------------------------------------------------------------


class _MutableStage:
    """Mutable twin of :class:`StageDefinition` used during resolution."""

    __slots__ = (
        "name",
        "load_from",
        "steps",
        "dependencies",
        "exit_codes",
        "command",
        "inputs",
        "outputs",
        "run_mode",
        "language",
    )

    def __init__(
        self,
        name: str,
        load_from: str,
        steps: list[str],
        dependencies: tuple[str, ...],
        exit_codes: tuple[int, ...],
        command: str | None,
        inputs: tuple[str, ...],
        outputs: tuple[str, ...],
        run_mode: str,
        language: str,
    ) -> None:
        self.name = name
        self.load_from = load_from
        self.steps = steps
        self.dependencies = dependencies
        self.exit_codes = exit_codes
        self.command = command
        self.inputs = inputs
        self.outputs = outputs
        self.run_mode = run_mode
        self.language = language

    @classmethod
    def from_definition(cls, sd: StageDefinition) -> _MutableStage:
        return cls(
            name=sd.name,
            load_from=sd.load_from,
            steps=list(sd.steps),
            dependencies=sd.dependencies,
            exit_codes=sd.exit_codes,
            command=sd.command,
            inputs=sd.inputs,
            outputs=sd.outputs,
            run_mode=sd.run_mode,
            language=sd.language,
        )

    def freeze(self) -> StageSpec:
        return StageSpec(
            name=self.name,
            load_from=self.load_from,
            steps=tuple(self.steps),
            dependencies=self.dependencies,
            exit_codes=self.exit_codes,
            command=self.command,
            inputs=self.inputs,
            outputs=self.outputs,
            run_mode=self.run_mode,  # type: ignore[arg-type]
            language=self.language,  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Action dispatch
# ---------------------------------------------------------------------------


def _apply_action(
    ctx: ChopperContext,
    working: list[_MutableStage],
    action: FlowAction,
    *,
    feature_name: str,
    step_after_offsets: dict[tuple[str, str, int | None], int],
    stage_after_offsets: dict[str, int],
) -> None:
    if isinstance(action, AddStepAction):
        _apply_add_step(
            ctx,
            working,
            action,
            feature_name=feature_name,
            step_after_offsets=step_after_offsets,
        )
    elif isinstance(action, RemoveStepAction):
        _apply_remove_step(ctx, working, action, feature_name=feature_name)
    elif isinstance(action, ReplaceStepAction):
        _apply_replace_step(ctx, working, action, feature_name=feature_name)
    elif isinstance(action, AddStageAction):
        _apply_add_stage(working, action, stage_after_offsets=stage_after_offsets)
    elif isinstance(action, RemoveStageAction):
        _apply_remove_stage(working, action)
    elif isinstance(action, ReplaceStageAction):
        _apply_replace_stage(working, action)
    elif isinstance(action, LoadFromAction):
        _apply_load_from(working, action)
    else:  # pragma: no cover — exhaustive dispatch
        raise ChopperError(f"unknown FlowAction variant: {type(action).__name__}")


def _find_stage(working: list[_MutableStage], name: str) -> _MutableStage:
    for stage in working:
        if stage.name == name:
            return stage
    raise ChopperError(f"flow_action references missing stage {name!r}")


def _find_stage_index(working: list[_MutableStage], name: str) -> int:
    for i, stage in enumerate(working):
        if stage.name == name:
            return i
    raise ChopperError(f"flow_action references missing stage {name!r}")


def _resolve_step_index(
    ctx: ChopperContext,
    stage: _MutableStage,
    reference: str,
    *,
    feature_name: str,
    action_kind: str,
) -> int | None:
    """Return the 0-based step index matched by ``reference``.

    Returns ``None`` when the resolver emits a diagnostic (caller skips
    the action). ``@1`` equals no ``@``; ``@0`` fires ``VE-19``;
    ``@n`` above the match count fires ``VE-10``; duplicate matches
    without ``@n`` fire ``VE-20``.
    """

    step_value, suffix = _split_reference(reference)
    matches = [i for i, s in enumerate(stage.steps) if s == step_value]

    if suffix is not None:
        if suffix == 0:
            _emit_ve19(ctx, feature=feature_name, stage=stage.name, reference=reference, action=action_kind)
            return None
        if suffix > len(matches):
            _emit_ve10(
                ctx,
                feature=feature_name,
                stage=stage.name,
                reference=reference,
                action=action_kind,
                count=len(matches),
            )
            return None
        return matches[suffix - 1]

    if len(matches) == 0:
        raise ChopperError(
            f"flow_action {action_kind} in feature {feature_name!r} references step "
            f"{reference!r} not found in stage {stage.name!r}"
        )
    if len(matches) > 1:
        _emit_ve20(
            ctx,
            feature=feature_name,
            stage=stage.name,
            reference=reference,
            action=action_kind,
            count=len(matches),
        )
        return None
    return matches[0]


# ---- step-level actions ----------------------------------------------------


def _apply_add_step(
    ctx: ChopperContext,
    working: list[_MutableStage],
    action: AddStepAction,
    *,
    feature_name: str,
    step_after_offsets: dict[tuple[str, str, int | None], int],
) -> None:
    stage = _find_stage(working, action.stage)
    idx = _resolve_step_index(ctx, stage, action.reference, feature_name=feature_name, action_kind=action.action)
    if idx is None:
        return
    if action.action == "add_step_before":
        # Anchor index is re-resolved each call; previous insertions
        # before the anchor have already shifted the anchor down, so
        # this insertion lands immediately before the (shifted) anchor
        # and naturally preserves selected feature order.
        insertion = idx
    else:
        # add_step_after: preserve selected feature order by walking
        # past prior same-anchor insertions from earlier features. The
        # reference string plus its ``@n`` suffix (if any) uniquely
        # identifies the anchor occurrence, so we key the offset on
        # it. "Selected feature order" = order of
        # :attr:`LoadedConfig.features`, whether it came from
        # ``project.json`` ``features[]`` or the ``--features`` CLI
        # flag.
        _step_value, suffix = _split_reference(action.reference)
        offset_key = (stage.name, _step_value, suffix)
        prior = step_after_offsets.get(offset_key, 0)
        insertion = idx + 1 + prior
        step_after_offsets[offset_key] = prior + len(action.items)
    stage.steps[insertion:insertion] = list(action.items)


def _apply_remove_step(
    ctx: ChopperContext,
    working: list[_MutableStage],
    action: RemoveStepAction,
    *,
    feature_name: str,
) -> None:
    stage = _find_stage(working, action.stage)
    idx = _resolve_step_index(ctx, stage, action.reference, feature_name=feature_name, action_kind="remove_step")
    if idx is None:
        return
    del stage.steps[idx]


def _apply_replace_step(
    ctx: ChopperContext,
    working: list[_MutableStage],
    action: ReplaceStepAction,
    *,
    feature_name: str,
) -> None:
    stage = _find_stage(working, action.stage)
    idx = _resolve_step_index(ctx, stage, action.reference, feature_name=feature_name, action_kind="replace_step")
    if idx is None:
        return
    stage.steps[idx] = action.replacement


# ---- stage-level actions ---------------------------------------------------


def _apply_add_stage(
    working: list[_MutableStage],
    action: AddStageAction,
    *,
    stage_after_offsets: dict[str, int],
) -> None:
    ref_idx = _find_stage_index(working, action.reference)
    new_stage = _MutableStage.from_definition(action.stage)
    # Disallow duplicate stage name.
    if any(s.name == new_stage.name for s in working):
        raise ChopperError(f"flow_action {action.action} would create duplicate stage {new_stage.name!r}")
    if action.action == "add_stage_before":
        # Mirrors ``add_step_before``: each insertion shifts the
        # reference stage down, so subsequent same-anchor inserts land
        # immediately before it in selected feature order.
        insertion = ref_idx
    else:
        # ``add_stage_after``: preserve selected feature order by
        # walking past prior same-anchor insertions from earlier
        # features.
        prior = stage_after_offsets.get(action.reference, 0)
        insertion = ref_idx + 1 + prior
        stage_after_offsets[action.reference] = prior + 1
    working.insert(insertion, new_stage)


def _apply_remove_stage(working: list[_MutableStage], action: RemoveStageAction) -> None:
    idx = _find_stage_index(working, action.reference)
    del working[idx]


def _apply_replace_stage(working: list[_MutableStage], action: ReplaceStageAction) -> None:
    idx = _find_stage_index(working, action.reference)
    old_name = working[idx].name
    replacement = _MutableStage.from_definition(action.replacement)
    if replacement.name != old_name and any(s.name == replacement.name for s in working):
        raise ChopperError(f"flow_action replace_stage would create duplicate stage {replacement.name!r}")
    working[idx] = replacement
    # Rewrite existing load_from references from the old stage name to
    # the replacement's name so later actions see the new graph
    # consistently.
    if replacement.name != old_name:
        for stage in working:
            if stage.load_from == old_name:
                stage.load_from = replacement.name


def _apply_load_from(working: list[_MutableStage], action: LoadFromAction) -> None:
    stage = _find_stage(working, action.stage)
    stage.load_from = action.reference


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def _assert_unique_stage_names(working: list[_MutableStage]) -> None:
    names = [s.name for s in working]
    if len(set(names)) != len(names):
        raise ChopperError(f"base stages contain duplicate names: {names!r}")


# ---------------------------------------------------------------------------
# Diagnostic emit helpers
# ---------------------------------------------------------------------------


def _emit_ve10(
    ctx: ChopperContext,
    *,
    feature: str,
    stage: str,
    reference: str,
    action: str,
    count: int,
) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-10",
            phase=Phase.P3_COMPILE,
            message=(
                f"@n suffix overflow in feature {feature!r} "
                f"({action} stage={stage!r} reference={reference!r}): only {count} match(es) found"
            ),
            hint="Reduce the @n index; indices are 1-based and must be ≤ the number of matching steps",
        )
    )


def _emit_ve19(
    ctx: ChopperContext,
    *,
    feature: str,
    stage: str,
    reference: str,
    action: str,
) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-19",
            phase=Phase.P3_COMPILE,
            message=(
                f"@0 occurrence suffix in feature {feature!r} "
                f"({action} stage={stage!r} reference={reference!r}): indices are 1-based"
            ),
            hint="Use @1 for the first occurrence; @0 has no meaning",
        )
    )


def _emit_ve20(
    ctx: ChopperContext,
    *,
    feature: str,
    stage: str,
    reference: str,
    action: str,
    count: int,
) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-20",
            phase=Phase.P3_COMPILE,
            message=(
                f"Ambiguous step target in feature {feature!r} "
                f"({action} stage={stage!r} reference={reference!r}): {count} matches found"
            ),
            hint="Disambiguate with an @n instance suffix (e.g. 'step.tcl@2')",
        )
    )


# Silence unused-import warning — ``replace`` is kept for future parity
# between StageDefinition and StageSpec copies.
_ = replace
