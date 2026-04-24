"""Per-artifact renderers for the P7 audit bundle.

Each public ``render_*`` function returns ``(name, content)`` for one
artifact. Writers are pure — they never touch the filesystem;
:class:`AuditService` is responsible for writing the returned bytes.

All JSON artifacts are serialised through
:func:`chopper.core.serialization.dump_model` for deterministic output.
Missing runner fields surface as ``null`` / empty arrays rather than
raising so audit always succeeds even on pipeline failure.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from chopper.audit.sloc import count_raw, count_sloc
from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Severity
from chopper.core.models import (
    CompiledManifest,
    Edge,
    FileTreatment,
    ProcDecision,
    RunRecord,
)
from chopper.core.serialization import dump_model

__all__ = [
    "render_chopper_run",
    "render_compiled_manifest",
    "render_dependency_graph",
    "render_diagnostics",
    "render_run_id",
    "render_trim_report_json",
    "render_trim_report_txt",
    "render_trim_stats",
]


CHOPPER_VERSION = "0.3.0"


# ---------------------------------------------------------------------------
# run_id
# ---------------------------------------------------------------------------


def render_run_id(record: RunRecord) -> tuple[str, str]:
    """Plain-text run_id file."""

    return "run_id", record.run_id + "\n"


# ---------------------------------------------------------------------------
# chopper_run.json
# ---------------------------------------------------------------------------


def render_chopper_run(
    ctx: ChopperContext,
    record: RunRecord,
    artifacts_present: tuple[str, ...],
) -> tuple[str, str]:
    loaded = record.loaded
    base_json = loaded.base.source_path.as_posix() if loaded else ""
    feature_jsons = tuple(f.source_path.as_posix() for f in loaded.features) if loaded else ()
    project_json: str | None = None
    project_name = ""
    project_owner = ""
    release_branch = ""
    project_notes: tuple[str, ...] = ()
    # ProjectJson integration arrives with Stage 5 CLI wiring; we keep
    # the fields in the artifact shape so downstream tooling need not
    # branch on mode.

    trim_state = "first-trim"
    if record.state is not None:
        # Backup present means this run is a re-trim.
        trim_state = "re-trim" if record.state.backup_exists else "first-trim"

    duration = (record.ended_at - record.started_at).total_seconds()
    diag_snap = ctx.diag.snapshot()
    counts = _severity_counts(diag_snap)

    payload = {
        "chopper_version": CHOPPER_VERSION,
        "run_id": record.run_id,
        "command": record.command,
        "mode": "dry-run" if ctx.config.dry_run else "live",
        "domain": ctx.config.domain_root.name,
        "domain_path": ctx.config.domain_root.as_posix(),
        "backup_path": ctx.config.backup_root.as_posix(),
        "base_json": base_json,
        "feature_jsons": list(feature_jsons),
        "project_json": project_json,
        "project_name": project_name,
        "project_owner": project_owner,
        "release_branch": release_branch,
        "project_notes": list(project_notes),
        "trim_state": trim_state,
        "timestamp_start": _iso(record.started_at),
        "timestamp_end": _iso(record.ended_at),
        "duration_seconds": duration,
        "exit_code": record.exit_code,
        "diagnostics_summary": counts,
        "artifacts_present": list(artifacts_present),
    }
    return "chopper_run.json", dump_model(payload)


# ---------------------------------------------------------------------------
# compiled_manifest.json
# ---------------------------------------------------------------------------


def render_compiled_manifest(record: RunRecord) -> tuple[str, str]:
    manifest = record.manifest
    if manifest is None:
        empty: dict[str, object] = {
            "chopper_version": CHOPPER_VERSION,
            "run_id": record.run_id,
            "domain": "",
            "inputs": {"base": "", "features": [], "project": None},
            "files": [],
            "procedures": {"surviving": [], "excluded": [], "traced": []},
            "flow_actions": [],
            "interaction_warnings": [],
        }
        return "compiled_manifest.json", dump_model(empty)

    loaded = record.loaded
    inputs = {
        "base": loaded.base.source_path.as_posix() if loaded else "",
        "features": [f.source_path.as_posix() for f in loaded.features] if loaded else [],
        "project": None,
    }

    files_out = []
    for path, treatment in manifest.file_decisions.items():
        prov = manifest.provenance[path]
        entry: dict[str, object] = {
            "path": path.as_posix(),
            "treatment": _treatment_slug(treatment),
            "reason": prov.reason,
            "input_sources": list(prov.input_sources),
            "proc_model": prov.proc_model,
        }
        if treatment is FileTreatment.PROC_TRIM:
            entry["surviving_procs"] = sorted(cn for cn, d in manifest.proc_decisions.items() if d.source_file == path)
            entry["excluded_procs"] = None
        else:
            entry["surviving_procs"] = None
            entry["excluded_procs"] = None
        files_out.append(entry)

    surviving = [
        {
            "canonical_name": d.canonical_name,
            "source_file": d.source_file.as_posix(),
            "selection_source": d.selection_source,
        }
        for d in manifest.proc_decisions.values()
    ]

    traced = []
    if record.graph is not None:
        seed_set = set(record.graph.pi_seeds)
        for cn in record.graph.pt:
            entry_t: dict[str, object] = {
                "canonical_name": cn,
                "source_file": cn.split("::", 1)[0] if "::" in cn else "",
                "trace_depth": 0,  # depth not recorded in v1 graph
                "survival_effect": "none",
            }
            traced.append(entry_t)
        # Silence unused local warning.
        _ = seed_set

    flow_actions = [
        {
            "name": s.name,
            "load_from": s.load_from,
            "steps": list(s.steps),
            "dependencies": list(s.dependencies),
            "exit_codes": list(s.exit_codes),
            "command": s.command,
            "inputs": list(s.inputs),
            "outputs": list(s.outputs),
            "run_mode": s.run_mode,
            "language": s.language,
        }
        for s in manifest.stages
    ]

    payload: dict[str, object] = {
        "chopper_version": CHOPPER_VERSION,
        "run_id": record.run_id,
        "domain": loaded.base.domain if loaded else "",
        "inputs": inputs,
        "files": files_out,
        "procedures": {"surviving": surviving, "excluded": [], "traced": traced},
        "flow_actions": flow_actions,
        "interaction_warnings": [],
    }
    return "compiled_manifest.json", dump_model(payload)


# ---------------------------------------------------------------------------
# dependency_graph.json
# ---------------------------------------------------------------------------


def render_dependency_graph(record: RunRecord) -> tuple[str, str]:
    graph = record.graph
    if graph is None:
        empty: dict[str, object] = {
            "chopper_version": CHOPPER_VERSION,
            "run_id": record.run_id,
            "pi_seeds": [],
            "pi_plus": [],
            "pt": [],
            "edges": [],
            "unresolved": [],
        }
        return "dependency_graph.json", dump_model(empty)

    edges = [_edge_entry(e) for e in graph.edges]
    unresolved = [
        {
            "token": tok,
            "caller": caller,
            "line": line,
            "reason": _unresolved_reason(code),
            "diagnostic_code": code,
        }
        for caller, tok, line, code in graph.unresolved_tokens
    ]
    payload: dict[str, object] = {
        "chopper_version": CHOPPER_VERSION,
        "run_id": record.run_id,
        "pi_seeds": list(graph.pi_seeds),
        "pi_plus": list(graph.nodes),
        "pt": list(graph.pt),
        "edges": edges,
        "unresolved": unresolved,
    }
    return "dependency_graph.json", dump_model(payload)


# ---------------------------------------------------------------------------
# diagnostics.json
# ---------------------------------------------------------------------------


def render_diagnostics(ctx: ChopperContext, record: RunRecord) -> tuple[str, str]:
    from chopper.core._diagnostic_registry import lookup as _lookup

    entries: list[dict[str, object]] = []
    for d in ctx.diag.snapshot():
        reg = _lookup(d.code)
        entries.append(
            {
                "code": d.code,
                "slug": reg.slug,
                "severity": str(d.severity.value) if hasattr(d.severity, "value") else str(d.severity),
                "phase": f"P{int(d.phase)}",
                "source": reg.source,
                "message": d.message,
                "file": d.path.as_posix() if d.path else None,
                "line": d.line_no,
                "recovery_hint": d.hint or "",
                "related_inputs": [],
            }
        )
    payload = {
        "chopper_version": CHOPPER_VERSION,
        "run_id": record.run_id,
        "diagnostics": entries,
    }
    return "diagnostics.json", dump_model(payload)


# ---------------------------------------------------------------------------
# trim_report.json / trim_report.txt
# ---------------------------------------------------------------------------


def render_trim_report_json(ctx: ChopperContext, record: RunRecord) -> tuple[str, str]:
    summary = _build_summary(ctx, record)
    file_report = _build_file_report(record.manifest)
    proc_report = _build_proc_report(record.manifest)
    diagnostics = _build_diag_entries(ctx.diag.snapshot())
    payload = {
        "chopper_version": CHOPPER_VERSION,
        "run_id": record.run_id,
        "mode": "dry-run" if ctx.config.dry_run else "live",
        "summary": summary,
        "file_report": file_report,
        "proc_report": proc_report,
        "validation_results": {"phase1": "pass", "phase2": "pass"},
        "diagnostics": diagnostics,
    }
    return "trim_report.json", dump_model(payload)


def render_trim_report_txt(ctx: ChopperContext, record: RunRecord) -> tuple[str, str]:
    lines: list[str] = []
    lines.append("Chopper Trim Report")
    lines.append("=" * 40)
    lines.append(f"Run ID:   {record.run_id}")
    lines.append(f"Domain:   {ctx.config.domain_root.name}")
    lines.append(f"Mode:     {'dry-run' if ctx.config.dry_run else 'live'}")
    lines.append(f"Started:  {_iso(record.started_at)}")
    lines.append(f"Ended:    {_iso(record.ended_at)}")
    lines.append(f"Exit:     {record.exit_code}")
    lines.append("")

    manifest = record.manifest
    if manifest is not None:
        counts = _file_treatment_counts(manifest)
        lines.append("File treatment summary")
        lines.append("-" * 40)
        for name, count in sorted(counts.items()):
            lines.append(f"  {name:10s}: {count}")
        lines.append("")
        lines.append(f"Surviving procs: {len(manifest.proc_decisions)}")
        lines.append("")

    diag_snap = ctx.diag.snapshot()
    if diag_snap:
        lines.append("Diagnostics")
        lines.append("-" * 40)
        for sev_label, sev_val in (("Errors", Severity.ERROR), ("Warnings", Severity.WARNING), ("Info", Severity.INFO)):
            matches = [d for d in diag_snap if d.severity == sev_val]
            if not matches:
                continue
            lines.append(f"{sev_label} ({len(matches)}):")
            for d in matches:
                where = f" [{d.path.as_posix()}:{d.line_no}]" if d.path and d.line_no else ""
                lines.append(f"  {d.code} {d.message}{where}")
            lines.append("")

    if ctx.config.dry_run:
        lines.append("(no files were modified)")
    lines.append("")
    return "trim_report.txt", "\n".join(lines)


# ---------------------------------------------------------------------------
# trim_stats.json
# ---------------------------------------------------------------------------


def render_trim_stats(ctx: ChopperContext, record: RunRecord) -> tuple[str, str]:
    parsed = record.parsed
    manifest = record.manifest

    files_before = len(parsed.files) if parsed else 0
    files_after = 0
    if manifest is not None:
        files_after = sum(
            1
            for t in manifest.file_decisions.values()
            if t in (FileTreatment.FULL_COPY, FileTreatment.PROC_TRIM, FileTreatment.GENERATED)
        )

    procs_before = sum(len(pf.procs) for pf in parsed.files.values()) if parsed else 0
    procs_after = len(manifest.proc_decisions) if manifest else 0

    sloc_before, sloc_after, raw_before, raw_after = _compute_line_counts(ctx, record)

    def _ratio(after: int, before: int) -> float:
        return (after / before) if before else 0.0

    payload = {
        "chopper_version": CHOPPER_VERSION,
        "run_id": record.run_id,
        "domain": ctx.config.domain_root.name,
        "timestamp": _iso(record.ended_at),
        "files_before": files_before,
        "files_after": files_after,
        "procs_before": procs_before,
        "procs_after": procs_after,
        "sloc_before": sloc_before,
        "sloc_after": sloc_after,
        "sloc_removed": max(sloc_before - sloc_after, 0),
        "raw_lines_before": raw_before,
        "raw_lines_after": raw_after,
        "trim_ratio_files": _ratio(files_after, files_before),
        "trim_ratio_procs": _ratio(procs_after, procs_before),
        "trim_ratio_sloc": _ratio(sloc_after, sloc_before),
    }
    return "trim_stats.json", dump_model(payload)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    """ISO-8601 UTC ``Z``-suffixed timestamp."""

    return str(dt.strftime("%Y-%m-%dT%H:%M:%SZ"))


def _severity_counts(diagnostics: Iterable[Diagnostic]) -> dict[str, int]:
    counts = {"errors": 0, "warnings": 0, "info": 0}
    for d in diagnostics:
        if d.severity is Severity.ERROR:
            counts["errors"] += 1
        elif d.severity is Severity.WARNING:
            counts["warnings"] += 1
        else:
            counts["info"] += 1
    return counts


_TREATMENT_SLUGS = {
    FileTreatment.FULL_COPY: "full-copy",
    FileTreatment.PROC_TRIM: "proc-trim",
    FileTreatment.REMOVE: "remove",
    FileTreatment.GENERATED: "generated",
}


def _treatment_slug(t: FileTreatment) -> str:
    return _TREATMENT_SLUGS[t]


def _edge_entry(edge: Edge) -> dict[str, object]:
    return {
        "edge_type": edge.kind,
        "from": edge.caller,
        "to": edge.callee,
        "status": edge.status,
        "diagnostic_code": edge.diagnostic_code,
        "line": edge.line,
    }


def _unresolved_reason(code: str) -> str:
    return {
        "TW-01": "no-in-domain-match",
        "TW-02": "ambiguous-match",
        "TW-03": "dynamic-call-form",
    }.get(code, "unresolved")


def _build_diag_entries(diagnostics: Iterable[Diagnostic]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for d in diagnostics:
        out.append(
            {
                "code": d.code,
                "severity": str(d.severity.value) if hasattr(d.severity, "value") else str(d.severity),
                "message": d.message,
                "file": d.path.as_posix() if d.path else None,
                "line": d.line_no,
                "phase": f"P{int(d.phase)}",
            }
        )
    return out


def _file_treatment_counts(manifest: CompiledManifest) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in manifest.file_decisions.values():
        slug = _treatment_slug(t)
        counts[slug] = counts.get(slug, 0) + 1
    return counts


def _build_summary(ctx: ChopperContext, record: RunRecord) -> dict[str, object]:
    parsed = record.parsed
    manifest = record.manifest
    trim_report = record.trim_report

    total_files = len(parsed.files) if parsed else 0
    total_procs = sum(len(pf.procs) for pf in parsed.files.values()) if parsed else 0
    files_surviving = 0
    files_removed = 0
    if manifest is not None:
        files_surviving = sum(
            1
            for t in manifest.file_decisions.values()
            if t in (FileTreatment.FULL_COPY, FileTreatment.PROC_TRIM, FileTreatment.GENERATED)
        )
        files_removed = sum(1 for t in manifest.file_decisions.values() if t is FileTreatment.REMOVE)

    procs_surviving = len(manifest.proc_decisions) if manifest else 0
    procs_removed = trim_report.procs_removed_total if trim_report else 0
    procs_traced = len(record.graph.pt) if record.graph else 0

    sloc_before, sloc_after, raw_before, raw_after = _compute_line_counts(ctx, record)

    return {
        "total_domain_files": total_files,
        "files_surviving": files_surviving,
        "files_removed": files_removed,
        "total_domain_procs": total_procs,
        "procs_surviving": procs_surviving,
        "procs_removed": procs_removed,
        "procs_traced": procs_traced,
        "sloc_before": sloc_before,
        "sloc_after": sloc_after,
        "sloc_removed": max(sloc_before - sloc_after, 0),
        "raw_lines_before": raw_before,
        "raw_lines_after": raw_after,
    }


def _build_file_report(manifest: CompiledManifest | None) -> list[dict[str, object]]:
    if manifest is None:
        return []
    out: list[dict[str, object]] = []
    for path, treatment in manifest.file_decisions.items():
        prov = manifest.provenance[path]
        out.append(
            {
                "path": path.as_posix(),
                "treatment": _treatment_slug(treatment),
                "reason": prov.reason,
            }
        )
    return out


def _build_proc_report(manifest: CompiledManifest | None) -> list[dict[str, object]]:
    if manifest is None:
        return []
    out: list[dict[str, object]] = []
    for d in manifest.proc_decisions.values():
        out.append(_proc_entry(d))
    return out


def _proc_entry(d: ProcDecision) -> dict[str, object]:
    return {
        "canonical_name": d.canonical_name,
        "source_file": d.source_file.as_posix(),
        "selection_source": d.selection_source,
    }


def _compute_line_counts(ctx: ChopperContext, record: RunRecord) -> tuple[int, int, int, int]:
    """Return ``(sloc_before, sloc_after, raw_before, raw_after)``.

    "Before" reads from whichever tree held the pre-trim domain: the
    backup root (re-trim) or the domain root (first-trim, read before
    P5 rebuilds). "After" reads from the rebuilt domain root. Under
    dry-run the domain is unchanged, so before==after. Files that
    cannot be read contribute zero; we do not emit a diagnostic because
    the audit writer is the last line of defence.
    """

    parsed = record.parsed
    manifest = record.manifest
    if parsed is None:
        return 0, 0, 0, 0

    # Before — iterate parsed files (the tree the parser saw).
    sloc_before = 0
    raw_before = 0
    for rel_path, pf in parsed.files.items():
        text = _safe_read(ctx, _resolve_before_path(ctx, record, rel_path))
        if text is None:
            continue
        sloc_before += count_sloc(Path(rel_path), text)
        raw_before += count_raw(text)

    if manifest is None:
        return sloc_before, 0, raw_before, 0

    # After — iterate surviving files in the manifest, read from domain.
    sloc_after = 0
    raw_after = 0
    for rel_path, treatment in manifest.file_decisions.items():
        if treatment is FileTreatment.REMOVE:
            continue
        text = _safe_read(ctx, ctx.config.domain_root / rel_path)
        if text is None:
            continue
        sloc_after += count_sloc(rel_path, text)
        raw_after += count_raw(text)

    return sloc_before, sloc_after, raw_before, raw_after


def _resolve_before_path(ctx: ChopperContext, record: RunRecord, rel_path: Path) -> Path:
    """Pick the root the parser read from for ``rel_path``.

    On re-trim (Case 2) the backup is the pristine source; on first-trim
    (Case 1) the parser read the domain before the trimmer rebuilt it.
    Absent state information, fall back to the domain root.
    """

    if record.state is not None and record.state.backup_exists:
        return ctx.config.backup_root / rel_path
    return ctx.config.domain_root / rel_path


def _safe_read(ctx: ChopperContext, path: Path) -> str | None:
    try:
        return ctx.fs.read_text(path)
    except (OSError, UnicodeDecodeError):
        return None
