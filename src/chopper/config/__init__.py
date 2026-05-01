"""Config loading service — Phase 1 (P1) of the Chopper pipeline.

This package provides :class:`~chopper.config.service.ConfigService`, which
reads, validates, and hydrates the base / feature / project JSON files into
the typed :class:`~chopper.core.models_config.LoadedConfig` aggregate consumed by
the compiler and tracer.

Sub-modules (internal; import only :class:`ConfigService` from the service):

* :mod:`~chopper.config.schema` — jsonschema validators backed by the
  authoritative schemas in ``schemas/``.
* :mod:`~chopper.config.loaders` — per-schema hydration functions that
  translate raw dicts into frozen dataclasses.
* :mod:`~chopper.config.service` — :class:`ConfigService` orchestrator.
"""

from __future__ import annotations

from chopper.config.service import ConfigService

__all__ = ["ConfigService"]
