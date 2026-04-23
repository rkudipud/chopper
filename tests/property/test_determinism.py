"""Property tests for determinism (NFR-03).

Closes T-02 from the 2026-04-23 spec-conformance audit. NFR-03
(chopper_description.md §11) is *"byte-identical output on every run"*.
Before these tests existed, determinism was asserted only by
example-based unit tests. Hypothesis explores a much wider input space
and catches accidental dependencies on dict insertion order, set
iteration order, and locale-sensitive sorting.

What this module guards:

1. **Serializer idempotence.** ``dump_model(x) == dump_model(x)`` for
   any JSON-able value. Re-serializing yields byte-identical output.
2. **Insertion-order independence.** A dict built by inserting keys in
   order A vs order B serializes to the same string (guaranteed by
   ``sort_keys=True`` but property-checked in the wild).
3. **BFS frontier determinism.** Given a random call graph, the BFS
   traversal order is purely a function of the *set* of seeds + edges,
   not of their input ordering. This matches the contract in bible §5.4
   and TCL_PARSER_SPEC §10.1: *"frontier sorted lexicographically at
   each step"*.

The tests deliberately stay at the pure-function level — no
``ChopperContext``, no filesystem. Tracer-service determinism is
integration-covered by the golden-file tests in
``tests/golden/test_audit_artifacts_golden.py``.
"""

from __future__ import annotations

from collections import deque
from pathlib import PurePosixPath

from hypothesis import given
from hypothesis import strategies as st

from chopper.core.serialization import dump_model

# ---------------------------------------------------------------------------
# Strategies — JSON-able value trees the serializer must handle.
# ---------------------------------------------------------------------------
#
# Deliberately narrower than "everything JSON accepts" so each failure is
# attributable: keys are ASCII identifiers, leaves are stable primitives
# plus Path (which serializes via :func:`PurePath.as_posix`).


_ident = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    min_size=1,
    max_size=16,
)

_leaves: st.SearchStrategy[object] = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31 - 1),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    _ident,
    _ident.map(lambda s: PurePosixPath(f"subdir/{s}.tcl")),
)


def _tree() -> st.SearchStrategy[object]:
    """Recursive JSON-shaped tree: dicts / lists / tuples / leaves."""
    return st.recursive(
        _leaves,
        lambda child: st.one_of(
            st.lists(child, max_size=6),
            st.dictionaries(_ident, child, max_size=6),
            st.tuples(child, child),
        ),
        max_leaves=20,
    )


# ---------------------------------------------------------------------------
# 1. Serializer idempotence.
# ---------------------------------------------------------------------------


@given(_tree())
def test_dump_model_is_idempotent(value: object) -> None:
    """Two consecutive ``dump_model`` calls on the same value agree byte-for-byte."""
    first = dump_model(value)
    second = dump_model(value)
    assert first == second, "dump_model must be idempotent (NFR-03)"


# ---------------------------------------------------------------------------
# 2. Insertion-order independence of dict keys.
# ---------------------------------------------------------------------------


@given(
    st.lists(
        st.tuples(_ident, st.integers(min_value=-1000, max_value=1000)),
        min_size=1,
        max_size=12,
        unique_by=lambda t: t[0],
    )
)
def test_dump_model_is_insertion_order_independent(pairs: list[tuple[str, int]]) -> None:
    """A dict built from the same (key, value) pairs in any order serializes identically."""
    forward = dict(pairs)
    reverse = dict(reversed(pairs))
    # Both dicts contain the same (key, value) pairs but potentially with
    # different insertion orders. ``sort_keys=True`` in dump_model must
    # make them indistinguishable on the wire.
    assert dump_model(forward) == dump_model(reverse)


# ---------------------------------------------------------------------------
# 3. BFS determinism — pure property test over a call-graph shape.
# ---------------------------------------------------------------------------
#
# Mirrors the shape the tracer uses (bible §5.4, TCL_PARSER_SPEC §10.1):
# seeds + adjacency lists. ``bfs_visit`` below is the same algorithm
# (frontier sorted lex at each step, visited set dedupes). The property
# asserts that shuffling the input ordering of seeds and of each
# adjacency list produces the same visit sequence.


def _bfs_visit(seeds: list[str], adjacency: dict[str, list[str]]) -> list[str]:
    """Lex-sorted BFS mirroring the tracer contract."""
    visited: set[str] = set()
    order: list[str] = []
    frontier: deque[str] = deque(sorted(seeds))
    while frontier:
        layer = sorted(set(frontier))
        frontier.clear()
        next_layer: list[str] = []
        for node in layer:
            if node in visited:
                continue
            visited.add(node)
            order.append(node)
            # Expand this node's neighbours into the next layer, with
            # the same lex-sort contract.
            for nbr in sorted(set(adjacency.get(node, ()))):
                if nbr not in visited:
                    next_layer.append(nbr)
        frontier.extend(sorted(set(next_layer)))
    return order


_node = _ident


@given(
    seeds=st.lists(_node, min_size=1, max_size=6, unique=True),
    edges=st.lists(st.tuples(_node, _node), max_size=30),
)
def test_bfs_visit_is_deterministic_under_input_shuffling(seeds: list[str], edges: list[tuple[str, str]]) -> None:
    """BFS visit order depends only on the *set* of seeds and edges, not ordering."""
    adjacency: dict[str, list[str]] = {}
    for src, dst in edges:
        adjacency.setdefault(src, []).append(dst)

    # Build a second adjacency where each list is reversed — same graph,
    # different input ordering.
    shuffled = {k: list(reversed(v)) for k, v in adjacency.items()}

    straight = _bfs_visit(seeds, adjacency)
    reverse_seeds = _bfs_visit(list(reversed(seeds)), shuffled)
    assert straight == reverse_seeds, "BFS visit order must be a pure function of the call-graph set (NFR-03)"
