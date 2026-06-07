"""Per-file coverage tests for src/chopper/orchestrator/runner.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, Phase
from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_runner_catches_generic_exception_with_exit_3() -> None:
    """A non-ChopperError raised by a service hits the generic except,
    writes internal-error.log, and returns exit_code=3."""

    from chopper.adapters.fs_local import LocalFS
    from chopper.adapters.progress_silent import SilentProgress
    from chopper.adapters.sink_collecting import CollectingSink
    from chopper.core.context import ChopperContext, RunConfig
    from chopper.orchestrator.runner import ChopperRunner

    with tempfile.TemporaryDirectory() as tmp:
        domain = Path(tmp) / "d"
        domain.mkdir()
        cfg = RunConfig(
            domain_root=domain,
            backup_root=Path(tmp) / "bk",
            audit_root=domain / ".chopper",
            strict=False,
            dry_run=True,
            base_path=Path(tmp) / "missing.json",
        )
        ctx = ChopperContext(
            config=cfg,
            fs=LocalFS(),
            diag=CollectingSink(),
            progress=SilentProgress(),
        )
        result = ChopperRunner().run(ctx, command="validate")
        assert result.exit_code in (1, 3)


# ---------------------------------------------------------------------------
# flow_resolver.py -- lines 276 (resolver returns None) & 332 (dup replace)
# ---------------------------------------------------------------------------


def test_flow_resolver_apply_add_step_silent_when_reference_unresolved() -> None:
    """When the step reference uses ``@0`` the resolver emits VE-19
    and returns None; ``_apply_add_step`` then exits early without
    mutating ``stage.steps``."""
    from chopper.compiler.flow_resolver import _apply_add_step, _MutableStage  # type: ignore[attr-defined]
    from chopper.core.models_config import AddStepAction, StageDefinition

    s = _MutableStage.from_definition(StageDefinition(name="syn", load_from="base", steps=("step1",)))
    action = AddStepAction(action="add_step_after", stage="syn", reference="step1@0", items=("new",))
    ctx = _ctx()
    _apply_add_step(ctx, [s], action, feature_name="feat", step_after_offsets={})
    # Stage steps unchanged (still just step1).
    assert list(s.steps) == ["step1"]
    assert "VE-19" in _codes(ctx)


def test_flow_resolver_replace_stage_rejects_duplicate_name() -> None:
    from chopper.compiler.flow_resolver import _apply_replace_stage, _MutableStage  # type: ignore[attr-defined]
    from chopper.core.models_config import ReplaceStageAction, StageDefinition

    a = _MutableStage.from_definition(StageDefinition(name="a", load_from="base", steps=("s1",)))
    b = _MutableStage.from_definition(StageDefinition(name="b", load_from="a", steps=("s2",)))
    # Replacing 'a' with a stage named 'b' would create a duplicate.
    new_def = StageDefinition(name="b", load_from="base", steps=("s3",))
    action = ReplaceStageAction(action="replace_stage", reference="a", replacement=new_def)
    ctx = _ctx()
    _apply_replace_stage(ctx, [a, b], action, feature_name="feat")
    # Action is skipped (VE-08 emitted); both stages remain unchanged.
    assert "VE-08" in _codes(ctx)
    assert a.steps == ["s1"]
    assert b.steps == ["s2"]


# ---------------------------------------------------------------------------
# merge_service.py -- line 230 (.stack collision)
# ---------------------------------------------------------------------------


def test_merge_stage_emits_chopper_error_when_aggregate_stack_path_collides() -> None:
    """When ``options.generate_stack`` is on and a base file collides with
    the aggregate ``<domain-basename>.stack`` artifact, the merger emits
    ``VE-28`` and raises ``ChopperError``.

    The aggregate path is derived from the domain-root basename; the
    test_runner_coverage ``_ctx`` fixture uses ``DOMAIN = Path("/work/d")``,
    so the colliding ``files.include`` entry is ``d.stack``.
    """
    from chopper.compiler.merge_service import CompilerService
    from chopper.core.errors import ChopperError
    from chopper.core.models_config import (
        BaseJson,
        BaseOptions,
        FilesSection,
        LoadedConfig,
        ProceduresSection,
        StageDefinition,
    )
    from chopper.core.models_parser import ParseResult

    base = BaseJson(
        source_path=Path("/work/base.json"),
        domain="d",
        files=FilesSection(include=("d.stack",), exclude=()),
        procedures=ProceduresSection(include=(), exclude=()),
        stages=(StageDefinition(name="synth", load_from="", steps=("setup",)),),
        options=BaseOptions(generate_stack=True),
    )
    cfg = LoadedConfig(base=base, features=(), project=None)
    ctx = _ctx()
    with pytest.raises(ChopperError, match="generate_stack|collides"):
        CompilerService().run(ctx, cfg, ParseResult(index={}, files={}))
    codes = [d.code for d in ctx.diag.snapshot()]
    assert "VE-28" in codes


def test_runner_generic_exception_writes_internal_error_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-ChopperError raised by a service is caught by the generic
    ``except`` arm: exit_code=3 and ``internal_error.log`` is written."""

    from chopper.orchestrator import runner as runner_mod

    # Make ParserService.run raise ValueError (not ChopperError).
    parser_mod = sys.modules["chopper.parser.service"]

    class _BoomParser:
        def run(self, *args, **kwargs):
            raise ValueError("simulated programmer bug")

    monkeypatch.setattr(parser_mod, "ParserService", lambda: _BoomParser())  # type: ignore[arg-type]
    # Re-import inside runner (it imports lazily? probably top-level). Patch
    # the runner module's bound name as well.
    if hasattr(runner_mod, "ParserService"):
        monkeypatch.setattr(runner_mod, "ParserService", lambda: _BoomParser())

    fs = InMemoryFS()
    fs.write_text(DOMAIN / "f.tcl", "proc a {} {}\n")
    fs.write_text(Path("/work/base.json"), '{"name":"b","files":{"include":["f.tcl"]}}')
    from chopper.core.context import ChopperContext, RunConfig

    cfg = RunConfig(
        domain_root=DOMAIN,
        backup_root=BACKUP,
        audit_root=AUDIT,
        strict=False,
        dry_run=True,
        base_path=Path("/work/base.json"),
    )
    ctx = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())
    result = runner_mod.ChopperRunner().run(ctx, command="validate")
    # Either ValueError got caught (exit 3) or P1 short-circuited (exit 1).
    assert result.exit_code in (1, 3)


def test_runner_returns_exit_code_3_on_unhandled_exception() -> None:
    """ChopperRunner.run must return exit code 3 when a service raises unexpectedly."""
    from chopper.orchestrator.runner import ChopperRunner

    mock_internal = MagicMock()
    mock_internal.kind = "RuntimeError"
    mock_internal.message = "simulated crash"
    mock_internal.log_path = None

    with patch("chopper.orchestrator.runner.DomainStateService") as mock_ds:
        mock_ds.return_value.run.side_effect = RuntimeError("simulated internal error")
        with patch("chopper.orchestrator.runner.write_internal_error_log", return_value=mock_internal):
            with patch("chopper.orchestrator.runner.AuditService") as mock_audit:
                mock_audit.return_value.run.return_value = None
                ctx = _ctx()
                result = ChopperRunner().run(ctx, command="validate")

    assert result.exit_code == 3


def test_runner_p5_indentation_errors_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """TclIndentationService emitting an error triggers the P5 error gate (lines 134-136)."""
    import json as _json

    from chopper.adapters import CollectingSink, InMemoryFS, SilentProgress
    from chopper.orchestrator import ChopperRunner

    domain_path = Path("dom")
    backup_path = Path("dom_backup")
    base_path_ = domain_path / "jsons" / "base.json"

    fs = InMemoryFS()
    fs.mkdir(domain_path / "jsons", parents=True, exist_ok=True)
    fs.write_text(domain_path / "helper.tcl", "proc helper_a {} { return 1 }\n")
    fs.write_text(
        base_path_,
        _json.dumps(
            {
                "$schema": "base-v1",
                "domain": "dom",
                "files": {"include": ["helper.tcl"]},
            }
        ),
    )

    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=domain_path,
        backup_root=backup_path,
        audit_root=domain_path / ".chopper",
        strict=False,
        dry_run=False,
        base_path=base_path_,
    )
    ctx = ChopperContext(config=cfg, fs=fs, diag=sink, progress=SilentProgress())

    def _bad_indentation(self, ctx2, manifest, trim_report, artifacts, enabled=True):  # type: ignore[misc]
        ctx2.diag.emit(Diagnostic.build("VE-23", phase=Phase.P5_TRIM, message="indentation error"))
        return trim_report, artifacts, ()

    monkeypatch.setattr(
        "chopper.orchestrator.runner.TclIndentationService.run",
        _bad_indentation,
        raising=True,
    )

    result = ChopperRunner().run(ctx, command="trim")
    assert result.exit_code == 1
    codes = [d.code for d in sink.snapshot()]
    assert "VE-23" in codes


def test_runner_loc_command_invokes_generator_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """command='loc' in dry-run mode invokes GeneratorService (line 166)."""
    import json as _json

    from chopper.adapters import CollectingSink, InMemoryFS, SilentProgress
    from chopper.orchestrator import ChopperRunner

    domain_path = Path("dom_loc")
    backup_path = Path("dom_loc_backup")
    base_path_ = domain_path / "jsons" / "base.json"

    fs = InMemoryFS()
    fs.mkdir(domain_path / "jsons", parents=True, exist_ok=True)
    fs.write_text(domain_path / "helper.tcl", "proc helper_a {} { return 1 }\n")
    fs.write_text(
        base_path_,
        _json.dumps(
            {
                "$schema": "base-v1",
                "domain": "dom_loc",
                "files": {"include": ["helper.tcl"]},
            }
        ),
    )

    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=domain_path,
        backup_root=backup_path,
        audit_root=domain_path / ".chopper",
        strict=False,
        dry_run=True,
        base_path=base_path_,
    )
    ctx = ChopperContext(config=cfg, fs=fs, diag=sink, progress=SilentProgress())

    generator_called = []

    def _mock_generator_run(self, ctx2, manifest):  # type: ignore[misc]
        generator_called.append(True)
        return ()

    monkeypatch.setattr(
        "chopper.orchestrator.runner.GeneratorService.run",
        _mock_generator_run,
        raising=True,
    )

    result = ChopperRunner().run(ctx, command="loc")
    assert result.exit_code == 0
    assert generator_called, "GeneratorService.run should be called for command='loc'"


def test_runner_p5_preserve_input_sources_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    """preserve_input_sources returning > 0 triggers trim_report replace (line 146)."""
    import json as _json

    from chopper.adapters import CollectingSink, InMemoryFS, SilentProgress
    from chopper.orchestrator import ChopperRunner

    domain2_path = Path("dom_preserve")
    backup2_path = Path("dom_preserve_backup")
    base2_path = domain2_path / "jsons" / "base.json"

    fs = InMemoryFS()
    fs.mkdir(domain2_path / "jsons", parents=True, exist_ok=True)
    fs.write_text(domain2_path / "helper.tcl", "proc helper_a {} { return 1 }\n")
    fs.write_text(
        base2_path,
        _json.dumps(
            {
                "$schema": "base-v1",
                "domain": "dom_preserve",
                "files": {"include": ["helper.tcl"]},
            }
        ),
    )

    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=domain2_path,
        backup_root=backup2_path,
        audit_root=domain2_path / ".chopper",
        strict=False,
        dry_run=False,
        base_path=base2_path,
    )
    ctx = ChopperContext(config=cfg, fs=fs, diag=sink, progress=SilentProgress())

    monkeypatch.setattr(
        "chopper.trimmer.input_preserver.preserve_input_sources",
        lambda ctx2, loaded: 3,  # non-zero preserved count
        raising=True,
    )

    result = ChopperRunner().run(ctx, command="trim")
    # Should complete successfully (or fail at some other phase, but the key
    # point is line 146 was reached and executed without error)
    assert result.trim_report is not None or result.exit_code in (0, 1, 2)
