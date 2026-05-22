"""Unit tests for :mod:`chopper.generators.stack_emitter` (3.3.0 contract).

Covers:

* :func:`aggregate_stack_path` and :func:`standalone_stack_path` path
  derivation.
* :func:`emit_flow_stack` — aggregate file shape: single Intel header
  on top, one record per stage separated by exactly one blank line,
  per-record line order ``N → J → L → I → O → D → R`` with ``R``
  emitted only for ``parallel`` stages, ``D`` derivation rules
  (``dependencies`` > ``load_from`` > bare ``D``), and ``J`` / ``L`` /
  ``I`` / ``O`` suppression when the corresponding field is empty.
* :func:`emit_standalone_stack` — per-stage file is Intel header + one
  blank line + authored ``steps`` joined by ``"\\n"`` verbatim.
"""

from __future__ import annotations

from pathlib import Path

from chopper.core.header import intel_header_lines, intel_header_text
from chopper.core.models_compiler import StageSpec
from chopper.generators.stack_emitter import (
    aggregate_stack_path,
    emit_flow_stack,
    emit_standalone_stack,
    standalone_stack_path,
)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def test_aggregate_stack_path_uses_domain_basename() -> None:
    assert aggregate_stack_path("my_domain") == Path("my_domain.stack")


def test_standalone_stack_path_uses_stage_name() -> None:
    stage = StageSpec(name="eco_apply_patch", steps=("x",))
    assert standalone_stack_path(stage) == Path("eco_apply_patch.stack")


# ---------------------------------------------------------------------------
# emit_flow_stack — single / multi
# ---------------------------------------------------------------------------


def test_emit_flow_stack_single_minimal_stage_layout() -> None:
    stage = StageSpec(name="setup", steps=("x",))
    art = emit_flow_stack((stage,), "my_domain")
    assert art.kind == "stack"
    # Aggregate artifacts use the domain name in source_stage (GeneratedArtifact
    # requires source_stage to be non-empty; there is no single owning stage).
    assert art.source_stage == "my_domain"
    assert art.path == Path("my_domain.stack")
    assert art.content.endswith("\n")

    lines = art.content.rstrip("\n").split("\n")
    # Header lines (no trailing newline on each), then ONE blank line, then record.
    header = list(intel_header_lines())
    assert lines[: len(header)] == header
    assert lines[len(header)] == ""  # blank separator between header and record
    assert lines[len(header) + 1 :] == [
        "# Chopper-generated stack: setup",
        "N setup",
        "D",
    ]


def test_emit_flow_stack_multi_stage_records_separated_by_single_blank_line() -> None:
    stages = (
        StageSpec(name="setup", steps=("x",)),
        StageSpec(name="run", steps=("x",), load_from="setup"),
    )
    art = emit_flow_stack(stages, "my_domain")
    # Header appears exactly once.
    assert art.content.count("#Intel Legal compliant copyright header") == 1
    # Both record banners present, separated by an empty line.
    assert "\n\n# Chopper-generated stack: setup\n" in art.content
    assert "\n\n# Chopper-generated stack: run\n" in art.content


# ---------------------------------------------------------------------------
# Per-record line order: N → J → L → I → O → D → R
# ---------------------------------------------------------------------------


def test_emit_flow_stack_full_record_line_order() -> None:
    stage = StageSpec(
        name="run_verify",
        steps=("ignored",),
        load_from="setup",
        command="-tool fm -B BLOCK -T run_verify",
        exit_codes=(0, 3, 5),
        dependencies=("setup",),
        inputs=("$ward/design.v.gz",),
        outputs=("$ward/result.rpt",),
        run_mode="parallel",
    )
    art = emit_flow_stack((stage,), "dom")
    # Slice the record (everything after the header + blank separator).
    header = intel_header_text()
    record = art.content[len(header) + 1 :].rstrip("\n")
    assert record.split("\n") == [
        "# Chopper-generated stack: run_verify",
        "N run_verify",
        "J -tool fm -B BLOCK -T run_verify",
        "L 0 3 5",
        "I $ward/design.v.gz",
        "O $ward/result.rpt",
        "D setup",
        "R parallel",
    ]


# ---------------------------------------------------------------------------
# R-line: parallel-only, serial omitted
# ---------------------------------------------------------------------------


def test_emit_flow_stack_serial_omits_r_line() -> None:
    stage = StageSpec(name="setup", steps=("x",), run_mode="serial")
    art = emit_flow_stack((stage,), "dom")
    assert "\nR " not in art.content
    assert "R serial" not in art.content


def test_emit_flow_stack_parallel_emits_r_parallel() -> None:
    stage = StageSpec(name="setup", steps=("x",), run_mode="parallel")
    art = emit_flow_stack((stage,), "dom")
    assert art.content.rstrip("\n").endswith("R parallel")


# ---------------------------------------------------------------------------
# Field suppression
# ---------------------------------------------------------------------------


def test_emit_flow_stack_empty_command_omits_j_line() -> None:
    stage = StageSpec(name="setup", steps=("x",))
    art = emit_flow_stack((stage,), "dom")
    assert "\nJ " not in art.content


def test_emit_flow_stack_empty_exit_codes_omits_l_line() -> None:
    stage = StageSpec(name="setup", steps=("x",))
    art = emit_flow_stack((stage,), "dom")
    assert "\nL " not in art.content


def test_emit_flow_stack_no_inputs_no_outputs_omits_those_lines() -> None:
    stage = StageSpec(name="setup", steps=("x",))
    art = emit_flow_stack((stage,), "dom")
    assert "\nI " not in art.content
    assert "\nO " not in art.content


def test_emit_flow_stack_inputs_emit_one_line_per_entry() -> None:
    stage = StageSpec(name="run", steps=("x",), inputs=("a.v", "b.v"))
    art = emit_flow_stack((stage,), "dom")
    assert "\nI a.v\nI b.v\n" in art.content


def test_emit_flow_stack_outputs_emit_one_line_per_entry() -> None:
    stage = StageSpec(name="run", steps=("x",), outputs=("r.rpt", "s.rpt"))
    art = emit_flow_stack((stage,), "dom")
    assert "\nO r.rpt\nO s.rpt\n" in art.content


# ---------------------------------------------------------------------------
# D-derivation rules: dependencies > load_from > bare D
# ---------------------------------------------------------------------------


def test_emit_flow_stack_dependencies_override_load_from() -> None:
    stage = StageSpec(
        name="promote",
        steps=("x",),
        load_from="setup",
        dependencies=("run_verify", "run_lint"),
    )
    art = emit_flow_stack((stage,), "dom")
    assert "\nD run_verify\nD run_lint\n" in art.content
    # load_from must NOT contribute a D line when dependencies is set.
    assert "\nD setup\n" not in art.content


def test_emit_flow_stack_load_from_used_when_no_dependencies() -> None:
    stage = StageSpec(name="promote", steps=("x",), load_from="setup")
    art = emit_flow_stack((stage,), "dom")
    assert "\nD setup\n" in art.content


def test_emit_flow_stack_no_deps_no_load_from_yields_bare_d() -> None:
    stage = StageSpec(name="setup", steps=("x",))
    art = emit_flow_stack((stage,), "dom")
    # bare "D" line (followed by newline) appears as a record-terminating line
    assert "\nD\n" in art.content


# ---------------------------------------------------------------------------
# emit_standalone_stack
# ---------------------------------------------------------------------------


def test_emit_standalone_stack_basic_shape() -> None:
    stage = StageSpec(name="eco_apply_patch", steps=("rm -rf old", "cp -r src dst"))
    art = emit_standalone_stack(stage)
    assert art.kind == "stack"
    assert art.path == Path("eco_apply_patch.stack")
    assert art.source_stage == "eco_apply_patch"
    # Intel header verbatim, then ONE blank line, then steps verbatim, trailing \n.
    expected = intel_header_text() + "\n" + "rm -rf old\ncp -r src dst\n"
    assert art.content == expected


def test_emit_standalone_stack_ignores_record_fields() -> None:
    """Standalone stack uses verbatim ``steps`` only; command/deps/etc. are not rendered."""

    stage = StageSpec(
        name="verbatim",
        steps=("echo hello",),
        command="-tool ignored",
        exit_codes=(0, 1),
        dependencies=("setup",),
        load_from="setup",
        inputs=("ignored.in",),
        outputs=("ignored.out",),
        run_mode="parallel",
    )
    art = emit_standalone_stack(stage)
    # No record-style lines should leak in.
    assert "\nN " not in art.content
    assert "\nJ " not in art.content
    assert "\nL " not in art.content
    assert "\nD " not in art.content
    assert "\nI " not in art.content
    assert "\nO " not in art.content
    assert "\nR " not in art.content
    # But the verbatim step is present.
    assert art.content.rstrip("\n").endswith("echo hello")


def test_emit_standalone_stack_single_step() -> None:
    stage = StageSpec(name="solo", steps=("one_step",))
    art = emit_standalone_stack(stage)
    assert art.content == intel_header_text() + "\n" + "one_step\n"
