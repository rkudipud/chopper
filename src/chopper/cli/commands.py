"""Subcommand handlers.

Each ``cmd_*`` function takes the parsed :class:`argparse.Namespace`
and returns a process exit code. The handlers own the translation
from CLI flags to :class:`RunConfig` and :class:`ChopperContext`.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from chopper.adapters import (
    CollectingSink,
    LocalFS,
    RichProgress,
    RichUnavailableError,
    SilentProgress,
)
from chopper.cli.domain_lookup import DomainLookupResult, resolve_domain
from chopper.cli.feature_lookup import resolve_feature_names
from chopper.cli.loc_report import (
    build_loc_report,
    build_loc_report_baseline_only,
    render_loc_report,
)
from chopper.cli.render import (
    render_cleanup_message,
    render_diagnostics,
    render_p4_branch_analysis,
    render_result,
    render_trim_stats,
)
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models_common import DomainRunResult, FileTreatment
from chopper.core.protocols import ProgressSink
from chopper.orchestrator import ChopperRunner

__all__ = ["cmd_cleanup", "cmd_loc", "cmd_trim", "cmd_validate"]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_domain_root(
    args: argparse.Namespace,
) -> tuple[Path, Path | None, DomainLookupResult | None]:
    """Resolve the operational domain root.

    Extended to support named domain lookup via ``$WARD/global/`` when
    ``--domain`` is a logical name rather than a filesystem path.
    See ``technical_docs/ARCHITECTURE.md`` §5.1.0.

    Returns ``(domain_root, original_candidate_if_redirected, lookup_result_or_none)``.
    The third element is the :class:`~chopper.cli.domain_lookup.DomainLookupResult`
    when name-mode was used; ``None`` when path-mode was used (backward compat)
    or when ``--domain`` was absent (cwd mode).

    Emits VE-32/VE-33/VE-34 via stderr and raises :class:`SystemExit(2)` when
    name-mode resolution fails.
    """
    raw = getattr(args, "domain", None)

    if raw is not None:
        errors: list[tuple[str, str, str]] = []

        def _emit(code: str, message: str, hint: str) -> None:
            errors.append((code, message, hint))

        lookup_result = resolve_domain(raw, _emit)
        if lookup_result is None:
            # Resolution failed; print the first error and exit 2.
            code, message, hint = errors[0]
            sys.stderr.write(f"[chopper] error ({code}): {message}\n")
            sys.stderr.write(f"  hint: {hint}\n")
            raise SystemExit(2)

        # Apply _backup redirect on the resolved domain_root.
        candidate = lookup_result.domain_root
        if candidate.name.endswith("_backup"):
            stripped = candidate.with_name(candidate.name[: -len("_backup")])
            if stripped.is_dir():
                return stripped, candidate, lookup_result
        return candidate, None, lookup_result

    # No --domain: use cwd.
    try:
        candidate = Path.cwd().resolve()
    except (FileNotFoundError, OSError) as exc:
        raise SystemExit(
            "[chopper] fatal: cannot determine current working directory "
            f"({type(exc).__name__}: {exc}). "
            "Pass --domain <path> or 'cd' into an existing directory."
        ) from exc
    if candidate.name.endswith("_backup"):
        stripped = candidate.with_name(candidate.name[: -len("_backup")])
        if stripped.is_dir():
            return stripped, candidate, None
    return candidate, None, None


def _make_progress(args: argparse.Namespace) -> ProgressSink:
    if args.quiet:
        return SilentProgress()
    try:
        return RichProgress(plain=args.plain)
    except RichUnavailableError:
        return SilentProgress()


def _autodiscover_base(domain_root: Path, domain_logical_name: str | None) -> Path | None:
    """Search for base.json in standard locations under domain_root.

    Tries:
    1. ``<domain_root>/jsons/base.json``
    2. ``<domain_root>/jsons/<domain_leaf_name>.json``

    Returns the first found path, or ``None``.
    """
    candidate1 = domain_root / "jsons" / "base.json"
    if candidate1.is_file():
        return candidate1
    if domain_logical_name is not None:
        leaf = domain_logical_name.split("/")[-1]
    else:
        leaf = domain_root.name
    candidate2 = domain_root / "jsons" / f"{leaf}.json"
    if candidate2.is_file():
        return candidate2
    return None


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
    domain_root, stripped_candidate, lookup_result = _resolve_domain_root(args)
    backup_root = domain_root.with_name(domain_root.name + "_backup")
    audit_root = domain_root / ".chopper"

    ward_root: Path | None = lookup_result.ward_root if lookup_result is not None else None
    domain_logical_name: str | None = lookup_result.domain_logical_name if lookup_result is not None else None

    project_path: Path | None = None
    base_path: Path | None = None
    feature_paths: tuple[Path, ...] = ()
    tool_command_paths: tuple[Path, ...] = ()

    if getattr(args, "project", None) is not None:
        project_path = Path(args.project).resolve()
    else:
        # Base resolution
        if getattr(args, "base", None) is not None:
            base_path = Path(args.base).resolve()
        else:
            # Auto-discover base JSON from domain (VE-35 if not found).
            base_path = _autodiscover_base(domain_root, domain_logical_name)
            if base_path is None:
                domain_basename = (domain_logical_name or domain_root.name).split("/")[-1]
                tried = [
                    (domain_root / "jsons" / "base.json").as_posix(),
                    (domain_root / "jsons" / f"{domain_basename}.json").as_posix(),
                ]
                sys.stderr.write(
                    "[chopper] error (VE-35): No base JSON found via auto-discovery.\n"
                    f"  Tried: {', '.join(tried)}\n"
                    "  hint: Pass --base <path> or add jsons/base.json to the domain.\n"
                )
                raise SystemExit(2)

        # Feature resolution: name-mode or path-mode.
        if getattr(args, "features", None):
            lookup_result_feat = resolve_feature_names(args.features, domain_root)
            if lookup_result_feat.unresolved_names:
                for unresolved in lookup_result_feat.unresolved_names:
                    suggestions = lookup_result_feat.suggestions.get(unresolved, ())
                    hint = (
                        f"Did you mean: {', '.join(suggestions)}?"
                        if suggestions
                        else f"Run `ls {(domain_root / 'jsons' / 'features').as_posix()}` to see available features."
                    )
                    sys.stderr.write(
                        f"[chopper] error (VE-36): Feature name {unresolved!r} not found in "
                        f"{(domain_root / 'jsons' / 'features').as_posix()!r}.\n"
                        f"  hint: {hint}\n"
                    )
                raise SystemExit(2)
            feature_paths = lookup_result_feat.resolved_paths

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
        ward_root=ward_root,
        domain_logical_name=domain_logical_name,
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


def _split_domain_csv(raw: str | None) -> list[str | None]:
    """Split --domain value into a list of domain tokens.

    A single domain (no comma) returns a one-element list.
    Path-mode values with a Windows drive letter colon are NOT split on
    the colon (only commas are delimiters).
    """
    if raw is None:
        return [None]  # type: ignore[list-item]
    if "," not in raw:
        return [raw]
    return [t.strip() for t in raw.split(",") if t.strip()]


def _make_domain_run_result(ctx: ChopperContext, result: object) -> DomainRunResult:
    """Extract P4 branch-analysis stats from a completed run result."""
    manifest = getattr(result, "manifest", None)
    edits = 0
    adds = 0
    removes = 0

    if manifest is not None:
        for _path, treatment in manifest.file_decisions.items():
            if treatment is FileTreatment.PROC_TRIM:
                edits += 1
            elif treatment is FileTreatment.GENERATED:
                # Count all GENERATED as edits (conservative; we cannot
                # distinguish edit vs add without filesystem access here).
                edits += 1
            elif treatment is FileTreatment.REMOVE:
                removes += 1

    domain_label = ctx.config.domain_logical_name or ctx.config.domain_root.name
    branch_needed = (edits + adds) > 0

    return DomainRunResult(
        domain_logical_name=domain_label,
        exit_code=getattr(result, "exit_code", 1),
        branch_needed=branch_needed,
        edits_count=edits,
        adds_count=adds,
        removes_count=removes,
    )


def _make_error_domain_result(token: str | None, rc: int) -> DomainRunResult:
    """Build a :class:`DomainRunResult` for a domain that failed pre-flight checks."""
    return DomainRunResult(
        domain_logical_name=str(token) if token is not None else "(unknown)",
        exit_code=rc,
        branch_needed=False,
        edits_count=0,
        adds_count=0,
        removes_count=0,
    )


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

    project_path = Path(project_arg).resolve()
    try:
        with open(project_path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError):
        # Let ConfigService surface VE-01/VE-04 with its richer context.
        return None
    if not isinstance(raw, dict):
        return None

    domain_root, _, _lookup = _resolve_domain_root(args)

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
    sys.stderr.write(f"  hint: {hint}\n")
    sys.stderr.write("Summary: 1 error(s), 0 warning(s), 0 info(s); exit 2\n")
    return 2


def cmd_validate(args: argparse.Namespace) -> int:
    """Run the pipeline in dry-run mode (validate only; no writes).

    Supports multi-domain CSV ``--domain`` (e.g. ``fev_formality,fev_conformal``).
    """
    domain_tokens = _split_domain_csv(getattr(args, "domain", None))

    if len(domain_tokens) <= 1:
        # Single domain — original behaviour.
        if getattr(args, "project", None) is None:
            args.features = _expand_feature_dirs(getattr(args, "features", None))

        rc = _check_project_paths_resolvable(args)
        if rc is not None:
            return rc

        ctx, sink = _make_context(args, dry_run=True)
        result = ChopperRunner().run(ctx, command="validate")
        render_result(result, sink.snapshot())
        domain_results = [_make_domain_run_result(ctx, result)]
        render_p4_branch_analysis(domain_results)
        return result.exit_code

    # Multi-domain loop.
    domain_results = []  # list[DomainRunResult]
    max_exit = 0
    for token in domain_tokens:
        domain_args = copy.copy(args)
        domain_args.domain = token
        if getattr(domain_args, "project", None) is None:
            domain_args.features = _expand_feature_dirs(getattr(domain_args, "features", None))
        rc = _check_project_paths_resolvable(domain_args)
        if rc is not None:
            domain_results.append(_make_error_domain_result(token, rc))
            max_exit = max(max_exit, rc)
            continue
        ctx, sink = _make_context(domain_args, dry_run=True)
        result = ChopperRunner().run(ctx, command="validate")
        render_result(result, sink.snapshot())
        domain_results.append(_make_domain_run_result(ctx, result))
        max_exit = max(max_exit, result.exit_code)

    render_p4_branch_analysis(domain_results)
    return max_exit


def cmd_trim(args: argparse.Namespace) -> int:
    """Execute the full trim pipeline, supporting multiple domains via CSV ``--domain``."""
    domain_tokens = _split_domain_csv(getattr(args, "domain", None))

    if len(domain_tokens) <= 1:
        # Single domain — original behaviour (plus new auto-discovery).
        rc = _check_project_paths_resolvable(args)
        if rc is not None:
            return rc

        ctx, sink = _make_context(args, dry_run=bool(getattr(args, "dry_run", False)))
        if not ctx.config.dry_run:
            _warn_if_cwd_will_be_renamed(ctx.config.domain_root, ctx.config.backup_root)

        result = ChopperRunner().run(ctx, command="trim")
        render_result(result, sink.snapshot())
        if not ctx.config.dry_run:
            render_trim_stats(ctx, result)
        domain_results = [_make_domain_run_result(ctx, result)]
        render_p4_branch_analysis(domain_results)
        return result.exit_code

    # Multi-domain loop.
    domain_results = []  # list[DomainRunResult]
    max_exit = 0
    for token in domain_tokens:
        domain_args = copy.copy(args)
        domain_args.domain = token
        rc = _check_project_paths_resolvable(domain_args)
        if rc is not None:
            domain_results.append(_make_error_domain_result(token, rc))
            max_exit = max(max_exit, rc)
            continue
        ctx, sink = _make_context(domain_args, dry_run=bool(getattr(domain_args, "dry_run", False)))
        if not ctx.config.dry_run:
            _warn_if_cwd_will_be_renamed(ctx.config.domain_root, ctx.config.backup_root)
        result = ChopperRunner().run(ctx, command="trim")
        render_result(result, sink.snapshot())
        if not ctx.config.dry_run:
            render_trim_stats(ctx, result)
        domain_results.append(_make_domain_run_result(ctx, result))
        max_exit = max(max_exit, result.exit_code)

    render_p4_branch_analysis(domain_results)
    return max_exit


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


def cmd_loc(args: argparse.Namespace) -> int:
    """Run the read-only LOC report subcommand, supporting CSV ``--domain``.

    Per architecture doc Sec.5.7 (and FR-46): runs the same P0-P4 +
    dry-run-P6 pipeline as ``chopper trim --dry-run``, additionally
    invokes ``GeneratorService`` in no-write mode, then renders a
    stdout LOC table comparing the source domain against the planned
    trimmed domain. Writes nothing -- no domain modifications and no
    ``.chopper/`` audit bundle (the runner suppresses P7 audit when
    ``command == "loc"``).
    """
    domain_tokens = _split_domain_csv(getattr(args, "domain", None))

    if len(domain_tokens) <= 1:
        # Single domain — original behaviour.
        if getattr(args, "project", None) is None:
            args.features = _expand_feature_dirs(getattr(args, "features", None))

        rc = _check_project_paths_resolvable(args)
        if rc is not None:
            return rc

        ctx, sink = _make_context(args, dry_run=True)
        result = ChopperRunner().run(ctx, command="loc")
        render_result(result, sink.snapshot())
        _render_loc_table(ctx, result)
        domain_results = [_make_domain_run_result(ctx, result)]
        render_p4_branch_analysis(domain_results)
        return result.exit_code

    # Multi-domain loop.
    domain_results = []  # list[DomainRunResult]
    max_exit = 0
    for token in domain_tokens:
        domain_args = copy.copy(args)
        domain_args.domain = token
        if getattr(domain_args, "project", None) is None:
            domain_args.features = _expand_feature_dirs(getattr(domain_args, "features", None))
        rc = _check_project_paths_resolvable(domain_args)
        if rc is not None:
            domain_results.append(_make_error_domain_result(token, rc))
            max_exit = max(max_exit, rc)
            continue
        ctx, sink = _make_context(domain_args, dry_run=True)
        result = ChopperRunner().run(ctx, command="loc")
        render_result(result, sink.snapshot())
        _render_loc_table(ctx, result)
        domain_results.append(_make_domain_run_result(ctx, result))
        max_exit = max(max_exit, result.exit_code)

    render_p4_branch_analysis(domain_results)
    return max_exit


def _render_loc_table(ctx: ChopperContext, result: object) -> None:
    """Render the LOC breakdown table for a single cmd_loc result."""
    manifest = getattr(result, "manifest", None)
    parsed = getattr(result, "parsed", None)
    loaded = getattr(result, "loaded", None)
    generated_artifacts = getattr(result, "generated_artifacts", None) or ()

    if manifest is not None and parsed is not None and loaded is not None:
        report = build_loc_report(
            ctx=ctx,
            loaded=loaded,
            parsed=parsed,
            manifest=manifest,
            generated_artifacts=generated_artifacts,
        )
        render_loc_report(report)
    else:
        report = build_loc_report_baseline_only(ctx)
        render_loc_report(report)


def cmd_cleanup(args: argparse.Namespace) -> int:
    """Remove ``<domain>_backup/`` after the trim window is complete.

    Refuses to run without ``--confirm``. Does not enter
    :class:`ChopperRunner`; this is a direct filesystem operation.
    """

    if not getattr(args, "confirm", False):
        render_cleanup_message("chopper cleanup: --confirm is required; refusing to remove backup")
        return 2

    domain_root, stripped_candidate, _lookup = _resolve_domain_root(args)
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
