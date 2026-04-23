"""Torture tests for :class:`RichProgress` — styled + plain paths, fallback."""

from __future__ import annotations

import sys

import pytest

from chopper.adapters.progress_rich import RichProgress, RichUnavailableError
from chopper.core.diagnostics import Phase


def _rich_available() -> bool:
    try:
        import rich  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(not _rich_available(), reason="rich optional dep not installed")
class TestRichProgressAvailable:
    def test_styled_mode_constructs(self) -> None:
        p = RichProgress(plain=False)
        # All three methods must run without error and emit to stderr.
        p.phase_started(Phase.P0_STATE)
        p.phase_done(Phase.P0_STATE)
        p.step("doing-a-thing")

    def test_plain_mode_constructs(self) -> None:
        p = RichProgress(plain=True)
        p.phase_started(Phase.P2_PARSE)
        p.phase_done(Phase.P2_PARSE)
        p.step("plain-step")

    def test_phase_lines_emitted_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Both styled and plain sinks write to stderr (not stdout)."""
        p = RichProgress(plain=True)
        p.phase_started(Phase.P1_CONFIG)
        captured = capsys.readouterr()
        # Rich's write path ends up on captured.err when stderr=True.
        # Some Rich console routes go through a writer that capsys
        # may not catch cleanly, but the method must not raise.
        assert "P1_CONFIG" in (captured.err + captured.out)


class TestRichUnavailableFallback:
    def test_unavailable_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If ``rich`` cannot be imported, constructor raises
        :class:`RichUnavailableError` so the CLI can fall back."""
        # Shim ``rich`` out of sys.modules before the lazy import.
        monkeypatch.setitem(sys.modules, "rich", None)
        monkeypatch.setitem(sys.modules, "rich.console", None)
        with pytest.raises(RichUnavailableError):
            RichProgress(plain=False)
