"""Stage dependency graph + topological ordering for aggregate stack emission.

Per ``technical_docs/ARCHITECTURE.md`` §3.6: when ``stages`` is non-empty,
the compiler builds a directed graph whose edges per stage ``S`` are the
union of

* ``P -> S`` for every ``P`` in ``S.dependencies``;
* ``S.load_from -> S`` when ``S.load_from`` is non-empty.

Cycles and dangling references are user errors regardless of
``options.generate_stack``:

* ``VE-30 stage-dependency-cycle`` — any cycle (including a self-loop).
* ``VE-31 stage-dependency-unresolved`` — any edge whose source is not a
  defined stage in the resolved flow.

Both surface as :class:`~chopper.core.diagnostics.Diagnostic` emissions
on ``ctx.diag``; the function then returns an empty tuple so the rest of
the compile phase can complete and the post-phase validator can report
the accumulated errors and exit 1. The function does **not** raise on
user-input errors — that would short-circuit the pipeline to an internal
error (exit 3), which is reserved for programmer mistakes.

When the graph is well-formed, :func:`compute_stack_order` returns a
topological ordering of stage names produced by Kahn's algorithm with
``(in_degree, authored_position)`` as the priority key — fully
deterministic, with **authored position** (index in the input tuple) as
the tiebreaker among equal-in-degree nodes.
"""

from __future__ import annotations

import heapq

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models_compiler import StageSpec

__all__ = ["compute_stack_order"]


def compute_stack_order(ctx: ChopperContext, stages: tuple[StageSpec, ...]) -> tuple[str, ...]:
    """Return the topological order of stage names for aggregate stack emission.

    Emits ``VE-30`` (cycle) or ``VE-31`` (unresolved reference) and
    returns an empty tuple when the graph is malformed; the post-phase
    validator exits 1 from the accumulated diagnostic state. Returns an
    empty tuple when ``stages`` is empty.
    """

    if not stages:
        return ()

    authored_index: dict[str, int] = {s.name: i for i, s in enumerate(stages)}
    stage_names = set(authored_index)

    # ---- Validate references (VE-31) ---------------------------------
    unresolved_emitted = False
    for stage in stages:
        for dep in stage.dependencies:
            if dep not in stage_names:
                _emit_ve31(ctx, referrer=stage.name, unresolved=dep, field_name="dependencies")
                unresolved_emitted = True
        if stage.load_from and stage.load_from not in stage_names:
            _emit_ve31(ctx, referrer=stage.name, unresolved=stage.load_from, field_name="load_from")
            unresolved_emitted = True
    if unresolved_emitted:
        # User-input error; diagnostic is already emitted. Skip ordering;
        # the validator will exit 1 from the diagnostic summary.
        return ()

    # ---- Build edge set: predecessor -> successor --------------------
    successors: dict[str, list[str]] = {name: [] for name in stage_names}
    in_degree: dict[str, int] = {name: 0 for name in stage_names}
    for stage in stages:
        preds: list[str] = []
        for dep in stage.dependencies:
            preds.append(dep)
        if stage.load_from:
            preds.append(stage.load_from)
        # Deduplicate (a stage may list the same predecessor twice via
        # both dependencies and load_from); count each edge once.
        seen: set[str] = set()
        for pred in preds:
            if pred in seen:
                continue
            seen.add(pred)
            if pred == stage.name:
                # Self-loop — surfaces as a cycle via Kahn's residual.
                successors[pred].append(stage.name)
                in_degree[stage.name] += 1
                continue
            successors[pred].append(stage.name)
            in_degree[stage.name] += 1

    # ---- Kahn's algorithm with authored-position tiebreaker ----------
    heap: list[tuple[int, str]] = [(authored_index[name], name) for name, deg in in_degree.items() if deg == 0]
    heapq.heapify(heap)

    order: list[str] = []
    while heap:
        _, name = heapq.heappop(heap)
        order.append(name)
        for succ in successors[name]:
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                heapq.heappush(heap, (authored_index[succ], succ))

    if len(order) != len(stages):
        cycle = _extract_cycle(successors, in_degree)
        _emit_ve30(ctx, cycle)
        # User-input error; diagnostic is already emitted. Skip ordering;
        # the validator will exit 1 from the diagnostic summary.
        return ()

    return tuple(order)


def _extract_cycle(successors: dict[str, list[str]], residual_in_degree: dict[str, int]) -> list[str]:
    """Return a representative cycle (list of stage names) from the residual graph.

    Called only when Kahn's algorithm has confirmed at least one cycle
    exists (some nodes still have non-zero in-degree). Strategy:

    1. Take the residual node set (in-degree > 0 after Kahn).
    2. Iteratively strip "leaves" — residual nodes with no residual
       successor — leaving only nodes that lie on at least one cycle.
    3. From the lex-smallest remaining node, walk forward picking the
       lex-smallest residual successor; the first revisit closes the
       cycle. Termination is guaranteed because every remaining node
       has at least one residual successor and the graph is finite.

    The returned list starts and ends with the same node (e.g.
    ``[a, b, c, a]`` for the cycle ``a -> b -> c -> a``).
    """

    in_cycle = {name for name, deg in residual_in_degree.items() if deg > 0}
    # Strip leaves until only cycle members remain.
    changed = True
    while changed:
        changed = False
        for name in list(in_cycle):
            if not any(succ in in_cycle for succ in successors[name]):
                in_cycle.discard(name)
                changed = True

    start = sorted(in_cycle)[0]
    position: dict[str, int] = {start: 0}
    path: list[str] = [start]
    current = start
    while True:
        succ = sorted(s for s in successors[current] if s in in_cycle)[0]
        if succ in position:
            return path[position[succ] :] + [succ]
        position[succ] = len(path)
        path.append(succ)
        current = succ


def _emit_ve30(ctx: ChopperContext, cycle: list[str]) -> None:
    cycle_str = " -> ".join(cycle)
    ctx.diag.emit(
        Diagnostic.build(
            "VE-30",
            phase=Phase.P3_COMPILE,
            message=(
                f"F3 stage dependency graph contains a cycle: {cycle_str}. "
                f"Cycles in 'dependencies' / 'load_from' are not permitted"
            ),
            hint=(
                "Break the cycle by removing the offending 'dependencies' entry "
                "or changing the 'load_from' reference on one of the stages in the cycle"
            ),
        )
    )


def _emit_ve31(ctx: ChopperContext, *, referrer: str, unresolved: str, field_name: str) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-31",
            phase=Phase.P3_COMPILE,
            message=(f"Stage {referrer!r} references unknown stage {unresolved!r} via {field_name!r}"),
            hint=(
                f"Define the referenced stage or correct the misspelling; or remove the bogus entry from '{field_name}'"
            ),
        )
    )
