"""Torture tests for :class:`ChopperRunner` — every abort + edge path.

These tests force the runner through each of its gates and exception
handlers using the :class:`InMemoryFS` adapter. Each test plants a
specific failure (bad JSON schema, missing source file, brace-imbalance,
strict-warning, crafted :class:`ChopperError`) and asserts the expected
exit code + diagnostic shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chopper.adapters import CollectingSink, InMemoryFS, SilentProgress
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.errors import ChopperError
from chopper.orchestrator import ChopperRunner

DOMAIN = Path("dom")
BACKUP = Path("dom_backup")
BASE_JSON = DOMAIN / "jsons" / "base.json"


def _seed_good_domain(fs: InMemoryFS) -> None:
    """Plant a minimal valid domain used as the base for torture overrides."""

    fs.mkdir(DOMAIN, parents=True, exist_ok=True)
    fs.write_text(DOMAIN / "vars.tcl", "# vars\nset PI 3.14\n")
    fs.write_text(DOMAIN / "helper.tcl", "proc helper_a {} { return 1 }\n")
    fs.write_text(
        BASE_JSON,
        json.dumps(
            {
                "$schema": "chopper/base/v1",
                "domain": "dom",
                "files": {"include": ["vars.tcl", "helper.tcl"]},
            }
        ),
    )


def _make_ctx(
    fs: InMemoryFS,
    *,
    dry_run: bool = True,
    strict: bool = False,
    base_path: Path | None = BASE_JSON,
) -> tuple[ChopperContext, CollectingSink]:
    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=DOMAIN,
        backup_root=BACKUP,
        audit_root=DOMAIN / ".chopper",
        strict=strict,
        dry_run=dry_run,
        base_path=base_path,
    )
    ctx = ChopperContext(config=cfg, fs=fs, diag=sink, progress=SilentProgress())
    return ctx, sink


# ---------------------------------------------------------------------------
# P1 gate — config/pre-validation errors
# ---------------------------------------------------------------------------


class TestP1ConfigGate:
    def test_missing_base_json_aborts_with_exit_1(self) -> None:
        """P1 emits an error (missing base JSON) → gate → exit 1 short-circuit."""
        fs = InMemoryFS()
        fs.mkdir(DOMAIN, parents=True, exist_ok=True)
        # No base JSON written → ConfigService emits VE-*
        ctx, sink = _make_ctx(fs, base_path=DOMAIN / "jsons" / "missing.json")
        result = ChopperRunner().run(ctx, command="validate")

        assert result.exit_code == 1
        # P1 was reached; P2 (parser) was NOT — parsed should be None.
        assert result.parsed is None
        assert result.manifest is None
        # An error diagnostic was emitted at P1.
        codes = [d.code for d in sink.snapshot()]
        assert any(c.startswith("VE-") for c in codes), codes

    def test_base_json_missing_domain_file_emits_ve06_aborts(self) -> None:
        """File named in base.files.include that does not exist → VE-06 → abort."""
        fs = InMemoryFS()
        fs.mkdir(DOMAIN, parents=True, exist_ok=True)
        fs.write_text(
            BASE_JSON,
            json.dumps(
                {
                    "$schema": "chopper/base/v1",
                    "domain": "dom",
                    "files": {"include": ["ghost.tcl"]},
                }
            ),
        )
        ctx, sink = _make_ctx(fs)
        result = ChopperRunner().run(ctx, command="validate")

        assert result.exit_code == 1
        codes = [d.code for d in sink.snapshot()]
        assert "VE-06" in codes, codes


# ---------------------------------------------------------------------------
# P2 gate — parse errors
# ---------------------------------------------------------------------------


class TestP2ParseGate:
    def test_unbalanced_brace_emits_pe02_and_aborts(self) -> None:
        """Bible §5.4.1: unbalanced braces → PE-02, returned proc list is empty → gate aborts."""
        fs = InMemoryFS()
        _seed_good_domain(fs)
        # Clobber helper.tcl with an unbalanced-brace disaster.
        fs.write_text(DOMAIN / "helper.tcl", "proc helper_a {} { open-brace-no-close\n")
        ctx, sink = _make_ctx(fs)
        result = ChopperRunner().run(ctx, command="validate")

        assert result.exit_code == 1
        codes = [d.code for d in sink.snapshot()]
        assert "PE-02" in codes, codes
        # P3 compiler was NOT reached.
        assert result.manifest is None


# ---------------------------------------------------------------------------
# Strict-mode warning escalation
# ---------------------------------------------------------------------------


class TestStrictMode:
    def test_strict_escalates_warnings_to_exit_1(self) -> None:
        """--strict + any warning → exit 1 (severity untouched)."""
        fs = InMemoryFS()
        _seed_good_domain(fs)
        # Add a file that will fire a warning: feature referencing a
        # file via glob that matches nothing → VW-02 / VW-03 style warning.
        # Easier path: hand-emit a warning via a pre-seeded diagnostic —
        # but the runner doesn't accept pre-seeded sinks, so use a
        # setup that produces a real warning.
        # Warning route: declare a feature with a glob that matches no
        # files. That should produce a warning somewhere in the pipeline.
        # Simpler: install a custom sink that injects a warning via a
        # hook? Easier to test: override a file to emit a warning.
        # Use an 'exclude' that cannot match anything → VW-09 style is
        # actually an info. Instead, hand-craft by emitting directly.
        ctx, sink = _make_ctx(fs, strict=True)
        # Pre-inject a warning directly via sink.emit — simulates any
        # phase having emitted a warning that should not gate, but
        # should trigger strict escalation at the final tallying.
        ctx.diag.emit(Diagnostic.build("VW-03", phase=Phase.P1_CONFIG, message="synthetic warn for strict test"))
        result = ChopperRunner().run(ctx, command="validate")

        # The pipeline succeeded on its own (no errors), but strict
        # saw the warning → exit 1.
        assert result.exit_code == 1
        assert result.summary.errors == 0
        assert result.summary.warnings >= 1


# ---------------------------------------------------------------------------
# ChopperError → exit 3
# ---------------------------------------------------------------------------


class TestChopperErrorPath:
    def test_chopper_error_yields_exit_3(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A service raising :class:`ChopperError` → exit 3 (programmer-error channel)."""
        fs = InMemoryFS()
        _seed_good_domain(fs)
        ctx, _sink = _make_ctx(fs)

        # Patch CompilerService.run to raise ChopperError.
        def _boom(self, ctx, loaded, parsed):  # noqa: ANN001, ARG001
            raise ChopperError("synthetic programmer error")

        monkeypatch.setattr(
            "chopper.orchestrator.runner.CompilerService.run",
            _boom,
            raising=True,
        )
        result = ChopperRunner().run(ctx, command="validate")
        assert result.exit_code == 3
        # Manifest never constructed.
        assert result.manifest is None

    def test_audit_exception_is_swallowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If :class:`AuditService` raises during the ``finally`` block,
        the runner must return the primary exit code, not crash."""
        fs = InMemoryFS()
        _seed_good_domain(fs)
        ctx, _sink = _make_ctx(fs)

        def _boom(self, ctx, record):  # noqa: ANN001, ARG001
            raise RuntimeError("audit disk full")

        monkeypatch.setattr(
            "chopper.orchestrator.runner.AuditService.run",
            _boom,
            raising=True,
        )
        # Force a ChopperError in the main try so exit_code is 3; the
        # audit swallow should preserve it.

        def _compile_boom(self, ctx, loaded, parsed):  # noqa: ANN001, ARG001
            raise ChopperError("primary failure")

        monkeypatch.setattr(
            "chopper.orchestrator.runner.CompilerService.run",
            _compile_boom,
            raising=True,
        )
        result = ChopperRunner().run(ctx, command="validate")
        # Primary failure surfaced; audit exception did not mask it.
        assert result.exit_code == 3


# ---------------------------------------------------------------------------
# Non-dry-run paths — trim + generator + post-validate
# ---------------------------------------------------------------------------


class TestLiveTrimPath:
    def test_live_trim_completes_and_writes_audit(self) -> None:
        """Full non-dry-run path: P5a trim + P5b generate + P6 post-validate + P7 audit."""
        fs = InMemoryFS()
        _seed_good_domain(fs)
        ctx, _sink = _make_ctx(fs, dry_run=False)
        result = ChopperRunner().run(ctx, command="trim")

        assert result.exit_code == 0
        assert result.trim_report is not None
        # Audit was written.
        assert fs.exists(DOMAIN / ".chopper" / "chopper_run.json")


# ---------------------------------------------------------------------------
# P3 / P5 / P6 error-gate coverage — each phase's error gate must abort
# ---------------------------------------------------------------------------


def _inject_error_at(phase: Phase, code: str = "VE-01"):
    """Return a monkeypatch shim that emits a synthetic error at ``phase``."""

    def _shim(self, ctx, *args, **kwargs):  # noqa: ANN001, ARG001
        ctx.diag.emit(Diagnostic.build(code, phase=phase, message=f"synthetic {code}"))
        # Still must return something plausible so the next line
        # (``has_errors`` check) can read it. Returning None is fine —
        # runner uses the return value only after the gate.
        # For services whose return value IS used before the gate,
        # we return a sentinel that the gate fires on regardless.
        return None

    return _shim


class TestP3CompileGate:
    def test_p3_error_aborts_pipeline_with_exit_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Compiler emits error → P3 gate → exit 1; P4+ never run."""
        fs = InMemoryFS()
        _seed_good_domain(fs)
        ctx, sink = _make_ctx(fs)

        def _shim(self, ctx, loaded, parsed):  # noqa: ANN001, ARG001
            ctx.diag.emit(Diagnostic.build("VE-01", phase=Phase.P3_COMPILE, message="synthetic compile fail"))
            # Return something that will be ignored by the gate abort
            # but must not raise to hit the P3 error-gate branch (not
            # the except ChopperError branch).
            from chopper.core.models import CompiledManifest

            return CompiledManifest(file_decisions={}, proc_decisions={}, provenance={})

        monkeypatch.setattr(
            "chopper.orchestrator.runner.CompilerService.run",
            _shim,
            raising=True,
        )
        result = ChopperRunner().run(ctx, command="validate")
        assert result.exit_code == 1
        assert "VE-01" in [d.code for d in sink.snapshot()]
        # P4 (trace) never ran → graph is None.
        assert result.graph is None


class TestP5TrimGate:
    def test_p5_error_aborts_live_trim_with_exit_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Trimmer emits error → P5 gate → exit 1; P6 never runs."""
        fs = InMemoryFS()
        _seed_good_domain(fs)
        ctx, sink = _make_ctx(fs, dry_run=False)

        def _shim(self, ctx, manifest, parsed, state):  # noqa: ANN001, ARG001
            ctx.diag.emit(Diagnostic.build("VE-23", phase=Phase.P5_TRIM, message="synthetic trim fail"))
            from chopper.core.models import TrimReport

            return TrimReport(
                outcomes=(),
                files_copied=0,
                files_trimmed=0,
                files_removed=0,
                procs_kept_total=0,
                procs_removed_total=0,
                rebuild_interrupted=True,
            )

        monkeypatch.setattr(
            "chopper.orchestrator.runner.TrimmerService.run",
            _shim,
            raising=True,
        )
        result = ChopperRunner().run(ctx, command="trim")
        assert result.exit_code == 1
        assert "VE-23" in [d.code for d in sink.snapshot()]


class TestP6PostValidateGates:
    def test_p6_error_live_path_aborts_exit_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """validate_post emits error on live path → P6 gate → exit 1."""
        fs = InMemoryFS()
        _seed_good_domain(fs)
        ctx, sink = _make_ctx(fs, dry_run=False)

        def _shim(ctx, manifest, graph, rewritten):  # noqa: ANN001, ARG001
            ctx.diag.emit(Diagnostic.build("VE-16", phase=Phase.P6_POSTVALIDATE, message="synthetic post fail"))

        monkeypatch.setattr(
            "chopper.orchestrator.runner.validate_post",
            _shim,
            raising=True,
        )
        result = ChopperRunner().run(ctx, command="trim")
        assert result.exit_code == 1
        assert "VE-16" in [d.code for d in sink.snapshot()]

    def test_p6_error_dry_run_aborts_exit_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """validate_post emits error on dry-run path → P6 gate → exit 1."""
        fs = InMemoryFS()
        _seed_good_domain(fs)
        ctx, sink = _make_ctx(fs, dry_run=True)

        def _shim(ctx, manifest, graph, rewritten):  # noqa: ANN001, ARG001
            ctx.diag.emit(Diagnostic.build("VE-16", phase=Phase.P6_POSTVALIDATE, message="synthetic dry-run post fail"))

        monkeypatch.setattr(
            "chopper.orchestrator.runner.validate_post",
            _shim,
            raising=True,
        )
        result = ChopperRunner().run(ctx, command="validate")
        assert result.exit_code == 1
        assert "VE-16" in [d.code for d in sink.snapshot()]
