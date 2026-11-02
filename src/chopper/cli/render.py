"""Diagnostic / RunResult rendering for the CLI.

Services never render; the CLI does. This module takes a
:class:`RunResult` (returned by :class:`ChopperRunner.run`) plus the
diagnostic snapshot and writes a human-readable summary to
``stderr``.

Rendering is a pure consumer of data. No side effects beyond writing
to the provided text stream.
"""

from __future__ import annotations

import shutil as _shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from chopper.app.errors import AppError
from chopper.app.trim_stats import TrimStats
from chopper.core.diagnostics import Diagnostic, Severity
from chopper.core.models_audit import LocReport, RunResult
from chopper.core.models_common import DomainRunResult, FileTreatment

__all__ = [
    "render_app_error",
    "render_audit_bundle_locations",
    "render_cleanup_message",
    "render_diagnostics",
    "render_loc_report",
    "render_p4_branch_analysis",
    "render_p4_checkout_enabled_notice",
    "render_p4_checkout_notice",
    "render_p4_checkout_opened",
    "render_result",
    "render_trim_stats",
]


_SEVERITY_LABEL = {
    Severity.ERROR: "ERROR",
    Severity.WARNING: "WARN ",
    Severity.INFO: "INFO ",
}


# Diagnostic codes that are intentionally suppressed from CLI stderr
# output. They are still recorded in the audit bundle, so debugging is
# unaffected; we just keep the terminal scrollback signal-to-noise high.
#
# TI-01 (known-tool-command): emitted once per proc-call site that
# resolves to the tool-command pool (e.g. `get_cells`, `set_top`, `memory`).
# On a real flow this fires hundreds of times and drowns out the
# warnings/errors users actually need to act on.
_SUPPRESSED_STDERR_CODES: frozenset[str] = frozenset({"TI-01"})


def render_diagnostics(
    diagnostics: Sequence[Diagnostic],
    stream: TextIO | None = None,
) -> None:
    """Write each diagnostic as a one-line ``LEVEL CODE: message`` row."""

    out = stream if stream is not None else sys.stderr
    for d in diagnostics:
        if d.code in _SUPPRESSED_STDERR_CODES:
            continue
        label = _SEVERITY_LABEL[d.severity]
        location = ""
        if d.path is not None:
            location = f" [{d.path.as_posix()}"
            if d.line_no is not None:
                location += f":{d.line_no}"
            location += "]"
        out.write(f"{label} {d.code}:{location} {d.message}\n")


def render_result(
    result: RunResult,
    diagnostics: Sequence[Diagnostic],
    stream: TextIO | None = None,
) -> None:
    """Render diagnostics followed by a one-line summary."""

    render_diagnostics(diagnostics, stream=stream)
    out = stream if stream is not None else sys.stderr
    s = result.summary
    out.write(f"Summary: {s.errors} error(s), {s.warnings} warning(s), {s.infos} info(s); exit {result.exit_code}\n")


def render_app_error(error: AppError, stream: TextIO | None = None) -> None:
    """Write each :class:`AppError` issue as a ``[chopper] error`` block.

    ``[chopper] error (<code>): <message>``, an optional detail line, then
    ``  hint: <hint>``. Code-less issues are rendered by the caller as a
    fatal exit instead.
    """

    out = stream if stream is not None else sys.stderr
    for issue in error.issues:
        out.write(f"[chopper] error ({issue.code}): {issue.message}\n")
        if issue.detail is not None:
            out.write(f"  {issue.detail}\n")
        out.write(f"  hint: {issue.hint}\n")


def render_cleanup_message(message: str, stream: TextIO | None = None) -> None:
    """Write a user-facing ``chopper cleanup`` status line to ``stdout``.

    Cleanup is a direct filesystem operation -- it does not enter
    :class:`~chopper.orchestrator.runner.ChopperRunner`, so there are no
    diagnostics to render. The caller provides the prose; this helper
    centralises the output channel (``stdout``) so ``cli/render.py``
    remains the single place library code talks to the user.
    """

    out = stream if stream is not None else sys.stdout
    out.write(f"{message}\n")


# ---------------------------------------------------------------------------
# Trim stats table (rendered after ``chopper trim`` completes)
# ---------------------------------------------------------------------------


def render_trim_stats(stats: TrimStats | None, stream: TextIO | None = None) -> None:
    """Render a console-width-aware before/after stats table.

    No-op when ``stats`` is ``None`` (dry-run, validate-only, early
    abort) or has no rows.
    """

    if stats is None or not stats.rows:
        return
    out = stream if stream is not None else sys.stderr
    width = max(60, _shutil.get_terminal_size(fallback=(100, 24)).columns)
    _render_table(out, stats, width=width)


_TREATMENT_LABELS = {
    FileTreatment.FULL_COPY: "COPY",
    FileTreatment.PROC_TRIM: "TRIM",
    FileTreatment.REMOVE: "DROP",
    FileTreatment.GENERATED: "GEN ",
}


def _fmt_int(n: int | None) -> str:
    return "-" if n is None else f"{n:,}"


def _fmt_pair(before: int | None, after: int | None) -> str:
    """Format a ``before -> after`` cell with delta tail."""

    b = _fmt_int(before)
    a = _fmt_int(after)
    if before is None or after is None or before == after:
        return f"{b} -> {a}"
    delta = after - before
    sign = "+" if delta > 0 else ""
    return f"{b} -> {a} ({sign}{delta:,})"


def _render_table(out: TextIO, stats: TrimStats, *, width: int) -> None:
    headers = ["File", "Op", "SLOC (in -> out)", "Procs (kept/dropped)"]

    body: list[list[str]] = [
        [r.path, _TREATMENT_LABELS[r.treatment], _fmt_pair(r.sloc_in, r.sloc_out), f"{r.kept}/{r.removed}"]
        for r in stats.rows
    ]
    body.append(
        [
            "TOTAL",
            f"{len(stats.rows)} files",
            _fmt_pair(stats.sloc_in, stats.sloc_out),
            f"{stats.kept}/{stats.removed}",
        ]
    )

    # Compute natural column widths.
    col_w = [len(h) for h in headers]
    for row in body:
        for i, cell in enumerate(row):
            col_w[i] = max(col_w[i], len(cell))

    # Right-shrink the File column to fit terminal width.
    separator = "  "
    fixed = sum(col_w[1:]) + len(separator) * (len(headers) - 1)
    file_w = max(12, width - fixed)
    if col_w[0] > file_w:
        col_w[0] = file_w

    def _emit(row: Sequence[str]) -> None:
        cells = []
        for i, cell in enumerate(row):
            text = cell
            if i == 0 and len(text) > col_w[0]:
                # Left-truncate the path so the basename stays visible.
                text = "..." + text[-(col_w[0] - 1) :]
            # Right-align numeric-ish columns; left-align file/op.
            if i in (0, 1):
                cells.append(text.ljust(col_w[i]))
            else:
                cells.append(text.rjust(col_w[i]))
        out.write(separator.join(cells).rstrip() + "\n")

    out.write("\n")
    out.write("Trim stats:\n")
    rule = separator.join("-" * w for w in col_w)
    out.write(rule + "\n")  # top border
    _emit(headers)
    out.write(rule + "\n")  # header / body separator
    for row in body[:-1]:
        _emit(row)
    out.write(rule + "\n")  # body / total separator
    _emit(body[-1])  # TOTAL row
    out.write(rule + "\n")  # bottom border (footer)


# ---------------------------------------------------------------------------
# chopper loc report (one ``key: value`` line per metric)
# ---------------------------------------------------------------------------


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def render_loc_report(report: LocReport) -> None:
    """Print the LOC report as one ``key: value`` line per metric.

    Line-oriented on purpose (no tables, no alignment) so pipes, ``grep``,
    and harness captures parse it deterministically. Per-treatment subtotals
    are namespaced ``treatment.<NAME>.<field>``.
    """
    out = sys.stdout
    write = out.write

    write("chopper loc: read-only LOC report\n")
    write(f"files.before: {report.files_before}\n")
    write(f"files.after: {report.files_after}\n")
    write(f"files.delta: {report.files_after - report.files_before:+d}\n")
    write(f"files.reduction_pct: {_fmt_pct(report.files_pct_reduction)}\n")
    write(f"lines.before: {report.lines_before}\n")
    write(f"lines.after: {report.lines_after}\n")
    write(f"lines.delta: {report.lines_after - report.lines_before:+d}\n")
    write(f"lines.reduction_pct: {_fmt_pct(report.lines_pct_reduction)}\n")
    write(f"sloc.before: {report.sloc_before}\n")
    write(f"sloc.after: {report.sloc_after}\n")
    write(f"sloc.delta: {report.sloc_after - report.sloc_before:+d}\n")
    write(f"sloc.reduction_pct: {_fmt_pct(report.sloc_pct_reduction)}\n")
    for bucket in report.buckets:
        prefix = f"treatment.{bucket.treatment}"
        write(f"{prefix}.files: {bucket.files}\n")
        write(f"{prefix}.lines_before: {bucket.lines_before}\n")
        write(f"{prefix}.lines_after: {bucket.lines_after}\n")
        write(f"{prefix}.sloc_before: {bucket.sloc_before}\n")
        write(f"{prefix}.sloc_after: {bucket.sloc_after}\n")
    if report.lines_before == 0:
        write("note: no countable source files in domain\n")
    out.flush()


# ---------------------------------------------------------------------------
# P4 branch analysis summary (rendered after trim or dry-run)
# ---------------------------------------------------------------------------


def render_p4_branch_analysis(
    domain_results: Sequence[DomainRunResult],
    *,
    stream: TextIO = sys.stdout,
) -> None:
    """Print a P4 branch analysis summary after trim or dry-run.

    For each domain, classifies the run as "NO BRANCH NEEDED" (only file
    removals -- a P4 template resync is sufficient) or "BRANCH NEEDED"
    (at least one ``PROC_TRIM`` or ``GENERATED`` treatment means files
    will be modified or added, requiring a P4 branch).

    In multi-domain mode the per-domain verdicts are followed by an
    aggregate verdict and the list of domains that need a branch.

    See ``technical_docs/ARCHITECTURE.md`` Section 5.5.15 and FR-48.
    """
    if not domain_results:
        return

    stream.write("\n=== P4 Branch Analysis ===\n")

    needs_branch: list[str] = []

    for dr in domain_results:
        if dr.branch_needed:
            detail = f"{dr.edits_count} edit(s), {dr.adds_count} add(s)"
            verdict = f"BRANCH NEEDED ({detail})"
            needs_branch.append(dr.domain_logical_name)
        else:
            verdict = f"NO BRANCH NEEDED -- only {dr.removes_count} removal(s); P4 template resync sufficient"

        if len(domain_results) == 1:
            stream.write(f"{dr.domain_logical_name}: {verdict}\n")
        else:
            stream.write(f"  {dr.domain_logical_name:<30s} : {verdict}\n")

    if len(domain_results) > 1:
        stream.write("\n")
        if needs_branch:
            stream.write("Final verdict     : BRANCH NEEDED\n")
            stream.write(f"Domains needing branch: {', '.join(needs_branch)}\n")
        else:
            stream.write("Final verdict     : NO BRANCH NEEDED -- all domains are removal-only\n")

    stream.write("\n")


# ---------------------------------------------------------------------------
# Audit bundle location summary (rendered after ``chopper trim`` completes)
# ---------------------------------------------------------------------------


def render_audit_bundle_locations(
    domain_paths: Sequence[tuple[str, Path]],
    *,
    stream: TextIO = sys.stdout,
) -> None:
    """Print the resolved ``.chopper/`` audit bundle path for each domain.

    Rendered once, after ``chopper trim`` (live or ``--dry-run``) finishes
    processing every domain in the run. ``--domain`` accepts a CSV list for
    sequential multi-domain trims, so each domain gets its own audit bundle
    path on its own line rather than a single shared path.

    ``domain_paths`` entries that were never run (e.g. a domain that failed
    the pre-flight ``--project`` path check before a context was built) must
    be excluded by the caller -- this function assumes every entry it
    receives has a real, already-resolved ``.chopper/`` root.

    Flushed immediately (matching the domain-run-header convention in
    ``_print_domain_header``) so the message is visible right away even
    when stdout is redirected to a log file.

    See ``technical_docs/ARCHITECTURE.md`` Section 5.5.17 and FR-52.
    """
    if not domain_paths:
        return

    if len(domain_paths) == 1:
        _label, audit_root = domain_paths[0]
        resolved = audit_root.resolve().as_posix()
        stream.write(f"\nThe output logs and other files of this run can be found at: {resolved}\n\n")
        stream.flush()
        return

    stream.write("\n=== Audit Bundle Locations ===\n")
    stream.write("The output logs and other files of this run can be found at:\n")
    for label, audit_root in domain_paths:
        stream.write(f"  {label:<30s} : {audit_root.resolve().as_posix()}\n")
    stream.write("\n")
    stream.flush()


# ---------------------------------------------------------------------------
# P4 checkout enabled notice (rendered once per domain, before the pipeline
# runs, whenever --p4 was passed)
# ---------------------------------------------------------------------------


def render_p4_checkout_enabled_notice(*, stream: TextIO = sys.stdout) -> None:
    """Print a notice that ``--p4`` checkout-before-edit is enabled for this domain.

    Printed once per domain, immediately after the domain run header
    (``_print_domain_header``) and before the pipeline starts, whenever
    ``--p4`` was passed and the run is not a ``--dry-run`` (``--p4`` is a
    strict no-op under ``--dry-run``, so the notice is suppressed there --
    printing it would imply checkout runs when it never does).

    Purely informational: it does not report whether checkout will
    ultimately succeed, be skipped (``p4`` unavailable, or
    ``DomainState.case == 3``), or fail. Those outcomes are reported
    separately after the pipeline runs -- :func:`render_p4_checkout_notice`
    for skips, ``VE-37`` in ``diagnostics.json``/stderr for failures, and
    :func:`render_p4_checkout_opened` for the final list of paths actually
    opened. In a multi-domain CSV ``--domain`` run, this prints once per
    domain, right after that domain's own header -- matching the existing
    per-domain header convention.

    See ``technical_docs/ARCHITECTURE.md`` FR-53.
    """
    stream.write("  --p4 enabled: files will be checked out via 'p4 edit' before rewriting.\n")
    stream.flush()


# ---------------------------------------------------------------------------
# P4 checkout notice (rendered when --p4 could not run)
# ---------------------------------------------------------------------------


def render_p4_checkout_notice(
    message: str,
    *,
    plain: bool,
    stream: TextIO | None = None,
) -> None:
    """Print a screen-visible notice when ``--p4`` checkout could not run.

    Rendered in red (ANSI ``\\x1b[31m``...``\\x1b[0m``) when the target
    stream is a real terminal and ``plain`` is False; degrades to plain
    text otherwise (``--plain`` flag, non-tty redirection, or a captured
    stream in tests) -- matching the existing ``--plain`` convention used
    by :class:`~chopper.adapters.progress_rich.RichProgress` elsewhere in
    the CLI layer.

    This is advisory UX only -- no diagnostic code is emitted and the
    exit code is unaffected. ``chopper trim --p4`` falls back to a normal
    (non-p4) trim whenever this fires.

    See ``technical_docs/ARCHITECTURE.md`` FR-53.
    """
    out = stream if stream is not None else sys.stderr
    use_color = not plain and hasattr(out, "isatty") and out.isatty()
    text = f"[chopper] P4 EDIT NOT POSSIBLE -- {message}. Trimming in place without P4 checkout."
    if use_color:
        out.write(f"\x1b[31m{text}\x1b[0m\n")
    else:
        out.write(f"{text}\n")


# ---------------------------------------------------------------------------
# P4 files opened for edit (rendered on stdout after a successful --p4 checkout)
# ---------------------------------------------------------------------------


def render_p4_checkout_opened(
    entries: Sequence[tuple[str, Sequence[Path]]],
    *,
    stream: TextIO = sys.stdout,
) -> None:
    """Print the absolute paths Chopper opened for edit via ``--p4`` checkout.

    Rendered once, after ``chopper trim`` (live only -- ``--p4`` is a strict
    no-op under ``--dry-run``) finishes processing every domain in the run,
    immediately after the audit bundle location summary
    (:func:`render_audit_bundle_locations`).

    ``entries`` is a ``(label, checked_out_paths)`` pair per domain, mirroring
    the shape consumed by :func:`render_audit_bundle_locations`. Domains that
    checked out zero files (``--p4`` not passed, checkout skipped, checkout
    failed, or a manifest with no ``PROC_TRIM`` / regenerate-in-place
    ``GENERATED`` files) are silently excluded from the printed path list --
    this function is a no-op when every entry is empty. Multi-domain form
    (per-domain ``label:`` line) is chosen by the *original* entry count
    (``len(entries) > 1``), matching :func:`render_audit_bundle_locations` --
    a multi-domain CSV run keeps its per-domain labels even when only one
    domain actually checked out files, so the label is never ambiguous.

    This mirrors what a user would otherwise have to run ``p4 opened``
    to see -- Chopper already tracks exactly which paths it successfully
    opened via ``p4 edit`` (:attr:`~chopper.core.models_trimmer.P4CheckoutResult.checked_out`),
    so it reports them directly instead of requiring a separate manual
    check. No new ``p4`` subprocess call is made to produce this output.

    See ``technical_docs/ARCHITECTURE.md`` FR-53.
    """
    non_empty = [(label, paths) for label, paths in entries if paths]
    if not non_empty:
        return

    multi_domain = len(entries) > 1
    stream.write("=== P4 Files Opened for Edit ===\n")
    for label, paths in non_empty:
        if multi_domain:
            stream.write(f"{label}:\n")
        for path in paths:
            stream.write(f"  {path.as_posix()}\n")
    stream.flush()
