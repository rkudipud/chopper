"""Unit tests for domain_lookup.resolve_domain.

Per architecture doc Sec.5.1.0 (Domain-name resolution).
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest

from chopper.cli.domain_lookup import resolve_domain


class _Error(NamedTuple):
    code: str
    message: str
    hint: str


def _collect_errors() -> tuple[list[_Error], object]:
    errors: list[_Error] = []

    def emit(code: str, message: str, hint: str) -> None:
        errors.append(_Error(code, message, hint))

    return errors, emit


class TestPathMode:
    def test_absolute_path_returns_path_mode(self, tmp_path: Path) -> None:
        errors, emit = _collect_errors()
        result = resolve_domain(tmp_path.as_posix(), emit)  # type: ignore[arg-type]
        assert result is not None
        assert result.domain_root == tmp_path.resolve()
        assert result.ward_root is None
        assert result.domain_logical_name is None
        assert errors == []

    def test_existing_relative_dir_returns_path_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        domain_dir = tmp_path / "my_domain"
        domain_dir.mkdir()
        errors, emit = _collect_errors()
        result = resolve_domain("my_domain", emit)  # type: ignore[arg-type]
        assert result is not None
        assert result.domain_root == domain_dir.resolve()
        assert result.ward_root is None
        assert result.domain_logical_name is None
        assert errors == []

    def test_absolute_path_no_ward_needed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Absolute path bypasses ward entirely even when ward is unset."""
        monkeypatch.delenv("ward", raising=False)
        errors, emit = _collect_errors()
        result = resolve_domain(tmp_path.as_posix(), emit)  # type: ignore[arg-type]
        assert result is not None
        assert result.ward_root is None
        assert errors == []


class TestNameModeBareName:
    def _make_ward(self, tmp_path: Path, domains: list[tuple[str, str]]) -> Path:
        """Create $ward/global/<vendor>/<domain> structure."""
        ward = tmp_path / "ward"
        global_dir = ward / "global"
        for vendor, domain in domains:
            (global_dir / vendor / domain).mkdir(parents=True)
        return ward

    def test_bare_name_single_match(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ward = self._make_ward(tmp_path, [("snps", "fev_formality")])
        monkeypatch.setenv("ward", ward.as_posix())
        errors, emit = _collect_errors()
        result = resolve_domain("fev_formality", emit)  # type: ignore[arg-type]
        assert result is not None
        assert result.domain_root == (ward / "global" / "snps" / "fev_formality").resolve()
        assert result.ward_root == ward.resolve()
        assert result.domain_logical_name == "snps/fev_formality"
        assert errors == []

    def test_bare_name_no_match_emits_ve33(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ward = self._make_ward(tmp_path, [("snps", "other_domain")])
        monkeypatch.setenv("ward", ward.as_posix())
        errors, emit = _collect_errors()
        result = resolve_domain("fev_formality", emit)  # type: ignore[arg-type]
        assert result is None
        assert len(errors) == 1
        assert errors[0].code == "VE-33"
        assert "fev_formality" in errors[0].message

    def test_bare_name_ambiguous_emits_ve34(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ward = self._make_ward(tmp_path, [("snps", "fev_formality"), ("cdns", "fev_formality")])
        monkeypatch.setenv("ward", ward.as_posix())
        errors, emit = _collect_errors()
        result = resolve_domain("fev_formality", emit)  # type: ignore[arg-type]
        assert result is None
        assert len(errors) == 1
        assert errors[0].code == "VE-34"
        assert "fev_formality" in errors[0].message

    def test_ward_not_set_emits_ve32(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ward", raising=False)
        errors, emit = _collect_errors()
        result = resolve_domain("fev_formality", emit)  # type: ignore[arg-type]
        assert result is None
        assert len(errors) == 1
        assert errors[0].code == "VE-32"
        assert "ward" in errors[0].message

    def test_global_dir_missing_emits_ve33(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ward = tmp_path / "ward"
        ward.mkdir()
        # No global/ subdir
        monkeypatch.setenv("ward", ward.as_posix())
        errors, emit = _collect_errors()
        result = resolve_domain("fev_formality", emit)  # type: ignore[arg-type]
        assert result is None
        assert len(errors) == 1
        assert errors[0].code == "VE-33"

    def test_bare_name_multiple_vendors_finds_correct(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiple vendor dirs, only one has the domain -> single match."""
        ward = self._make_ward(tmp_path, [("snps", "fev_formality"), ("cdns", "different_domain")])
        monkeypatch.setenv("ward", ward.as_posix())
        errors, emit = _collect_errors()
        result = resolve_domain("fev_formality", emit)  # type: ignore[arg-type]
        assert result is not None
        assert result.domain_logical_name == "snps/fev_formality"
        assert errors == []

    def test_ward_empty_string_emits_ve32(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty string ward is treated same as unset."""
        monkeypatch.setenv("ward", "")
        errors, emit = _collect_errors()
        result = resolve_domain("fev_formality", emit)  # type: ignore[arg-type]
        assert result is None
        assert len(errors) == 1
        assert errors[0].code == "VE-32"


class TestNameModeVendorQualified:
    def test_vendor_qualified_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ward = tmp_path / "ward"
        (ward / "global" / "snps" / "fev_formality").mkdir(parents=True)
        monkeypatch.setenv("ward", ward.as_posix())
        errors, emit = _collect_errors()
        result = resolve_domain("snps/fev_formality", emit)  # type: ignore[arg-type]
        assert result is not None
        assert result.domain_logical_name == "snps/fev_formality"
        assert result.ward_root == ward.resolve()
        assert result.domain_root == (ward / "global" / "snps" / "fev_formality").resolve()
        assert errors == []

    def test_vendor_qualified_not_found_emits_ve33(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ward = tmp_path / "ward"
        (ward / "global").mkdir(parents=True)
        monkeypatch.setenv("ward", ward.as_posix())
        errors, emit = _collect_errors()
        result = resolve_domain("snps/nonexistent", emit)  # type: ignore[arg-type]
        assert result is None
        assert len(errors) == 1
        assert errors[0].code == "VE-33"
        assert "snps/nonexistent" in errors[0].message

    def test_ward_not_set_vendor_qualified_emits_ve32(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ward", raising=False)
        errors, emit = _collect_errors()
        result = resolve_domain("snps/fev_formality", emit)  # type: ignore[arg-type]
        assert result is None
        assert len(errors) == 1
        assert errors[0].code == "VE-32"

    def test_vendor_qualified_ward_root_recorded(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """ward_root must be the resolved $ward, not None."""
        ward = tmp_path / "ward"
        (ward / "global" / "cdns" / "fev_formality").mkdir(parents=True)
        monkeypatch.setenv("ward", ward.as_posix())
        errors, emit = _collect_errors()
        result = resolve_domain("cdns/fev_formality", emit)  # type: ignore[arg-type]
        assert result is not None
        assert result.ward_root is not None
        assert result.ward_root == ward.resolve()

    def test_vendor_qualified_logical_name_format(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """domain_logical_name must be 'vendor/name' exactly."""
        ward = tmp_path / "ward"
        (ward / "global" / "snps" / "fev_eco").mkdir(parents=True)
        monkeypatch.setenv("ward", ward.as_posix())
        errors, emit = _collect_errors()
        result = resolve_domain("snps/fev_eco", emit)  # type: ignore[arg-type]
        assert result is not None
        assert result.domain_logical_name == "snps/fev_eco"


class TestBareNameOSError:
    def test_oserror_during_iterdir_emits_ve33(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An OSError from global_root.iterdir() must emit VE-33 and return None."""
        from unittest.mock import patch

        ward = tmp_path / "ward"
        global_dir = ward / "global"
        global_dir.mkdir(parents=True)
        monkeypatch.setenv("ward", ward.as_posix())

        errors, emit = _collect_errors()
        with patch("chopper.cli.domain_lookup.Path.iterdir", side_effect=OSError("perm denied")):
            result = resolve_domain("fev_formality", emit)  # type: ignore[arg-type]

        assert result is None
        assert len(errors) == 1
        assert errors[0].code == "VE-33"
        assert "perm denied" in errors[0].message

    def test_non_directory_entry_in_global_is_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Line 144: a regular file inside $ward/global/ triggers 'continue' and is skipped."""
        ward = tmp_path / "ward"
        global_dir = ward / "global"
        (global_dir / "snps" / "fev_formality").mkdir(parents=True)
        (global_dir / "not_a_vendor.txt").write_text("file")  # non-directory entry
        monkeypatch.setenv("ward", ward.as_posix())

        errors, emit = _collect_errors()
        result = resolve_domain("fev_formality", emit)  # type: ignore[arg-type]

        assert result is not None
        assert result.domain_logical_name == "snps/fev_formality"
        assert errors == []
