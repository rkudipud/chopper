"""Baseline smoke checks that keep the documented unit-test target live."""

from __future__ import annotations

from pathlib import Path

import chopper


def test_package_version_is_defined() -> None:
    assert chopper.__version__
    assert Path("pyproject.toml").exists()
