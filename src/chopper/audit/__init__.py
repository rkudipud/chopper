"""Audit package — Phase 7 (P7).

Writes the ``.chopper/`` forensic bundle. Always runs, even when earlier
phases aborted, so every invocation leaves a record on disk.

Public surface: :class:`AuditService`. Per-artifact writers live in
:mod:`chopper.audit.writers` and are exposed only through the service.
"""

from __future__ import annotations

from chopper.audit.service import AuditService

__all__ = ["AuditService"]
