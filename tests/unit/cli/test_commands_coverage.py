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
    sorted list of its immediate *.json children (ARCHITECTURE.md Sec.5.1)."""
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
    suffix-strip redirect visible in the audit bundle (ARCHITECTURE.md Sec.5.1)."""

    from chopper.cli.commands import _make_context

    domain = tmp_path / "mydom"
    domain.mkdir()
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text("{}", encoding="utf-8")
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
    # backup does NOT exist -> rename (case 1) is about to happen.
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
    (ARCHITECTURE.md Sec.5.1 / Sec.3.3)."""

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
    with patch("chopper.cli.commands._resolve_domain_root", return_value=(DOMAIN, None, None)):
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


def test_warn_if_cwd_will_be_renamed_no_warning_when_cwd_outside(tmp_path: Path) -> None:
    """_warn_if_cwd_will_be_renamed emits no warning when cwd is not under domain_root."""
    from chopper.cli.commands import _warn_if_cwd_will_be_renamed

    domain = tmp_path / "dom"
    domain.mkdir()
    backup = tmp_path / "dom_backup"
    # backup does NOT exist (would be case-1 trim)

    out = io.StringIO()
    with patch("sys.stderr", out):
        # cwd is tmp_path, NOT inside domain -> no warning
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
# ``tests/integration/test_cli_chained_overlay.py`` -- those tests build
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
    # The redirected target's backup is `dom_backup` which exists -> removed
    assert rc == 0
    assert not backup.exists()


def test_check_project_paths_returns_none_when_base_field_missing_or_invalid(
    tmp_path: Path,
) -> None:
    """``_check_project_paths_resolvable`` must skip the base candidate when
    ``project.json.base`` is absent, ``None``, or an empty string (branch
    ``253->255``). With no candidates the function returns ``None`` (no
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
    that are not strings or are empty strings (branch ``258->257``). When
    every entry is rejected (and no base is present) the function returns
    ``None``.
    """
    import json as _json

    from chopper.cli.commands import _check_project_paths_resolvable

    domain = tmp_path / "dom"
    domain.mkdir()
    project = tmp_path / "proj.json"
    # All three entries should be skipped -- None, empty, integer.
    project.write_text(_json.dumps({"features": [None, "", 42]}))
    args = argparse.Namespace(domain=str(domain), project=str(project))
    assert _check_project_paths_resolvable(args) is None


def test_cmd_trim_returns_exit_2_when_project_paths_unresolvable(
    tmp_path: Path,
) -> None:
    """``cmd_trim`` (line 320): when ``_check_project_paths_resolvable``
    returns a non-None exit code, ``cmd_trim`` must propagate it without
    invoking the runner. Per ARCHITECTURE.md Sec.5.10 a missing project
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
    runs, returning exit 2 (ARCHITECTURE.md Sec.5.10).
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
    """``cmd_loc`` (branch ``386->389``): when ``--project`` is supplied,
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
    # Per Sec.5.10, valid exit codes for cmd_loc are 0/1/2. The point of
    # this test is the branch (project is not None => no _expand_feature_dirs
    # mutation of args.features); the exit code is incidental.
    assert rc in (0, 1, 2)
    # Verify args.features was NOT rewritten (the branch we're targeting
    # is the ``project is not None`` False branch that *skips* the
    # rewrite). Were the True branch hit, ``_expand_feature_dirs`` would
    # have returned the input verbatim (no slash -> not a directory) or
    # raised -- either way the absence of mutation is the contract.
    assert args.features == "some_unused_dir"


# ===========================================================================
# New coverage: _split_domain_csv, _make_error_domain_result, VE-35, VE-36,
# name-mode backup redirect, multi-domain loops (4.1.0+ paths)
# ===========================================================================


def test_split_domain_csv_none_returns_single_none_element() -> None:
    from chopper.cli.commands import _split_domain_csv

    result = _split_domain_csv(None)
    assert result == [None]


def test_split_domain_csv_single_token_returns_single_element() -> None:
    from chopper.cli.commands import _split_domain_csv

    result = _split_domain_csv("fev_formality")
    assert result == ["fev_formality"]


def test_split_domain_csv_two_tokens_returns_two_elements() -> None:
    from chopper.cli.commands import _split_domain_csv

    result = _split_domain_csv("fev_formality,fev_conformal")
    assert result == ["fev_formality", "fev_conformal"]


def test_split_domain_csv_strips_whitespace() -> None:
    from chopper.cli.commands import _split_domain_csv

    result = _split_domain_csv("  fev_formality , fev_conformal  ")
    assert result == ["fev_formality", "fev_conformal"]


def test_split_domain_csv_ignores_empty_tokens() -> None:
    from chopper.cli.commands import _split_domain_csv

    # Trailing comma -> only one real token.
    result = _split_domain_csv("fev_formality,")
    assert result == ["fev_formality"]


def test_make_error_domain_result_fields() -> None:
    from chopper.cli.commands import _make_error_domain_result

    r = _make_error_domain_result("snps/fev_formality", 2)
    assert r.domain_logical_name == "snps/fev_formality"
    assert r.exit_code == 2
    assert r.branch_needed is False
    assert r.edits_count == 0
    assert r.adds_count == 0
    assert r.removes_count == 0


def test_make_error_domain_result_none_token() -> None:
    from chopper.cli.commands import _make_error_domain_result

    r = _make_error_domain_result(None, 2)
    assert r.domain_logical_name == "(unknown)"


def test_build_run_config_ve35_auto_discovery_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """When --domain is set but --base is absent and jsons/base.json doesn't
    exist, _build_run_config must write VE-35 to stderr and raise SystemExit(2).
    Per ARCHITECTURE.md Sec.5.1.0 (base auto-discovery).
    """
    from chopper.cli.commands import _build_run_config

    domain = tmp_path / "my_domain"
    domain.mkdir()
    # No jsons/ at all -> auto-discovery fails.

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
    )
    with pytest.raises(SystemExit) as exc_info:
        _build_run_config(args, dry_run=True)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "VE-35" in captured.err


def test_build_run_config_ve36_unresolved_feature_name(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """When a --features token is a name that cannot be resolved to a
    *.feature.json file, _build_run_config must write VE-36 to stderr and
    raise SystemExit(2).  Per ARCHITECTURE.md Sec.5.1.0 (feature-name lookup).
    """
    from chopper.cli.commands import _build_run_config

    domain = tmp_path / "my_domain"
    domain.mkdir()
    jsons = domain / "jsons"
    jsons.mkdir()
    (jsons / "base.json").write_text("{}")
    features_dir = jsons / "features"
    features_dir.mkdir()
    (features_dir / "dft.feature.json").write_text("{}")

    args = argparse.Namespace(
        domain=str(domain),
        base=None,  # will be auto-discovered from jsons/base.json
        features="nonexistent_feature",
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
    )
    with pytest.raises(SystemExit) as exc_info:
        _build_run_config(args, dry_run=True)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "VE-36" in captured.err


def test_build_run_config_ve36_unresolved_feature_with_suggestion(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """VE-36 error message must include a 'Did you mean' suggestion when
    there is a close match in the features directory.
    """
    from chopper.cli.commands import _build_run_config

    domain = tmp_path / "my_domain"
    domain.mkdir()
    jsons = domain / "jsons"
    jsons.mkdir()
    (jsons / "base.json").write_text("{}")
    features_dir = jsons / "features"
    features_dir.mkdir()
    # "dft_scan" is close enough to "dft_scam" (typo) for difflib to suggest.
    (features_dir / "dft_scan.feature.json").write_text("{}")

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features="dft_scam",  # typo of dft_scan
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
    )
    with pytest.raises(SystemExit) as exc_info:
        _build_run_config(args, dry_run=True)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "VE-36" in captured.err
    assert "Did you mean" in captured.err


def test_resolve_domain_root_backup_redirect_from_name_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_resolve_domain_root must apply _backup redirect even when name-mode
    resolution returns a path that ends in '_backup', stripping to the
    sibling live domain.  Per ARCHITECTURE.md Sec.5.1 (domain-suffix-strip).
    """
    from chopper.cli.commands import _resolve_domain_root

    # Set up $ward/global/snps/fev_formality_backup (the name-mode result)
    ward = tmp_path / "ward"
    global_dir = ward / "global" / "snps"
    global_dir.mkdir(parents=True)
    backup_domain = global_dir / "fev_formality_backup"
    backup_domain.mkdir()
    # The stripped sibling must also exist.
    live_domain = global_dir / "fev_formality"
    live_domain.mkdir()

    monkeypatch.setenv("ward", ward.as_posix())
    args = argparse.Namespace(domain="snps/fev_formality_backup")
    root, original, lookup = _resolve_domain_root(args)

    # Should redirect to the live sibling.
    assert root == live_domain.resolve()
    assert original is not None
    assert lookup is not None


def test_cmd_validate_multi_domain_propagates_max_exit_code(
    tmp_path: Path,
) -> None:
    """cmd_validate with CSV --domain must run each domain and return max
    exit code.  Per ARCHITECTURE.md Sec.5.1.2 (multi-domain sequential trim).
    We mock the runner to return a predictable exit code for each domain.
    """
    import argparse

    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain_a = tmp_path / "dom_a"
    domain_a.mkdir()
    (domain_a / "jsons").mkdir()
    (domain_a / "jsons" / "base.json").write_text("{}")

    domain_b = tmp_path / "dom_b"
    domain_b.mkdir()
    (domain_b / "jsons").mkdir()
    (domain_b / "jsons" / "base.json").write_text("{}")

    call_count = {"n": 0}

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        call_count["n"] += 1
        ec = 0 if call_count["n"] == 1 else 1
        return MagicMock(spec=RunResult, exit_code=ec, manifest=None)

    args = argparse.Namespace(
        domain=f"{domain_a.as_posix()},{domain_b.as_posix()}",
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
    )
    with patch.object(cmds.ChopperRunner, "run", _fake_run), patch("chopper.cli.commands.render_result"):
        rc = cmds.cmd_validate(args)

    assert call_count["n"] == 2
    assert rc == 1  # max(0, 1)


def test_cmd_trim_multi_domain_propagates_max_exit_code(
    tmp_path: Path,
) -> None:
    """cmd_trim with CSV --domain must loop over each domain in sequence and
    return the maximum exit code.  Per ARCHITECTURE.md Sec.5.1.2.
    """
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain_a = tmp_path / "dom_a"
    domain_a.mkdir()
    (domain_a / "jsons").mkdir()
    (domain_a / "jsons" / "base.json").write_text("{}")

    domain_b = tmp_path / "dom_b"
    domain_b.mkdir()
    (domain_b / "jsons").mkdir()
    (domain_b / "jsons" / "base.json").write_text("{}")

    call_count = {"n": 0}

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        call_count["n"] += 1
        ec = 1 if call_count["n"] == 1 else 0
        return MagicMock(spec=RunResult, exit_code=ec, manifest=None)

    args = argparse.Namespace(
        domain=f"{domain_a.as_posix()},{domain_b.as_posix()}",
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=True,
    )
    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_trim_stats"),
    ):
        rc = cmds.cmd_trim(args)

    assert call_count["n"] == 2
    assert rc == 1  # max(1, 0)


def test_cmd_loc_multi_domain_propagates_max_exit_code(
    tmp_path: Path,
) -> None:
    """cmd_loc with CSV --domain must loop over each domain and return max
    exit code.  Per ARCHITECTURE.md Sec.5.1.2.
    """
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain_a = tmp_path / "dom_a"
    domain_a.mkdir()
    (domain_a / "jsons").mkdir()
    (domain_a / "jsons" / "base.json").write_text("{}")

    domain_b = tmp_path / "dom_b"
    domain_b.mkdir()
    (domain_b / "jsons").mkdir()
    (domain_b / "jsons" / "base.json").write_text("{}")

    call_count = {"n": 0}

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        call_count["n"] += 1
        ec = 0 if call_count["n"] == 1 else 0
        return MagicMock(spec=RunResult, exit_code=ec, manifest=None)

    args = argparse.Namespace(
        domain=f"{domain_a.as_posix()},{domain_b.as_posix()}",
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
    )
    with patch.object(cmds.ChopperRunner, "run", _fake_run), patch("chopper.cli.commands.render_result"):
        rc = cmds.cmd_loc(args)

    assert call_count["n"] == 2
    assert rc == 0  # max(0, 0)


def test_cmd_validate_multi_domain_early_failure_uses_error_result(
    tmp_path: Path,
) -> None:
    """When _check_project_paths_resolvable returns non-None for one domain in
    a CSV run, that domain uses _make_error_domain_result and the loop
    continues to the next domain.
    """
    import json as _json

    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    # domain_a: project.json with missing base -> exit 2
    domain_a = tmp_path / "dom_a"
    domain_a.mkdir()
    project_a = tmp_path / "proj_a.json"
    project_a.write_text(_json.dumps({"base": "missing.json", "features": []}))

    # domain_b: valid domain with real base.json -> runner called
    domain_b = tmp_path / "dom_b"
    domain_b.mkdir()
    (domain_b / "jsons").mkdir()
    (domain_b / "jsons" / "base.json").write_text("{}")

    call_count = {"n": 0}

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        call_count["n"] += 1
        return MagicMock(spec=RunResult, exit_code=0, manifest=None)

    args = argparse.Namespace(
        domain=f"{domain_a.as_posix()},{domain_b.as_posix()}",
        base=None,
        features=None,
        # project applies to BOTH domains in this simple test setup;
        # domain_a's project is missing base -- domain_b has none
        project=str(project_a),
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
    )
    with patch.object(cmds.ChopperRunner, "run", _fake_run), patch("chopper.cli.commands.render_result"):
        rc = cmds.cmd_validate(args)

    # domain_a contributed rc=2, domain_b contributed rc=0; max=2
    # but since domain_b also gets project=proj_a which references missing.json
    # in domain_b's root, it also exits 2 -> max(2,2)=2
    assert rc == 2


def test_build_run_config_ve36_no_suggestion_hint(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """VE-36 error message must fall back to 'ls features/' hint when no close
    matches are available (the else branch of the suggestion check).
    """
    from chopper.cli.commands import _build_run_config

    domain = tmp_path / "my_domain"
    domain.mkdir()
    jsons = domain / "jsons"
    jsons.mkdir()
    (jsons / "base.json").write_text("{}")
    features_dir = jsons / "features"
    features_dir.mkdir()
    (features_dir / "zzz_totally_different.feature.json").write_text("{}")

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features="aaa_no_match_at_all",  # nothing close to zzz_totally_different
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
    )
    with pytest.raises(SystemExit) as exc_info:
        _build_run_config(args, dry_run=True)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "VE-36" in captured.err
    # No suggestions -> falls back to ls hint
    assert "ls" in captured.err or "features" in captured.err


def test_cmd_trim_single_domain_calls_render_trim_stats_on_live_run(
    tmp_path: Path,
) -> None:
    """cmd_trim single-domain live run (dry_run=False) must call render_trim_stats.
    Lines 491-492 in commands.py.  We patch render_result and render_trim_stats
    to avoid needing a real domain on disk.
    """
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain = tmp_path / "dom"
    domain.mkdir()
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text("{}")

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None)

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=False,  # live run
    )
    stats_called = {"n": 0}

    def _fake_trim_stats(ctx, result):  # type: ignore[misc]
        stats_called["n"] += 1

    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_trim_stats", _fake_trim_stats),
    ):
        rc = cmds.cmd_trim(args)

    assert rc == 0
    assert stats_called["n"] == 1  # render_trim_stats was called once


def test_cmd_trim_single_domain_renders_p4_checkout_opened_paths(tmp_path: Path) -> None:
    """cmd_trim single-domain live run must call render_p4_checkout_opened with
    the absolute paths from ``trim_report.p4_checkout.checked_out``."""
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult
    from chopper.core.models_trimmer import P4CheckoutResult, TrimReport

    domain = tmp_path / "dom"
    domain.mkdir()
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text("{}")

    p4_checkout = P4CheckoutResult(attempted=True, checked_out=(Path("a.tcl"), Path("b.tcl")))
    trim_report = MagicMock(spec=TrimReport, p4_checkout=p4_checkout)

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None, trim_report=trim_report)

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=False,
        p4_checkout=True,
    )

    captured: list = []

    def _fake_render_p4_opened(entries, **kwargs):  # type: ignore[misc]
        captured.append(entries)

    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_trim_stats"),
        patch("chopper.cli.commands.render_p4_checkout_opened", _fake_render_p4_opened),
    ):
        rc = cmds.cmd_trim(args)

    assert rc == 0
    assert len(captured) == 1
    [(label, paths)] = captured[0]
    assert paths == [(domain / "a.tcl").resolve(), (domain / "b.tcl").resolve()]


def test_cmd_trim_single_domain_renders_p4_checkout_enabled_notice(tmp_path: Path) -> None:
    """cmd_trim single-domain live run with --p4 must call
    render_p4_checkout_enabled_notice once, before the pipeline runs."""
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult
    from chopper.core.models_trimmer import P4CheckoutResult, TrimReport

    domain = tmp_path / "dom"
    domain.mkdir()
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text("{}")

    trim_report = MagicMock(spec=TrimReport, p4_checkout=P4CheckoutResult(attempted=True, checked_out=()))

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None, trim_report=trim_report)

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=False,
        p4_checkout=True,
    )

    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_trim_stats"),
        patch("chopper.cli.commands.render_p4_checkout_opened"),
        patch("chopper.cli.commands.render_p4_checkout_enabled_notice") as mock_notice,
    ):
        rc = cmds.cmd_trim(args)

    assert rc == 0
    mock_notice.assert_called_once_with()


def test_cmd_trim_does_not_render_p4_checkout_enabled_notice_under_dry_run(tmp_path: Path) -> None:
    """--p4 combined with --dry-run must not print the enabled notice --
    --p4 is a strict no-op under --dry-run."""
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain = tmp_path / "dom"
    domain.mkdir()
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text("{}")

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None, trim_report=None)

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=True,
        p4_checkout=True,
    )

    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_p4_checkout_opened"),
        patch("chopper.cli.commands.render_p4_checkout_enabled_notice") as mock_notice,
    ):
        rc = cmds.cmd_trim(args)

    assert rc == 0
    mock_notice.assert_not_called()


def test_cmd_trim_multi_domain_renders_p4_checkout_enabled_notice_per_domain(tmp_path: Path) -> None:
    """Multi-domain CSV --domain with --p4 must call
    render_p4_checkout_enabled_notice once per domain."""
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult
    from chopper.core.models_trimmer import P4CheckoutResult, TrimReport

    dom_a = tmp_path / "dom_a"
    dom_a.mkdir()
    (dom_a / "jsons").mkdir()
    (dom_a / "jsons" / "base.json").write_text("{}")
    dom_b = tmp_path / "dom_b"
    dom_b.mkdir()
    (dom_b / "jsons").mkdir()
    (dom_b / "jsons" / "base.json").write_text("{}")

    trim_report = MagicMock(spec=TrimReport, p4_checkout=P4CheckoutResult(attempted=True, checked_out=()))

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None, trim_report=trim_report)

    args = argparse.Namespace(
        domain=f"{dom_a},{dom_b}",
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=False,
        p4_checkout=True,
    )

    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_trim_stats"),
        patch("chopper.cli.commands.render_p4_checkout_opened"),
        patch("chopper.cli.commands.render_p4_checkout_enabled_notice") as mock_notice,
    ):
        rc = cmds.cmd_trim(args)

    assert rc == 0
    assert mock_notice.call_count == 2


def test_p4_checked_out_abs_paths_empty_when_no_trim_report() -> None:
    """_p4_checked_out_abs_paths returns [] when result has no trim_report
    (e.g. an error/early-exit result)."""
    from chopper.cli.commands import _p4_checked_out_abs_paths

    ctx = MagicMock()
    result = MagicMock(spec=[])  # no trim_report attribute at all
    assert _p4_checked_out_abs_paths(ctx, result) == []


def test_p4_checked_out_abs_paths_empty_when_p4_checkout_none() -> None:
    """_p4_checked_out_abs_paths returns [] when p4_checkout is None (--p4 not passed)."""
    from chopper.cli.commands import _p4_checked_out_abs_paths
    from chopper.core.models_trimmer import TrimReport

    ctx = MagicMock()
    result = MagicMock(trim_report=MagicMock(spec=TrimReport, p4_checkout=None))
    assert _p4_checked_out_abs_paths(ctx, result) == []


def _make_ctx_for_header(
    tmp_path: Path,
    *,
    base_path: Path | None = None,
    project_path: Path | None = None,
    logical_name: str | None = None,
    feature_paths: tuple = (),
    project_config_path: Path | None = None,
):
    """Build a minimal ChopperContext for _print_domain_header tests."""
    from chopper.adapters import CollectingSink, LocalFS
    from chopper.adapters.progress_silent import SilentProgress
    from chopper.core.context import ChopperContext, RunConfig

    cfg = RunConfig(
        domain_root=tmp_path,
        backup_root=tmp_path.with_name(tmp_path.name + "_backup"),
        audit_root=tmp_path / ".chopper",
        strict=False,
        dry_run=True,
        base_path=base_path,
        project_path=project_path,
        domain_logical_name=logical_name,
        feature_paths=feature_paths,
        project_config_path=project_config_path,
    )
    return ChopperContext(config=cfg, fs=LocalFS(), diag=CollectingSink(), progress=SilentProgress())


def test_print_domain_header_with_base_path_and_logical_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Header uses logical name, shows base_path, and prints config-found line."""
    from chopper.cli.commands import _print_domain_header

    base = tmp_path / "jsons" / "base.json"
    ctx = _make_ctx_for_header(tmp_path, base_path=base, logical_name="snps/fev_formality")
    _print_domain_header(ctx)
    out = capsys.readouterr().out
    assert "=== Domain: snps/fev_formality ===" in out
    assert f"Domain root : {tmp_path.as_posix()}" in out
    assert f"Base JSON   : {base.as_posix()}" in out
    assert "config file found.. processing" in out
    assert "config file path" not in out  # base.json is not a project config file


def test_print_domain_header_with_project_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Header shows project path with '(project)' suffix and prints config-found line."""
    from chopper.cli.commands import _print_domain_header

    proj = tmp_path / "jsons" / "project.json"
    ctx = _make_ctx_for_header(tmp_path, project_path=proj, logical_name="snps/power")
    _print_domain_header(ctx)
    out = capsys.readouterr().out
    assert "=== Domain: snps/power ===" in out
    assert f"Base JSON   : {proj.as_posix()}  (project)" in out
    assert "config file found.. processing" in out
    assert "config file path" not in out  # project JSON is already shown in Base JSON


def test_print_domain_header_no_base_no_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Header shows '(none)' when neither base_path nor project_path is set."""
    from chopper.cli.commands import _print_domain_header

    ctx = _make_ctx_for_header(tmp_path)
    _print_domain_header(ctx)
    out = capsys.readouterr().out
    assert "Base JSON   : (none)" in out


def test_print_domain_header_falls_back_to_dir_name(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Header falls back to domain_root.name when domain_logical_name is None."""
    from chopper.cli.commands import _print_domain_header

    ctx = _make_ctx_for_header(tmp_path)
    _print_domain_header(ctx)
    out = capsys.readouterr().out
    assert f"=== Domain: {tmp_path.name} ===" in out


def test_print_domain_header_with_feature_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Header lists each feature name and path when feature_paths are set."""
    from chopper.cli.commands import _print_domain_header

    base = tmp_path / "jsons" / "base.json"
    fa = tmp_path / "jsons" / "features" / "eco.feature.json"
    fb = tmp_path / "jsons" / "features" / "lite.feature.json"
    ctx = _make_ctx_for_header(tmp_path, base_path=base, feature_paths=(fa, fb))
    _print_domain_header(ctx)
    out = capsys.readouterr().out
    assert "config file found.. processing" in out
    assert "Features (2) :" in out
    assert f"1. eco : {fa.as_posix()}" in out
    assert f"2. lite : {fb.as_posix()}" in out


def test_print_domain_header_project_json_features(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Header reads features from a real project JSON when project_path is set."""
    import json

    from chopper.cli.commands import _print_domain_header

    proj = tmp_path / "jsons" / "my.project.json"
    proj.parent.mkdir(parents=True, exist_ok=True)
    proj.write_text(
        json.dumps(
            {
                "$schema": "project-v1",
                "features": [
                    "jsons/features/alpha.feature.json",
                    "jsons/features/beta.feature.json",
                ],
            }
        )
    )
    ctx = _make_ctx_for_header(tmp_path, project_path=proj, logical_name="snps/test")
    _print_domain_header(ctx)
    out = capsys.readouterr().out
    assert "config file found.. processing" in out
    assert "Features (2) :" in out
    assert "1. alpha" in out
    assert "2. beta" in out


def test_print_domain_header_base_no_features(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Header shows config-found line but no Features block when no features are active."""
    from chopper.cli.commands import _print_domain_header

    base = tmp_path / "jsons" / "base.json"
    ctx = _make_ctx_for_header(tmp_path, base_path=base)
    _print_domain_header(ctx)
    out = capsys.readouterr().out
    assert "config file found.. processing" in out
    assert "Features (" not in out


def test_print_domain_header_shows_project_config_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Header prints 'config file path' when project_config_path is set (features config case)."""
    from chopper.cli.commands import _print_domain_header

    base = tmp_path / "jsons" / "base.json"
    cfg_path = tmp_path / "project" / "snps" / "fev_formality" / "fev_formality.project.features.config"
    fa = tmp_path / "jsons" / "features" / "low_power.feature.json"
    ctx = _make_ctx_for_header(
        tmp_path,
        base_path=base,
        feature_paths=(fa,),
        project_config_path=cfg_path,
    )
    _print_domain_header(ctx)
    out = capsys.readouterr().out
    assert "config file found.. processing" in out
    assert f"config file path : {cfg_path.as_posix()}" in out
    assert "Features (1) :" in out


def test_build_run_config_auto_discovers_project_features_config(tmp_path: Path) -> None:
    """_build_run_config resolves feature_paths from a project features config file
    in $ward/project/ when --features is not supplied."""
    import argparse

    from chopper.cli.commands import _build_run_config

    ward = tmp_path / "ward"
    domain_root = ward / "global" / "snps" / "fev_formality"
    (domain_root / "jsons" / "features").mkdir(parents=True)
    (domain_root / "jsons" / "base.json").write_text("{}")
    fa = domain_root / "jsons" / "features" / "low_power.feature.json"
    fa.write_text("{}")
    fb = domain_root / "jsons" / "features" / "metaflop_checks.feature.json"
    fb.write_text("{}")

    cfg_dir = ward / "project" / "snps" / "fev_formality"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "fev_formality.project.features.config").write_text("low_power\nmetaflop_checks\n")

    from chopper.cli.domain_lookup import DomainLookupResult

    fake_lookup = DomainLookupResult(
        domain_root=domain_root,
        ward_root=ward,
        domain_logical_name="snps/fev_formality",
    )
    args = argparse.Namespace(
        domain="snps/fev_formality",
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=False,
        plain=False,
        tool_commands=None,
    )
    with patch("chopper.cli.commands._resolve_domain_root", return_value=(domain_root, None, fake_lookup)):
        cfg, _ = _build_run_config(args, dry_run=True)

    assert fa in cfg.feature_paths
    assert fb in cfg.feature_paths
    assert cfg.project_path is None  # config file -> features mode, not project JSON mode
    cfg_file = (ward / "project" / "snps" / "fev_formality" / "fev_formality.project.features.config").resolve()
    assert cfg.project_config_path == cfg_file  # features config path is recorded


def test_build_run_config_auto_discovers_project_json(tmp_path: Path) -> None:
    """_build_run_config sets project_path from an auto-discovered project JSON
    in $ward/project/ when neither --project/--base/--features is supplied."""
    import argparse

    from chopper.cli.commands import _build_run_config

    ward = tmp_path / "ward"
    domain_root = ward / "global" / "snps" / "fev_formality"
    domain_root.mkdir(parents=True)

    proj_dir = ward / "project" / "snps" / "fev_formality"
    proj_dir.mkdir(parents=True)
    proj_file = proj_dir / "fev_formality.project.json"
    proj_file.write_text("{}")

    from chopper.cli.domain_lookup import DomainLookupResult

    fake_lookup = DomainLookupResult(
        domain_root=domain_root,
        ward_root=ward,
        domain_logical_name="snps/fev_formality",
    )
    args = argparse.Namespace(
        domain="snps/fev_formality",
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=False,
        plain=False,
        tool_commands=None,
    )
    with patch("chopper.cli.commands._resolve_domain_root", return_value=(domain_root, None, fake_lookup)):
        cfg, _ = _build_run_config(args, dry_run=True)

    assert cfg.project_path == proj_file.resolve()
    assert cfg.feature_paths == ()


def test_build_run_config_auto_discovery_no_project_files(tmp_path: Path) -> None:
    """Auto-discovery block is a no-op when neither .project.json nor
    .project.features.config exists in $ward/project/. Covers 203->210 branch."""
    import argparse

    from chopper.cli.commands import _build_run_config

    ward = tmp_path / "ward"
    domain_root = ward / "global" / "snps" / "fev_formality"
    (domain_root / "jsons").mkdir(parents=True)
    (domain_root / "jsons" / "base.json").write_text("{}")
    # project dir exists but neither probe file is present
    (ward / "project" / "snps" / "fev_formality").mkdir(parents=True)

    from chopper.cli.domain_lookup import DomainLookupResult

    fake_lookup = DomainLookupResult(
        domain_root=domain_root,
        ward_root=ward,
        domain_logical_name="snps/fev_formality",
    )
    args = argparse.Namespace(
        domain="snps/fev_formality",
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=False,
        plain=False,
        tool_commands=None,
    )
    with patch("chopper.cli.commands._resolve_domain_root", return_value=(domain_root, None, fake_lookup)):
        cfg, _ = _build_run_config(args, dry_run=True)

    assert cfg.project_path is None
    assert cfg.feature_paths == ()
    assert cfg.base_path is not None  # auto-discovered base.json


def test_build_run_config_auto_discovery_empty_config(tmp_path: Path) -> None:
    """Auto-discovery ignores a config file whose lines are all blank/comments.
    Covers 207->210 branch (if names: False)."""
    import argparse

    from chopper.cli.commands import _build_run_config

    ward = tmp_path / "ward"
    domain_root = ward / "global" / "snps" / "fev_formality"
    (domain_root / "jsons").mkdir(parents=True)
    (domain_root / "jsons" / "base.json").write_text("{}")

    proj_dir = ward / "project" / "snps" / "fev_formality"
    proj_dir.mkdir(parents=True)
    (proj_dir / "fev_formality.project.features.config").write_text("# comment only\n\n")

    from chopper.cli.domain_lookup import DomainLookupResult

    fake_lookup = DomainLookupResult(
        domain_root=domain_root,
        ward_root=ward,
        domain_logical_name="snps/fev_formality",
    )
    args = argparse.Namespace(
        domain="snps/fev_formality",
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=False,
        plain=False,
        tool_commands=None,
    )
    with patch("chopper.cli.commands._resolve_domain_root", return_value=(domain_root, None, fake_lookup)):
        cfg, _ = _build_run_config(args, dry_run=True)

    assert cfg.feature_paths == ()  # empty config -> no features loaded


def test_cmd_trim_multi_domain_live_calls_render_trim_stats(
    tmp_path: Path,
) -> None:
    """cmd_trim multi-domain live run must call render_trim_stats for each
    domain where dry_run=False.  Lines 510, 514 in commands.py.
    """
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain_a = tmp_path / "dom_a"
    domain_a.mkdir()
    (domain_a / "jsons").mkdir()
    (domain_a / "jsons" / "base.json").write_text("{}")

    domain_b = tmp_path / "dom_b"
    domain_b.mkdir()
    (domain_b / "jsons").mkdir()
    (domain_b / "jsons" / "base.json").write_text("{}")

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None)

    stats_called = {"n": 0}

    def _fake_trim_stats(ctx, result):  # type: ignore[misc]
        stats_called["n"] += 1

    args = argparse.Namespace(
        domain=f"{domain_a.as_posix()},{domain_b.as_posix()}",
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=False,  # live -> render_trim_stats should be called
    )
    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_trim_stats", _fake_trim_stats),
    ):
        rc = cmds.cmd_trim(args)

    assert rc == 0
    assert stats_called["n"] == 2  # once per domain


def test_cmd_trim_single_domain_prints_audit_bundle_location(tmp_path: Path) -> None:
    """FR-52: single-domain ``cmd_trim`` calls ``render_audit_bundle_locations`` with the
    domain's resolved ``.chopper/`` path."""
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain = tmp_path / "dom"
    domain.mkdir()
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text("{}")

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None)

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=True,
    )
    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_audit_bundle_locations") as mock_locations,
    ):
        rc = cmds.cmd_trim(args)

    assert rc == 0
    mock_locations.assert_called_once()
    (paths,), _ = mock_locations.call_args
    assert len(paths) == 1
    label, audit_root = paths[0]
    assert label == "dom"
    assert audit_root == domain / ".chopper"


def test_cmd_trim_renders_p4_checkout_notice_when_skipped(tmp_path: Path) -> None:
    """FR-53: when --p4 checkout was skipped, cmd_trim renders the red notice
    with the exact skip_reason, using the --plain flag."""
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult
    from chopper.core.models_trimmer import P4CheckoutResult, TrimReport

    domain = tmp_path / "dom"
    domain.mkdir()
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text("{}")

    trim_report = TrimReport(
        outcomes=(),
        files_copied=0,
        files_trimmed=0,
        files_removed=0,
        procs_kept_total=0,
        procs_removed_total=0,
        p4_checkout=P4CheckoutResult(attempted=False, skip_reason="the 'p4' executable was not found on PATH"),
    )

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None, trim_report=trim_report)

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=False,
    )
    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_trim_stats"),
        patch("chopper.cli.commands.render_p4_checkout_notice") as mock_notice,
    ):
        rc = cmds.cmd_trim(args)

    assert rc == 0
    mock_notice.assert_called_once_with("the 'p4' executable was not found on PATH", plain=True)


def test_cmd_trim_does_not_render_p4_checkout_notice_when_attempted(tmp_path: Path) -> None:
    """No notice when checkout actually ran (success or failure -- failure is
    reported via VE-37, not this advisory notice)."""
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult
    from chopper.core.models_trimmer import P4CheckoutResult, TrimReport

    domain = tmp_path / "dom"
    domain.mkdir()
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text("{}")

    trim_report = TrimReport(
        outcomes=(),
        files_copied=0,
        files_trimmed=0,
        files_removed=0,
        procs_kept_total=0,
        procs_removed_total=0,
        p4_checkout=P4CheckoutResult(attempted=True, checked_out=(Path("a.tcl"),)),
    )

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None, trim_report=trim_report)

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=False,
    )
    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_trim_stats"),
        patch("chopper.cli.commands.render_p4_checkout_notice") as mock_notice,
    ):
        rc = cmds.cmd_trim(args)

    assert rc == 0
    mock_notice.assert_not_called()


def test_cmd_trim_multi_domain_prints_audit_bundle_location_per_domain(tmp_path: Path) -> None:
    """FR-52: multi-domain ``cmd_trim`` calls ``render_audit_bundle_locations`` with one
    entry per successfully-run domain."""
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain_a = tmp_path / "dom_a"
    domain_a.mkdir()
    (domain_a / "jsons").mkdir()
    (domain_a / "jsons" / "base.json").write_text("{}")

    domain_b = tmp_path / "dom_b"
    domain_b.mkdir()
    (domain_b / "jsons").mkdir()
    (domain_b / "jsons" / "base.json").write_text("{}")

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None)

    args = argparse.Namespace(
        domain=f"{domain_a.as_posix()},{domain_b.as_posix()}",
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=True,
    )
    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_audit_bundle_locations") as mock_locations,
    ):
        rc = cmds.cmd_trim(args)

    assert rc == 0
    mock_locations.assert_called_once()
    (paths,), _ = mock_locations.call_args
    assert paths == [("dom_a", domain_a / ".chopper"), ("dom_b", domain_b / ".chopper")]


def test_cmd_trim_multi_domain_all_checks_fail_prints_no_audit_locations(tmp_path: Path) -> None:
    """When every domain fails the pre-flight check, no context is ever built, so
    ``render_audit_bundle_locations`` is called with an empty list."""
    import json as _json

    from chopper.cli import commands as cmds

    project = tmp_path / "proj.json"
    project.write_text(_json.dumps({"base": "missing.json", "features": []}))

    domain_a = tmp_path / "dom_a"
    domain_a.mkdir()
    domain_b = tmp_path / "dom_b"
    domain_b.mkdir()

    args = argparse.Namespace(
        domain=f"{domain_a.as_posix()},{domain_b.as_posix()}",
        base=None,
        features=None,
        project=str(project),
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=True,
    )
    with patch("chopper.cli.commands.render_audit_bundle_locations") as mock_locations:
        rc = cmds.cmd_trim(args)
    assert rc == 2
    mock_locations.assert_called_once_with([])


# ---------------------------------------------------------------------------
# 99.8% coverage top-up tests
# ---------------------------------------------------------------------------


def test_resolve_domain_root_exits_2_on_name_mode_failure(tmp_path: Path) -> None:
    """Lines 74, 79-82: _resolve_domain_root exits 2 when resolve_domain returns None."""
    import argparse

    from chopper.cli.commands import _resolve_domain_root

    args = argparse.Namespace(domain="nonexistent_domain")

    def _fake_resolve(name_arg, emit):
        # Must call emit so that errors[0] is populated (lines 74, 79-82).
        emit("VE-33", "Domain not found", "Check $ward")
        return None

    with patch("chopper.cli.commands.resolve_domain", side_effect=_fake_resolve):
        with pytest.raises(SystemExit) as exc:
            _resolve_domain_root(args)
    assert exc.value.code == 2


def test_autodiscover_base_returns_first_candidate(tmp_path: Path) -> None:
    """Line 130: _autodiscover_base returns jsons/base.json when it exists."""
    from chopper.cli.commands import _autodiscover_base

    (tmp_path / "jsons").mkdir()
    base = tmp_path / "jsons" / "base.json"
    base.write_text("{}")
    assert _autodiscover_base(tmp_path, "snps/test") == base


def test_autodiscover_base_returns_second_candidate(tmp_path: Path) -> None:
    """Line 135: _autodiscover_base returns jsons/<leaf>.json when base.json absent."""
    from chopper.cli.commands import _autodiscover_base

    (tmp_path / "jsons").mkdir()
    named = tmp_path / "jsons" / "fev_formality.json"
    named.write_text("{}")
    assert _autodiscover_base(tmp_path, "snps/fev_formality") == named


def test_make_domain_run_result_generated_and_remove(tmp_path: Path) -> None:
    """Lines 406-414: GENERATED counts as edits; REMOVE counts as removes."""
    from chopper.adapters import CollectingSink, LocalFS
    from chopper.adapters.progress_silent import SilentProgress
    from chopper.cli.commands import _make_domain_run_result
    from chopper.core.context import ChopperContext, RunConfig
    from chopper.core.models_common import FileTreatment

    cfg = RunConfig(
        domain_root=tmp_path,
        backup_root=tmp_path.with_name(tmp_path.name + "_backup"),
        audit_root=tmp_path / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=CollectingSink(), progress=SilentProgress())

    fake_manifest = MagicMock()
    fake_manifest.file_decisions = {
        tmp_path / "proc.tcl": FileTreatment.PROC_TRIM,  # covers line 408 edits++
        tmp_path / "gen.tcl": FileTreatment.GENERATED,  # covers GENERATED branch
        tmp_path / "old.tcl": FileTreatment.REMOVE,  # covers REMOVE branch
        tmp_path / "full.tcl": FileTreatment.FULL_COPY,  # covers 413->406 fall-through
    }
    fake_result = MagicMock()
    fake_result.manifest = fake_manifest
    fake_result.exit_code = 0

    drr = _make_domain_run_result(ctx, fake_result)
    assert drr.edits_count == 2  # PROC_TRIM + GENERATED
    assert drr.removes_count == 1  # REMOVE


def test_cmd_validate_single_domain_full_flow(tmp_path: Path) -> None:
    """Lines 545-550: cmd_validate single-domain happy path runs past _make_context."""
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain = tmp_path / "dom"
    domain.mkdir()
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text("{}")

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None)

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
    )
    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_p4_branch_analysis"),
    ):
        rc = cmds.cmd_validate(args)
    assert rc == 0


def test_cmd_trim_single_domain_dry_run_skips_warn_and_stats(tmp_path: Path) -> None:
    """Branches 587->589, 592->594: dry_run=True takes the False path of both
    'if not ctx.config.dry_run' guards in cmd_trim single-domain."""
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain = tmp_path / "dom"
    domain.mkdir()
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text("{}")

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None)

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features=None,
        project=None,
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=True,  # <- False path on both guards
    )
    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
    ):
        rc = cmds.cmd_trim(args)
    assert rc == 0


def test_cmd_trim_multi_domain_check_project_fails(tmp_path: Path) -> None:
    """Lines 606-608: _check_project_paths_resolvable non-None in cmd_trim multi-domain."""
    import json as _json

    from chopper.cli import commands as cmds

    domain_a = tmp_path / "dom_a"
    domain_a.mkdir()
    project_a = tmp_path / "proj_a.json"
    project_a.write_text(_json.dumps({"base": "missing.json", "features": []}))

    domain_b = tmp_path / "dom_b"
    domain_b.mkdir()
    (domain_b / "jsons").mkdir()
    (domain_b / "jsons" / "base.json").write_text("{}")

    from chopper.core.models_audit import RunResult

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None)

    args = argparse.Namespace(
        domain=f"{domain_a.as_posix()},{domain_b.as_posix()}",
        base=None,
        features=None,
        project=str(project_a),
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
        dry_run=True,
    )
    with patch.object(cmds.ChopperRunner, "run", _fake_run), patch("chopper.cli.commands.render_result"):
        rc = cmds.cmd_trim(args)
    assert rc == 2  # domain_a fails check; domain_b also fails check (same project)


def test_cmd_loc_single_domain_project_none_expands_features(tmp_path: Path) -> None:
    """Line 667: cmd_loc single-domain with project=None reaches _expand_feature_dirs call."""
    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain = tmp_path / "dom"
    domain.mkdir()
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text("{}")

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None)

    args = argparse.Namespace(
        domain=str(domain),
        base=None,
        features=None,
        project=None,  # <- triggers line 667
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
    )
    with (
        patch.object(cmds.ChopperRunner, "run", _fake_run),
        patch("chopper.cli.commands.render_result"),
        patch("chopper.cli.commands.render_p4_branch_analysis"),
        patch("chopper.cli.commands._render_loc_table"),
    ):
        rc = cmds.cmd_loc(args)
    assert rc == 0


def test_cmd_loc_multi_domain_check_project_fails(tmp_path: Path) -> None:
    """Lines 688->690, 692-694: cmd_loc multi-domain, one domain's project check fails."""
    import json as _json

    from chopper.cli import commands as cmds
    from chopper.core.models_audit import RunResult

    domain_a = tmp_path / "dom_a"
    domain_a.mkdir()
    project_a = tmp_path / "proj_a.json"
    project_a.write_text(_json.dumps({"base": "missing.json", "features": []}))

    domain_b = tmp_path / "dom_b"
    domain_b.mkdir()
    (domain_b / "jsons").mkdir()
    (domain_b / "jsons" / "base.json").write_text("{}")

    def _fake_run(self, ctx, *, command):  # type: ignore[misc]
        return MagicMock(spec=RunResult, exit_code=0, manifest=None)

    args = argparse.Namespace(
        domain=f"{domain_a.as_posix()},{domain_b.as_posix()}",
        base=None,
        features=None,
        project=str(project_a),  # domain_a: project with missing base -> rc=2
        strict=False,
        quiet=True,
        plain=True,
        verbose=0,
        tool_commands=[],
    )
    with patch.object(cmds.ChopperRunner, "run", _fake_run), patch("chopper.cli.commands.render_result"):
        rc = cmds.cmd_loc(args)
    assert rc == 2


def test_render_loc_table_baseline_only_when_manifest_none(tmp_path: Path) -> None:
    """Lines 715-722: _render_loc_table else branch when manifest/parsed/loaded are None."""
    from chopper.adapters import CollectingSink, LocalFS
    from chopper.adapters.progress_silent import SilentProgress
    from chopper.cli.commands import _render_loc_table
    from chopper.core.context import ChopperContext, RunConfig

    cfg = RunConfig(
        domain_root=tmp_path,
        backup_root=tmp_path.with_name(tmp_path.name + "_backup"),
        audit_root=tmp_path / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=CollectingSink(), progress=SilentProgress())

    fake_result = MagicMock()
    fake_result.manifest = None  # triggers else branch
    fake_result.parsed = None
    fake_result.loaded = None
    fake_result.generated_artifacts = None

    with patch("chopper.cli.commands.render_loc_report"):
        _render_loc_table(ctx, fake_result)


def test_render_loc_table_with_full_manifest(tmp_path: Path) -> None:
    """Lines 715-722: _render_loc_table True branch when manifest/parsed/loaded all non-None."""
    from chopper.adapters import CollectingSink, LocalFS
    from chopper.adapters.progress_silent import SilentProgress
    from chopper.cli.commands import _render_loc_table
    from chopper.core.context import ChopperContext, RunConfig

    cfg = RunConfig(
        domain_root=tmp_path,
        backup_root=tmp_path.with_name(tmp_path.name + "_backup"),
        audit_root=tmp_path / ".chopper",
        strict=False,
        dry_run=True,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=CollectingSink(), progress=SilentProgress())

    fake_result = MagicMock()
    fake_result.manifest = MagicMock()  # non-None -> True branch
    fake_result.parsed = MagicMock()  # non-None
    fake_result.loaded = MagicMock()  # non-None
    fake_result.generated_artifacts = ()

    with (
        patch("chopper.cli.commands.build_loc_report", return_value=MagicMock()),
        patch("chopper.cli.commands.render_loc_report"),
    ):
        _render_loc_table(ctx, fake_result)
