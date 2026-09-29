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
is whatever order :attr:`LoadedConfig.features` carries -- i.e. the
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

**Marker contract (Sec.3.11):** markers are always inserted while actions
apply, so block-aware anchoring behaves the same with
``options.insert_markers`` on or off. Once every action has applied they
are either stripped (switch off, or a ``standalone_stack`` stage) or moved
outward to top-level Tcl command boundaries -- never inside braces or a
quoted word, after a continuation line, or above a line-1 shebang -- so a
marker can never change what the script does.

Diagnostics emitted:

* ``VE-05 missing-action-target`` -- a flow_action ``stage`` or step
  ``reference`` cannot be found in the working stage sequence (e.g.
  whitespace mismatch in a ``replace_step.reference``, or a stage
  name introduced by an unselected prerequisite feature).
* ``VE-08 duplicate-stage-names`` -- ``add_stage_*`` or
  ``replace_stage`` would create a stage whose name already exists.
* ``VE-10 occurrence-suffix-overflow`` -- ``@n`` with *n* exceeding the
  number of matching steps in the stage.
* ``VE-19 occurrence-suffix-zero`` -- ``@0``; indices are 1-based.
* ``VE-20 ambiguous-step-target`` -- a step-level action with no ``@n``
  where the step string appears more than once in the stage.
* ``VI-05 flow-action-skipped-no-stage`` -- an action declared
  ``"skip_if_no_stage": true`` and the named stage is not present in
  the working sequence; the action is skipped silently. Step-level
  miss inside a present stage is **not** softened; that still emits
  ``VE-05``.

Programmer-error conditions (missing stage target, unknown action kind)
raise :class:`ChopperError` and the runner maps that to exit 3.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from itertools import chain

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
from chopper.core.provenance_markers import Action, Kind, marker_pair

__all__ = ["resolve_stages"]

# Sec.3.11 marker line prefixes -- used only to detect when an add_step_*
# anchor is itself the boundary content line of an earlier feature's
# added/replaced block, so "before"/"after" resolves to the whole block
# rather than splitting it.
_MARKER_BEGIN_PREFIX = "## CHOPPER: BEGIN"
_MARKER_END_PREFIX = "## CHOPPER: END"


class _Marker(str):
    """A marker line this run inserted -- the only kind of line placement may move or drop."""

    __slots__ = ()


def _markers(*, action: Action, kind: Kind, name: str, feature: str) -> tuple[_Marker, _Marker]:
    begin, end = marker_pair(action=action, kind=kind, name=name, source=f"feature:{feature}")
    return _Marker(begin), _Marker(end)


def _is_begin(step: str) -> bool:
    return isinstance(step, _Marker) and step.startswith(_MARKER_BEGIN_PREFIX)


def _is_end(step: str) -> bool:
    return isinstance(step, _Marker) and step.startswith(_MARKER_END_PREFIX)


# ``step@n`` -- ``@n`` applies to the trailing integer only; step strings
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
    *,
    insert_markers: bool = True,
) -> tuple[StageSpec, ...]:
    """Return the resolved stage sequence.

    The input ``base_stages`` is never mutated; the resolver works on a
    list-of-lists copy internally. ``insert_markers`` is
    ``options.insert_markers``; see the module docstring's marker contract.
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

    for stage in working:
        if insert_markers and not stage.standalone_stack:
            stage.steps = _place_markers(stage.steps)
        else:
            stage.steps = [step for step in stage.steps if not isinstance(step, _Marker)]
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
        "standalone_stack",
        "reference_file",
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
        standalone_stack: bool,
        reference_file: str | None = None,
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
        self.standalone_stack = standalone_stack
        self.reference_file = reference_file

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
            standalone_stack=sd.standalone_stack,
            reference_file=sd.reference_file,
        )

    def freeze(self) -> StageSpec:
        return StageSpec(
            name=self.name,
            load_from=self.load_from,
            steps=tuple(str(step) for step in self.steps),
            dependencies=self.dependencies,
            exit_codes=self.exit_codes,
            command=self.command,
            inputs=self.inputs,
            outputs=self.outputs,
            run_mode=self.run_mode,  # type: ignore[arg-type]
            language=self.language,  # type: ignore[arg-type]
            standalone_stack=self.standalone_stack,
            reference_file=self.reference_file,
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
        _apply_add_stage(ctx, working, action, feature_name=feature_name, stage_after_offsets=stage_after_offsets)
    elif isinstance(action, RemoveStageAction):
        _apply_remove_stage(ctx, working, action, feature_name=feature_name)
    elif isinstance(action, ReplaceStageAction):
        _apply_replace_stage(ctx, working, action, feature_name=feature_name)
    elif isinstance(action, LoadFromAction):
        _apply_load_from(ctx, working, action, feature_name=feature_name)
    else:  # pragma: no cover -- exhaustive dispatch
        raise ChopperError(f"unknown FlowAction variant: {type(action).__name__}")


def _find_stage(working: list[_MutableStage], name: str) -> _MutableStage | None:
    """Return the stage named ``name`` or ``None`` if absent.

    Lookup is non-raising; callers emit ``VE-05`` (missing-action-target)
    and skip the action when the result is ``None``.
    """
    for stage in working:
        if stage.name == name:
            return stage
    return None


def _find_stage_index(working: list[_MutableStage], name: str) -> int | None:
    """Return the index of the stage named ``name`` or ``None`` if absent.

    Lookup is non-raising; callers emit ``VE-05`` (missing-action-target)
    and skip the action when the result is ``None``.
    """
    for i, stage in enumerate(working):
        if stage.name == name:
            return i
    return None


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
        _emit_ve05(
            ctx,
            feature=feature_name,
            action=action_kind,
            target_kind="step",
            target=reference,
            stage=stage.name,
        )
        return None
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
    if stage is None:
        if action.skip_if_no_stage:
            _emit_vi05_skipped(ctx, feature=feature_name, action=action.action, target=action.stage)
            return
        _emit_ve05(
            ctx,
            feature=feature_name,
            action=action.action,
            target_kind="stage",
            target=action.stage,
        )
        return
    idx = _resolve_step_index(ctx, stage, action.reference, feature_name=feature_name, action_kind=action.action)
    if idx is None:
        return
    begin, end = _markers(action="added", kind="step", name=", ".join(action.items), feature=feature_name)
    wrapped_items = [begin, *action.items, end]
    if action.action == "add_step_before":
        # If the anchor is itself the first content line of an earlier
        # feature's added/replaced marker block, "before" means before
        # that whole block, not between its BEGIN marker and content.
        if idx > 0 and _is_begin(stage.steps[idx - 1]):
            idx -= 1
        # Anchor index is re-resolved each call; previous insertions
        # before the anchor have already shifted the anchor down, so
        # this insertion lands immediately before the (shifted) anchor
        # and naturally preserves selected feature order.
        insertion = idx
    else:
        # If the anchor is itself the last content line of an earlier
        # feature's added/replaced marker block, "after" means after
        # that whole block, not between its content and END marker.
        if idx + 1 < len(stage.steps) and _is_end(stage.steps[idx + 1]):
            idx += 1
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
        step_after_offsets[offset_key] = prior + len(wrapped_items)
    stage.steps[insertion:insertion] = wrapped_items


def _enclosing_span(stage: _MutableStage, idx: int) -> tuple[int, int]:
    """Return the ``[start, end]`` (inclusive) span to rewrite for step index ``idx``.

    When ``idx`` is a *solitary* single-item marker block (immediately
    preceded by a BEGIN line and immediately followed by an END line), a
    later ``replace_step``/``remove_step`` targeting it must replace the
    whole block -- otherwise the earlier action's now-stale BEGIN/END
    would keep naming content that this action just superseded (R1
    last-mention-wins applies to the whole marked unit, not just its
    inner text). Multi-item blocks are left alone: only the exact
    matched line is rewritten, since expanding would also consume
    unrelated sibling items from the same action.
    """

    if idx > 0 and _is_begin(stage.steps[idx - 1]) and idx + 1 < len(stage.steps) and _is_end(stage.steps[idx + 1]):
        return idx - 1, idx + 1
    return idx, idx


def _apply_remove_step(
    ctx: ChopperContext,
    working: list[_MutableStage],
    action: RemoveStepAction,
    *,
    feature_name: str,
) -> None:
    stage = _find_stage(working, action.stage)
    if stage is None:
        if action.skip_if_no_stage:
            _emit_vi05_skipped(ctx, feature=feature_name, action="remove_step", target=action.stage)
            return
        _emit_ve05(
            ctx,
            feature=feature_name,
            action="remove_step",
            target_kind="stage",
            target=action.stage,
        )
        return
    idx = _resolve_step_index(ctx, stage, action.reference, feature_name=feature_name, action_kind="remove_step")
    if idx is None:
        return
    begin, end = _markers(action="removed", kind="step", name=stage.steps[idx], feature=feature_name)
    start, stop = _enclosing_span(stage, idx)
    stage.steps[start : stop + 1] = [begin, end]


def _apply_replace_step(
    ctx: ChopperContext,
    working: list[_MutableStage],
    action: ReplaceStepAction,
    *,
    feature_name: str,
) -> None:
    stage = _find_stage(working, action.stage)
    if stage is None:
        if action.skip_if_no_stage:
            _emit_vi05_skipped(ctx, feature=feature_name, action="replace_step", target=action.stage)
            return
        _emit_ve05(
            ctx,
            feature=feature_name,
            action="replace_step",
            target_kind="stage",
            target=action.stage,
        )
        return
    idx = _resolve_step_index(ctx, stage, action.reference, feature_name=feature_name, action_kind="replace_step")
    if idx is None:
        return
    begin, end = _markers(action="replaced", kind="step", name=action.replacement, feature=feature_name)
    start, stop = _enclosing_span(stage, idx)
    stage.steps[start : stop + 1] = [begin, action.replacement, end]


# ---- stage-level actions ---------------------------------------------------


def _apply_add_stage(
    ctx: ChopperContext,
    working: list[_MutableStage],
    action: AddStageAction,
    *,
    feature_name: str,
    stage_after_offsets: dict[str, int],
) -> None:
    ref_idx = _find_stage_index(working, action.reference)
    if ref_idx is None:
        if action.skip_if_no_stage:
            _emit_vi05_skipped(ctx, feature=feature_name, action=action.action, target=action.reference)
            return
        _emit_ve05(
            ctx,
            feature=feature_name,
            action=action.action,
            target_kind="stage",
            target=action.reference,
        )
        return
    new_stage = _MutableStage.from_definition(action.stage)
    # Disallow duplicate stage name.
    if any(s.name == new_stage.name for s in working):
        _emit_ve08(
            ctx,
            feature=feature_name,
            action=action.action,
            stage_name=new_stage.name,
        )
        return
    begin, end = _markers(action="added", kind="stage", name=new_stage.name, feature=feature_name)
    new_stage.steps = [begin, *new_stage.steps, end]
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


def _apply_remove_stage(
    ctx: ChopperContext,
    working: list[_MutableStage],
    action: RemoveStageAction,
    *,
    feature_name: str,
) -> None:
    idx = _find_stage_index(working, action.reference)
    if idx is None:
        if action.skip_if_no_stage:
            _emit_vi05_skipped(ctx, feature=feature_name, action="remove_stage", target=action.reference)
            return
        _emit_ve05(
            ctx,
            feature=feature_name,
            action="remove_stage",
            target_kind="stage",
            target=action.reference,
        )
        return
    del working[idx]


def _apply_replace_stage(
    ctx: ChopperContext,
    working: list[_MutableStage],
    action: ReplaceStageAction,
    *,
    feature_name: str,
) -> None:
    idx = _find_stage_index(working, action.reference)
    if idx is None:
        if action.skip_if_no_stage:
            _emit_vi05_skipped(ctx, feature=feature_name, action="replace_stage", target=action.reference)
            return
        _emit_ve05(
            ctx,
            feature=feature_name,
            action="replace_stage",
            target_kind="stage",
            target=action.reference,
        )
        return
    old_name = working[idx].name
    replacement = _MutableStage.from_definition(action.replacement)
    if replacement.name != old_name and any(s.name == replacement.name for s in working):
        _emit_ve08(
            ctx,
            feature=feature_name,
            action="replace_stage",
            stage_name=replacement.name,
        )
        return
    begin, end = _markers(action="replaced", kind="stage", name=replacement.name, feature=feature_name)
    replacement.steps = [begin, *replacement.steps, end]
    working[idx] = replacement
    # Rewrite existing load_from references from the old stage name to
    # the replacement's name so later actions see the new graph
    # consistently.
    if replacement.name != old_name:
        for stage in working:
            if stage.load_from == old_name:
                stage.load_from = replacement.name


def _apply_load_from(
    ctx: ChopperContext,
    working: list[_MutableStage],
    action: LoadFromAction,
    *,
    feature_name: str,
) -> None:
    stage = _find_stage(working, action.stage)
    if stage is None:
        if action.skip_if_no_stage:
            _emit_vi05_skipped(ctx, feature=feature_name, action="load_from", target=action.stage)
            return
        _emit_ve05(
            ctx,
            feature=feature_name,
            action="load_from",
            target_kind="stage",
            target=action.stage,
        )
        return
    stage.load_from = action.reference


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def _assert_unique_stage_names(working: list[_MutableStage]) -> None:
    names = [s.name for s in working]
    if len(set(names)) != len(names):
        raise ChopperError(f"base stages contain duplicate names: {names!r}")


# ---------------------------------------------------------------------------
# Marker placement (Sec.3.11)
# ---------------------------------------------------------------------------


@dataclass
class _Pair:
    """A BEGIN/END marker pair, located by the gaps between content lines it sits in."""

    top: int
    begin: str
    bottom: int = -1
    end: str = ""


def _place_markers(steps: list[str]) -> list[str]:
    """Keep marker pairs on top-level Tcl command boundaries; content lines never move.

    A pair off a safe gap moves outward -- BEGIN up, END down -- to wrap the
    enclosing top-level command. A pair with no safe gap to reach, or missing
    its partner, is dropped.
    """

    content: list[str] = []
    gaps: list[int] = []
    pairs: list[_Pair] = []
    open_pairs: list[_Pair] = []
    for step in steps:
        if not isinstance(step, _Marker):
            content.append(step)
            continue
        gaps.append(len(content))
        if _is_begin(step):
            open_pairs.append(_Pair(top=len(content), begin=step))
            pairs.append(open_pairs[-1])
        elif open_pairs:
            closed = open_pairs.pop()
            closed.bottom, closed.end = len(content), step
    safe = _safe_gaps(content) if gaps else []
    if all(safe[gap] for gap in gaps):
        return steps

    placed: list[tuple[int, _Pair]] = []
    for ordinal, pair in enumerate(pairs):
        # BEGIN goes up; only a line-1 shebang with nothing safe above pushes it down.
        top = _first_safe(safe, chain(range(pair.top, -1, -1), range(pair.top + 1, len(safe))))
        if top is None or not pair.end:
            continue
        bottom = _first_safe(safe, range(max(pair.bottom, top), len(safe)))
        if bottom is not None:
            placed.append((ordinal, _Pair(top=top, begin=pair.begin, bottom=bottom, end=pair.end)))

    # Per gap: close inner pairs first, then empty pairs, then open outer pairs first.
    out: list[str] = []
    for gap in range(len(content) + 1):
        closing = sorted((p for p in placed if p[1].top < gap == p[1].bottom), key=lambda p: (-p[1].top, -p[0]))
        opening = sorted((p for p in placed if p[1].top == gap < p[1].bottom), key=lambda p: (-p[1].bottom, p[0]))
        out.extend(pair.end for _, pair in closing)
        for _, pair in placed:
            if pair.top == gap == pair.bottom:
                out.extend((pair.begin, pair.end))
        out.extend(pair.begin for _, pair in opening)
        if gap < len(content):
            out.append(content[gap])
    return out


def _first_safe(safe: list[bool], gaps: Iterable[int]) -> int | None:
    return next((gap for gap in gaps if safe[gap]), None)


def _safe_gaps(lines: list[str]) -> list[bool]:
    """Return ``safe[g]``: a new ``#`` line inserted before ``lines[g]`` (or at the end) is a top-level comment.

    Tracks what Tcl tracks across lines -- brace depth, an open quoted word,
    backslash-newline continuation -- and never allows a line above a line-1
    ``#!`` shebang.
    """

    safe: list[bool] = []
    depth, in_quote, continued, in_comment = 0, False, False, False
    for line in lines:
        at_top = depth == 0 and not in_quote and not continued
        safe.append(at_top)
        if in_comment or (at_top and line.lstrip().startswith("#")):
            in_comment = continued = _continues(line)
            continue
        depth, in_quote, trailing_comment = _scan_code(line, depth, in_quote)
        continued = _continues(line)
        in_comment = trailing_comment and continued
    safe.append(depth == 0 and not in_quote and not continued)
    if lines and lines[0].startswith("#!"):
        safe[0] = False
    return safe


def _scan_code(line: str, depth: int, in_quote: bool) -> tuple[int, bool, bool]:
    """Advance brace depth and quote state across one line of Tcl code.

    Inside braces every unescaped brace counts, comment text included, as in
    Tcl's own brace matching. At top level only a word-initial ``{`` or ``"``
    opens a word, and ``;#`` starts a comment (reported by the third value).
    """

    word_start = True
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\":
            i += 2
            word_start = False
            continue
        if in_quote:
            in_quote = ch != '"'
        elif depth:
            depth += {"{": 1, "}": -1}.get(ch, 0)
        elif ch == '"' and word_start:
            in_quote = True
        elif ch == "{" and word_start:
            depth = 1
        elif ch == ";" and line[i + 1 :].lstrip().startswith("#"):
            return depth, in_quote, True
        word_start = ch in " \t;["
        i += 1
    return depth, in_quote, False


def _continues(line: str) -> bool:
    """Whether ``line`` ends in an unescaped backslash, joining the next line to it."""

    return (len(line) - len(line.rstrip("\\"))) % 2 == 1


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
            hint="Reduce the @n index; indices are 1-based and must be <= the number of matching steps",
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


def _emit_ve05(
    ctx: ChopperContext,
    *,
    feature: str,
    action: str,
    target_kind: str,
    target: str,
    stage: str | None = None,
) -> None:
    """Emit ``VE-05 missing-action-target`` for a flow_action that names
    a non-existent stage or step.

    ``target_kind`` is ``"stage"`` or ``"step"``; ``stage`` (the stage
    being acted upon) is included only for step-level misses to disambiguate
    where the search failed.
    """
    where = f" in stage {stage!r}" if (target_kind == "step" and stage is not None) else ""
    ctx.diag.emit(
        Diagnostic.build(
            "VE-05",
            phase=Phase.P3_COMPILE,
            message=(
                f"flow_action {action!r} in feature {feature!r} references missing {target_kind} {target!r}{where}"
            ),
            hint=(
                "Verify the target exists in the compiled stage sequence. Check spelling, "
                "whitespace (step strings are matched literally), and that any prerequisite "
                "feature that introduces the target is selected before this one."
            ),
        )
    )


def _emit_vi05_skipped(
    ctx: ChopperContext,
    *,
    feature: str,
    action: str,
    target: str,
) -> None:
    """Emit ``VI-05 flow-action-skipped-no-stage`` for an action that
    declared ``skip_if_no_stage: true`` and whose stage target is absent.

    Architecture doc Sec.6.7 'Optional Stage Targets'. Severity is info
    (exit 0); ``--strict`` does **not** escalate ``VI-*`` codes.
    """
    ctx.diag.emit(
        Diagnostic.build(
            "VI-05",
            phase=Phase.P3_COMPILE,
            message=(
                f"flow_action {action!r} in feature {feature!r} skipped: "
                f"target stage {target!r} not present in compiled sequence "
                f"and action declared skip_if_no_stage=true"
            ),
            hint=(
                "No action required if the silent skip matches the author's intent. "
                "If the stage should be present, add the feature that introduces it. "
                "To restore strict behaviour, remove skip_if_no_stage from this action."
            ),
        )
    )


def _emit_ve08(
    ctx: ChopperContext,
    *,
    feature: str,
    action: str,
    stage_name: str,
) -> None:
    """Emit ``VE-08 duplicate-stage-names`` when a flow_action would
    create a stage whose name already exists in the working sequence.
    """
    ctx.diag.emit(
        Diagnostic.build(
            "VE-08",
            phase=Phase.P3_COMPILE,
            message=(f"flow_action {action!r} in feature {feature!r} would create duplicate stage {stage_name!r}"),
            hint="Rename one of the conflicting stages, or remove the action that creates the duplicate.",
        )
    )


# Silence unused-import warning -- ``replace`` is kept for future parity
# between StageDefinition and StageSpec copies.
_ = replace
