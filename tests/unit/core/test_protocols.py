"""Unit tests for :mod:`chopper.core.protocols`.

Protocols are structural types — there is nothing to execute at module
load beyond ``isinstance`` / attribute checks. These tests verify:

* All three ports are exported.
* Protocols are marked ``@runtime_checkable`` so ``isinstance`` checks
  work against stub adapters.
* A minimal stub class satisfies each protocol (compile-time via ``mypy``,
  plus runtime via ``isinstance``).

Each protocol's full behavioural contract is tested where the concrete
adapter lives (``tests/unit/adapters/``). These tests pin only the
shape.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models import FileStat
from chopper.core.protocols import DiagnosticSink, FileSystemPort, ProgressSink

# ---------------------------------------------------------------------------
# FileSystemPort
# ---------------------------------------------------------------------------


class _StubFS:
    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        return ""

    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:
        return None

    def exists(self, path: Path) -> bool:
        return False

    def list(self, path: Path, *, pattern: str | None = None) -> Sequence[Path]:
        return ()

    def stat(self, path: Path) -> FileStat:
        return FileStat(size=0, mtime=0.0, is_dir=False)

    def rename(self, src: Path, dst: Path) -> None:
        return None

    def remove(self, path: Path, *, recursive: bool = False) -> None:
        return None

    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None:
        return None

    def copy_tree(self, src: Path, dst: Path) -> None:
        return None


def test_stub_fs_satisfies_protocol() -> None:
    stub = _StubFS()
    assert isinstance(stub, FileSystemPort)


# ---------------------------------------------------------------------------
# DiagnosticSink
# ---------------------------------------------------------------------------


class _StubSink:
    def emit(self, diagnostic: Diagnostic) -> None:
        return None

    def snapshot(self) -> Sequence[Diagnostic]:
        return ()

    def finalize(self) -> DiagnosticSummary:
        return DiagnosticSummary(errors=0, warnings=0, infos=0)


def test_stub_sink_satisfies_protocol() -> None:
    assert isinstance(_StubSink(), DiagnosticSink)


# ---------------------------------------------------------------------------
# ProgressSink
# ---------------------------------------------------------------------------


class _StubProgress:
    def phase_started(self, phase: Phase) -> None:
        return None

    def phase_done(self, phase: Phase) -> None:
        return None

    def step(self, message: str) -> None:
        return None


def test_stub_progress_satisfies_protocol() -> None:
    assert isinstance(_StubProgress(), ProgressSink)


# ---------------------------------------------------------------------------
# Missing-method detection
# ---------------------------------------------------------------------------


class _MissingWriteFS:
    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        return ""

    # No other methods — must fail isinstance check.


def test_incomplete_stub_fails_protocol() -> None:
    assert not isinstance(_MissingWriteFS(), FileSystemPort)
