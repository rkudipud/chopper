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
from chopper.cli.render import (
    render_cleanup_message,
    render_diagnostics,
    render_result,
    render_trim_stats,
)
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.protocols import ProgressSink
from chopper.orchestrator import ChopperRunner

__all__ = ["cmd_cleanup", "cmd_loc", "cmd_trim", "cmd_validate"]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_domain_root(args: argparse.Namespace) -> tuple[Path, Path | None]:
    """Resolve the operational domain root.

    Per ``technical_docs/ARCHITECTURE.md`` Sec.5.1 (Domain-root resolution),
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
       returned unchanged -- a coincidentally-named domain is honored
       as-is.

    Returns a ``(domain_root, original_candidate)`` tuple. The second
    element is the unstripped candidate when the redirect was applied;
    it is ``None`` otherwise.
    """
    raw = getattr(args, "domain", None)
    if raw is not None:
        candidate = Path(raw).resolve()
    else:
        try:
            candidate = Path.cwd().resolve()
        except (FileNotFoundError, OSError) as exc:
            # Current working directory was deleted or is otherwise
            # inaccessible (common on NFS when a sibling process
            # replaces the inode). We have no sensible fallback --
            # ``--domain`` is the supported escape hatch.
            raise SystemExit(
                "[chopper] fatal: cannot determine current working directory "
                f"({type(exc).__name__}: {exc}). "
                "Pass --domain <path> or 'cd' into an existing directory."
            ) from exc
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
    ``technical_docs/ARCHITECTURE.md`` Sec.5.1: any entry that resolves
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
        # Per ARCHITECTURE.md Sec.5.1, emit VI-03 so the suffix-strip
        # redirect is visible in stderr and recorded in the audit
        # bundle. Info severity; --strict does not escalate.
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


def _check_project_paths_resolvable(args: argparse.Namespace) -> int | None:
    """CLI pre-runner check for ``--project`` mode (issue #23, VE-13).

    When ``--project <project.json>`` is given, the project JSON's
    ``base`` and ``features`` entries are resolved relative to the
    operational domain root (per ARCHITECTURE.md Sec.3.3 and Sec.5.1). If
    the user runs Chopper from outside the domain (e.g. from the
    install/sbox directory) without passing ``--domain``, the
    domain root defaults to ``Path.cwd()`` and those relative paths
    silently resolve under the wrong directory. The downstream
    failure surfaces inside ``ConfigService`` as a generic VE-01
    file-not-found error pointing at a path under the sbox -- exit
    code 1 with no hint that ``--domain`` is the fix.

    This helper performs a fast pre-check after argument parsing but
    before constructing the :class:`RunConfig`: load the project
    JSON, resolve each ``base``/``features`` entry against the
    candidate domain root, and emit ``VE-13`` (exit 2) when any path
    does not exist on disk. The downstream pipeline is bypassed
    entirely so the user sees the actionable diagnostic only.

    Returns ``2`` when the check fires (caller must propagate as the
    process exit code), ``None`` otherwise. Returns ``None`` for
    structural problems with the project JSON (missing keys, malformed
    JSON, schema violations) -- those remain ``ConfigService``'s
    responsibility (VE-01 / VE-04 / schema diagnostics).
    """
    project_arg = getattr(args, "project", None)
    if project_arg is None:
        return None

    import json as _json

    project_path = Path(project_arg).resolve()
    try:
        with open(project_path, encoding="utf-8") as fh:
            raw = _json.load(fh)
    except (OSError, _json.JSONDecodeError):
        # Let ConfigService surface VE-01/VE-04 with its richer context.
        return None
    if not isinstance(raw, dict):
        return None

    domain_root, _ = _resolve_domain_root(args)

    candidates: list[tuple[str, Path]] = []
    base_val = raw.get("base")
    if isinstance(base_val, str) and base_val:
        candidates.append(("base", domain_root / base_val))
    features_val = raw.get("features")
    if isinstance(features_val, list):
        for entry in features_val:
            if isinstance(entry, str) and entry:
                candidates.append(("features[]", domain_root / entry))

    missing = [(field, path) for field, path in candidates if not path.exists()]
    if not missing:
        return None

    field, missing_path = missing[0]
    others = ", ".join(f"{f}={p.as_posix()}" for f, p in missing[1:])
    explicit_domain = getattr(args, "domain", None) is not None
    hint = (
        f"Resolved from domain root {domain_root.as_posix()!r} "
        f"(from {'--domain' if explicit_domain else 'cwd'}). "
        "Pass --domain <path-to-domain-root>, or 'cd' into the domain "
        "root before running Chopper. See ARCHITECTURE.md Sec.3.3."
    )
    diag = Diagnostic.build(
        "VE-13",
        phase=Phase.P1_CONFIG,
        message=(
            f"project.json {field} {missing_path.as_posix()!r} does not exist on disk"
            + (f"; also missing: {others}" if others else "")
        ),
        path=project_path,
        hint=hint,
        context={
            "domain_root": domain_root.as_posix(),
            "domain_source": "--domain" if explicit_domain else "cwd",
            "missing": [{"field": f, "path": p.as_posix()} for f, p in missing],
        },
    )
    render_diagnostics([diag])
    import sys as _sys

    _sys.stderr.write(f"  hint: {hint}\n")
    _sys.stderr.write("Summary: 1 error(s), 0 warning(s), 0 info(s); exit 2\n")
    return 2


def cmd_validate(args: argparse.Namespace) -> int:
    """Run the pipeline in dry-run mode (validate only; no writes)."""

    # Validate-only convenience: expand any directory in ``--features`` to
    # its sorted ``*.json`` children. See architecture doc Sec.5.1.
    if getattr(args, "project", None) is None:
        args.features = _expand_feature_dirs(getattr(args, "features", None))

    rc = _check_project_paths_resolvable(args)
    if rc is not None:
        return rc

    ctx, sink = _make_context(args, dry_run=True)
    result = ChopperRunner().run(ctx, command="validate")
    render_result(result, sink.snapshot())
    return result.exit_code


def cmd_trim(args: argparse.Namespace) -> int:
    """Execute the full trim pipeline."""

    rc = _check_project_paths_resolvable(args)
    if rc is not None:
        return rc

    ctx, sink = _make_context(args, dry_run=bool(getattr(args, "dry_run", False)))

    # NFS/shell UX guard: if the user invoked us from inside the
    # domain root (or anywhere under it) and the backup does not yet
    # exist, the trimmer will rename ``domain -> domain_backup`` (case
    # 1 of the workspace-prep state machine in
    # ``trimmer/service.py::_prepare_workspace``). The shell's cwd
    # then points at an inode now reachable under a different name,
    # which on NFS surfaces as ``pwd: Stale file handle``. We cannot
    # repair the parent shell's cwd from Python, so warn up front.
    if not ctx.config.dry_run:
        _warn_if_cwd_will_be_renamed(ctx.config.domain_root, ctx.config.backup_root)

    result = ChopperRunner().run(ctx, command="trim")
    render_result(result, sink.snapshot())
    if not ctx.config.dry_run:
        render_trim_stats(ctx, result)
    return result.exit_code


def _warn_if_cwd_will_be_renamed(domain_root: Path, backup_root: Path) -> None:
    """Emit a stderr notice when cwd is inside a soon-to-be-renamed domain.

    Only triggers when the backup does not yet exist (trim case 1 --
    the only case that issues ``rename(domain, backup)``). Pure UX;
    no diagnostic code, no audit-bundle entry.
    """

    import sys as _sys

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
    _sys.stderr.write(
        "[chopper] notice: your shell's current directory is inside "
        f"{domain_root.as_posix()!r}, which will be renamed to "
        f"{backup_root.name!r} during trim. After the run, the shell's "
        "cwd will be stale (`pwd: Stale file handle` on NFS). Recover with:\n"
        f"    cd {domain_root.parent.as_posix()} && cd {domain_root.name}\n"
        "Tip: run `chopper trim` from the parent directory to avoid this.\n"
    )


def cmd_loc(args: argparse.Namespace) -> int:
    """Run the read-only LOC report subcommand.

    Per architecture doc Sec.5.7 (and FR-46): runs the same P0-P4 +
    dry-run-P6 pipeline as ``chopper trim --dry-run``, additionally
    invokes ``GeneratorService`` in no-write mode, then renders a
    stdout LOC table comparing the source domain against the planned
    trimmed domain. Writes nothing -- no domain modifications and no
    ``.chopper/`` audit bundle (the runner suppresses P7 audit when
    ``command == "loc"``).
    """

    # Same validate-only authoring convenience as ``chopper validate``:
    # accept directory entries in ``--features`` for ad-hoc LOC sweeps.
    if getattr(args, "project", None) is None:
        args.features = _expand_feature_dirs(getattr(args, "features", None))

    rc = _check_project_paths_resolvable(args)
    if rc is not None:
        return rc

    ctx, sink = _make_context(args, dry_run=True)
    result = ChopperRunner().run(ctx, command="loc")

    # Always render diagnostics (so users see VE-/VW- before the table).
    render_result(result, sink.snapshot())

    # Render the LOC table. Preferred path: dry-run pipeline reached
    # P3 and produced a manifest, so we can attribute per-treatment
    # buckets. Fallback path: pipeline aborted early (e.g. ``PE-01``
    # duplicate procs or ``PE-02`` unbalanced braces in P2). ``chopper
    # loc`` is read-only, so we still emit a baseline-only SLOC report
    # -- users get the on-disk numbers even when their domain has
    # quality issues that block trim planning.
    if result.manifest is not None and result.parsed is not None and result.loaded is not None:
        from chopper.cli.loc_report import build_loc_report, render_loc_report

        report = build_loc_report(
            ctx=ctx,
            loaded=result.loaded,
            parsed=result.parsed,
            manifest=result.manifest,
            generated_artifacts=result.generated_artifacts,
        )
        render_loc_report(report)
    else:
        from chopper.cli.loc_report import build_loc_report_baseline_only, render_loc_report

        report = build_loc_report_baseline_only(ctx)
        render_loc_report(report)

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
