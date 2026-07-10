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

from chopper.audit.sloc import count_sloc
from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Severity
from chopper.core.fs_walk import EXCLUDED_FILENAMES, EXCLUDED_SUFFIXES, TEXT_LIKE_EXTENSIONS, walk_files
from chopper.core.models_audit import RunResult
from chopper.core.models_common import DomainRunResult, FileTreatment
from chopper.core.models_trimmer import TrimReport

__all__ = [
    "render_audit_bundle_locations",
    "render_cleanup_message",
    "render_diagnostics",
    "render_p4_branch_analysis",
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


def render_trim_stats(
    ctx: ChopperContext,
    result: RunResult,
    stream: TextIO | None = None,
) -> None:
    """Render a console-width-aware before/after stats table.

    No-op when ``result.trim_report`` is absent (dry-run, validate-only,
    early abort) or when the rebuilt domain has not been written to disk
    yet. SLOC is computed by reading the backup (before) and domain
    (after) files via the local filesystem; failures fall back to ``-``.
    """

    report = result.trim_report
    if report is None or not report.outcomes:
        return

    out = stream if stream is not None else sys.stderr
    width = max(60, _shutil.get_terminal_size(fallback=(100, 24)).columns)

    rows = _collect_rows(ctx, report)
    rows.extend(_collect_generated_rows(ctx, result.generated_artifacts))
    rows.extend(_collect_dropped_rows(ctx, report, result.generated_artifacts))
    rows.sort(key=lambda r: str(r["path"]))
    if not rows:  # pragma: no cover - unreachable: outcomes non-empty => _collect_rows yields >=1 row
        return

    totals = _totals_row(rows)
    _render_table(out, rows, totals, width=width)


def _is_excluded_artifact(rel: Path) -> bool:
    """Return ``True`` when ``rel`` is an authoring artifact, not a domain file.

    Mirrors :mod:`chopper.core.fs_walk` so the live console table, the
    LOC reporter, and the audit ``trim_stats.json`` agree on the set
    of files that contribute to before/after deltas.  See
    ARCHITECTURE.md \u00a75.5.13.
    """

    return rel.name in EXCLUDED_FILENAMES or rel.suffix.lower() in EXCLUDED_SUFFIXES


def _collect_rows(ctx: ChopperContext, report: TrimReport) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    backup_root: Path = ctx.config.backup_root
    domain_root: Path = ctx.config.domain_root
    dry_run = ctx.config.dry_run

    for outcome in report.outcomes:
        if _is_excluded_artifact(outcome.path):
            continue
        # In dry-run no backup is taken; the pre-trim source still
        # lives at ``domain_root`` (the trimmer never wrote). Prefer
        # the backup when present so both modes report the same
        # baseline (A7).
        sloc_in = _safe_sloc(backup_root / outcome.path, outcome.path)
        if sloc_in is None and dry_run:
            sloc_in = _safe_sloc(domain_root / outcome.path, outcome.path)
        if outcome.treatment is FileTreatment.REMOVE:
            sloc_out: int | None = 0
        else:
            sloc_out = _safe_sloc(domain_root / outcome.path, outcome.path)

        rows.append(
            {
                "path": outcome.path.as_posix(),
                "treatment": _treatment_label(outcome.treatment),
                "bytes_in": outcome.bytes_in,
                "bytes_out": outcome.bytes_out,
                "sloc_in": sloc_in,
                "sloc_out": sloc_out,
                "kept": len(outcome.procs_kept),
                "removed": len(outcome.procs_removed),
            }
        )

    return rows


def _collect_generated_rows(
    ctx: ChopperContext,
    artifacts: Sequence,
) -> list[dict[str, object]]:
    """Build rows for GENERATED artifacts (stage tcl / stack / csv).

    Under dry-run the rebuilt domain does not exist on disk, so the
    ``out`` side comes from :attr:`GeneratedArtifact.content` directly.
    Under live trim the on-disk file is read (it has already passed
    through the optional P5c indentation pass). If the same path
    existed in the source domain (now under ``backup_root``) its bytes
    are captured as the ``in`` baseline so the regenerate-in-place
    case shows a real before->after delta.
    """

    rows: list[dict[str, object]] = []
    domain_root: Path = ctx.config.domain_root
    backup_root: Path = ctx.config.backup_root
    dry_run = ctx.config.dry_run

    for artifact in artifacts:
        rel: Path = artifact.path
        if _is_excluded_artifact(rel):
            continue
        if dry_run:
            # No filesystem write happened -- the artifact content is
            # the authoritative "after" payload.
            text = artifact.content
        else:
            target = domain_root / rel
            try:
                text = target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = artifact.content
        bytes_out = len(text.encode("utf-8"))
        sloc_out = count_sloc(rel, text)

        # Pre-existing source for this generated path?  Under live trim
        # it lives at ``backup_root``; under dry-run it is still at
        # ``domain_root`` (the trimmer never wrote, so backup was never
        # taken).  Try both, preferring backup when present.
        bytes_in = 0
        sloc_in: int | None = 0
        src_text: str | None = None
        for candidate in (backup_root / rel, domain_root / rel) if dry_run else (backup_root / rel,):
            try:
                src_text = candidate.read_text(encoding="utf-8", errors="replace")
                break
            except OSError:
                continue
        if src_text is not None:
            bytes_in = len(src_text.encode("utf-8"))
            sloc_in = count_sloc(rel, src_text)

        rows.append(
            {
                "path": rel.as_posix(),
                "treatment": "GEN ",
                "bytes_in": bytes_in,
                "bytes_out": bytes_out,
                "sloc_in": sloc_in,
                "sloc_out": sloc_out,
                "kept": 0,
                "removed": 0,
            }
        )

    return rows


def _collect_dropped_rows(
    ctx: ChopperContext,
    report: TrimReport,
    artifacts: Sequence,
) -> list[dict[str, object]]:
    """Add DROP rows for domain files the trim removed entirely.

    The trimmer records outcomes only for files it rewrote or copied;
    files dropped under default-exclude (R2) never appear in
    ``report.outcomes``. To make the live console table cover the whole
    domain -- matching ``chopper loc`` and the audit
    ``trim_stats.json`` -- walk the pristine source tree
    (``backup_root`` when present, else ``domain_root``) and emit a
    DROP row for every source file not already accounted for as a
    rewrite, copy, or generated artifact.
    """

    source_root: Path = ctx.config.backup_root if ctx.fs.exists(ctx.config.backup_root) else ctx.config.domain_root
    accounted = {o.path.as_posix() for o in report.outcomes}
    accounted |= {a.path.as_posix() for a in artifacts}

    rows: list[dict[str, object]] = []
    for rel in walk_files(ctx.fs, source_root):
        # ``walk_files`` already hard-excludes authoring artifacts
        # (``.json`` / ``instructions.md``) and the ``.chopper/`` tree,
        # so no further artifact filtering is needed here.
        if rel.as_posix() in accounted:
            continue
        try:
            raw = (source_root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        bytes_in = len(raw.encode("utf-8"))
        sloc_in: int | None = count_sloc(rel, raw) if rel.suffix.lower() in TEXT_LIKE_EXTENSIONS else 0
        rows.append(
            {
                "path": rel.as_posix(),
                "treatment": "DROP",
                "bytes_in": bytes_in,
                "bytes_out": 0,
                "sloc_in": sloc_in,
                "sloc_out": 0,
                "kept": 0,
                "removed": 0,
            }
        )

    return rows


def _totals_row(rows: Sequence[dict[str, object]]) -> dict[str, object]:
    """Aggregate row across every file in the domain.

    The row sums all files the trim touched: rewrites (COPY/TRIM),
    generated artifacts (GEN), and files dropped entirely (DROP). The
    full-domain coverage means these totals match ``chopper loc`` and
    the audit bundle's ``trim_stats.json`` byte-for-byte. The label and
    the values are intentionally identical between live and dry-run
    modes so the two tables can be diffed byte-for-byte (A7).
    """

    def _isum(key: str) -> int:
        total = 0
        for r in rows:
            v = r[key]
            if isinstance(v, int):
                total += v
        return total

    return {
        "path": "TOTAL",
        "treatment": f"{len(rows)} files",
        "bytes_in": _isum("bytes_in"),
        "bytes_out": _isum("bytes_out"),
        "sloc_in": _isum("sloc_in"),
        "sloc_out": _isum("sloc_out"),
        "kept": _isum("kept"),
        "removed": _isum("removed"),
    }


_TREATMENT_LABELS = {
    FileTreatment.FULL_COPY: "COPY",
    FileTreatment.PROC_TRIM: "TRIM",
    FileTreatment.REMOVE: "DROP",
    FileTreatment.GENERATED: "GEN ",
}


def _treatment_label(treatment: FileTreatment) -> str:
    return _TREATMENT_LABELS.get(treatment, str(treatment))


def _safe_sloc(path: Path, rel: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return count_sloc(rel, text)


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


def _render_table(
    out: TextIO,
    rows: Sequence[dict[str, object]],
    totals: dict[str, object],
    *,
    width: int,
) -> None:
    headers = ["File", "Op", "SLOC (in -> out)", "Procs (kept/dropped)"]

    body: list[list[str]] = []
    for r in rows:
        body.append(
            [
                str(r["path"]),
                str(r["treatment"]),
                _fmt_pair(r["sloc_in"], r["sloc_out"]),  # type: ignore[arg-type]
                f"{r['kept']}/{r['removed']}",
            ]
        )
    body.append(
        [
            str(totals["path"]),
            str(totals["treatment"]),
            _fmt_pair(totals["sloc_in"], totals["sloc_out"]),  # type: ignore[arg-type]
            f"{totals['kept']}/{totals['removed']}",
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
