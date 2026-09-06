"""Adversarial chained-overlay integration tests for F3 ``flow_actions``.

Companion to :mod:`test_cli_chained_overlay` (which tortures F1 / F2
merge corners). This module focuses on the **F3 axis**: every flow-
action variant in the feature-v1 schema and their cross-product with
F1 (FE/FI) and F2 (PE/PI) overlay states.

Each scenario authors a self-describing on-disk domain (base.json
+ N feature jsons + Tcl sources) under ``tmp_path``, drives the real
:class:`~chopper.orchestrator.runner.ChopperRunner` through
``cmd_validate``'s dry-run pipeline, and asserts both the resolved
:attr:`CompiledManifest.stages` tuple and the diagnostic stream
against the spec in ``technical_docs/ARCHITECTURE.md`` Sec.6.6/Sec.6.7 and
``technical_docs/DIAGNOSTIC_CODES.md`` (VE-10 / VE-19 / VE-20).

The actions exercised here are the full union::

    add_step_before, add_step_after
    add_stage_before, add_stage_after
    remove_step, remove_stage
    replace_step, replace_stage
    load_from

The F1/F2 cross-product torture sits in
:mod:`test_cli_chained_overlay`; this file deliberately mirrors that
authoring style (no committed fixtures, every JSON inline) so the
torture corners stay self-contained and grep-able.
"""

from __future__ import annotations

import json
from pathlib import Path

from chopper.adapters import CollectingSink, LocalFS, SilentProgress
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.models_common import FileTreatment
from chopper.core.provenance_markers import marker_pair
from chopper.orchestrator import ChopperRunner

# ---------------------------------------------------------------------------
# Authoring helpers (clone of test_cli_chained_overlay's helpers -- kept
# local so each torture file stays self-contained and inspectable).
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_tcl(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _run_pipeline(
    domain: Path,
    *,
    base: Path,
    features: tuple[Path, ...],
    command: str = "validate",
    dry_run: bool = True,
) -> tuple[CollectingSink, object]:
    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=domain,
        backup_root=domain.with_name(domain.name + "_backup"),
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=dry_run,
        base_path=base,
        feature_paths=features,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=sink, progress=SilentProgress())
    result = ChopperRunner().run(ctx, command=command)
    return sink, result


def _stage_by_name(stages: tuple, name: str):
    for s in stages:
        if s.name == name:
            return s
    return None


def _base_with_main_only(domain: Path) -> Path:
    """Author a minimal base with a single ``main`` stage and one Tcl source."""

    _write_tcl(domain / "src" / "core.tcl", "proc setup {} { return ok }\nproc run {} { return done }\n")
    base = domain / "jsons" / "base.json"
    _write_json(
        base,
        {
            "$schema": "base-v1",
            "domain": domain.name,
            "files": {"include": ["src/core.tcl"]},
            "stages": [
                {
                    "name": "main",
                    "load_from": "",
                    "command": "-T main",
                    "exit_codes": [0],
                    "steps": ["source src/core.tcl", "setup", "run"],
                }
            ],
        },
    )
    return base


# ===========================================================================
# Scenario A1 -- ``add_step_after`` against a unique anchor.
#
# Spec: ARCHITECTURE.md Sec.6.6 / flow_resolver.py module docstring -- the
# new step lands immediately after the named reference step. No VE-10/
# VE-19/VE-20 because the anchor is unique.
# ===========================================================================


def test_add_step_after_unique_anchor_inserts_in_place(tmp_path: Path) -> None:
    domain = tmp_path / "add_step_after"
    domain.mkdir()
    base = _base_with_main_only(domain)
    feat = domain / "jsons" / "features" / "verify.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "verify",
            "flow_actions": [
                {
                    "action": "add_step_after",
                    "stage": "main",
                    "reference": "run",
                    "items": ["verify"],
                }
            ],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))
    codes = [d.code for d in sink.snapshot()]

    assert result.exit_code == 0, f"unexpected non-zero exit; codes={codes}"
    main = _stage_by_name(result.manifest.stages, "main")
    assert main is not None
    begin, end = marker_pair(action="added", kind="step", name="verify", source="feature:verify")
    assert main.steps == ("source src/core.tcl", "setup", "run", begin, "verify", end)


def test_dry_run_validates_generated_tcl_brace_balance(tmp_path: Path) -> None:
    domain = tmp_path / "dry_run_generated_brace_balance"
    domain.mkdir()
    base = _base_with_main_only(domain)
    feat = domain / "jsons" / "features" / "invalid.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "invalid",
            "flow_actions": [
                {
                    "action": "add_step_after",
                    "stage": "main",
                    "reference": "run",
                    "items": ["if {condition} {"],
                }
            ],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,), command="trim")

    assert result.exit_code == 1
    assert "VE-16" in [diagnostic.code for diagnostic in sink.snapshot()]
    assert not (domain / "main.tcl").exists()


# ===========================================================================
# Scenario A2 -- ``add_step_before`` against a unique anchor.
# ===========================================================================


def test_add_step_before_unique_anchor_inserts_in_place(tmp_path: Path) -> None:
    domain = tmp_path / "add_step_before"
    domain.mkdir()
    base = _base_with_main_only(domain)
    feat = domain / "jsons" / "features" / "pre.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "pre",
            "flow_actions": [
                {
                    "action": "add_step_before",
                    "stage": "main",
                    "reference": "run",
                    "items": ["precheck"],
                }
            ],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))
    codes = [d.code for d in sink.snapshot()]

    assert result.exit_code == 0, f"unexpected non-zero exit; codes={codes}"
    main = _stage_by_name(result.manifest.stages, "main")
    assert main is not None
    begin, end = marker_pair(action="added", kind="step", name="precheck", source="feature:pre")
    assert main.steps == ("source src/core.tcl", "setup", begin, "precheck", end, "run")


# ===========================================================================
# Scenario A3 -- Three features each ``add_step_after`` on the same
# anchor. Selected feature order must be preserved verbatim (R1
# ordered overlay for F3, ARCHITECTURE.md Sec.6.7).
# ===========================================================================


def test_add_step_after_same_anchor_three_features_preserve_order(tmp_path: Path) -> None:
    domain = tmp_path / "add_step_after_order"
    domain.mkdir()
    base = _base_with_main_only(domain)

    feats = []
    for name in ("f1", "f2", "f3"):
        feat = domain / "jsons" / "features" / f"{name}.feature.json"
        _write_json(
            feat,
            {
                "$schema": "feature-v1",
                "name": name,
                "flow_actions": [
                    {
                        "action": "add_step_after",
                        "stage": "main",
                        "reference": "run",
                        "items": [f"step_from_{name}"],
                    }
                ],
            },
        )
        feats.append(feat)

    sink, result = _run_pipeline(domain, base=base, features=tuple(feats))
    codes = [d.code for d in sink.snapshot()]

    assert result.exit_code == 0, f"unexpected non-zero exit; codes={codes}"
    main = _stage_by_name(result.manifest.stages, "main")
    assert main is not None
    # f1, f2, f3 must appear in that exact selected order.
    f1_begin, f1_end = marker_pair(action="added", kind="step", name="step_from_f1", source="feature:f1")
    f2_begin, f2_end = marker_pair(action="added", kind="step", name="step_from_f2", source="feature:f2")
    f3_begin, f3_end = marker_pair(action="added", kind="step", name="step_from_f3", source="feature:f3")
    assert main.steps == (
        "source src/core.tcl",
        "setup",
        "run",
        f1_begin,
        "step_from_f1",
        f1_end,
        f2_begin,
        "step_from_f2",
        f2_end,
        f3_begin,
        "step_from_f3",
        f3_end,
    )


# ===========================================================================
# Scenario A4 -- Three features each ``add_step_before`` on the same
# anchor. ``add_step_before`` preserves order naturally because each
# new insertion sits immediately before a shifted anchor.
# ===========================================================================


def test_add_step_before_same_anchor_three_features_preserve_order(tmp_path: Path) -> None:
    domain = tmp_path / "add_step_before_order"
    domain.mkdir()
    base = _base_with_main_only(domain)

    feats = []
    for name in ("f1", "f2", "f3"):
        feat = domain / "jsons" / "features" / f"{name}.feature.json"
        _write_json(
            feat,
            {
                "$schema": "feature-v1",
                "name": name,
                "flow_actions": [
                    {
                        "action": "add_step_before",
                        "stage": "main",
                        "reference": "run",
                        "items": [f"step_from_{name}"],
                    }
                ],
            },
        )
        feats.append(feat)

    sink, result = _run_pipeline(domain, base=base, features=tuple(feats))

    assert result.exit_code == 0
    main = _stage_by_name(result.manifest.stages, "main")
    assert main is not None
    f1_begin, f1_end = marker_pair(action="added", kind="step", name="step_from_f1", source="feature:f1")
    f2_begin, f2_end = marker_pair(action="added", kind="step", name="step_from_f2", source="feature:f2")
    f3_begin, f3_end = marker_pair(action="added", kind="step", name="step_from_f3", source="feature:f3")
    assert main.steps == (
        "source src/core.tcl",
        "setup",
        f1_begin,
        "step_from_f1",
        f1_end,
        f2_begin,
        "step_from_f2",
        f2_end,
        f3_begin,
        "step_from_f3",
        f3_end,
        "run",
    )


# ===========================================================================
# Scenario B1 -- ``add_stage_after`` produces a new GENERATED entry in
# ``file_decisions`` (``<stage>.tcl``) and the new stage shows up at
# the correct position in the resolved stage sequence.
# ===========================================================================


def test_add_stage_after_registers_generated_tcl_and_orders_stage(tmp_path: Path) -> None:
    domain = tmp_path / "add_stage_after"
    domain.mkdir()
    base = _base_with_main_only(domain)
    feat = domain / "jsons" / "features" / "dft.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "dft",
            "flow_actions": [
                {
                    "action": "add_stage_after",
                    "name": "dft_check",
                    "reference": "main",
                    "load_from": "main",
                    "command": "-T dft_check",
                    "exit_codes": [0],
                    "steps": ["check_scan", "report_scan"],
                }
            ],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))
    codes = [d.code for d in sink.snapshot()]

    assert result.exit_code == 0, f"unexpected non-zero exit; codes={codes}"
    names = tuple(s.name for s in result.manifest.stages)
    assert names == ("main", "dft_check"), f"stage order wrong: {names}"
    # GENERATED bucket: dft_check.tcl must be registered.
    assert result.manifest.file_decisions.get(Path("dft_check.tcl")) is FileTreatment.GENERATED


# ===========================================================================
# Scenario B2 -- ``add_stage_before``: same shape, inserted before the
# anchor instead of after.
# ===========================================================================


def test_add_stage_before_inserts_ahead_of_anchor(tmp_path: Path) -> None:
    domain = tmp_path / "add_stage_before"
    domain.mkdir()
    base = _base_with_main_only(domain)
    feat = domain / "jsons" / "features" / "prep.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "prep",
            "flow_actions": [
                {
                    "action": "add_stage_before",
                    "name": "prep",
                    "reference": "main",
                    "load_from": "",
                    "command": "-T prep",
                    "exit_codes": [0],
                    "steps": ["init_env"],
                }
            ],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))

    assert result.exit_code == 0
    names = tuple(s.name for s in result.manifest.stages)
    assert names == ("prep", "main")
    assert result.manifest.file_decisions.get(Path("prep.tcl")) is FileTreatment.GENERATED


# ===========================================================================
# Scenario C -- ``remove_step`` deletes a unique step from a stage.
# ===========================================================================


def test_remove_step_drops_named_step(tmp_path: Path) -> None:
    domain = tmp_path / "remove_step"
    domain.mkdir()
    base = _base_with_main_only(domain)
    feat = domain / "jsons" / "features" / "trim.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "trim",
            "flow_actions": [{"action": "remove_step", "stage": "main", "reference": "setup"}],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))

    assert result.exit_code == 0
    main = _stage_by_name(result.manifest.stages, "main")
    assert main is not None
    begin, end = marker_pair(action="removed", kind="step", name="setup", source="feature:trim")
    assert main.steps == ("source src/core.tcl", begin, end, "run")


# ===========================================================================
# Scenario D -- ``remove_stage`` removes a whole stage and its
# GENERATED ``<stage>.tcl`` entry must NOT be present (because the
# stage is gone from the resolved sequence).
# ===========================================================================


def test_remove_stage_drops_stage_and_no_generated_tcl(tmp_path: Path) -> None:
    domain = tmp_path / "remove_stage"
    domain.mkdir()
    # Base has TWO stages so removing one still leaves a valid pipeline.
    _write_tcl(domain / "src" / "a.tcl", "proc a {} { return 1 }\n")
    base = domain / "jsons" / "base.json"
    _write_json(
        base,
        {
            "$schema": "base-v1",
            "domain": "remove_stage",
            "files": {"include": ["src/a.tcl"]},
            "stages": [
                {"name": "setup", "load_from": "", "command": "-T setup", "exit_codes": [0], "steps": ["a"]},
                # 3.4.0: ``main`` is independent of ``setup`` (no load_from)
                # so removing ``setup`` does not leave a dangling reference.
                {"name": "main", "load_from": "", "command": "-T main", "exit_codes": [0], "steps": ["a"]},
            ],
        },
    )
    feat = domain / "jsons" / "features" / "drop.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "drop",
            "flow_actions": [{"action": "remove_stage", "reference": "setup"}],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))

    assert result.exit_code == 0
    names = tuple(s.name for s in result.manifest.stages)
    assert names == ("main",)
    # setup.tcl GENERATED entry must not exist for a removed stage.
    assert Path("setup.tcl") not in result.manifest.file_decisions


# ===========================================================================
# Scenario E -- ``replace_step`` swaps one step for another.
# ===========================================================================


def test_replace_step_swaps_exact_token(tmp_path: Path) -> None:
    domain = tmp_path / "replace_step"
    domain.mkdir()
    base = _base_with_main_only(domain)
    feat = domain / "jsons" / "features" / "swap.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "swap",
            "flow_actions": [
                {
                    "action": "replace_step",
                    "stage": "main",
                    "reference": "run",
                    "with": "run_fast",
                }
            ],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))

    assert result.exit_code == 0
    main = _stage_by_name(result.manifest.stages, "main")
    assert main is not None
    begin, end = marker_pair(action="replaced", kind="step", name="run_fast", source="feature:swap")
    assert main.steps == ("source src/core.tcl", "setup", begin, "run_fast", end)


# ===========================================================================
# Scenario F -- ``replace_stage`` swaps a whole stage for a new
# definition. When the replacement carries a DIFFERENT name, downstream
# stages that referenced the old name via ``load_from`` must have
# their ``load_from`` rewritten to the new name (flow_resolver.py
# `_apply_replace_stage` rewrite loop).
# ===========================================================================


def test_replace_stage_with_new_name_rewrites_downstream_load_from(tmp_path: Path) -> None:
    domain = tmp_path / "replace_stage"
    domain.mkdir()
    _write_tcl(domain / "src" / "a.tcl", "proc a {} { return 1 }\n")
    base = domain / "jsons" / "base.json"
    _write_json(
        base,
        {
            "$schema": "base-v1",
            "domain": "replace_stage",
            "files": {"include": ["src/a.tcl"]},
            "stages": [
                {"name": "setup", "load_from": "", "command": "-T setup", "exit_codes": [0], "steps": ["a"]},
                {"name": "main", "load_from": "setup", "command": "-T main", "exit_codes": [0], "steps": ["a"]},
            ],
        },
    )
    feat = domain / "jsons" / "features" / "swap.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "swap",
            "flow_actions": [
                {
                    "action": "replace_stage",
                    "reference": "setup",
                    "with": {
                        "name": "init",
                        "load_from": "",
                        "command": "-T init",
                        "exit_codes": [0],
                        "steps": ["a"],
                    },
                }
            ],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))

    assert result.exit_code == 0
    names = tuple(s.name for s in result.manifest.stages)
    assert names == ("init", "main")
    # Downstream ``main`` must have its load_from rewritten setup -> init.
    main = _stage_by_name(result.manifest.stages, "main")
    assert main is not None
    assert main.load_from == "init"


# ===========================================================================
# Scenario G -- ``load_from`` retargets a stage's predecessor.
# ===========================================================================


def test_load_from_retargets_predecessor(tmp_path: Path) -> None:
    domain = tmp_path / "load_from"
    domain.mkdir()
    _write_tcl(domain / "src" / "a.tcl", "proc a {} { return 1 }\n")
    base = domain / "jsons" / "base.json"
    _write_json(
        base,
        {
            "$schema": "base-v1",
            "domain": "load_from",
            "files": {"include": ["src/a.tcl"]},
            "stages": [
                {"name": "setup", "load_from": "", "command": "-T setup", "exit_codes": [0], "steps": ["a"]},
                {"name": "alt", "load_from": "", "command": "-T alt", "exit_codes": [0], "steps": ["a"]},
                {"name": "main", "load_from": "setup", "command": "-T main", "exit_codes": [0], "steps": ["a"]},
            ],
        },
    )
    feat = domain / "jsons" / "features" / "retarget.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "retarget",
            "flow_actions": [{"action": "load_from", "stage": "main", "reference": "alt"}],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))

    assert result.exit_code == 0
    main = _stage_by_name(result.manifest.stages, "main")
    assert main is not None
    assert main.load_from == "alt"


# ===========================================================================
# Scenario H -- ``add_step_after`` with @n instance targeting on a
# step token that appears multiple times. Spec: flow_resolver.py
# module docstring + DIAGNOSTIC_CODES.md (VE-10/VE-19/VE-20 only fire
# on out-of-range / ambiguous cases). @2 of a 2-occurrence step is
# valid and resolves to the second occurrence.
# ===========================================================================


def test_add_step_after_with_at_n_instance_targeting(tmp_path: Path) -> None:
    domain = tmp_path / "at_n"
    domain.mkdir()
    _write_tcl(domain / "src" / "x.tcl", "proc x {} { return 1 }\n")
    base = domain / "jsons" / "base.json"
    _write_json(
        base,
        {
            "$schema": "base-v1",
            "domain": "at_n",
            "files": {"include": ["src/x.tcl"]},
            "stages": [
                {
                    "name": "main",
                    "load_from": "",
                    "command": "-T main",
                    "exit_codes": [0],
                    # "x" appears twice -- disambiguation via @n.
                    "steps": ["x", "y", "x"],
                }
            ],
        },
    )
    feat = domain / "jsons" / "features" / "tag.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "tag",
            "flow_actions": [
                {
                    "action": "add_step_after",
                    "stage": "main",
                    "reference": "x@2",
                    "items": ["after_second_x"],
                }
            ],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))
    codes = [d.code for d in sink.snapshot()]

    assert result.exit_code == 0, f"unexpected non-zero exit; codes={codes}"
    main = _stage_by_name(result.manifest.stages, "main")
    assert main is not None
    begin, end = marker_pair(action="added", kind="step", name="after_second_x", source="feature:tag")
    assert main.steps == ("x", "y", "x", begin, "after_second_x", end)
    # Must NOT emit VE-20 (suffix disambiguates).
    assert "VE-20" not in codes


# ===========================================================================
# Scenario I -- VE-20 ``ambiguous-step-target``: feature uses a step
# reference with no @n on a step that appears multiple times.
# ===========================================================================


def test_ambiguous_step_target_emits_ve20(tmp_path: Path) -> None:
    domain = tmp_path / "ve20"
    domain.mkdir()
    _write_tcl(domain / "src" / "x.tcl", "proc x {} { return 1 }\n")
    base = domain / "jsons" / "base.json"
    _write_json(
        base,
        {
            "$schema": "base-v1",
            "domain": "ve20",
            "files": {"include": ["src/x.tcl"]},
            "stages": [
                {
                    "name": "main",
                    "load_from": "",
                    "command": "-T main",
                    "exit_codes": [0],
                    "steps": ["x", "x"],
                }
            ],
        },
    )
    feat = domain / "jsons" / "features" / "amb.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "amb",
            "flow_actions": [{"action": "add_step_after", "stage": "main", "reference": "x", "items": ["after_x"]}],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))
    codes = [d.code for d in sink.snapshot()]

    assert "VE-20" in codes, f"expected VE-20 ambiguous-step-target; got {codes}"
    assert result.exit_code == 1


# ===========================================================================
# Scenario J -- VE-10 ``occurrence-suffix-overflow``: @n with n above
# the match count.
# ===========================================================================


def test_at_n_overflow_emits_ve10(tmp_path: Path) -> None:
    domain = tmp_path / "ve10"
    domain.mkdir()
    _write_tcl(domain / "src" / "x.tcl", "proc x {} { return 1 }\n")
    base = domain / "jsons" / "base.json"
    _write_json(
        base,
        {
            "$schema": "base-v1",
            "domain": "ve10",
            "files": {"include": ["src/x.tcl"]},
            "stages": [
                {
                    "name": "main",
                    "load_from": "",
                    "command": "-T main",
                    "exit_codes": [0],
                    "steps": ["x"],
                }
            ],
        },
    )
    feat = domain / "jsons" / "features" / "overflow.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "overflow",
            "flow_actions": [{"action": "add_step_after", "stage": "main", "reference": "x@5", "items": ["never"]}],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))
    codes = [d.code for d in sink.snapshot()]

    assert "VE-10" in codes, f"expected VE-10 overflow; got {codes}"
    assert result.exit_code == 1


# ===========================================================================
# Scenario K -- F3 generated path collides with an explicit
# ``files.include`` literal. ARCHITECTURE.md / merge_service.py
# `_register_generated_stage_files` mandates a :class:`ChopperError`
# which the runner maps to exit 3 + internal-error.log.
#
# Authoring rule (memory invariant): "A path emitted by F3 must NOT
# also appear in files.include."
# ===========================================================================


def test_f3_generated_collides_with_fi_literal_exits_3(tmp_path: Path) -> None:
    domain = tmp_path / "f3_collision"
    domain.mkdir()
    # Pre-existing ``dft_check.tcl`` lives on disk AND is FI-included.
    # The feature also tries to add a stage named ``dft_check`` which
    # would emit ``dft_check.tcl`` as a GENERATED path.
    _write_tcl(domain / "dft_check.tcl", "# pre-existing\n")
    _write_tcl(domain / "src" / "core.tcl", "proc r {} { return 1 }\n")
    base = domain / "jsons" / "base.json"
    _write_json(
        base,
        {
            "$schema": "base-v1",
            "domain": "f3_collision",
            "files": {"include": ["src/core.tcl", "dft_check.tcl"]},
            "stages": [
                {"name": "main", "load_from": "", "command": "-T main", "exit_codes": [0], "steps": ["r"]},
            ],
        },
    )
    feat = domain / "jsons" / "features" / "dft.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "dft",
            "flow_actions": [
                {
                    "action": "add_stage_after",
                    "name": "dft_check",
                    "reference": "main",
                    "load_from": "main",
                    "command": "-T dft_check",
                    "exit_codes": [0],
                    "steps": ["r"],
                }
            ],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))

    # ChopperError -> exit 3 + internal_error populated.
    assert result.exit_code == 3, f"expected ChopperError-mapped exit 3 for F3/FI collision; got {result.exit_code}"
    assert result.internal_error is not None


# ===========================================================================
# Scenario L -- Cross-product torture: feature A adds a stage AFTER
# main; feature B then REMOVES the stage A just added. The net effect
# is that the resolved stage sequence equals the base sequence.
# Order matters: features run in selected order.
# ===========================================================================


def test_add_then_remove_same_stage_net_zero(tmp_path: Path) -> None:
    domain = tmp_path / "add_then_remove"
    domain.mkdir()
    base = _base_with_main_only(domain)
    fa = domain / "jsons" / "features" / "a.feature.json"
    fb = domain / "jsons" / "features" / "b.feature.json"
    _write_json(
        fa,
        {
            "$schema": "feature-v1",
            "name": "a",
            "flow_actions": [
                {
                    "action": "add_stage_after",
                    "name": "extra",
                    "reference": "main",
                    "load_from": "main",
                    "command": "-T extra",
                    "exit_codes": [0],
                    "steps": ["nop"],
                }
            ],
        },
    )
    _write_json(
        fb,
        {
            "$schema": "feature-v1",
            "name": "b",
            "flow_actions": [{"action": "remove_stage", "reference": "extra"}],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(fa, fb))

    assert result.exit_code == 0
    names = tuple(s.name for s in result.manifest.stages)
    assert names == ("main",), f"expected only base stage to survive; got {names}"
    # No GENERATED .tcl for ``extra`` because the stage no longer
    # exists at register time.
    assert Path("extra.tcl") not in result.manifest.file_decisions


# ===========================================================================
# Scenario M -- Cross-axis torture: feature A adds a new stage whose
# steps "source" a file the SAME feature `files.include`s; feature B
# then `files.exclude`s that file (FE in a later layer). The stage
# survives (F3 is independent of F1) but the FE downgrades F1 to
# REMOVE -- emitting VW-21 ``downgrade-whole-to-remove`` per R1 row 4.
# ===========================================================================


def test_action_plus_fe_in_later_layer_downgrades_f1_with_vw21(tmp_path: Path) -> None:
    domain = tmp_path / "action_plus_fe"
    domain.mkdir()
    _write_tcl(domain / "src" / "lib.tcl", "proc h {} { return 1 }\n")
    _write_tcl(domain / "src" / "core.tcl", "proc setup {} { }\nproc run {} { }\n")
    base = domain / "jsons" / "base.json"
    _write_json(
        base,
        {
            "$schema": "base-v1",
            "domain": "action_plus_fe",
            "files": {"include": ["src/core.tcl"]},
            "stages": [
                {"name": "main", "load_from": "", "command": "-T main", "exit_codes": [0], "steps": ["setup", "run"]},
            ],
        },
    )
    fa = domain / "jsons" / "features" / "a.feature.json"
    fb = domain / "jsons" / "features" / "b.feature.json"
    _write_json(
        fa,
        {
            "$schema": "feature-v1",
            "name": "a",
            "files": {"include": ["src/lib.tcl"]},
            "flow_actions": [
                {
                    "action": "add_stage_after",
                    "name": "extra",
                    "reference": "main",
                    "load_from": "main",
                    "command": "-T extra",
                    "exit_codes": [0],
                    "steps": ["source src/lib.tcl", "h"],
                }
            ],
        },
    )
    _write_json(
        fb,
        {
            "$schema": "feature-v1",
            "name": "b",
            "files": {"exclude": ["src/lib.tcl"]},
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(fa, fb))
    codes = [d.code for d in sink.snapshot()]

    # Stage still resolves -- F3 is independent of F1.
    assert result.exit_code == 0
    names = tuple(s.name for s in result.manifest.stages)
    assert "extra" in names
    # F1 final treatment for src/lib.tcl is REMOVE (FE in later layer).
    assert result.manifest.file_decisions.get(Path("src/lib.tcl"), FileTreatment.REMOVE) is FileTreatment.REMOVE
    # VW-21 must fire for the lib.tcl downgrade.
    vw21 = [d for d in sink.snapshot() if d.code == "VW-21" and d.path == Path("src/lib.tcl")]
    assert vw21, f"expected VW-21 on src/lib.tcl FE shadow; codes={codes}"


# ===========================================================================
# Scenario N -- Cross-axis torture: feature A adds a stage whose step
# calls a proc; feature B then PE-removes that proc from its source
# file. Stage definition is byte-stable (F3 step strings are opaque to
# F2). The proc is dropped from the trimmed output. No diagnostic
# couples the two axes -- F3 does not "know" about F2 by design.
# ===========================================================================


def test_action_step_references_pe_dropped_proc_stages_unchanged(tmp_path: Path) -> None:
    domain = tmp_path / "action_plus_pe"
    domain.mkdir()
    _write_tcl(
        domain / "src" / "lib.tcl",
        "proc helper_a {} { return 1 }\nproc helper_b {} { return 2 }\n",
    )
    base = domain / "jsons" / "base.json"
    _write_json(
        base,
        {
            "$schema": "base-v1",
            "domain": "action_plus_pe",
            "files": {"include": ["src/lib.tcl"]},
            "stages": [
                {
                    "name": "main",
                    "load_from": "",
                    "command": "-T main",
                    "exit_codes": [0],
                    "steps": ["source src/lib.tcl", "helper_a", "helper_b"],
                },
            ],
        },
    )
    feat = domain / "jsons" / "features" / "drop_b.feature.json"
    _write_json(
        feat,
        {
            "$schema": "feature-v1",
            "name": "drop_b",
            "procedures": {"exclude": [{"file": "src/lib.tcl", "procs": ["helper_b"]}]},
            "flow_actions": [
                {
                    "action": "add_step_after",
                    "stage": "main",
                    "reference": "helper_b",
                    "items": ["echo done"],
                }
            ],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(feat,))

    assert result.exit_code == 0
    # Stage steps are byte-stable: F3 keeps "helper_b" + "echo done" in order.
    main = _stage_by_name(result.manifest.stages, "main")
    assert main is not None
    begin, end = marker_pair(action="added", kind="step", name="echo done", source="feature:drop_b")
    assert main.steps == ("source src/lib.tcl", "helper_a", "helper_b", begin, "echo done", end)
    # F2: lib.tcl was demoted from FULL_COPY to PROC_TRIM by the PE.
    assert result.manifest.file_decisions.get(Path("src/lib.tcl")) is FileTreatment.PROC_TRIM
    survivors = {
        d.canonical_name.split("::", 1)[1]
        for d in result.manifest.proc_decisions.values()
        if d.source_file == Path("src/lib.tcl")
    }
    assert survivors == {"helper_a"}, f"expected helper_a kept, helper_b dropped; got {survivors}"


# ===========================================================================
# Scenario O -- Chained replace_step: feature A replaces "run" -> "run1";
# feature B then replaces "run1" -> "run2". Last layer wins.
# ===========================================================================


def test_chained_replace_step_last_layer_wins(tmp_path: Path) -> None:
    domain = tmp_path / "chained_replace"
    domain.mkdir()
    base = _base_with_main_only(domain)
    fa = domain / "jsons" / "features" / "a.feature.json"
    fb = domain / "jsons" / "features" / "b.feature.json"
    _write_json(
        fa,
        {
            "$schema": "feature-v1",
            "name": "a",
            "flow_actions": [{"action": "replace_step", "stage": "main", "reference": "run", "with": "run1"}],
        },
    )
    _write_json(
        fb,
        {
            "$schema": "feature-v1",
            "name": "b",
            "flow_actions": [{"action": "replace_step", "stage": "main", "reference": "run1", "with": "run2"}],
        },
    )

    sink, result = _run_pipeline(domain, base=base, features=(fa, fb))

    assert result.exit_code == 0
    main = _stage_by_name(result.manifest.stages, "main")
    assert main is not None
    begin, end = marker_pair(action="replaced", kind="step", name="run2", source="feature:b")
    assert main.steps == ("source src/core.tcl", "setup", begin, "run2", end)
