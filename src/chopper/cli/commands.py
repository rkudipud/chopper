"""Subcommand handlers.

Each ``cmd_*`` function takes the parsed :class:`argparse.Namespace` and
returns a process exit code. Handlers translate flags into
:mod:`chopper.app` requests, render the typed results through
:mod:`chopper.cli.render`, and map :class:`~chopper.app.errors.AppError`
to stderr and exit code 2. ``validate``, ``trim``, and ``loc`` share one
multi-domain loop (:func:`_dispatch`).
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import NoReturn

from chopper.adapters import CollectingSink, RichProgress, RichUnavailableError, SilentProgress
from chopper.app.catalog import expand_feature_dirs, selected_feature_paths
from chopper.app.domain import DomainLookupResult, resolve_target
from chopper.app.errors import AppError
from chopper.app.session import (
    Command,
    RunRequest,
    build_run_config,
    check_project_paths,
    domain_summary,
    failed_domain_summary,
    loc_report,
    open_context,
    p4_opened_paths,
    remove_backup,
    run,
)
from chopper.app.trim_stats import build_trim_stats
from chopper.cli.render import (
    render_app_error,
    render_audit_bundle_locations,
    render_cleanup_message,
    render_diagnostics,
    render_loc_report,
    render_p4_branch_analysis,
    render_p4_checkout_enabled_notice,
    render_p4_checkout_notice,
    render_p4_checkout_opened,
    render_result,
    render_trim_stats,
)
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.models_audit import RunResult
from chopper.core.models_common import DomainRunResult
from chopper.core.protocols import ProgressSink

__all__ = ["cmd_cleanup", "cmd_loc", "cmd_trim", "cmd_validate"]


# ---------------------------------------------------------------------------
# Argv -> application adapters
# ---------------------------------------------------------------------------


def _fail(error: AppError) -> NoReturn:
    """Map an :class:`AppError` to the CLI's stderr text and exit."""
    issue = error.issues[0]
    if issue.code is None:
        raise SystemExit(f"[chopper] fatal: {issue.message}. {issue.hint}") from error
    render_app_error(error)
    raise SystemExit(2) from error


def _request(args: argparse.Namespace, *, dry_run: bool = False) -> RunRequest:
    return RunRequest(
        domain=getattr(args, "domain", None),
        project=getattr(args, "project", None),
        base=getattr(args, "base", None),
        features=getattr(args, "features", None),
        # ``--tool-commands`` exists only on validate/trim/loc.
        tool_commands=tuple(getattr(args, "tool_commands", None) or ()),
        strict=getattr(args, "strict", False),
        dry_run=dry_run,
        p4_checkout=bool(getattr(args, "p4_checkout", False)),
    )


def _resolve_domain_root(
    args: argparse.Namespace,
) -> tuple[Path, Path | None, DomainLookupResult | None]:
    """Return ``(domain_root, redirected_from, lookup)`` for ``args.domain``."""
    try:
        target = resolve_target(getattr(args, "domain", None))
    except AppError as error:
        _fail(error)
    return target.root, target.redirected_from, target.lookup


def _build_run_config(args: argparse.Namespace, *, dry_run: bool) -> tuple[RunConfig, Path | None]:
    try:
        return build_run_config(_request(args, dry_run=dry_run))
    except AppError as error:
        _fail(error)


def _make_progress(args: argparse.Namespace) -> ProgressSink:
    if args.quiet:
        return SilentProgress()
    try:
        return RichProgress(plain=args.plain)
    except RichUnavailableError:
        return SilentProgress()


def _make_context(args: argparse.Namespace, *, dry_run: bool) -> tuple[ChopperContext, CollectingSink]:
    cfg, redirected_from = _build_run_config(args, dry_run=dry_run)
    return open_context(cfg, redirected_from, _make_progress(args))


def _check_project_paths_resolvable(args: argparse.Namespace) -> int | None:
    """``--project`` preflight: render ``VE-13`` and return 2, else ``None``."""
    try:
        diag = check_project_paths(_request(args))
    except AppError as error:
        _fail(error)
    if diag is None:
        return None
    render_diagnostics([diag])
    sys.stderr.write(f"  hint: {diag.hint}\n")
    sys.stderr.write("Summary: 1 error(s), 0 warning(s), 0 info(s); exit 2\n")
    return 2


def _split_domain_csv(raw: str | None) -> list[str | None]:
    """Split ``--domain`` into domain tokens (commas only; drive colons are kept)."""
    if raw is None:
        return [None]
    if "," not in raw:
        return [raw]
    return [t.strip() for t in raw.split(",") if t.strip()]


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _print_domain_header(ctx: ChopperContext) -> None:
    """Print a scannable per-domain header to stdout before the pipeline starts."""
    cfg = ctx.config
    label = cfg.domain_logical_name or cfg.domain_root.name
    if cfg.base_path is not None:
        base_display = cfg.base_path.as_posix()
    elif cfg.project_path is not None:
        base_display = cfg.project_path.as_posix() + "  (project)"
    else:
        base_display = "(none)"
    print(f"\n=== Domain: {label} ===", flush=True)
    print(f"  Domain root : {cfg.domain_root.as_posix()}", flush=True)
    print(f"  Base JSON   : {base_display}", flush=True)

    feature_paths = selected_feature_paths(cfg)
    if cfg.base_path is not None or cfg.project_path is not None:
        print("  config file found.. processing", flush=True)
    if cfg.project_config_path is not None:
        print(f"  config file path : {cfg.project_config_path.as_posix()}", flush=True)
    if feature_paths:
        print(f"  Features ({len(feature_paths)}) :", flush=True)
        for i, fp in enumerate(feature_paths, 1):
            name = fp.stem.removesuffix(".feature")
            print(f"    {i}. {name} : {fp.as_posix()}", flush=True)


def _render_p4_checkout_notice_if_skipped(result: object, *, plain: bool) -> None:
    """Render the red "P4 EDIT NOT POSSIBLE" notice when ``--p4`` checkout was skipped.

    No-op when ``--p4`` was never passed (``p4_checkout`` is ``None`` on the
    trim report) or when checkout was attempted -- a failed attempt is
    already reported via ``VE-37``.
    """
    trim_report = getattr(result, "trim_report", None)
    p4_checkout = getattr(trim_report, "p4_checkout", None) if trim_report is not None else None
    if p4_checkout is None or p4_checkout.attempted:
        return
    render_p4_checkout_notice(p4_checkout.skip_reason or "unknown reason", plain=plain)


def _warn_if_cwd_will_be_renamed(domain_root: Path, backup_root: Path) -> None:
    """Emit a stderr notice when cwd is inside a soon-to-be-renamed domain.

    Only triggers when the backup does not yet exist (trim case 1 --
    the only case that issues ``rename(domain, backup)``). Pure UX;
    no diagnostic code, no audit-bundle entry.
    """
    try:
        cwd = Path.cwd().resolve()
    except OSError:
        return
    if backup_root.exists():
        return
    try:
        cwd.relative_to(domain_root)
    except ValueError:
        return
    sys.stderr.write(
        "[chopper] notice: your shell's current directory is inside "
        f"{domain_root.as_posix()!r}, which will be renamed to "
        f"{backup_root.name!r} during trim. After the run, the shell's "
        "cwd will be stale (`pwd: Stale file handle` on NFS). Recover with:\n"
        f"    cd {domain_root.parent.as_posix()} && cd {domain_root.name}\n"
        "Tip: run `chopper trim` from the parent directory to avoid this.\n"
    )


def _render_loc_table(ctx: ChopperContext, result: RunResult) -> None:
    render_loc_report(loc_report(ctx, result))


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _dispatch(args: argparse.Namespace, command: Command) -> int:
    """The one multi-domain loop behind ``validate``, ``trim``, and ``loc``.

    A single ``--domain`` (or none) runs against ``args`` itself and returns
    a preflight failure at once. A CSV list runs each domain on a shallow
    copy, records preflight failures in the branch analysis, continues, and
    returns the highest exit code.
    """
    tokens = _split_domain_csv(getattr(args, "domain", None))
    single = len(tokens) <= 1
    runs = [args] if single else [copy.copy(args) for _ in tokens]
    if not single:
        for domain_args, token in zip(runs, tokens, strict=True):
            domain_args.domain = token
    trim = command == "trim"

    summaries: list[DomainRunResult] = []
    audit_paths: list[tuple[str, Path]] = []
    p4_opened: list[tuple[str, list[Path]]] = []
    exit_code = 0
    for domain_args in runs:
        if not trim and getattr(domain_args, "project", None) is None:
            domain_args.features = expand_feature_dirs(getattr(domain_args, "features", None))
        rc = _check_project_paths_resolvable(domain_args)
        if rc is not None:
            if single:
                return rc
            summaries.append(failed_domain_summary(domain_args.domain, rc))
            exit_code = max(exit_code, rc)
            continue

        ctx, sink = _make_context(domain_args, dry_run=bool(getattr(domain_args, "dry_run", False)) if trim else True)
        live = trim and not ctx.config.dry_run
        if live:
            _warn_if_cwd_will_be_renamed(ctx.config.domain_root, ctx.config.backup_root)
        _print_domain_header(ctx)
        if live and ctx.config.p4_checkout:
            render_p4_checkout_enabled_notice()
        result = run(ctx, command)
        render_result(result, sink.snapshot())
        if live:
            render_trim_stats(build_trim_stats(ctx, result))
            _render_p4_checkout_notice_if_skipped(result, plain=domain_args.plain)
        if command == "loc":
            _render_loc_table(ctx, result)
        summaries.append(domain_summary(ctx, result))
        if trim:
            audit_paths.append((summaries[-1].domain_logical_name, ctx.config.audit_root))
            p4_opened.append((summaries[-1].domain_logical_name, p4_opened_paths(ctx, result)))
        exit_code = result.exit_code if single else max(exit_code, result.exit_code)

    render_p4_branch_analysis(summaries)
    if trim:
        render_audit_bundle_locations(audit_paths)
        render_p4_checkout_opened(p4_opened)
    return exit_code


def cmd_validate(args: argparse.Namespace) -> int:
    """Run the pipeline in dry-run mode (validate only; no writes)."""
    return _dispatch(args, "validate")


def cmd_trim(args: argparse.Namespace) -> int:
    """Execute the full trim pipeline (``--dry-run`` writes only the audit bundle)."""
    return _dispatch(args, "trim")


def cmd_loc(args: argparse.Namespace) -> int:
    """Run the read-only LOC report (architecture doc Sec.5.7, FR-46).

    Runs the ``chopper trim --dry-run`` pipeline plus generation in
    no-write mode and prints a LOC table comparing the source domain with
    the planned trimmed domain. Writes nothing: no domain changes and no
    ``.chopper/`` audit bundle.
    """
    return _dispatch(args, "loc")


def cmd_cleanup(args: argparse.Namespace) -> int:
    """Remove ``<domain>_backup/`` after the trim window is complete.

    Refuses to run without ``--confirm``. Does not enter the pipeline.
    """
    if not getattr(args, "confirm", False):
        render_cleanup_message("chopper cleanup: --confirm is required; refusing to remove backup")
        return 2

    domain_root, redirected_from, _lookup = _resolve_domain_root(args)
    if redirected_from is not None:
        render_cleanup_message(
            f"chopper cleanup: --domain or cwd ended in '_backup' and live sibling exists; "
            f"redirected to {domain_root.as_posix()} (from {redirected_from.as_posix()}) [VI-03]"
        )
    outcome = remove_backup(domain_root)
    if outcome.removed:
        render_cleanup_message(f"chopper cleanup: removed {outcome.backup_root.as_posix()}")
    else:
        render_cleanup_message(f"chopper cleanup: no backup to remove at {outcome.backup_root.as_posix()}")
    return 0
