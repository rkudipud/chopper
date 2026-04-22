"""Compiler package — Phase 3 (P3) of the Chopper pipeline.

Public surface:

* :class:`CompilerService` — orchestrator-facing entry point that
  consumes a :class:`~chopper.core.models.LoadedConfig` and a
  :class:`~chopper.core.models.ParseResult` and returns a frozen
  :class:`~chopper.core.models.CompiledManifest`.

See :mod:`chopper.compiler.merge_service` for the two-pass R1 merge
algorithm (bible §§4, 5.3).
"""

from __future__ import annotations

from chopper.compiler.merge_service import CompilerService
from chopper.compiler.trace_service import TracerService

__all__ = ["CompilerService", "TracerService"]
