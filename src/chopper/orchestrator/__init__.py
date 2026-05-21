"""Pipeline orchestration.

Owns the per-phase drivers that sequence P0 → P7. Exports:

* :class:`DomainStateService` — P0 classifier that observes
  ``<domain>/`` and ``<domain>_backup/`` and routes downstream phases.
* :class:`ChopperRunner` — sequences every phase and applies the
  severity-to-exit-code policy.
* :func:`has_errors` — gate helper shared by runner and CLI.
"""

from __future__ import annotations

from chopper.orchestrator.domain_state import DomainStateService
from chopper.orchestrator.gates import has_errors
from chopper.orchestrator.runner import ChopperRunner

__all__ = ["ChopperRunner", "DomainStateService", "has_errors"]
