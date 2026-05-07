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
from chopper.cli.render import render_cleanup_message, render_result
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.protocols import ProgressSink
from chopper.orchestrator import ChopperRunner

__all__ = ["cmd_cleanup", "cmd_mcp_serve", "cmd_trim", "cmd_validate"]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_domain_root(args: argparse.Namespace) -> tuple[Path, Path | None]:
    """Resolve the operational domain root.

    Per ``technical_docs/ARCHITECTURE.md`` §5.1 (Domain-root resolution),
    a single two-step rule applies:

    1. **Pick the candidate.** If ``--domain`` is provided, the candidate
       is ``Path(args.domain).resolve()`` and cwd is not consulted.
       Otherwise the candidate is ``Path.cwd().resolve()``.
    2. **Conditional ``_backup`` redirect.** If the candidate's basename
       ends in ``_backup`` *and* the stripped sibling exists as a
       directory, the operational domain root becomes that sibling and
       the original candidate is reported as the previous-run snapshot
       (caller emits ``VI-03 domain-suffix-strip-applied``). The
       redirect is single-shot: ``foo_backup_backup`` redirects to
       ``foo_backup`` if and only if ``foo_backup/`` exists. If the
       stripped sibling does not exist on disk, the candidate is
       returned unchanged — a coincidentally-named domain is honored
       as-is.

    Returns a ``(domain_root, original_candidate)`` tuple. The second
    element is the unstripped candidate when the redirect was applied;
    it is ``None`` otherwise.
    """
    raw = getattr(args, "domain", None)
    candidate = Path(raw).resolve() if raw is not None else Path.cwd().resolve()
    if candidate.name.endswith("_backup"):
        stripped = candidate.with_name(candidate.name[: -len("_backup")])
        if stripped.is_dir():
            return stripped, candidate
    return candidate, None


def _make_progress(args: argparse.Namespace) -> ProgressSink:
    if args.quiet:
        return SilentProgress()
    try:
        return RichProgress(plain=args.plain)
    except RichUnavailableError:
        return SilentProgress()


def _expand_feature_dirs(features: str | None) -> str | None:
    """Expand directory entries in a ``--features`` comma-separated list.

    Validate-only authoring convenience per
    ``technical_docs/ARCHITECTURE.md`` §5.1: any entry that resolves
    to a directory is replaced in place by the sorted (lexicographic),
    non-recursive list of its immediate ``*.json`` children. File entries
    pass through unchanged. Empty segments are preserved so that the
    downstream empty-segment stripping in :func:`_build_run_config` keeps
    its existing behavior.

    Called only from :func:`cmd_validate`. ``chopper trim`` and
    ``--project`` require explicit per-file paths.
    """
    if not features:
        return features
    expanded: list[str] = []
    for raw in features.split(","):
        segment = raw.strip()
        if not segment:
            expanded.append(raw)
            continue
        candidate = Path(segment)
        if candidate.is_dir():
            children = sorted(candidate.glob("*.json"))
            expanded.extend(child.as_posix() for child in children)
        else:
            expanded.append(segment)
    return ",".join(expanded)


def _build_run_config(args: argparse.Namespace, *, dry_run: bool) -> tuple[RunConfig, Path | None]:
    domain_root, stripped_candidate = _resolve_domain_root(args)
    backup_root = domain_root.with_name(domain_root.name + "_backup")
    audit_root = domain_root / ".chopper"

    project_path: Path | None = None
    base_path: Path | None = None
    feature_paths: tuple[Path, ...] = ()
    tool_command_paths: tuple[Path, ...] = ()

    if getattr(args, "project", None) is not None:
        project_path = Path(args.project).resolve()
    else:
        if getattr(args, "base", None) is not None:
            base_path = Path(args.base).resolve()
        if getattr(args, "features", None):
            feature_paths = tuple(Path(p).resolve() for p in args.features.split(",") if p.strip())

    # ``--tool-commands`` is ``action="append"`` on both ``validate`` and
    # ``trim``; the attribute is absent on other subcommands. Treat
    # missing / empty identically.
    raw_tc = getattr(args, "tool_commands", None) or []
    tool_command_paths = tuple(Path(p).resolve() for p in raw_tc)

    cfg = RunConfig(
        domain_root=domain_root,
        backup_root=backup_root,
        audit_root=audit_root,
        strict=args.strict,
        dry_run=dry_run,
        project_path=project_path,
        base_path=base_path,
        feature_paths=feature_paths,
        tool_command_paths=tool_command_paths,
    )
    return cfg, stripped_candidate


def _make_context(args: argparse.Namespace, *, dry_run: bool) -> tuple[ChopperContext, CollectingSink]:
    sink = CollectingSink()
    cfg, stripped_candidate = _build_run_config(args, dry_run=dry_run)
    ctx = ChopperContext(
        config=cfg,
        fs=LocalFS(),
        diag=sink,
        progress=_make_progress(args),
    )
    if stripped_candidate is not None:
        # Per ARCHITECTURE.md §5.1, emit VI-03 so the suffix-strip
        # redirect is visible in stderr and recorded in the audit
        # bundle. Info severity; --strict does not escalate.
        from chopper.core.diagnostics import Diagnostic, Phase

        sink.emit(
            Diagnostic.build(
                "VI-03",
                phase=Phase.P1_CONFIG,
                message=(
                    f"--domain or cwd ended in '_backup' and a stripped sibling exists; "
                    f"resolved operational domain root to {cfg.domain_root.as_posix()!r} "
                    f"(redirected from {stripped_candidate.as_posix()!r}). "
                    "The original path is treated as the previous-run snapshot."
                ),
                path=stripped_candidate,
                hint=(
                    "If this redirect was unintended, rename the live domain so it does not "
                    "shadow the backup, or run from inside the intended domain"
                ),
                context={
                    "original_candidate": stripped_candidate.as_posix(),
                    "resolved_domain_root": cfg.domain_root.as_posix(),
                },
            )
        )
    return ctx, sink


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    """Run the pipeline in dry-run mode (validate only; no writes)."""

    # Validate-only convenience: expand any directory in ``--features`` to
    # its sorted ``*.json`` children. See architecture doc §5.1.
    if getattr(args, "project", None) is None:
        args.features = _expand_feature_dirs(getattr(args, "features", None))

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
    :class:`ChopperRunner`; this is a direct filesystem operation.
    """

    if not getattr(args, "confirm", False):
        render_cleanup_message("chopper cleanup: --confirm is required; refusing to remove backup")
        return 2

    domain_root, stripped_candidate = _resolve_domain_root(args)
    if stripped_candidate is not None:
        render_cleanup_message(
            f"chopper cleanup: --domain or cwd ended in '_backup' and live sibling exists; "
            f"redirected to {domain_root.as_posix()} (from {stripped_candidate.as_posix()}) [VI-03]"
        )
    backup_root = domain_root.with_name(domain_root.name + "_backup")
    if not backup_root.exists():
        render_cleanup_message(f"chopper cleanup: no backup to remove at {backup_root.as_posix()}")
        return 0

    import shutil

    shutil.rmtree(backup_root)
    render_cleanup_message(f"chopper cleanup: removed {backup_root.as_posix()}")
    return 0


def cmd_mcp_serve(args: argparse.Namespace) -> int:
    """Start the stdio MCP server.

    Lazy-imports :mod:`chopper.mcp` so importing :mod:`chopper.cli.commands`
    does not pull in the `mcp` SDK during `chopper validate` / `trim` /
    `cleanup` runs. Blocks until the client disconnects (stdin EOF) or
    SIGINT. See ``technical_docs/ARCHITECTURE.md`` §3.9.
    """

    del args  # MCP server takes no subcommand arguments; globals are ignored.
    from chopper.mcp import run_stdio_server

    return run_stdio_server()
