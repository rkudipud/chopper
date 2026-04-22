"""F3 flow-action resolver (bible §6.7).

Consumes the base stage sequence and every selected feature's ordered
``flow_actions`` and returns the resolved tuple of
:class:`~chopper.core.models.StageSpec`.

The resolver is **reporting-only for feature order, authoritative for
F3 ordering** (bible §§5.3, 5.4):

* features are applied in selection order (the order in
  :attr:`LoadedConfig.features`, which the loader already topo-sorts);
* within one feature, actions are applied top-to-bottom;
* ``@n`` instance targeting on step-level actions follows the spec in
  bible §6.7 "Instance Targeting with ``@n``".

Diagnostics emitted here (all registered at
:mod:`chopper.core._diagnostic_registry`):

* ``VE-10 occurrence-suffix-overflow`` — ``@n`` where *n* exceeds the
  number of matching steps in the stage.
* ``VE-19 occurrence-suffix-zero`` — ``@0``; indices are 1-based.
* ``VE-20 ambiguous-step-target`` — a step-level action with no ``@n``
  where the step string appears more than once in the stage.

Programmer-error conditions (action references a missing stage, an
unknown action kind, etc.) raise :class:`~chopper.core.errors.ChopperError`;
the runner maps this to exit 3 (internal invariant violation).
"""

from __future__ import annotations

import re
from dataclasses import replace

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.errors import ChopperError
from chopper.core.models import (
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
    StageSpec,
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
    """Return the resolved stage sequence per bible §6.7.

    The input ``base_stages`` is never mutated; the resolver works on a
    list-of-lists copy internally.
    """

    # Working state: list of dicts so we can mutate steps in place.
    working: list[_MutableStage] = [_MutableStage.from_definition(s) for s in base_stages]

    _assert_unique_stage_names(working)

    for feature in features:
        for action in feature.flow_actions:
            _apply_action(ctx, working, action, feature_name=feature.name)

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
) -> None:
    if isinstance(action, AddStepAction):
        _apply_add_step(ctx, working, action, feature_name=feature_name)
    elif isinstance(action, RemoveStepAction):
        _apply_remove_step(ctx, working, action, feature_name=feature_name)
    elif isinstance(action, ReplaceStepAction):
        _apply_replace_step(ctx, working, action, feature_name=feature_name)
    elif isinstance(action, AddStageAction):
        _apply_add_stage(working, action)
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
    the action). Bible §6.7: ``@1`` is equivalent to no ``@``; ``@0``
    fires ``VE-19``; ``@n`` above the match count fires ``VE-10``;
    duplicate matches without ``@n`` fire ``VE-20``.
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
) -> None:
    stage = _find_stage(working, action.stage)
    idx = _resolve_step_index(ctx, stage, action.reference, feature_name=feature_name, action_kind=action.action)
    if idx is None:
        return
    insertion = idx if action.action == "add_step_before" else idx + 1
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


def _apply_add_stage(working: list[_MutableStage], action: AddStageAction) -> None:
    ref_idx = _find_stage_index(working, action.reference)
    new_stage = _MutableStage.from_definition(action.stage)
    # Disallow duplicate stage name (bible §6.7: stage names must be unique).
    if any(s.name == new_stage.name for s in working):
        raise ChopperError(f"flow_action {action.action} would create duplicate stage {new_stage.name!r}")
    insertion = ref_idx if action.action == "add_stage_before" else ref_idx + 1
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
    # Bible §6.7: rewrite existing load_from references from the old
    # stage name to the replacement's name so later actions see the new
    # graph consistently.
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
