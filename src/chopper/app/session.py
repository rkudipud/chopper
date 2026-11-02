"""Run use cases: recipe -> context -> run -> typed projections.

* :class:`RunRequest` / :func:`build_run_config` -- front-end inputs to a
  :class:`RunConfig` (base / project-config auto-discovery, feature-name
  lookup; ``VE-35`` / ``VE-36`` as :class:`AppError`).
* :func:`check_project_paths` -- the ``VE-13`` ``--project`` preflight.
* :func:`open_context` / :func:`run` -- context construction (``VI-03``)
  and dispatch through the single composer.
* :func:`loc_report`, :func:`domain_summary`, :func:`p4_opened_paths` --
  typed read models over a :class:`RunResult`.
* :func:`remove_backup` -- confirmed ``<domain>_backup/`` removal.
* :func:`record_crash` -- crash log for failures outside the runner.

See ``technical_docs/ARCHITECTURE.md`` Sec.5.11.2.
"""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from chopper.adapters import CollectingSink, LocalFS
from chopper.app.catalog import base_candidates, find_base, find_project_config, resolve_feature_names
from chopper.app.domain import resolve_target
from chopper.app.errors import AppError, AppIssue
from chopper.audit.internal_error import write_internal_error_log
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models_audit import InternalError, LocReport, RunResult
from chopper.core.models_common import DomainRunResult, FileTreatment
from chopper.core.protocols import ProgressSink
from chopper.orchestrator import ChopperRunner
from chopper.orchestrator.projection import build_loc_report, build_loc_report_baseline_only

__all__ = [
    "CleanupOutcome",
    "Command",
    "RunRequest",
    "build_run_config",
    "check_project_paths",
    "domain_summary",
    "failed_domain_summary",
    "loc_report",
    "open_context",
    "p4_opened_paths",
    "record_crash",
    "remove_backup",
    "run",
]


Command = Literal["validate", "trim", "loc"]
"""Pipeline commands a front end can dispatch through :func:`run`."""


@dataclass(frozen=True)
class RunRequest:
    """Front-end inputs for one domain run (raw, as the user supplied them)."""

    domain: str | None = None
    project: str | None = None
    base: str | None = None
    features: str | None = None
    tool_commands: tuple[str, ...] = ()
    strict: bool = False
    dry_run: bool = False
    p4_checkout: bool = False


@dataclass(frozen=True)
class CleanupOutcome:
    """Result of :func:`remove_backup`."""

    backup_root: Path
    removed: bool


def build_run_config(req: RunRequest) -> tuple[RunConfig, Path | None]:
    """Build the :class:`RunConfig` for ``req``.

    Returns ``(config, redirected_from)``; ``redirected_from`` is the
    ``*_backup`` path the request was redirected away from, if any.
    Raises :class:`AppError` for domain lookup failures, ``VE-35`` (no base
    JSON found), and ``VE-36`` (one issue per unknown feature name).
    """
    target = resolve_target(req.domain)
    domain_root = target.root
    ward_root = target.lookup.ward_root if target.lookup is not None else None
    domain_logical_name = target.lookup.domain_logical_name if target.lookup is not None else None

    # Mirror $ward/global/<vendor>/<domain> -> $ward/project/<vendor>/<domain>
    # when no explicit --project/--base/--features was supplied.
    explicit_project = req.project
    explicit_features = req.features
    project_config_path: Path | None = None
    if (
        explicit_project is None
        and req.base is None
        and not explicit_features
        and ward_root is not None
        and domain_logical_name is not None
    ):
        explicit_project, explicit_features, project_config_path = find_project_config(ward_root, domain_logical_name)

    project_path: Path | None = None
    base_path: Path | None = None
    feature_paths: tuple[Path, ...] = ()

    if explicit_project is not None:
        project_path = Path(explicit_project).resolve()
    else:
        if req.base is not None:
            base_path = Path(req.base).resolve()
        else:
            base_path = find_base(domain_root, domain_logical_name)
            if base_path is None:
                tried = ", ".join(p.as_posix() for p in base_candidates(domain_root, domain_logical_name))
                raise AppError(
                    AppIssue(
                        "VE-35",
                        "No base JSON found via auto-discovery.",
                        "Pass --base <path> or add jsons/base.json to the domain.",
                        detail=f"Tried: {tried}",
                    )
                )

        if explicit_features:
            lookup = resolve_feature_names(explicit_features, domain_root)
            if lookup.unresolved_names:
                features_dir = (domain_root / "jsons" / "features").as_posix()
                issues: list[AppIssue] = []
                for name in lookup.unresolved_names:
                    suggestions = lookup.suggestions.get(name, ())
                    hint = (
                        f"Did you mean: {', '.join(suggestions)}?"
                        if suggestions
                        else f"Run `ls {features_dir}` to see available features."
                    )
                    issues.append(AppIssue("VE-36", f"Feature name {name!r} not found in {features_dir!r}.", hint))
                raise AppError(*issues)
            feature_paths = lookup.resolved_paths

    cfg = RunConfig(
        domain_root=domain_root,
        backup_root=domain_root.with_name(domain_root.name + "_backup"),
        audit_root=domain_root / ".chopper",
        strict=req.strict,
        dry_run=req.dry_run,
        project_path=project_path,
        base_path=base_path,
        feature_paths=feature_paths,
        tool_command_paths=tuple(Path(p).resolve() for p in req.tool_commands),
        ward_root=ward_root,
        domain_logical_name=domain_logical_name,
        project_config_path=project_config_path,
        p4_checkout=req.p4_checkout,
    )
    return cfg, target.redirected_from


def check_project_paths(req: RunRequest) -> Diagnostic | None:
    """``--project`` preflight (issue #23): ``VE-13`` when a path is missing.

    The project JSON's ``base`` and ``features`` entries resolve against
    the operational domain root (ARCHITECTURE.md Sec.3.3 and Sec.5.1).
    Run from outside the domain without ``--domain`` and they silently
    resolve under the wrong directory, surfacing later as a generic
    ``VE-01`` with no hint that ``--domain`` is the fix. This check loads
    the project JSON, resolves each entry, and returns a ``VE-13``
    diagnostic for the first missing path so the caller can stop before
    the pipeline runs.

    Returns ``None`` when there is no ``--project`` or every path exists,
    and for structural problems (unreadable, malformed, or non-object
    JSON) -- those stay ``ConfigService``'s responsibility (``VE-01`` /
    ``VE-04`` / schema diagnostics). Domain lookup failures raise
    :class:`AppError`.
    """
    if req.project is None:
        return None

    project_path = Path(req.project).resolve()
    try:
        with open(project_path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None

    domain_root = resolve_target(req.domain).root

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
    domain_source = "--domain" if req.domain is not None else "cwd"
    hint = (
        f"Resolved from domain root {domain_root.as_posix()!r} "
        f"(from {domain_source}). "
        "Pass --domain <path-to-domain-root>, or 'cd' into the domain "
        "root before running Chopper. See ARCHITECTURE.md Sec.3.3."
    )
    return Diagnostic.build(
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
            "domain_source": domain_source,
            "missing": [{"field": f, "path": p.as_posix()} for f, p in missing],
        },
    )


def open_context(
    cfg: RunConfig,
    redirected_from: Path | None,
    progress: ProgressSink,
) -> tuple[ChopperContext, CollectingSink]:
    """Construct the run context and its collecting diagnostic sink.

    Emits ``VI-03`` when the domain was redirected away from a
    ``*_backup`` path (ARCHITECTURE.md Sec.5.1) so the redirect is visible
    on stderr and in the audit bundle.
    """
    sink = CollectingSink()
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=sink, progress=progress)
    if redirected_from is not None:
        sink.emit(
            Diagnostic.build(
                "VI-03",
                phase=Phase.P1_CONFIG,
                message=(
                    f"--domain or cwd ended in '_backup' and a stripped sibling exists; "
                    f"resolved operational domain root to {cfg.domain_root.as_posix()!r} "
                    f"(redirected from {redirected_from.as_posix()!r}). "
                    "The original path is treated as the previous-run snapshot."
                ),
                path=redirected_from,
                hint=(
                    "If this redirect was unintended, rename the live domain so it does not "
                    "shadow the backup, or run from inside the intended domain"
                ),
                context={
                    "original_candidate": redirected_from.as_posix(),
                    "resolved_domain_root": cfg.domain_root.as_posix(),
                },
            )
        )
    return ctx, sink


def run(ctx: ChopperContext, command: Command) -> RunResult:
    """Dispatch ``validate`` / ``trim`` / ``loc`` through the single composer."""
    return ChopperRunner().run(ctx, command=command)


def loc_report(ctx: ChopperContext, result: RunResult) -> LocReport:
    """The ``chopper loc`` projection; baseline-only when the run aborted early."""
    manifest = getattr(result, "manifest", None)
    parsed = getattr(result, "parsed", None)
    if manifest is not None and parsed is not None:
        return build_loc_report(
            ctx=ctx,
            parsed=parsed,
            manifest=manifest,
            generated_artifacts=getattr(result, "generated_artifacts", None) or (),
        )
    return build_loc_report_baseline_only(ctx)


def domain_summary(ctx: ChopperContext, result: RunResult) -> DomainRunResult:
    """P4 branch-analysis counts for one completed domain run."""
    manifest = getattr(result, "manifest", None)
    edits = 0
    adds = 0
    removes = 0
    if manifest is not None:
        for treatment in manifest.file_decisions.values():
            # GENERATED counts as an edit: edit vs add is not knowable here
            # without filesystem access (conservative).
            if treatment is FileTreatment.PROC_TRIM or treatment is FileTreatment.GENERATED:
                edits += 1
            elif treatment is FileTreatment.REMOVE:
                removes += 1
    return DomainRunResult(
        domain_logical_name=ctx.config.domain_logical_name or ctx.config.domain_root.name,
        exit_code=getattr(result, "exit_code", 1),
        branch_needed=(edits + adds) > 0,
        edits_count=edits,
        adds_count=adds,
        removes_count=removes,
    )


def failed_domain_summary(domain: str | None, exit_code: int) -> DomainRunResult:
    """Branch-analysis entry for a domain that failed before its run started."""
    return DomainRunResult(
        domain_logical_name=str(domain) if domain is not None else "(unknown)",
        exit_code=exit_code,
        branch_needed=False,
        edits_count=0,
        adds_count=0,
        removes_count=0,
    )


def p4_opened_paths(ctx: ChopperContext, result: RunResult) -> list[Path]:
    """Absolute paths ``--p4`` checkout opened for edit.

    Empty when ``--p4`` was not passed, checkout was skipped or failed, or
    the run was a dry-run (``trim_report.p4_checkout`` is ``None`` then).
    """
    trim_report = getattr(result, "trim_report", None)
    p4_checkout = getattr(trim_report, "p4_checkout", None) if trim_report is not None else None
    if p4_checkout is None or not p4_checkout.checked_out:
        return []
    return [(ctx.config.domain_root / rel).resolve() for rel in p4_checkout.checked_out]


def remove_backup(domain_root: Path) -> CleanupOutcome:
    """Remove ``<domain>_backup/``; a missing backup is a no-op."""
    backup_root = domain_root.with_name(domain_root.name + "_backup")
    if not backup_root.exists():
        return CleanupOutcome(backup_root, removed=False)
    shutil.rmtree(backup_root)
    return CleanupOutcome(backup_root, removed=True)


def record_crash(exc: BaseException) -> InternalError:
    """Write ``.chopper/internal-error.log`` for a failure outside the runner.

    There is no context yet, so the log lands under ``Path.cwd()/.chopper``.
    """
    return write_internal_error_log(None, run_id=uuid.uuid4().hex, exc=exc)
