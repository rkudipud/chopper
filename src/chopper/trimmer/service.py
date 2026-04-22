"""Phase 5a trimmer — top-level state machine.

:class:`TrimmerService` consumes the Phase 0
:class:`~chopper.core.models.DomainState`, the frozen
:class:`~chopper.core.models.CompiledManifest`, and the Phase 2
:class:`~chopper.core.models.ParseResult`, and rebuilds the domain
directory per bible §2.8 / §5.2 P5.

State-machine summary
---------------------

+------+---------------+-------------------+----------------------------------+
| Case | ``domain/``   | ``domain_backup/``| Prep before per-file dispatch    |
+======+===============+===================+==================================+
| 1    | exists        | missing           | Move ``.chopper/`` aside, rename |
|      |               |                   | domain → backup, re-create empty |
|      |               |                   | domain.                          |
+------+---------------+-------------------+----------------------------------+
| 2    | exists        | exists            | Recursively delete domain,       |
|      |               |                   | re-create empty. Backup is       |
|      |               |                   | untouched and authoritative.     |
+------+---------------+-------------------+----------------------------------+
| 3    | missing       | exists            | Re-create empty domain. Backup   |
|      |               |                   | is authoritative.                |
+------+---------------+-------------------+----------------------------------+
| 4    | missing       | missing           | Never reached. ``DomainState``   |
|      |               |                   | case 4 is fatal at P0.           |
+------+---------------+-------------------+----------------------------------+

Under ``--dry-run`` the prep step is skipped and no files are written;
the returned :class:`TrimReport` still describes the planned actions
so the audit bundle at P7 is faithful.

Failure recovery
----------------

If the prep step completes but per-file dispatch aborts mid-run
(disk full, permission denied, ``VE-26`` proc-drop failure), the
partially rebuilt ``<domain>/`` is left in place and the backup
remains intact. On the next invocation the edge-case matrix observes
case 2 and rebuilds cleanly from the backup. The returned
:class:`TrimReport` has ``rebuild_interrupted=True`` in this path so
the audit output flags it.
"""

from __future__ import annotations

from pathlib import Path

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models import (
    CompiledManifest,
    DomainState,
    FileOutcome,
    FileTreatment,
    ParseResult,
    TrimReport,
)
from chopper.trimmer.file_writer import full_copy_file, proc_trim_file, remove_file
from chopper.trimmer.proc_dropper import ProcDropError

__all__ = ["TrimmerService"]


class TrimmerService:
    """Top-level P5a driver. See module docstring."""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(
        self,
        ctx: ChopperContext,
        manifest: CompiledManifest,
        parsed: ParseResult,
        state: DomainState,
    ) -> TrimReport:
        """Execute Phase 5a and return a frozen :class:`TrimReport`.

        The caller is expected to have emitted ``VE-21`` and exited
        before reaching here if ``state.case == 4``. This method asserts
        that invariant.
        """

        if state.case == 4:
            raise ValueError("TrimmerService.run must not be invoked with DomainState case 4 (fatal at P0)")

        # ------------------------------------------------------------------
        # Dry-run short-circuit (bible §5.2 "P5 — Build output (skipped
        # under --dry-run)"). Produce a plan-only report from the
        # manifest without touching the filesystem.
        # ------------------------------------------------------------------
        if ctx.config.dry_run:
            return _plan_only_report(manifest)

        # ------------------------------------------------------------------
        # Phase 5a prep
        # ------------------------------------------------------------------
        try:
            self._prepare_workspace(ctx, state)
        except OSError as exc:
            _emit_ve23(ctx, f"workspace preparation failed: {exc}")
            return _empty_report(interrupted=True)

        # ------------------------------------------------------------------
        # Per-file dispatch
        # ------------------------------------------------------------------
        keep_by_file = _keep_by_file(manifest)
        outcomes: list[FileOutcome] = []
        interrupted = False

        for rel_path in sorted(manifest.file_decisions, key=lambda p: p.as_posix()):
            treatment = manifest.file_decisions[rel_path]
            if treatment is FileTreatment.GENERATED:
                # Bible §P5b: GENERATED files are written by GeneratorService
                # in P5b, not by the trimmer. They have no backup source
                # (they do not exist until the generator emits them), so
                # skipping here is correct — the generator returns its own
                # :class:`GeneratedArtifact` records for audit.
                continue
            try:
                outcome = self._dispatch(ctx, rel_path, treatment, parsed, keep_by_file)
            except ProcDropError as exc:
                _emit_ve26(ctx, rel_path, str(exc))
                interrupted = True
                break
            except FileNotFoundError as exc:
                _emit_ve24(ctx, rel_path, str(exc))
                interrupted = True
                break
            except OSError as exc:
                _emit_ve25(ctx, rel_path, str(exc))
                interrupted = True
                break
            outcomes.append(outcome)

        outcomes.sort(key=lambda o: o.path.as_posix())
        return _build_report(outcomes, rebuild_interrupted=interrupted)

    # ------------------------------------------------------------------
    # Workspace prep per §2.8
    # ------------------------------------------------------------------
    def _prepare_workspace(self, ctx: ChopperContext, state: DomainState) -> None:
        """Execute the case-specific prep step.

        All four cases leave a clean, empty ``<domain>/`` ready for the
        per-file dispatch loop to populate from ``<domain>_backup/``.
        """

        domain = ctx.config.domain_root
        backup = ctx.config.backup_root

        if state.case == 1:
            # Move any pre-existing .chopper/ aside (it will be re-created
            # by P7 in the rebuilt domain).
            audit_in_domain = domain / ".chopper"
            if ctx.fs.exists(audit_in_domain):
                ctx.fs.remove(audit_in_domain, recursive=True)
            ctx.fs.rename(domain, backup)
            ctx.fs.mkdir(domain, parents=True, exist_ok=False)
        elif state.case == 2:
            ctx.fs.remove(domain, recursive=True)
            ctx.fs.mkdir(domain, parents=True, exist_ok=False)
        elif state.case == 3:
            ctx.fs.mkdir(domain, parents=True, exist_ok=False)
        else:  # pragma: no cover — guarded by run()
            raise ValueError(f"unexpected DomainState case {state.case}")

    # ------------------------------------------------------------------
    # Per-file dispatch
    # ------------------------------------------------------------------
    def _dispatch(
        self,
        ctx: ChopperContext,
        rel_path: Path,
        treatment: FileTreatment,
        parsed: ParseResult,
        keep_by_file: dict[Path, frozenset[str]],
    ) -> FileOutcome:
        if treatment is FileTreatment.FULL_COPY:
            procs_here = tuple(sorted(cn for cn in keep_by_file.get(rel_path, frozenset())))
            return full_copy_file(ctx, rel_path, procs_in_file=procs_here)
        if treatment is FileTreatment.PROC_TRIM:
            parsed_file = parsed.files.get(rel_path)
            if parsed_file is None:
                raise FileNotFoundError(
                    f"PROC_TRIM requested for {rel_path.as_posix()!r} but file is absent from ParseResult"
                )
            keep_canonical = keep_by_file.get(rel_path, frozenset())
            return proc_trim_file(ctx, rel_path, parsed=parsed_file, keep_canonical=keep_canonical)
        if treatment is FileTreatment.REMOVE:
            return remove_file(ctx, rel_path)
        if treatment is FileTreatment.GENERATED:
            # Filtered out at the dispatch loop; reaching here is a bug.
            raise ValueError(
                f"_dispatch received GENERATED treatment for {rel_path.as_posix()!r}; "
                "GENERATED files are owned by GeneratorService (P5b) and must be "
                "filtered before per-file dispatch"
            )
        raise ValueError(f"unknown FileTreatment for {rel_path.as_posix()!r}: {treatment!r}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _keep_by_file(manifest: CompiledManifest) -> dict[Path, frozenset[str]]:
    """Index surviving canonical procs by their source file path."""

    out: dict[Path, set[str]] = {}
    for cn, decision in manifest.proc_decisions.items():
        out.setdefault(decision.source_file, set()).add(cn)
    return {p: frozenset(v) for p, v in out.items()}


def _empty_report(*, interrupted: bool) -> TrimReport:
    return TrimReport(
        outcomes=(),
        files_copied=0,
        files_trimmed=0,
        files_removed=0,
        procs_kept_total=0,
        procs_removed_total=0,
        rebuild_interrupted=interrupted,
    )


def _plan_only_report(manifest: CompiledManifest) -> TrimReport:
    """Synthesize a TrimReport from manifest alone (dry-run path).

    Byte counts are zero because the filesystem is not touched. Surviving
    procs per file are derived from ``manifest.proc_decisions``.
    """

    keep_by_file = _keep_by_file(manifest)
    outcomes: list[FileOutcome] = []
    for rel_path in sorted(manifest.file_decisions, key=lambda p: p.as_posix()):
        treatment = manifest.file_decisions[rel_path]
        kept = tuple(sorted(keep_by_file.get(rel_path, frozenset())))
        if treatment is FileTreatment.GENERATED:
            # See :meth:`TrimmerService._dispatch` loop comment.
            continue
        if treatment is FileTreatment.FULL_COPY:
            outcomes.append(
                FileOutcome(
                    path=rel_path,
                    treatment=treatment,
                    bytes_in=0,
                    bytes_out=0,
                    procs_kept=kept,
                    procs_removed=(),
                )
            )
        elif treatment is FileTreatment.PROC_TRIM:
            outcomes.append(
                FileOutcome(
                    path=rel_path,
                    treatment=treatment,
                    bytes_in=0,
                    bytes_out=0,
                    procs_kept=kept,
                    procs_removed=(),
                )
            )
        elif treatment is FileTreatment.REMOVE:
            outcomes.append(
                FileOutcome(
                    path=rel_path,
                    treatment=treatment,
                    bytes_in=0,
                    bytes_out=0,
                    procs_kept=(),
                    procs_removed=(),
                )
            )
        else:
            raise ValueError(f"unknown FileTreatment for {rel_path.as_posix()!r}: {treatment!r}")
    return _build_report(outcomes, rebuild_interrupted=False)


def _build_report(outcomes: list[FileOutcome], *, rebuild_interrupted: bool) -> TrimReport:
    files_copied = sum(1 for o in outcomes if o.treatment is FileTreatment.FULL_COPY)
    files_trimmed = sum(1 for o in outcomes if o.treatment is FileTreatment.PROC_TRIM)
    files_removed = sum(1 for o in outcomes if o.treatment is FileTreatment.REMOVE)
    procs_kept_total = sum(len(o.procs_kept) for o in outcomes)
    procs_removed_total = sum(len(o.procs_removed) for o in outcomes)
    return TrimReport(
        outcomes=tuple(outcomes),
        files_copied=files_copied,
        files_trimmed=files_trimmed,
        files_removed=files_removed,
        procs_kept_total=procs_kept_total,
        procs_removed_total=procs_removed_total,
        rebuild_interrupted=rebuild_interrupted,
    )


# ---------------------------------------------------------------------------
# Diagnostic emit helpers
# ---------------------------------------------------------------------------


def _emit_ve23(ctx: ChopperContext, detail: str) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-23",
            phase=Phase.P5_TRIM,
            message=f"Filesystem error during trim: {detail}",
            hint="Inspect the underlying OS error; re-running will rebuild from backup (Case 2)",
        )
    )


def _emit_ve24(ctx: ChopperContext, rel_path: Path, detail: str) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-24",
            phase=Phase.P5_TRIM,
            message=f"Backup contents missing for {rel_path.as_posix()!r}: {detail}",
            hint=(
                "<domain>_backup/ must contain every file the manifest references; "
                "restore the backup or re-run without a partial backup tree"
            ),
        )
    )


def _emit_ve25(ctx: ChopperContext, rel_path: Path, detail: str) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-25",
            phase=Phase.P5_TRIM,
            message=f"Failed to write {rel_path.as_posix()!r} into rebuilt domain: {detail}",
            hint="Inspect the underlying OS error; partial domain will rebuild from backup on re-run",
        )
    )


def _emit_ve26(ctx: ChopperContext, rel_path: Path, detail: str) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-26",
            phase=Phase.P5_TRIM,
            message=f"Proc atomic drop failed for {rel_path.as_posix()!r}: {detail}",
            hint=(
                "Parser output is stale relative to the file on disk; re-run after reconciling "
                "the backup contents with the expected domain state"
            ),
        )
    )
