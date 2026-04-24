"""Chopper — EDA TFM trimming tool for Cheetah R2G flows."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("chopper")
except PackageNotFoundError:
    # Source checkout without install (e.g. `PYTHONPATH=src python -c 'import chopper'`).
    # Fall back to parsing pyproject.toml so the package still reports a sensible version.
    import tomllib
    from pathlib import Path

    _pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        __version__ = tomllib.loads(_pyproject.read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError):
        __version__ = "0+unknown"
