"""Unit tests for :mod:`chopper.generators.stack_emitter`."""

from __future__ import annotations

from pathlib import Path

from chopper.core.models_compiler import StageSpec
from chopper.generators.stack_emitter import emit_stage_stack, stack_output_path


def test_stack_output_path_defaults_to_stage_name_stack() -> None:
    stage = StageSpec(name="verify", steps=("x",))
    assert stack_output_path(stage) == Path("verify.stack")


def test_minimal_stage_emits_only_required_lines() -> None:
    stage = StageSpec(name="setup", steps=("a",))
    art = emit_stage_stack(stage)
    assert art.kind == "stack"
    assert art.source_stage == "setup"
    assert art.path == Path("setup.stack")
    assert art.content.endswith("\n")
    lines = art.content.rstrip("\n").split("\n")
    assert lines == [
        "# Chopper-generated stack: setup",
        "N setup",
        "D",
        "R serial",
    ]


def test_command_emits_j_line() -> None:
    stage = StageSpec(name="run", steps=("x",), command="-tool fm -B BLOCK")
    content = emit_stage_stack(stage).content
    assert "\nJ -tool fm -B BLOCK\n" in content


def test_exit_codes_emit_l_line_space_joined() -> None:
    stage = StageSpec(name="run", steps=("x",), exit_codes=(0, 3, 5))
    content = emit_stage_stack(stage).content
    assert "\nL 0 3 5\n" in content


def test_dependencies_override_load_from_and_emit_one_d_per_entry() -> None:
    stage = StageSpec(
        name="promote",
        steps=("x",),
        load_from="setup",
        dependencies=("run_verify", "run_lint"),
    )
    content = emit_stage_stack(stage).content
    assert "\nD run_verify\n" in content
    assert "\nD run_lint\n" in content
    # load_from must NOT appear in a D line when dependencies is set.
    assert "\nD setup\n" not in content


def test_load_from_used_for_d_when_no_dependencies() -> None:
    stage = StageSpec(name="promote", steps=("x",), load_from="setup")
    content = emit_stage_stack(stage).content
    assert "\nD setup\n" in content


def test_no_deps_no_load_from_yields_bare_d_line() -> None:
    stage = StageSpec(name="setup", steps=("x",))
    content = emit_stage_stack(stage).content
    # bare "D" line followed by newline
    assert "\nD\n" in content


def test_inputs_and_outputs_emit_one_line_each() -> None:
    stage = StageSpec(
        name="run",
        steps=("x",),
        inputs=("a.v", "b.v"),
        outputs=("r.rpt",),
    )
    content = emit_stage_stack(stage).content
    assert "\nI a.v\nI b.v\n" in content
    assert "\nO r.rpt\n" in content


def test_run_mode_parallel_emitted() -> None:
    stage = StageSpec(name="run", steps=("x",), run_mode="parallel")
    content = emit_stage_stack(stage).content
    assert content.rstrip("\n").endswith("R parallel")


def test_full_field_stage_golden_layout() -> None:
    stage = StageSpec(
        name="run_verify",
        steps=("x",),
        load_from="setup",
        command="-tool fm -B BLOCK -T run_verify",
        exit_codes=(0, 3, 5),
        dependencies=("setup",),
        inputs=("$ward/design.v.gz",),
        outputs=("$ward/result.rpt",),
        run_mode="serial",
    )
    assert emit_stage_stack(stage).content == (
        "# Chopper-generated stack: run_verify\n"
        "N run_verify\n"
        "J -tool fm -B BLOCK -T run_verify\n"
        "L 0 3 5\n"
        "D setup\n"
        "I $ward/design.v.gz\n"
        "O $ward/result.rpt\n"
        "R serial\n"
    )
