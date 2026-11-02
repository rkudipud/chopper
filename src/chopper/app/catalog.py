"""JSON catalog discovery for a domain.

* :func:`find_base` -- base JSON auto-discovery (``VE-35`` when absent).
* :func:`find_project_config` -- ``$ward/project/`` project-config
  auto-discovery (``technical_docs/ARCHITECTURE.md`` Section 5.1.3).
* :func:`resolve_feature_names` -- ``--features`` CSV of names or paths to
  ordered ``<domain>/jsons/features/*.feature.json`` paths. Tokens
  containing ``/`` or ending with ``.json`` pass through unchanged.
* :func:`expand_feature_dirs` -- validate/loc directory expansion.
* :func:`selected_feature_paths` -- the feature list a run config selects.

See ``technical_docs/ARCHITECTURE.md`` Section 5.1 (``--features`` as names).
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path

from chopper.core.context import RunConfig

__all__ = [
    "FeatureLookupResult",
    "base_candidates",
    "expand_feature_dirs",
    "find_base",
    "find_project_config",
    "resolve_feature_names",
    "selected_feature_paths",
]


def base_candidates(domain_root: Path, domain_logical_name: str | None) -> tuple[Path, Path]:
    """The two base JSON locations auto-discovery tries, in order.

    ``<domain_root>/jsons/base.json`` then
    ``<domain_root>/jsons/<domain_leaf_name>.json``.
    """
    leaf = (domain_root.name if domain_logical_name is None else domain_logical_name).split("/")[-1]
    return domain_root / "jsons" / "base.json", domain_root / "jsons" / f"{leaf}.json"


def find_base(domain_root: Path, domain_logical_name: str | None) -> Path | None:
    """Return the first existing :func:`base_candidates` entry, or ``None``."""
    return next((p for p in base_candidates(domain_root, domain_logical_name) if p.is_file()), None)


def find_project_config(
    ward_root: Path,
    domain_logical_name: str,
) -> tuple[str | None, str | None, Path | None]:
    """Search ``$ward/project/<domain_logical_name>/`` for a project-level config.

    Returns ``(explicit_project, explicit_features, project_config_path)``.
    Search order per ``technical_docs/ARCHITECTURE.md`` Section 5.1.3:

    1. ``<leaf>.project.json``            -> ``(str(path), None, None)``
    2. ``<leaf>.project.features.config`` -> ``(None, "name1,name2", resolved_path)``

    All three are ``None`` when neither file is found or the config is empty.
    """
    leaf = domain_logical_name.split("/")[-1]
    project_dir = ward_root / "project" / domain_logical_name
    probe_json = project_dir / f"{leaf}.project.json"
    probe_cfg = project_dir / f"{leaf}.project.features.config"
    if probe_json.is_file():
        return str(probe_json), None, None
    if probe_cfg.is_file():
        names = [
            ln.strip() for ln in probe_cfg.read_text().splitlines() if ln.strip() and not ln.strip().startswith("#")
        ]
        if names:
            return None, ",".join(names), probe_cfg.resolve()
    return None, None, None


def expand_feature_dirs(features: str | None) -> str | None:
    """Expand directory entries in a ``--features`` comma-separated list.

    Authoring convenience for ``validate`` and ``loc`` per
    ``technical_docs/ARCHITECTURE.md`` Sec.5.1: any entry that resolves
    to a directory is replaced in place by the sorted (lexicographic),
    non-recursive list of its immediate ``*.json`` children. File entries
    pass through unchanged. Empty segments are preserved so the
    downstream empty-segment stripping keeps its behavior. ``chopper
    trim`` and ``--project`` require explicit per-file paths.
    """
    if not features:
        return features
    expanded: list[str] = []
    for raw in features.split(","):
        segment = raw.strip()
        if not segment:
            expanded.append(raw)
            continue
        candidate = Path(segment)
        if candidate.is_dir():
            children = sorted(candidate.glob("*.json"))
            expanded.extend(child.as_posix() for child in children)
        else:
            expanded.append(segment)
    return ",".join(expanded)


def selected_feature_paths(cfg: RunConfig) -> list[Path]:
    """Feature JSONs a run config selects, in order.

    The explicit feature list, or -- in ``--project`` mode -- the project
    JSON's ``features`` entries resolved under the domain root. An
    unreadable or malformed project JSON yields an empty list; the
    pipeline reports the real error.
    """
    feature_paths: list[Path] = list(cfg.feature_paths)
    if not feature_paths and cfg.project_path is not None:
        try:
            proj = json.loads(cfg.project_path.read_text())
            for raw in proj.get("features") or []:
                feature_paths.append(cfg.domain_root / raw)
        except Exception:
            pass
    return feature_paths


@dataclass(frozen=True)
class FeatureLookupResult:
    """Outcome of resolving a --features CSV."""

    resolved_paths: tuple[Path, ...]
    """Feature JSON paths in the order the names were supplied."""

    unresolved_names: tuple[str, ...]
    """Names that could not be resolved to a file."""

    suggestions: dict[str, tuple[str, ...]]
    """Maps each unresolved name to close matches from available features."""


def resolve_feature_names(
    features_csv: str,
    domain_root: Path,
) -> FeatureLookupResult:
    """Resolve a comma-separated list of feature names/paths.

    Args:
        features_csv: Raw ``--features`` value, e.g. ``"dft,power,scan_opt"``.
        domain_root: Resolved domain root used to locate
            ``jsons/features/*.feature.json``.

    Returns:
        A :class:`FeatureLookupResult` with resolved paths, any unresolved
        names, and close-match suggestions for each unresolved name.
    """
    tokens = [t.strip() for t in features_csv.split(",") if t.strip()]

    # Build the name -> path map lazily (only when a name-mode token is found)
    _name_map: dict[str, Path] | None = None

    def _get_name_map() -> dict[str, Path]:
        nonlocal _name_map
        if _name_map is None:
            features_dir = domain_root / "jsons" / "features"
            _name_map = {}
            if features_dir.is_dir():
                for p in sorted(features_dir.glob("*.feature.json")):
                    # stem of "dft.feature.json" is "dft.feature"
                    # removesuffix(".feature") gives "dft"
                    name = p.stem.removesuffix(".feature")
                    _name_map[name] = p
        return _name_map

    resolved: list[Path] = []
    unresolved: list[str] = []
    suggestions: dict[str, list[str]] = {}

    for token in tokens:
        # Passthrough: explicit path reference (contains slash or ends with .json)
        if "/" in token or "\\" in token or token.endswith(".json"):
            resolved.append(Path(token))
            continue
        # Name-mode lookup
        name_map = _get_name_map()
        if token in name_map:
            resolved.append(name_map[token])
        else:
            unresolved.append(token)
            close = difflib.get_close_matches(token, list(name_map.keys()), n=3, cutoff=0.5)
            suggestions[token] = close

    return FeatureLookupResult(
        resolved_paths=tuple(resolved),
        unresolved_names=tuple(unresolved),
        suggestions={k: tuple(v) for k, v in suggestions.items()},
    )
