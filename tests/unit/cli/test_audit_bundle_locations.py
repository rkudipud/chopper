"""Tests for :func:`chopper.cli.render.render_audit_bundle_locations` (FR-52)."""

from __future__ import annotations

import io
from pathlib import Path

from chopper.cli.render import render_audit_bundle_locations


class TestSingleDomain:
    def test_prints_resolved_chopper_path(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        audit_root = tmp_path / "my_domain" / ".chopper"
        render_audit_bundle_locations([("my_domain", audit_root)], stream=buf)
        out = buf.getvalue()
        assert "The output logs of this run can be found at" in out
        assert audit_root.resolve().as_posix() in out
        # Single-domain form is one line, not the multi-domain banner.
        assert "=== Audit Bundle Locations ===" not in out

    def test_empty_list_prints_nothing(self) -> None:
        buf = io.StringIO()
        render_audit_bundle_locations([], stream=buf)
        assert buf.getvalue() == ""


class TestMultiDomain:
    def test_prints_one_line_per_domain(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        audit_a = tmp_path / "dom_a" / ".chopper"
        audit_b = tmp_path / "dom_b" / ".chopper"
        render_audit_bundle_locations(
            [("snps/fev_formality", audit_a), ("cdns/fev_conformal", audit_b)],
            stream=buf,
        )
        out = buf.getvalue()
        assert "=== Audit Bundle Locations ===" in out
        assert "snps/fev_formality" in out
        assert audit_a.resolve().as_posix() in out
        assert "cdns/fev_conformal" in out
        assert audit_b.resolve().as_posix() in out
