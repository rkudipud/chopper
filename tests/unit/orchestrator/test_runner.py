"""Unit tests for :class:`chopper.orchestrator.runner.ChopperRunner`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chopper.adapters import CollectingSink, InMemoryFS, SilentProgress
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, Phase, Severity
from chopper.core.errors import ChopperError
from chopper.core.models import FileTreatment
from chopper.orchestrator import ChopperRunner, has_errors

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


def test_runner_case4_exits_with_code_2() -> None:
    """Neither domain nor backup exists → VE-21 → exit 2."""

    fs = InMemoryFS()
    ctx, sink = _make_ctx(fs, dry_run=False, base_path=None)
    result = ChopperRunner().run(ctx)
    assert result.exit_code == 2
    codes = [d.code for d in sink.snapshot()]
    assert "VE-21" in codes
    assert result.state is not None
    assert result.state.case == 4


def test_runner_returns_run_result_with_summary() -> None:
    fs = InMemoryFS()
    ctx, _ = _make_ctx(fs, dry_run=False, base_path=None)
    result = ChopperRunner().run(ctx)
    assert result.summary.errors >= 1
    assert result.exit_code == 2


def test_has_errors_filters_by_phase() -> None:
    fs = InMemoryFS()
    ctx, _ = _make_ctx(fs, dry_run=False, base_path=None)
    d = Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="x", path=Path("a"))
    ctx.diag.emit(d)
    assert has_errors(ctx, Phase.P1_CONFIG) is True
    assert has_errors(ctx, Phase.P2_PARSE) is False


def test_has_errors_ignores_warnings() -> None:
    fs = InMemoryFS()
    ctx, _ = _make_ctx(fs, dry_run=False, base_path=None)
    d = Diagnostic.build("VW-03", phase=Phase.P1_CONFIG, message="warn")
    ctx.diag.emit(d)
    assert has_errors(ctx, Phase.P1_CONFIG) is False
    # Severity accessor sanity.
    assert d.severity is Severity.WARNING


@pytest.mark.parametrize("command", ["validate", "trim"])
def test_runner_accepts_command_label(command: str) -> None:
    fs = InMemoryFS()
    ctx, _ = _make_ctx(fs, dry_run=False, base_path=None)
    result = ChopperRunner().run(ctx, command=command)  # type: ignore[arg-type]
    # Case-4 short-circuit regardless of command label.
    assert result.exit_code == 2


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


def test_runner_full_dry_run_happy_path() -> None:
    fs = InMemoryFS()
    _seed_good_domain(fs)
    ctx, sink = _make_ctx(fs)
    result = ChopperRunner().run(ctx, command="validate")

    codes = [d.code for d in sink.snapshot()]
    assert result.exit_code == 0, f"non-zero exit; diagnostics: {codes}"
    # All phases reached manifest + graph construction.
    assert result.state is not None
    assert result.state.case == 1
    assert result.loaded is not None
    assert result.parsed is not None
    assert result.manifest is not None
    assert result.graph is not None
    # Dry-run: trim was NOT executed; trim_report must stay None.
    assert result.trim_report is None
    # Summary exposes the final counts.
    assert result.summary.errors == 0


def test_runner_writes_audit_bundle_in_dry_run() -> None:
    fs = InMemoryFS()
    _seed_good_domain(fs)
    ctx, _ = _make_ctx(fs)
    ChopperRunner().run(ctx, command="validate")
    # Audit service always runs — chopper_run.json is written.
    assert fs.exists(DOMAIN / ".chopper" / "chopper_run.json")


# ---------------------------------------------------------------------------
# options.generate_stack — InMemoryFS end-to-end
# ---------------------------------------------------------------------------


def _seed_stages_domain(fs: InMemoryFS) -> None:
    """Plant a stages-only domain with ``options.generate_stack: true``."""

    fs.mkdir(DOMAIN, parents=True, exist_ok=True)
    fs.write_text(
        BASE_JSON,
        json.dumps(
            {
                "$schema": "chopper/base/v1",
                "domain": "dom",
                "options": {"generate_stack": True},
                "stages": [
                    {
                        "name": "setup",
                        "load_from": "",
                        "command": "shell -T setup",
                        "exit_codes": [0],
                        "steps": ["source setup.tcl"],
                    },
                    {
                        "name": "run",
                        "load_from": "setup",
                        "command": "shell -T run",
                        "exit_codes": [0, 3],
                        "dependencies": ["setup"],
                        "steps": ["source run.tcl", "check_results"],
                    },
                ],
            }
        ),
    )


class TestGenerateStackPipeline:
    """End-to-end tests for ``options.generate_stack`` through the full runner."""

    def test_dry_run_manifest_has_generated_stack_entries(self) -> None:
        """Dry-run: manifest records GENERATED for both .tcl and .stack per stage."""
        fs = InMemoryFS()
        _seed_stages_domain(fs)
        ctx, sink = _make_ctx(fs, dry_run=True)
        result = ChopperRunner().run(ctx, command="validate")

        codes = [d.code for d in sink.snapshot()]
        assert result.exit_code == 0, f"non-zero exit; diagnostics: {codes}"
        assert result.manifest is not None
        assert result.manifest.generate_stack is True

        file_decisions = result.manifest.file_decisions
        assert file_decisions.get(Path("setup.tcl")) is FileTreatment.GENERATED
        assert file_decisions.get(Path("setup.stack")) is FileTreatment.GENERATED
        assert file_decisions.get(Path("run.tcl")) is FileTreatment.GENERATED
        assert file_decisions.get(Path("run.stack")) is FileTreatment.GENERATED

    def test_dry_run_does_not_write_stack_files(self) -> None:
        """Dry-run must not write any .tcl or .stack files to the filesystem."""

        fs = InMemoryFS()
        _seed_stages_domain(fs)
        ctx, _ = _make_ctx(fs, dry_run=True)
        ChopperRunner().run(ctx, command="validate")

        assert not fs.exists(DOMAIN / "setup.tcl")
        assert not fs.exists(DOMAIN / "setup.stack")
        assert not fs.exists(DOMAIN / "run.tcl")
        assert not fs.exists(DOMAIN / "run.stack")

    def test_live_trim_writes_tcl_and_stack_files(self) -> None:
        """Live trim writes one .tcl and one .stack file per resolved stage."""

        fs = InMemoryFS()
        _seed_stages_domain(fs)
        ctx, sink = _make_ctx(fs, dry_run=False)
        result = ChopperRunner().run(ctx, command="trim")

        codes = [d.code for d in sink.snapshot()]
        assert result.exit_code == 0, f"non-zero exit; diagnostics: {codes}"
        assert result.trim_report is not None

        # GeneratorService emitted 4 artifacts: tcl+stack for 2 stages.
        assert len(result.generated_artifacts) == 4
        kinds = tuple(a.kind for a in result.generated_artifacts)
        assert kinds == ("tcl", "stack", "tcl", "stack")

        assert fs.exists(DOMAIN / "setup.tcl")
        assert fs.exists(DOMAIN / "setup.stack")
        assert fs.exists(DOMAIN / "run.tcl")
        assert fs.exists(DOMAIN / "run.stack")

    def test_live_trim_stack_content_setup_stage(self) -> None:
        """setup.stack has correct N/J/L/D/R lines for the first stage."""

        fs = InMemoryFS()
        _seed_stages_domain(fs)
        ctx, _ = _make_ctx(fs, dry_run=False)
        ChopperRunner().run(ctx, command="trim")

        content = fs.read_text(DOMAIN / "setup.stack")
        assert content.startswith("# Chopper-generated stack: setup\n")
        assert "N setup\n" in content
        assert "J shell -T setup\n" in content
        assert "L 0\n" in content
        assert "D\n" in content  # first stage — bare D (no predecessor)
        assert "R serial\n" in content

    def test_live_trim_stack_content_run_stage(self) -> None:
        """run.stack has D-line derived from ``dependencies`` field."""

        fs = InMemoryFS()
        _seed_stages_domain(fs)
        ctx, _ = _make_ctx(fs, dry_run=False)
        ChopperRunner().run(ctx, command="trim")

        content = fs.read_text(DOMAIN / "run.stack")
        assert "N run\n" in content
        assert "D setup\n" in content
        assert "L 0 3\n" in content

    def test_live_trim_tcl_content_setup_stage(self) -> None:
        """setup.tcl contains the generated banner and the authored steps."""

        fs = InMemoryFS()
        _seed_stages_domain(fs)
        ctx, _ = _make_ctx(fs, dry_run=False)
        ChopperRunner().run(ctx, command="trim")

        content = fs.read_text(DOMAIN / "setup.tcl")
        assert "# Chopper-generated" in content
        assert "source setup.tcl" in content

    def test_generate_stack_false_does_not_emit_stack_files(self) -> None:
        """When ``generate_stack`` is absent (default false), no .stack files are written."""

        fs = InMemoryFS()
        _seed_good_domain(fs)  # mini domain — no stages, generate_stack defaults to False
        ctx, sink = _make_ctx(fs, dry_run=False)
        result = ChopperRunner().run(ctx, command="trim")

        codes = [d.code for d in sink.snapshot()]
        assert result.exit_code == 0, f"non-zero exit; diagnostics: {codes}"
        # No .stack files written.
        for p in fs._files:  # type: ignore[attr-defined]
            assert not str(p).endswith(".stack"), f"unexpected .stack file: {p}"
