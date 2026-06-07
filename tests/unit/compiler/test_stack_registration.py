"""Compiler-side tests for the 3.3.0 stack-file registration contract.

Covers :func:`chopper.compiler.merge_service._register_generated_stage_files`
via :class:`CompilerService.run` -- the public entry point. Asserts:

* Aggregate ``<domain-basename>.stack`` is registered as ``GENERATED``
  exactly once when ``options.generate_stack: true`` and at least one
  stage is resolved.
* Per-stage ``<stage>.stack`` is registered only when the stage sets
  ``standalone_stack: true`` -- orthogonal to ``generate_stack``.
* ``VE-28 aggregate-stack-collision`` fires when the aggregate path
  collides with an existing ``files.*`` entry, and the compiler then
  raises :class:`ChopperError`.
* ``VE-29 standalone-stack-collision`` fires when a stage's per-stage
  ``<stage>.stack`` collides with an existing ``files.*`` entry or with
  the aggregate path itself, and raises :class:`ChopperError`.
* ``VW-23 stack-stage-empty-command`` fires for any stage included in
  the aggregate whose ``command`` is empty (it does **not** fire when
  ``generate_stack`` is off, since no aggregate record is emitted).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.compiler.merge_service import CompilerService
from chopper.core.errors import ChopperError
from chopper.core.models_common import FileTreatment
from chopper.core.models_config import (
    BaseJson,
    BaseOptions,
    FilesSection,
    LoadedConfig,
    ProceduresSection,
    StageDefinition,
)
from chopper.core.models_parser import ParseResult
from tests.unit.compiler._helpers import make_ctx


def _empty_parsed() -> ParseResult:
    return ParseResult(files={}, index={})


def _base(
    *,
    stages: tuple[StageDefinition, ...],
    files_include: tuple[str, ...] = (),
    generate_stack: bool = False,
) -> BaseJson:
    return BaseJson(
        source_path=Path("/dom/my_domain/base.json"),
        domain="my_domain",
        files=FilesSection(include=files_include, exclude=()),
        procedures=ProceduresSection(include=(), exclude=()),
        stages=stages,
        options=BaseOptions(generate_stack=generate_stack),
    )


# ---------------------------------------------------------------------------
# Aggregate registration
# ---------------------------------------------------------------------------


def test_aggregate_stack_registered_when_generate_stack_on() -> None:
    """``options.generate_stack: true`` registers exactly one aggregate
    ``<domain-basename>.stack`` as ``GENERATED`` and no per-stage ``.stack``.
    """

    ctx, _sink = make_ctx()
    base = _base(
        generate_stack=True,
        stages=(
            StageDefinition(name="setup", load_from="", steps=("a",), command="-tool x"),
            StageDefinition(name="run", load_from="setup", steps=("b",), command="-tool y"),
        ),
    )
    manifest = CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())

    # Domain basename is "my_domain" -> my_domain.stack.
    assert manifest.file_decisions[Path("my_domain.stack")] is FileTreatment.GENERATED
    # No per-stage .stack entries.
    assert Path("setup.stack") not in manifest.file_decisions
    assert Path("run.stack") not in manifest.file_decisions
    # Each stage .tcl is registered.
    assert manifest.file_decisions[Path("setup.tcl")] is FileTreatment.GENERATED
    assert manifest.file_decisions[Path("run.tcl")] is FileTreatment.GENERATED


def test_no_aggregate_when_generate_stack_off() -> None:
    """No aggregate entry without ``generate_stack: true``."""

    ctx, _sink = make_ctx()
    base = _base(
        generate_stack=False,
        stages=(StageDefinition(name="setup", load_from="", steps=("a",)),),
    )
    manifest = CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())

    assert Path("my_domain.stack") not in manifest.file_decisions
    assert manifest.file_decisions[Path("setup.tcl")] is FileTreatment.GENERATED


def test_no_aggregate_when_no_stages_resolved() -> None:
    """Aggregate is not registered when the resolved stage tuple is empty,
    even with ``generate_stack: true``."""

    ctx, _sink = make_ctx()
    base = _base(generate_stack=True, stages=())
    manifest = CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())
    assert Path("my_domain.stack") not in manifest.file_decisions


# ---------------------------------------------------------------------------
# Standalone (per-stage) registration
# ---------------------------------------------------------------------------


def test_standalone_stack_registered_only_for_marked_stages() -> None:
    """Only stages with ``standalone_stack: true`` get a per-stage ``.stack``
    entry; orthogonal to the aggregate flag."""

    ctx, _sink = make_ctx()
    base = _base(
        generate_stack=False,
        stages=(
            StageDefinition(name="setup", load_from="", steps=("a",)),
            StageDefinition(
                name="eco_apply_patch",
                load_from="setup",
                steps=("rm -rf x",),
                standalone_stack=True,
            ),
        ),
    )
    manifest = CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())

    assert manifest.file_decisions[Path("eco_apply_patch.stack")] is FileTreatment.GENERATED
    assert Path("setup.stack") not in manifest.file_decisions
    # No aggregate because generate_stack is False.
    assert Path("my_domain.stack") not in manifest.file_decisions
    # 3.4.0: standalone_stack stage does NOT register a .tcl; non-standalone does.
    assert manifest.file_decisions[Path("setup.tcl")] is FileTreatment.GENERATED
    assert Path("eco_apply_patch.tcl") not in manifest.file_decisions


def test_aggregate_and_standalone_together() -> None:
    """Mixed flow: aggregate + one standalone stage coexist."""

    ctx, _sink = make_ctx()
    base = _base(
        generate_stack=True,
        stages=(
            StageDefinition(name="setup", load_from="", steps=("a",), command="-tool x"),
            StageDefinition(
                name="eco_apply_patch",
                load_from="setup",
                steps=("rm -rf x",),
                command="-tool patch",
                standalone_stack=True,
            ),
        ),
    )
    manifest = CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())

    assert manifest.file_decisions[Path("my_domain.stack")] is FileTreatment.GENERATED
    assert manifest.file_decisions[Path("eco_apply_patch.stack")] is FileTreatment.GENERATED
    assert Path("setup.stack") not in manifest.file_decisions
    # 3.4.0: standalone stage suppresses .tcl; the non-standalone stage keeps it.
    assert manifest.file_decisions[Path("setup.tcl")] is FileTreatment.GENERATED
    assert Path("eco_apply_patch.tcl") not in manifest.file_decisions


# ---------------------------------------------------------------------------
# VE-28 aggregate-stack-collision
# ---------------------------------------------------------------------------


def test_ve28_emitted_when_aggregate_collides_with_files_entry() -> None:
    """Aggregate path collides with a literal ``files.include`` entry ->
    ``VE-28`` + ``ChopperError``."""

    ctx, sink = make_ctx()
    base = _base(
        generate_stack=True,
        files_include=("my_domain.stack",),  # collides with aggregate path
        stages=(StageDefinition(name="setup", load_from="", steps=("a",), command="-tool x"),),
    )
    with pytest.raises(ChopperError, match="generate_stack|collides"):
        CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())
    assert "VE-28" in sink.codes()


# ---------------------------------------------------------------------------
# VE-29 standalone-stack-collision
# ---------------------------------------------------------------------------


def test_ve29_emitted_when_standalone_collides_with_files_entry() -> None:
    """Per-stage ``<stage>.stack`` collides with a ``files.include`` entry ->
    ``VE-29`` + ``ChopperError``."""

    ctx, sink = make_ctx()
    base = _base(
        generate_stack=False,
        files_include=("eco_apply_patch.stack",),
        stages=(
            StageDefinition(
                name="eco_apply_patch",
                load_from="",
                steps=("rm -rf x",),
                standalone_stack=True,
            ),
        ),
    )
    with pytest.raises(ChopperError, match="standalone_stack|collides"):
        CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())
    assert "VE-29" in sink.codes()


def test_ve29_emitted_when_standalone_path_equals_aggregate_path() -> None:
    """A stage whose name equals the domain basename produces a
    ``<stage>.stack`` path that collides with the aggregate
    ``<domain-basename>.stack`` -> ``VE-29`` + ``ChopperError``.

    The compiler test context uses ``DOMAIN_ROOT = /dom/my_domain``; a
    stage literally named ``my_domain`` triggers the collision.
    """

    ctx, sink = make_ctx()
    base = _base(
        generate_stack=True,
        stages=(
            StageDefinition(
                name="my_domain",
                load_from="",
                steps=("a",),
                command="-tool x",
                standalone_stack=True,
            ),
        ),
    )
    with pytest.raises(ChopperError, match="standalone_stack|collides"):
        CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())
    assert "VE-29" in sink.codes()


# ---------------------------------------------------------------------------
# VW-23 stack-stage-empty-command
# ---------------------------------------------------------------------------


def test_vw23_emitted_when_aggregate_stage_has_empty_command() -> None:
    """A stage in the aggregate with no ``command`` fires ``VW-23``."""

    ctx, sink = make_ctx()
    base = _base(
        generate_stack=True,
        stages=(
            StageDefinition(name="setup", load_from="", steps=("a",), command="-tool x"),
            StageDefinition(name="noop", load_from="setup", steps=("a",)),  # empty command
        ),
    )
    CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())
    codes = sink.codes()
    assert "VW-23" in codes
    # Only the empty-command stage triggers VW-23.
    assert codes.count("VW-23") == 1


def test_vw23_not_emitted_when_generate_stack_off() -> None:
    """Stages outside the aggregate (no ``generate_stack``) never fire
    ``VW-23``, even with empty ``command``."""

    ctx, sink = make_ctx()
    base = _base(
        generate_stack=False,
        stages=(StageDefinition(name="noop", load_from="", steps=("a",)),),
    )
    CompilerService().run(ctx, LoadedConfig(base=base, features=(), project=None), _empty_parsed())
    assert "VW-23" not in sink.codes()
