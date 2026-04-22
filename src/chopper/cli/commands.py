"""Subcommand handlers.

Each ``cmd_*`` function takes the parsed :class:`argparse.Namespace`
and returns a process exit code. The handlers own the translation
from CLI flags to :class:`RunConfig` and :class:`ChopperContext`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from chopper.adapters import (
    CollectingSink,
    LocalFS,
    RichProgress,
    RichUnavailableError,
    SilentProgress,
)
from chopper.cli.render import render_result
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.protocols import ProgressSink
from chopper.orchestrator import ChopperRunner

__all__ = ["cmd_cleanup", "cmd_trim", "cmd_validate"]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_domain_root(args: argparse.Namespace) -> Path:
    raw = getattr(args, "domain", None)
    if raw is None:
        return Path.cwd().resolve()
    return Path(raw).resolve()


def _make_progress(args: argparse.Namespace) -> ProgressSink:
    if args.quiet:
        return SilentProgress()
    try:
        return RichProgress(plain=args.plain)
    except RichUnavailableError:
        return SilentProgress()


def _build_run_config(args: argparse.Namespace, *, dry_run: bool) -> RunConfig:
    domain_root = _resolve_domain_root(args)
    backup_root = domain_root.with_name(domain_root.name + "_backup")
    audit_root = domain_root / ".chopper"

    project_path: Path | None = None
    base_path: Path | None = None
    feature_paths: tuple[Path, ...] = ()

    if getattr(args, "project", None) is not None:
        project_path = Path(args.project).resolve()
    else:
        if getattr(args, "base", None) is not None:
            base_path = Path(args.base).resolve()
        if getattr(args, "features", None):
            feature_paths = tuple(Path(p).resolve() for p in args.features.split(",") if p.strip())

    return RunConfig(
        domain_root=domain_root,
        backup_root=backup_root,
        audit_root=audit_root,
        strict=args.strict,
        dry_run=dry_run,
        project_path=project_path,
        base_path=base_path,
        feature_paths=feature_paths,
    )


def _make_context(args: argparse.Namespace, *, dry_run: bool) -> tuple[ChopperContext, CollectingSink]:
    sink = CollectingSink()
    cfg = _build_run_config(args, dry_run=dry_run)
    ctx = ChopperContext(
        config=cfg,
        fs=LocalFS(),
        diag=sink,
        progress=_make_progress(args),
    )
    return ctx, sink


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    """Run the pipeline in dry-run mode (validate only; no writes)."""

    ctx, sink = _make_context(args, dry_run=True)
    result = ChopperRunner().run(ctx, command="validate")
    render_result(result, sink.snapshot())
    return result.exit_code


def cmd_trim(args: argparse.Namespace) -> int:
    """Execute the full trim pipeline."""

    ctx, sink = _make_context(args, dry_run=bool(getattr(args, "dry_run", False)))
    result = ChopperRunner().run(ctx, command="trim")
    render_result(result, sink.snapshot())
    return result.exit_code


def cmd_cleanup(args: argparse.Namespace) -> int:
    """Remove ``<domain>_backup/`` after the trim window is complete.

    Refuses to run without ``--confirm``. Does not enter
    :class:`ChopperRunner`; this is a direct filesystem operation
    per DAY0_REVIEW A7.
    """

    if not getattr(args, "confirm", False):
        print("chopper cleanup: --confirm is required; refusing to remove backup")
        return 2

    domain_root = _resolve_domain_root(args)
    backup_root = domain_root.with_name(domain_root.name + "_backup")
    if not backup_root.exists():
        print(f"chopper cleanup: no backup to remove at {backup_root.as_posix()}")
        return 0

    import shutil

    shutil.rmtree(backup_root)
    print(f"chopper cleanup: removed {backup_root.as_posix()}")
    return 0
