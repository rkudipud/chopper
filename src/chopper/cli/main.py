"""Chopper CLI entry point.

``chopper [<global options>] <subcommand> [<subcommand options>]``

This module parses and dispatches; subcommand behaviour lives in
:mod:`chopper.cli.commands`.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Sequence

from chopper.audit.internal_error import write_internal_error_log
from chopper.cli.commands import cmd_cleanup, cmd_mcp_serve, cmd_trim, cmd_validate

__all__ = ["build_parser", "main"]


_DESCRIPTION = (
    "Chopper — EDA TFM domain trimming tool.\n"
    "\n"
    "Trims EDA tool flow domains to project-specific subsets using JSON\n"
    "configuration. Supports whole-file (F1), proc-level (F2), and run-file\n"
    "generation (F3) capabilities."
)


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level :class:`argparse.ArgumentParser`."""

    parser = argparse.ArgumentParser(
        prog="chopper",
        description=_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (-v=INFO, -vv=DEBUG)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output (CI / grid)")
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Disable Rich rendering and ANSI colors; use plain text output",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any warning is present (does not rewrite severity)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- validate ----------------------------------------------------------
    p_validate = subparsers.add_parser("validate", help="Validate JSON inputs against domain structure")
    _add_input_args(p_validate)
    p_validate.set_defaults(func=cmd_validate)

    # --- trim --------------------------------------------------------------
    p_trim = subparsers.add_parser("trim", help="Execute the full trim pipeline")
    _add_input_args(p_trim)
    p_trim.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help=("Compile, trace, run synthetic post-trim validation, and emit reports without modifying domain files"),
    )
    p_trim.set_defaults(func=cmd_trim)

    # --- cleanup -----------------------------------------------------------
    p_cleanup = subparsers.add_parser("cleanup", help="Remove domain backup after the trim window")
    p_cleanup.add_argument("--domain", help="Domain root path (default: current directory)")
    p_cleanup.add_argument(
        "--confirm",
        action="store_true",
        help="Required confirmation flag (cleanup refuses to run without it)",
    )
    p_cleanup.set_defaults(func=cmd_cleanup)

    # --- mcp-serve ---------------------------------------------------------
    p_mcp = subparsers.add_parser(
        "mcp-serve",
        help="Start a stdio-only Model Context Protocol server (read-only tools)",
    )
    p_mcp.set_defaults(func=cmd_mcp_serve)

    return parser


def _add_input_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--domain", help="Domain root path (default: current directory)")
    sub.add_argument("--base", help="Path to base JSON (required unless --project is used)")
    sub.add_argument(
        "--features",
        help="Comma-separated ordered list of feature JSON paths",
    )
    sub.add_argument(
        "--project",
        help="Path to project JSON (mutually exclusive with --base/--features)",
    )
    sub.add_argument(
        "--tool-commands",
        action="append",
        default=[],
        metavar="FILE",
        help=(
            "Path to a plain-text file of known external tool-command names "
            "(whitespace-separated, '#' line comments). Repeatable. Each file "
            "extends the built-in tool-command pool so P4 trace emits TI-01 "
            "known-tool-command instead of TW-02 unresolved-proc-call for "
            "listed names. See architecture doc §3.10."
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint. Returns a process exit code.

    The runner has its own ``try/except`` that maps service-level
    exceptions to exit 3 + ``.chopper/internal-error.log``. This outer
    guard catches anything escaping *before* the runner is entered
    (config parsing, ctx construction, importable misconfiguration,
    etc.) and returns exit 1 — the failure is outside the runner's
    contract so it cannot be exit 3, and a synthetic crash log is
    still written so the user has an artifact to attach to a bug
    report. ``argparse`` errors raise :class:`SystemExit` and bypass
    this guard (exit 2, intentional).
    """

    parser = build_parser()
    args = parser.parse_args(argv)

    # Mutual exclusivity: --project vs --base/--features.
    if getattr(args, "command", None) in ("validate", "trim"):
        if args.project and (args.base or args.features):
            parser.error("--project is mutually exclusive with --base / --features")
        if not args.project and not args.base:
            parser.error("one of --base or --project is required")

    try:
        exit_code: int = args.func(args)
        return exit_code
    except SystemExit:
        # argparse / explicit sys.exit — propagate without rewriting.
        raise
    except Exception as exc:  # noqa: BLE001 — last-resort guard
        # Pre-runner programmer error. We have no ChopperContext, so
        # the writer falls back to ``Path.cwd() / '.chopper'`` for the
        # log location. Exit 1 (per IMPROVEMENTS.md D2) — the failure
        # is outside the runner's exit-3 contract.
        run_id = uuid.uuid4().hex
        internal = write_internal_error_log(None, run_id=run_id, exc=exc)
        sys.stderr.write(
            f"[chopper] fatal: {internal.kind}: {internal.message}\n"
            f"[chopper] crash log: {internal.log_path if internal.log_path else '(could not write)'}\n"
        )
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
