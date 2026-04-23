"""Torture tests for :mod:`chopper.cli.commands` — internal-helper edges.

These bypass the integration harness in :mod:`tests.integration.test_cli_e2e`
and call the private helpers directly to drive uncovered branches:

* ``_resolve_domain_root`` when ``args.domain`` is None (cwd fallback).
* ``_make_progress`` when :class:`RichProgress` raises :class:`RichUnavailableError`.
* ``_build_run_config`` ``--features`` parsing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from chopper.adapters import RichUnavailableError, SilentProgress


def _ns(**kwargs) -> argparse.Namespace:
    """Return a Namespace with every commands.py-touched flag defaulted."""
    defaults = {
        "domain": None,
        "quiet": False,
        "plain": False,
        "strict": False,
        "project": None,
        "base": None,
        "features": None,
        "dry_run": False,
        "confirm": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# _resolve_domain_root — None → cwd
# ---------------------------------------------------------------------------


def test_resolve_domain_root_falls_back_to_cwd_when_args_domain_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from chopper.cli.commands import _resolve_domain_root

    monkeypatch.chdir(tmp_path)
    args = _ns(domain=None)
    resolved = _resolve_domain_root(args)
    assert resolved == tmp_path.resolve()


# ---------------------------------------------------------------------------
# _make_progress — Rich unavailable → SilentProgress
# ---------------------------------------------------------------------------


def test_make_progress_falls_back_to_silent_when_rich_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from chopper.cli import commands

    def _exploding_init(*_args, **_kwargs):
        raise RichUnavailableError("rich not installed in test")

    monkeypatch.setattr(commands, "RichProgress", _exploding_init)
    args = _ns(quiet=False, plain=False)
    progress = commands._make_progress(args)
    assert isinstance(progress, SilentProgress)


def test_make_progress_returns_silent_when_quiet_set() -> None:
    from chopper.cli.commands import _make_progress

    args = _ns(quiet=True)
    progress = _make_progress(args)
    assert isinstance(progress, SilentProgress)


# ---------------------------------------------------------------------------
# _build_run_config — --features parsing
# ---------------------------------------------------------------------------


def test_build_run_config_parses_comma_separated_features(tmp_path: Path) -> None:
    from chopper.cli.commands import _build_run_config

    f1 = tmp_path / "feat_a.json"
    f2 = tmp_path / "feat_b.json"
    f1.write_text("{}", encoding="utf-8")
    f2.write_text("{}", encoding="utf-8")
    base = tmp_path / "base.json"
    base.write_text("{}", encoding="utf-8")

    args = _ns(
        domain=str(tmp_path),
        base=str(base),
        features=f"{f1},{f2}",
    )
    cfg = _build_run_config(args, dry_run=True)
    assert cfg.feature_paths == (f1.resolve(), f2.resolve())


def test_build_run_config_skips_empty_feature_segments(tmp_path: Path) -> None:
    """``--features=a.json,,b.json`` strips empty segments."""
    from chopper.cli.commands import _build_run_config

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    for p in (a, b):
        p.write_text("{}", encoding="utf-8")

    args = _ns(domain=str(tmp_path), features=f"{a},,{b}")
    cfg = _build_run_config(args, dry_run=False)
    assert cfg.feature_paths == (a.resolve(), b.resolve())


def test_build_run_config_with_project_ignores_base_and_features(tmp_path: Path) -> None:
    from chopper.cli.commands import _build_run_config

    project = tmp_path / "project.json"
    project.write_text("{}", encoding="utf-8")
    args = _ns(
        domain=str(tmp_path),
        project=str(project),
        base="ignored_base.json",
        features="ignored_a.json,ignored_b.json",
    )
    cfg = _build_run_config(args, dry_run=True)
    assert cfg.project_path == project.resolve()
    assert cfg.base_path is None
    assert cfg.feature_paths == ()
