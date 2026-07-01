"""Unit tests for feature_lookup.resolve_feature_names."""

from __future__ import annotations

from pathlib import Path

from chopper.cli.feature_lookup import resolve_feature_names


def _make_domain(tmp_path: Path, feature_names: list[str]) -> Path:
    """Create <domain>/jsons/features/<name>.feature.json stubs."""
    features_dir = tmp_path / "jsons" / "features"
    features_dir.mkdir(parents=True)
    for name in feature_names:
        (features_dir / f"{name}.feature.json").write_text("{}")
    return tmp_path


class TestResolveFeatureNames:
    def test_single_name_resolved(self, tmp_path: Path) -> None:
        domain = _make_domain(tmp_path, ["dft", "power"])
        result = resolve_feature_names("dft", domain)
        assert result.unresolved_names == ()
        assert len(result.resolved_paths) == 1
        assert result.resolved_paths[0].name == "dft.feature.json"

    def test_multiple_names_order_preserved(self, tmp_path: Path) -> None:
        domain = _make_domain(tmp_path, ["dft", "power", "scan_opt"])
        result = resolve_feature_names("power,dft,scan_opt", domain)
        assert result.unresolved_names == ()
        names = [p.stem.removesuffix(".feature") for p in result.resolved_paths]
        assert names == ["power", "dft", "scan_opt"]

    def test_unresolved_name_returned(self, tmp_path: Path) -> None:
        domain = _make_domain(tmp_path, ["dft"])
        result = resolve_feature_names("nonexistent", domain)
        assert "nonexistent" in result.unresolved_names

    def test_close_match_suggested(self, tmp_path: Path) -> None:
        domain = _make_domain(tmp_path, ["power"])
        result = resolve_feature_names("powre", domain)  # typo
        assert "powre" in result.unresolved_names
        assert "power" in result.suggestions.get("powre", ())

    def test_no_suggestions_when_nothing_close(self, tmp_path: Path) -> None:
        domain = _make_domain(tmp_path, ["dft"])
        result = resolve_feature_names("zzz_xyz_abc", domain)
        assert result.suggestions.get("zzz_xyz_abc", ()) == ()

    def test_passthrough_json_suffix(self, tmp_path: Path) -> None:
        """Token ending in .json passes through as a direct path."""
        domain = _make_domain(tmp_path, [])
        result = resolve_feature_names("jsons/features/dft.feature.json", domain)
        assert result.unresolved_names == ()
        assert result.resolved_paths[0] == Path("jsons/features/dft.feature.json")

    def test_passthrough_slash_path(self, tmp_path: Path) -> None:
        """Token with / passes through as a direct path."""
        domain = _make_domain(tmp_path, [])
        result = resolve_feature_names("some/path", domain)
        assert result.unresolved_names == ()
        assert result.resolved_paths[0] == Path("some/path")

    def test_mixed_names_and_paths(self, tmp_path: Path) -> None:
        """Mix of name tokens and path tokens."""
        domain = _make_domain(tmp_path, ["dft"])
        result = resolve_feature_names("dft,jsons/features/power.feature.json", domain)
        assert result.unresolved_names == ()
        assert len(result.resolved_paths) == 2
        assert result.resolved_paths[0].name == "dft.feature.json"
        assert result.resolved_paths[1] == Path("jsons/features/power.feature.json")

    def test_empty_features_dir(self, tmp_path: Path) -> None:
        """No .feature.json files → name not found."""
        domain = tmp_path
        (domain / "jsons" / "features").mkdir(parents=True)
        result = resolve_feature_names("dft", domain)
        assert "dft" in result.unresolved_names

    def test_no_features_dir(self, tmp_path: Path) -> None:
        """Missing jsons/features dir → name not found."""
        result = resolve_feature_names("dft", tmp_path)
        assert "dft" in result.unresolved_names

    def test_whitespace_stripped(self, tmp_path: Path) -> None:
        """Whitespace around tokens is stripped."""
        domain = _make_domain(tmp_path, ["dft", "power"])
        result = resolve_feature_names("  dft , power  ", domain)
        assert result.unresolved_names == ()
        assert len(result.resolved_paths) == 2

    def test_partial_resolution(self, tmp_path: Path) -> None:
        """Some names resolve, some don't; both returned correctly."""
        domain = _make_domain(tmp_path, ["dft"])
        result = resolve_feature_names("dft,missing_feature", domain)
        assert len(result.resolved_paths) == 1
        assert result.resolved_paths[0].name == "dft.feature.json"
        assert "missing_feature" in result.unresolved_names
