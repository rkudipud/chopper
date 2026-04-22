"""AuditService — Phase 7 (P7) of the Chopper pipeline.

Writes the ``.chopper/`` bundle per bible §§5.5.1–5.5.11 and returns an
:class:`~chopper.core.models.AuditManifest` describing what was written.

The service always runs, even when earlier phases aborted (bible
§5.5.10); each writer tolerates ``None`` inputs on its
:class:`~chopper.core.models.RunRecord` and produces an artifact that
still parses as valid JSON.

Determinism
-----------
Every JSON artifact is serialised through
:func:`chopper.core.serialization.dump_model`, guaranteeing sorted keys,
2-space indent, UTF-8, and a trailing newline (bible §5.5.11). The
``sha256`` field on each :class:`AuditArtifact` hashes the exact bytes
written, so downstream reviewers can diff without re-running Chopper.
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
    render_run_id,
    render_trim_report_json,
    render_trim_report_txt,
    render_trim_stats,
)
from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Severity
from chopper.core.models import AuditArtifact, AuditManifest, RunRecord

__all__ = ["AuditService"]


@dataclass(frozen=True)
class AuditService:
    """P7 audit writer (bible §§5.5, 5.5.10)."""

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

        # Input preservation (bible §5.5.9): exact byte-for-byte copies.
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
            except OSError:
                # Bible §5.5.10: audit writes are best-effort. The runner's
                # outer try/except discards any exception here so the
                # primary failure is never masked.
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
        """Verbatim copies of base + feature JSONs (bible §5.5.9).

        Content is read through :attr:`ctx.fs.read_text` and written back
        byte-for-byte as part of the second pass. If the read fails, the
        input is silently skipped — audit is best-effort per §5.5.10.
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
            # Bible §5.5.1: "feature JSONs are prefixed with a two-digit
            # sequence number reflecting selected feature order".
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
