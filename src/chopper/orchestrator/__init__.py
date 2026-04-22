"""Pipeline orchestration services.

This package owns the per-phase drivers that coordinate Chopper's
services. Stage 3a introduces
:class:`~chopper.orchestrator.domain_state.DomainStateService` — the
Phase 0 classifier that observes ``<domain>/`` and ``<domain>_backup/``
and routes downstream phases per the four-case matrix in bible §2.8.

Later stages extend this package with a full ``PipelineRunner`` that
sequences P0 → P7 and applies the severity / exit-code policy from
bible §8.2.
"""

from __future__ import annotations

from chopper.orchestrator.domain_state import DomainStateService

__all__ = ["DomainStateService"]
