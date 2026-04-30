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

* It does not perform R1 conflict resolution between sources — that is
  the compiler's job (P3). P1 *does* expand ``files.include`` glob
  patterns against the on-disk domain so the P2 parser can find files
  reachable only via a glob; ``files.exclude`` globs are still resolved
  in P3 against the parsed universe.
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
import re
from collections import deque
from dataclasses import dataclass
from fnmatch import fnmatchcase
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

    Canonical signature::

        ConfigService.run(ctx, state) → LoadedConfig

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
        surface = _collect_surface_files(base_json, sorted_features, ctx)
        surface_sorted = tuple(sorted(surface, key=lambda p: p.as_posix()))

        # --- tool_command_pool: built-in lists + any --tool-commands paths ---
        # See architecture doc §3.10 and FR-44. The pool is a flat
        # frozenset of bare external-tool-command names that P4 trace
        # consults before emitting TW-02. Built-in lists under
        # ``src/chopper/data/tool_commands/`` are always loaded; user
        # paths from ``RunConfig.tool_command_paths`` extend the set.
        from chopper.compiler.tool_commands import load_pool as _load_pool

        pool = _load_pool(ctx.config.tool_command_paths)

        return LoadedConfig(
            base=base_json,
            features=tuple(sorted_features),
            project=project_json,
            surface_files=surface_sorted,
            tool_command_pool=pool,
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


def _is_glob_pattern(s: str) -> bool:
    """Return True if ``s`` contains glob metacharacters."""
    return any(ch in s for ch in ("*", "?", "["))


def _glob_to_regex_local(pattern: str) -> re.Pattern[str] | None:
    """Translate a POSIX-style glob with ``**`` semantics into a compiled regex.

    Mirrors the logic in :func:`chopper.compiler.merge_service._glob_to_regex`
    so that P1 surface-file collection and P3 conflict resolution use identical
    glob semantics.  Returns ``None`` for patterns that contain no ``**`` so
    the caller can fall back to :func:`fnmatch.fnmatchcase`.
    """
    if "**" not in pattern:
        return None
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                if i + 2 < n and pattern[i + 2] == "/":
                    out.append("(?:.*/)?")
                    i += 3
                else:
                    out.append(".*")
                    i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        elif ch == "[":
            j = i + 1
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                out.append(re.escape("["))
                i += 1
            else:
                cls = pattern[i + 1 : j]
                if cls.startswith("!"):
                    cls = "^" + cls[1:]
                out.append("[" + cls + "]")
                i = j + 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("".join(out))


def _enumerate_domain_files(ctx: ChopperContext) -> list[tuple[Path, str]]:
    """Walk the domain filesystem once and return all regular files as
    ``(domain_relative_path, posix_string)`` pairs.

    The ``.chopper/`` audit directory is always excluded.  Returns an empty
    list if the domain root does not exist (e.g. unit-test in-memory FS).
    """
    domain = ctx.config.domain_root
    if not ctx.fs.exists(domain):
        return []

    results: list[tuple[Path, str]] = []
    frontier: deque[Path] = deque([domain])
    while frontier:
        current = frontier.popleft()
        try:
            children = ctx.fs.list(current)
        except OSError:
            continue
        for child in children:
            try:
                rel = child.relative_to(domain)
            except ValueError:
                continue
            rel_posix = rel.as_posix()
            if rel_posix == ".chopper" or rel_posix.startswith(".chopper/"):
                continue
            try:
                st = ctx.fs.stat(child)
            except OSError:
                continue
            if st.is_dir:
                frontier.append(child)
            else:
                results.append((rel, rel_posix))
    return results


def _match_glob_against(pattern: str, domain_files: list[tuple[Path, str]]) -> set[Path]:
    """Filter pre-enumerated domain files by a single glob pattern."""
    regex = _glob_to_regex_local(pattern)
    matches: set[Path] = set()
    if regex is not None:
        for rel, rel_posix in domain_files:
            if regex.fullmatch(rel_posix):
                matches.add(rel)
    else:
        for rel, rel_posix in domain_files:
            if fnmatchcase(rel_posix, pattern):
                matches.add(rel)
    return matches


def _collect_surface_files(base: BaseJson, features: list[FeatureJson], ctx: ChopperContext) -> set[Path]:
    """Union of every file path contributed by all JSON sources.

    Literal paths (no glob metacharacters) are added directly.  Glob
    patterns in ``files.include`` are expanded against the real domain
    filesystem so that files reachable only via a glob — never named
    literally — are included in the P2 parse universe.  Glob patterns in
    ``files.exclude`` are intentionally not expanded here (the compiler
    applies them against ``parsed_paths`` in P3).

    ``procedures.include`` / ``procedures.exclude`` always use exact file
    paths, so those are added directly.

    Performance: the domain filesystem is walked at most once, regardless
    of how many sources or glob patterns are present.  The walk is skipped
    entirely when no source has a glob pattern in ``files.include``.
    """
    paths: set[Path] = set()

    def _add_literal(s: str) -> None:
        if not _is_glob_pattern(s):
            paths.add(Path(s))

    sources: tuple[BaseJson | FeatureJson, ...] = (base, *features)
    has_fi_glob = any(_is_glob_pattern(p) for s in sources for p in s.files.include)
    domain_files: list[tuple[Path, str]] = _enumerate_domain_files(ctx) if has_fi_glob else []

    for src in sources:
        for pattern in src.files.include:
            if _is_glob_pattern(pattern):
                paths.update(_match_glob_against(pattern, domain_files))
            else:
                paths.add(Path(pattern))
        for pattern in src.files.exclude:
            _add_literal(pattern)
        for ref in src.procedures.include:
            paths.add(ref.file)
        for ref in src.procedures.exclude:
            paths.add(ref.file)

    return paths
