"""Baseline smoke checks that keep the documented unit-test target live."""

from __future__ import annotations

import importlib.metadata
import runpy
from pathlib import Path

import pytest

import chopper


def test_package_version_is_defined() -> None:
    assert chopper.__version__
    assert Path("pyproject.toml").exists()


def test_package_version_falls_back_to_pyproject(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing(_: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", _missing)

    namespace = runpy.run_path("src/chopper/__init__.py")

    assert namespace["__version__"] == "0.9.2"


def test_package_version_uses_unknown_when_pyproject_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing(_: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    def _broken_read_text(self: Path, *, encoding: str = "utf-8") -> str:
        return "[project]\n"

    monkeypatch.setattr(importlib.metadata, "version", _missing)
    monkeypatch.setattr(Path, "read_text", _broken_read_text)

    namespace = runpy.run_path("src/chopper/__init__.py")

    assert namespace["__version__"] == "0+unknown"
