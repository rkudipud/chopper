"""P7 audit writer — fills the ``.chopper/`` bundle.

Returns an :class:`AuditManifest` describing every artifact written.
Runs unconditionally; writers tolerate ``None`` inputs from aborted
earlier phases and still emit valid JSON.

All JSON output goes through :func:`chopper.core.serialization.dump_model`
(sorted keys, 2-space indent, UTF-8, trailing newline). Each artifact is
hashed with SHA-256 for tamper-evident diffing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chopper.audit.hashing import sha256_hex
from chopper.audit.writers import (
    render_chopper_run,
    render_compiled_manifest,
    render_dependency_graph,
    render_diagnostics,
    render_files_kept,
    render_files_removed,
    render_run_id,
    render_trim_report_json,
    render_trim_report_txt,
    render_trim_stats,
)
from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase, Severity
from chopper.core.models_audit import AuditArtifact, AuditManifest, RunRecord

__all__ = ["AuditService"]


@dataclass(frozen=True)
class AuditService:
    """P7 audit writer."""

    def run(self, ctx: ChopperContext, record: RunRecord) -> AuditManifest:
        """Write the audit bundle and return its inventory."""

        audit_root = ctx.config.audit_root
        artifacts: list[AuditArtifact] = []

        # First pass — render every artifact that does not depend on the
        # final ``artifacts_present`` listing. ``chopper_run.json`` needs
        # that listing, so it is rendered last.
        renderings: list[tuple[str, str]] = []
        renderings.append(render_run_id(record))
        renderings.append(render_compiled_manifest(record))
        renderings.append(render_dependency_graph(record))
        renderings.append(render_diagnostics(ctx, record))
        renderings.append(render_trim_report_json(ctx, record))
        renderings.append(render_trim_report_txt(ctx, record))
        renderings.append(render_trim_stats(ctx, record))
        renderings.append(render_files_removed(ctx, record))
        renderings.append(render_files_kept(record))

        # Preserve input files as exact byte-for-byte copies.
        input_copies = self._copy_inputs(ctx, record)
        renderings.extend(input_copies)

        # Now we know every artifact name; render chopper_run.json with
        # the full ``artifacts_present`` listing (including itself).
        present_names = tuple(sorted([name for name, _ in renderings] + ["chopper_run.json"]))
        renderings.append(render_chopper_run(ctx, record, present_names))

        # Second pass — write every rendering to disk.
        for name, content in renderings:
            target = self._target_path(audit_root, name)
            try:
                ctx.fs.mkdir(target.parent, parents=True, exist_ok=True)
                ctx.fs.write_text(target, content)
            except OSError as exc:
                # Audit writes are best-effort, but we no longer
                # swallow silently. Emit VW-20 so the user sees that
                # an artifact failed to land — partial bundles must
                # never be invisible (architecture doc NFR-13).
                ctx.diag.emit(
                    Diagnostic.build(
                        "VW-20",
                        phase=Phase.P7_AUDIT,
                        message=(f"Failed to write audit artifact {name!r}: {type(exc).__name__}: {exc}"),
                        path=target,
                        context={"artifact": name},
                    )
                )
                continue
            data = content.encode("utf-8")
            artifacts.append(
                AuditArtifact(
                    name=name,
                    path=target,
                    size=len(data),
                    sha256=sha256_hex(content),
                )
            )

        artifacts.sort(key=lambda a: a.name)
        counts = self._severity_counts(ctx)
        return AuditManifest(
            run_id=record.run_id,
            started_at=record.started_at,
            ended_at=record.ended_at,
            exit_code=record.exit_code,
            artifacts=tuple(artifacts),
            diagnostic_counts=counts,
        )

    # ---- internals ---------------------------------------------------

    def _target_path(self, audit_root: Path, name: str) -> Path:
        """Resolve ``name`` (possibly nested, e.g. ``input_features/01_x.json``)
        under ``audit_root``."""

        return audit_root / name

    def _copy_inputs(self, ctx: ChopperContext, record: RunRecord) -> list[tuple[str, str]]:
        """Verbatim copies of base + feature JSONs.

        Content is read through :attr:`ctx.fs.read_text` and written back
        byte-for-byte as part of the second pass. If the read fails, the
        input is silently skipped.
        """

        out: list[tuple[str, str]] = []
        loaded = record.loaded
        if loaded is None:
            return out

        base_text = self._safe_read(ctx, loaded.base.source_path)
        if base_text is not None:
            out.append(("input_base.json", base_text))

        for index, feature in enumerate(loaded.features, start=1):
            text = self._safe_read(ctx, feature.source_path)
            if text is None:
                continue
            # Prefix feature JSONs with a two-digit sequence number that
            # reflects selected feature order.
            filename = f"{index:02d}_{feature.source_path.name}"
            out.append((f"input_features/{filename}", text))

        return out

    def _safe_read(self, ctx: ChopperContext, path: Path) -> str | None:
        try:
            return ctx.fs.read_text(path)
        except (OSError, UnicodeDecodeError):
            return None

    def _severity_counts(self, ctx: ChopperContext) -> dict[str, int]:
        counts = {"error": 0, "warning": 0, "info": 0}
        for d in ctx.diag.snapshot():
            if d.severity is Severity.ERROR:
                counts["error"] += 1
            elif d.severity is Severity.WARNING:
                counts["warning"] += 1
            else:
                counts["info"] += 1
        return counts
