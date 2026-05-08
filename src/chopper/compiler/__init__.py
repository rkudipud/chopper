"""Compiler package — Phase 3 (P3) + Phase 4 (P4).

Public surface:

* :class:`CompilerService` — consumes :class:`LoadedConfig` +
  :class:`ParseResult` and returns a frozen :class:`CompiledManifest`.
* :class:`TracerService` — consumes the manifest + parse index and
  returns a frozen :class:`DependencyGraph`.

See :mod:`chopper.compiler.merge_service` for the R1 ordered-overlay
fold algorithm.
"""

from __future__ import annotations

from chopper.compiler.merge_service import CompilerService
from chopper.compiler.trace_service import TracerService

__all__ = ["CompilerService", "TracerService"]
