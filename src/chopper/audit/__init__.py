"""Audit package — Phase 7 (P7) of the Chopper pipeline.

Writes the ``.chopper/`` bundle described in bible §5.5. The service
always runs — even when earlier phases failed, even when the pipeline
aborted on a gated error — so that every run leaves a forensic record
on disk.

Public surface:

* :class:`AuditService` — the P7 service; orchestrates every artifact
  writer and returns an :class:`~chopper.core.models.AuditManifest`.

All per-artifact writers are module-private helpers in
:mod:`chopper.audit.writers`; they are exposed only through the service
so the one bible-defined artifact vocabulary stays in one place.
"""

from __future__ import annotations

from chopper.audit.service import AuditService

__all__ = ["AuditService"]
