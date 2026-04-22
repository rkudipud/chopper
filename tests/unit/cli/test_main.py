"""Unit tests for :mod:`chopper.cli.main` argument parsing."""

from __future__ import annotations

import pytest

from chopper.cli.main import build_parser


def test_build_parser_has_three_subcommands() -> None:
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


def test_trim_requires_base_or_project() -> None:
    from chopper.cli.main import main

    with pytest.raises(SystemExit):
        main(["trim"])
