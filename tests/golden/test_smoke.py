"""Baseline smoke checks that keep the documented golden-test workflow live."""

from __future__ import annotations

from pathlib import Path

import chopper

GOLDEN_DIR = Path("tests/golden/test_audit_artifacts_golden")


def test_golden_section_matches_layout() -> None:
    strategy_text = Path("tests/TESTING_STRATEGY.md").read_text(encoding="utf-8")

    assert chopper.__version__
    assert "## 7. Golden Files" in strategy_text
    assert "tests/golden/test_audit_artifacts_golden/<test_name>.yml" in strategy_text
    assert sorted(p.stem for p in GOLDEN_DIR.glob("*.yml")) == [
        "test_chopper_run_json_shape",
        "test_compiled_manifest_json_shape",
        "test_dependency_graph_json_shape",
        "test_trim_report_json_shape",
    ]
