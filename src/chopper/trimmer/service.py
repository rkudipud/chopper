"""P5 trimmer service -- top-level state machine.

Dispatches per-file FULL_COPY / PROC_TRIM / REMOVE operations over
``domain/`` based on :class:`CompiledManifest`, using ``domain_backup/``
as the authoritative source tree. Prep varies by domain-state case:

* Case 1 (domain only)            -- move ``.chopper`` aside, rename to backup, create fresh domain.
* Case 2 (domain + backup)        -- delete domain, recreate empty; backup untouched.
* Case 3 (backup only)            -- recreate empty domain; backup untouched.
* Case 4 (neither)                -- never reached; fatal at P0.

``--dry-run`` skips all filesystem mutation; the returned
:class:`TrimReport` still describes planned actions so audit at P7 is
faithful.

If dispatch aborts mid-run, the partial domain is left in place and the
next invocation rebuilds cleanly from the intact backup
(``rebuild_interrupted=True`` in the trim report).

Optional P4 checkout-before-edit (``--p4``, opt-in, FR-53)
-----------------------------------------------------------
When ``RunConfig.p4_checkout`` is True and the run is not a dry-run,
``run()`` runs ``p4 edit -t text+x`` on every ``PROC_TRIM`` / regenerate-
in-place ``GENERATED`` path *before* ``_prepare_workspace()`` renames
anything -- Perforce tracks "opened" state by client path, not inode, so
checking out the real pre-trim files before the rename/rebuild still
counts as "that path got edited" once the new content lands. This only
runs on ``DomainState.case == 1`` (a genuine first trim): on a re-trim
(cases 2/3) ``domain_root`` no longer holds the original p4-synced
files, so checkout is skipped with a reason rather than attempted.

Failure handling is asymmetric by design:

* If checkout itself fails partway through the batch, nothing has been
  renamed or rewritten yet -- rollback is just ``p4 revert`` on whatever
  succeeded before the failing file, then the whole trim aborts
  (``VE-37``).
* If a *later* P5 step fails after checkout already succeeded, rollback
  additionally restores ``domain/`` from ``domain_backup/`` immediately
  (rather than deferring to the next invocation, which is the default
  recovery timing for every other P5 failure).

Chopper never runs ``p4 add``, ``p4 delete``, or ``p4 submit`` here --
only ``p4 edit`` (checkout) and, on rollback, ``p4 revert``. See
``src/chopper/trimmer/p4_checkout.py`` and
``technical_docs/ARCHITECTURE.md`` FR-53.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models_common import DomainState, FileTreatment
from chopper.core.models_compiler import CompiledManifest
from chopper.core.models_parser import ParseResult
from chopper.core.models_trimmer import FileOutcome, P4CheckoutResult, TrimReport
from chopper.trimmer.file_writer import full_copy_file, proc_trim_file, remove_file
from chopper.trimmer.p4_checkout import check_p4_available, checkout_files, revert_files
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
        # Dry-run short-circuit. Produce a plan-only report from the
        # manifest without touching the filesystem. p4 checkout never runs
        # under --dry-run, regardless of --p4.
        # ------------------------------------------------------------------
        if ctx.config.dry_run:
            return _plan_only_report(manifest)

        # ------------------------------------------------------------------
        # Optional P4 checkout-before-edit (opt-in --p4). Must run before
        # _prepare_workspace() -- see module docstring for why.
        # ------------------------------------------------------------------
        p4_result: P4CheckoutResult | None = None
        if ctx.config.p4_checkout:
            p4_result = _perform_p4_checkout(ctx, manifest, state)
            if p4_result.failed:
                _emit_ve37(ctx, p4_result)
                return _empty_report(interrupted=True, p4_checkout=p4_result)

        # ------------------------------------------------------------------
        # Phase 5a prep
        # ------------------------------------------------------------------
        try:
            self._prepare_workspace(ctx, state)
        except OSError as exc:
            p4_result = _rollback_late_failure(ctx, p4_result, state)
            _emit_ve23(ctx, f"workspace preparation failed: {exc}")
            return _empty_report(interrupted=True, p4_checkout=p4_result)

        # ------------------------------------------------------------------
        # Per-file dispatch
        # ------------------------------------------------------------------
        keep_by_file = _keep_by_file(manifest)
        outcomes: list[FileOutcome] = []
        interrupted = False

        for rel_path in sorted(manifest.file_decisions, key=lambda p: p.as_posix()):
            treatment = manifest.file_decisions[rel_path]
            if treatment is FileTreatment.GENERATED:
                # GENERATED files are written by GeneratorService, not by
                # the trimmer. They have no backup source, so skipping them
                # here is correct.
                continue
            try:
                outcome = self._dispatch(ctx, rel_path, treatment, parsed, keep_by_file)
            except ProcDropError as exc:
                _emit_ve26(ctx, rel_path, str(exc))
                interrupted = True
                p4_result = _rollback_late_failure(ctx, p4_result, state)
                break
            except FileNotFoundError as exc:
                _emit_ve24(ctx, rel_path, str(exc))
                interrupted = True
                p4_result = _rollback_late_failure(ctx, p4_result, state)
                break
            except OSError as exc:
                _emit_ve25(ctx, rel_path, str(exc))
                interrupted = True
                p4_result = _rollback_late_failure(ctx, p4_result, state)
                break
            outcomes.append(outcome)

        outcomes.sort(key=lambda o: o.path.as_posix())
        return _build_report(outcomes, rebuild_interrupted=interrupted, p4_checkout=p4_result)

    # ------------------------------------------------------------------
    # Workspace prep per Sec.2.8
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
            # Sync the user's current jsons/ into the backup before
            # deleting the domain. Users edit JSONs in <domain>/jsons/,
            # not in <domain>_backup/jsons/. Without this step the stale
            # backup copy would overwrite their edits when
            # preserve_input_sources mirrors jsons/ back at P5a tail.
            self._sync_domain_jsons_to_backup(ctx, domain, backup)
            ctx.fs.remove(domain, recursive=True)
            ctx.fs.mkdir(domain, parents=True, exist_ok=False)
        elif state.case == 3:
            ctx.fs.mkdir(domain, parents=True, exist_ok=False)
        else:  # pragma: no cover -- guarded by run()
            raise ValueError(f"unexpected DomainState case {state.case}")

    # ------------------------------------------------------------------
    # JSON sync for Case 2 reruns
    # ------------------------------------------------------------------
    @staticmethod
    def _sync_domain_jsons_to_backup(ctx: ChopperContext, domain: Path, backup: Path) -> None:
        """Copy ``<domain>/jsons/`` -> ``<domain>_backup/jsons/`` so the
        backup always reflects the user's latest JSON edits.

        Users edit JSONs in the working domain, not in the backup. On a
        Case 2 rerun the domain is about to be deleted; without this
        sync step the stale backup copy would win when
        ``preserve_input_sources`` mirrors jsons/ back at P5a tail.

        Failures are suppressed -- the run will proceed with whatever
        jsons/ content the backup already contains.
        """
        domain_jsons = domain / "jsons"
        backup_jsons = backup / "jsons"

        if not ctx.fs.exists(domain_jsons):
            return

        try:
            # Remove stale backup jsons/ first so deleted files don't
            # persist (e.g. user removed a feature JSON between runs).
            if ctx.fs.exists(backup_jsons):
                ctx.fs.remove(backup_jsons, recursive=True)
            ctx.fs.mkdir(backup_jsons, parents=True, exist_ok=True)
            _sync_dir(ctx, domain_jsons, backup_jsons)
        except OSError:
            # Best-effort; preserve_input_sources will use whatever the
            # backup has. The run itself is unaffected because P1 already
            # loaded the JSONs from the domain path before we got here.
            pass

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
            outcome = proc_trim_file(ctx, rel_path, parsed=parsed_file, keep_canonical=keep_canonical)
            if not outcome.procs_removed:
                _emit_vw22(ctx, rel_path)
            return outcome
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


def _empty_report(*, interrupted: bool, p4_checkout: P4CheckoutResult | None = None) -> TrimReport:
    return TrimReport(
        outcomes=(),
        files_copied=0,
        files_trimmed=0,
        files_removed=0,
        procs_kept_total=0,
        procs_removed_total=0,
        rebuild_interrupted=interrupted,
        p4_checkout=p4_checkout,
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


def _build_report(
    outcomes: list[FileOutcome], *, rebuild_interrupted: bool, p4_checkout: P4CheckoutResult | None = None
) -> TrimReport:
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
        p4_checkout=p4_checkout,
    )


# ---------------------------------------------------------------------------
# Optional P4 checkout-before-edit (opt-in --p4, FR-53)
# ---------------------------------------------------------------------------


def _compute_p4_edit_paths(ctx: ChopperContext, manifest: CompiledManifest) -> list[Path]:
    """Sorted ``PROC_TRIM`` + regenerate-in-place ``GENERATED`` paths to check out.

    Resolved against ``domain_root`` directly (not ``backup_root``) because
    this only ever runs before :meth:`TrimmerService._prepare_workspace`
    renames anything -- the caller gates this on ``DomainState.case == 1``,
    so ``domain_root`` still holds the original, un-rebuilt files.

    ``GENERATED`` paths that do not yet exist in ``domain_root`` are newly
    created stage files (``p4 add`` territory, not ``p4 edit``) -- excluded
    here by design; Chopper never runs ``p4 add``.
    """
    domain_root = ctx.config.domain_root
    paths: list[Path] = []
    for rel_path, treatment in manifest.file_decisions.items():
        if treatment is FileTreatment.PROC_TRIM:
            paths.append(rel_path)
        elif treatment is FileTreatment.GENERATED and ctx.fs.exists(domain_root / rel_path):
            paths.append(rel_path)
    paths.sort(key=lambda p: p.as_posix())
    return paths


def _perform_p4_checkout(ctx: ChopperContext, manifest: CompiledManifest, state: DomainState) -> P4CheckoutResult:
    """Run the pre-P5 P4 checkout step and return its typed outcome.

    Skips (``attempted=False``, with a reason) rather than attempting
    checkout when this is a re-trim (``state.case != 1`` -- ``domain_root``
    no longer holds the original p4-synced files) or when ``p4`` is
    unavailable / the domain is not a working p4 client workspace.

    On checkout failure, already-succeeded paths are reverted immediately
    (nothing has been renamed or rewritten yet at this point in ``run()``,
    so ``domain_restored`` stays ``False`` -- there is nothing to restore).
    """
    if state.case != 1:
        return P4CheckoutResult(
            attempted=False,
            skip_reason=(
                "a previous trim already exists (<domain>_backup/ present); P4 checkout "
                "only runs on a first trim, before any rebuild has occurred"
            ),
        )

    available, reason = check_p4_available(ctx.config.domain_root)
    if not available:
        return P4CheckoutResult(attempted=False, skip_reason=reason)

    edit_paths = _compute_p4_edit_paths(ctx, manifest)
    if not edit_paths:
        return P4CheckoutResult(attempted=True)

    succeeded, failed_path, failure_message = checkout_files(ctx.config.domain_root, edit_paths)
    if failed_path is not None:
        revert_files(ctx.config.domain_root, succeeded)
        return P4CheckoutResult(
            attempted=True,
            checked_out=succeeded,
            failed_path=failed_path,
            failure_message=failure_message,
            reverted=succeeded,
            domain_restored=False,
        )
    return P4CheckoutResult(attempted=True, checked_out=succeeded)


def _rollback_late_failure(
    ctx: ChopperContext, p4_result: P4CheckoutResult | None, state: DomainState
) -> P4CheckoutResult | None:
    """Recover from a P5 failure that happened *after* checkout already succeeded.

    No-op (returns ``p4_result`` unchanged) when checkout was never
    attempted, skipped, already failed, or checked out zero files -- in
    every one of those cases there is nothing p4-side to revert.

    Otherwise: ``p4 revert`` every checked-out path, and -- only for
    ``DomainState.case == 1``, the sole case checkout can run in --
    immediately restore ``domain/`` from ``domain_backup/`` rather than
    deferring to the next invocation's default rebuild-from-backup
    recovery. Best-effort: filesystem errors during the restore itself are
    swallowed so the original failure's diagnostic is what the user sees.
    """
    if p4_result is None or not p4_result.attempted or p4_result.failed or not p4_result.checked_out:
        return p4_result

    revert_files(ctx.config.domain_root, list(p4_result.checked_out))

    restored = False
    if state.case == 1:
        domain = ctx.config.domain_root
        backup = ctx.config.backup_root
        try:
            if ctx.fs.exists(domain):
                ctx.fs.remove(domain, recursive=True)
            if ctx.fs.exists(backup):
                ctx.fs.rename(backup, domain)
                restored = True
        except OSError:
            pass

    return replace(p4_result, reverted=p4_result.checked_out, domain_restored=restored)


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


def _emit_ve37(ctx: ChopperContext, p4_result: P4CheckoutResult) -> None:
    failed_display = p4_result.failed_path.as_posix() if p4_result.failed_path is not None else "<unknown>"
    ctx.diag.emit(
        Diagnostic.build(
            "VE-37",
            phase=Phase.P5_TRIM,
            message=f"p4 edit -t text+x failed for {failed_display!r}: {p4_result.failure_message}",
            path=p4_result.failed_path,
            hint=(
                "Check the reported file/reason (locked by another user, wrong client workspace, "
                "p4 not logged in, network/server issue), fix it, and re-run 'chopper trim --p4'. "
                "The domain is left exactly as it was before this run -- no partial state."
            ),
        )
    )


def _emit_vw22(ctx: ChopperContext, rel_path: Path) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VW-22",
            phase=Phase.P5_TRIM,
            message=(
                f"PROC_TRIM file had no procs to remove: {rel_path.as_posix()!r}. "
                "The backup copy already contains only the surviving proc set; "
                "the rebuilt file is byte-identical to the backup. "
                "Most likely cause: <domain>_backup/ holds a prior run's post-trim output "
                "rather than the original pre-trim source."
            ),
            path=rel_path,
            hint=(
                "Verify that <domain>_backup/ was not replaced with an already-trimmed copy between runs. "
                "If the backup is stale, restore the original source from version control, "
                "delete <domain>_backup/, and re-run chopper trim. "
                "Do not run chopper cleanup --confirm between regression passes "
                "if consistent proc-drop statistics across runs are required."
            ),
        )
    )


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _sync_dir(ctx: ChopperContext, src: Path, dst: Path) -> None:
    """Recursively copy all files under *src* into *dst*.

    Creates intermediate directories as needed. *dst* must already exist.
    """
    for child in ctx.fs.list(src):
        stat = ctx.fs.stat(child)
        rel = child.relative_to(src)
        dst_child = dst / rel
        if stat.is_dir:
            ctx.fs.mkdir(dst_child, parents=True, exist_ok=True)
            _sync_dir(ctx, child, dst_child)
        else:
            ctx.fs.mkdir(dst_child.parent, parents=True, exist_ok=True)
            ctx.fs.copy_file(child, dst_child)
