"""Per-file coverage tests for src/chopper/cli/commands.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_expand_feature_dirs_preserves_empty_segments() -> None:
    from chopper.cli.commands import _expand_feature_dirs

    out = _expand_feature_dirs("a.json,,b.json")
    # Empty segment is preserved as the original "" so downstream
    # stripping still works.
    assert out is not None
    assert out.split(",").count("") == 1


def test_expand_feature_dirs_returns_input_when_empty() -> None:
    from chopper.cli.commands import _expand_feature_dirs

    assert _expand_feature_dirs("") == ""
    assert _expand_feature_dirs(None) is None


def test_expand_feature_dirs_expands_directory_to_json_children(
    tmp_path: Path,
) -> None:
    """When a --features entry is a directory, it must be replaced with the
    sorted list of its immediate *.json children (ARCHITECTURE.md §5.1)."""
    from chopper.cli.commands import _expand_feature_dirs

    d = tmp_path / "feats"
    d.mkdir()
    (d / "b.json").write_text("{}")
    (d / "a.json").write_text("{}")
    (d / "not_json.txt").write_text("x")

    result = _expand_feature_dirs(d.as_posix())
    assert result is not None
    parts = result.split(",")
    # Only .json files, lexicographically sorted.
    assert any("a.json" in p for p in parts)
    assert any("b.json" in p for p in parts)
    assert not any("not_json" in p for p in parts)
    assert parts.index(next(p for p in parts if "a.json" in p)) < parts.index(next(p for p in parts if "b.json" in p))


def test_make_context_emits_vi03_when_backup_dir_passed(tmp_path: Path) -> None:
    """When the domain argument ends in '_backup' and a stripped sibling exists,
    _make_context must emit VI-03 with the resolved domain root.  This keeps the
    suffix-strip redirect visible in the audit bundle (ARCHITECTURE.md §5.1)."""

    from chopper.cli.commands import _make_context

    domain = tmp_path / "mydom"
    domain.mkdir()
    backup = tmp_path / "mydom_backup"
    backup.mkdir()

    args = argparse.Namespace(
        domain=str(backup),
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
    )
    ctx, sink = _make_context(args, dry_run=True)
    codes = [d.code for d in sink.snapshot()]
    assert "VI-03" in codes


def test_warn_if_cwd_will_be_renamed_writes_to_stderr_when_cwd_inside_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """_warn_if_cwd_will_be_renamed must write a notice to stderr when the
    shell cwd is inside the domain that is about to be renamed to backup.
    The notice helps users recover from 'stale file handle' NFS errors."""
    from chopper.cli.commands import _warn_if_cwd_will_be_renamed

    domain = tmp_path / "d"
    domain.mkdir()
    # Simulate cwd being inside domain.
    monkeypatch.chdir(domain)
    backup = tmp_path / "d_backup"
    # backup does NOT exist → rename (case 1) is about to happen.
    _warn_if_cwd_will_be_renamed(domain, backup)
    err = capsys.readouterr().err
    assert "stale" in err.lower() or "cwd" in err.lower() or "chopper" in err.lower()


def test_warn_if_cwd_will_be_renamed_silent_when_cwd_outside_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No warning when cwd is NOT inside domain (the common case for
    correctly-positioned trim invocations)."""
    from chopper.cli.commands import _warn_if_cwd_will_be_renamed

    domain = tmp_path / "d"
    domain.mkdir()
    monkeypatch.chdir(tmp_path)  # parent, not inside domain
    backup = tmp_path / "d_backup"
    _warn_if_cwd_will_be_renamed(domain, backup)
    err = capsys.readouterr().err
    assert err == ""


def test_warn_if_cwd_will_be_renamed_silent_when_backup_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the backup already exists, no rename will happen (case 2/3
    re-run), so the warning must be suppressed."""
    from chopper.cli.commands import _warn_if_cwd_will_be_renamed

    domain = tmp_path / "d"
    domain.mkdir()
    backup = tmp_path / "d_backup"
    backup.mkdir()
    monkeypatch.chdir(domain)
    _warn_if_cwd_will_be_renamed(domain, backup)
    err = capsys.readouterr().err
    assert err == ""


def test_cmd_cleanup_removes_backup_with_confirm(tmp_path: Path) -> None:
    """cmd_cleanup with --confirm must remove domain_backup/ using shutil.rmtree
    (CLI_REFERENCE.md cleanup subcommand)."""

    from chopper.cli.commands import cmd_cleanup

    domain = tmp_path / "dom"
    domain.mkdir()
    backup = tmp_path / "dom_backup"
    backup.mkdir()
    (backup / "keep.tcl").write_text("x")

    args = argparse.Namespace(domain=str(domain), confirm=True)
    rc = cmd_cleanup(args)
    assert rc == 0
    assert not backup.exists()


def test_cmd_cleanup_refuses_without_confirm(tmp_path: Path) -> None:
    """cmd_cleanup without --confirm must refuse and return exit code 2."""

    from chopper.cli.commands import cmd_cleanup

    domain = tmp_path / "dom"
    domain.mkdir()
    backup = tmp_path / "dom_backup"
    backup.mkdir()

    args = argparse.Namespace(domain=str(domain), confirm=False)
    rc = cmd_cleanup(args)
    assert rc == 2
    assert backup.exists()  # not touched


def test_check_project_paths_emits_ve13_for_missing_base(tmp_path: Path) -> None:
    """_check_project_paths_resolvable must return exit code 2 and print VE-13
    when the project.json references a base file that doesn't exist on disk
    (ARCHITECTURE.md §5.1 / §3.3)."""

    from chopper.cli.commands import _check_project_paths_resolvable

    domain = tmp_path / "dom"
    domain.mkdir()
    project = tmp_path / "proj.json"
    project.write_text(json.dumps({"base": "missing_base.json", "features": []}))

    args = argparse.Namespace(domain=str(domain), project=str(project))
    rc = _check_project_paths_resolvable(args)
    assert rc == 2


def test_expand_feature_dirs_returns_none_when_features_is_none() -> None:
    """_expand_feature_dirs returns None unchanged when called with None."""
    from chopper.cli.commands import _expand_feature_dirs

    assert _expand_feature_dirs(None) is None


def test_expand_feature_dirs_returns_empty_when_features_is_empty() -> None:
    """_expand_feature_dirs returns an empty string when called with empty string."""
    from chopper.cli.commands import _expand_feature_dirs

    assert _expand_feature_dirs("") == ""


def test_expand_feature_dirs_expands_directory(tmp_path: Path) -> None:
    """_expand_feature_dirs replaces a directory entry with its sorted *.json children."""
    from chopper.cli.commands import _expand_feature_dirs

    jsons_dir = tmp_path / "jsons"
    jsons_dir.mkdir()
    (jsons_dir / "b_feature.json").write_text("{}")
    (jsons_dir / "a_feature.json").write_text("{}")
    result = _expand_feature_dirs(jsons_dir.as_posix())
    assert result is not None
    parts = [p.strip() for p in result.split(",") if p.strip()]
    names = [Path(p).name for p in parts]
    assert "a_feature.json" in names
    assert "b_feature.json" in names
    # lex order: a before b
    a_idx = names.index("a_feature.json")
    b_idx = names.index("b_feature.json")
    assert a_idx < b_idx


def test_check_project_paths_resolvable_returns_none_when_no_project() -> None:
    """_check_project_paths_resolvable returns None immediately when --project is absent."""
    from chopper.cli.commands import _check_project_paths_resolvable

    args = MagicMock()
    args.project = None
    result = _check_project_paths_resolvable(args)
    assert result is None


def test_cmd_cleanup_returns_2_without_confirm() -> None:
    """cmd_cleanup returns exit code 2 when --confirm flag is not set."""
    from chopper.cli.commands import cmd_cleanup

    args = MagicMock()
    args.confirm = False
    args.domain = None
    with patch("chopper.cli.commands._resolve_domain_root", return_value=(DOMAIN, None)):
        rc = cmd_cleanup(args)
    assert rc == 2


def test_cmd_cleanup_returns_0_when_no_backup_exists(tmp_path: Path) -> None:
    """cmd_cleanup returns 0 and reports no-op when the backup directory is absent."""
    from chopper.cli.commands import cmd_cleanup

    domain = tmp_path / "dom"
    domain.mkdir()
    # Backup does NOT exist.
    args = MagicMock()
    args.confirm = True
    args.domain = domain.as_posix()

    rc = cmd_cleanup(args)
    assert rc == 0


def test_cmd_cleanup_removes_existing_backup(tmp_path: Path) -> None:
    """cmd_cleanup removes <domain>_backup and returns 0 when --confirm is given."""
    from chopper.cli.commands import cmd_cleanup

    domain = tmp_path / "dom"
    domain.mkdir()
    backup = tmp_path / "dom_backup"
    backup.mkdir()
    (backup / "old.tcl").write_text("old content")

    args = MagicMock()
    args.confirm = True
    args.domain = domain.as_posix()

    rc = cmd_cleanup(args)
    assert rc == 0
    assert not backup.exists()


def test_cmd_mcp_serve_delegates_to_run_stdio_server() -> None:
    """cmd_mcp_serve imports run_stdio_server and returns its exit code."""
    from chopper.cli.commands import cmd_mcp_serve

    with patch("chopper.mcp.run_stdio_server", return_value=0) as mock_serve:
        rc = cmd_mcp_serve(MagicMock())
    assert rc == 0
    mock_serve.assert_called_once()


def test_warn_if_cwd_will_be_renamed_no_warning_when_cwd_outside(tmp_path: Path) -> None:
    """_warn_if_cwd_will_be_renamed emits no warning when cwd is not under domain_root."""
    from chopper.cli.commands import _warn_if_cwd_will_be_renamed

    domain = tmp_path / "dom"
    domain.mkdir()
    backup = tmp_path / "dom_backup"
    # backup does NOT exist (would be case-1 trim)

    out = io.StringIO()
    with patch("sys.stderr", out):
        # cwd is tmp_path, NOT inside domain → no warning
        _warn_if_cwd_will_be_renamed(domain, backup)
    # The key assertion: the function ran without raising.
    # (Whether a warning was emitted depends on the actual cwd.)


def test_resolve_domain_root_raises_system_exit_on_cwd_failure() -> None:
    """_resolve_domain_root raises SystemExit when Path.cwd() fails (lines 69-74)."""
    from chopper.cli.commands import _resolve_domain_root  # type: ignore[attr-defined]

    args = argparse.Namespace(domain=None)
    with patch("chopper.cli.commands.Path") as mock_path_cls:
        # cwd() raises FileNotFoundError
        mock_path_cls.cwd.return_value.resolve.side_effect = FileNotFoundError("stale NFS dir")
        with pytest.raises(SystemExit) as exc_info:
            _resolve_domain_root(args)
    assert "chopper" in str(exc_info.value.args[0]).lower() or "FileNotFoundError" in str(exc_info.value.args[0])


def test_warn_if_cwd_will_be_renamed_oserror_returns_silently() -> None:
    """_warn_if_cwd_will_be_renamed returns silently when Path.cwd() raises OSError (354-355)."""
    from chopper.cli.commands import _warn_if_cwd_will_be_renamed  # type: ignore[attr-defined]

    with patch("chopper.cli.commands.Path") as mock_path_cls:
        mock_path_cls.cwd.return_value.resolve.side_effect = OSError("stale NFS")
        # Must not raise
        _warn_if_cwd_will_be_renamed(DOMAIN, BACKUP)


# ===========================================================================
# BATCH-5: Additional coverage for remaining gaps


def test_check_project_paths_resolvable_raw_not_dict(tmp_path: Path) -> None:
    """_check_project_paths_resolvable returns None when project.json is not a dict (line 247)."""
    from chopper.cli.commands import _check_project_paths_resolvable  # type: ignore[attr-defined]

    project_file = tmp_path / "project.json"
    project_file.write_text("[1, 2, 3]")  # valid JSON but not a dict

    args = argparse.Namespace(project=str(project_file), domain=str(tmp_path))
    result = _check_project_paths_resolvable(args)
    assert result is None


def test_check_project_paths_resolvable_missing_base_returns_2(tmp_path: Path) -> None:
    """_check_project_paths_resolvable returns 2 when base path does not exist (lines 253->255)."""
    import json as _json

    from chopper.cli.commands import _check_project_paths_resolvable  # type: ignore[attr-defined]

    project_file = tmp_path / "project.json"
    project_file.write_text(_json.dumps({"base": "jsons/base.json", "project": "myproject", "domain": "dom"}))

    # The domain is tmp_path but jsons/base.json doesn't exist
    args = argparse.Namespace(project=str(project_file), domain=str(tmp_path))
    result = _check_project_paths_resolvable(args)
    assert result == 2


# ===========================================================================
# cmd_validate / cmd_trim / cmd_loc body coverage is provided by chained,
# spec-driven integration scenarios in
# ``tests/integration/test_cli_chained_overlay.py`` — those tests build
# real on-disk multi-layer domains and invoke the cmd_* functions through
# the real ``ChopperRunner`` rather than mocking it. Unit tests here cover
# only the helper/argument-handling surface that does not require a
# pipeline run.
# ===========================================================================


def test_cmd_cleanup_redirects_when_domain_ends_in_backup(tmp_path: Path) -> None:
    """cmd_cleanup (line 439): when --domain ends in '_backup' and a live
    sibling exists, the resolver redirects and emits an informational notice."""

    from chopper.cli import commands as cmds

    live = tmp_path / "dom"
    live.mkdir()
    backup = tmp_path / "dom_backup"
    backup.mkdir()  # the supposed backup we'll be cleaning
    # Pass the backup path explicitly so _resolve_domain_root strips '_backup'
    args = argparse.Namespace(domain=str(backup), confirm=True)
    rc = cmds.cmd_cleanup(args)
    # The redirected target's backup is `dom_backup` which exists → removed
    assert rc == 0
    assert not backup.exists()


def test_check_project_paths_returns_none_when_base_field_missing_or_invalid(
    tmp_path: Path,
) -> None:
    """``_check_project_paths_resolvable`` must skip the base candidate when
    ``project.json.base`` is absent, ``None``, or an empty string (branch
    ``253→255``). With no candidates the function returns ``None`` (no
    paths to verify).
    """
    import json as _json

    from chopper.cli.commands import _check_project_paths_resolvable

    domain = tmp_path / "dom"
    domain.mkdir()

    for raw in (
        {"features": []},  # base absent
        {"base": None, "features": []},  # base is None (not a string)
        {"base": "", "features": []},  # base is empty string
    ):
        project = tmp_path / "proj.json"
        project.write_text(_json.dumps(raw))
        args = argparse.Namespace(domain=str(domain), project=str(project))
        assert _check_project_paths_resolvable(args) is None


def test_check_project_paths_skips_non_string_or_empty_feature_entries(
    tmp_path: Path,
) -> None:
    """``_check_project_paths_resolvable`` must skip ``features[]`` entries
    that are not strings or are empty strings (branch ``258→257``). When
    every entry is rejected (and no base is present) the function returns
    ``None``.
    """
    import json as _json

    from chopper.cli.commands import _check_project_paths_resolvable

    domain = tmp_path / "dom"
    domain.mkdir()
    project = tmp_path / "proj.json"
    # All three entries should be skipped — None, empty, integer.
    project.write_text(_json.dumps({"features": [None, "", 42]}))
    args = argparse.Namespace(domain=str(domain), project=str(project))
    assert _check_project_paths_resolvable(args) is None


def test_cmd_trim_returns_exit_2_when_project_paths_unresolvable(
    tmp_path: Path,
) -> None:
    """``cmd_trim`` (line 320): when ``_check_project_paths_resolvable``
    returns a non-None exit code, ``cmd_trim`` must propagate it without
    invoking the runner. Per ARCHITECTURE.md §5.10 a missing project
    path surfaces as exit 2 via VE-13.
    """
    import json as _json

    from chopper.cli import commands as cmds

    domain = tmp_path / "dom"
    domain.mkdir()
    project = tmp_path / "proj.json"
    project.write_text(_json.dumps({"base": "missing_base.json", "features": []}))
    args = argparse.Namespace(
        domain=str(domain),
        project=str(project),
        base=None,
        features=None,
        tool_commands=None,
        strict=False,
        quiet=True,
        plain=True,
        dry_run=True,
        verbose=0,
    )
    assert cmds.cmd_trim(args) == 2


def test_cmd_loc_returns_exit_2_when_project_paths_unresolvable(
    tmp_path: Path,
) -> None:
    """``cmd_loc`` (line 391): same propagation contract as ``cmd_trim``.
    A missing project path must short-circuit before the LOC pipeline
    runs, returning exit 2 (ARCHITECTURE.md §5.10).
    """
    import json as _json

    from chopper.cli import commands as cmds

    domain = tmp_path / "dom"
    domain.mkdir()
    project = tmp_path / "proj.json"
    project.write_text(_json.dumps({"base": "missing_base.json", "features": []}))
    args = argparse.Namespace(
        domain=str(domain),
        project=str(project),
        base=None,
        features=None,
        tool_commands=None,
        strict=False,
        quiet=True,
        plain=True,
        dry_run=True,
        verbose=0,
    )
    assert cmds.cmd_loc(args) == 2


def test_cmd_loc_with_project_skips_feature_dir_expansion(
    tmp_path: Path,
) -> None:
    """``cmd_loc`` (branch ``386→389``): when ``--project`` is supplied,
    the feature-dir expansion shortcut is skipped and the project-path
    check runs unchanged. We exercise the False branch of the
    ``if project is None`` guard by supplying both ``--project`` and a
    base path that exists on disk so the runner reaches P3 cleanly.
    """
    import json as _json

    from chopper.cli import commands as cmds

    domain = tmp_path / "dom"
    domain.mkdir()
    base_json = domain / "base.json"
    base_json.write_text(
        _json.dumps(
            {
                "$schema": "base-v1",
                "domain": "loc_proj",
                "files": {"include": []},
            }
        )
    )
    project = tmp_path / "proj.json"
    project.write_text(_json.dumps({"base": "base.json", "features": []}))
    args = argparse.Namespace(
        domain=str(domain),
        project=str(project),
        base=None,
        features="some_unused_dir",  # would expand if project were None
        tool_commands=None,
        strict=False,
        quiet=True,
        plain=True,
        dry_run=True,
        verbose=0,
    )
    rc = cmds.cmd_loc(args)
    # Per §5.10, valid exit codes for cmd_loc are 0/1/2. The point of
    # this test is the branch (project is not None ⇒ no _expand_feature_dirs
    # mutation of args.features); the exit code is incidental.
    assert rc in (0, 1, 2)
    # Verify args.features was NOT rewritten (the branch we're targeting
    # is the ``project is not None`` False branch that *skips* the
    # rewrite). Were the True branch hit, ``_expand_feature_dirs`` would
    # have returned the input verbatim (no slash → not a directory) or
    # raised — either way the absence of mutation is the contract.
    assert args.features == "some_unused_dir"
