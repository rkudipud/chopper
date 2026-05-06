"""Unit tests for :mod:`chopper.audit.internal_error`."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.adapters import InMemoryFS
from chopper.audit import internal_error
from chopper.audit.internal_error import write_internal_error_log
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase


class _Sink:
    def __init__(self, diagnostics: tuple[Diagnostic, ...] = ()) -> None:
        self._diagnostics = diagnostics

    def emit(self, d: Diagnostic) -> None: ...

    def snapshot(self) -> tuple[Diagnostic, ...]:
        return self._diagnostics

    def finalize(self) -> DiagnosticSummary:
        return DiagnosticSummary(errors=0, warnings=0, infos=0)


class _BrokenSink(_Sink):
    def snapshot(self) -> tuple[Diagnostic, ...]:
        raise RuntimeError("snapshot broke")


class _Progress:
    def phase_started(self, phase: Phase) -> None: ...
    def phase_done(self, phase: Phase) -> None: ...
    def step(self, message: str) -> None: ...


def _ctx(tmp_path: Path, *, sink: _Sink | None = None) -> ChopperContext:
    domain = tmp_path / "domain"
    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "domain_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=False,
    )
    return ChopperContext(config=cfg, fs=InMemoryFS(), diag=sink or _Sink(), progress=_Progress())


def test_write_internal_error_log_without_context_uses_override(tmp_path: Path) -> None:
    audit_root = tmp_path / "audit"

    result = write_internal_error_log(None, run_id="", exc=ValueError("boom"), audit_root=audit_root)

    assert result.kind == "ValueError"
    assert result.message == "boom"
    assert result.log_path == audit_root / "internal-error.log"
    text = result.log_path.read_text(encoding="utf-8")
    assert "run_id: unknown" in text
    assert "ValueError: boom" in text
    assert "(no context" in text


def test_write_internal_error_log_renders_diagnostics_and_config(tmp_path: Path) -> None:
    diag = Diagnostic.build(
        "VE-06",
        phase=Phase.P1_CONFIG,
        message="missing file",
        path=Path("lib/a.tcl"),
        line_no=7,
    )
    ctx = _ctx(tmp_path, sink=_Sink((diag,)))

    result = write_internal_error_log(ctx, run_id="abc123", exc=RuntimeError("crash"))

    assert result.log_path is not None
    text = result.log_path.read_text(encoding="utf-8")
    assert "run_id: abc123" in text
    assert "[ERROR] VE-06 file-not-in-domain at lib/a.tcl:7: missing file" in text
    assert "domain_root:" in text
    assert "strict: False" in text


def test_write_internal_error_log_falls_back_to_stderr_on_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise_write(self: Path, text: str, *, encoding: str = "utf-8") -> int:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", _raise_write)

    result = write_internal_error_log(None, run_id="abc", exc=RuntimeError("boom"), audit_root=tmp_path)

    captured = capsys.readouterr()
    assert result.log_path is None
    assert "RuntimeError: boom" in captured.err


def test_render_handles_diagnostic_snapshot_failure(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, sink=_BrokenSink())

    result = write_internal_error_log(ctx, run_id="abc", exc=RuntimeError("boom"))

    assert result.log_path is not None
    text = result.log_path.read_text(encoding="utf-8")
    assert "snapshot unavailable" in text


class _ContextWithBrokenConfig:
    @property
    def config(self) -> object:
        raise RuntimeError("config broke")

    diag = _Sink()


def test_render_handles_config_introspection_failure(tmp_path: Path) -> None:
    result = write_internal_error_log(
        _ContextWithBrokenConfig(),  # type: ignore[arg-type]
        run_id="abc",
        exc=RuntimeError("boom"),
        audit_root=tmp_path,
    )

    assert result.log_path is not None
    text = result.log_path.read_text(encoding="utf-8")
    assert "config unavailable" in text


def test_resolve_audit_root_defaults_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert internal_error._resolve_audit_root(None, None) == tmp_path / ".chopper"
