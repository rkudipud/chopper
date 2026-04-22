"""Validator package — pre- and post-trim diagnostic emission.

Per ARCHITECTURE_PLAN.md §9.2, validation is implemented as two
module-level functions rather than a service class; they read typed
inputs and emit diagnostics through ``ctx.diag`` without returning
typed results.

Public API:

* :func:`validate_pre` — P1b, runs after :class:`ConfigService` and
  before :class:`ParserService`. Consumes :class:`LoadedConfig`.
* :func:`validate_post` — P6, runs after trim + generation. Consumes
  :class:`CompiledManifest`, :class:`DependencyGraph`, and the tuple of
  rewritten paths.
"""

from __future__ import annotations

from chopper.validator.functions import validate_post, validate_pre

__all__ = ["validate_post", "validate_pre"]
