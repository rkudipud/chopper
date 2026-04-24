"""TracerService — Phase 4 (P4) BFS trace expansion.

* **Seeds**: the PI set — every canonical proc name in
  ``manifest.proc_decisions``.
* **Walk**: breadth-first, frontier always popped in lex order. The
  frontier does not deduplicate on enqueue — every call-token
  occurrence becomes an :class:`Edge` record with its own line and
  token. Deduplication happens only at visited-set level.
* **Resolution**: lexical namespace contract. For each raw token the
  tracer tries a deterministic candidate list: absolute (``::ns::x``)
  resolves only itself; relative / bare forms try
  ``<caller_namespace>::<qname>`` first, then the token at global scope.
  A candidate resolves when exactly one canonical proc has that
  qualified name.

Outputs on :class:`DependencyGraph`:

* ``pi_seeds`` — the frontier's starting set (lex-sorted).
* ``nodes`` — full transitive closure (PI+).
* ``pt`` — ``nodes − pi_seeds`` (traced-only).
* ``edges`` — every caller → callee record, sorted by
  ``(caller, kind, line, token, callee)``.
* ``unresolved_tokens`` — lex-sorted projection of non-resolved edges.

Diagnostics: ``TW-01`` (ambiguous), ``TW-02`` (no match),
``TW-03`` (dynamic/unresolvable), ``TW-04`` (cycle). All warnings; P4
never blocks P5. The tracer **never** mutates the
manifest — it is frozen and the dataclass invariant guarantees mutation
raises.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models import (
    CompiledManifest,
    DependencyGraph,
    Edge,
    LoadedConfig,
    ParseResult,
    ProcEntry,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["TracerService"]


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TracerService:
    """Phase 4 BFS trace service."""

    def run(
        self,
        ctx: ChopperContext,
        manifest: CompiledManifest,
        parsed: ParseResult,
        loaded: LoadedConfig | None = None,
    ) -> DependencyGraph:
        # ``loaded`` is the source of the tool-command pool (see
        # architecture doc §3.10 and FR-44). Accept ``None`` so unit
        # tests that exercise the tracer in isolation keep their
        # existing call sites — an empty frozenset means no token will
        # ever be downgraded from TW-02 to TI-01, matching pre-0.5.0
        # behaviour exactly.
        tool_pool: frozenset[str] = loaded.tool_command_pool if loaded is not None else frozenset()

        seeds: tuple[str, ...] = tuple(sorted(manifest.proc_decisions.keys()))
        # Only seeds that exist in the parsed index can drive the walk;
        # everything else is already covered by VE-08 (proc-not-in-file)
        # at P1/P3 validation.
        valid_seeds = tuple(cn for cn in seeds if cn in parsed.index)

        # Build a qualified-name index for O(1) candidate lookup.
        # ``qualified_name`` is namespace-qualified with leading ``::`` stripped
        # (see ProcEntry invariants). Multiple procs can share a qualified
        # name across files → ambiguity (TW-01).
        qname_index: dict[str, list[str]] = defaultdict(list)
        for cn, entry in parsed.index.items():
            qname_index[entry.qualified_name].append(cn)
        # Canonicalise: lex-sort each candidate list so ambiguity reporting
        # is deterministic.
        qname_lookup: dict[str, tuple[str, ...]] = {k: tuple(sorted(v)) for k, v in qname_index.items()}

        visited: set[str] = set()
        frontier: deque[str] = deque(sorted(valid_seeds))
        nodes: set[str] = set(valid_seeds)
        edges: list[Edge] = []

        while frontier:
            # Re-sort on every pop: enqueues that happened since the last
            # pop may have put smaller names back in play. We want
            # lex-least across the whole frontier at every step.
            ordered = sorted(frontier)
            frontier.clear()
            caller_cn = ordered[0]
            frontier.extend(ordered[1:])

            if caller_cn in visited:
                continue
            visited.add(caller_cn)

            caller_entry = parsed.index[caller_cn]

            # Proc-call edges.
            for token in caller_entry.calls:
                edge = _resolve_token(
                    ctx=ctx,
                    caller=caller_entry,
                    token=token,
                    qname_lookup=qname_lookup,
                    visited=visited,
                    tool_pool=tool_pool,
                )
                edges.append(edge)
                if edge.status == "resolved" and edge.callee not in visited:
                    frontier.append(edge.callee)
                    nodes.add(edge.callee)

            # source / iproc_source edges — reporting-only file refs.
            for ref in caller_entry.source_refs:
                edges.append(
                    Edge(
                        caller=caller_cn,
                        callee=ref,
                        kind="source",
                        status="resolved",
                        token=ref,
                        line=caller_entry.body_start_line,
                        diagnostic_code=None,
                    )
                )

        # Sort edges by (caller, kind, line, token, callee) for stability.
        edges.sort(key=lambda e: (e.caller, e.kind, e.line, e.token, e.callee))

        # Emit TW-04 for cycles (after the walk so cycle paths are complete).
        _emit_cycle_diagnostics(ctx, edges)

        sorted_nodes = tuple(sorted(nodes))
        pt = tuple(sorted(set(sorted_nodes) - set(valid_seeds)))
        # ``unresolved_tokens`` reports genuinely-unresolved call tokens
        # (TW-01 / TW-02 / TW-03). ``tool_command`` edges are
        # informational (TI-01) and do NOT belong here — they represent
        # tokens that were intentionally downgraded via the pool.
        unresolved = tuple(
            sorted(
                (e.caller, e.token, e.line, e.diagnostic_code or "")
                for e in edges
                if e.status not in ("resolved", "tool_command") and e.diagnostic_code is not None
            )
        )

        return DependencyGraph(
            pi_seeds=tuple(sorted(valid_seeds)),
            nodes=sorted_nodes,
            pt=pt,
            edges=tuple(edges),
            reachable_from_includes=frozenset(sorted_nodes),
            unresolved_tokens=unresolved,
        )


# ---------------------------------------------------------------------------
# Call-token resolution — lexical namespace contract
# ---------------------------------------------------------------------------


def _resolve_token(
    *,
    ctx: ChopperContext,
    caller: ProcEntry,
    token: str,
    qname_lookup: dict[str, tuple[str, ...]],
    visited: set[str],
    tool_pool: frozenset[str],
) -> Edge:
    """Resolve ``token`` under the lexical namespace contract.

    Returns exactly one :class:`Edge` per call site. Emits ``TW-01`` /
    ``TW-02`` / ``TW-03`` / ``TI-01`` diagnostics as side effects via
    ``ctx.diag``. See architecture doc §5.4 for the full six-step ladder.
    """
    caller_cn = caller.canonical_name
    line = caller.body_start_line  # parser doesn't pin per-token lines yet

    # TW-03 — dynamic / syntactically unresolvable call forms.
    # A token is "dynamic" when the parser could not strip it to a pure
    # identifier chain: variable substitution (``$cmd``), bracket-command
    # substitution (``[expr ...]``), or empty after suppression.
    if _is_dynamic(token):
        _emit_tw03(ctx, caller_cn, token, line)
        return Edge(
            caller=caller_cn,
            callee="",
            kind="proc_call",
            status="dynamic",
            token=token,
            line=line,
            diagnostic_code="TW-03",
        )

    candidates = _candidate_qnames(token, caller.namespace_path)

    matched_canonical: str | None = None
    for qname in candidates:
        hits = qname_lookup.get(qname, ())
        if not hits:
            continue
        if len(hits) == 1:
            matched_canonical = hits[0]
            break
        # More than one canonical proc shares this qualified name → TW-01.
        _emit_tw01(ctx, caller_cn, token, line, hits)
        return Edge(
            caller=caller_cn,
            callee="",
            kind="proc_call",
            status="ambiguous",
            token=token,
            line=line,
            diagnostic_code="TW-01",
        )

    if matched_canonical is None:
        # Tool-command pool check (architecture doc §3.10). The pool is
        # consulted ONLY on the TW-02 branch — after the lexical ladder
        # has failed to resolve the token to an in-domain canonical
        # proc. Matching is on raw token OR namespace-stripped leaf so
        # both ``get_app_var`` and ``::pt::get_app_var`` downgrade.
        leaf = token.rsplit("::", 1)[-1] if "::" in token else token
        if token in tool_pool or leaf in tool_pool:
            _emit_ti01(ctx, caller_cn, token, line)
            return Edge(
                caller=caller_cn,
                callee="",
                kind="proc_call",
                status="tool_command",
                token=token,
                line=line,
                diagnostic_code="TI-01",
            )

        _emit_tw02(ctx, caller_cn, token, line)
        return Edge(
            caller=caller_cn,
            callee="",
            kind="proc_call",
            status="unresolved",
            token=token,
            line=line,
            diagnostic_code="TW-02",
        )

    return Edge(
        caller=caller_cn,
        callee=matched_canonical,
        kind="proc_call",
        status="resolved",
        token=token,
        line=line,
        diagnostic_code=None,
    )


def _candidate_qnames(token: str, caller_namespace: str) -> tuple[str, ...]:
    """Build the ordered candidate qualified-name list for a raw token.

    Lexical namespace resolution:

    * ``::ns::helper`` — absolute; single candidate ``ns::helper``.
    * ``ns::helper`` — relative; try ``<caller_ns>::ns::helper`` then
      ``ns::helper``.
    * ``helper`` — bare; try ``<caller_ns>::helper`` then ``helper``.
    """
    # Strip leading ``::`` to get the "absolute" form test.
    if token.startswith("::"):
        return (token[2:],)

    # Relative or bare.
    if caller_namespace:
        qualified_first = f"{caller_namespace}::{token}"
        # When the token is already caller-namespace-qualified the two
        # candidates collapse to one. Dedupe while preserving order.
        if qualified_first == token:
            return (token,)
        return (qualified_first, token)
    return (token,)


def _is_dynamic(token: str) -> bool:
    """True if ``token`` is a dynamic / syntactically unresolvable call form."""
    if not token:
        return True
    # Variable substitution or bracket-command substitution in the head.
    if "$" in token or "[" in token or "]" in token:
        return True
    # Control tokens the parser leaves for the tracer — they are not proc names.
    # (Example: ``eval`` / ``uplevel`` head words that the parser did not
    # rewrite; the parser drops them in practice, but be defensive.)
    if token in {"eval", "uplevel", "uplevel#0", "apply"}:
        return True
    return False


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def _emit_cycle_diagnostics(ctx: ChopperContext, edges: Iterable[Edge]) -> None:
    """Walk the resolved-edge subgraph and emit ``TW-04`` for each cycle.

    Uses Tarjan-style DFS to find strongly connected components with size
    ≥ 2 and also flags any node that calls itself directly.
    """
    adjacency: dict[str, list[str]] = defaultdict(list)
    nodes: set[str] = set()
    for e in edges:
        if e.kind != "proc_call" or e.status != "resolved":
            continue
        adjacency[e.caller].append(e.callee)
        nodes.add(e.caller)
        nodes.add(e.callee)

    # Iterative Tarjan's SCC.
    index_counter = [0]
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(start: str) -> None:
        work_stack: list[tuple[str, int]] = [(start, 0)]
        while work_stack:
            v, pi = work_stack[-1]
            if pi == 0:
                indices[v] = index_counter[0]
                lowlinks[v] = index_counter[0]
                index_counter[0] += 1
                stack.append(v)
                on_stack.add(v)
            neighbours = adjacency.get(v, [])
            if pi < len(neighbours):
                work_stack[-1] = (v, pi + 1)
                w = neighbours[pi]
                if w not in indices:
                    work_stack.append((w, 0))
                elif w in on_stack:
                    lowlinks[v] = min(lowlinks[v], indices[w])
                continue
            # Done with v.
            if lowlinks[v] == indices[v]:
                component: list[str] = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    component.append(w)
                    if w == v:
                        break
                sccs.append(component)
            work_stack.pop()
            if work_stack:
                parent = work_stack[-1][0]
                lowlinks[parent] = min(lowlinks[parent], lowlinks[v])

    for n in sorted(nodes):
        if n not in indices:
            strongconnect(n)

    # An SCC with > 1 node is always a cycle. A singleton SCC is a cycle
    # only if it has a self-edge.
    self_loops = {e.caller for e in edges if e.kind == "proc_call" and e.status == "resolved" and e.caller == e.callee}
    for component in sccs:
        if len(component) > 1:
            path = " → ".join(sorted(component) + [sorted(component)[0]])
            _emit_tw04(ctx, sorted(component)[0], path)
        elif component and component[0] in self_loops:
            proc = component[0]
            _emit_tw04(ctx, proc, f"{proc} → {proc}")


# ---------------------------------------------------------------------------
# Diagnostic emit helpers
# ---------------------------------------------------------------------------


def _emit_tw01(ctx: ChopperContext, caller_cn: str, token: str, line: int, candidates: tuple[str, ...]) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "TW-01",
            phase=Phase.P4_TRACE,
            message=(
                f"Proc call {token!r} in {caller_cn!r} is ambiguous: matches "
                f"{len(candidates)} canonical procs ({', '.join(candidates)})"
            ),
            line_no=line,
            hint="Disambiguate by using the fully-qualified namespace or add explicit procedures.include",
        )
    )


def _emit_tw02(ctx: ChopperContext, caller_cn: str, token: str, line: int) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "TW-02",
            phase=Phase.P4_TRACE,
            message=(
                f"Proc call {token!r} in {caller_cn!r} resolves to no canonical proc in the domain; "
                f"assumed external or cross-domain"
            ),
            line_no=line,
            hint="If this proc is needed, add it explicitly or verify it lives in external libraries",
        )
    )


def _emit_ti01(ctx: ChopperContext, caller_cn: str, token: str, line: int) -> None:
    """Emit ``TI-01 known-tool-command`` — the pool-match informational variant of TW-02.

    Emitted from the P4 tracer when a call token's raw name or
    namespace-stripped leaf is a member of the tool-command pool (see
    architecture doc §3.10 and ``FR-44``). Exit code 0, does not count
    against ``--strict``. The edge carries ``status="tool_command"``.
    """
    ctx.diag.emit(
        Diagnostic.build(
            "TI-01",
            phase=Phase.P4_TRACE,
            message=(
                f"Proc call {token!r} in {caller_cn!r} matches the tool-command pool "
                f"(external EDA tool command; not an in-domain proc)"
            ),
            line_no=line,
            hint=None,
        )
    )


def _emit_tw03(ctx: ChopperContext, caller_cn: str, token: str, line: int) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "TW-03",
            phase=Phase.P4_TRACE,
            message=(
                f"Dynamic or syntactically unresolvable call form {token!r} in {caller_cn!r}; cannot statically trace"
            ),
            line_no=line,
            hint="Add missing dependencies explicitly to procedures.include if needed; review call site",
        )
    )


def _emit_tw04(ctx: ChopperContext, anchor_cn: str, cycle_path: str) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "TW-04",
            phase=Phase.P4_TRACE,
            message=f"Cycle detected in proc call graph: {cycle_path}",
            hint="Cycles are reporting-only; survival still requires explicit include",
            dedupe_bucket=anchor_cn,
        )
    )
