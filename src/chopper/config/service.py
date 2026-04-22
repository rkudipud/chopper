"""ConfigService — Phase 1 (P1) of the Chopper pipeline.

:class:`ConfigService` is the orchestrator-facing entry point for loading,
validating, and aggregating the base / feature / project JSONs into the
:class:`~chopper.core.models.LoadedConfig` consumed by :class:`ParserService`
and :class:`CompilerService`.

Responsibilities:

1. Determine input mode — project path (``ctx.config.project_path``) or
   explicit base / features (``ctx.config.base_path`` + ``ctx.config.feature_paths``).
2. Read each JSON file through ``ctx.fs.read_text`` (never
   :meth:`pathlib.Path.read_text` directly).
3. Parse JSON — emit ``VE-01`` / ``VE-02`` / ``VE-12`` on decode / schema
   failures via :func:`~chopper.config.schema.validate_json`.
4. Hydrate raw dicts into typed dataclasses via
   :mod:`chopper.config.loaders`.
5. Apply topo-sort on features (``VE-14``, ``VE-15``, ``VE-22``).
6. Build ``surface_files`` — the union of every domain-relative path
   contributed by any JSON source (lex-sorted POSIX form), ready for
   :class:`~chopper.parser.service.ParserService`.

What ConfigService does **not** do:

* It does not expand globs — that is the compiler's job (P3).
* It does not check whether files exist on disk — ``VE-06`` is the
  validator's job (``validate_pre``).
* It does not check domain-name consistency (``VE-17``) or duplicate
  feature entries (``VE-18``) — those are ``validate_pre``'s
  responsibility.

Exit behaviour: every error diagnostic emitted here carries phase
``P1_CONFIG``.  The orchestrator's phase gate (``_has_errors(ctx,
Phase.P1_CONFIG)``) decides whether to abort the pipeline after this
service returns.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models import (
    BaseJson,
    DomainState,
    FeatureJson,
    LoadedConfig,
)

from .loaders import load_base, load_feature, load_project, topo_sort_features
from .schema import validate_json

__all__ = ["ConfigService"]


@dataclass(frozen=True)
class ConfigService:
    """P1 config-loading service.

    Implements the service-catalog contract from ARCHITECTURE_PLAN.md §4:

        ``ConfigService.run(ctx, state) → LoadedConfig``

    ``state`` is accepted for API symmetry with the orchestrator runner
    (which always passes it) but is not currently read by this service —
    the config load is unconditional regardless of domain state (Case 1–4).
    Future callers that need state-conditional loading should call
    ``ConfigService`` after a DomainStateService pass and inspect ``state``
    themselves.
    """

    def run(self, ctx: ChopperContext, state: DomainState) -> LoadedConfig:
        """Load, validate, hydrate and aggregate all JSON sources.

        :param ctx: Run context providing ``ctx.fs`` for I/O and
            ``ctx.diag`` for diagnostic emission.  ``ctx.config`` carries
            the resolved JSON paths (``project_path`` / ``base_path`` /
            ``feature_paths``).
        :param state: Domain state classification from P0 (passed for
            API symmetry; not currently inspected).
        :returns: :class:`LoadedConfig` — may be **partially populated** if
            errors were emitted.  The orchestrator's phase gate decides
            whether to continue.
        """
        cfg = ctx.config
        project_json = None
        feature_paths: tuple[Path, ...]

        if cfg.project_path is not None:
            # Project-mode: load the project JSON first to get base + feature paths.
            project_raw = self._load_raw(ctx, cfg.project_path)
            if project_raw is None:
                return _empty_config()
            if not validate_json(project_raw, cfg.project_path, ctx.diag.emit):
                return _empty_config()
            project_json = load_project(project_raw, cfg.project_path)

            base_path = cfg.domain_root / project_json.base
            feature_paths = tuple(cfg.domain_root / fp for fp in project_json.features)
        else:
            # Direct-mode: base_path and feature_paths come straight from RunConfig.
            base_path = cfg.base_path  # type: ignore[assignment]
            if base_path is None:
                # No project_path and no base_path — caller error; emit a clear
                # message and return empty so the phase gate can abort.
                ctx.diag.emit(
                    Diagnostic.build(
                        "VE-02",
                        phase=Phase.P1_CONFIG,
                        message="No base JSON path provided (neither --project nor --base given)",
                        hint="Pass --project <project.json> or --base <base.json>",
                    )
                )
                return _empty_config()
            feature_paths = cfg.feature_paths

        # --- Load base ---
        base_json = self._load_and_hydrate_base(ctx, base_path)
        if base_json is None:
            return _empty_config()

        # --- Load features ---
        features: list[FeatureJson] = []
        for fp in feature_paths:
            feat = self._load_and_hydrate_feature(ctx, fp)
            if feat is not None:
                features.append(feat)

        # Topo-sort (emits VE-14, VE-15, VE-22 as needed).
        provenance = cfg.project_path or base_path
        sorted_features = topo_sort_features(features, provenance, ctx.diag.emit)

        # --- surface_files: union of literal file refs from all sources ---
        surface = _collect_surface_files(base_json, sorted_features)
        surface_sorted = tuple(sorted(surface, key=lambda p: p.as_posix()))

        return LoadedConfig(
            base=base_json,
            features=tuple(sorted_features),
            project=project_json,
            surface_files=surface_sorted,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_raw(ctx: ChopperContext, path: Path) -> dict[str, Any] | None:
        """Read + JSON-decode a file; emit VE-01 on failure."""
        try:
            text = ctx.fs.read_text(path, encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            ctx.diag.emit(
                Diagnostic.build(
                    "VE-01",
                    phase=Phase.P1_CONFIG,
                    message=f"Could not read {path}: {exc}",
                    path=path,
                    hint="Check the file path and permissions",
                )
            )
            return None

        try:
            result: dict[str, Any] = json.loads(text)
            return result
        except json.JSONDecodeError as exc:
            ctx.diag.emit(
                Diagnostic.build(
                    "VE-01",
                    phase=Phase.P1_CONFIG,
                    message=f"JSON parse error in {path}: {exc}",
                    path=path,
                    hint="Validate the JSON syntax; note that trailing commas are not allowed",
                )
            )
            return None

    def _load_and_hydrate_base(self, ctx: ChopperContext, path: Path) -> BaseJson | None:
        raw = self._load_raw(ctx, path)
        if raw is None:
            return None
        if not validate_json(raw, path, ctx.diag.emit):
            return None
        return load_base(raw, path, ctx.diag.emit)

    def _load_and_hydrate_feature(self, ctx: ChopperContext, path: Path) -> FeatureJson | None:
        raw = self._load_raw(ctx, path)
        if raw is None:
            return None
        if not validate_json(raw, path, ctx.diag.emit):
            return None
        return load_feature(raw, path, ctx.diag.emit)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_config() -> LoadedConfig:
    """Sentinel returned when config loading cannot proceed.

    A stub :class:`BaseJson` is required by :class:`LoadedConfig` (non-optional).
    The orchestrator's phase gate will abort before this value is used for
    anything meaningful.
    """
    from chopper.core.models import BaseJson as _BaseJson  # local to avoid circular

    return LoadedConfig(
        base=_BaseJson(source_path=Path("<error>"), domain="<error>"),
    )


def _collect_surface_files(base: BaseJson, features: list[FeatureJson]) -> set[Path]:
    """Union of every *literal* file path named across all JSON sources.

    Glob patterns (strings containing ``*`` or ``?``) are intentionally
    excluded here — glob expansion against the real filesystem is the
    compiler's responsibility (P3).  This function collects only the
    concrete ``file`` entries from ``procedures.include`` /
    ``procedures.exclude`` and the literal (non-glob) entries from
    ``files.include`` / ``files.exclude``.
    """
    paths: set[Path] = set()

    def _add_literal(s: str) -> None:
        if "*" not in s and "?" not in s and "{" not in s:
            paths.add(Path(s))

    def _harvest(obj: BaseJson | FeatureJson) -> None:
        for pattern in obj.files.include:
            _add_literal(pattern)
        for pattern in obj.files.exclude:
            _add_literal(pattern)
        for ref in obj.procedures.include:
            paths.add(ref.file)
        for ref in obj.procedures.exclude:
            paths.add(ref.file)

    _harvest(base)
    for feat in features:
        _harvest(feat)

    return paths
