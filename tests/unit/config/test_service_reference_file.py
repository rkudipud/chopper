"""Unit tests for stage ``reference_file`` resolution in :mod:`chopper.config.service`.

Covers the full failure-mode matrix for FR-55 / ``VE-39``: line-ending
normalization (CRLF / bare CR / LF), blank/comment-line preservation, empty
and missing files, non-UTF-8 content, Case 2 re-trim backup-root reads, and
all three authoring surfaces (base ``stages[]``, feature
``add_stage_before``/``add_stage_after``, feature ``replace_stage.with``).

``InMemoryFS``/``_InMemoryFS`` test doubles return stored strings verbatim
and do not simulate real byte-level decoding (no universal-newline
translation, no BOM stripping) -- that is deliberate: it proves the
line-splitting logic in ``_materialize_stage_steps`` is correct on its own
terms, independent of what a given filesystem adapter does upstream. The
BOM-stripping and true-UTF-8-decode-failure tests at the bottom use a real
``LocalFS`` against ``tmp_path`` instead, because that behavior lives in
Python's own codec layer, not in Chopper's code.
"""

from __future__ import annotations

import json
from pathlib import Path

from chopper.adapters.fs_local import LocalFS
from chopper.config.service import ConfigService
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.models_common import DomainState

from .test_service import _BACKUP, _DOMAIN, _CollectingSink, _default_state, _InMemoryFS, _make_ctx, _NullProgress

# ---------------------------------------------------------------------------
# Base stages[] -- happy paths and line-ending / content edge cases
# ---------------------------------------------------------------------------


def _base_with_reference_file(reference_file: str = "scripts/setup.steps") -> str:
    return json.dumps(
        {
            "$schema": "base-v1",
            "domain": "my_domain",
            "stages": [{"name": "setup", "load_from": "", "reference_file": reference_file}],
        }
    )


class TestBaseStageReferenceFileHappyPath:
    def test_simple_multiline_file_becomes_steps(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ref_path = _DOMAIN / "scripts/setup.steps"
        ctx, sink = _make_ctx(
            {base_path: _base_with_reference_file(), ref_path: "source a.tcl\nsource b.tcl\n"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        assert result.base.stages[0].steps == ("source a.tcl", "source b.tcl")

    def test_reference_file_recorded_as_provenance(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ref_path = _DOMAIN / "scripts/setup.steps"
        ctx, _ = _make_ctx(
            {base_path: _base_with_reference_file(), ref_path: "source a.tcl\n"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert result.base.stages[0].reference_file == "scripts/setup.steps"

    def test_crlf_line_endings_normalized(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ref_path = _DOMAIN / "scripts/setup.steps"
        ctx, sink = _make_ctx(
            {base_path: _base_with_reference_file(), ref_path: "source a.tcl\r\nsource b.tcl\r\n"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        assert result.base.stages[0].steps == ("source a.tcl", "source b.tcl")

    def test_bare_cr_legacy_mac_line_endings_normalized(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ref_path = _DOMAIN / "scripts/setup.steps"
        ctx, _ = _make_ctx(
            {base_path: _base_with_reference_file(), ref_path: "source a.tcl\rsource b.tcl\r"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert result.base.stages[0].steps == ("source a.tcl", "source b.tcl")

    def test_mixed_line_endings_normalized(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ref_path = _DOMAIN / "scripts/setup.steps"
        ctx, _ = _make_ctx(
            {base_path: _base_with_reference_file(), ref_path: "a\r\nb\nc\r"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert result.base.stages[0].steps == ("a", "b", "c")

    def test_trailing_newline_does_not_add_phantom_step(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ref_path = _DOMAIN / "scripts/setup.steps"
        ctx, _ = _make_ctx(
            {base_path: _base_with_reference_file(), ref_path: "only_line.tcl\n"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert result.base.stages[0].steps == ("only_line.tcl",)

    def test_blank_and_comment_lines_preserved_verbatim(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ref_path = _DOMAIN / "scripts/setup.steps"
        content = "source a.tcl\n\n# separator comment\n\nsource b.tcl\n"
        ctx, _ = _make_ctx(
            {base_path: _base_with_reference_file(), ref_path: content},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert result.base.stages[0].steps == (
            "source a.tcl",
            "",
            "# separator comment",
            "",
            "source b.tcl",
        )

    def test_file_of_only_blank_lines_is_not_treated_as_empty(self) -> None:
        """0 lines is empty (VE-39); N blank-string lines is not."""
        base_path = _DOMAIN / "jsons/base.json"
        ref_path = _DOMAIN / "scripts/setup.steps"
        ctx, sink = _make_ctx(
            {base_path: _base_with_reference_file(), ref_path: "\n\n\n"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        assert result.base.stages[0].steps == ("", "", "")


# ---------------------------------------------------------------------------
# Failure modes -- VE-39
# ---------------------------------------------------------------------------


class TestReferenceFileVE39:
    def test_missing_file_emits_ve39(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ctx, sink = _make_ctx({base_path: _base_with_reference_file()}, base_path=base_path)
        result = ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-39" for d in sink.emissions)
        assert result.base.stages == ()  # load aborted -> _empty_config()

    def test_empty_file_emits_ve39(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ref_path = _DOMAIN / "scripts/setup.steps"
        ctx, sink = _make_ctx(
            {base_path: _base_with_reference_file(), ref_path: ""},
            base_path=base_path,
        )
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-39" for d in sink.emissions)

    def test_unreadable_file_emits_ve39(self) -> None:
        class _DenyRead(_InMemoryFS):
            def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
                if path == _DOMAIN / "scripts/setup.steps":
                    raise OSError("permission denied")
                return super().read_text(path, encoding=encoding)

        base_path = _DOMAIN / "jsons/base.json"
        cfg = RunConfig(
            domain_root=_DOMAIN,
            backup_root=_BACKUP,
            audit_root=_DOMAIN / ".chopper",
            strict=False,
            dry_run=False,
            base_path=base_path,
        )
        sink = _CollectingSink()
        fs = _DenyRead({base_path: _base_with_reference_file()})
        ctx = ChopperContext(config=cfg, fs=fs, diag=sink, progress=_NullProgress())
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-39" for d in sink.emissions)

    def test_undecodable_content_emits_ve39(self) -> None:
        class _BadDecode(_InMemoryFS):
            def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
                if path == _DOMAIN / "scripts/setup.steps":
                    raise UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1, "invalid start byte")
                return super().read_text(path, encoding=encoding)

        base_path = _DOMAIN / "jsons/base.json"
        cfg = RunConfig(
            domain_root=_DOMAIN,
            backup_root=_BACKUP,
            audit_root=_DOMAIN / ".chopper",
            strict=False,
            dry_run=False,
            base_path=base_path,
        )
        sink = _CollectingSink()
        fs = _BadDecode({base_path: _base_with_reference_file()})
        ctx = ChopperContext(config=cfg, fs=fs, diag=sink, progress=_NullProgress())
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-39" for d in sink.emissions)


# ---------------------------------------------------------------------------
# Case 2 re-trim -- must read from backup_root, not domain_root
# ---------------------------------------------------------------------------


class TestReferenceFileBackupRootAware:
    def test_case2_retrim_reads_reference_file_from_backup_root(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        # Only the backup copy holds the pristine reference file; the live
        # domain copy (if any) must NOT be consulted on a Case 2 re-trim.
        backup_ref_path = _BACKUP / "scripts/setup.steps"
        ctx, sink = _make_ctx(
            {base_path: _base_with_reference_file(), backup_ref_path: "pristine_step.tcl\n"},
            base_path=base_path,
        )
        state = DomainState(case=2, domain_exists=True, backup_exists=True, hand_edited=False)
        result = ConfigService().run(ctx, state)
        assert sink.emissions == []
        assert result.base.stages[0].steps == ("pristine_step.tcl",)

    def test_case1_first_trim_reads_reference_file_from_domain_root(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ref_path = _DOMAIN / "scripts/setup.steps"
        ctx, sink = _make_ctx(
            {base_path: _base_with_reference_file(), ref_path: "domain_step.tcl\n"},
            base_path=base_path,
        )
        state = DomainState(case=1, domain_exists=True, backup_exists=False, hand_edited=False)
        result = ConfigService().run(ctx, state)
        assert sink.emissions == []
        assert result.base.stages[0].steps == ("domain_step.tcl",)


# ---------------------------------------------------------------------------
# Feature flow_actions -- add_stage_before/after and replace_stage.with
# ---------------------------------------------------------------------------


class TestFeatureFlowActionReferenceFile:
    def test_add_stage_after_resolves_reference_file(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        ref_path = _DOMAIN / "scripts/dft_check.steps"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["source main.tcl"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [
                    {
                        "action": "add_stage_after",
                        "name": "dft_check",
                        "reference": "main",
                        "load_from": "main",
                        "reference_file": "scripts/dft_check.steps",
                    }
                ],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, feat_path: feat_raw, ref_path: "run_scan\nrun_atpg\n"},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        action = result.features[0].flow_actions[0]
        assert action.stage.steps == ("run_scan", "run_atpg")
        assert action.stage.reference_file == "scripts/dft_check.steps"

    def test_replace_stage_with_resolves_reference_file(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        ref_path = _DOMAIN / "scripts/new_main.steps"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["source old_main.tcl"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [
                    {
                        "action": "replace_stage",
                        "reference": "main",
                        "with": {"name": "main", "load_from": "", "reference_file": "scripts/new_main.steps"},
                    }
                ],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, feat_path: feat_raw, ref_path: "source new_main.tcl\n"},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        action = result.features[0].flow_actions[0]
        assert action.replacement.steps == ("source new_main.tcl",)

    def test_replace_stage_missing_reference_file_emits_ve39(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["source old_main.tcl"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [
                    {
                        "action": "replace_stage",
                        "reference": "main",
                        "with": {"name": "main", "load_from": "", "reference_file": "scripts/missing.steps"},
                    }
                ],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, feat_path: feat_raw},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-39" for d in sink.emissions)

    def test_missing_reference_file_in_feature_flow_action_emits_ve39(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["source main.tcl"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [
                    {
                        "action": "add_stage_after",
                        "name": "dft_check",
                        "reference": "main",
                        "load_from": "main",
                        "reference_file": "scripts/missing.steps",
                    }
                ],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, feat_path: feat_raw},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-39" for d in sink.emissions)

    def test_non_stage_flow_action_is_passed_through_untouched(self) -> None:
        """``remove_step`` (and every other non-stage-creating action) never
        touches ``reference_file`` resolution -- it must pass through the
        materialization walk unchanged."""
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["source main.tcl"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [{"action": "remove_step", "stage": "main", "reference": "source main.tcl"}],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, feat_path: feat_raw},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        assert result.features[0].flow_actions[0].reference == "source main.tcl"


def test_two_stages_sharing_one_reference_file_resolve_independently() -> None:
    base_path = _DOMAIN / "jsons/base.json"
    ref_path = _DOMAIN / "scripts/shared.steps"
    base_raw = json.dumps(
        {
            "$schema": "base-v1",
            "domain": "my_domain",
            "stages": [
                {"name": "a", "load_from": "", "reference_file": "scripts/shared.steps"},
                {"name": "b", "load_from": "a", "reference_file": "scripts/shared.steps"},
            ],
        }
    )
    ctx, sink = _make_ctx(
        {base_path: base_raw, ref_path: "shared_step_one\nshared_step_two\n"},
        base_path=base_path,
    )
    result = ConfigService().run(ctx, _default_state())
    assert sink.emissions == []
    assert result.base.stages[0].steps == result.base.stages[1].steps == ("shared_step_one", "shared_step_two")
    assert result.base.stages[0] is not result.base.stages[1]


# ---------------------------------------------------------------------------
# Real filesystem -- BOM stripping and genuine UTF-8 decode failure.
#
# InMemoryFS doubles return stored strings verbatim (no byte-level decode
# simulation), so BOM-stripping and real UnicodeDecodeError behavior can
# only be proven against the actual LocalFS adapter over real files.
# ---------------------------------------------------------------------------


class TestRealFilesystemEncoding:
    def test_bom_prefixed_utf8_file_is_stripped(self, tmp_path: Path) -> None:
        domain = tmp_path / "my_domain"
        domain.mkdir()
        (domain / "scripts").mkdir()
        base_path = domain / "jsons" / "base.json"
        base_path.parent.mkdir(parents=True)
        base_path.write_text(_base_with_reference_file(), encoding="utf-8")
        ref_path = domain / "scripts" / "setup.steps"
        # Real UTF-8 BOM byte sequence + CRLF line endings, written as raw bytes.
        ref_path.write_bytes(b"\xef\xbb\xbfsource a.tcl\r\nsource b.tcl\r\n")

        cfg = RunConfig(
            domain_root=domain,
            backup_root=domain.parent / "my_domain_backup",
            audit_root=domain / ".chopper",
            strict=False,
            dry_run=False,
            base_path=base_path,
        )
        sink = _CollectingSink()
        ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=sink, progress=_NullProgress())
        result = ConfigService().run(ctx, _default_state())

        assert sink.emissions == []
        steps = result.base.stages[0].steps
        assert steps == ("source a.tcl", "source b.tcl")
        assert not steps[0].startswith("\ufeff")

    def test_non_utf8_bytes_emit_ve39(self, tmp_path: Path) -> None:
        domain = tmp_path / "my_domain"
        domain.mkdir()
        (domain / "scripts").mkdir()
        base_path = domain / "jsons" / "base.json"
        base_path.parent.mkdir(parents=True)
        base_path.write_text(_base_with_reference_file(), encoding="utf-8")
        ref_path = domain / "scripts" / "setup.steps"
        # Latin-1 byte 0xE9 ('e' with acute) is not valid standalone UTF-8.
        ref_path.write_bytes(b"source a.tcl\n\xe9invalid\n")

        cfg = RunConfig(
            domain_root=domain,
            backup_root=domain.parent / "my_domain_backup",
            audit_root=domain / ".chopper",
            strict=False,
            dry_run=False,
            base_path=base_path,
        )
        sink = _CollectingSink()
        ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=sink, progress=_NullProgress())
        ConfigService().run(ctx, _default_state())

        assert any(d.code == "VE-39" for d in sink.emissions)


# ---------------------------------------------------------------------------
# Mixed formats -- inline steps and reference_file coexisting.
#
# This is the realistic scenario the feature exists for (issue #28): a
# domain migrates incrementally, so some stages stay JSON-native (``steps``)
# while others point at an existing hand-maintained script file
# (``reference_file``). Both must resolve independently and correctly in
# the same document, and a failure in one must not silently corrupt or
# skip the others.
# ---------------------------------------------------------------------------


class TestMixedStageFormats:
    def test_inline_and_reference_file_stages_both_resolve_correctly(self) -> None:
        """Positive: 3 stages -- inline, reference_file, inline -- each
        resolve independently with correct provenance."""
        base_path = _DOMAIN / "jsons/base.json"
        ref_path = _DOMAIN / "scripts/synth.steps"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [
                    {"name": "setup", "load_from": "", "steps": ["source setup.tcl"]},
                    {"name": "synth", "load_from": "setup", "reference_file": "scripts/synth.steps"},
                    {"name": "report", "load_from": "synth", "steps": ["emit_reports"]},
                ],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, ref_path: "run_synth\nsource synth_opts.tcl\n"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        setup, synth, report = result.base.stages
        assert setup.steps == ("source setup.tcl",)
        assert setup.reference_file is None
        assert synth.steps == ("run_synth", "source synth_opts.tcl")
        assert synth.reference_file == "scripts/synth.steps"
        assert report.steps == ("emit_reports",)
        assert report.reference_file is None

    def test_bad_reference_file_among_mixed_stages_aborts_whole_base_load(self) -> None:
        """Negative: with 3 mixed stages, a missing reference_file on the
        *middle* stage still emits VE-39 and aborts the entire base load --
        there is no partial success where the two inline stages load anyway.
        """
        base_path = _DOMAIN / "jsons/base.json"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [
                    {"name": "setup", "load_from": "", "steps": ["source setup.tcl"]},
                    {"name": "synth", "load_from": "setup", "reference_file": "scripts/missing.steps"},
                    {"name": "report", "load_from": "synth", "steps": ["emit_reports"]},
                ],
            }
        )
        ctx, sink = _make_ctx({base_path: base_raw}, base_path=base_path)
        result = ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-39" for d in sink.emissions)
        assert result.base.stages == ()

    def test_project_mode_resolves_mixed_stage_formats(self) -> None:
        """Positive, ``--project`` mode: base has an inline stage, the
        selected feature adds a reference_file stage -- both resolve the
        same as direct ``--base``/``--features`` mode."""
        proj_path = _DOMAIN / "project.json"
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        ref_path = _DOMAIN / "scripts/dft_check.steps"
        proj_raw = json.dumps(
            {
                "$schema": "project-v1",
                "project": "PROJ",
                "domain": "my_domain",
                "base": "jsons/base.json",
                "features": ["jsons/features/dft.json"],
            }
        )
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["source main.tcl"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [
                    {
                        "action": "add_stage_after",
                        "name": "dft_check",
                        "reference": "main",
                        "load_from": "main",
                        "reference_file": "scripts/dft_check.steps",
                    }
                ],
            }
        )
        ctx, sink = _make_ctx(
            {proj_path: proj_raw, base_path: base_raw, feat_path: feat_raw, ref_path: "run_scan\n"},
            project_path=proj_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        assert result.project is not None
        assert result.base.stages[0].steps == ("source main.tcl",)
        assert result.features[0].flow_actions[0].stage.steps == ("run_scan",)

    def test_feature_mixes_reference_file_stage_with_plain_step_modification(self) -> None:
        """Positive, end-to-end through P1 load *and* P3 flow resolution:
        one feature's ``flow_actions`` contains both a reference_file-backed
        ``add_stage_after`` and an unrelated ``remove_step`` targeting a base
        inline stage. Both must apply -- reference_file resolution must not
        short-circuit or interfere with a sibling non-stage action."""
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        ref_path = _DOMAIN / "scripts/dft_check.steps"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["source main.tcl", "debug_hook"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [
                    {"action": "remove_step", "stage": "main", "reference": "debug_hook"},
                    {
                        "action": "add_stage_after",
                        "name": "dft_check",
                        "reference": "main",
                        "load_from": "main",
                        "reference_file": "scripts/dft_check.steps",
                    },
                ],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, feat_path: feat_raw, ref_path: "run_scan\n"},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []

        from chopper.compiler.flow_resolver import resolve_stages

        resolved = resolve_stages(ctx, result.base.stages, result.features)
        by_name = {s.name: s for s in resolved}
        # Sec.3.11: remove_step wraps the removed line in BEGIN/END provenance
        # markers rather than silently deleting it -- "debug_hook" itself no
        # longer appears as a literal step, but the marker names it.
        assert "source main.tcl" in by_name["main"].steps
        assert "debug_hook" not in by_name["main"].steps
        assert any("debug_hook" in s and "removed step" in s for s in by_name["main"].steps)
        # Sec.3.11 also wraps an entirely *added* stage's steps in BEGIN/END
        # markers -- file-sourced steps get exactly the same treatment as
        # inline-authored ones would, proving indistinguishability downstream.
        assert "run_scan" in by_name["dft_check"].steps
        assert any("dft_check" in s and "added stage" in s for s in by_name["dft_check"].steps)
        assert by_name["dft_check"].reference_file == "scripts/dft_check.steps"


# ---------------------------------------------------------------------------
# add_step_before / add_step_after -- reference_file for anchor-injected
# blocks (4.8.0 extension of the same mechanism to step-level injection).
# ---------------------------------------------------------------------------


class TestAddStepActionReferenceFile:
    def test_add_step_after_resolves_items_from_reference_file(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        ref_path = _DOMAIN / "scripts/scan_block.steps"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["setup", "run"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [
                    {
                        "action": "add_step_after",
                        "stage": "main",
                        "reference": "run",
                        "reference_file": "scripts/scan_block.steps",
                    }
                ],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, feat_path: feat_raw, ref_path: "run_scan\n\n# post-scan check\nverify_scan\n"},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        action = result.features[0].flow_actions[0]
        assert action.items == ("run_scan", "", "# post-scan check", "verify_scan")
        assert action.reference_file == "scripts/scan_block.steps"

    def test_add_step_before_resolves_items_from_reference_file(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        ref_path = _DOMAIN / "scripts/pre_block.steps"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["setup", "run"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [
                    {
                        "action": "add_step_before",
                        "stage": "main",
                        "reference": "run",
                        "reference_file": "scripts/pre_block.steps",
                    }
                ],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, feat_path: feat_raw, ref_path: "prep_scan\r\ncheck_scan_ready\r\n"},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        action = result.features[0].flow_actions[0]
        assert action.items == ("prep_scan", "check_scan_ready")

    def test_add_step_after_reference_file_end_to_end_through_resolution(self) -> None:
        """The injected block actually lands at the anchor after P3 flow
        resolution -- not just at the P1 load layer."""
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        ref_path = _DOMAIN / "scripts/scan_block.steps"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["setup", "run"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [
                    {
                        "action": "add_step_after",
                        "stage": "main",
                        "reference": "run",
                        "reference_file": "scripts/scan_block.steps",
                    }
                ],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, feat_path: feat_raw, ref_path: "run_scan\nverify_scan\n"},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []

        from chopper.compiler.flow_resolver import resolve_stages

        resolved = resolve_stages(ctx, result.base.stages, result.features)
        main = next(s for s in resolved if s.name == "main")
        assert "setup" in main.steps
        assert "run" in main.steps
        assert "run_scan" in main.steps
        assert "verify_scan" in main.steps
        assert main.steps.index("run") < main.steps.index("run_scan") < main.steps.index("verify_scan")

    def test_add_step_after_missing_reference_file_emits_ve39(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["setup", "run"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [
                    {
                        "action": "add_step_after",
                        "stage": "main",
                        "reference": "run",
                        "reference_file": "scripts/missing.steps",
                    }
                ],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, feat_path: feat_raw},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-39" for d in sink.emissions)

    def test_items_and_reference_file_coexist_across_sibling_actions(self) -> None:
        """Mixed positive: one add_step_after uses inline items, another
        (different anchor, same feature) uses reference_file -- both apply."""
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        ref_path = _DOMAIN / "scripts/scan_block.steps"
        base_raw = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "stages": [{"name": "main", "load_from": "", "steps": ["setup", "run", "report"]}],
            }
        )
        feat_raw = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "dft",
                "flow_actions": [
                    {
                        "action": "add_step_after",
                        "stage": "main",
                        "reference": "setup",
                        "items": ["inline_prep"],
                    },
                    {
                        "action": "add_step_after",
                        "stage": "main",
                        "reference": "run",
                        "reference_file": "scripts/scan_block.steps",
                    },
                ],
            }
        )
        ctx, sink = _make_ctx(
            {base_path: base_raw, feat_path: feat_raw, ref_path: "run_scan\n"},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        assert sink.emissions == []
        first, second = result.features[0].flow_actions
        assert first.items == ("inline_prep",)
        assert first.reference_file is None
        assert second.items == ("run_scan",)
        assert second.reference_file == "scripts/scan_block.steps"
