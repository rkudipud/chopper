"""P5d companion-file sync -- FD-15 / ARCHITECTURE.md Sec.5.5 P5d.

For every ``PROC_TRIM`` file whose POSIX basename matches
``default_rules.<sfx>.tcl``, two companion files that were
``FULL_COPY``-written into the rebuilt domain are filtered in-place:

* ``<dir>/default_config.<sfx>.csv``   -- rows for non-surviving procs deleted.
* ``<dir>/default_milestone.<sfx>.tcl`` -- ``change_config <ProcName>`` lines
  for non-surviving procs deleted.

The surviving proc set is derived from ``CompiledManifest.proc_decisions``
(the final compiled PI set), which accounts for both ``procedures.include``
and ``procedures.exclude`` across all feature layers (R1 overlay).

Companion files are expected to be declared as ``files.include`` entries so
they are unconditionally ``FULL_COPY``-present in the rebuilt domain before
P5d runs.  If a companion is absent ``VW-24 companion-file-missing`` is
emitted and sync is skipped for that file.  On success ``VI-04
companion-sync-applied`` is emitted.

The returned :class:`~chopper.core.models_trimmer.TrimReport` carries
updated ``bytes_out`` for every ``FULL_COPY`` outcome whose companion file
was rewritten, so P6's ``VW-10`` byte-size check remains accurate.

P5d is skipped entirely under ``--dry-run`` (the runner never calls this
module in that case).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest
from chopper.core.models_trimmer import FileOutcome, TrimReport

__all__ = ["CompanionSyncService"]

# Matches e.g. "default_rules.fm.tcl", "default_rules.cfm.tcl".
# Group 1 captures the suffix token (everything between the two dots).
_RULES_RE = re.compile(r"^default_rules\.(.+)\.tcl$")

# Matches "change_config ProcName ..." anywhere in a milestone line.
# Group 1 is the proc name.
_CHANGE_CONFIG_RE = re.compile(r"^\s*change_config\s+(\w+)\b")

_Mode = Literal["csv", "milestone"]


class CompanionSyncService:
    """P5d: filter companion CSV/milestone files after P5c.

    Instantiate and call :meth:`run` from the orchestrator after
    :class:`~chopper.trimmer.indentation.TclIndentationService` returns.
    """

    def run(
        self,
        ctx: ChopperContext,
        manifest: CompiledManifest,
        trim_report: TrimReport,
    ) -> TrimReport:
        """Apply P5d companion-file sync.

        Returns an updated :class:`TrimReport` with corrected ``bytes_out``
        for every ``FULL_COPY`` companion outcome that was rewritten.
        If no companion files are found or modified the original
        ``trim_report`` is returned unchanged.
        """
        updated_bytes: dict[Path, int] = {}

        for rel_path in sorted(manifest.file_decisions, key=lambda p: p.as_posix()):
            if manifest.file_decisions[rel_path] is not FileTreatment.PROC_TRIM:
                continue

            m = _RULES_RE.match(rel_path.name)
            if m is None:
                continue

            sfx = m.group(1)
            parent = rel_path.parent

            # Final PI proc names for this file (qualified name within the file,
            # i.e. the part after the first "::" in the canonical name).
            pi_names: frozenset[str] = frozenset(
                cn.split("::", 1)[1]
                for cn, decision in manifest.proc_decisions.items()
                if decision.source_file == rel_path
            )

            csv_rel = parent / f"default_config.{sfx}.csv"
            milestone_rel = parent / f"default_milestone.{sfx}.tcl"

            companions: list[tuple[Path, _Mode]] = [
                (csv_rel, "csv"),
                (milestone_rel, "milestone"),
            ]
            for companion_rel, mode in companions:
                new_size = self._sync_one(ctx, companion_rel, pi_names, mode)
                if new_size is not None:
                    updated_bytes[companion_rel] = new_size

        if not updated_bytes:
            return trim_report

        return _with_updated_companion_bytes(trim_report, updated_bytes)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sync_one(
        self,
        ctx: ChopperContext,
        companion_rel: Path,
        pi_names: frozenset[str],
        mode: _Mode,
    ) -> int | None:
        """Filter one companion file in-place.

        Returns the new ``bytes_out`` on success, or ``None`` if the file
        was absent (``VW-24`` emitted) or an I/O error occurred.
        """
        companion_abs = ctx.config.domain_root / companion_rel

        if not ctx.fs.exists(companion_abs):
            ctx.diag.emit(
                Diagnostic.build(
                    "VW-24",
                    phase=Phase.P5_TRIM,
                    message=(
                        f"companion-file sync: expected {companion_rel.as_posix()!r} "
                        "not found in rebuilt domain -- declare it in files.include"
                    ),
                    path=companion_rel,
                )
            )
            return None

        try:
            text = ctx.fs.read_text(companion_abs)
            filtered = _filter_csv(text, pi_names) if mode == "csv" else _filter_milestone(text, pi_names)
            ctx.fs.write_text(companion_abs, filtered)
        except (OSError, UnicodeDecodeError):
            # Best-effort: don't break the run for a companion sync failure.
            return None

        new_size = len(filtered.encode("utf-8"))
        ctx.diag.emit(
            Diagnostic.build(
                "VI-04",
                phase=Phase.P5_TRIM,
                message=(f"companion-sync-applied: filtered {companion_rel.as_posix()!r} to match surviving proc set"),
                path=companion_rel,
            )
        )
        return new_size


# ---------------------------------------------------------------------------
# Filter algorithms
# ---------------------------------------------------------------------------


def _filter_csv(text: str, pi_names: frozenset[str]) -> str:
    """Return *text* with non-surviving proc rows removed.

    * Original blank lines and ``#``-comment lines are kept unchanged.
    * Data rows whose first comma-separated column (proc name, stripped) is
      absent from *pi_names* are deleted entirely -- no blank placeholder.
    """
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            result.append(line)
        else:
            col0 = stripped.split(",")[0].strip()
            if col0 in pi_names:
                result.append(line)
    return "".join(result)


def _filter_milestone(text: str, pi_names: frozenset[str]) -> str:
    """Return *text* with non-surviving ``change_config`` lines removed.

    * ``change_config <ProcName> ...`` lines whose ``<ProcName>`` is absent
      from *pi_names* are deleted entirely -- no blank placeholder.
    * All other lines (blanks, comments, other Tcl statements) are kept.
    """
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        m = _CHANGE_CONFIG_RE.match(line)
        if m:
            if m.group(1) in pi_names:
                result.append(line)
            # else: drop the line entirely
        else:
            result.append(line)
    return "".join(result)


# ---------------------------------------------------------------------------
# TrimReport byte-count update
# ---------------------------------------------------------------------------


def _with_updated_companion_bytes(
    report: TrimReport,
    updated_bytes: dict[Path, int],
) -> TrimReport:
    """Rebuild *report* with corrected ``bytes_out`` for companion FULL_COPY outcomes."""
    new_outcomes: list[FileOutcome] = []
    changed = False
    for outcome in report.outcomes:
        new_size = updated_bytes.get(outcome.path)
        if new_size is None or outcome.treatment is not FileTreatment.FULL_COPY:
            new_outcomes.append(outcome)
            continue
        changed = changed or new_size != outcome.bytes_out
        new_outcomes.append(
            FileOutcome(
                path=outcome.path,
                treatment=outcome.treatment,
                bytes_in=outcome.bytes_in,
                bytes_out=new_size,
                procs_kept=outcome.procs_kept,
                procs_removed=outcome.procs_removed,
            )
        )
    if not changed:
        return report
    outcomes_t = tuple(new_outcomes)
    return TrimReport(
        outcomes=outcomes_t,
        files_copied=sum(1 for o in outcomes_t if o.treatment is FileTreatment.FULL_COPY),
        files_trimmed=sum(1 for o in outcomes_t if o.treatment is FileTreatment.PROC_TRIM),
        files_removed=sum(1 for o in outcomes_t if o.treatment is FileTreatment.REMOVE),
        procs_kept_total=sum(len(o.procs_kept) for o in outcomes_t),
        procs_removed_total=sum(len(o.procs_removed) for o in outcomes_t),
        rebuild_interrupted=report.rebuild_interrupted,
        inputs_preserved=report.inputs_preserved,
    )
