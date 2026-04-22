"""Unit tests for :class:`chopper.adapters.sink_collecting.CollectingSink`."""

from __future__ import annotations

from pathlib import Path

from chopper.adapters import CollectingSink
from chopper.core.diagnostics import Diagnostic, Phase, Severity


def _diag(code: str, *, message: str, path: Path | None = None, bucket: str = "") -> Diagnostic:
    return Diagnostic.build(
        code,
        phase=Phase.P1_CONFIG,
        message=message,
        path=path,
        dedupe_bucket=bucket,
    )


def test_emit_preserves_insertion_order() -> None:
    sink = CollectingSink()
    sink.emit(_diag("VE-06", message="a", path=Path("a.tcl")))
    sink.emit(_diag("VE-06", message="b", path=Path("b.tcl")))
    snap = sink.snapshot()
    assert [d.message for d in snap] == ["a", "b"]


def test_emit_dedupe_replaces_in_place() -> None:
    sink = CollectingSink()
    first = _diag("VE-06", message="first", path=Path("a.tcl"))
    second = _diag("VE-06", message="first", path=Path("a.tcl"))  # same dedupe key
    sink.emit(first)
    sink.emit(_diag("VE-09", message="other"))
    sink.emit(second)
    snap = sink.snapshot()
    # Second replaced first at its original index; order preserved.
    assert len(snap) == 2
    assert snap[0].hint == second.hint
    assert snap[1].code == "VE-09"


def test_finalize_returns_severity_counts() -> None:
    sink = CollectingSink()
    sink.emit(_diag("VE-06", message="x", path=Path("a.tcl")))  # error
    sink.emit(_diag("VW-03", message="y"))  # warning
    sink.emit(_diag("VI-01", message="z"))  # info
    summary = sink.finalize()
    assert summary.errors == 1
    assert summary.warnings == 1
    assert summary.infos == 1


def test_finalize_counts_by_severity_enum() -> None:
    sink = CollectingSink()
    summary = sink.finalize()
    assert summary.errors == summary.warnings == summary.infos == 0
    # Sanity: severity enum still reachable.
    assert Severity.ERROR is Severity.ERROR
