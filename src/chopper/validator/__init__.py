"""Validator package — pre-trim (P1b) and post-trim (P6) checks.

Implemented as two module-level functions (no service class). Each
reads typed inputs and emits diagnostics through ``ctx.diag``.

* :func:`validate_pre` — runs after :class:`ConfigService`, before
  :class:`ParserService`. Consumes :class:`LoadedConfig`.
* :func:`validate_post` — runs after trim + generation. Consumes
  :class:`CompiledManifest`, :class:`DependencyGraph`, and the tuple of
  rewritten paths.
"""

from __future__ import annotations

from chopper.validator.functions import validate_post, validate_pre

__all__ = ["validate_post", "validate_pre"]
