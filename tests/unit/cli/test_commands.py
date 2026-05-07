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
    resolved, stripped = _resolve_domain_root(args)
    assert resolved == tmp_path.resolve()
    assert stripped is None


def test_resolve_domain_root_redirects_backup_cwd_when_live_sibling_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Conditional redirect: cwd ends in ``_backup`` and live sibling exists."""
    from chopper.cli.commands import _resolve_domain_root

    live = tmp_path / "mini"
    live.mkdir()
    backup_cwd = tmp_path / "mini_backup"
    backup_cwd.mkdir()
    monkeypatch.chdir(backup_cwd)

    args = _ns(domain=None)
    resolved, stripped = _resolve_domain_root(args)
    assert resolved == live.resolve()
    assert stripped == backup_cwd.resolve()


def test_resolve_domain_root_honors_backup_cwd_when_no_live_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No redirect when the stripped sibling does not exist on disk.

    A coincidentally ``_backup``-suffixed directory with no live
    sibling is honored as-is (a fresh domain, not a Chopper backup).
    """
    from chopper.cli.commands import _resolve_domain_root

    backup_cwd = tmp_path / "mini_backup"
    backup_cwd.mkdir()
    # No tmp_path/"mini" sibling exists.
    monkeypatch.chdir(backup_cwd)

    args = _ns(domain=None)
    resolved, stripped = _resolve_domain_root(args)
    assert resolved == backup_cwd.resolve()
    assert stripped is None


def test_resolve_domain_root_prefers_domain_flag_over_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--domain`` is the highest-priority resolution source.

    Per ``technical_docs/ARCHITECTURE.md`` §5.1, when ``--domain`` is
    provided the candidate is ``Path(args.domain).resolve()`` and
    ``Path.cwd()`` is not consulted.
    """
    from chopper.cli.commands import _resolve_domain_root

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    unrelated_cwd = tmp_path / "unrelated_cwd"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)

    args = _ns(domain=str(elsewhere))
    resolved, stripped = _resolve_domain_root(args)
    assert resolved == elsewhere.resolve()
    assert stripped is None


def test_resolve_domain_root_redirects_explicit_domain_flag_when_live_sibling_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Conditional redirect applies to ``--domain`` too, not only cwd.

    If the user (or a script) points ``--domain`` at ``<domain>_backup/``
    and a live ``<domain>/`` sibling exists, redirect to the sibling
    and report the original candidate so the caller can emit VI-03.
    """
    from chopper.cli.commands import _resolve_domain_root

    live = tmp_path / "mini"
    live.mkdir()
    backup = tmp_path / "mini_backup"
    backup.mkdir()
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    args = _ns(domain=str(backup))
    resolved, stripped = _resolve_domain_root(args)
    assert resolved == live.resolve()
    assert stripped == backup.resolve()


def test_resolve_domain_root_honors_explicit_domain_flag_when_no_live_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--domain /path/foo_backup`` with no ``foo/`` sibling is honored as-is.

    The redirect is conditional, not unconditional: a coincidentally
    ``_backup``-suffixed domain remains usable.
    """
    from chopper.cli.commands import _resolve_domain_root

    backup = tmp_path / "mini_backup"
    backup.mkdir()
    # No tmp_path/"mini" sibling exists.
    monkeypatch.chdir(tmp_path)

    args = _ns(domain=str(backup))
    resolved, stripped = _resolve_domain_root(args)
    assert resolved == backup.resolve()
    assert stripped is None


def test_resolve_domain_root_redirect_is_single_shot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``foo_backup_backup`` redirects to ``foo_backup`` only, never to ``foo``."""
    from chopper.cli.commands import _resolve_domain_root

    one_strip = tmp_path / "mini_backup"
    one_strip.mkdir()
    two_strip = tmp_path / "mini_backup_backup"
    two_strip.mkdir()
    monkeypatch.chdir(tmp_path)

    args = _ns(domain=str(two_strip))
    resolved, stripped = _resolve_domain_root(args)
    assert resolved == one_strip.resolve()
    assert stripped == two_strip.resolve()


def test_make_context_emits_vi03_when_redirect_fires(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When the conditional ``_backup`` redirect fires, ``_make_context``
    emits ``VI-03 domain-suffix-strip-applied`` into the diagnostic sink.
    """
    from chopper.cli.commands import _make_context

    live = tmp_path / "mini"
    live.mkdir()
    backup = tmp_path / "mini_backup"
    backup.mkdir()
    monkeypatch.chdir(tmp_path)

    args = _ns(domain=str(backup))
    ctx, sink = _make_context(args, dry_run=True)
    assert ctx.config.domain_root == live.resolve()
    codes = [d.code for d in sink.snapshot()]
    assert "VI-03" in codes


def test_make_context_does_not_emit_vi03_when_no_redirect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No VI-03 when the candidate is not redirected (no live sibling)."""
    from chopper.cli.commands import _make_context

    backup = tmp_path / "mini_backup"
    backup.mkdir()
    # No tmp_path/"mini" sibling.
    monkeypatch.chdir(tmp_path)

    args = _ns(domain=str(backup))
    _ctx, sink = _make_context(args, dry_run=True)
    codes = [d.code for d in sink.snapshot()]
    assert "VI-03" not in codes


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
    cfg, _stripped = _build_run_config(args, dry_run=True)
    assert cfg.feature_paths == (f1.resolve(), f2.resolve())


def test_build_run_config_skips_empty_feature_segments(tmp_path: Path) -> None:
    """``--features=a.json,,b.json`` strips empty segments."""
    from chopper.cli.commands import _build_run_config

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    for p in (a, b):
        p.write_text("{}", encoding="utf-8")

    args = _ns(domain=str(tmp_path), features=f"{a},,{b}")
    cfg, _stripped = _build_run_config(args, dry_run=False)
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
    cfg, _stripped = _build_run_config(args, dry_run=True)
    assert cfg.project_path == project.resolve()
    assert cfg.base_path is None
    assert cfg.feature_paths == ()


# ---------------------------------------------------------------------------
# _expand_feature_dirs — validate-only directory expansion (architecture doc §5.1)
# ---------------------------------------------------------------------------


def test_expand_feature_dirs_none_and_empty_pass_through() -> None:
    from chopper.cli.commands import _expand_feature_dirs

    assert _expand_feature_dirs(None) is None
    assert _expand_feature_dirs("") == ""


def test_expand_feature_dirs_leaves_file_entries_unchanged(tmp_path: Path) -> None:
    from chopper.cli.commands import _expand_feature_dirs

    a = tmp_path / "a.feature.json"
    b = tmp_path / "b.feature.json"
    for p in (a, b):
        p.write_text("{}", encoding="utf-8")

    result = _expand_feature_dirs(f"{a},{b}")
    assert result == f"{a},{b}"


def test_expand_feature_dirs_expands_directory_to_sorted_json_children(tmp_path: Path) -> None:
    from chopper.cli.commands import _expand_feature_dirs

    feats = tmp_path / "features"
    feats.mkdir()
    # Intentionally create out of lexicographic order.
    (feats / "zeta.feature.json").write_text("{}", encoding="utf-8")
    (feats / "alpha.feature.json").write_text("{}", encoding="utf-8")
    (feats / "middle.feature.json").write_text("{}", encoding="utf-8")
    # Non-json files must be ignored.
    (feats / "README.md").write_text("ignored", encoding="utf-8")

    result = _expand_feature_dirs(str(feats))
    parts = result.split(",")
    assert parts == [
        (feats / "alpha.feature.json").as_posix(),
        (feats / "middle.feature.json").as_posix(),
        (feats / "zeta.feature.json").as_posix(),
    ]


def test_expand_feature_dirs_mixes_files_and_directories(tmp_path: Path) -> None:
    from chopper.cli.commands import _expand_feature_dirs

    standalone = tmp_path / "standalone.feature.json"
    standalone.write_text("{}", encoding="utf-8")
    feats = tmp_path / "features"
    feats.mkdir()
    (feats / "a.feature.json").write_text("{}", encoding="utf-8")
    (feats / "b.feature.json").write_text("{}", encoding="utf-8")
    trailing = tmp_path / "trailing.feature.json"
    trailing.write_text("{}", encoding="utf-8")

    result = _expand_feature_dirs(f"{standalone},{feats},{trailing}")
    assert result.split(",") == [
        str(standalone),
        (feats / "a.feature.json").as_posix(),
        (feats / "b.feature.json").as_posix(),
        str(trailing),
    ]


def test_expand_feature_dirs_empty_directory_yields_no_entries(tmp_path: Path) -> None:
    from chopper.cli.commands import _expand_feature_dirs

    empty = tmp_path / "empty_features"
    empty.mkdir()
    other = tmp_path / "x.feature.json"
    other.write_text("{}", encoding="utf-8")

    result = _expand_feature_dirs(f"{empty},{other}")
    # Empty dir contributes nothing; only the file entry survives.
    assert result == str(other)


def test_cmd_validate_expands_feature_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``cmd_validate`` rewrites ``args.features`` via ``_expand_feature_dirs``."""
    from chopper.cli import commands

    feats = tmp_path / "features"
    feats.mkdir()
    (feats / "a.feature.json").write_text("{}", encoding="utf-8")
    (feats / "b.feature.json").write_text("{}", encoding="utf-8")
    base = tmp_path / "base.json"
    base.write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    class _StubResult:
        exit_code = 0
        warnings: tuple = ()

    def _fake_make_context(args, *, dry_run):  # noqa: ANN001
        captured["features"] = args.features
        captured["dry_run"] = dry_run
        raise RuntimeError("short-circuit after capture")

    monkeypatch.setattr(commands, "_make_context", _fake_make_context)

    args = _ns(domain=str(tmp_path), base=str(base), features=str(feats))
    with pytest.raises(RuntimeError, match="short-circuit"):
        commands.cmd_validate(args)

    # Directory expanded to sorted POSIX-normalized *.json children.
    assert captured["features"] == ",".join(
        [
            (feats / "a.feature.json").as_posix(),
            (feats / "b.feature.json").as_posix(),
        ]
    )


def test_cmd_trim_does_not_expand_feature_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``cmd_trim`` must leave ``args.features`` untouched — trim requires explicit files."""
    from chopper.cli import commands

    feats = tmp_path / "features"
    feats.mkdir()
    (feats / "a.feature.json").write_text("{}", encoding="utf-8")
    base = tmp_path / "base.json"
    base.write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    def _fake_make_context(args, *, dry_run):  # noqa: ANN001
        captured["features"] = args.features
        raise RuntimeError("short-circuit after capture")

    monkeypatch.setattr(commands, "_make_context", _fake_make_context)

    args = _ns(domain=str(tmp_path), base=str(base), features=str(feats), dry_run=False)
    with pytest.raises(RuntimeError, match="short-circuit"):
        commands.cmd_trim(args)

    # Trim leaves the raw directory path alone (downstream config load will error).
    assert captured["features"] == str(feats)
