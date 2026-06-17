"""Feature name resolution from ``<domain>/jsons/features/*.feature.json``.

Resolves the ``--features`` CLI argument from a CSV of feature names
(e.g. ``dft,power``) to ordered feature JSON file paths.

Tokens containing ``/`` or ending with ``.json`` pass through unchanged
as direct file-path references (backward compatibility for scripts that
already pass explicit paths).

See ``technical_docs/ARCHITECTURE.md`` §5.1 (``--features`` as names).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

__all__ = ["resolve_feature_names", "FeatureLookupResult"]


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

    # Build the name → path map lazily (only when a name-mode token is found)
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
