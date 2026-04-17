"""Baseline smoke checks that keep the documented golden-test target live."""

from __future__ import annotations

from pathlib import Path

import chopper


def test_golden_guide_uses_current_paths() -> None:
    guide_text = Path("tests/GOLDEN_FILE_GUIDE.md").read_text(encoding="utf-8")

    assert chopper.__version__
    assert "tests/golden/<module>__<fixture_name>.json" in guide_text
    assert "tests/fixtures/edge_cases/parser_basic_single_proc.tcl" in guide_text
