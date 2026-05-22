"""Unit tests for :mod:`chopper.compiler.stack_graph` (3.4.0 contract).

Covers:

* Topological sort with the authored-position tiebreaker.
* Graph edges = ``dependencies`` ∪ ``{load_from}`` (union, deduplicated).
* ``VE-30 stage-dependency-cycle`` on cycles (including self-loops).
* ``VE-31 stage-dependency-unresolved`` on dangling references via
  either ``dependencies`` or ``load_from``.
* ``CompiledManifest.stack_order`` permutation invariant.
* ``standalone_stack: true`` suppresses the per-stage ``<stage>.tcl``
  registration in ``_register_generated_stage_files``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.compiler.merge_service import CompilerService
from chopper.compiler.stack_graph import compute_stack_order
from chopper.core.errors import ChopperError
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest, StageSpec
from chopper.core.models_config import (
    BaseJson,
    BaseOptions,
    FilesSection,
    LoadedConfig,
    ProceduresSection,
    StageDefinition,
)
from chopper.core.models_parser import ParseResult

from ._helpers import make_ctx

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


DOMAIN_ROOT = Path("/dom/my_domain")


def _stage(name: str, *, load_from: str = "", dependencies: tuple[str, ...] = ()) -> StageSpec:
    return StageSpec(name=name, steps=("a",), load_from=load_from, dependencies=dependencies)


def _empty_parsed() -> ParseResult:
    return ParseResult(index={}, files={})


def _base(stages: tuple[StageDefinition, ...], generate_stack: bool = True) -> BaseJson:
    return BaseJson(
        source_path=Path("/dom/my_domain/base.json"),
        domain="my_domain",
        files=FilesSection(include=(), exclude=()),
        procedures=ProceduresSection(include=(), exclude=()),
        stages=stages,
        options=BaseOptions(generate_stack=generate_stack),
    )


# ---------------------------------------------------------------------------
# compute_stack_order — happy paths
# ---------------------------------------------------------------------------


def test_compute_stack_order_empty() -> None:
    ctx, _ = make_ctx()
    assert compute_stack_order(ctx, ()) == ()


def test_compute_stack_order_single_stage_no_edges() -> None:
    ctx, _ = make_ctx()
    order = compute_stack_order(ctx, (_stage("a"),))
    assert order == ("a",)


def test_compute_stack_order_already_topological_preserves_order() -> None:
    """A chain ``a -> b -> c`` in authored order stays in authored order."""

    ctx, _ = make_ctx()
    stages = (
        _stage("a"),
        _stage("b", load_from="a"),
        _stage("c", load_from="b"),
    )
    assert compute_stack_order(ctx, stages) == ("a", "b", "c")


def test_compute_stack_order_reorders_when_authoring_is_reverse_topological() -> None:
    """Authored order ``c, b, a`` with deps ``b<-a, c<-b`` is fully
    reordered to ``a, b, c``."""

    ctx, _ = make_ctx()
    stages = (
        _stage("c", load_from="b"),
        _stage("b", load_from="a"),
        _stage("a"),
    )
    assert compute_stack_order(ctx, stages) == ("a", "b", "c")


def test_compute_stack_order_dependencies_union_with_load_from() -> None:
    """An edge contributed only via ``dependencies`` still affects order."""

    ctx, _ = make_ctx()
    stages = (
        _stage("c", dependencies=("a", "b")),
        _stage("a"),
        _stage("b"),
    )
    order = compute_stack_order(ctx, stages)
    # ``a`` and ``b`` come before ``c``. Among ``a`` and ``b`` (both
    # in-degree 0), authored-position tiebreaker means: ``a`` was at
    # index 1, ``b`` at index 2, so ``a`` first.
    assert order == ("a", "b", "c")


def test_compute_stack_order_tiebreaker_is_authored_position_not_lex() -> None:
    """Two zero-in-degree stages: the earlier-authored wins regardless
    of lex order."""

    ctx, _ = make_ctx()
    # ``zeta`` authored first, ``alpha`` authored second; both have
    # in-degree 0. Authored position wins: zeta before alpha.
    stages = (_stage("zeta"), _stage("alpha"))
    assert compute_stack_order(ctx, stages) == ("zeta", "alpha")


def test_compute_stack_order_duplicate_predecessor_via_both_fields_counted_once() -> None:
    """A stage that names the same predecessor via both ``dependencies``
    and ``load_from`` is not double-counted (the in-degree stays 1)."""

    ctx, _ = make_ctx()
    stages = (
        _stage("a"),
        _stage("b", load_from="a", dependencies=("a",)),
    )
    assert compute_stack_order(ctx, stages) == ("a", "b")


# ---------------------------------------------------------------------------
# VE-30 stage-dependency-cycle
# ---------------------------------------------------------------------------


def test_ve30_emitted_on_two_node_cycle() -> None:
    ctx, sink = make_ctx()
    stages = (
        _stage("a", load_from="b"),
        _stage("b", load_from="a"),
    )
    with pytest.raises(ChopperError, match="cycle"):
        compute_stack_order(ctx, stages)
    assert "VE-30" in [d.code for d in sink.snapshot()]


def test_ve30_emitted_on_self_loop_via_load_from() -> None:
    ctx, sink = make_ctx()
    stages = (_stage("a", load_from="a"),)
    with pytest.raises(ChopperError, match="cycle"):
        compute_stack_order(ctx, stages)
    assert "VE-30" in [d.code for d in sink.snapshot()]


def test_ve30_emitted_on_self_loop_via_dependencies() -> None:
    ctx, sink = make_ctx()
    stages = (_stage("a", dependencies=("a",)),)
    with pytest.raises(ChopperError, match="cycle"):
        compute_stack_order(ctx, stages)
    assert "VE-30" in [d.code for d in sink.snapshot()]


def test_ve30_emitted_on_three_node_cycle_mixing_fields() -> None:
    ctx, sink = make_ctx()
    stages = (
        _stage("a", load_from="c"),
        _stage("b", dependencies=("a",)),
        _stage("c", load_from="b"),
    )
    with pytest.raises(ChopperError, match="cycle"):
        compute_stack_order(ctx, stages)
    assert "VE-30" in [d.code for d in sink.snapshot()]


def test_ve30_strips_residual_leaf_attached_to_cycle() -> None:
    """A residual leaf (downstream of a cycle, no out-edges) must be
    stripped from the cycle-extraction walk so the reported cycle
    contains only true cycle members."""

    ctx, sink = make_ctx()
    # Cycle: y <-> z (y.load_from=z and z.load_from=y).
    # Leaf:  a depends on z but has no outgoing edges. ``a`` is
    # residual (z never completes) yet is not on the cycle.
    stages = (
        _stage("a", load_from="z"),
        _stage("y", load_from="z"),
        _stage("z", load_from="y"),
    )
    with pytest.raises(ChopperError, match="cycle"):
        compute_stack_order(ctx, stages)
    diags = [d for d in sink.snapshot() if d.code == "VE-30"]
    assert len(diags) == 1
    # The reported cycle must contain only true cycle members (y, z) —
    # the residual leaf ``a`` must have been stripped before walking.
    assert "y -> z -> y" in diags[0].message or "z -> y -> z" in diags[0].message


# ---------------------------------------------------------------------------
# VE-31 stage-dependency-unresolved
# ---------------------------------------------------------------------------


def test_ve31_emitted_on_unresolved_load_from() -> None:
    ctx, sink = make_ctx()
    stages = (_stage("a", load_from="ghost"),)
    with pytest.raises(ChopperError, match="unresolved"):
        compute_stack_order(ctx, stages)
    codes = [d.code for d in sink.snapshot()]
    assert "VE-31" in codes


def test_ve31_emitted_on_unresolved_dependency() -> None:
    ctx, sink = make_ctx()
    stages = (_stage("a", dependencies=("ghost",)),)
    with pytest.raises(ChopperError, match="unresolved"):
        compute_stack_order(ctx, stages)
    assert "VE-31" in [d.code for d in sink.snapshot()]


def test_ve31_emitted_for_each_bogus_reference() -> None:
    """Multiple unresolved references fire one VE-31 each before raising."""

    ctx, sink = make_ctx()
    stages = (
        _stage("a", load_from="ghost1"),
        _stage("b", dependencies=("ghost2", "ghost3")),
    )
    with pytest.raises(ChopperError, match="unresolved"):
        compute_stack_order(ctx, stages)
    codes = [d.code for d in sink.snapshot()]
    assert codes.count("VE-31") == 3


def test_ve31_message_names_field() -> None:
    ctx, sink = make_ctx()
    stages = (_stage("a", load_from="ghost"),)
    with pytest.raises(ChopperError):
        compute_stack_order(ctx, stages)
    msg = sink.snapshot()[0].message
    assert "'ghost'" in msg
    assert "load_from" in msg


# ---------------------------------------------------------------------------
# CompilerService end-to-end: stack_order populated, .tcl suppressed
# ---------------------------------------------------------------------------


def test_compiler_populates_stack_order_in_topological_order() -> None:
    """End-to-end: CompilerService computes and records ``stack_order``."""

    ctx, _ = make_ctx()
    base = _base(
        generate_stack=True,
        stages=(
            StageDefinition(name="c", load_from="b", steps=("a",), command="-T c"),
            StageDefinition(name="a", load_from="", steps=("a",), command="-T a"),
            StageDefinition(name="b", load_from="a", steps=("a",), command="-T b"),
        ),
    )
    manifest = CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())
    # manifest.stages keeps authored order; stack_order is topological.
    assert tuple(s.name for s in manifest.stages) == ("c", "a", "b")
    assert manifest.stack_order == ("a", "b", "c")


def test_compiler_populates_stack_order_even_when_generate_stack_off() -> None:
    """``stack_order`` is computed regardless of ``generate_stack``.

    The graph is validated unconditionally; the order is cheap and
    useful for audit consumers.
    """

    ctx, _ = make_ctx()
    base = _base(
        generate_stack=False,
        stages=(
            StageDefinition(name="b", load_from="a", steps=("a",)),
            StageDefinition(name="a", load_from="", steps=("a",)),
        ),
    )
    manifest = CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())
    assert manifest.stack_order == ("a", "b")


def test_compiler_raises_ve31_when_load_from_dangles() -> None:
    ctx, sink = make_ctx()
    base = _base(
        generate_stack=False,
        stages=(StageDefinition(name="a", load_from="ghost", steps=("a",)),),
    )
    with pytest.raises(ChopperError):
        CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())
    assert "VE-31" in [d.code for d in sink.snapshot()]


def test_compiler_raises_ve30_on_cycle() -> None:
    ctx, sink = make_ctx()
    base = _base(
        generate_stack=False,
        stages=(
            StageDefinition(name="a", load_from="b", steps=("a",)),
            StageDefinition(name="b", load_from="a", steps=("a",)),
        ),
    )
    with pytest.raises(ChopperError):
        CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())
    assert "VE-30" in [d.code for d in sink.snapshot()]


def test_standalone_stack_stage_does_not_register_tcl() -> None:
    """3.4.0: ``standalone_stack: true`` suppresses ``<stage>.tcl``
    registration entirely."""

    ctx, _ = make_ctx()
    base = _base(
        generate_stack=False,
        stages=(
            StageDefinition(name="setup", load_from="", steps=("a",)),
            StageDefinition(
                name="patch",
                load_from="setup",
                steps=("rm -rf x",),
                standalone_stack=True,
            ),
        ),
    )
    manifest = CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())
    assert manifest.file_decisions[Path("setup.tcl")] is FileTreatment.GENERATED
    assert Path("patch.tcl") not in manifest.file_decisions
    assert manifest.file_decisions[Path("patch.stack")] is FileTreatment.GENERATED


# ---------------------------------------------------------------------------
# CompiledManifest.stack_order invariant
# ---------------------------------------------------------------------------


def test_compiled_manifest_rejects_stack_order_not_permutation_of_stages() -> None:
    """stack_order must be exactly the set of stage names."""

    s = _stage("a")
    with pytest.raises(ValueError, match="permutation"):
        CompiledManifest(stages=(s,), stack_order=("a", "b"))


def test_compiled_manifest_rejects_duplicate_names_in_stack_order() -> None:
    s_a = _stage("a")
    s_b = _stage("b")
    with pytest.raises(ValueError, match="unique"):
        CompiledManifest(stages=(s_a, s_b), stack_order=("a", "a"))


def test_compiled_manifest_accepts_empty_stack_order_with_any_stages() -> None:
    """Empty stack_order is the legacy default — no validation against
    stages."""

    s = _stage("a")
    m = CompiledManifest(stages=(s,))
    assert m.stack_order == ()


def test_compiled_manifest_accepts_valid_topological_stack_order() -> None:
    s_a = _stage("a")
    s_b = _stage("b", load_from="a")
    m = CompiledManifest(stages=(s_b, s_a), stack_order=("a", "b"))
    assert m.stack_order == ("a", "b")
