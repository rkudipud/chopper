"""Unit tests for :mod:`chopper.core.context`."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from chopper.core.context import ChopperContext, PresentationConfig, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary
from chopper.core.protocols import DiagnosticSink, FileSystemPort, ProgressSink


class _StubFS:
    def read_text(self, path: Path) -> str:  # pragma: no cover - not invoked
        return ""

    def write_text(self, path: Path, content: str) -> None:  # pragma: no cover
        ...

    def exists(self, path: Path) -> bool:  # pragma: no cover
        return False

    def list(self, path: Path) -> list[Path]:  # pragma: no cover
        return []

    def stat(self, path: Path):  # pragma: no cover
        raise NotImplementedError

    def rename(self, src: Path, dst: Path) -> None:  # pragma: no cover
        ...

    def remove(self, path: Path) -> None:  # pragma: no cover
        ...

    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None:  # pragma: no cover
        ...

    def copy_tree(self, src: Path, dst: Path) -> None:  # pragma: no cover
        ...


class _StubSink:
    def emit(self, diagnostic: Diagnostic) -> None:  # pragma: no cover
        ...

    def snapshot(self) -> tuple[Diagnostic, ...]:  # pragma: no cover
        return ()

    def finalize(self) -> DiagnosticSummary:  # pragma: no cover
        return DiagnosticSummary(errors=0, warnings=0, infos=0)


class _StubProgress:
    def phase_started(self, phase, label: str) -> None:  # pragma: no cover
        ...

    def phase_done(self, phase, status: str) -> None:  # pragma: no cover
        ...

    def step(self, phase, message: str) -> None:  # pragma: no cover
        ...


def _make_ctx() -> ChopperContext:
    cfg = RunConfig(
        domain_root=Path("dom"),
        backup_root=Path("dom_backup"),
        audit_root=Path("dom/.chopper"),
        strict=False,
        dry_run=False,
    )
    return ChopperContext(config=cfg, fs=_StubFS(), diag=_StubSink(), progress=_StubProgress())


class TestRunConfig:
    def test_construction(self) -> None:
        cfg = RunConfig(
            domain_root=Path("a"),
            backup_root=Path("a_backup"),
            audit_root=Path("a/.chopper"),
            strict=True,
            dry_run=False,
        )
        assert cfg.strict is True
        assert cfg.dry_run is False

    def test_frozen(self) -> None:
        cfg = RunConfig(
            domain_root=Path("a"),
            backup_root=Path("b"),
            audit_root=Path("c"),
            strict=False,
            dry_run=False,
        )
        with pytest.raises(FrozenInstanceError):
            cfg.strict = True  # type: ignore[misc]

    def test_no_mode_field(self) -> None:
        # Guard against reintroduction of the rejected ``mode`` field
        # (DAY0_REVIEW A7 / scope-lock).
        assert "mode" not in RunConfig.__dataclass_fields__


class TestPresentationConfig:
    def test_defaults(self) -> None:
        pc = PresentationConfig()
        assert pc.verbose is False
        assert pc.quiet is False
        assert pc.plain is False

    def test_explicit(self) -> None:
        pc = PresentationConfig(verbose=True, quiet=False, plain=True)
        assert pc.verbose is True
        assert pc.plain is True

    def test_frozen(self) -> None:
        pc = PresentationConfig()
        with pytest.raises(FrozenInstanceError):
            pc.verbose = True  # type: ignore[misc]


class TestChopperContext:
    def test_bundles_ports(self) -> None:
        ctx = _make_ctx()
        assert isinstance(ctx.fs, FileSystemPort)
        assert isinstance(ctx.diag, DiagnosticSink)
        assert isinstance(ctx.progress, ProgressSink)

    def test_config_is_run_config(self) -> None:
        ctx = _make_ctx()
        assert isinstance(ctx.config, RunConfig)

    def test_frozen_bindings(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(FrozenInstanceError):
            ctx.fs = _StubFS()  # type: ignore[misc]

    def test_no_presentation_config_field(self) -> None:
        # PresentationConfig is CLI-local and must not leak onto the
        # service-facing context (ARCH §6.1 construction rules).
        assert "presentation" not in ChopperContext.__dataclass_fields__
