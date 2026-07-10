"""Unit tests for :mod:`chopper.cli.main` argument parsing."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

from chopper.cli.main import build_parser
from chopper.core.models_audit import InternalError


def test_build_parser_has_four_subcommands() -> None:
    parser = build_parser()
    # Parse each subcommand with minimum required flags to confirm dispatch wiring.
    ns = parser.parse_args(["validate", "--base", "base.json"])
    assert ns.command == "validate"
    assert callable(ns.func)

    ns = parser.parse_args(["trim", "--base", "base.json"])
    assert ns.command == "trim"
    assert ns.dry_run is False

    ns = parser.parse_args(["cleanup", "--confirm"])
    assert ns.command == "cleanup"
    assert ns.confirm is True


def test_trim_accepts_dry_run_flag() -> None:
    ns = build_parser().parse_args(["trim", "--base", "base.json", "--dry-run"])
    assert ns.dry_run is True


def test_trim_p4_flag_defaults_false_and_is_settable() -> None:
    ns = build_parser().parse_args(["trim", "--base", "base.json"])
    assert ns.p4_checkout is False

    ns = build_parser().parse_args(["trim", "--base", "base.json", "--p4"])
    assert ns.p4_checkout is True


def test_p4_flag_not_available_on_other_subcommands() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["validate", "--base", "base.json", "--p4"])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["loc", "--base", "base.json", "--p4"])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["cleanup", "--confirm", "--p4"])


def test_global_flags_are_parsed_before_subcommand() -> None:
    ns = build_parser().parse_args(["-v", "-q", "--plain", "--strict", "validate", "--base", "base.json"])
    assert ns.verbose == 1
    assert ns.quiet is True
    assert ns.plain is True
    assert ns.strict is True


def test_repeated_verbose_increments_count() -> None:
    ns = build_parser().parse_args(["-vv", "validate", "--base", "base.json"])
    assert ns.verbose == 2


def test_missing_subcommand_is_error() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_project_mutually_exclusive_with_base_enforced_in_main() -> None:
    from chopper.cli.main import main

    with pytest.raises(SystemExit):
        main(["trim", "--project", "p.json", "--base", "b.json"])


def test_trim_requires_base_or_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without --base or --project, trim auto-discovers base JSON.

    When auto-discovery fails (no jsons/base.json in cwd), VE-35 fires
    and the process exits with code 2.  The guard has moved from argparse
    into _build_run_config (VE-35 auto-discovery failure).
    """
    from chopper.cli.main import main

    monkeypatch.chdir(tmp_path)  # tmp_path has no jsons/base.json
    with pytest.raises(SystemExit):
        main(["trim"])


def test_version_flag_prints_version_and_exits(capsys: pytest.CaptureFixture[str]) -> None:
    from chopper import __version__

    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert f"chopper {__version__}" in captured.out


def test_version_flag_does_not_require_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["--version"])
    assert exc_info.value.code == 0


def test_main_pre_runner_exception_writes_internal_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    main_module = import_module("chopper.cli.main")

    def _boom(args):  # noqa: ANN001, ARG001
        raise RuntimeError("synthetic setup failure")

    def _fake_internal_error(ctx, *, run_id, exc):  # noqa: ANN001, ARG001
        return InternalError(kind=type(exc).__name__, message=str(exc), log_path=Path(".chopper/internal-error.log"))

    monkeypatch.setattr(main_module, "cmd_cleanup", _boom)
    monkeypatch.setattr(main_module, "write_internal_error_log", _fake_internal_error)

    assert main_module.main(["cleanup"]) == 1
    captured = capsys.readouterr()
    assert "[chopper] fatal: RuntimeError: synthetic setup failure" in captured.err
    assert (
        "[chopper] crash log: .chopper\\internal-error.log" in captured.err
        or "[chopper] crash log: .chopper/internal-error.log" in captured.err
    )
